"""
基于 Lyapunov drift-plus-penalty 框架的预测性网关选择算法。

问题建模：
  决策变量：当前时隙选哪个网关 a(t) ∈ {1..N}（或保持当前 = "stay"）
  目标：长期平均代价
      cost(t) = α * 1{a(t) 不可见 OR ΔT_a(t) 即将耗尽}    （中断/转换失败惩罚）
             + β * L_{a(t)}(t)                              （所选网关负载惩罚）
             + γ * 1{a(t) ≠ a(t-1)}                         （切换瞬时代价）
  约束：长期平均切换率 ≤ C_max  （切换预算约束）

Lyapunov 方法：
  设虚拟队列 Q(t)，每次切换 +1，每个时隙 -C_max（仅减不为负）。
  drift + V*penalty 上界：
      Δ(t) + V·cost(t) ≤ B + Q(t)·(switch(t) - C_max) + V·cost(t)
  每时隙最小化 RHS（去掉常数）：
      a*(t) = argmin_a  V·cost_a(t) + Q(t)·1{a ≠ a(t-1)}

  → 这是一个对 N 个候选的逐点比较，O(N)，无需 CVXPY 即可解出闭式。
  → 闭式策略可证明 [O(1/V), O(V)] 的 utility-延迟权衡。

我们额外实现一个 CVXPY 离线最优批量求解器（用于生成模仿学习的"专家轨迹"，
对照在线 Lyapunov 解的紧致性，并在论文里作为性能上界画图）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from tqdm import tqdm

from config import CFG
from orbit.topology import TopologySnapshot


# --------------------------- 网关运行状态生成 ---------------------------
def synthesize_gateway_loads(num_gateways: int, num_steps: int,
                             rng: np.random.Generator) -> np.ndarray:
    """
    每个网关基础负载 + 一个慢变正弦分量（其他业务起伏）。
    输出形状 (T, N) ∈ [0, 1]。
    """
    base = rng.uniform(*CFG.gateway_base_load_range, size=num_gateways)
    t = np.arange(num_steps).reshape(-1, 1)
    phase = rng.uniform(0, 2 * np.pi, size=num_gateways).reshape(1, -1)
    freq = rng.uniform(1 / 600, 1 / 200, size=num_gateways).reshape(1, -1)
    osc = 0.2 * np.sin(2 * np.pi * freq * t + phase)
    L = base.reshape(1, -1) + osc + rng.normal(0, 0.02, size=(num_steps, num_gateways))
    return np.clip(L, 0.0, 1.0)


# --------------------------- 在线 Lyapunov 求解器 ---------------------------
@dataclass
class LyapunovDecision:
    target_gateway: int       # 选中的网关 index
    cost: float               # 该时隙瞬时 cost
    q_after: float            # 决策后虚拟队列长度
    is_switch: bool
    rationale: dict           # 各候选的得分，便于调试


@dataclass
class LyapunovTrajectory:
    """一段时间内 Lyapunov 在线决策的完整轨迹。供模仿学习训练。"""
    states: np.ndarray        # (T, state_dim)
    actions: np.ndarray       # (T,) int
    rewards: np.ndarray       # (T,)
    q_history: np.ndarray     # (T,)
    switch_count: int
    loads: np.ndarray         # (T, N) 记录的负载（state 已含，但单独保存方便分析）


def build_state_vector(topo: TopologySnapshot, t_idx: int,
                       loads: np.ndarray, current_gw: int) -> np.ndarray:
    """
    State = [ΔT_1..N, L_1..N, prop_delay_1..N, visible_1..N, current_gw_onehot]
    """
    N = topo.num_gateways
    rem = topo.remaining_visibility(t_idx)                   # (N,)
    L = loads[t_idx]                                         # (N,)
    delay = topo.prop_delay_ms[t_idx]                        # (N,)
    vis = topo.visible[t_idx].astype(float)                  # (N,)
    cur = np.zeros(N, dtype=float)
    if 0 <= current_gw < N:
        cur[current_gw] = 1.0
    # 归一化
    rem_n = rem / max(1.0, CFG.sim_duration_sec)
    delay_n = delay / 50.0  # ms scale
    return np.concatenate([rem_n, L, delay_n, vis, cur]).astype(np.float32)


def lyapunov_online(topo: TopologySnapshot, loads: np.ndarray,
                    initial_gw: Optional[int] = None,
                    V: float = None,
                    C_max: float = None,
                    alpha: float = None,
                    beta: float = None,
                    gamma_switch: float = 0.5,
                    interruption_horizon_sec: float = 5.0,
                    verbose: bool = False) -> LyapunovTrajectory:
    """
    在线 Lyapunov 决策。返回完整轨迹（state, action, reward）。
    """
    V = V if V is not None else CFG.V_lyapunov
    C_max = C_max if C_max is not None else CFG.switch_budget_per_sec
    alpha = alpha if alpha is not None else CFG.alpha
    beta = beta if beta is not None else CFG.beta

    T = topo.num_steps
    N = topo.num_gateways
    dt = float(topo.times_sec[1] - topo.times_sec[0])

    # 初始网关：选当前可见且 ΔT 最大者
    if initial_gw is None:
        rem0 = topo.remaining_visibility(0)
        initial_gw = int(np.argmax(rem0)) if rem0.max() > 0 else 0

    Q = 0.0
    current_gw = initial_gw
    actions = np.zeros(T, dtype=np.int64)
    rewards = np.zeros(T, dtype=np.float32)
    q_hist = np.zeros(T, dtype=np.float32)
    state_dim = 4 * N + N  # 与 build_state_vector 对齐
    states = np.zeros((T, state_dim), dtype=np.float32)
    switch_count = 0

    iterator = range(T)
    if verbose:
        iterator = tqdm(iterator, desc="Lyapunov online")

    for k in iterator:
        states[k] = build_state_vector(topo, k, loads, current_gw)
        rem = topo.remaining_visibility(k)
        L_k = loads[k]
        vis_k = topo.visible[k]

        # 计算每个候选的 instant cost
        best_a, best_score = current_gw, np.inf
        scores = np.full(N, np.inf, dtype=float)
        for a in range(N):
            # 中断惩罚：不可见 或 剩余可见时长太短
            interrupt = (not vis_k[a]) or (rem[a] < interruption_horizon_sec)
            cost_a = alpha * (1.0 if interrupt else 0.0) + beta * L_k[a]
            # 切换瞬时代价 + 虚拟队列引力
            switch_indicator = 0.0 if a == current_gw else 1.0
            score = V * (cost_a + gamma_switch * switch_indicator) + Q * switch_indicator
            scores[a] = score
            if score < best_score:
                best_score = score
                best_a = a

        is_switch = (best_a != current_gw)
        if is_switch:
            switch_count += 1
        # 实际产生的 cost（用于 reward 记录与虚拟队列更新）
        interrupt_real = (not vis_k[best_a]) or (rem[best_a] < interruption_horizon_sec)
        realized_cost = (alpha * (1.0 if interrupt_real else 0.0)
                         + beta * L_k[best_a]
                         + gamma_switch * (1.0 if is_switch else 0.0))
        rewards[k] = -realized_cost  # reward = -cost

        # 虚拟队列更新：Q(t+1) = max{Q(t) + switch - C_max*dt, 0}
        Q = max(Q + (1.0 if is_switch else 0.0) - C_max * dt, 0.0)
        q_hist[k] = Q
        actions[k] = best_a
        current_gw = best_a

    return LyapunovTrajectory(
        states=states, actions=actions, rewards=rewards,
        q_history=q_hist, switch_count=switch_count, loads=loads,
    )


# --------------------------- 离线最优批量求解（论文性能上界）---------------------------
def lyapunov_offline_optimal(topo: TopologySnapshot, loads: np.ndarray,
                             alpha: float = None, beta: float = None,
                             gamma_switch: float = 0.5,
                             max_switches: Optional[int] = None,
                             interruption_horizon_sec: float = 5.0) -> dict:
    """
    动态规划求"切换预算 K 下"的最小化代价（可作为论文中的最优下界）。
    复杂度 O(T·N·K) —— T 步、N 网关、K 切换预算。
    """
    alpha = alpha if alpha is not None else CFG.alpha
    beta = beta if beta is not None else CFG.beta
    T, N = topo.num_steps, topo.num_gateways
    if max_switches is None:
        dt = float(topo.times_sec[1] - topo.times_sec[0])
        max_switches = int(CFG.switch_budget_per_sec * T * dt) + 2

    # cost[t, a]
    inst = np.zeros((T, N), dtype=np.float32)
    for k in range(T):
        rem = topo.remaining_visibility(k)
        vis = topo.visible[k]
        for a in range(N):
            interrupt = (not vis[a]) or (rem[a] < interruption_horizon_sec)
            inst[k, a] = alpha * (1.0 if interrupt else 0.0) + beta * loads[k, a]

    INF = 1e9
    # dp[t][a][k] = min cost up to t, ending at gateway a with k switches used
    dp = np.full((T, N, max_switches + 1), INF, dtype=np.float32)
    parent = np.full((T, N, max_switches + 1, 2), -1, dtype=np.int32)
    # 初始：t=0，任意 a，0 切换
    for a in range(N):
        dp[0, a, 0] = inst[0, a]
    for t in range(1, T):
        for a in range(N):
            for k in range(max_switches + 1):
                # 保持
                v_stay = dp[t - 1, a, k] + inst[t, a]
                # 切换 from any a' != a
                v_sw = INF
                best_prev = -1
                if k > 0:
                    prev_vals = dp[t - 1, :, k - 1] + gamma_switch
                    prev_vals[a] = INF  # 同网关不算切换
                    best_prev = int(np.argmin(prev_vals))
                    v_sw = float(prev_vals[best_prev]) + inst[t, a]
                if v_stay <= v_sw:
                    dp[t, a, k] = v_stay
                    parent[t, a, k] = [a, k]
                else:
                    dp[t, a, k] = v_sw
                    parent[t, a, k] = [best_prev, k - 1]

    # 回溯最优解
    best_end = np.unravel_index(np.argmin(dp[-1]), dp[-1].shape)  # (a*, k*)
    a_star, k_star = int(best_end[0]), int(best_end[1])
    actions = np.zeros(T, dtype=np.int64)
    actions[-1] = a_star
    cur_a, cur_k = a_star, k_star
    for t in range(T - 1, 0, -1):
        prev_a, prev_k = parent[t, cur_a, cur_k]
        actions[t - 1] = prev_a
        cur_a, cur_k = int(prev_a), int(prev_k)
    total_cost = float(dp[-1, a_star, k_star])
    n_switch = int(np.sum(actions[1:] != actions[:-1]))
    return {
        "actions": actions,
        "total_cost": total_cost,
        "num_switches": n_switch,
        "max_switches_used": k_star,
    }


if __name__ == "__main__":
    # 自检
    from orbit.topology import get_or_build_topology
    topo, _, _ = get_or_build_topology("smoke", 300.0, step_sec=1.0, use_fallback_tle=True)
    rng = np.random.default_rng(0)
    loads = synthesize_gateway_loads(topo.num_gateways, topo.num_steps, rng)
    traj = lyapunov_online(topo, loads, verbose=True)
    print(f"[lyap-online] switches={traj.switch_count} mean_reward={traj.rewards.mean():.4f}")
    opt = lyapunov_offline_optimal(topo, loads, max_switches=traj.switch_count + 3)
    print(f"[lyap-offline-opt] cost={opt['total_cost']:.2f} switches={opt['num_switches']}")
