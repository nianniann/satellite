# Lyapunov drift-plus-penalty 决策算法完整推导

本文档把"算法 1：Lyapunov 在线决策"的全部数学推导走一遍。读完应当能独立答出：

1. 优化问题是什么、约束什么样
2. 虚拟队列 Q(t)、Lyapunov 函数 L(t)、漂移 Δ(Q) 的定义与互相关系
3. 怎样从一阶约束推出闭式决策策略 a*(t)
4. 算法的性能上界（[O(1/V), O(V)] 权衡）是怎么证明的
5. 每个超参（V、C_max、α、β、γ）的物理意义和取值

---

## 0. 符号约定

| 符号 | 含义 | 取值 / 维度 |
|---|---|---|
| t | 时隙索引，每秒一个 | t = 0, 1, 2, … |
| Δt | 时隙长度 | 1 秒 |
| N | 候选 IPv6 网关数 | 16 |
| a(t) ∈ {0, 1, …, N-1} | 决策变量：第 t 秒选哪个网关 | 整数 |
| a_prev | 上一秒选的网关 | 整数 |
| ΔT_i(t) | 第 i 颗网关剩余连续可见时长 | 秒 |
| L_i(t) ∈ [0, 1] | 第 i 颗网关当前负载占比 | 实数 |
| V_i(t) ∈ {0, 1} | 第 i 颗网关此刻是否可见 | 0/1 |
| T_h | 中断判定阈值（剩余可见时长 < T_h 也判中断） | 5 秒 |

---

## 1. 即时代价函数 c(t)

每秒钟选完 a(t) 后会立刻产生一个代价 c(t)，由三项加权和构成：

$$
c(t) \;=\; \underbrace{\alpha \cdot \mathbf{1}\{\text{interrupt}_{a(t)}(t)\}}_{\text{中断罚}}
\;+\; \underbrace{\beta \cdot L_{a(t)}(t)}_{\text{拥塞罚}}
\;+\; \underbrace{\gamma \cdot \mathbf{1}\{a(t) \ne a(t{-}1)\}}_{\text{切换抖动罚}}
$$

其中中断判定为：

$$
\text{interrupt}_a(t) \;=\; \neg V_a(t) \;\vee\; (\Delta T_a(t) < T_h)
$$

| 权重 | 值 | 物理意义 |
|---|---|---|
| α | 1.0 | 中断罚最重，决不能选不可见 / 即将不可见的网关 |
| β | 0.3 | 拥塞罚次之，倾向于选负载低的网关 |
| γ | 0.5 | 抖动罚，抑制无意义的频繁切换 |

> 三项均做了量纲归一化，使代价的绝对值不依赖于星座规模。

---

## 2. 原始优化问题

目标：让长期平均代价最小，同时切换率不超出预算。

$$
\begin{aligned}
\min_{\{a(t)\}_{t=0}^{\infty}} \quad & \bar{c} \;=\; \lim_{T\to\infty}\;\frac{1}{T}\sum_{t=0}^{T-1} c(t) \\[6pt]
\text{s.t.} \quad & \lim_{T\to\infty}\;\frac{1}{T}\sum_{t=0}^{T-1} \mathbf{1}\{a(t) \ne a(t{-}1)\} \;\le\; C_{\max}
\end{aligned}
$$

| 量 | 物理意义 | 取值 |
|---|---|---|
| $C_{\max}$ | 长期平均切换次数上限（每秒） | 1/120 ≈ 0.0083 次/秒 |

**约束的难点**：这是一个**长期平均**的硬约束（不是逐时隙的）——离线整数规划复杂度 $O(N^T)$，在线无法求解。需要把它"软化"成可在线处理的形式。

---

## 3. 引入虚拟队列 Q(t)

定义一个虚拟队列（账户）：

$$
\boxed{\;Q(t+1) \;=\; \max\bigl\{\,Q(t) \;+\; s(t) \;-\; C_{\max}\cdot\Delta t,\; 0\bigr\}\;}
$$

其中 $s(t) = \mathbf{1}\{a(t) \ne a(t{-}1)\}$，初值 $Q(0) = 0$。

**动力学解读**：

- 切换一次 → 账户 +1
- 每秒固定扣 $C_{\max}\cdot\Delta t \approx 0.0083$
- $\max(\cdot, 0)$ 保证 Q 不为负

**这个变换把"长期约束"转化为"账户不发散"**：只要 Q(t) 长期有界（不持续增长），就能反过来推出长期切换率 ≤ C_max（见 §10）。

---

## 4. Lyapunov 函数 L(t)

定义：

$$
L(t) \;=\; \tfrac{1}{2}\,Q^2(t)
$$

**几何意义**：账户余额到 0 的距离的平方。L 越小，约束满足得越好。

**为什么用平方**：

- 凸函数，易于做不等式分析
- 配合下面要算的"漂移"，能得到关于 Q(t) 的线性上界
- 这是 Neely 的 Lyapunov 优化框架里的标准选择

---

## 5. Lyapunov 漂移 Δ(Q)

一步条件期望增量：

$$
\Delta(Q(t)) \;=\; \mathbb{E}\bigl[\,L(t+1) - L(t)\,\bigm|\,Q(t)\bigr]
\;=\; \tfrac{1}{2}\,\mathbb{E}\bigl[\,Q^2(t+1) - Q^2(t)\,\bigm|\,Q(t)\bigr]
$$

**意义**：给定当前 Q(t)，期望下一步 Q 的二次量会变大多少。让 Δ(Q) 尽量小 → 队列不会发散。

---

## 6. drift-plus-penalty 目标

把"约束（漂移）"和"性能（代价）"合在一起最小化：

$$
\min_{a(t)} \quad \Delta(Q(t)) \;+\; V \cdot \mathbb{E}[\,c(t)\,|\,Q(t)\,]
$$

| 参数 | 含义 | 取值 |
|---|---|---|
| V | 权衡参数：V 大偏重代价、V 小偏重约束 | 50 |

这是 Lyapunov 优化框架的核心思想：**让"队列稳定"与"代价最小"在同一个目标里平衡**，由 V 控制偏好。

---

## 7. 漂移的可解上界

直接最小化 $\Delta(Q)$ 不可行（含期望、含 max）。先把它放成**可在线最小化的上界**。

### 7.1 去掉 max

由 $\max\{x, 0\}^2 \le x^2$：

$$
Q^2(t+1) \;=\; \max\{\,Q + s - C_{\max}\Delta t,\,0\,\}^2 \;\le\; (Q + s - C_{\max}\Delta t)^2
$$

### 7.2 完全平方展开

$$
Q^2(t+1) - Q^2(t) \;\le\; 2Q(t)\bigl(s(t) - C_{\max}\Delta t\bigr) \;+\; \bigl(s(t) - C_{\max}\Delta t\bigr)^2
$$

两边乘 1/2 并取期望：

$$
\Delta(Q(t)) \;\le\; \underbrace{\tfrac{1}{2}\,\mathbb{E}\bigl[(s(t) - C_{\max}\Delta t)^2\,|\,Q(t)\bigr]}_{\le\,B\,\text{常数}}
\;+\; Q(t)\cdot\mathbb{E}\bigl[\,s(t) - C_{\max}\Delta t\,\bigm|\,Q(t)\bigr]
$$

其中：

$$
B \;=\; \tfrac{1}{2}\max\bigl((s - C_{\max}\Delta t)^2\bigr) \;\le\; \tfrac{1}{2}\;(1 - 0)^2 = 0.5
$$

（s ∈ {0, 1}, $C_{\max}\Delta t \approx 0.008$，所以 B 是个 ≤ 0.5 的有限常数。）

---

## 8. 加上 V·c(t) 得到 drift-plus-penalty 上界

$$
\Delta(Q(t)) + V\,\mathbb{E}[c(t)|Q(t)] \;\le\; B \;+\; Q(t)\,\mathbb{E}\bigl[s(t) - C_{\max}\Delta t\bigr] \;+\; V\,\mathbb{E}[c(t)|Q(t)]
$$

整理掉与决策 a(t) **无关**的项（$B$ 与 $-Q(t)C_{\max}\Delta t$）：

$$
\Delta(Q) + V\,c(t) \;\le\; \text{const} + \mathbb{E}\bigl[\,\underbrace{V\cdot c_{a}(t) \;+\; Q(t)\cdot\mathbf{1}\{a \ne a_{\mathrm{prev}}\}}_{\text{只剩这部分跟 }a\text{ 有关}}\,\bigm|\,Q(t)\bigr]
$$

---

## 9. 闭式决策策略

要最小化上界 → 让方括号里的项最小。每秒贪心：

$$
\boxed{\;a^{*}(t) \;=\; \arg\min_{a\in\{0,\dots,N-1\}} \Bigl[\, V \cdot c_{a}(t) \;+\; Q(t)\cdot\mathbf{1}\{a \ne a_{\mathrm{prev}}\}\,\Bigr]\;}
$$

展开 $c_a(t)$：

$$
a^{*}(t) \;=\; \arg\min_{a} \Bigl[\, V\bigl(\alpha\cdot\mathbf{1}\{\text{interrupt}_a\} + \beta L_a + \gamma\cdot\mathbf{1}\{a\ne a_{\mathrm{prev}}\}\bigr) \;+\; Q(t)\cdot\mathbf{1}\{a\ne a_{\mathrm{prev}}\}\Bigr]
$$

**关键性质**：

- 复杂度 **O(N)**：对每个候选算一次 score，挑最小
- 完全闭式：不需要任何 solver
- 决策仅依赖**当前观测**（ΔT、L、V）+ **当前账户** Q(t)，无需未来信息

---

## 10. 切换率约束的自动满足

由虚拟队列定义（去掉 max 取下界）：

$$
Q(t+1) \;\ge\; Q(t) + s(t) - C_{\max}\Delta t
$$

对 t = 0, …, T-1 求和并伸缩：

$$
Q(T) - Q(0) \;\ge\; \sum_{t=0}^{T-1} s(t) \;-\; C_{\max}\cdot T\cdot\Delta t
$$

移项除以 $T\Delta t$：

$$
\underbrace{\frac{1}{T}\sum_{t=0}^{T-1} s(t)}_{\text{长期切换率}} \;\le\; \frac{Q(T) - Q(0)}{T\Delta t} \;+\; C_{\max}
$$

如果 $\bar{Q} = \lim_{T\to\infty}\frac{1}{T}\sum Q(t)$ 有限（这点由下面的定理 2 保证），则 $Q(T)/T \to 0$，于是：

$$
\boxed{\;\lim_{T\to\infty}\;\frac{1}{T}\sum_{t=0}^{T-1} s(t) \;\le\; C_{\max}\;}
$$

**即长期平均切换次数自动满足预算约束，无需逐时隙强制。**

---

## 11. 性能上界

drift-plus-penalty 框架给出两个关键定理：

### 定理 1：代价上界（utility gap）

$$
\bar{c}^{\,\mathrm{Lyap}} \;\le\; \bar{c}^{*} \;+\; \frac{B}{V}
$$

其中 $\bar{c}^*$ 是离线全知最优解的代价。**算法平均代价偏离最优最多 B/V**。

### 定理 2：队列上界（constraint）

$$
\bar{Q} \;\le\; \frac{B + V\cdot(c_{\max} - c_{\min})}{\varepsilon}
$$

其中 $\varepsilon > 0$ 是约束的 Slater 间隙（可行内点松弛度）。**虚拟队列长期平均有界**。

### V 的权衡

| V 取值 | 偏向 | 代价偏离 | 队列振幅 |
|---|---|---|---|
| V ↑ | 偏重最小化代价 | B/V → 0（更接近最优）| 上界正比 V |
| V ↓ | 偏重约束（Q 不增长）| B/V → ∞ | 上界小 |

这就是著名的 **[O(1/V), O(V)] 权衡**。本工作取 V = 50，是个中性折中。

---

## 12. 算法伪代码

```python
# 初始化
Q = 0.0
a_prev = argmax(topo.remaining_visibility(0))   # 选可见时长最长的

for t = 0, 1, 2, …:
    # 1. 读当前观测
    rem = topo.remaining_visibility(t)          # 每颗网关的剩余可见时长
    L   = loads[t]                              # 每颗网关的当前负载
    vis = topo.visible[t]                       # 每颗网关此刻是否可见
    
    # 2. 对每个候选 a 算瞬时代价 + 切换押金
    for a in range(N):
        interrupt = (not vis[a]) or (rem[a] < T_h)
        c_a = α * interrupt + β * L[a] + γ * (a != a_prev)
        score[a] = V * c_a + Q * (a != a_prev)
    
    # 3. 取最小
    a_star = argmin(score)
    
    # 4. 触发切换（仅当目标 ≠ 当前）
    if a_star != a_prev:
        trigger_two_phase_migration(a_prev → a_star)
    
    # 5. 更新虚拟队列
    s = 1.0 if a_star != a_prev else 0.0
    Q = max(Q + s - C_max * Δt, 0.0)
    
    a_prev = a_star
```

**复杂度**：每秒 O(N) 浮点比较，N = 16 时 < 1 μs。

代码在 `optimizer/lyapunov_solver.py::lyapunov_online`，约 80 行。

---

## 13. 流程总图

```
┌─────────────────────────────────────────────────────────────┐
│ 优化问题：min c̄  s.t.  s̄_sw ≤ C_max                          │
│         （长期硬约束 → 离线 NP-hard）                          │
└────────────────────────┬────────────────────────────────────┘
                         │ ① 引入虚拟队列 Q(t)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Q(t+1) = max{Q(t) + s(t) - C_max·Δt, 0}                     │
│ Q 不发散 ⇒ 切换率自动 ≤ C_max （定理见§10）                   │
└────────────────────────┬────────────────────────────────────┘
                         │ ② 定义 Lyapunov 函数 L(t) = ½Q²(t)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 漂移 Δ(Q) = E[L(t+1) - L(t) | Q]                             │
│ 目标：min Δ(Q) + V·E[c(t) | Q]   ← drift-plus-penalty 目标   │
└────────────────────────┬────────────────────────────────────┘
                         │ ③ 完全平方展开 + 去 max
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Δ(Q) + V·c(t)  ≤  const + E[ V·c_a(t) + Q·1{a≠a_prev} ]     │
│                          ↑                                  │
│                  只有这部分跟动作 a 相关                       │
└────────────────────────┬────────────────────────────────────┘
                         │ ④ 贪心最小化上界
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ a*(t) = argmin_a [ V·c_a(t) + Q(t)·1{a ≠ a_prev} ]           │
│         ↑ 闭式 O(N)，每秒 < 1 μs                              │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 性能保证（drift-plus-penalty 框架）：                          │
│   定理 1: c̄^Lyap ≤ c̄* + B/V         （代价上界）              │
│   定理 2: Q̄ ≤ (B + V·Δc) / ε        （队列上界）              │
│   ⇒ [O(1/V), O(V)] 权衡                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 14. 超参取值速查

| 符号 | 来源（config.py） | 值 | 物理意义 |
|---|---|---|---|
| Δt | decision_interval_sec | 1.0 秒 | 时隙长度 |
| N | num_candidate_gateways | 16 | 候选网关数 |
| α | alpha | 1.0 | 中断罚（硬性，最大权重） |
| β | beta | 0.3 | 负载罚 |
| γ | gamma_switch (lyapunov_solver 默认参数) | 0.5 | 切换抖动罚（即时代价的一部分） |
| V | V_lyapunov | 50 | drift-plus-penalty 权衡参数 |
| C_max | switch_budget_per_sec | 1/120 ≈ 0.00833 次/秒 | 长期平均切换率上限 |
| T_h | interruption_horizon_sec | 5.0 秒 | 中断判定阈值 |

---

## 15. 实测验证

### 15.1 V 扫描（fig2）

代码在 `experiments/plot_figures.py::fig2_lyapunov_v_sweep`，让 V 在 {1, 5, 10, 50, 100, 500, 1000} 上扫描，跑 Lyapunov 并记录平均代价 + 切换率：

- 平均代价曲线在卫星硬可见性约束下**几乎水平**——因为可见性约束几乎在每个时隙都收敛到唯一最优 a*，V 调多调少都没法逃出可见性框
- 切换率曲线随 V 增大缓慢上升（V 大允许更频繁追求最优代价）

结论：**算法在卫星场景下对 V 的选择天然鲁棒**。

### 15.2 训练集生成验证

8 个训练负载场次跑出来的 Lyapunov 轨迹：

- 每条 trajectory 切换次数约 2–4 次
- 平均代价 ≈ -0.30（reward = -cost）
- Q(t) 曲线在切换时跳升 +1，平时缓慢下降，长期回归 ≈ 0

这就是后续 IL 网络要学习的"专家示范"。

---

## 16. 与其它方案的关系

| 方案 | 决策规则 | 跟 Lyapunov 的关系 |
|---|---|---|
| Reactive | 当前不可见才切，挑 max(rem) | 不考虑 Q，不考虑 L，相当于 V=∞ + 仅当 c_a=∞ 才切 |
| Max-Visibility | 每秒挑 max(rem) | 不考虑 Q、L、抖动，纯几何贪心 |
| MPTCP-style | 综合分 + 60s 迟滞 | 用启发式硬阈值代替 Q(t)，无理论保证 |
| **Ours-Lyap** | **本文的 a*(t)** | **本人** |
| Ours (IL) | 学生网络模仿 Lyapunov | 把 Lyapunov 在线求解器蒸馏到小 MLP，**部署时无需 Q 更新** |

---

## 17. 一句话总结

> Lyapunov drift-plus-penalty 把"长期硬约束 + 长期最小化代价"通过虚拟队列 Q(t) 翻译成**每秒可贪心求解**的 O(N) 闭式问题：
> $a^*(t) = \arg\min_a [V \cdot c_a(t) + Q(t)\cdot\mathbf{1}\{a \ne a_{\mathrm{prev}}\}]$
> 同时给出代价偏离最优 ≤ $B/V$ 与队列有界两个上界，构成 [O(1/V), O(V)] 权衡。

---

## 附录 A：代码与文档对照

| 概念 | 代码位置 | PPT 页 |
|---|---|---|
| 即时代价 c(t) | `lyapunov_solver.py:144-148` | 第 9 页 |
| 虚拟队列 Q(t+1) | `lyapunov_solver.py:164` | 第 9, 10 页 |
| Lyapunov 函数 L(t) | （仅在推导文档里） | 第 10 页 |
| Drift Δ(Q) | （仅在推导文档里） | 第 10 页 |
| 闭式策略 a*(t) | `lyapunov_solver.py:140-151` | 第 9, 10 页 |
| 性能上界 | （仅在文档里，PPT 已简化） | 已从 PPT 删除，保留为脚注 |
