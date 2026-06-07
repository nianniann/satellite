"""
主实验脚本：串通整个 pipeline。

阶段：
  1) 加载/构建拓扑（真实 Starlink TLE，失败回退合成）
  2) 生成训练集（多条 Lyapunov 离线最优轨迹）→ 模仿学习训练
  3) 训练 Pure DRL（消融）
  4) 在测试拓扑上跑 5 个方案 → 各自一次完整 SimPy 仿真
  5) 落盘所有结果 → plot_figures.py 出图

每个方案配置：
  方案                | 决策算法          | 状态迁移
  Reactive            | reactive          | hard
  Max-Visibility      | max_visibility    | hard
  MPTCP-style         | mptcp_style       | hard（软切但无状态迁移）
  Pure DRL            | DQN              | hard
  Ours (Lyap + IL)    | Lyapunov 在线/IL  | 两阶段
"""
from __future__ import annotations

import json
import pickle
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from tqdm import tqdm

from config import CFG, RESULTS_DIR, FIG_DIR, CKPT_DIR, get_device
from orbit.topology import get_or_build_topology
from optimizer.lyapunov_solver import (
    lyapunov_online, lyapunov_offline_optimal,
    synthesize_gateway_loads,
)
from optimizer.policy_net import build_il_dataset, train_il, load_policy
from network.simpy_env import run_simulation
from baselines.reactive import reactive_decision_fn
from baselines.max_visibility import max_visibility_decision_fn
from baselines.mptcp_style import mptcp_style_decision_fn
from baselines.pure_drl import train_dqn, dqn_decision_fn


# --------------------------- 实验配置 ---------------------------
RUN_CFG = dict(
    train_duration_sec=2400.0,   # 训练拓扑时长（40 分钟）
    test_duration_sec=1800.0,    # 测试拓扑时长（30 分钟）
    step_sec=1.0,
    num_train_scenarios=6,       # 每个场景一组负载随机种子
    aos_rate_pps=300.0,
    use_fallback_tle=False,      # 优先真实 TLE
    il_epochs=40,
    dqn_epochs=20,
)


# --------------------------- 工具 ---------------------------
def _il_decision_fn(model, topo, loads, device):
    state = {"cur": None}

    def decide(t_idx: int) -> int:
        if state["cur"] is None:
            r0 = topo.remaining_visibility(0)
            state["cur"] = int(np.argmax(r0)) if r0.max() > 0 else 0
        from optimizer.lyapunov_solver import build_state_vector
        s = build_state_vector(topo, t_idx, loads, state["cur"])
        a = model.predict(s, visible_mask=topo.visible[t_idx])
        state["cur"] = a
        return a

    return decide


def _lyap_online_decision_fn(traj):
    """直接用预生成的 Lyapunov 在线决策序列。"""
    def decide(t_idx: int) -> int:
        return int(traj.actions[t_idx])
    return decide


def _summarize(results, switches=None):
    plr = results.packet_loss_rate()
    e2e = results.avg_e2e_latency_ms()
    n_sw = len(results.switches)
    drop_during_switch = sum(s.fragments_dropped for s in results.switches)
    interrupt_total = sum(s.interrupt_sec for s in results.switches)
    # 负载均衡度：使用次数的变异系数（CV）
    usage = list(results.gateway_usage_count.values()) or [0]
    cv = float(np.std(usage) / max(1.0, np.mean(usage)))
    return dict(
        plr=plr, e2e_ms=e2e, num_switches=n_sw,
        fragments_dropped_in_switch=drop_during_switch,
        total_interrupt_sec=interrupt_total,
        gateway_usage=results.gateway_usage_count,
        gateway_usage_cv=cv,
        gossip_rounds=results.gossip_rounds,
        gossip_evictions=results.gossip_evictions,
        static_replicas_installed=results.static_replicas_installed,
        static_bytes_replicated=results.static_bytes_replicated,
    )


# --------------------------- 主流程 ---------------------------
def main():
    np.random.seed(CFG.seed)
    torch.manual_seed(CFG.seed)

    print("=" * 70)
    print("Stage 1: 构建拓扑")
    print("=" * 70)
    test_topo, _, _ = get_or_build_topology(
        cache_name="test",
        duration_sec=RUN_CFG["test_duration_sec"],
        step_sec=RUN_CFG["step_sec"],
        use_fallback_tle=RUN_CFG["use_fallback_tle"],
    )
    print(f"test topo: T={test_topo.num_steps} N={test_topo.num_gateways}")
    print(f"  per-gateway visibility ratio: {test_topo.visible.mean(axis=0)}")

    train_topo, _, _ = get_or_build_topology(
        cache_name="train",
        duration_sec=RUN_CFG["train_duration_sec"],
        step_sec=RUN_CFG["step_sec"],
        use_fallback_tle=RUN_CFG["use_fallback_tle"],
    )

    print("\n" + "=" * 70)
    print("Stage 2: 生成 Lyapunov 专家轨迹 → 训练 IL 网络")
    print("=" * 70)
    expert_trajs = []
    for k in tqdm(range(RUN_CFG["num_train_scenarios"]), desc="expert traj"):
        rng = np.random.default_rng(CFG.seed + k)
        loads = synthesize_gateway_loads(train_topo.num_gateways, train_topo.num_steps, rng)
        traj = lyapunov_online(train_topo, loads)
        expert_trajs.append(traj)
        print(f"  scenario {k}: switches={traj.switch_count} "
              f"mean_reward={traj.rewards.mean():.4f}")

    ds = build_il_dataset(expert_trajs)
    print(f"\nIL dataset: {len(ds.states)} samples, state_dim={ds.states.shape[1]}")
    il_out = train_il(ds, train_topo.num_gateways,
                      epochs=RUN_CFG["il_epochs"], tag="ours_il", verbose=True)
    il_model = il_out["model"]
    print(f"IL ckpt: {il_out['ckpt']}")

    print("\n" + "=" * 70)
    print("Stage 3: 训练 Pure DRL (DQN) — 消融对比")
    print("=" * 70)
    dqn_loads = [synthesize_gateway_loads(train_topo.num_gateways, train_topo.num_steps,
                                          np.random.default_rng(CFG.seed + 100 + k))
                 for k in range(RUN_CFG["num_train_scenarios"])]
    dqn_out = train_dqn([train_topo] * RUN_CFG["num_train_scenarios"], dqn_loads,
                        epochs=RUN_CFG["dqn_epochs"], tag="ablation_dqn", verbose=True)

    print("\n" + "=" * 70)
    print("Stage 4: 在测试拓扑上跑全部方案")
    print("=" * 70)
    test_loads = synthesize_gateway_loads(
        test_topo.num_gateways, test_topo.num_steps,
        np.random.default_rng(CFG.seed + 999),
    )
    # 离线最优（论文中作为性能下界画图）
    opt_info = lyapunov_offline_optimal(test_topo, test_loads,
                                        max_switches=int(test_topo.num_steps * 0.05))
    print(f"Offline-optimal cost={opt_info['total_cost']:.2f} "
          f"switches={opt_info['num_switches']}")

    # 在线 Lyapunov 决策序列（理论方案）
    lyap_traj = lyapunov_online(test_topo, test_loads)
    print(f"Online Lyapunov switches={lyap_traj.switch_count}")

    # 6 个方案
    scenarios = {
        "Reactive":        dict(decision=reactive_decision_fn(test_topo),
                                two_phase=False, consistency=False),
        "Max-Visibility":  dict(decision=max_visibility_decision_fn(test_topo),
                                two_phase=False, consistency=False),
        "MPTCP-style":     dict(decision=mptcp_style_decision_fn(test_topo, test_loads),
                                two_phase=False, consistency=False),
        "Pure-DRL":        dict(decision=dqn_decision_fn(dqn_out["model"], test_topo,
                                                          test_loads, dqn_out["device"]),
                                two_phase=False, consistency=False),
        "Ours-Lyap":       dict(decision=_lyap_online_decision_fn(lyap_traj),
                                two_phase=True, consistency=True),
        "Ours-IL":         dict(decision=_il_decision_fn(il_model, test_topo,
                                                          test_loads, get_device()),
                                two_phase=True, consistency=True),
    }

    all_results = {}
    for name, conf in scenarios.items():
        print(f"\n--- {name} ---")
        res = run_simulation(
            test_topo, test_loads, decision_fn=conf["decision"],
            sim_duration=RUN_CFG["test_duration_sec"],
            aos_rate_pps=RUN_CFG["aos_rate_pps"],
            do_two_phase=conf["two_phase"],
            enable_consistency=conf["consistency"],
        )
        all_results[name] = res
        s = _summarize(res)
        print(f"  PLR={s['plr']*100:.3f}% e2e={s['e2e_ms']:.2f}ms "
              f"switches={s['num_switches']} "
              f"drop_in_switch={s['fragments_dropped_in_switch']} "
              f"total_interrupt={s['total_interrupt_sec']:.2f}s "
              f"load_CV={s['gateway_usage_cv']:.3f}")

    # 落盘
    out_fp = RESULTS_DIR / "run_all_results.pkl"
    with open(out_fp, "wb") as f:
        pickle.dump({
            "test_topo": test_topo,
            "test_loads": test_loads,
            "lyap_traj": lyap_traj,
            "opt_info": opt_info,
            "il_history": il_out["history"],
            "dqn_history": dqn_out["history"],
            "results": all_results,
            "summaries": {k: _summarize(v) for k, v in all_results.items()},
        }, f)
    print(f"\n✅ 全部结果落盘: {out_fp}")

    # 摘要 JSON（人类可读）
    def _to_jsonable(obj):
        if isinstance(obj, dict):
            return {str(k): _to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_jsonable(x) for x in obj]
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        return obj

    summary_fp = RESULTS_DIR / "summary.json"
    summary_fp.write_text(json.dumps(
        {k: _to_jsonable(_summarize(v)) for k, v in all_results.items()},
        indent=2, ensure_ascii=False,
    ))
    print(f"✅ 摘要 JSON: {summary_fp}")


if __name__ == "__main__":
    main()
