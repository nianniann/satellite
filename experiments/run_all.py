"""
主实验脚本：完整 pipeline。

阶段：
  1) 加载/构建拓扑（真实 Starlink + Iridium-NEXT TLE，失败回退合成）
  2) 生成训练集（多条 Lyapunov 离线最优轨迹）→ 模仿学习（IL）训练
  3) 训练 Pure DRL（DQN 消融）
  4) 在多个 test load 种子上跑 6 个方案 → 报均值±std
  5) IL 推理延迟基准（GPU vs CPU），证明星上部署可行
  6) 落盘所有结果 → plot_figures.py 出图

每个方案配置：
  方案                | 决策算法          | 状态迁移
  Reactive            | reactive          | hard
  Max-Visibility      | max_visibility    | hard
  MPTCP-style         | mptcp_style       | hard（软切但无状态迁移）
  Pure DRL            | DQN               | hard
  Ours (Lyap)         | Lyapunov 在线     | 两阶段 + Gossip
  Ours (IL)           | IL 网络（GPU 训）  | 两阶段 + Gossip
"""
from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

import numpy as np
import torch
from tqdm import tqdm

from config import CFG, RESULTS_DIR, get_device
from orbit.topology import get_or_build_topology
from optimizer.lyapunov_solver import (
    lyapunov_online, lyapunov_offline_optimal,
    synthesize_gateway_loads, build_state_vector,
)
from optimizer.policy_net import build_il_dataset, train_il
from network.simpy_env import run_simulation
from baselines.reactive import reactive_decision_fn
from baselines.max_visibility import max_visibility_decision_fn
from baselines.mptcp_style import mptcp_style_decision_fn
from baselines.pure_drl import train_dqn, dqn_decision_fn


# --------------------------- 实验配置 ---------------------------
RUN_CFG = dict(
    train_duration_sec=3600.0,   # 训练拓扑时长（60 分钟）
    test_duration_sec=1800.0,    # 测试拓扑时长（30 分钟）
    step_sec=1.0,
    num_train_scenarios=8,       # 训练负载随机种子数
    num_test_seeds=5,            # 测试负载随机种子数（用于报均值±std）
    aos_rate_pps=300.0,          # 单流速率，300pps 对协议转换是中等压力
    # 真实 Starlink TLE 取出的相邻轨道面卫星几乎共面，AOS 几乎总能看到同一颗
    # 给不了有意义的切换决策；用合成星座（synth_constellation）能控制几何
    # 在 30 min 内提供 2-4 次真实切换需求。
    use_fallback_tle=True,
    il_epochs=60,                # GPU 上 60 epoch 已收敛
    il_hidden_dim=128,           # 稍微加大网络
    dqn_epochs=15,               # DQN 受 Python 循环限速，过多 epoch 收益小
)


# --------------------------- 工具 ---------------------------
def _il_decision_fn(model, topo, loads):
    state = {"cur": None}

    def decide(t_idx: int) -> int:
        if state["cur"] is None:
            r0 = topo.remaining_visibility(0)
            state["cur"] = int(np.argmax(r0)) if r0.max() > 0 else 0
        s = build_state_vector(topo, t_idx, loads, state["cur"])
        a = model.predict(s, visible_mask=topo.visible[t_idx])
        state["cur"] = a
        return a

    return decide


def _lyap_online_decision_fn(traj):
    def decide(t_idx: int) -> int:
        return int(traj.actions[t_idx])
    return decide


def _summarize(results) -> dict:
    plr = results.packet_loss_rate()
    e2e = results.avg_e2e_latency_ms()
    n_sw = len(results.switches)
    drop_during_switch = sum(s.fragments_dropped for s in results.switches)
    interrupt_total = sum(s.interrupt_sec for s in results.switches)
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


def _agg_mean_std(per_seed: list[dict]) -> dict:
    """对多种子结果做均值/std。非标量字段（如 gateway_usage dict）跳过。"""
    if not per_seed:
        return {}
    keys = [k for k, v in per_seed[0].items()
            if isinstance(v, (int, float, np.integer, np.floating))]
    out = {}
    for k in keys:
        vals = np.array([float(d[k]) for d in per_seed], dtype=float)
        out[k] = {"mean": float(vals.mean()), "std": float(vals.std(ddof=0)),
                  "values": vals.tolist()}
    return out


# --------------------------- 推理延迟基准 ---------------------------
def benchmark_inference_latency(model, sample_state: np.ndarray,
                                visible_mask: np.ndarray,
                                num_iters: int = 2000) -> dict:
    """对比 IL 网络在 GPU 和 CPU 上的单次推理延迟。"""
    out = {}
    for dev_name in ("gpu", "cpu"):
        if dev_name == "gpu" and not torch.cuda.is_available():
            continue
        dev = get_device() if dev_name == "gpu" else torch.device("cpu")
        m = type(model)(model.state_dim, model.num_gateways).to(dev)
        m.load_state_dict(model.state_dict())
        m.eval()
        # 预热
        for _ in range(50):
            m.predict(sample_state, visible_mask=visible_mask)
        if dev.type == "cuda":
            torch.cuda.synchronize(dev)
        t0 = time.perf_counter()
        for _ in range(num_iters):
            m.predict(sample_state, visible_mask=visible_mask)
        if dev.type == "cuda":
            torch.cuda.synchronize(dev)
        dt_ms = (time.perf_counter() - t0) / num_iters * 1000.0
        out[dev_name] = dt_ms
    return out


# --------------------------- 主流程 ---------------------------
def main():
    np.random.seed(CFG.seed)
    torch.manual_seed(CFG.seed)
    device = get_device()
    print("=" * 70)
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"  GPU name: {torch.cuda.get_device_name(device)}")
        free, total = torch.cuda.mem_get_info(device)
        print(f"  GPU memory: free {free/1e9:.1f}GB / total {total/1e9:.1f}GB")
    # 把 RUN_CFG 中的 IL 超参回写到 CFG，方便 train_il 使用
    CFG.il_epochs = RUN_CFG["il_epochs"]
    CFG.il_hidden_dim = RUN_CFG["il_hidden_dim"]
    print("=" * 70)

    print("Stage 1: 构建拓扑")
    print("-" * 70)
    test_topo, _, _ = get_or_build_topology(
        cache_name="test",
        duration_sec=RUN_CFG["test_duration_sec"],
        step_sec=RUN_CFG["step_sec"],
        use_fallback_tle=RUN_CFG["use_fallback_tle"],
    )
    print(f"test topo: T={test_topo.num_steps} N={test_topo.num_gateways}")
    print(f"  per-gateway visibility ratio: "
          f"{np.round(test_topo.visible.mean(axis=0), 3).tolist()}")

    train_topo, _, _ = get_or_build_topology(
        cache_name="train",
        duration_sec=RUN_CFG["train_duration_sec"],
        step_sec=RUN_CFG["step_sec"],
        use_fallback_tle=RUN_CFG["use_fallback_tle"],
    )

    print("\n" + "=" * 70)
    print("Stage 2: 生成 Lyapunov 专家轨迹 → 训练 IL 网络（GPU）")
    print("=" * 70)
    expert_trajs = []
    for k in tqdm(range(RUN_CFG["num_train_scenarios"]), desc="expert traj"):
        rng = np.random.default_rng(CFG.seed + k)
        loads = synthesize_gateway_loads(train_topo.num_gateways, train_topo.num_steps, rng)
        traj = lyapunov_online(train_topo, loads)
        expert_trajs.append(traj)
    print(f"训练场景 {RUN_CFG['num_train_scenarios']} 条 | "
          f"平均切换/场景 = "
          f"{np.mean([t.switch_count for t in expert_trajs]):.1f}")

    ds = build_il_dataset(expert_trajs)
    print(f"IL dataset: {len(ds.states)} samples, state_dim={ds.states.shape[1]}")
    il_out = train_il(ds, train_topo.num_gateways,
                      epochs=RUN_CFG["il_epochs"], tag="ours_il", verbose=True)
    il_model = il_out["model"]
    print(f"IL 最终 val_acc={il_out['history']['val_acc'][-1]:.4f} | "
          f"val_loss={il_out['history']['val_loss'][-1]:.4f}")
    print(f"IL ckpt: {il_out['ckpt']}")

    print("\n" + "=" * 70)
    print("Stage 3: 训练 Pure DRL (DQN) — 消融对比")
    print("=" * 70)
    dqn_loads = [synthesize_gateway_loads(train_topo.num_gateways, train_topo.num_steps,
                                          np.random.default_rng(CFG.seed + 100 + k))
                 for k in range(RUN_CFG["num_train_scenarios"])]
    dqn_out = train_dqn([train_topo] * RUN_CFG["num_train_scenarios"], dqn_loads,
                        epochs=RUN_CFG["dqn_epochs"], tag="ablation_dqn", verbose=True)
    print(f"DQN 最终平均 reward = {dqn_out['history'][-1]:.4f} "
          f"(对比 IL 专家 = {np.mean([t.rewards.mean() for t in expert_trajs]):.4f})")

    print("\n" + "=" * 70)
    print(f"Stage 4: 在 {RUN_CFG['num_test_seeds']} 个测试种子上跑全部方案")
    print("=" * 70)
    scheme_names = ["Reactive", "Max-Visibility", "MPTCP-style",
                    "Pure-DRL", "Ours-Lyap", "Ours-IL"]
    # 收集 [scheme] -> [seed] -> SimResults
    results_by_scheme: dict[str, list] = {n: [] for n in scheme_names}
    summaries_by_scheme: dict[str, list[dict]] = {n: [] for n in scheme_names}
    test_loads_by_seed = []
    lyap_trajs = []

    # 第一个种子的离线最优 + 拓扑用于详细图（migration overhead 等）
    opt_info_first = None

    for s_idx in range(RUN_CFG["num_test_seeds"]):
        seed_v = CFG.seed + 999 + s_idx
        test_loads = synthesize_gateway_loads(
            test_topo.num_gateways, test_topo.num_steps,
            np.random.default_rng(seed_v),
        )
        test_loads_by_seed.append(test_loads)

        if s_idx == 0:
            opt_info_first = lyapunov_offline_optimal(
                test_topo, test_loads,
                max_switches=int(test_topo.num_steps * 0.05),
            )
            print(f"[seed#{s_idx}] Offline-optimal cost="
                  f"{opt_info_first['total_cost']:.2f} "
                  f"switches={opt_info_first['num_switches']}")

        lyap_traj = lyapunov_online(test_topo, test_loads)
        lyap_trajs.append(lyap_traj)

        scenarios = {
            "Reactive":       dict(decision=reactive_decision_fn(test_topo),
                                   two_phase=False, consistency=False),
            "Max-Visibility": dict(decision=max_visibility_decision_fn(test_topo),
                                   two_phase=False, consistency=False),
            "MPTCP-style":    dict(decision=mptcp_style_decision_fn(test_topo, test_loads),
                                   two_phase=False, consistency=False),
            "Pure-DRL":       dict(decision=dqn_decision_fn(dqn_out["model"], test_topo,
                                                              test_loads, dqn_out["device"]),
                                   two_phase=False, consistency=False),
            "Ours-Lyap":      dict(decision=_lyap_online_decision_fn(lyap_traj),
                                   two_phase=True, consistency=True),
            "Ours-IL":        dict(decision=_il_decision_fn(il_model, test_topo, test_loads),
                                   two_phase=True, consistency=True),
        }

        print(f"\n--- seed#{s_idx} (={seed_v}) ---")
        for name, conf in scenarios.items():
            res = run_simulation(
                test_topo, test_loads, decision_fn=conf["decision"],
                sim_duration=RUN_CFG["test_duration_sec"],
                aos_rate_pps=RUN_CFG["aos_rate_pps"],
                do_two_phase=conf["two_phase"],
                enable_consistency=conf["consistency"],
                seed=seed_v,
            )
            results_by_scheme[name].append(res)
            s = _summarize(res)
            summaries_by_scheme[name].append(s)
            print(f"  {name:14s}  PLR={s['plr']*100:6.3f}%  "
                  f"e2e={s['e2e_ms']:7.2f}ms  switches={s['num_switches']:3d}  "
                  f"drop_in_switch={s['fragments_dropped_in_switch']:4d}  "
                  f"interrupt={s['total_interrupt_sec']:6.2f}s")

    # 聚合统计
    agg = {name: _agg_mean_std(summaries_by_scheme[name]) for name in scheme_names}
    print("\n" + "=" * 70)
    print("聚合结果（mean ± std，跨 test seeds）")
    print("=" * 70)
    print(f"{'Scheme':<16s} {'PLR(%)':<16s} {'E2E(ms)':<16s} "
          f"{'#switch':<14s} {'interrupt(s)':<16s}")
    for name in scheme_names:
        a = agg[name]
        plr = a["plr"]; e2e = a["e2e_ms"]; sw = a["num_switches"]; ir = a["total_interrupt_sec"]
        print(f"{name:<16s} "
              f"{plr['mean']*100:6.3f}±{plr['std']*100:5.3f}  "
              f"{e2e['mean']:7.2f}±{e2e['std']:5.2f}    "
              f"{sw['mean']:5.1f}±{sw['std']:4.1f}   "
              f"{ir['mean']:6.2f}±{ir['std']:5.2f}")

    # 推理延迟基准
    print("\n" + "=" * 70)
    print("Stage 5: IL 推理延迟基准（GPU vs CPU）")
    print("=" * 70)
    sample_state = build_state_vector(test_topo, 0, test_loads_by_seed[0],
                                      current_gw=0)
    inf_lat = benchmark_inference_latency(
        il_model, sample_state,
        visible_mask=test_topo.visible[0],
    )
    for k, v in inf_lat.items():
        print(f"  IL inference on {k}: {v:.4f} ms / call")

    # 落盘
    print("\n" + "=" * 70)
    print("Stage 6: 写结果")
    print("=" * 70)
    out_fp = RESULTS_DIR / "run_all_results.pkl"
    with open(out_fp, "wb") as f:
        pickle.dump({
            "device": str(device),
            "run_cfg": RUN_CFG,
            "test_topo": test_topo,
            # 第一种子的代表性数据，供详细图使用
            "test_loads": test_loads_by_seed[0],
            "lyap_traj": lyap_trajs[0],
            "opt_info": opt_info_first,
            "il_history": il_out["history"],
            "dqn_history": dqn_out["history"],
            # 主图用单种子的 results（保留原 plot_figures 的 API 兼容）
            "results": {n: results_by_scheme[n][0] for n in scheme_names},
            "summaries": {n: summaries_by_scheme[n][0] for n in scheme_names},
            # 多种子原始数据 + 聚合统计
            "results_all_seeds": results_by_scheme,
            "summaries_all_seeds": summaries_by_scheme,
            "summary_agg": agg,
            "inference_latency_ms": inf_lat,
        }, f)
    print(f"✅ 全部结果落盘: {out_fp}")

    # 摘要 JSON
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
    summary_fp.write_text(json.dumps({
        "device": str(device),
        "run_cfg": RUN_CFG,
        "summary_agg": _to_jsonable(agg),
        "inference_latency_ms": inf_lat,
    }, indent=2, ensure_ascii=False))
    print(f"✅ 摘要 JSON: {summary_fp}")


if __name__ == "__main__":
    main()
