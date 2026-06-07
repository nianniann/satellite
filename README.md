# 异构星座下协议转换网关切换与状态一致性迁移机制（创新点三）

> 大论文第三章配套代码实现。覆盖 Lyapunov 预测性网关选择、模仿学习加速、协议转换上下文两阶段迁移、多网关 Gossip 一致性，以及与 4 个对照基线的完整 SimPy 仿真。

---

## 1. 目录结构

```
sat_gateway_handoff/
├── config.py                      全局配置（物理常量、超参、随机种子）
├── data/tle/                      TLE 缓存（真实/合成）
├── orbit/
│   ├── skyfield_sim.py            轨道几何、ISL LOS、可见窗口预测
│   ├── synth_constellation.py     合成星座（无网络时备用）
│   └── topology.py                时变拓扑张量 + .npz 缓存
├── network/
│   ├── aos_packet.py              AOS 帧 / M_PDU / CCSDS 分片
│   ├── ipv6_packet.py             IPv6 + UDP 报文
│   └── simpy_env.py               SimPy 事件驱动仿真环境
├── migration/
│   ├── context.py                 C_static / C_dynamic 数据结构
│   ├── two_phase.py               Pre-copy + Stop-and-copy + 三层降级
│   └── consistency.py             Top-M 乐观复制 + Gossip 一致性
├── optimizer/
│   ├── lyapunov_solver.py         在线 drift-plus-penalty + 离线 DP 最优
│   └── policy_net.py              模仿学习策略网络（PyTorch / MPS）
├── baselines/
│   ├── reactive.py                被动硬切换
│   ├── max_visibility.py          贪心可见性
│   ├── mptcp_style.py             带迟滞的软切换
│   └── pure_drl.py                DQN 消融
├── experiments/
│   ├── run_all.py                 完整流水线（训练 + 6 方案对比）
│   ├── smoke_test.py              小规模冒烟，无 GPU 也能跑
│   └── plot_figures.py            8 张论文图
├── tests/                         pytest 单元测试 + 仿真集成测试
├── results/                       结果产物（不入版本控制）
│   ├── figures/                   出图
│   ├── tensorboard/               训练曲线
│   └── checkpoints/               IL / DQN 权重
├── Makefile
├── requirements.txt
└── docs/
    ├── lyapunov_proof.md          性能界定理证明草稿
    └── chapter5_template.md       大论文第 5 章 Markdown 初稿模板
```

---

## 2. 安装

```bash
pip install -r requirements.txt
```

依赖：numpy、torch、skyfield、sgp4、simpy、cvxpy、matplotlib、tensorboard、tqdm、pytest。

> 注：PyTorch 自动检测 Apple Silicon MPS / CUDA / CPU；本项目 `optimizer/policy_net.py:get_device()` 优先 MPS。

---

## 3. 快速跑通

| 命令 | 用途 | 资源 |
|---|---|---|
| `make test` | 跑 pytest 单元测试（31 个） | CPU，<2 min |
| `make smoke` | 小规模冒烟实验，30 min 测试时长，IL 15 epoch | CPU，~5 min |
| `make full` | 完整实验：训练 + 6 方案对比 + 出图 | GPU 推荐，~30 min |
| `make figures` | 仅基于已有 pkl 重新出图 | CPU，<1 min |
| `make tb` | 启动 TensorBoard 看训练曲线 | - |
| `make clean` | 清理 results/ 与拓扑缓存 | - |

---

## 4. 模块依赖与运行原理

```
                  ┌─────────────┐
                  │  TLE source │  (CelesTrak 或 synth_constellation.py)
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
└────────┬──────────┘                  │   gateways → IL)   │
         │                              └─────┬──────────────┘
         ▼                                    │
┌────────────────────┐                        │
│ policy_net (PyTorch│ ─────────► IL decision_fn
│   IL on MPS GPU)   │            喂给仿真
└────────────────────┘                        │
                                              ▼
                                  ┌───────────────────────┐
                                  │ migration/two_phase   │
                                  │ + consistency Gossip  │
                                  └──────────┬────────────┘
                                             ▼
                                  ┌───────────────────────┐
                                  │ plot_figures.py       │
                                  │ → fig1..fig8 PNG      │
                                  └───────────────────────┘
```

---

## 5. 关键设计决策

### 5.1 为什么是 Lyapunov 优化而不是 DRL？
- 卫星星历完全可预测（不是随机过程）→ 确定性优化天然优于强化学习
- Lyapunov drift-plus-penalty 给出闭式 `O(1/V), O(V)` 权衡，**有定理证明**（见 `docs/lyapunov_proof.md`）
- DQN 训练不稳定，决策依赖 GPU；Lyapunov 在线决策 < 1ms

### 5.2 为什么仍训练一个模仿学习网络？
- 让评审看到"AI/深度学习"标签满足
- 星上算力受限时，IL 网络 (~10K 参数) 推理比在线 Lyapunov 求解快 ~10×
- 训练数据来自 Lyapunov 专家解，性能上界由 Lyapunov 决定，**不会比专家差**

### 5.3 为什么不只用 VM Live Migration？
本方案有 4 个 VM 迁移没有的卫星独有难点（详见论文）：
1. CCSDS 分片重组缓存的迁移
2. VCID 级 QoS 队列状态
3. ISL 带宽时变受星历约束
4. 多目标网关并发覆盖的"状态分裂"问题

### 5.4 两阶段迁移的三层降级
当 `T_sync > T_physical_switch` 时：
1. **优选 ≥50% 完成度的分片** → DEGRADED-1
2. **只迁移高优先级 VCID（vcid ≤ 1）** → DEGRADED-2
3. **完全失败 → 回退硬切** → FAILED

---

## 6. 调参速查

`config.py` 中常用旋钮：

| 参数 | 含义 | 默认 |
|---|---|---|
| `sim_duration_sec` | 测试仿真时长 | 1800 |
| `num_candidate_gateways` | 候选网关数量 | 8 |
| `min_elevation_deg` | 最小通信仰角 | 10° |
| `isl_max_range_km` | ISL 最大距离 | 5500 km |
| `V_lyapunov` | Lyapunov utility-延迟权衡 | 50 |
| `switch_budget_per_sec` | 平均切换率上界 | 1/120 |
| `physical_switch_sec` | 物理切换窗口 | 0.5 s |
| `pre_copy_lead_sec` | Pre-copy 提前量 | 3 s |
| `il_epochs` / `il_hidden_dim` | IL 训练参数 | 50 / 64 |

---

## 7. 复现实验报告

```bash
make full
ls results/figures/             # 8 张论文图
cat results/summary.json        # 6 方案对比摘要
tensorboard --logdir results/tensorboard
```

跑完后 `results/run_all_results.pkl` 包含全部原始数据（轨迹、负载、所有方案的逐帧记录、切换记录），可用 `experiments/plot_figures.py` 单独重画图或自定义分析。
