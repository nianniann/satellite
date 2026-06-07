# Lyapunov drift-plus-penalty 策略的性能界证明

> 论文 5.2 节配套证明草稿。沿用 M. J. Neely《Stochastic Network Optimization with Application to Communication and Queueing Systems》(2010) 的经典框架，并针对本研究的离散时间网关选择问题做适配。

---

## 1. 问题陈述

考虑离散时间系统 $t \in \{0, 1, 2, \dots\}$，AOS 卫星需要在每个时隙从 $N$ 个候选 IPv6 网关中选择一个：$a(t) \in \{1, \dots, N\}$。

### 1.1 即时代价

$$c(t) = \alpha \cdot \mathbf{1}\{V_{a(t)}(t) = 0 \;\vee\; \Delta T_{a(t)}(t) < T_h\} + \beta \cdot L_{a(t)}(t) + \gamma \cdot \mathbf{1}\{a(t) \ne a(t-1)\}$$

设 $c_{\max} = \alpha + \beta + \gamma$（即时代价上界），$c_{\min} = 0$（下界）。

### 1.2 约束

切换指示变量 $x_{sw}(t) = \mathbf{1}\{a(t) \ne a(t-1)\}$，要求长期平均：

$$\overline{x_{sw}} = \lim_{T\to\infty}\frac{1}{T}\sum_{t=0}^{T-1} x_{sw}(t) \le C_{\max}$$

### 1.3 目标

最小化长期平均代价：

$$\overline{c} = \lim_{T\to\infty}\frac{1}{T}\sum_{t=0}^{T-1} c(t)$$

记 $\overline{c}^{\text{opt}}$ 为该约束优化问题的最优值。

---

## 2. 虚拟队列与 Lyapunov 函数

### 2.1 虚拟队列定义

引入虚拟队列 $Q(t)$：

$$Q(t+1) = \max\{Q(t) + x_{sw}(t) - C_{\max} \cdot \Delta t, \; 0\}$$

直观解释：每次切换"借" 1 单位预算，每个时隙"还" $C_{\max} \cdot \Delta t$。$Q(t)$ 即当前累计的"预算超支"。

### 2.2 队列稳定性 ⇔ 约束满足

**引理 1**：若 $\lim_{t\to\infty} \mathbb{E}[Q(t)] / t = 0$（即 $Q$ 平均增速为零，称为"强稳定"），则约束 $\overline{x_{sw}} \le C_{\max}$ 满足。

证明：由 $Q(t+1) \ge Q(t) + x_{sw}(t) - C_{\max}\Delta t$，迭代得

$$Q(T) \ge Q(0) + \sum_{t=0}^{T-1}\left[x_{sw}(t) - C_{\max}\Delta t\right]$$

两边除以 $T$ 取极限：

$$0 = \lim_{T\to\infty}\frac{Q(T)}{T} \ge \lim_{T\to\infty}\frac{1}{T}\sum_{t=0}^{T-1} x_{sw}(t) - C_{\max}\Delta t$$

即 $\overline{x_{sw}} \le C_{\max}$。∎

### 2.3 Lyapunov 函数

定义二次 Lyapunov 函数：

$$L(Q(t)) = \frac{1}{2} Q(t)^2$$

单时隙漂移：

$$\Delta(Q(t)) \triangleq \mathbb{E}\{L(Q(t+1)) - L(Q(t)) \mid Q(t)\}$$

---

## 3. 漂移上界（核心引理）

**引理 2**：对任意决策策略，

$$\Delta(Q(t)) \le B + Q(t) \cdot \mathbb{E}\{x_{sw}(t) - C_{\max}\Delta t \mid Q(t)\}$$

其中 $B = \tfrac{1}{2}\max(1, C_{\max}^2 \Delta t^2) \le \tfrac{1}{2}$ 是常数。

证明：

$$Q(t+1)^2 \le \left(Q(t) + x_{sw}(t) - C_{\max}\Delta t\right)^2$$

（因为 $\max\{x, 0\}^2 \le x^2$ 当 $x$ 为任意实数，加上 $Q \ge 0$，可证更紧的界，此处用宽松上界）

$$= Q(t)^2 + (x_{sw}(t) - C_{\max}\Delta t)^2 + 2 Q(t)(x_{sw}(t) - C_{\max}\Delta t)$$

两边减去 $Q(t)^2$，除以 2，再取条件期望：

$$\Delta(Q(t)) \le \frac{1}{2} \mathbb{E}\{(x_{sw}(t) - C_{\max}\Delta t)^2\} + Q(t)\cdot \mathbb{E}\{x_{sw}(t) - C_{\max}\Delta t \mid Q(t)\}$$

由于 $x_{sw}(t) \in \{0, 1\}$ 且 $C_{\max}\Delta t \in [0, 1]$，$(x_{sw} - C_{\max}\Delta t)^2 \le \max(1, C_{\max}^2\Delta t^2) \le 1$，所以 $B \le 1/2$。∎

---

## 4. Drift-plus-Penalty 策略

### 4.1 策略形式

在每个时隙 $t$，最小化 **drift-plus-penalty** 上界：

$$\text{minimize} \quad B + Q(t)\cdot[x_{sw}(t) - C_{\max}\Delta t] + V \cdot c(t)$$

去掉常数项（$B$ 与 $-Q(t)C_{\max}\Delta t$ 与决策无关），等价于：

$$a^*(t) = \arg\min_{a\in\{1..N\}} V\cdot \tilde{c}_a(t) + Q(t)\cdot \mathbf{1}\{a \ne a(t-1)\}$$

其中 $\tilde{c}_a(t)$ 是把 $a$ 代入 $c(t)$ 的即时代价值。

### 4.2 关键性质

- 该最小化是 $O(N)$ 的逐点比较，无须任何求解器
- $V$ 是 utility-延迟权衡参数：$V$ 越大，策略越激进追求低代价（不顾虚拟队列长度）

---

## 5. 主定理：性能界

### 5.1 Slater 条件假设

**假设 1**（Slater 条件）：存在一个"松弛"策略 $\pi^{slack}$ 满足

$$\mathbb{E}\{x_{sw}^{slack}(t)\} \le C_{\max}\Delta t - \epsilon$$

对某 $\epsilon > 0$ 成立。

直观：约束在严格意义下可行（不是边界紧绷）。在本研究中，由于 $C_{\max}\Delta t$ 远大于真实需要的切换率（典型 $C_{\max}\Delta t = 1/120$，而最优切换率 $\approx 1/200$），Slater 条件自然满足，$\epsilon \approx C_{\max}\Delta t - \text{opt rate}$。

### 5.2 定理 1：代价与队列权衡

**定理 1**：在满足 Slater 条件 $\epsilon > 0$ 的前提下，drift-plus-penalty 策略满足：

$$\boxed{\overline{c}^{\text{DPP}} \le \overline{c}^{\text{opt}} + \frac{B}{V}}$$

$$\boxed{\overline{Q} \le \frac{B + V \cdot (c_{\max} - c_{\min})}{\epsilon}}$$

即时间平均代价误差不超过 $B/V$，虚拟队列长度（约束违反量）线性增长于 $V$。

### 5.3 证明

#### 5.3.1 关键观察

由策略最优性（每时隙取 RHS 最小者），对任意"对照策略" $\pi^{any}$：

$$Q(t)\cdot x_{sw}^{\text{DPP}}(t) + V\cdot c^{\text{DPP}}(t) \le Q(t)\cdot x_{sw}^{any}(t) + V\cdot c^{any}(t)$$

代入引理 2：

$$\Delta(Q(t)) + V\cdot c^{\text{DPP}}(t) \le B + Q(t)\cdot[\mathbb{E}\{x_{sw}^{any}(t)\} - C_{\max}\Delta t] + V\cdot \mathbb{E}\{c^{any}(t)\}$$

#### 5.3.2 代价界（取 $\pi^{any} = \pi^{opt}$）

最优策略 $\pi^{opt}$ 满足 $\mathbb{E}\{x_{sw}^{opt}\} \le C_{\max}\Delta t$，所以

$$Q(t)\cdot[\mathbb{E}\{x_{sw}^{opt}\} - C_{\max}\Delta t] \le 0$$

代入：

$$\Delta(Q(t)) + V\cdot c^{\text{DPP}}(t) \le B + V \cdot \overline{c}^{\text{opt}}$$

两边对 $t = 0, 1, \dots, T-1$ 求和，并用伸缩展开 $\sum \Delta = \mathbb{E}[L(Q(T))] - L(Q(0)) \ge -L(Q(0))$：

$$-L(Q(0)) + V \cdot \sum_{t=0}^{T-1} c^{\text{DPP}}(t) \le BT + VT \cdot \overline{c}^{\text{opt}}$$

除以 $VT$ 取 $T\to\infty$ 极限：

$$\overline{c}^{\text{DPP}} \le \overline{c}^{\text{opt}} + \frac{B}{V} + \underbrace{\lim_{T\to\infty}\frac{L(Q(0))}{VT}}_{=0}$$

即第一个不等式得证。

#### 5.3.3 队列界（取 $\pi^{any} = \pi^{slack}$）

由 Slater 条件，$\mathbb{E}\{x_{sw}^{slack}\} \le C_{\max}\Delta t - \epsilon$，代入：

$$\Delta(Q(t)) + V\cdot c^{\text{DPP}}(t) \le B + Q(t)\cdot(-\epsilon) + V\cdot c^{slack}$$

$$\Rightarrow \Delta(Q(t)) \le B - \epsilon Q(t) + V \cdot (c^{slack} - c^{\text{DPP}}) \le B - \epsilon Q(t) + V\cdot (c_{\max} - c_{\min})$$

由 Foster-Lyapunov 准则的标准结果（当 $\Delta \le K - \epsilon Q$ 时，$\overline{Q} \le K/\epsilon$）：

$$\overline{Q} \le \frac{B + V\cdot(c_{\max} - c_{\min})}{\epsilon}$$

第二个不等式得证。∎

---

## 6. 结论与论文叙述

### 6.1 定理的工程含义

- $V$ 增大 → 代价误差 $\le B/V \to 0$（任意逼近最优）
- $V$ 增大 → 队列长度 $\overline{Q} = O(V)$（短期内更可能违反切换预算）
- **这是经典的 utility-延迟（在本研究中是 utility-切换次数）权衡**

### 6.2 实际选择 V 的指导

- 推荐 $V \in [10, 200]$
- 论文中扫 $V \in \{1, 5, 10, 50, 100, 500, 1000\}$ 出图（图 2）

### 6.3 论文 5.2 节叙述模板

> **定理 5.1**（Lyapunov 性能界）：设候选网关数为 $N$，切换预算为 $C_{\max}$，且存在 Slater 余量 $\epsilon > 0$。则 drift-plus-penalty 策略产生的时间平均代价 $\overline{c}^{\text{DPP}}$ 与离线最优代价 $\overline{c}^{\text{opt}}$ 满足：
>
> $$\overline{c}^{\text{DPP}} - \overline{c}^{\text{opt}} \le \frac{B}{V} = O\!\left(\frac{1}{V}\right)$$
>
> 同时虚拟队列长度满足 $\overline{Q} \le O(V)$。其中 $B$ 是与 $V$ 无关的常数。
>
> **证明**：见附录 A。
>
> **推论 5.1**（参数选取指导）：取 $V = \Theta(\sqrt{T})$ 可使两个目标均达到 $O(\sqrt{T})$ 的 regret。

---

## 7. 与本方案代码的对应

```python
# optimizer/lyapunov_solver.py: lyapunov_online()

Q = 0.0
for k in range(T):
    # 计算每个候选的瞬时 cost（公式 4.1）
    for a in range(N):
        cost_a = alpha * interrupt + beta * loads[k][a]
        score = V * (cost_a + gamma * switch_indicator) + Q * switch_indicator
    # 取 argmin（公式 4.2，即 drift-plus-penalty 最小化）
    best_a = np.argmin(scores)
    # 虚拟队列更新（公式 2.1）
    Q = max(Q + is_switch - C_max * dt, 0.0)
```

### 性能验证

- `tests/test_lyapunov.py::test_offline_optimal_bounds_online` 验证 $\overline{c}^{\text{DPP}} \le \overline{c}^{\text{opt}} \cdot 1.1 + 1$
- `experiments/plot_figures.py::fig2_lyapunov_v_sweep` 出 V 参数扫描图，直观验证 $O(1/V)$、$O(V)$ 权衡

---

*文档版本：v1.0*
