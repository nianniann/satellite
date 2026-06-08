# 异构星座下协议转换网关切换与状态一致性迁移机制（创新点三）

> 大论文第五章配套代码实现。覆盖 Lyapunov 预测性网关选择、模仿学习加速、协议转换上下文两阶段迁移、多网关 Gossip 一致性，以及与 4 个对照基线的完整 SimPy 仿真。
>
> 在 NVIDIA L20X 单卡上，全流水线（拓扑 → 训练 → 30 次仿真 → 出图）一次跑通约 15 分钟，**5 个测试种子上稳定取得 PLR=0%、handoff 中断 0 s**。

---

## 1. 目录结构

```
sat_gateway_handoff/
├── config.py                      全局配置（物理常量、超参、设备选择）
├── data/tle/                      TLE 缓存（真实/合成）
├── orbit/
│   ├── skyfield_sim.py            轨道几何、ISL LOS、可见窗口预测
│   ├── synth_constellation.py     合成星座（默认使用，几何受控）
│   └── topology.py                时变拓扑张量 + .npz 缓存
├── network/
│   ├── aos_packet.py              AOS 帧 / M_PDU / CCSDS 分片
│   ├── ipv6_packet.py             IPv6 + UDP 报文
│   └── simpy_env.py               SimPy 事件驱动仿真环境
├── migration/
│   ├── context.py                 C_static / C_dynamic 数据结构（含 O(1) 完成检测）
│   ├── two_phase.py               Pre-copy + Stop-and-copy + 三层降级
│   └── consistency.py             Top-M 乐观复制 + Gossip 一致性
├── optimizer/
│   ├── lyapunov_solver.py         在线 drift-plus-penalty + 离线 DP 最优
│   └── policy_net.py              模仿学习策略网络（PyTorch / CUDA）
├── baselines/
│   ├── reactive.py                被动硬切换
│   ├── max_visibility.py          贪心可见性
│   ├── mptcp_style.py             带迟滞的软切换
│   └── pure_drl.py                DQN 消融
├── experiments/
│   ├── run_all.py                 完整流水线（训练 + 6 方案 × 5 seed 对比 + 出图）
│   └── plot_figures.py            9 张论文图
├── tests/                         31 个 pytest 单元 + 仿真集成测试
├── results/                       结果产物（不入版本控制）
│   ├── figures/                   fig1..fig9 png
│   ├── tensorboard/               IL / DQN 训练曲线
│   ├── checkpoints/               ours_il.pt, ablation_dqn.pt
│   ├── run_all_results.pkl        全量原始数据
│   ├── summary.json               人类可读的均值±std 摘要
│   ├── EXPERIMENT_REPORT.md       详细中文实验报告
│   └── run.log                    最后一次 make full 的日志
├── Makefile
├── requirements.txt
└── docs/
    ├── lyapunov_proof.md          性能界定理证明 + V 实测分析
    └── 创新点三-完整技术文档.md      v2 完整技术文档（含真实测试结果）
```

---

## 2. 安装

```bash
pip install -r requirements.txt
```

依赖：numpy、torch、skyfield、sgp4、simpy、cvxpy、matplotlib、tensorboard、tqdm、pytest。

> 注：本项目 `config.py:get_device()` 优先 CUDA，可用 `SAT_GPU_INDEX=N` 指定卡号；若无 GPU 自动回退到 CPU（强烈不建议，IL/DQN 训练会非常慢）。

---

## 3. 快速跑通

| 命令 | 用途 | 资源 |
|---|---|---|
| `make test` | 跑 pytest 单元测试（31 个）| < 10 s |
| `make full` | 完整实验：训练 + 6 方案 × 5 seed 对比 + 出图 | 1× GPU（默认 cuda:0），~15 min |
| `make full GPU=2` | 指定占用某张 GPU 卡 | - |
| `make figures` | 仅基于已有 pkl 重新出图 | < 1 min |
| `make tb` | 启动 TensorBoard 看训练曲线 | - |
| `make clean` | 清理 results/ 与拓扑缓存 | - |

> GPU 选择遵循 `SAT_GPU_INDEX` 环境变量（默认 0）。`Makefile` 会同时设置 `CUDA_VISIBLE_DEVICES`，保证只占用 1 张卡。

---

## 4. 模块依赖与运行原理

```
                  ┌─────────────┐
                  │  TLE source │  (合成 synth_constellation.py / CelesTrak)
                  └──────┬──────┘
                         ▼
                ┌──────────────────┐
                │ orbit/topology.py │  → (T × N) 距离/可见/带宽张量
                └────────┬─────────┘
        ┌────────────────┴───────────────────────┐
        ▼                                         ▼
┌───────────────────┐                  ┌────────────────────┐
│ Lyapunov solver   │  专家轨迹           │ network/simpy_env  │
│ (on-line + DP)    │ ─────────────►   │  (AOS sender →     │
└────────┬──────────┘                  │   gateways)        │
         │                              └─────┬──────────────┘
         ▼                                    │
┌────────────────────┐                        │
│ policy_net (PyTorch│ ─────────► IL decision_fn
│   IL on CUDA)      │            喂给仿真
└────────────────────┘                        │
                                              ▼
                                  ┌───────────────────────┐
                                  │ migration/two_phase   │
                                  │ + consistency Gossip  │
                                  └──────────┬────────────┘
                                             ▼
                                  ┌───────────────────────┐
                                  │ plot_figures.py       │
                                  │ → fig1..fig9 PNG      │
                                  └───────────────────────┘
```

---

## 5. 关键设计决策

### 5.1 为什么是 Lyapunov 优化而不是 DRL？
- 卫星星历完全可预测（不是随机过程）→ 确定性优化天然优于强化学习
- Lyapunov drift-plus-penalty 给出闭式 `O(1/V), O(V)` 权衡，**有定理证明**（见 `docs/lyapunov_proof.md`）
- 实测 Pure-DRL 在确定性场景下平均代价是 Lyapunov 专家的 4.7× 差
- Lyapunov 在线决策 < 1 ms

### 5.2 为什么仍训练一个模仿学习网络？
- 真实卫星载荷算力受限，IL（~45K 参数）推理 0.14 ms（CPU）/ 0.18 ms（GPU）
- 训练数据来自 Lyapunov 专家解，性能上界由 Lyapunov 决定，**不会比专家差**
- 实测 IL 网络在测试集上与 Lyapunov 给出 100% 一致的决策序列、`val_acc=99.91%`

### 5.3 为什么不只用 VM Live Migration？
本方案有 4 个 VM 迁移没有的卫星独有难点（详见 `docs/创新点三-完整技术文档.md` 第 2.4 节）：
1. CCSDS 分片重组缓存的迁移
2. VCID 级 QoS 队列状态
3. ISL 带宽时变受星历约束
4. 多目标网关并发覆盖的"状态分裂"问题

### 5.4 两阶段迁移的三层降级
当 `T_sync > T_physical_switch` 时：
1. **优选 ≥50% 完成度的分片** → DEGRADED-1
2. **只迁移高优先级 VCID（vcid ≤ 1）** → DEGRADED-2
3. **完全失败 → 回退硬切** → FAILED

> 实测中 30 min 仿真的所有切换均命中 L1 SEAMLESS（sync ≈ 30 ms ≪ T_phys = 500 ms）。

### 5.5 为什么默认用合成星座？
真实 Starlink TLE 中同一壳内相邻轨道面卫星几乎共面 → AOS 视角下某颗 Starlink 要么持续可见、要么持续不可见，没有切换决策可言。
`orbit/synth_constellation.py` 控制 AOS 87° 极轨 + 16 网关 53° 等 RAAN 间距分布，在 30 min 内提供 1-3 次有意义的切换机会。
要切换回真实 TLE，把 `experiments/run_all.py:RUN_CFG['use_fallback_tle']` 改为 `False` 即可。

---

## 6. 调参速查

`config.py` 中常用旋钮：

| 参数 | 含义 | 默认 |
|---|---|---|
| `sim_duration_sec` | 仿真时长 | 3600 |
| `num_candidate_gateways` | 候选网关数量 | 16 |
| `min_elevation_deg` | 最小通信仰角 | 10° |
| `isl_max_range_km` | ISL 最大距离 | 3500 km |
| `V_lyapunov` | Lyapunov utility-延迟权衡 | 50 |
| `switch_budget_per_sec` | 平均切换率上界 | 1/120 |
| `physical_switch_sec` | 物理切换窗口 | 0.5 s |
| `pre_copy_lead_sec` | Pre-copy 提前量 | 3 s |
| `il_epochs` / `il_hidden_dim` | IL 训练参数 | 60 / 128 |

`experiments/run_all.py:RUN_CFG` 中可覆盖：

| 参数 | 含义 | 默认 |
|---|---|---|
| `train_duration_sec` | 训练拓扑时长 | 3600 |
| `test_duration_sec` | 测试拓扑时长 | 1800 |
| `num_train_scenarios` | Lyapunov 专家场景数 | 8 |
| `num_test_seeds` | 测试负载种子数（mean±std）| 5 |
| `aos_rate_pps` | AOS 单流速率 | 300 |
| `dqn_epochs` | DQN 消融训练轮数 | 15 |
| `use_fallback_tle` | 使用合成星座 | True |

---

## 7. 实测结果一览（5 seed mean ± std）

| 方案 | PLR (%) | E2E (ms) | 切换次数 | 总中断 (s) |
|---|---|---|---|---|
| Reactive | 0.233 ± 0.000 | 6.07 ± 0.00 | 3.0 ± 0.0 | 1.50 ± 0.00 |
| Max-Visibility | 0.275 ± 0.000 | 7.82 ± 0.00 | 3.0 ± 0.0 | 1.50 ± 0.00 |
| MPTCP-style | **6.382 ± 1.454** | 8.60 ± 0.35 | **69.6 ± 17.8** | **34.80 ± 8.89** |
| Pure-DRL | 0.217 ± 0.153 | 7.05 ± 1.14 | 2.4 ± 1.36 | 1.20 ± 0.68 |
| **Ours-Lyap** | **0.000 ± 0.000** | 6.24 ± 0.00 | 1.0 ± 0.0 | **0.00 ± 0.00** |
| **Ours-IL** | **0.000 ± 0.000** | 6.24 ± 0.00 | 1.0 ± 0.0 | **0.00 ± 0.00** |

完整结果与图表分析见 `results/EXPERIMENT_REPORT.md`。

---

## 8. 复现实验

```bash
make full GPU=0                 # 默认占用 cuda:0，~15 min
ls results/figures/             # 9 张论文图
cat results/summary.json        # 5 个 test seed 的均值±std 摘要
cat results/EXPERIMENT_REPORT.md  # 详细中文报告（含结论与对比表）
tensorboard --logdir results/tensorboard
```

跑完后 `results/run_all_results.pkl` 包含全部原始数据（轨迹、负载、所有方案的逐帧记录、切换记录、多 seed 聚合统计），可用 `experiments/plot_figures.py` 单独重画图或自定义分析。

### 一行结论

`Ours-Lyap / Ours-IL` 在 5 个 test seed 上稳定取得 **PLR = 0%，handoff 中断 = 0 s**；
传统 `Reactive/Max-Visibility` 因没有状态迁移，每次硬切丢 ~15 万分片；
`MPTCP-style` 在确定性卫星场景里过度切换（~70 次/30 min，6% 丢包），完全不适用；
`Pure-DRL` 收敛到次优且高方差，reward 比 Lyapunov 专家差 4.7×。

---

## 9. 文档索引

| 文档 | 主题 |
|---|---|
| [`docs/lyapunov_proof.md`](docs/lyapunov_proof.md) | Lyapunov 性能界定理（含定理 1 完整证明 + V 实测分析）|
| [`docs/创新点三-完整技术文档.md`](docs/创新点三-完整技术文档.md) | 论文第五章底稿（v2，含真实测试结果与图表解读）|
| [`results/EXPERIMENT_REPORT.md`](results/EXPERIMENT_REPORT.md) | 实验报告（5 seed mean±std + 性能优化记录）|
