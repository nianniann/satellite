"""
读取 run_all_results.pkl，出 8 张论文图。
风格：科研论文常见的简洁配色。
"""
from __future__ import annotations

import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from config import FIG_DIR, RESULTS_DIR


plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "legend.fontsize": 9,
    "figure.dpi": 110,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})

COLOR_MAP = {
    "Reactive": "#888888",
    "Max-Visibility": "#4477AA",
    "MPTCP-style": "#EE6677",
    "Pure-DRL": "#CCBB44",
    "Ours-Lyap": "#228833",
    "Ours-IL": "#AA3377",
}


def load_results(fp: Path = None):
    fp = fp or (RESULTS_DIR / "run_all_results.pkl")
    with open(fp, "rb") as f:
        return pickle.load(f)


# --------------------------- 图1：星座拓扑与可见窗口 ---------------------------
def fig1_visibility_window(data, fp: Path):
    topo = data["test_topo"]
    fig, ax = plt.subplots(figsize=(10, 4))
    for j in range(topo.num_gateways):
        ax.fill_between(topo.times_sec, j, j + 0.8,
                        where=topo.visible[:, j],
                        color=plt.cm.tab10(j % 10), alpha=0.7,
                        label=topo.gateway_names[j][:15])
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Candidate IPv6 gateway")
    ax.set_yticks([j + 0.4 for j in range(topo.num_gateways)])
    ax.set_yticklabels([n[:15] for n in topo.gateway_names])
    ax.set_title(f"Fig.1 AOS→Gateway visibility windows ({topo.aos_name})")
    ax.set_xlim(0, topo.times_sec[-1])
    plt.savefig(fp)
    plt.close()


# --------------------------- 图2：Lyapunov V 参数扫描 ---------------------------
def fig2_lyapunov_v_sweep(data, fp: Path):
    """重新跑 Lyapunov，扫不同 V 看 utility-延迟权衡。"""
    from optimizer.lyapunov_solver import lyapunov_online
    topo = data["test_topo"]
    loads = data["test_loads"]
    Vs = [1, 5, 10, 50, 100, 500, 1000]
    avg_cost, avg_switch_rate = [], []
    for V in Vs:
        traj = lyapunov_online(topo, loads, V=V)
        avg_cost.append(float(-traj.rewards.mean()))
        avg_switch_rate.append(traj.switch_count / topo.num_steps)
    fig, ax1 = plt.subplots(figsize=(6, 4))
    ax1.set_xscale("log")
    l1 = ax1.plot(Vs, avg_cost, "o-", color="#228833", label="Average cost")
    ax1.set_xlabel("Lyapunov parameter V")
    ax1.set_ylabel("Average cost", color="#228833")
    ax2 = ax1.twinx()
    l2 = ax2.plot(Vs, avg_switch_rate, "s--", color="#EE6677", label="Switch rate")
    ax2.set_ylabel("Switch rate (per step)", color="#EE6677")
    ax1.set_title("Fig.2 Lyapunov V utility–switch trade-off")
    plt.savefig(fp)
    plt.close()


# --------------------------- 图3：IL 训练曲线 ---------------------------
def fig3_il_training_curve(data, fp: Path):
    hist = data["il_history"]
    fig, ax = plt.subplots(figsize=(6, 4))
    eps = np.arange(len(hist["train_loss"]))
    ax.plot(eps, hist["train_loss"], label="train loss")
    ax.plot(eps, hist["val_loss"], label="val loss")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Behavior cloning loss")
    ax2 = ax.twinx()
    ax2.plot(eps, hist["val_acc"], "g--", label="val accuracy")
    ax2.set_ylabel("Action match accuracy", color="green")
    ax.set_title("Fig.3 Imitation learning training (GPU)")
    ax.legend(loc="upper left")
    ax2.legend(loc="lower right")
    plt.savefig(fp)
    plt.close()


# --------------------------- 图4：丢包率时序对比 ---------------------------
def fig4_loss_rate_timeseries(data, fp: Path):
    fig, ax = plt.subplots(figsize=(10, 4))
    for name, res in data["results"].items():
        t, rate = res.loss_rate_timeseries(bin_sec=2.0)
        if len(t) == 0:
            continue
        ax.plot(t, rate * 100, label=name, color=COLOR_MAP.get(name), lw=1.2)
    # 标记切换瞬间
    for name in ("Reactive", "Ours-Lyap"):
        for s in data["results"][name].switches:
            ax.axvline(s.decision_at_sec, color=COLOR_MAP.get(name),
                       alpha=0.15, lw=0.6)
    ax.set_xlabel("Simulation time (s)")
    ax.set_ylabel("Packet loss rate (%)")
    ax.set_title("Fig.4 Packet loss rate over time — switches spike traditional methods")
    ax.legend(ncol=3, fontsize=8)
    plt.savefig(fp)
    plt.close()


# --------------------------- 图5：端到端延迟 CDF ---------------------------
def fig5_e2e_latency_cdf(data, fp: Path):
    fig, ax = plt.subplots(figsize=(6, 4))
    for name, res in data["results"].items():
        lats = [(r.delivered_at_sec - r.sent_at_sec) * 1000
                for r in res.frames if not r.dropped and r.delivered_at_sec is not None]
        if not lats:
            continue
        lats = np.sort(lats)
        cdf = np.linspace(0, 1, len(lats))
        ax.plot(lats, cdf, label=name, color=COLOR_MAP.get(name))
    ax.set_xlabel("End-to-end latency (ms)")
    ax.set_ylabel("CDF")
    ax.set_title("Fig.5 End-to-end latency CDF")
    ax.set_xscale("log")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.savefig(fp)
    plt.close()


# --------------------------- 图6：状态迁移开销分解 ---------------------------
def fig6_migration_overhead(data, fp: Path):
    """对 Ours-Lyap 方案，逐次切换的 static/dynamic 字节与 sync time。"""
    swrec = data["results"]["Ours-Lyap"].switches
    if not swrec:
        # 没有切换时画占位提示
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No handoffs in test scenario",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Fig.6 Migration overhead (Ours-Lyap)")
        plt.savefig(fp); plt.close()
        return
    idx = np.arange(len(swrec))
    sync_ms = [s.sync_time_sec * 1000 for s in swrec]
    mig = [s.fragments_migrated for s in swrec]
    drop = [s.fragments_dropped for s in swrec]
    outcomes = [s.outcome for s in swrec]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    bars = ax1.bar(idx, sync_ms, color=["#228833" if o == "seamless"
                                         else "#EE6677" if o == "degraded"
                                         else "#888888"
                                         for o in outcomes])
    ax1.axhline(500, color="red", ls="--", lw=1, label="T_phys = 500ms")
    ax1.set_ylabel("Sync time (ms)")
    ax1.set_title("Fig.6 Migration overhead per handoff (Ours-Lyap)")
    ax1.legend()
    ax2.bar(idx, mig, color="#228833", label="migrated")
    ax2.bar(idx, drop, bottom=mig, color="#EE6677", label="dropped")
    ax2.set_xlabel("Handoff index")
    ax2.set_ylabel("Fragments")
    ax2.legend()
    plt.savefig(fp)
    plt.close()


# --------------------------- 图7：负载均衡度 ---------------------------
def fig7_load_balance(data, fp: Path):
    fig, ax = plt.subplots(figsize=(8, 4))
    names = list(data["results"].keys())
    width = 0.13
    N_gw = data["test_topo"].num_gateways
    x = np.arange(N_gw)
    for i, name in enumerate(names):
        usage = data["results"][name].gateway_usage_count
        counts = np.array([usage.get(j, 0) for j in range(N_gw)])
        ax.bar(x + i * width, counts, width, label=name,
               color=COLOR_MAP.get(name))
    ax.set_xticks(x + width * (len(names) - 1) / 2)
    ax.set_xticklabels([f"GW{j}" for j in range(N_gw)])
    ax.set_ylabel("Packets handled")
    ax.set_title("Fig.7 Load balance across gateways")
    ax.legend(ncol=3, fontsize=8)
    plt.savefig(fp)
    plt.close()


# --------------------------- 图8：综合指标对比 ---------------------------
def fig8_summary_bars(data, fp: Path):
    summaries = data["summaries"]
    names = list(summaries.keys())
    metrics = ["plr", "e2e_ms", "num_switches", "total_interrupt_sec"]
    metric_titles = {
        "plr": "Packet loss rate (%)",
        "e2e_ms": "Avg E2E latency (ms)",
        "num_switches": "Number of handoffs",
        "total_interrupt_sec": "Total interrupt (s)",
    }
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax, m in zip(axes, metrics):
        vals = [summaries[n][m] * (100 if m == "plr" else 1) for n in names]
        bars = ax.bar(range(len(names)), vals,
                      color=[COLOR_MAP.get(n) for n in names])
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=30, ha="right")
        ax.set_title(metric_titles[m])
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                    f"{v:.2f}", ha="center", va="bottom", fontsize=8)
    fig.suptitle("Fig.8 Summary comparison across schemes")
    plt.savefig(fp)
    plt.close()


# --------------------------- 主入口 ---------------------------
def main():
    data = load_results()
    fig1_visibility_window(data, FIG_DIR / "fig1_visibility.png")
    fig2_lyapunov_v_sweep(data, FIG_DIR / "fig2_lyapunov_V.png")
    fig3_il_training_curve(data, FIG_DIR / "fig3_il_training.png")
    fig4_loss_rate_timeseries(data, FIG_DIR / "fig4_loss_rate.png")
    fig5_e2e_latency_cdf(data, FIG_DIR / "fig5_latency_cdf.png")
    fig6_migration_overhead(data, FIG_DIR / "fig6_migration_overhead.png")
    fig7_load_balance(data, FIG_DIR / "fig7_load_balance.png")
    fig8_summary_bars(data, FIG_DIR / "fig8_summary.png")
    print(f"✅ 已生成 8 张图到 {FIG_DIR}")


if __name__ == "__main__":
    main()
