"""
课题进展汇报 PPT 生成脚本
- 中文：PingFang SC
- 公式：matplotlib mathtext (cm 字体，Computer Modern)
- 输出：docs/ppt_创新点三/01_*.png ... 20_*.png
"""
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg

# ===== 全局样式 =====
# 显式加载微软雅黑（系统未默认安装的话，从 Office 自带字体目录拿）
from matplotlib import font_manager as _fm
_MSYH_CANDIDATES = [
    '/Library/Fonts/Microsoft/msyh.ttf',
    '/Users/sir1st/Library/Fonts/msyh.ttf',
    '/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts/msyh.ttf',
    '/Applications/Microsoft Word.app/Contents/Resources/DFonts/msyh.ttf',
]
for _p in _MSYH_CANDIDATES:
    if os.path.exists(_p):
        try:
            _fm.fontManager.addfont(_p)
        except Exception:
            pass
        break

mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'PingFang SC', 'Heiti SC', 'Arial Unicode MS']
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['axes.unicode_minus'] = False
mpl.rcParams['mathtext.fontset'] = 'cm'   # 公式始终用 Computer Modern

PURPLE = '#5a2d8a'
GOLD = '#c9a96e'
DARK = '#1f1535'
GRAY = '#5a5a6e'
LIGHT_PURPLE = '#efeaf6'
LIGHT_GOLD = '#faf4e6'
LIGHT_RED = '#fbeaea'
LIGHT_GREEN = '#e8f3ea'
LIGHT_BLUE = '#e8eff8'
LIGHT_ORANGE = '#fbeedd'

OUT = os.path.join(os.path.dirname(__file__), 'ppt_创新点三')
FIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'results', 'figures')
BG_PATH = os.path.join(os.path.dirname(__file__), 'ppt_bg.png')

W, H = 14.8, 8.32   # 16:9
_BG = mpimg.imread(BG_PATH) if os.path.exists(BG_PATH) else None

# 背景上需要保护的区域：
# · 校徽：约 x ∈ [3, 14], y ∈ [85, 99]
# · 校园线稿：约 y ∈ [0, 10]
# 故内容安全区: 标题 y=93 x>=15; 正文 y ∈ [11, 87] x ∈ [4, 96]

def new_slide():
    fig, ax = plt.subplots(figsize=(W, H), dpi=110)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.axis('off')
    fig.patch.set_facecolor('white')
    if _BG is not None:
        ax.imshow(_BG, extent=[0, 100, 0, 100], aspect='auto', zorder=0)
    return fig, ax

def header(ax, title, sub=None):
    ax.text(16, 93, title, fontsize=21, color=PURPLE, weight='bold', va='center', zorder=10)
    ax.plot([16, min(16 + len(title)*2.4, 80)], [89.4, 89.4], color=GOLD, lw=2, zorder=10)
    if sub:
        ax.text(16, 86, sub, fontsize=11.5, color=GRAY, va='center', zorder=10)

def panel(ax, x, y, w, h, fc=LIGHT_PURPLE, ec=PURPLE, lw=1.2, alpha=0.92):
    # alpha 让背景的线稿不会被纯色矩形完全覆盖，但又足以保证文字清晰
    box = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.4,rounding_size=0.6',
                         fc=fc, ec=ec, lw=lw, alpha=alpha, zorder=2)
    ax.add_patch(box)

def title_panel(ax, x, y, w, h, title, color=PURPLE, fc=None):
    if fc is None:
        fc = LIGHT_PURPLE
    panel(ax, x, y, w, h, fc=fc, ec=color)
    ax.text(x + 1.5, y + h - 1.5, title, fontsize=12, color=color,
            weight='bold', va='top', zorder=10)

def body_y(panel_y, panel_h, line=0, lh=3.2):
    """Recommended top-y for body text inside a title_panel.
    line=0 is the first body line (sits ~4.5 below title bottom).
    Each subsequent line shifts down by lh (axes units)."""
    return panel_y + panel_h - 5.5 - line * lh

def save(fig, name):
    out = os.path.join(OUT, name)
    fig.savefig(out, dpi=140, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'  ✓ {name}')

def add_image(ax, path, x, y, w, h):
    """在指定矩形区域内贴一张外部 png"""
    if not os.path.exists(path):
        ax.text(x + w/2, y + h/2, f'[缺图: {os.path.basename(path)}]',
                ha='center', va='center', color='red')
        return
    img = mpimg.imread(path)
    # use inset_axes via add_axes with normalized figure coords
    fig = ax.figure
    # convert data coords (0-100) → figure fraction (use bbox)
    bbox = ax.get_position()
    fx = bbox.x0 + (x/100.0) * bbox.width
    fy = bbox.y0 + (y/100.0) * bbox.height
    fw = (w/100.0) * bbox.width
    fh = (h/100.0) * bbox.height
    iax = fig.add_axes([fx, fy, fw, fh])
    iax.imshow(img)
    iax.axis('off')


IMG_DIR = os.path.join(os.path.dirname(__file__), 'slide_imgs')

def image_slide(out_name, src_image):
    """整页贴图：直接把 src_image 拷贝到 OUT/out_name，保留原图质量。"""
    import shutil
    src_path = os.path.join(IMG_DIR, src_image)
    dst_path = os.path.join(OUT, out_name)
    shutil.copy(src_path, dst_path)
    print(f'  ✓ {out_name}  (image)')

# =========================================================
# 01 封面
# =========================================================
def slide_01():
    fig, ax = new_slide()
    ax.text(50, 65, '异构星座下基于星历预测的', fontsize=30, color=PURPLE,
            weight='bold', ha='center', zorder=10)
    ax.text(50, 55, '协议转换网关切换与状态一致性迁移机制', fontsize=30,
            color=PURPLE, weight='bold', ha='center', zorder=10)
    ax.text(50, 45, '—— 课题阶段进展汇报', fontsize=18, color=GRAY, ha='center', zorder=10)
    ax.text(50, 37,
            r'Lyapunov 在线优化  ·  模仿学习  ·  两阶段状态迁移  ·  Lamport-Gossip 一致性',
            fontsize=14, color=GOLD, ha='center', zorder=10)
    ax.text(50, 25, '汇报人：xxx     课题组      2026.06',
            fontsize=13, color=GRAY, ha='center', zorder=10)
    save(fig, '01_cover.png')

# =========================================================
# 02 目录
# =========================================================
def slide_02():
    fig, ax = new_slide()
    header(ax, '汇报目录')
    items = [
        ('01', '研究背景与问题挑战',
         '空天地一体化背景 · 代际异构现状 · 前期"静态互联"工作 · 动态场景下两类核心困境'),
        ('02', '系统模型与四段式解决机制',
         '从"静态可转换"升级到"持续可转换"：四段式机制因果链 + 系统建模 / 决策 / 迁移 / 一致性 详细原理'),
        ('03', '算法设计与总体技术路线',
         '四个关键算法的伪代码 · 实验流程总览与各阶段详细拆解 (拓扑构建 → 训练 → 仿真 → 出图)'),
        ('04', '实验验证与性能评估',
         '合成 LEO 星座 + 6 方案 + 5 种子 + 9 指标 实验设计 · 训练 / 综合指标 / 关键可视化 三类结果'),
        ('05', '总结与下一步工作',
         '研究实现了什么 · AOS<->IPv6 场景下的性能数字 · 可应用的实际场景 · 局限与下一步工作'),
    ]
    y0 = 76
    for i, (num, title, desc) in enumerate(items):
        y = y0 - i * 12.5
        # 数字底色
        ax.add_patch(FancyBboxPatch((9, y - 3.2), 7.5, 7,
                                    boxstyle='round,pad=0.2,rounding_size=0.5',
                                    fc=LIGHT_PURPLE, ec=PURPLE, lw=1.2, alpha=0.92, zorder=2))
        ax.text(12.75, y + 0.3, num, fontsize=19, color=PURPLE, weight='bold',
                ha='center', va='center', zorder=11)
        ax.text(20, y + 2.2, title, fontsize=17, color=PURPLE, weight='bold', va='center', zorder=10)
        ax.text(20, y - 1.8, desc, fontsize=11.5, color=DARK, va='center', zorder=10)
    save(fig, '02_outline.png')

# =========================================================
# 03 背景
# =========================================================
def slide_03():
    image_slide('03_background.png', '03_background.png')


# =========================================================
# 04 前期工作：从"能通信"到"能转换"的静态互联闭环
# =========================================================
PRIOR_ADDR_IMG  = os.path.join(os.path.dirname(__file__), 'prior_addr_config.png')
PRIOR_PROTO_IMG = os.path.join(os.path.dirname(__file__), 'prior_proto_convert.png')

def slide_04():
    image_slide('04_prior_work.png', '04_prior_work.png')


# =========================================================
# 05 现状
# =========================================================
def slide_05():
    image_slide('05_status.png', '05_status.png')


# =========================================================
# 05 困境①
# =========================================================
def slide_06():
    image_slide('06_problem_tc.png', '06_problem_tc.png')


# =========================================================
# 06 困境② VM
# =========================================================
def slide_07():
    image_slide('07_problem_multi.png', '07_problem_multi.png')



# =========================================================
# 07 解决思路
# =========================================================
def slide_08():
    image_slide('08_overview.png', '08_overview.png')


# =========================================================
# 08 详细原理①：系统模型 + TC
# =========================================================
def slide_09():
    fig, ax = new_slide()
    header(ax, '详细原理①：系统模型与即时代价函数')

    # ===== 左：星座构型 + 时间离散化 =====
    title_panel(ax, 4, 56, 46, 28, '系统建模', color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 78,
            '· AOS 卫星：1 颗，轨道高度 400 km；',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(5.5, 74.5,
            '· IPv6 网关卫星：16 颗，轨道高度 550 km，',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(5.5, 71,
            '  同倾角面、等 RAAN 间距均匀分布；',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(5.5, 67,
            '· 时间离散化：时隙长度 1 秒；',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(5.5, 63.5,
            '· 决策变量：每秒选哪一颗 IPv6 网关。',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(5.5, 59.5,
            r'每颗候选 $g_i$ 的状态量：距离 $D_i$、剩余可见时长 $\Delta T_i$、'
            'ISL 带宽、CPU 负载。',
            fontsize=9.6, color=GRAY, va='center', style='italic', zorder=10)

    # ===== 左下：星间可见性约束 =====
    title_panel(ax, 4, 28, 46, 26,
                '星间可见性约束（避大气切线高度）',
                color='#c8651f', fc=LIGHT_ORANGE)
    ax.text(5.5, 48,
            '· 传统的"仰角 ≥ 10°"是地面对卫星的约束，',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(5.5, 44.5,
            '  目的是避地面建筑遮挡与低空大气折射；',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(5.5, 41,
            '· 星间链路不存在"仰角"概念，应改用',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(5.5, 37.5,
            '  "LoS 不被大气遮挡"准则；',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(5.5, 33,
            r'· 取大气边界 $h_{\mathrm{atm}}=80$ km，可得',
            fontsize=10, color=PURPLE, weight='bold', va='center', zorder=10)
    ax.text(5.5, 30,
            r'  $D_{\max}\approx 4567$ km；',
            fontsize=10.2, color=DARK, va='center', zorder=10)

    # ===== 右上：即时代价 c(t) =====
    title_panel(ax, 52, 50, 44, 34, '即时代价  $c(t)$  的设计', color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(53.5, 78,
            r'$c(t)\;=\;\alpha\cdot$ 中断罚 $+\;\beta\cdot$ 拥塞罚 $+\;\gamma\cdot$ 切换罚',
            fontsize=11, color=DARK, zorder=10)
    items = [
        ('中断罚', '#a52828', '1.0',
         '若候选网关已不可见，或剩余可见时长不足阈值（如 5 秒，\n'
         '不够安全完成两阶段迁移），则该项 = 1；否则 = 0。'),
        ('拥塞罚', '#c8651f', '0.3',
         r'即候选网关的 CPU 负载 $L_i\in[0,1]$；'
         '\n'
         '负载越高、拥塞惩罚越大，自然避开"扎堆"网关。'),
        ('切换罚', '#3666b8', '0.5',
         '若本时隙选了与上一时隙不同的网关，该项 = 1；否则 = 0。\n'
         '用于抑制频繁切换、避免乒乓现象。'),
    ]
    for i, (label, color, w, body) in enumerate(items):
        y = 70 - i*8.5
        ax.add_patch(FancyBboxPatch((53.5, y - 2.4), 9, 5,
                                    boxstyle='round,pad=0.2,rounding_size=0.4',
                                    fc=color, ec=color, alpha=0.9, zorder=3))
        ax.text(58, y + 0.1, label, ha='center', va='center',
                fontsize=10, color='white', weight='bold', zorder=11)
        ax.text(64, y + 2.0, f'权重 = {w}',
                fontsize=9.5, color=color, weight='bold', va='center', zorder=10)
        ax.text(64, y - 1.5, body, fontsize=9.3, color=DARK, va='center',
                linespacing=1.55, zorder=10)

    # ===== 右下：长期目标 + 说明 =====
    title_panel(ax, 52, 4, 44, 42, '长期目标', color='#2e7d4f', fc=LIGHT_GREEN)
    ax.text(53.5, 40,
            r'$\min_{a(\cdot)}\;\bar c \;=\; \lim_{T\to\infty}\;\frac{1}{T}\sum_{t=0}^{T-1} c(t)$,'
            r'   s.t.   $\bar s_{\mathrm{sw}}\;\leq\;C_{\max}$',
            fontsize=10.5, color=DARK, zorder=10)
    ax.text(53.5, 35,
            '即在长期平均代价尽量小的同时，',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(53.5, 32,
            '保证切换总次数不超出预算 $C_{\\max}$。',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(53.5, 27,
            r'三项均做了量纲归一，使代价不依赖星座规模；',
            fontsize=9.6, color=GRAY, va='center', style='italic', zorder=10)
    ax.text(53.5, 24,
            '权重 (α, β, γ) 可根据场景做敏感性分析。',
            fontsize=9.6, color=GRAY, va='center', style='italic', zorder=10)

    ax.text(53.5, 18,
            '设计意图：',
            fontsize=10.2, color='#2e7d4f', weight='bold', zorder=10)
    ax.text(53.5, 14.5,
            '· 中断罚最大（α = 1.0）：决不能让业务中断；',
            fontsize=9.5, color=DARK, va='center', zorder=10)
    ax.text(53.5, 11.5,
            '· 拥塞罚次之（β = 0.3）：均衡所有网关；',
            fontsize=9.5, color=DARK, va='center', zorder=10)
    ax.text(53.5, 8.5,
            '· 切换罚（γ = 0.5）：避免乒乓抖动。',
            fontsize=9.5, color=DARK, va='center', zorder=10)
    save(fig, '09_principle_model.png')


# =========================================================
# 10 详细原理③：IL
# =========================================================
def slide_10():
    fig, ax = new_slide()
    header(ax, '详细原理②：drift-plus-penalty 在线决策')

    # === 左 1：长期平均最小化 + 切换预算约束 ===
    title_panel(ax, 4, 60, 46, 24,
                '1) 长期平均最小化  +  切换预算约束',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 78,
            r'$\min\;\bar c\;=\;\lim_{T\to\infty}\frac{1}{T}\sum_{t=0}^{T-1} c(t)$,'
            r'   s.t.   $\bar s_{\mathrm{sw}}\;\leq\;C_{\max}$',
            fontsize=11.5, color=DARK, va='center', zorder=10)
    ax.text(5.5, 73,
            r'$\bar s_{\mathrm{sw}}$：单位时间切换次数的长期平均；',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(5.5, 69.5,
            r'$C_{\max}$：硬性预算上界。',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(5.5, 64,
            '· 只追求每步代价最小 → 会频繁切换；\n'
            '· 直接硬限切换次数 → 变成离线整数规划，无法在线求解。',
            fontsize=9.6, color=GRAY, va='top', linespacing=1.6, style='italic', zorder=10)

    # === 左 2：虚拟队列 + Lyapunov 函数 ===
    title_panel(ax, 4, 32, 46, 26,
                '2) 引入"虚拟队列" — 把硬约束变软',
                color='#c8651f', fc=LIGHT_ORANGE)
    ax.text(5.5, 52,
            r'$Q(t{+}1)=\max\{\,Q(t)+\mathbf{1}\{\mathrm{switch}\}-C_{\max}\Delta t,\;0\}$',
            fontsize=11, color=DARK, va='center', zorder=10)
    ax.text(5.5, 46.5,
            '把 $Q(t)$ 想成"切换次数账户"：',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(5.5, 42.5,
            '· 切了一次  →  账户 +1；每时隙固定扣除预算；',
            fontsize=9.8, color=DARK, va='center', zorder=10)
    ax.text(5.5, 39,
            '· 账户余额越大 → 算法越倾向于"这次别切"；',
            fontsize=9.8, color=DARK, va='center', zorder=10)
    ax.text(5.5, 35.5,
            '· 长时间看，账户自动收敛 → 切换率自然满足预算。',
            fontsize=9.8, color=DARK, va='center', zorder=10)

    # === 左 3：闭式决策策略 ===
    title_panel(ax, 4, 4, 46, 26,
                '3) drift-plus-penalty 闭式决策策略',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 25,
            r'$a^{*}(t)=\arg\min_a\;V\cdot c_a(t)\;+\;Q(t)\cdot\mathbf{1}\{a\neq a_{\mathrm{prev}}\}$',
            fontsize=11, color=DARK, va='center', zorder=10)
    ax.text(5.5, 19.5,
            '· 每时隙 $O(N)$ 闭式比较即可，无需任何求解器；\n'
            '· $V$ 是"代价 <-> 切换次数"的权衡参数；\n'
            '· $V$ 大：更看重低代价、可能多切；\n'
            '· $V$ 小：更看重少切、可能高代价。',
            fontsize=9.6, color=DARK, va='top', linespacing=1.65, zorder=10)

    # === 右上：直观含义 ===
    title_panel(ax, 52, 56, 44, 28,
                'drift-plus-penalty 的直观含义',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(53.5, 77,
            '每秒选哪颗网关 = 总成本最小的那颗，总成本由两件事组成：',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(53.5, 71.5,
            r'$V\cdot c_a(t)$ ：这一步的即时代价（中断/拥塞/抖动加权）；',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(53.5, 67,
            r'$Q(t)\cdot\mathbf{1}\{a\neq a_{\mathrm{prev}}\}$ ：选它会让账户增加多少。',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(53.5, 62.5,
            '· 选上一秒同一颗 → 账户项为 0，无切换押金；',
            fontsize=9.7, color=DARK, va='center', zorder=10)
    ax.text(53.5, 59,
            '· 换一颗 → 要付一笔等于当前账户余额的切换押金。',
            fontsize=9.7, color=DARK, va='center', zorder=10)

    # === 右下：每时隙决策流程 ===
    title_panel(ax, 52, 22, 44, 32,
                '每时隙决策流程（O(N) 闭式）',
                color='#c8651f', fc=LIGHT_ORANGE)
    steps = [
        '① 读星历预测：取出每颗候选的 $\\Delta T_i,B_i,V_i$；',
        '② 读当前网关负载 $L_i$、上一步选的网关 $a_{\\mathrm{prev}}$；',
        r'③ 对每个候选 $a$ 算即时代价 $c_a(t)=\alpha\cdot$中断$+\beta L+\gamma\cdot$切换；',
        r'④ 计算总分 $s_a=V\cdot c_a + Q\cdot\mathbf{1}\{a\neq a_{\mathrm{prev}}\}$；',
        '⑤ 选总分最小的那颗作为这一秒的网关；',
        r'⑥ 更新账户：$Q\leftarrow\max(Q+\Delta-C_{\max}\Delta t,\,0)$。',
    ]
    for i, s in enumerate(steps):
        ax.text(53.5, 45 - i*3.6, s, fontsize=9.6, color=DARK, va='center', zorder=10)

    # === 右下注脚：小结 + 性能压缩成一句话 ===
    panel(ax, 52, 4, 44, 14, fc=LIGHT_GREEN, ec='#2e7d4f', lw=1.2)
    ax.text(53.5, 14.5,
            '小结：',
            fontsize=10.5, color='#2e7d4f', weight='bold', va='center', zorder=10)
    ax.text(57, 14.5,
            'Lyapunov 决策既是可证的次优决策，',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(53.5, 11,
            r'又为后续的模仿学习提供了完美的"专家示范"。',
            fontsize=10, color=DARK, va='center', zorder=10)
    ax.text(53.5, 7,
            r'(理论上可证：长期平均代价偏离最优 $\leq B/V$。)',
            fontsize=9.2, color=GRAY, va='center', style='italic', zorder=10)
    save(fig, '10_principle_lyapunov.png')


# =========================================================
# 11 详细原理④：两阶段迁移
# =========================================================
def slide_11():
    image_slide('11_principle_il.png', '11_principle_il.png')


# =========================================================
# 12 详细原理⑤：三层降级
# =========================================================
def slide_12():
    image_slide('12_principle_twophase.png', '12_principle_twophase.png')


# =========================================================
# 13 详细原理⑥：Top-M + Gossip
# =========================================================
def slide_13():
    image_slide('13_principle_degrade.png', '13_principle_degrade.png')


# =========================================================
# 14 关键算法伪代码
# =========================================================

# =========================================================
# 14 详细原理⑥：Top-M 乐观复制 + Lamport-Gossip
# =========================================================
def slide_14():
    image_slide('14_principle_gossip.png', '14_principle_gossip.png')

def slide_15():
    fig, ax = new_slide()
    header(ax, '关键算法伪代码')

    # 算法 1
    ax.text(5, 84, '算法 1  Lyapunov 在线决策', fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    code1 = (
        "Q ← 0;  a_prev ← initial_gw\n"
        "for t = 0, 1, 2, …:\n"
        "    rem ← topo.remaining_visibility(t)\n"
        "    L   ← gateway_loads(t)\n"
        "    vis ← topo.visible[t]\n"
        "    for a in 1..N:\n"
        "        interrupt ← (not vis[a]) or (rem[a] < T_h)\n"
        "        c_a ← α·interrupt + β·L[a] + γ·(a ≠ a_prev)\n"
        "        s[a] ← V·c_a + Q·(a ≠ a_prev)\n"
        "    a* ← argmin(s)\n"
        "    if a* ≠ a_prev:\n"
        "        trigger_two_phase_migration(a_prev → a*)\n"
        "    Q ← max(Q + (a*≠a_prev) − C_max·Δt, 0)\n"
        "    a_prev ← a*"
    )
    ax.text(5.5, 80, code1, fontsize=8.2, color=DARK, va='top',
            family='monospace', zorder=10,
            bbox=dict(boxstyle='round,pad=0.5', fc='#f6f4fb', ec=PURPLE, lw=0.8))

    # 算法 2
    ax.text(5, 38, '算法 2  两阶段迁移 + 三层降级', fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    code2 = (
        "def migrate(A, bw, prop, lead, T_phys):\n"
        "    snap  ← A.dynamic.snapshot()\n"
        "    send(A.static → B);  wait(lead)\n"
        "    delta ← A.dynamic.diff_bytes_since(snap)\n"
        "    t_sync ← delta/(bw·η) + prop\n"
        "    if t_sync ≤ T_phys:        return SEAMLESS,    migrate_all\n"
        "    sel,b ← select_by_completion(A.dyn, ≥0.5)\n"
        "    if b/(bw·η)+prop ≤ T_phys: return DEGRADED_1,  sel\n"
        "    sel,b ← select_by_completion(…, high_prio_only=True)\n"
        "    if b/(bw·η)+prop ≤ T_phys: return DEGRADED_2,  sel\n"
        "    return FAILED, hard_handoff"
    )
    ax.text(5.5, 36, code2, fontsize=8.2, color=DARK, va='top',
            family='monospace', zorder=10,
            bbox=dict(boxstyle='round,pad=0.5', fc='#f6f4fb', ec=PURPLE, lw=0.8))

    # 算法 3
    ax.text(52, 84, '算法 3  Top-M 乐观复制 + Gossip', fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    code3 = (
        "def replicate_static(A, candidates, M):\n"
        "    scores ← [ΔT_i − 50·L_i  for i in candidates]\n"
        "    top_M  ← topk(scores, M)\n"
        "    for g in top_M:\n"
        "        g.replica_store.install(\n"
        "            (A.static, version=v, ttl=ΔT_g))\n\n"
        "def gossip_round(stores):       # every 10 s\n"
        "    for g in stores:\n"
        "        for msg in g.announce():\n"
        "            for other in stores − {g}:\n"
        "                if other.replicas[msg.scid].v < msg.v:\n"
        "                    other.evict(msg.scid)\n"
        "        g.evict_stale(now)"
    )
    ax.text(52.5, 80, code3, fontsize=8.2, color=DARK, va='top',
            family='monospace', zorder=10,
            bbox=dict(boxstyle='round,pad=0.5', fc='#f6f4fb', ec=PURPLE, lw=0.8))

    ax.text(52, 38, '算法核心特性总结', fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    feats = [
        r'Lyapunov 闭式 $O(N)$，每时隙 < 1 ms；',
        '两阶段迁移：Pre-copy + Stop-copy + 三层降级；',
        r'Top-M 复制：score = $\Delta T - 50\!\cdot\!L$；',
        'Gossip 周期 10 s + Lamport 逻辑时钟；',
        '全模块开源；单元测试 31 个；',
        '推理延迟可上界，决策周期 5000× 富余。',
    ]
    for i, t in enumerate(feats):
        ax.text(52.5, 33 - i*3.6, '•', fontsize=11, color=GOLD, va='center', zorder=10)
        ax.text(54.5, 33 - i*3.6, t, fontsize=10, color=DARK, va='center', zorder=10)
    save(fig, '15_pseudocode.png')

# =========================================================
# 15 实验设计
# =========================================================
def slide_16():
    fig, ax = new_slide()
    header(ax, '实验设计：合成星座 + 4 方案对比 + 5 个独立测试场次')

    # 左：实验场景
    ax.text(5, 82, '实验场景', fontsize=12.5, color=PURPLE, weight='bold')
    rows = [
        ('AOS 卫星',     r'1 颗  极轨 $i=87^\circ$  高度 400 km'),
        ('IPv6 网关',    r'16 颗 $i=53^\circ$  高度 550 km  等 RAAN 间距'),
        ('ISL 最大距离', r'$D_{\max}=3500$ km  (保守工程取值)'),
        ('仿真时长',     '训练 3600 s × 8 场次 / 测试 1800 s × 5 场次'),
        ('AOS 帧速率',   '300 帧 / 秒'),
        ('决策时隙',     r'1 s   物理切换窗口 $T_{\mathrm{phys}}=500$ ms'),
    ]
    for i, (k, v) in enumerate(rows):
        y = 77 - i*4
        ax.text(7, y, k, fontsize=11, color=PURPLE, va='center', weight='bold')
        ax.text(22, y, v, fontsize=10.5, color=DARK, va='center')

    # 右：实验环境
    ax.text(55, 82, '实验环境', fontsize=12.5, color=PURPLE, weight='bold')
    env = [
        ('GPU',     'NVIDIA RTX 4090 (24 GB) × 1'),
        ('OS',      'Linux 5.10'),
        ('Python',  '3.10  +  torch 2.8 cu128'),
        ('仿真器',  'SimPy 4.1 离散事件驱动'),
        ('轨道库',  'Skyfield 1.54 + 合成 TLE'),
        ('绘图',    'matplotlib 3.10 + TensorBoard 2.20'),
    ]
    for i, (k, v) in enumerate(env):
        y = 77 - i*4
        ax.text(56, y, k, fontsize=11, color=PURPLE, va='center', weight='bold')
        ax.text(64, y, v, fontsize=10.5, color=DARK, va='center')

    # 下：4 方案对比表
    ax.text(5, 50, '4 个对比方案', fontsize=12.5, color=PURPLE, weight='bold')
    headers = ['方案', '决策', '状态迁移', '说明']
    schemes = [
        ('Reactive',       '当前网关失效才切',           '硬切',
         '弱基线 — 被动式，几乎不主动迁移'),
        ('Max-Visibility', r'贪心选 $\Delta T$ 最大',    '硬切',
         '贪心基线 — 只看剩余可见时长，不考虑负载'),
        ('MPTCP-style',    '综合分 + 60 s 迟滞',         '硬切',
         '强基线 — 传统多路径思想移植'),
        ('Ours',           '模仿学习网络 (IL)',          '两阶段 + 三层降级 + 多副本',
         '本方案 — Lyapunov 离线 oracle 蒸馏后部署'),
    ]
    col_xs = [5, 22, 45, 70]; y0 = 44
    ax.add_patch(Rectangle((5, y0 - 1), 90, 3.5, fc=PURPLE))
    for c, h in enumerate(headers):
        ax.text(col_xs[c] + 0.5, y0 + 0.7, h, fontsize=10.5,
                color='white', weight='bold', va='center')
    for r, row in enumerate(schemes):
        y = y0 - 3.6 - r*4.5
        is_ours = (r == len(schemes) - 1)
        bg = LIGHT_GREEN if is_ours else (LIGHT_PURPLE if r % 2 == 0 else None)
        if bg is not None:
            ax.add_patch(Rectangle((5, y - 1.6), 90, 4.2, fc=bg))
        for c, v in enumerate(row):
            color = '#2e7d4f' if is_ours and c == 0 else (PURPLE if c == 0 else DARK)
            weight = 'bold' if c == 0 else 'normal'
            ax.text(col_xs[c] + 0.5, y + 0.7, v, fontsize=10,
                    color=color, weight=weight, va='center')

    ax.text(5, 12,
            '指标体系：丢包率 PLR (%)、端到端时延 (ms)、切换次数、总中断时长 (s)、迁移分片数、'
            '平均奖励、决策延迟。\n'
            '统计方法：5 个独立负载场次 → mean ± std；显著性比较采用配对 t-test (本方案 vs MPTCP)。',
            fontsize=10, color=GRAY, va='top', linespacing=1.6, style='italic')
    save(fig, '16_exp_design.png')


# =========================================================
# 17 仿真系统架构与平台搭建
# =========================================================
def slide_17():
    fig, ax = new_slide()
    header(ax, '高保真离散事件驱动仿真平台构建')

    ax.text(4, 84,
            '为了让 4 种方案在严格同等条件下对比，我们自研了一套离散事件驱动的卫星协议转换\n'
            '仿真平台，覆盖"轨道动力学 → 链路 → 协议栈 → 决策 → 状态迁移 → 指标"的端到端链路。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.65, zorder=10)

    # ===== 左：平台分层 =====
    title_panel(ax, 4, 28, 46, 50, '平台分层架构', color=PURPLE, fc=LIGHT_PURPLE)
    layers = [
        ('① 轨道动力学层', '#3666b8',
         'Skyfield 1.54 + 合成 TLE，按 SGP4 推算\n'
         '每秒位置；逐秒输出距离 / 可见性 / ΔT。'),
        ('② 链路层', '#3666b8',
         'ISL 带宽 = 反距离平方模型；\n'
         '大气切线高度约束 (D_max ≈ 3500 km)。'),
        ('③ 协议栈层', '#c8651f',
         'AOS 帧 (256 B 定长) + IPv6 报文 (UDP/IPv6\n'
         '封装)；CCSDS 跨帧分片重组与 M_PDU 处理。'),
        ('④ 决策器层 (可插拔)', PURPLE,
         '统一 Decider 接口；4 种实现并存：\n'
         'Reactive / Max-Vis / MPTCP-style / Ours-IL。'),
        ('⑤ 状态迁移层', '#c8651f',
         '两阶段 Pre-copy + Stop-copy；\n'
         '三层降级兜底；多副本 Gossip 同步。'),
        ('⑥ 指标采集层', '#2e7d4f',
         '逐秒记录 PLR / E2E / 切换 / 迁移 / 决策延迟，\n'
         '聚合到 .pkl + JSON + Markdown 报告。'),
    ]
    for i, (name, color, body) in enumerate(layers):
        y = 73 - i * 7.5
        ax.add_patch(FancyBboxPatch((5.5, y - 3.0), 13.5, 5.8,
                                    boxstyle='round,pad=0.2,rounding_size=0.4',
                                    fc=color, ec=color, alpha=0.92, zorder=3))
        ax.text(12.2, y - 0.1, name, ha='center', va='center',
                fontsize=9.5, color='white', weight='bold', zorder=11)
        ax.text(20.5, y - 0.1, body, fontsize=9.3, color=DARK,
                va='center', linespacing=1.55, zorder=10)

    # ===== 右上：仿真核心机制 =====
    title_panel(ax, 52, 50, 44, 28,
                'SimPy 离散事件驱动核心', color='#3666b8', fc=LIGHT_BLUE)
    ax.text(53.5, 72,
            '· **事件驱动** 而非时间步进：报文到达、可见性变化、\n'
            '   切换触发、Gossip 周期均以"事件"入队；',
            fontsize=9.5, color=DARK, va='top', linespacing=1.65, zorder=10)
    ax.text(53.5, 65,
            '· **确定性可复现**：固定 seed → 完全相同的事件序列；',
            fontsize=9.5, color=DARK, va='top', zorder=10)
    ax.text(53.5, 61.5,
            '· **微秒级时序精度**：事件队列按时间戳严格排序；',
            fontsize=9.5, color=DARK, va='top', zorder=10)
    ax.text(53.5, 58,
            r'· **加速比 200×**：引入 $O(1)$ 完成检测后，',
            fontsize=9.5, color=DARK, va='top', zorder=10)
    ax.text(53.5, 54.5,
            '   单次 30 min 仿真由 600 s → 3 s。',
            fontsize=9.5, color=DARK, va='top', zorder=10)

    # ===== 右下：规模 + 复现 =====
    title_panel(ax, 52, 16, 44, 32, '仿真规模与可复现性',
                color='#2e7d4f', fc=LIGHT_GREEN)
    rows = [
        ('单次仿真', '30 分钟 × 300 包/秒 × 16 候选 ≈ 100 万事件'),
        ('独立场次', '5 个不同负载种子，结果取 mean ± std'),
        ('方案规模', '4 种方案 × 5 场次 = 20 次仿真，约 90 秒完成'),
        ('硬件需求', '单台 RTX 4090 + 8 GB RAM (可用普通笔记本)'),
        ('一键复现', 'make full GPU=0 → 15 分钟产出全部图表'),
        ('开源测试', '31 个单元测试覆盖关键路径'),
    ]
    for i, (k, v) in enumerate(rows):
        y = 42 - i * 4
        ax.text(53.5, y, '· ' + k + '：',
                fontsize=9.7, color='#2e7d4f', weight='bold', va='center', zorder=10)
        ax.text(66, y, v, fontsize=9.4, color=DARK, va='center', zorder=10)

    # 底部一句话
    panel(ax, 4, 4, 92, 9, fc=LIGHT_PURPLE, ec=PURPLE, lw=1.2)
    ax.text(50, 8.5,
            '设计准则：把"星历 / 协议栈 / 决策 / 迁移"完全解耦，新决策器只需实现 Decider 接口即可插入对比。',
            ha='center', va='center', fontsize=11,
            color=PURPLE, weight='bold', zorder=11)
    save(fig, '17_sim_platform.png')


# =========================================================
# 18 实验结果①：训练
# =========================================================
def slide_18():
    fig, ax = new_slide()
    header(ax, '实验结果①：本方案 (Ours) 的小网络训练情况')

    add_image(ax, os.path.join(FIG_DIR, 'fig3_il_training.png'), 4, 32, 44, 46)
    ax.text(4, 28,
            '图：小网络训练曲线  (RTX 4090，60 epoch)\n'
            '蓝/绿：训练 / 验证损失；橙：决策与"老师"一致比例。\n'
            '5 epoch 内损失由 0.8 跌至 < 0.02；60 epoch 收敛于 0.0092。',
            fontsize=10, color=GRAY, va='top', linespacing=1.55, style='italic')

    # 右上：训练结果指标
    title_panel(ax, 52, 56, 43, 28, '训练结果：精度近乎完美',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(54, 75,
            '· 与"老师"决策一致比例：',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(54, 71.5,
            '   60 epoch 时达 99.91 %；第 5 epoch 已达 99.7 %；',
            fontsize=10.2, color='#2e7d4f', weight='bold', va='center', zorder=10)
    ax.text(54, 67,
            '· 验证损失：60 epoch 收敛于 0.0092；',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(54, 63.5,
            '· 训练时长：仅 30 秒（RTX 4090）；',
            fontsize=10.5, color=DARK, va='center', zorder=10)
    ax.text(54, 60,
            '· 在所有测试场次上，本方案与"老师"的决策序列完全一致。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55, zorder=10)

    # 右下：工程意义
    title_panel(ax, 52, 22, 43, 30, '训练高效的工程意义',
                color='#2e7d4f', fc=LIGHT_GREEN)
    ax.text(54, 45,
            '· **训练快**：30 秒 → 任何参数调整都可快速迭代；',
            fontsize=10.2, color=DARK, va='top', linespacing=1.65, zorder=10)
    ax.text(54, 41,
            '· **样本省**：仅需 4.3 万条专家轨迹即可饱和；',
            fontsize=10.2, color=DARK, va='top', linespacing=1.65, zorder=10)
    ax.text(54, 37,
            '· **精度高**：几乎"无损"复制了"老师"的决策能力；',
            fontsize=10.2, color=DARK, va='top', linespacing=1.65, zorder=10)
    ax.text(54, 33,
            '· **可上星**：45 K 参数、180 KB 权重、推理 < 0.2 ms。',
            fontsize=10.2, color=DARK, va='top', linespacing=1.65, zorder=10)
    ax.text(54, 26.5,
            '一句话：本方案部署版的实际效果 = "老师"的理论最优效果。',
            fontsize=10, color='#2e7d4f', weight='bold', va='center',
            linespacing=1.55, zorder=10)

    ax.text(4, 16,
            '图怎么看：左 y 轴是训练损失（越低越好），右 y 轴是与"老师"决策一致的比例（越高越好）。\n'
            '5 epoch 后曲线基本不动，说明小网络已经把"老师"的本事完整学到，再加层加宽也不会更好。\n'
            '这正是后面主表中 Ours 能拿到接近"理论最优"指标的根本原因。',
            fontsize=10, color=GRAY, va='top', linespacing=1.6, style='italic')
    save(fig, '18_train_results.png')

# =========================================================
# 18 主表
# =========================================================
def slide_19():
    fig, ax = new_slide()
    header(ax, '实验结果②：综合性能指标  (5 个独立场次 mean ± std)')

    headers = ['方案', 'PLR (%)', 'E2E (ms)', '切换次数', '总中断 (s)', '切换中丢分片']
    rows = [
        ('Reactive',       '0.233 ± 0.000',  '6.07 ± 0.00',  '3.0 ± 0.0',
         '1.50 ± 0.00',  '175 240'),
        ('Max-Visibility', '0.275 ± 0.000',  '7.82 ± 0.00',  '3.0 ± 0.0',
         '1.50 ± 0.00',  '145 279'),
        ('MPTCP-style',    '6.382 ± 1.454',  '8.60 ± 0.35',  '69.6 ± 17.8',
         '34.80 ± 8.89', '146 853 ± 3 040'),
        ('Ours',           '0.000 ± 0.000',  '6.24 ± 0.00',  '1.0 ± 0.0',
         '0.00 ± 0.00',  '0'),
    ]
    col_xs = [5, 22, 38, 54, 68, 82]
    y0 = 78
    ax.add_patch(Rectangle((5, y0 - 1.2), 90, 4, fc=PURPLE))
    for c, h in enumerate(headers):
        ax.text(col_xs[c] + 0.3, y0 + 0.8, h, fontsize=11, color='white',
                weight='bold', va='center')
    for r, row in enumerate(rows):
        y = y0 - 4.5 - r * 5.0
        is_ours = (r == len(rows) - 1)
        if is_ours:
            ax.add_patch(Rectangle((5, y - 1.8), 90, 4.4,
                                   fc=LIGHT_GREEN, ec='#2e7d4f', lw=1.2))
        elif r % 2 == 0:
            ax.add_patch(Rectangle((5, y - 1.8), 90, 4.4, fc=LIGHT_PURPLE))
        for c, v in enumerate(row):
            color = '#2e7d4f' if is_ours else (PURPLE if c == 0 else DARK)
            ax.text(col_xs[c] + 0.3, y + 0.7, v, fontsize=10.5, color=color,
                    weight=('bold' if is_ours else 'normal'), va='center')

    ax.text(5, 48, '核心结论', fontsize=13, color=PURPLE, weight='bold')
    bullets = [
        '本方案是所有方案中**唯一同时取得 PLR = 0 % 且 0 中断**的方案；',
        'Reactive / Max-Visibility 即使可见性策略最优，由于没有状态迁移，每次硬切仍丢约 15 万个分片；',
        'MPTCP-style 是确定性卫星场景的**反模式**：60 s 迟滞误判触发 70 次切换 → 丢包率 6.4 %；',
        '本方案 E2E 时延 6.24 ms，与最快基线 (Reactive 6.07 ms) 几乎相当，',
        '   说明"零中断 / 零丢包"不是以延迟为代价换取的；',
        '切换次数仅 1 次（5 个场次都一样），证明 IL 决策器在等效几何下输出确定的最优序列。',
    ]
    for i, t in enumerate(bullets):
        ax.text(5.5, 43 - i*4.5, '•', fontsize=12, color=GOLD)
        ax.text(7.5, 43 - i*4.5, t, fontsize=11, color=DARK, va='center')
    save(fig, '19_main_table.png')

# =========================================================
# 19 关键可视化
# =========================================================
def slide_20():
    fig, ax = new_slide()
    header(ax, '实验结果③：关键可视化  (4 张图逐图解读)')

    # 2x2 单元格：每格 标题(顶) + 图(中) + 文字解读(底)
    # 单元格宽 44、高 36；左 x=4..48，右 x=50..94
    cells = [
        # (cell_x, cell_y, img_file, title, analysis)
        (4, 46, 'fig4_loss_rate.png', '图 4  丢包率随时间变化',
         'Reactive / Max-Visibility 在 1100–1800 s 因硬切丢包出现孤立尖峰；\n'
         'MPTCP-style 因频繁切换全程高位；**本方案曲线始终贴底 = 0**。'),
        (50, 46, 'fig7_load_balance.png', '图 7  16 颗候选网关的负载均衡',
         '横轴 16 颗 IPv6 网关；纵轴各方案承载分片数。\n'
         '本方案变异系数 CV = 0.64，远优于 MPTCP-style 的 1.63（均衡性更好）。'),
        (4, 8, 'fig5_latency_cdf.png', '图 5  端到端时延累积分布 (CDF, 对数 x 轴)',
         'MPTCP-style 因频繁切换出现明显长尾 (P99 > 10 ms)；\n'
         '**本方案与 Reactive / Max-Vis 重合于左侧最快段**，零中断不以延迟为代价。'),
        (50, 8, 'fig8_summary.png', '图 8  4 方案 × 5 场次 mean ± std 汇总柱状图',
         '一图概括 PLR / E2E / 切换数 / 中断时长 4 个核心指标。\n'
         '本方案在 PLR / 切换 / 中断 3 项几乎为 0；MPTCP-style 中断误差棒最长。'),
    ]
    CW, CH = 44, 36
    for cx, cy, img, title, an in cells:
        # 单元格淡底
        panel(ax, cx, cy, CW, CH, fc='white', ec=PURPLE, lw=0.8, alpha=0.85)
        # 标题（顶部，紧贴 panel 顶下方 1 单位）
        ax.text(cx + 1.5, cy + CH - 2, title, fontsize=10.5, color=PURPLE,
                weight='bold', va='top', zorder=10)
        # 图（中部，占大头）
        add_image(ax, os.path.join(FIG_DIR, img),
                  cx + 2, cy + 8, CW - 4, CH - 14)
        # 文字解读（底部 7 单位高）
        ax.text(cx + 1.5, cy + 6.5, an, fontsize=9.5, color=DARK,
                va='top', linespacing=1.55, zorder=10)
    save(fig, '20_visualizations.png')

# =========================================================
# 20 结论
# =========================================================
def slide_21():
    fig, ax = new_slide()
    header(ax, '结论')

    # ============ 第 1 行 ============
    # 左上：本研究实现了什么
    title_panel(ax, 4, 60, 46, 23, '本研究实现了什么', color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 76,
            '面向 LEO 异构星座中“AOS <-> IPv6 协议转换网关”的高动态切换难题，\n'
            '建成 “理论 → 算法 → 系统 → 实测” 完整闭环。',
            fontsize=9.8, color=DARK, va='top', linespacing=1.6, zorder=10)
    achievs = [
        r'理论：证明 Lyapunov drift-plus-penalty 在卫星场景的 $[O(1/V),O(V)]$ 上界；',
        r'机制：$\mathcal{C}_{\mathrm{static}}/\mathcal{C}_{\mathrm{dynamic}}$ 二分模型 + 两阶段 + 三层降级；',
        '协议：Top-M 乐观复制 + Lamport-Gossip，解决多覆盖状态分裂；',
        '系统：开源 SimPy 平台 + 31 单元测试 + 5 seed × 30 min 仿真。',
    ]
    for i, t in enumerate(achievs):
        y = 70 - i*2.6
        ax.text(6, y, '•', fontsize=10, color=GOLD, va='center', zorder=10)
        ax.text(8, y, t, fontsize=9.3, color=DARK, va='center', zorder=10)

    # 右上：场景化定量结果  (核心新增)
    title_panel(ax, 52, 60, 45, 23,
                'AOS <-> IPv6 转换场景下的实测结果', color='#2e7d4f', fc=LIGHT_GREEN)
    scen_results = [
        ('LEO 单 AOS + 16 颗 IPv6 网关、30 min 持续切换',
         'PLR = 0.00 %、0 中断、E2E 6.24 ms (vs 基线 6.07–8.60)'),
        ('300 pps · 100 万事件 · 5 种子',
         '切换数 1.0、迁移分片 ~15 万、零丢分片 (跨全部种子)'),
        ('星上 CPU 推理路径',
         '决策延迟 < 0.2 ms / 时隙，对 $T_{\\mathrm{phys}}=500$ ms 富余 2500×'),
        ('多覆盖 (k ≥ 2) 状态分裂场景',
         '179 轮 Gossip 后副本最终一致，开销 << ISL 带宽'),
    ]
    for i, (cond, result) in enumerate(scen_results):
        y = 78 - i*5
        ax.text(53.5, y, '场景：' + cond, fontsize=9.2, color='#2e7d4f',
                weight='bold', va='center', zorder=10)
        ax.text(53.5, y - 2.6, '→ ' + result, fontsize=9.3, color=DARK, va='center', zorder=10)

    # ============ 第 2 行：场景适用性（三块子面板，互不重叠） ============
    ax.text(4, 56,
            '在 AOS <-> IPv6 协议转换网关侧可直接受益的具体业务场景：',
            fontsize=11, color=PURPLE, weight='bold', va='center', zorder=10)
    apps = [
        ('窄带遥测 / 遥控\n(气象 · 海事 · 灾区)', '#2e7d4f', LIGHT_GREEN,
         '长时段会话 + 低速率，对零丢包敏感；\n'
         '两阶段迁移保证 CCSDS 长帧重组上下文不丢；\n'
         '实测每次切换迁 ~15 万分片、0 丢包。'),
        ('实时控制 / 视频回传', '#c8651f', LIGHT_ORANGE,
         '端到端延迟稳定 6.24 ms，与无切换基线一致；\n'
         '切换瞬间 0 中断，画面无卡顿；\n'
         '适用：UAV 回传、星载视频直播、指控链路。'),
        ('多运营商共建共享星座', '#3666b8', LIGHT_BLUE,
         '多颗 IPv6 网关来自不同运营商时，\n'
         'Top-M + Gossip 无需 leader、副本最终一致；\n'
         '适用：千帆 + OneWeb 互联、卫星 MVNO 漫游。'),
    ]
    cell_w = 30; gap = 1.5; cy_panel = 32; ch_panel = 21
    for i, (title, color, fc, body) in enumerate(apps):
        cx = 4 + i*(cell_w + gap)
        panel(ax, cx, cy_panel, cell_w, ch_panel, fc=fc, ec=color, lw=1.2)
        ax.text(cx + 1.2, cy_panel + ch_panel - 2, title, fontsize=10,
                color=color, weight='bold', va='top', linespacing=1.4, zorder=10)
        ax.text(cx + 1.2, cy_panel + ch_panel - 8, body, fontsize=9, color=DARK,
                va='top', linespacing=1.65, zorder=10)

    # ============ 第 3 行：局限性 + 下一步 ============
    title_panel(ax, 4, 5, 46, 25, '局限性', color='#a52828', fc=LIGHT_RED)
    lims = [
        '当前仅支持单颗 AOS；多 AOS 并发未建博弈模型；',
        'Pre-copy 与业务流共享 ISL，未严格抢占调度；',
        'Gossip 节点假设可信，HMAC/抗女巫尚未编码；',
        'TLE 24 h 后陈旧，长仿真未覆盖更新流程。',
    ]
    for i, t in enumerate(lims):
        y = 25 - i*3.0
        ax.text(5.5, y, '·', fontsize=11, color='#a52828', va='center', zorder=10)
        ax.text(7.5, y, t, fontsize=9.2, color=DARK, va='center', zorder=10)
    ax.text(5.5, 11.5,
            '说明：以上局限来自仿真假设，不影响算法本身的正确性。',
            fontsize=8.8, color=GRAY, va='top', style='italic', zorder=10)

    title_panel(ax, 52, 5, 45, 25, '下一步工作', color='#3666b8', fc=LIGHT_BLUE)
    futs = [
        '多 AOS 扩展：拍卖 / 博弈机制实现资源共享；',
        'LSTM 在线修正陈旧 TLE，减小预测误差；',
        'SDR / FPGA 硬件在环 (HIL) 验证决策延迟；',
        '与课题前序工作 (地址、报文) 端到端联调；',
        '安全：Gossip HMAC + 抗女巫 + 副本签名。',
    ]
    for i, t in enumerate(futs):
        y = 25 - i*3.0
        ax.text(53.5, y, '·', fontsize=11, color='#3666b8', va='center', zorder=10)
        ax.text(55.5, y, t, fontsize=9.2, color=DARK, va='center', zorder=10)

    save(fig, '21_conclusion.png')


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in [slide_01, slide_02,
               slide_03, slide_04, slide_05, slide_06, slide_07, slide_08,
               slide_09, slide_10, slide_11, slide_12, slide_13, slide_14,
               slide_15, slide_16, slide_17,
               slide_18, slide_19, slide_20, slide_21]:
        fn()

if __name__ == '__main__':
    main()
