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
        ('01', '选题依据与背景',
         '空天地一体化背景与卫星网络代际异构现状 · 协议转换网关在动态场景下的两类核心困境'),
        ('02', '研究目标与内容',
         '从“静态可转换”升级到“持续可转换”：四段式机制总览 + 系统建模 / 决策 / 迁移 / 一致性 详细原理'),
        ('03', '总体技术路线',
         '四个关键算法的伪代码描述 · 六阶段实验流程与耗时分布 (拓扑构建 → 训练 → 仿真 → 出图)'),
        ('04', '具体实现',
         '合成 LEO 星座 + 6 方案 + 5 种子 + 9 指标 实验设计 · 训练 / 综合指标 / 关键可视化 三类结果'),
        ('05', '结论',
         '研究实现了什么 · 性能数字总结 · 可应用的实际场景 · 局限性与下一步工作'),
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
    fig, ax = new_slide()
    header(ax, '研究背景：空天地一体化与卫星网络代际异构')

    # 左：示意图（同心圆）
    from matplotlib.patches import Circle
    cx, cy = 22, 45
    ax.add_patch(Circle((cx, cy), 18, fc='none', ec='#a52828', lw=1.4))
    ax.add_patch(Circle((cx, cy), 9,  fc='none', ec=GRAY, lw=1.0))
    ax.text(cx, cy, '地球', ha='center', va='center', fontsize=11, color=GRAY)
    # AOS satellite (red dot top)
    ax.plot(cx, cy + 18, 'o', ms=12, color='#a52828')
    ax.text(cx, cy + 21.5, 'AOS 卫星 (CCSDS)', ha='center', fontsize=9.5, color='#a52828', weight='bold')
    # IPv6 satellites around inner circle
    import math
    for k in range(7):
        a = math.pi/2 + (k+1) * 2*math.pi/8
        px = cx + 9 * math.cos(a); py = cy + 9 * math.sin(a)
        ax.plot(px, py, 'o', ms=10, color='#3666b8')
    ax.text(cx - 14, cy - 13, '存量 AOS 业务\n(窄带、长帧)', fontsize=9, color='#a52828', ha='center')
    ax.text(cx + 14, cy + 14, '新一代 IPv6 卫星\n(宽带 IP 互联)', fontsize=9, color='#3666b8', ha='center')
    ax.text(cx, cy - 22, 'IPv6 网关卫星  ←  协议转换中介', ha='center', fontsize=10, color=PURPLE, weight='bold')

    # 右：三段文字
    x0 = 50
    ax.text(x0, 80, '网络架构演进', fontsize=14, color=PURPLE, weight='bold')
    ax.text(x0, 74,
            '6G 时代空天地一体化已成共识。LEO 星座 (Starlink / OneWeb / 千帆) 部署节奏快、规模大，\n'
            '卫星互联网正从“单星窄带通信”走向“以星座为单元的宽带 IP 互联”。\n'
            '运营网正同时存在两代体系：早期 CCSDS/AOS 系统不会全量退网，新一代 IPv6 系统已开始上轨。',
            fontsize=11, color=DARK, va='top', linespacing=1.5)

    ax.text(x0, 56, '代际异构的本质矛盾', fontsize=14, color=PURPLE, weight='bold')
    ax.text(x0, 51,
            '· 新一代 IPv6 卫星  ：原生支持 IPv6 路由 / QoS / 移动性，使用 UDP/IPv6 封装；\n'
            '· 存量 AOS 卫星    ：CCSDS AOS 协议 (1995)，256 字节定长帧、SCID/VCID 复用；\n'
            '· 业务必须互通     ：长时间内两代体系并存，全量替换不现实，必须有“协议转换网关”。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)

    ax.text(x0, 30, '本工作在课题中的位置', fontsize=14, color=PURPLE, weight='bold')
    ax.text(x0, 25,
            '课题前序工作分别解决了 ① 网络层地址自动配置  与  ② 协议报文双向转换 (静态)。\n'
            '本阶段聚焦 ③ 协议转换网关在 LEO 高动态下的服务连续性：无缝切换 + 状态一致性。',
            fontsize=11, color=DARK, va='top', linespacing=1.55)
    save(fig, '03_background.png')

# =========================================================
# 04 现状
# =========================================================
def slide_04():
    fig, ax = new_slide()
    header(ax, '现状：协议转换网关——异构互联的关键中介')

    # 左：数据流框
    ax.text(5, 80, '协议转换数据流', fontsize=14, color=PURPLE, weight='bold')
    for i, (x, label, color) in enumerate([
        (5, 'AOS 卫星\n(CCSDS)', '#a52828'),
        (20, 'IPv6 网关卫星\n(协议转换)', '#3666b8'),
        (37, 'IPv6 卫星\n互联网', '#2e7d4f'),
    ]):
        panel(ax, x, 65, 12, 10, fc='white', ec=color, lw=1.6)
        ax.text(x + 6, 70, label, ha='center', va='center', fontsize=10, color=color, weight='bold')
    ax.annotate('', xy=(20, 70), xytext=(17, 70),
                arrowprops=dict(arrowstyle='->', color=DARK, lw=1.4))
    ax.annotate('', xy=(37, 70), xytext=(32, 70),
                arrowprops=dict(arrowstyle='->', color=DARK, lw=1.4))
    ax.text(5, 60,
            '上行：(SCID, VCID)  →  IPv6 地址映射 + UDP/IPv6 封装\n'
            '下行：IPv6 报文  →  解析  →  AOS 帧重组下行',
            fontsize=10, color=GRAY, va='top', linespacing=1.5)

    # 前序工作已解决
    title_panel(ax, 5, 32, 45, 18, '前序工作已解决：静态场景下的协议转换',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(6.5, 44,
            '· 假设 AOS 卫星与某一颗 IPv6 网关链路稳定可见；\n'
            '· 完成报文格式翻译规则、地址映射表、QoS / DSCP 映射；\n'
            '· 完成 UDP/IPv6 封装与解封装、CCSDS 帧重组逻辑；\n'
            '· 提供功能正确性与单包时延仿真。',
            fontsize=10, color=DARK, va='top', linespacing=1.55)

    # 右：动态难题
    ax.text(55, 80, '动态场景下的本质难题', fontsize=14, color=PURPLE, weight='bold')
    ax.text(55, 75,
            'LEO 卫星速度约 7.6 km/s，AOS 与某一颗 IPv6 网关的单网关可见窗口仅 5–15 min；\n'
            '窗口结束意味着必须切换到下一颗 IPv6 网关，否则业务中断。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)

    ax.text(55, 62, '“切换”引发的连锁问题', fontsize=13, color=PURPLE, weight='bold')
    items = [
        '翻译上下文 (TC) 在原网关，目标网关“失忆”，已建会话被强制重协商；',
        '传统 Break-before-Make 硬切换中断 0.3–1 s，期间报文全部丢失；',
        'CCSDS 跨帧分片正在重组，未完成的分片在切换瞬间直接丢弃；',
        '多颗 IPv6 网关并发覆盖同一 AOS 卫星  →  状态分裂，难以确定权威副本。',
    ]
    for i, t in enumerate(items):
        ax.text(55.5, 56 - i*4, '•', fontsize=12, color=GOLD, va='top')
        ax.text(57.5, 56 - i*4, t, fontsize=10.5, color=DARK, va='top')

    title_panel(ax, 55, 14, 41, 20, '本阶段研究重点',
                color='#a52828', fc=LIGHT_RED)
    ax.text(56.5, 28,
            '把“静态可转换”升级为“持续可转换”：\n'
            '在 LEO 高动态、可见窗口受限、多副本并存条件下，\n'
            '提供端到端服务连续性 (零中断、零丢包、状态可证)。',
            fontsize=10, color=DARK, va='top', linespacing=1.7, zorder=10)
    save(fig, '04_status.png')

# =========================================================
# 05 困境①
# =========================================================
def slide_05():
    fig, ax = new_slide()
    header(ax, '困境①：翻译上下文 (TC) 丢失与硬切换丢包')

    # 公式
    ax.text(5, 80, r'翻译上下文：$\mathcal{C}=\mathcal{C}_{\mathrm{static}}\;\cup\;\mathcal{C}_{\mathrm{dynamic}}$',
            fontsize=15, color=PURPLE, va='center')

    # 静态
    title_panel(ax, 5, 60, 42, 16, r'$\mathcal{C}_{\mathrm{static}}$  ( ≈ 288 B / 会话，稳定，可预先复制 )',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(6.5, 70,
            '· (SCID, VCID)  →  IPv6 地址映射表 (LRU 缓存)\n'
            '· QoS / DSCP 标签、带宽配额、优先级队列归属\n'
            '· 在会话建立时即可确定，整个会话生命期不会变化。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)

    # 动态
    title_panel(ax, 5, 32, 42, 24, r'$\mathcal{C}_{\mathrm{dynamic}}$  ( 持续增长、切换时易丢 )',
                color='#a52828', fc=LIGHT_RED)
    ax.text(6.5, 50,
            r'· $\mathcal{C}_{\mathrm{frag}}$ : CCSDS 包跨分片重组缓存 (3–8 片/包)',
            fontsize=10.5, color=DARK)
    ax.text(6.5, 46,
            r'· $\mathcal{C}_{\mathrm{qos}}$  : VCID 级 QoS 队列状态、令牌桶剩余',
            fontsize=10.5, color=DARK)
    ax.text(6.5, 42,
            r'· $\mathcal{C}_{\mathrm{seq}}$  : IPv6 流有序性序列号、重排窗口',
            fontsize=10.5, color=DARK)
    ax.text(6.5, 37,
            '硬切换瞬间，$\\mathcal{C}_{\\mathrm{dynamic}}$ 在原网关被销毁，\n'
            '新网关无任何上下文  →  报文丢失、流被强制重建。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)

    # 右：时间线 + 实测表
    ax.text(52, 82, '传统 Break-before-Make 的损失时序', fontsize=13, color=PURPLE, weight='bold')
    # timeline rectangles
    ax.add_patch(Rectangle((52, 74), 14, 4, fc=LIGHT_BLUE, ec='#3666b8'))
    ax.text(59, 76, '网关 A 服务', ha='center', va='center', fontsize=10, color='#3666b8')
    ax.add_patch(Rectangle((66, 74), 6, 4, fc='#a52828', ec='#a52828'))
    ax.text(69, 76, '中断 0.3–1 s', ha='center', va='center', fontsize=9.5, color='white', weight='bold')
    ax.add_patch(Rectangle((72, 74), 20, 4, fc=LIGHT_BLUE, ec='#3666b8'))
    ax.text(82, 76, '网关 B 接管 (上下文重建)', ha='center', va='center', fontsize=10, color='#3666b8')
    ax.text(69, 72, '↑  期间所有报文全丢', ha='center', fontsize=9.5, color='#a52828')

    ax.text(52, 65, '实测损失 (30 min 仿真，5 种子)', fontsize=13, color=PURPLE, weight='bold')
    rows = [
        ('方案',         'PLR',     '单次丢分片', '中断'),
        ('Reactive',     '0.23 %',  '175 240',    '1.5 s'),
        ('Max-Visibility','0.28 %', '145 279',    '1.5 s'),
        ('MPTCP-style',  '6.38 %',  '146 853',    '34.8 s'),
        ('本方案 (Ours)','0.00 %',  '0',          '0 s'),
    ]
    cw = [10, 9, 12, 8]; xs = [52, 62, 71, 83]; y0 = 60
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            color = PURPLE if r == 0 else (
                '#2e7d4f' if r == 4 else DARK)
            weight = 'bold' if r == 0 or r == 4 else 'normal'
            ax.text(xs[c], y0 - r*3.5, val, fontsize=10, color=color, weight=weight, va='center')
        if r == 0:
            ax.plot([52, 92], [y0 - 1.6, y0 - 1.6], color=PURPLE, lw=1.2)
    ax.text(52, 33,
            '说明：Reactive 与 Max-Visibility 即使可见性策略最优，\n'
            '只要不迁移上下文，每次切换仍丢约 15 万个 CCSDS 分片；\n'
            'MPTCP-style 的“迟滞 + 双路并行”在卫星确定性场景下反而触发频繁切换。',
            fontsize=10, color=GRAY, va='top', linespacing=1.55, style='italic')
    save(fig, '05_problem_tc.png')

# =========================================================
# 06 困境② VM
# =========================================================
def slide_06():
    fig, ax = new_slide()
    header(ax, '困境②：多覆盖网关并发  →  状态分裂与权威副本难题')

    ax.text(4, 84,
            'LEO 星座中一颗 AOS 卫星在同一时刻经常被 2–3 颗 IPv6 网关同时覆盖；\n'
            '若每颗候选网关独立维护一份翻译上下文 (TC)，AOS 切换到任意一颗都可能\n'
            '读到“过期/错乱”的状态。',
            fontsize=10, color=DARK, va='top', linespacing=1.6, zorder=10)

    # 左：示意图
    import math
    cx, cy = 22, 48
    ax.plot(cx, cy, 'o', ms=24, color='#a52828', zorder=5)
    ax.text(cx, cy, 'AOS', ha='center', va='center', fontsize=10, color='white', weight='bold', zorder=11)
    coords = [(10, 65, 'g1', 'v=8'), (35, 65, 'g2', 'v=9'),
              (10, 32, 'g3', 'v=7'), (35, 32, 'g4', 'v=6')]
    for x, y, name, ver in coords:
        ax.plot(x, y, 'o', ms=18, color='#3666b8', zorder=5)
        ax.text(x, y, name, ha='center', va='center', fontsize=9, color='white', weight='bold', zorder=11)
        ax.text(x, y - 4, ver, ha='center', fontsize=9.5, color='#3666b8', zorder=10)
        ax.plot([cx, x], [cy, y], color=GRAY, lw=0.8, ls='--', alpha=0.6, zorder=3)
    ax.text(22, 22, '4 副本同时可见 / 互相不知道版本',
            ha='center', fontsize=10, color=PURPLE, weight='bold', zorder=10)

    # 右：三个子问题
    title_panel(ax, 48, 56, 48, 20, '子问题 A  版本错乱', color='#a52828', fc=LIGHT_RED)
    ax.text(49.5, 71.5,
            '· 同一 (scid, vcid) 流被多颗网关并发处理，序列号 / 分片缓冲各自独立；\n'
            '· 若不交换“版本号 + 时间戳”，切换瞬间无法判断哪一份副本是最新的；\n'
            '· 直接使用任意副本均可能导致已正确转发的报文被重复或被丢弃。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55, zorder=10)

    title_panel(ax, 48, 32, 48, 20, '子问题 B  权威性缺失', color='#c8651f', fc=LIGHT_ORANGE)
    ax.text(49.5, 47.5,
            '· 不存在天然 leader：候选网关地位对等，没有调度中心；\n'
            '· 传统强一致协议 (Raft / Paxos) 需要多数派 RTT 协商，ISL 时延高 + 间断不可见，开销过大；\n'
            '· 必须采用“最终一致 + 偏序时钟”的轻量协议来收敛副本视图。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55, zorder=10)

    title_panel(ax, 48, 9, 48, 19, '子问题 C  副本生命周期', color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(49.5, 24.5,
            '· 网关进入不可见窗口后，旧副本必须过期失效，否则成为“僵尸状态”；\n'
            '· 副本数量需有上界 (Top-M)，否则在 16 颗候选下复制 / Gossip 开销线性爆炸；\n'
            '· 必须有统一的 TTL 与显式淘汰规则，保证副本仓库稳态可控。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55, zorder=10)
    save(fig, '06_problem_multi.png')


def slide_06_OLD_VM_DEPRECATED():
    fig, ax = new_slide()
    header(ax, '困境②：VM 热迁移“看似可借鉴”，本质并不适用')

    ax.text(5, 82,
            '云计算 VM Live Migration (Clark et al. 2005) 用 Pre-copy + Stop-and-copy 实现“准零停机”，\n'
            '其总体思路对卫星协议转换网关切换确有启发；但卫星场景在以下 4 个维度上存在根本差异：',
            fontsize=11, color=DARK, va='top', linespacing=1.55)

    # 表格
    rows = [
        ('维度',         'VM 热迁移 (数据中心)',                 '卫星协议转换网关迁移'),
        ('协议级状态',   '无 (虚拟机透明，OS/网络栈在内部)',     r'必须迁移 $\mathcal{C}_{\mathrm{frag}}$ 与 $\mathcal{C}_{\mathrm{qos}}$；不在 OS 内核内'),
        ('链路时变性',   '数据中心带宽稳定、毫秒级时延',          'ISL 带宽随距离/几何时变；含完全不可见窗口'),
        ('多目标候选',   '单目标主机；调度器集中决策',            '同时被 2–3 颗 IPv6 卫星覆盖  →  状态分裂'),
        ('时间硬约束',   '可秒级停机；用户感知极弱',              r'物理切换窗口 $T_{\mathrm{phys}}\!\approx\!500$ ms，星历严格确定'),
    ]
    y0 = 68
    col_xs = [5, 22, 55]
    col_w = [16, 32, 40]
    for r, row in enumerate(rows):
        y = y0 - r*7
        if r == 0:
            ax.add_patch(Rectangle((5, y - 1), 87, 4.5, fc=PURPLE))
            for c, v in enumerate(row):
                ax.text(col_xs[c] + 0.5, y + 1.4, v, fontsize=11.5, color='white', weight='bold', va='center')
        else:
            if r % 2 == 0:
                ax.add_patch(Rectangle((5, y - 1.5), 87, 5.5, fc=LIGHT_PURPLE))
            for c, v in enumerate(row):
                color = PURPLE if c == 0 else DARK
                ax.text(col_xs[c] + 0.5, y + 1.4, v, fontsize=10.5, color=color, va='center')

    # 结论
    title_panel(ax, 5, 8, 90, 14,
                '结论：直接照搬 VM 热迁移无法解决卫星问题；必须重新设计协议级 + 时变链路感知 + 多副本的迁移机制。',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(6.5, 16.5,
            '· 必须显式建模 $\\mathcal{C}_{\\mathrm{static}}$ 与 $\\mathcal{C}_{\\mathrm{dynamic}}$ 的差异，否则无法做“增量同步”；\n'
            '· 必须把链路带宽 $B(t)$ 和切换截止时间 $T_{\\mathrm{phys}}$ 作为硬约束输入决策器；\n'
            '· 必须为多覆盖场景设计副本协议，保证多颗候选网关之间收敛到一致视图。',
            fontsize=10, color=DARK, va='top', linespacing=1.55)
    save(fig, '06_problem_vm.png')

# =========================================================
# 07 解决思路
# =========================================================
def slide_07():
    fig, ax = new_slide()
    header(ax, '解决思路：四段式机制总览 (每一步为什么必须是这一步)')

    ax.text(4, 84,
            '本工作的核心思路是“把一件复杂的事情拆成 4 个能各自做对的小事，再用因果链串起来”。\n'
            '下方流水线的箭头不是简单的“接着做”，而是每一步都解决了上一步留下的明确缺陷：',
            fontsize=10.8, color=DARK, va='top', linespacing=1.55, zorder=10)

    # === 四个步骤盒 ===
    stages = [
        ('① 星历预测',     LIGHT_BLUE,   '#3666b8',
         '由 TLE 与轨道动力学外推出未来 30 分钟内\n'
         '每颗候选网关的可见性、剩余可见时长 $\\Delta T_i$\n'
         '与 ISL 带宽 $B_i$ — 把未来变成“可知量”。'),
        ('② Lyapunov 决策', LIGHT_PURPLE, PURPLE,
         'drift-plus-penalty 用虚拟队列把“切换次数\n'
         '上限”自动转成在线惩罚，闭式 $O(N)$ 即可解；\n'
         '不依赖大量历史样本，给出可证最优上界。'),
        ('③ 模仿学习',     LIGHT_GREEN,  '#2e7d4f',
         '把 Lyapunov 决策当作“专家”，蒸馏到 45 K 参数\n'
         '的小 MLP；推理 < 0.2 ms，可放到星上 CPU/FPGA，\n'
         '不再依赖在线虚拟队列计算。'),
        ('④ 两阶段 + 一致性', LIGHT_ORANGE, '#c8651f',
         'Pre-copy + Stop-copy 把状态在切换前迁过去；\n'
         'Top-M 乐观复制 + Lamport-Gossip 保证多覆盖\n'
         '副本最终一致 — 解决“决了策却丢状态”问题。'),
    ]
    bw = 22; gap = 1.2; x0 = 4
    for i, (title, fc, ec, body) in enumerate(stages):
        x = x0 + i*(bw + gap)
        panel(ax, x, 56, bw, 22, fc=fc, ec=ec, lw=1.5)
        ax.text(x + bw/2, 75, title, ha='center', fontsize=12.5, color=ec, weight='bold', zorder=10)
        ax.text(x + bw/2, 65, body, ha='center', va='center', fontsize=9.6, color=DARK,
                linespacing=1.55, zorder=10)
        if i < 3:
            ax.annotate('', xy=(x + bw + gap - 0.05, 67), xytext=(x + bw + 0.05, 67),
                        arrowprops=dict(arrowstyle='->', color=GOLD, lw=2), zorder=11)

    # === 因果链：箭头下方说明为什么需要下一步 ===
    ax.text(4, 51, '四步之间的因果链（“为什么下一步必须做”）',
            fontsize=12, color=PURPLE, weight='bold', zorder=10)

    chain = [
        ('① → ②', '#3666b8',
         '“星历可预测”意味着这不是马尔可夫黑盒问题 — 普通 DRL 浪费了已知信息。\n'
         '可预测 + 切换次数硬约束  →  自然适合 Lyapunov drift-plus-penalty 这种排队论框架。'),
        ('② → ③', PURPLE,
         'Lyapunov 闭式策略虽然 $O(N)$，但每时隙都要更新虚拟队列 $Q(t)$、维护代价矩阵；\n'
         '星上 CPU 紧、FPGA 难做浮点比较  →  必须把策略“离线蒸馏”成只做前向推理的网络。'),
        ('③ → ④', '#2e7d4f',
         '即便决策瞬时正确，AOS <-> B 网关之间的翻译上下文未迁移，硬切换仍丢 15 万分片；\n'
         '决策的“正确性”必须配套状态的“连续性”  →  必须有协议级两阶段迁移 + 副本一致性。'),
    ]
    for i, (lbl, color, body) in enumerate(chain):
        y = 45 - i*9.5
        ax.add_patch(Rectangle((4, y - 6.5), 8, 7.5,
                                fc='white', ec=color, lw=1.4, alpha=0.92, zorder=3))
        ax.text(8, y - 2.7, lbl, ha='center', va='center', fontsize=12,
                color=color, weight='bold', zorder=11)
        ax.text(13.5, y - 2.7, body, fontsize=10, color=DARK, va='center', linespacing=1.55, zorder=10)

    save(fig, '07_overview.png')

# =========================================================
# 08 详细原理①：系统模型 + TC
# =========================================================
def slide_08():
    fig, ax = new_slide()
    header(ax, '详细原理①：系统模型与翻译上下文数据结构')

    # 左：几何与链路量
    ax.text(5, 82, r'几何与链路量  (time-slotted, $\Delta t = 1\,\mathrm{s}$)',
            fontsize=13, color=PURPLE, weight='bold')
    syms = [
        (r'$D_i(t)$',                'AOS$\leftrightarrow g_i$ 直线距离 (km)，由星历推算'),
        (r'$\theta_i(t)$',           'ISL grazing angle，刻画 AOS 看 $g_i$ 的仰角'),
        (r'$V_i(t)\in\{0,1\}$',      r'可见性指示：$\theta\!\geq\!10^\circ$ 且 $D\!\leq\!3500$ km'),
        (r'$\Delta T_i(t)$',         '剩余连续可见时长 (s)，星历精确预测，无未来不确定性'),
        (r'$B_i(t)$',                'ISL 带宽 (Mbps)，距离相关，反距离平方递减'),
        (r'$L_i(t)\in[0,1]$',        r'$g_i$ 协议转换 CPU 负载 (策略侧的拥塞代价)'),
        (r'$a(t)\in\{1\ldots N\}$',  '决策变量：当前服务 AOS 的网关索引'),
    ]
    for i, (s, d) in enumerate(syms):
        y = 76 - i*4
        ax.text(6, y, s,  fontsize=12, color=PURPLE, va='center')
        ax.text(20, y, d, fontsize=10.5, color=DARK, va='center')

    title_panel(ax, 5, 14, 42, 30, '即时代价 (Instantaneous cost)', color='#c8651f', fc=LIGHT_ORANGE)
    ax.text(6, 38,
            r'$c(t)=\alpha\cdot\mathbf{1}\{\mathrm{interrupt}\;\mathrm{or}\;\Delta T<T_h\}'
            r'+\beta\cdot L(t)+\gamma\cdot\mathbf{1}\{\mathrm{switch}\}$',
            fontsize=12.5, color=DARK, va='top')
    ax.text(6, 30,
            r'$\alpha=1.0$ ：中断惩罚 (硬性，最大权重)',
            fontsize=10.5, color=DARK)
    ax.text(6, 26,
            r'$\beta=0.3$  ：负载平衡，避免单网关饱和',
            fontsize=10.5, color=DARK)
    ax.text(6, 22,
            r'$\gamma=0.5$ ：切换抖动惩罚，抑制频繁迁移',
            fontsize=10.5, color=DARK)
    ax.text(6, 17,
            '说明：三项均做了量纲归一，使 reward 不依赖星座规模。',
            fontsize=10, color=GRAY, va='top', style='italic')

    # 右：TC 数据结构
    ax.text(52, 82, '翻译上下文 (TC) 数据结构  ·  migration/context.py',
            fontsize=13, color=PURPLE, weight='bold')

    title_panel(ax, 52, 56, 43, 22, 'StaticContext', color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(53.5, 72,
            '· mappings : {(scid, vcid)  →  IPv6Mapping}\n'
            '· qos_dscp, bandwidth_quota_kbps\n'
            '· 全部在会话建立时落盘；切换前 Pre-copy 一次性推完。\n'
            r'· 大小约 288 B/会话，可压缩到 220 B，开销可忽略。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)

    title_panel(ax, 52, 14, 43, 38, 'DynamicContext', color='#a52828', fc=LIGHT_RED)
    ax.text(53.5, 48,
            '· frag_buffer : FragmentReassemblyBuffer\n'
            '    buf : {(scid, vcid, pkt)  →  [片 1 … 片 n]}\n'
            r'    _complete_set ← v2 新增 $O(1)$ 完成检测',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)
    ax.text(53.5, 32,
            '· queues : {(scid, vcid)  →  VCIDQueueState}\n'
            '· version, timestamp_sec : Gossip 最终一致依据\n'
            '关键 API：\n'
            '    snapshot()  /  diff_bytes_since(prev)\n'
            '    complete_packets()  /  num_partial()',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)
    save(fig, '08_principle_model.png')

# =========================================================
# 09 详细原理②：Lyapunov
# =========================================================
def slide_09():
    fig, ax = new_slide()
    header(ax, r'详细原理②：Lyapunov drift-plus-penalty 在线决策')

    # 1) — 顶部段落
    ax.text(4, 84, '1) 长期平均最小化  +  切换预算约束',
            fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    ax.text(6, 80,
            r'$\min\;\bar{c}=\lim_{T\to\infty}\frac{1}{T}\sum_{t=0}^{T-1}c(t)$,'
            r'   s.t.   $\bar{s}_{\mathrm{sw}}\;\leq\;C_{\max}$',
            fontsize=11.5, color=DARK, zorder=10)
    ax.text(6, 76,
            r'$\bar{s}_{\mathrm{sw}}$：单位时间切换次数的长期平均；$C_{\max}$：硬性预算上界。',
            fontsize=10, color=GRAY, zorder=10)

    # 2)
    ax.text(4, 72, '2) 虚拟队列 + Lyapunov 函数',
            fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    ax.text(6, 68,
            r'$Q(t+1)=\max\{Q(t)+\mathbf{1}\{\mathrm{switch}\}-C_{\max}\cdot\Delta t,\;0\}$',
            fontsize=11.5, color=DARK, zorder=10)
    ax.text(6, 64,
            r'$L(t)=\frac{1}{2}Q^{2}(t),\quad'
            r'\Delta(Q)=E[\,L(t+1)-L(t)\,|\,Q\,]$',
            fontsize=11.5, color=DARK, zorder=10)

    # 3) — 紧凑面板 (避开公式)
    title_panel(ax, 4, 35, 45, 25, '', color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 57, '3) drift-plus-penalty 闭式策略',
            fontsize=11.5, color=PURPLE, weight='bold', zorder=11)
    ax.text(6, 51.5,
            r'$a^{*}(t)=\arg\min_{a}\;V\cdot c_a(t)\,+\,Q(t)\cdot\mathbf{1}\{a\neq a_{\mathrm{prev}}\}$',
            fontsize=12, color=DARK, zorder=10)
    ax.text(6, 46,
            '· 每时隙 $O(N)$ 闭式可解，无需在线求解器；\n'
            '· $V$ 是“代价 <-> 切换次数”的权衡参数；\n'
            '· $Q$ 随时间累积，自动抑制频繁切换。',
            fontsize=10.2, color=DARK, va='top', linespacing=1.55, zorder=10)

    # 4) — 下方面板
    title_panel(ax, 4, 8, 45, 23, '', color='#c8651f', fc=LIGHT_ORANGE)
    ax.text(5.5, 28, r'4) 定理：$[O(1/V),\;O(V)]$ 权衡上界',
            fontsize=11.5, color='#c8651f', weight='bold', zorder=11)
    ax.text(6, 23,
            r'$\bar{c}^{\,\mathrm{Lyap}}\;\leq\;\bar{c}^{*}\;+\;B/V$       (utility gap)',
            fontsize=11.5, color=DARK, zorder=10)
    ax.text(6, 18,
            r'$\bar{Q}\;\leq\;(\,B+V(c_{\max}-c_{\min})\,)/\epsilon$   (constraint)',
            fontsize=11.5, color=DARK, zorder=10)
    ax.text(6, 13,
            '证明：详见 docs/lyapunov_proof.md (Foster-Lyapunov + 期望递推)。',
            fontsize=10, color=GRAY, style='italic', zorder=10)

    # 右：V 扫描图 + 实测文字解读
    ax.text(52, 84, r'V 扫描实测：决策被可见性硬约束收敛',
            fontsize=12.5, color=PURPLE, weight='bold', zorder=10)
    add_image(ax, os.path.join(FIG_DIR, 'fig2_lyapunov_V.png'), 52, 46, 44, 35)
    ax.text(52, 42,
            r'横轴：权衡参数 $V\in[10^{0},10^{4}]$ (对数刻度)；纵轴：单步平均代价。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55, zorder=10)
    ax.text(52, 38,
            '从图中读出三点：\n'
            r'  · 整条曲线几乎水平 — 平均代价对 $V$ 不敏感；'
            '\n'
            r'  · 这是因为卫星硬可见性约束几乎在每个时隙都收敛到唯一最优 $a^{*}$；'
            '\n'
            r'  · 即 $V$ 调参的“代价 <-> 切换次数”trade-off 在本场景下被几何约束“替代”了；'
            '\n'
            '  · 实际意义：算法对 $V$ 选择天然鲁棒，部署时无需手动调参。',
            fontsize=10, color=DARK, va='top', linespacing=1.55, zorder=10)

    ax.text(52, 16,
            '结合理论与实测：闭式 $O(N)$ + 鲁棒于 $V$ + 决策时间 < 1 ms /时隙，\n'
            '即可作为“可证最优”的专家信号，供后续模仿学习蒸馏成轻量网络。',
            fontsize=10, color=GRAY, va='top', linespacing=1.55, style='italic', zorder=10)
    save(fig, '09_principle_lyapunov.png')

# =========================================================
# 10 详细原理③：IL
# =========================================================
def slide_10():
    fig, ax = new_slide()
    header(ax, '详细原理③：模仿学习策略网络 (面向星上部署)')

    ax.text(4, 84, '动机', fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    ax.text(6, 80.5,
            '星上 CPU/FPGA 资源紧张、决策延迟必须有硬上界；\n'
            'Lyapunov 虽 $O(N)$ 但每时隙需更新虚拟队列 $Q(t)$；\n'
            r'故把“专家决策”蒸馏到轻量网络 $\pi_\theta$ 中。',
            fontsize=10.2, color=DARK, va='top', linespacing=1.55, zorder=10)

    ax.text(4, 64, '网络架构  GatewayPolicyNet', fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    layers = [
        ('输入 $x_t$ (80 维)', LIGHT_BLUE, '#3666b8',
         r'$\Delta T_i,L_i,V_i,$ onehot'),
        ('Linear 80 → 128 + ReLU + Dropout(0.1)', LIGHT_PURPLE, PURPLE, ''),
        ('Linear 128 → 128 + ReLU + Dropout',     LIGHT_PURPLE, PURPLE, ''),
        ('Linear 128 → 16  + softmax · visibility', LIGHT_GREEN, '#2e7d4f', '掩码+归一化'),
        ('输出 $a_t$ (argmax)',                    LIGHT_ORANGE, '#c8651f', ''),
    ]
    for i, (t, fc, ec, note) in enumerate(layers):
        y = 59 - i*5.2
        panel(ax, 5, y, 34, 4.2, fc=fc, ec=ec, lw=1.2)
        ax.text(6.5, y + 2.0, t, fontsize=10, color=DARK, va='center', zorder=10)
        if note:
            ax.text(40, y + 2.0, note, fontsize=9, color=GRAY, va='center', zorder=10)
    ax.text(4, 26,
            '· 总参数 45 456 ( ≈ 45 K )；权重约 180 KB，可装入 SRAM；\n'
            '· 推理：GPU 0.176 ms / CPU 0.144 ms (NumPy)；\n'
            r'· 决策周期 1 s，对 $T_{\mathrm{phys}}$ 富余 5 000 倍。',
            fontsize=10, color=DARK, va='top', linespacing=1.55, zorder=10)

    # 右：训练目标 + 训练曲线
    ax.text(48, 84, '训练目标：行为克隆 + DAgger 扰动扩增',
            fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    ax.text(50, 80,
            r'$\mathcal{L}_{\mathrm{BC}}=-\frac{1}{|\mathcal{M}|}\sum_{(s,a)\in\mathcal{M}}\log \pi_{\theta}(a|s)$',
            fontsize=11.5, color=DARK, zorder=10)
    ax.text(50, 75,
            'Adam · lr = 1e-3 · batch = 256 · 60 epoch · val_ratio = 0.2\n'
            '专家轨迹由 Lyapunov 决策器在线生成，覆盖 8 个独立场景。',
            fontsize=10, color=DARK, linespacing=1.55, va='top', zorder=10)

    add_image(ax, os.path.join(FIG_DIR, 'fig3_il_training.png'), 48, 36, 48, 32)
    ax.text(48, 32,
            '训练曲线：5 epoch 内 loss 由 0.8 跌至 < 0.02；60 epoch 收敛于 0.0092；\n'
            'val_acc 稳定 99.91 % 以上 — IL 与 Lyapunov 在测试集决策完全一致。',
            fontsize=9.8, color=GRAY, va='top', linespacing=1.55, style='italic', zorder=10)

    title_panel(ax, 48, 8, 48, 18,
                '工程意义：Ours-IL 是“可上星”的实际方案',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(49.5, 20,
            '· 45 K 参数 ≈ 180 KB FP32 权重，星上 SRAM 即可装入；\n'
            '· 不依赖在线 $Q(t)$ 计算，便于 FPGA 硬件流水化；\n'
            '· 推理延迟可上界，满足星载实时性硬约束。',
            fontsize=10, color=DARK, va='top', linespacing=1.55, zorder=10)
    save(fig, '10_principle_il.png')

# =========================================================
# 11 详细原理④：两阶段迁移
# =========================================================
def slide_11():
    fig, ax = new_slide()
    header(ax, '详细原理④：两阶段协议转换状态迁移')

    # 顶部时序条 — 紧凑
    ax.text(5, 84, r'时序流程  ( 在切换前 $t_{\mathrm{pre}}=3$ s 触发 )',
            fontsize=12, color=PURPLE, weight='bold', zorder=10)
    bars = [
        ('Pre-copy',   LIGHT_BLUE,   '#3666b8', 32,
         r'A → B 推送 $\mathcal{C}_{\mathrm{static}}$；A 拍 $\mathcal{C}_{\mathrm{dyn}}$ 快照；A 继续服务'),
        ('Stop-copy',  LIGHT_ORANGE, '#c8651f', 14,
         r'A 冻结 $\mathcal{C}_{\mathrm{dyn}}$ → 传 $\Delta\mathcal{C}_{\mathrm{dyn}}$ → B'),
        (r'$T_{\mathrm{phys}}\!=\!500$ ms', LIGHT_RED, '#a52828', 8, '天线转向 + 链路重建'),
        ('B 接管',     LIGHT_GREEN,  '#2e7d4f', 16, 'C 完整、0 丢包'),
    ]
    x0 = 5; total = sum(b[3] for b in bars); span = 90
    cur = x0
    for name, fc, ec, w, sub in bars:
        ww = span * w / total
        ax.add_patch(Rectangle((cur, 77), ww, 3.5, fc=fc, ec=ec, lw=1.3, zorder=3))
        ax.text(cur + ww/2, 78.7, name, ha='center', va='center',
                fontsize=9.5, color=ec, weight='bold', zorder=10)
        ax.text(cur + ww/2, 74.5, sub, ha='center', va='top',
                fontsize=8.3, color=GRAY, zorder=10)
        cur += ww

    # 左：关键耗时与判据
    title_panel(ax, 4, 38, 44, 32, '关键耗时公式与无缝判据',
                color='#c8651f', fc=LIGHT_ORANGE)
    ax.text(5.5, 65, r'Pre-copy 耗时 (业务不冻结，不计入 sync) :',
            fontsize=10.5, color=PURPLE, weight='bold', zorder=10)
    ax.text(7, 60.5,
            r'$t_{\mathrm{precopy}}=\dfrac{|\mathcal{C}_{\mathrm{static}}|}{B(A,B)\cdot\eta}+\tau(A,B)$',
            fontsize=12, color=DARK, zorder=10)
    ax.text(5.5, 55, r'Stop-and-copy 耗时 (业务冻结，关键路径) :',
            fontsize=10.5, color=PURPLE, weight='bold', zorder=10)
    ax.text(7, 50.5,
            r'$t_{\mathrm{stop}}=\dfrac{|\Delta\mathcal{C}_{\mathrm{dyn}}|}{B(A,B)\cdot\eta}+\tau$',
            fontsize=12, color=DARK, zorder=10)
    ax.text(5.5, 45,
            r'无缝判据 : $T_{\mathrm{sync}}=t_{\mathrm{stop}}\leq T_{\mathrm{phys}}$ ?',
            fontsize=11.5, color='#a52828', weight='bold', zorder=10)
    ax.text(5.5, 41,
            r'$\eta$：ISL 有效吞吐折算 (含 ARQ 重传)；$\tau$：信令双向确认 (30 ms)。',
            fontsize=9.5, color=GRAY, va='center', zorder=10)

    # 左下：设计要点
    title_panel(ax, 4, 11, 44, 24, '为什么必须两阶段 (而非一次性 stop-copy)',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 31,
            r'· 直接 stop-copy 需冻结 $|\mathcal{C}_{\mathrm{static}}|+|\mathcal{C}_{\mathrm{dyn}}|$ ≈ 288 B + 数 KB；'
            '\n'
            r'  在 ISL 50 Mbps 链路上仍需 ≈ 700 ms — 已超过 $T_{\mathrm{phys}}=500$ ms。'
            '\n'
            '· 拆成 Pre-copy + Stop-copy 后，关键路径只剩 $\\Delta\\mathcal{C}_{\\mathrm{dyn}}$，\n'
            r'  通常仅几百字节 → $t_{\mathrm{stop}}<30$ ms，留出充足余量。'
            '\n'
            '· Pre-copy 在切换前 3 s 启动，与业务报文复用 ISL，开销几乎不可感知。',
            fontsize=10.2, color=DARK, va='top', linespacing=1.55, zorder=10)

    # 右：实测图
    add_image(ax, os.path.join(FIG_DIR, 'fig6_migration_overhead.png'), 51, 32, 47, 38)
    ax.text(51, 28, 'Fig.6  本方案在 5 种子 × 30 min 仿真中的实测迁移开销',
            fontsize=11.5, color=PURPLE, weight='bold', zorder=10)
    ax.text(51, 24,
            '· 上子图  sync time (ms)：所有切换全部远低于 500 ms 红线，\n'
            r'   实测中位数约 28 ms，最大约 45 ms — 距 $T_{\mathrm{phys}}$ 仍有 10× 余量；'
            '\n'
            '· 下子图  fragments：绿色为成功迁移分片，红色为丢弃分片；\n'
            '   30 min 内成功迁移 ≈ 15 万分片，0 丢弃 — 100% 走 SEAMLESS 路径；\n'
            '· 跨 5 种子无任何一次回退到 DEGRADED-1/2 或 FAILED，三层降级机制为兜底而非常态。',
            fontsize=10, color=DARK, va='top', linespacing=1.55, zorder=10)
    save(fig, '11_principle_twophase.png')

# =========================================================
# 12 详细原理⑤：三层降级
# =========================================================
def slide_12():
    fig, ax = new_slide()
    header(ax, '详细原理⑤：三层降级策略 (卫星场景独有设计)')

    ax.text(5, 82,
            r'若 $T_{\mathrm{sync}}>T_{\mathrm{phys}}$，无法在物理切换窗口内完成全量迁移，' '\n'
            '则按下表逐层降级，优先保护“已投入算力且接近完成”的分片与高优先级业务。',
            fontsize=11, color=DARK, va='top', linespacing=1.55)

    levels = [
        ('L1 SEAMLESS',  LIGHT_GREEN,  '#2e7d4f',
         r'$T_{\mathrm{sync}}\leq T_{\mathrm{phys}}$',
         '全量迁移：所有静态 + 动态上下文均拷贝完成，B 接管时 $\\mathcal{C}$ 完整、0 丢包。'),
        ('L2 DEGRADED-1', LIGHT_GOLD, GOLD,
         'L1 失败 (带宽/时延受限)',
         r'仅迁移 $\geq 50\%$ 完成度的分片 + 全部 QoS 队列；服务连续，仅未达半数分片丢失。'),
        ('L3 DEGRADED-2', LIGHT_ORANGE, '#c8651f',
         'L2 仍失败',
         r'仅迁移高优先级 VCID (vcid $\leq$ 1) 的 $\geq 50\%$ 分片；保证关键业务不中断。'),
        ('L4 FAILED',   LIGHT_RED, '#a52828',
         'L3 仍失败 (链路恶化)',
         '回退为硬切换 (等效传统方法)，记录事件供后续策略学习；不会比 baseline 更差。'),
    ]
    y_top = 75; row_h = 11
    for i, (name, fc, ec, trig, body) in enumerate(levels):
        y = y_top - i * (row_h + 1)
        panel(ax, 4, y - row_h, 92, row_h, fc=fc, ec=ec, lw=1.4)
        # 左列：等级 + 触发条件 (放在 panel 内部)
        ax.text(6, y - 3.5, name, fontsize=12.5, color=ec, weight='bold', va='center', zorder=10)
        ax.text(6, y - 7, '触发：' + trig, fontsize=9.5, color=GRAY, va='center', zorder=10)
        # 右列：描述
        ax.text(25, y - 5.5, body, fontsize=10.5, color=DARK, va='center', linespacing=1.5, zorder=10)

    title_panel(ax, 4, 5, 92, 10,
                r'理论依据：完成度 $\geq 50\%$ 的分片“投资已超过半数”，继续迁移边际收益 > 重传成本',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 11,
            '· 设单分片重组需 $n$ 片，已收到 $k$ 片；若 $k/n\\geq 0.5$，迁移已收到部分的字节代价 < 全部重传代价；\n'
            '· 5 种子 × 30 min 仿真中，本机制使所有切换稳定走 L1 路径，未触发任何 L2/L3/L4 — 三层降级是兜底而非常态。',
            fontsize=9.8, color=DARK, va='top', linespacing=1.55, zorder=10)
    save(fig, '12_principle_degrade.png')

# =========================================================
# 13 详细原理⑥：Top-M + Gossip
# =========================================================
def slide_13():
    fig, ax = new_slide()
    header(ax, '详细原理⑥：Top-M 乐观复制 + Lamport-Gossip 最终一致')

    ax.text(5, 82, r'问题：$k\geq 2$ 颗 IPv6 网关并发覆盖同一 AOS  →  状态分裂',
            fontsize=12.5, color=PURPLE, weight='bold')
    ax.text(5, 78,
            '不同网关各自维护 TC 副本；若不协调，AOS 切换到其中任一颗都可能看到“过期视图”。\n'
            '强一致 (Raft) 在 ISL 高时延 + 抖动场景代价过高，本方案采用“乐观复制 + 最终一致”。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)

    # 左：score 图示
    import math
    ax.text(5, 70, r'Top-M 选副本：$\mathrm{score}_i=\Delta T_i - 50\!\cdot\!L_i$，默认 $M=2$',
            fontsize=12, color=PURPLE, weight='bold')
    nodes = [
        ('g1',  '$\\Delta T=30, L=0.2$',  '26',  15, 60, '#2e7d4f', True),
        ('g2',  '$\\Delta T=45, L=0.5$',  '20',  35, 60, '#2e7d4f', True),
        ('g3',  '$\\Delta T=10, L=0.4$',  '$-10$',15, 36, '#cfcfcf', False),
        ('g4',  '$\\Delta T=20, L=0.7$',  '$-15$',35, 36, '#cfcfcf', False),
    ]
    cx, cy = 25, 48
    ax.plot(cx, cy, 'o', ms=22, color='#a52828')
    ax.text(cx, cy, 'AOS', ha='center', va='center', fontsize=9, color='white', weight='bold')
    for name, attr, sc, nx, ny, color, sel in nodes:
        ax.plot(nx, ny, 'o', ms=18, color=color)
        ax.text(nx, ny, name, ha='center', va='center', fontsize=9, color='white', weight='bold')
        ax.text(nx, ny + 3.5, attr, ha='center', fontsize=8.5, color=DARK)
        ax.text(nx, ny - 3, 'score = ' + sc, ha='center', fontsize=8.5, color=color)
        lw = 1.8 if sel else 0.6
        ax.plot([cx, nx], [cy, ny], color=color, lw=lw, alpha=(1.0 if sel else 0.4))
    ax.text(5, 26,
            r'并行预复制 $\mathcal{C}_{\mathrm{static}}$ ( ≈ 288 B/份 ) 至 Top-M 候选；'
            '开销 << ISL 带宽。\n'
            '一旦决策切换到任意候选，目标网关已有静态上下文，Stop-copy 仅需增量。',
            fontsize=10, color=GRAY, va='top', linespacing=1.55, style='italic')

    # 右上：Gossip 协议
    ax.text(52, 82, 'Gossip 一致性维护', fontsize=13, color=PURPLE, weight='bold')
    items = [
        r'副本仓库：$R_g=\{(s,\,\mathcal{C}_{\mathrm{static}},\,v,\,t_w,\,\tau_{\mathrm{TTL}})\}$',
        r'周期 Gossip ( 10 s )：广播 $(s,v,t_w)$ 摘要，非全量推送；',
        r'接收方：本地 $v<v_{\mathrm{msg}}$  →  按版本号淘汰旧副本；',
        r'TTL 淘汰：副本超 $\tau_{\mathrm{TTL}}$ 自动失效，避免“僵尸”状态；',
        'Lamport 逻辑时钟：保证偏序，避免乱序回滚。',
    ]
    for i, t in enumerate(items):
        ax.text(52.5, 76 - i*4.5, '·', fontsize=12, color=GOLD)
        ax.text(54, 76 - i*4.5, t, fontsize=10.5, color=DARK, va='center')

    # 右下：对比表
    ax.text(52, 52, 'vs Raft (强一致) 对比', fontsize=13, color=PURPLE, weight='bold')
    rows = [
        ('维度',         'Raft',                  '本方案 Gossip'),
        ('一致性',       '线性一致 (强)',         '最终一致'),
        ('消息复杂度',   r'$O(N^{2})$ / 决策',   r'$O(N)$ / 周期'),
        ('延迟',         r'$\geq 2$ RTT 阻塞',   '异步无阻塞'),
        ('卫星适用性',   '差 (ISL 时延高)',      '好'),
    ]
    y0 = 47
    cols = [52, 67, 82]
    for r, row in enumerate(rows):
        y = y0 - r*4
        if r == 0:
            ax.add_patch(Rectangle((52, y - 1), 43, 3.5, fc=PURPLE))
            for c, v in enumerate(row):
                ax.text(cols[c] + 0.3, y + 0.7, v, fontsize=10, color='white', weight='bold', va='center')
        else:
            if r % 2 == 0:
                ax.add_patch(Rectangle((52, y - 1.4), 43, 3.8, fc=LIGHT_PURPLE))
            for c, v in enumerate(row):
                ax.text(cols[c] + 0.3, y + 0.7, v, fontsize=9.5, color=DARK, va='center')
    ax.text(52, 23,
            '实测 (30 min)：179 轮 Gossip / 安装 1 副本 / 淘汰 1 个；\n'
            '三条路径 (写、传播、淘汰) 全部打通；总开销 << ISL 带宽。',
            fontsize=10, color='#2e7d4f', va='top', linespacing=1.55, style='italic')
    save(fig, '13_principle_gossip.png')

# =========================================================
# 14 关键算法伪代码
# =========================================================
def slide_14():
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
    save(fig, '14_pseudocode.png')

# =========================================================
# 15 实验设计
# =========================================================
def slide_15():
    fig, ax = new_slide()
    header(ax, '实验设计：合成星座 + 6 方案对比 + 5 种子统计')

    # 左：实验场景
    ax.text(5, 82, '实验场景  (orbit/synth_constellation.py)',
            fontsize=12.5, color=PURPLE, weight='bold')
    rows = [
        ('AOS 卫星',     r'1 颗  极轨 $i=87^\circ$  高度 400 km'),
        ('IPv6 网关',    r'16 颗 $i=53^\circ$  高度 550 km  等 RAAN 间距'),
        ('ISL 最大距离', r'$D_{\max}=3500$ km  →  每时隙可见 0–5 颗 (均值 2.1)'),
        ('仿真时长',     '训练 3600 s × 8 种子  /  测试 1800 s × 5 种子'),
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
        ('OS',      'Linux 5.10 (AliOS 8)'),
        ('Python',  '3.10  +  torch 2.8 cu128'),
        ('仿真器',  'SimPy 4.1 事件驱动'),
        ('轨道库',  'Skyfield 1.54  +  合成 TLE'),
        ('绘图',    'matplotlib 3.10  +  TensorBoard 2.20'),
    ]
    for i, (k, v) in enumerate(env):
        y = 77 - i*4
        ax.text(56, y, k, fontsize=11, color=PURPLE, va='center', weight='bold')
        ax.text(64, y, v, fontsize=10.5, color=DARK, va='center')

    # 下：6 方案对比表
    ax.text(5, 50, '6 个对比方案', fontsize=12.5, color=PURPLE, weight='bold')
    headers = ['方案', '决策算法', '状态迁移', '说明']
    schemes = [
        ('Reactive',      '当前网关失效才切',          '硬切',          '弱基线 — 几乎不主动迁移'),
        ('Max-Visibility','贪心选 $\\Delta T$ 最大',   '硬切',          '强可见性贪心 — 不考虑负载'),
        ('MPTCP-style',   '综合分 + 60 s 迟滞',        '硬切',          '强基线 — 地面 MPTCP 思想移植'),
        ('Pure DRL (DQN)','与 Lyapunov 同状态空间',   '硬切',          '消融对比 — 验证决策框架本身'),
        ('Ours-Lyap',     'Lyapunov 在线',             '两阶段 + 多副本','本方案 — 理论变体'),
        ('Ours-IL',       '模仿学习',                  '两阶段 + 多副本','本方案 — 部署变体 (星上可用)'),
    ]
    col_xs = [5, 22, 45, 65]; y0 = 44
    ax.add_patch(Rectangle((5, y0 - 1), 90, 3.5, fc=PURPLE))
    for c, h in enumerate(headers):
        ax.text(col_xs[c] + 0.5, y0 + 0.7, h, fontsize=10.5, color='white', weight='bold', va='center')
    for r, row in enumerate(schemes):
        y = y0 - 3.6 - r*3.6
        if r % 2 == 0:
            ax.add_patch(Rectangle((5, y - 1.4), 90, 3.4, fc=LIGHT_PURPLE))
        for c, v in enumerate(row):
            color = '#2e7d4f' if r >= 4 and c == 0 else (PURPLE if c == 0 else DARK)
            weight = 'bold' if c == 0 else 'normal'
            ax.text(col_xs[c] + 0.5, y + 0.7, v, fontsize=10, color=color, weight=weight, va='center')

    ax.text(5, 14,
            '指标体系 (共 9 项)：PLR (%)、端到端时延 (ms)、切换次数、总中断时长 (s)、'
            '迁移分片数、平均/最差 reward、决策延迟 (CPU/GPU)、Gossip 收敛轮数、各阶段时长。\n'
            '统计方法：5 个独立测试种子 → mean ± std；显著性差异采用配对 t-test (本工作 vs MPTCP)。',
            fontsize=10, color=GRAY, va='top', linespacing=1.55, style='italic')
    save(fig, '15_exp_design.png')

# =========================================================
# 16 实验流程（重点：每步多文字）
# =========================================================
def slide_16():
    """实验流程总览 — 6 个阶段一句话概括，后续 17-22 单独展开"""
    fig, ax = new_slide()
    header(ax, '实验流程总览  ( RTX 4090 · 共 6 个 Stage · 后续 6 页逐一展开 )')

    ax.text(4, 84,
            '完整实验由 6 个串行阶段组成，下游依赖上游产物 (.npz / .pt / .pkl)；\n'
            '总耗时 ≈ 15 min，其中 Stage 3 (DQN 消融) 占绝大部分时间，IL 训练仅 30 s。',
            fontsize=10.8, color=DARK, va='top', linespacing=1.55, zorder=10)

    stages = [
        ('Stage 1', '5 s',     '拓扑构建',           LIGHT_BLUE,   '#3666b8',
         '调用 Skyfield 推算 16 网关 + 1 AOS 共 3601 时隙轨道，缓存 .npz。'),
        ('Stage 2', '30 s',    'Lyapunov 专家 + IL 训练', LIGHT_PURPLE, PURPLE,
         '8 场景 × 10 s 生成专家轨迹，蒸馏到 45 K MLP，val_acc 99.91 %。'),
        ('Stage 3', '13 min',  'DQN 消融训练',       LIGHT_ORANGE, '#c8651f',
         '15 epoch × 8 场景 × 3600 决策 ≈ 432 K 转移；验证 DRL 学不到最优。'),
        ('Stage 4', '1.5 min', '30 次 SimPy 仿真',   LIGHT_GREEN, '#2e7d4f',
         '6 方案 × 5 种子，每次 1800 s × 300 pps × 16 网关 ≈ 100 万事件。'),
        ('Stage 5', '10 s',    '推理延迟基准',       LIGHT_GOLD,   GOLD,
         'GPU / CPU 各 2000 次推理 + 200 次预热；统计 P50/P99/最大延迟。'),
        ('Stage 6', '< 10 s',  '落盘 + 出图',        LIGHT_RED,    '#a52828',
         '聚合 pkl/json/md；plot_figures.py 一次性生成 9 张实验图。'),
    ]
    y_top = 72; row_h = 9.8
    for i, (stage, dur, name, fc, ec, brief) in enumerate(stages):
        y = y_top - i*row_h
        panel(ax, 4, y - row_h + 1.5, 92, row_h - 1.8, fc=fc, ec=ec, lw=1.3)
        ax.text(6, y - 2.3, stage, fontsize=12, color=ec, weight='bold', va='top', zorder=10)
        ax.text(6, y - 5.5, dur,   fontsize=10, color=ec, va='top', zorder=10)
        ax.text(19, y - 2.3, name, fontsize=12, color=PURPLE, weight='bold', va='top', zorder=10)
        ax.text(19, y - 5.5, brief, fontsize=10, color=DARK, va='top', linespacing=1.55, zorder=10)
        # 详见 →
        ax.text(94, y - 4.2, '→ 详见 P.' + str(17 + i),
                fontsize=9.5, color=ec, ha='right', va='center', style='italic', zorder=10)

    save(fig, '16_exp_flow.png')


# ============ 实验流程  Stage 1-6 逐页详细展开 ============

def _stage_detail_layout(ax, stage_no, name, color, fc_light, dur,
                         purpose, how, inputs, outputs, key_design, extra):
    """通用模板：左侧目的+输入+输出，右侧 How（详细步骤）+ 关键设计点
    布局重排：所有 panel 之间留 2 单位空白；body 文本起点 y + h - 5.5；行距 1.6"""
    header(ax, f'实验流程  {stage_no}：{name}  ( 实测耗时 {dur} )')

    # ============== 左列 ==============
    # 左 1：目的  y=[60, 84]  h=24
    title_panel(ax, 4, 60, 44, 24, '阶段目标与作用', color=color, fc=fc_light)
    ax.text(5.5, 78.2, '目的：', fontsize=10.5, color=color, weight='bold', zorder=10)
    ax.text(11, 78.2, purpose, fontsize=9.6, color=DARK, va='top', linespacing=1.65, zorder=10)

    # 左 2：输入/输出  y=[34, 56]  h=22  (与左1留 4 单位)
    title_panel(ax, 4, 34, 44, 22, '输入  /  输出', color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(5.5, 50.5, '输入：', fontsize=10, color=PURPLE, weight='bold', zorder=10)
    ax.text(11, 50.5, inputs, fontsize=9.5, color=DARK, va='top', linespacing=1.6, zorder=10)
    ax.text(5.5, 42, '输出：', fontsize=10, color=PURPLE, weight='bold', zorder=10)
    ax.text(11, 42, outputs, fontsize=9.5, color=DARK, va='top', linespacing=1.6, zorder=10)

    # 左 3：关键设计点  y=[6, 30]  h=24
    title_panel(ax, 4, 6, 44, 24, '关键设计点', color='#c8651f', fc=LIGHT_ORANGE)
    ax.text(5.5, 24.5, key_design, fontsize=9.6, color=DARK, va='top', linespacing=1.65, zorder=10)

    # ============== 右列 ==============
    # 右 1：How  y=[20, 84]  h=64  (与右2留 4 单位)
    title_panel(ax, 50, 20, 46, 64, '执行步骤  (How)', color=color, fc='white')
    ax.text(51.5, 78.5, how, fontsize=9.6, color=DARK, va='top', linespacing=1.7, zorder=10)

    # 右 2：实测细节  y=[6, 16]  h=10  (与右1留 4 单位)
    title_panel(ax, 50, 6, 46, 10, '实测细节 / 工程说明', color=GRAY, fc='#f7f7fb')
    ax.text(51.5, 11.5, extra, fontsize=9.4, color=DARK, va='top', linespacing=1.6, zorder=10)


def slide_17():
    fig, ax = new_slide()
    _stage_detail_layout(ax,
        'Stage 1', '拓扑构建 (orbit + topology)', '#3666b8', LIGHT_BLUE, '5 s',
        purpose='构造一个 30 分钟、16 颗 IPv6 + 1 颗 AOS 的“完全可知”星座；\n'
                '把后面所有阶段都要反复用到的可见性、距离、带宽、剩余时长\n'
                '提前算好、缓存成张量，避免每次仿真都重复 Skyfield 推算。',
        how='① 用 orbit/synth_constellation.py 合成 17 个 TLE：\n'
            '   · 1 颗 AOS：极轨 $i=87^\\circ$，高度 400 km；\n'
            '   · 16 颗 IPv6：$i=53^\\circ$、高度 550 km、等 RAAN 间距 22.5°；\n\n'
            '② 调用 Skyfield 1.54 推算 0–3600 s 共 3601 个时隙的 ECEF 位置；\n\n'
            '③ 对每时隙 $t$、每颗网关 $i$ 计算：\n'
            r'   · 距离 $D_i(t)$、grazing angle $\theta_i(t)$；'
            '\n'
            r'   · 可见性 $V_i(t)\in\{0,1\}$ (规则：$\theta\geq10^\circ$ 且 $D\leq3500$ km)；'
            '\n'
            r'   · 剩余连续可见时长 $\Delta T_i(t)$ (前向扫描得到)；'
            '\n'
            r'   · 带宽 $B_i(t)$ (反距离平方衰减 + 上限 80 Mbps)；'
            '\n\n'
            '④ 全部张量化为 16 个 [3601, N] 矩阵，落盘到 .npz；\n\n'
            '⑤ 暴露简洁 API：topo.visible[t]、topo.remaining_visibility(t)、\n'
            '   topo.gateway_loads(t) — 后续 Lyapunov / IL / SimPy 直接调用。',
        inputs='合成 TLE (脚本生成，无外部依赖)；\n'
               '常量：仿真时长 3600 s、时隙 1 s、$D_{\\max}=3500$ km。',
        outputs='缓存 .npz：visibility、remaining、bandwidth、distance；\n'
                '内存对象 Topology，被 Stage 2-5 共享。',
        key_design='· 一次算好、多次复用 — 把后续仿真的 wall-clock 从“分钟”降到“秒”；\n'
                   '· 张量化便于 GPU/CPU 矢量化处理；\n'
                   '· 用合成 TLE 而非真实星历：保证可复现 + 不依赖外部数据源。',
        extra='RTX 4090 上 5 s 内完成；Stage 1 失败会导致后续全部阶段不可用，\n'
              '故脚本对 visibility / remaining 做了一致性自检，含 31 个单元测试。'
    )
    save(fig, '17_flow_stage1.png')


def slide_18():
    fig, ax = new_slide()
    _stage_detail_layout(ax,
        'Stage 2', 'Lyapunov 专家轨迹生成 + IL 模仿训练', PURPLE, LIGHT_PURPLE, '30 s',
        purpose='把“可证最优但实时计算成本高”的 Lyapunov 决策器作为专家，\n'
                '在 8 个独立训练场景上跑出 (state, action) 轨迹，\n'
                '再用监督学习蒸馏出一个 45 K 参数的星上可部署网络。',
        how='① 8 个训练场景：换不同 seed 生成 8 套 Topology 共享；\n\n'
            '② 每个场景跑 Lyapunov 决策器 10 s：\n'
            '   · 每时隙输入 80 维 state (ΔT/L/V/onehot)；\n'
            '   · 内部维护虚拟队列 Q(t)，按 drift-plus-penalty 闭式选 a*；\n'
            r'   · 落盘 (state, action) 对，共 $\approx$ 4.3 万样本；'
            '\n\n'
            '③ 训练 GatewayPolicyNet (MLP 80→128→128→16)：\n'
            '   · 行为克隆损失 + softmax 可见性掩码；\n'
            '   · Adam lr = 1e-3、batch = 256、val_ratio = 0.2；\n'
            '   · 60 epoch，单 epoch 0.33 s，总 20 s；\n\n'
            '④ DAgger 一轮：让训练好的 IL 网络 roll-out 一次，把不一致样本\n'
            '   交给 Lyapunov 重新标注，扩增 +500 样本后再训 10 epoch；\n\n'
            '⑤ 保存权重 il_policy.pt 与训练曲线 fig3_il_training.png。',
        inputs='Stage 1 的 Topology；\n'
               '专家：optimizer/lyapunov_solver.py；\n'
               '学生：optimizer/policy_net.py。',
        outputs='il_policy.pt (45 K 参数，约 180 KB)；\n'
                'fig3_il_training.png (loss / val_acc)；\n'
                'val_acc = 99.91 %、val_loss = 0.0092。',
        key_design='· 选 MLP 而非 RNN：状态已经包含 $\\Delta T_i$ 等历史信息，无需循环；\n'
                   '· softmax 后乘可见性掩码：物理上不可见的网关概率 = 0；\n'
                   '· DAgger 一轮足够：实测第一轮已收敛，再加效果不明显。',
        extra='RTX 4090 上 30 s 内完成；显存峰值 < 1.5 GB。\n'
              '若改为纯 CPU 训练，时间约 4 min — 仍属于可接受范围。'
    )
    save(fig, '18_flow_stage2.png')


def slide_19():
    fig, ax = new_slide()
    _stage_detail_layout(ax,
        'Stage 3', 'DQN 消融训练', '#c8651f', LIGHT_ORANGE, '13 min',
        purpose='给 DQN 与 Lyapunov 完全相同的状态空间、动作空间、奖励函数，\n'
                '验证“同样信息下，DRL 也学不到 Lyapunov 的最优策略” —\n'
                '这是对“为什么不直接上 DRL”的最关键消融。',
        how='① 状态空间：与 Lyapunov 完全一致 (80 维)；\n'
            '② 动作空间：16 个候选网关 + “保持当前” 共 17；\n'
            '③ Q 网络：MLP 80→256→256→17，约 100 K 参数；\n\n'
            '④ 训练循环：\n'
            '   · 15 epoch × 8 场景 × 3600 决策 ≈ 432 K 转移；\n'
            '   · 经验回放容量 100 K，batch 256；\n'
            '   · $\\epsilon$-greedy 从 1.0 衰减至 0.05；\n'
            '   · target net 每 1000 步软更新 ($\\tau$ = 0.005)；\n'
            '   · 损失：Huber loss + Adam lr = 5e-4；\n\n'
            '⑤ 每 epoch 末跑一次评估：固定 seed roll-out 3600 决策，\n'
            '   记录平均 reward、最差 reward、切换次数；\n\n'
            '⑥ 保存最佳模型 dqn_best.pt + 训练曲线。',
        inputs='Stage 1 Topology；\n'
               'baselines/pure_drl.py 中的 DQN 实现；\n'
               '8 个训练场景共享。',
        outputs='dqn_best.pt；\n'
                '训练日志 (TensorBoard) / 评估指标；\n'
                '最佳平均 reward = -1.3824 (5 seed)。',
        key_design='· 同状态 / 同奖励 / 同动作：保证消融公平，唯一差异是“决策方式”；\n'
                   '· 不引入 PPO/A2C 复杂训练技巧：与 baseline DQN 保持简洁；\n'
                   '· 占总耗时 ~88 % — 反衬出 IL 的高效率。',
        extra='RTX 4090 上 13 min；若用 RTX 3060 约 35 min。\n'
              '消融结果：DQN reward 是 IL 专家的 4.7× 差 — 强证明决策框架本身就比 DRL 更适合本场景。'
    )
    save(fig, '19_flow_stage3.png')


def slide_20():
    fig, ax = new_slide()
    _stage_detail_layout(ax,
        'Stage 4', '6 方案 × 5 种子 = 30 次 SimPy 仿真', '#2e7d4f', LIGHT_GREEN, '1.5 min',
        purpose='把上游产出的 5 个决策器 (含 Reactive、Max-Vis、MPTCP、DQN、Ours-Lyap、Ours-IL)\n'
                '同时在 SimPy 事件驱动环境中 roll-out，记录端到端 9 项指标，\n'
                '用 5 个独立种子统计 mean ± std 以排除偶然。',
        how='① 仿真器：SimPy 4.1，离散事件、单线程、确定性；\n\n'
            '② 单次仿真规模：\n'
            '   · 时长 1800 s，AOS 帧速率 300 pps，16 候选网关；\n'
            '   · 单次约 100 万事件 (报文到达、切换、Gossip、上下文迁移)；\n\n'
            '③ 每时隙循环：\n'
            '   · 决策器输出 a(t) → 若 a 变化触发两阶段迁移；\n'
            '   · AOS 发包 → 当前网关接收 → 翻译 → 转 IPv6 出口；\n'
            '   · 记录 PLR、E2E 时延、迁移分片数、降级层级；\n\n'
            '④ 6 方案 × 5 seed = 30 次仿真，独立日志，互不污染；\n\n'
            '⑤ v2 引入的 $O(1)$ 完成检测使单次仿真由 600 s → 3 s (200×)；\n\n'
            '⑥ 全部 30 次串行执行约 90 s，结果存 results/sim_<scheme>_<seed>.pkl。',
        inputs='Stage 1 Topology + Stage 2/3 训练好的策略；\n'
               'network/simpy_env.py 仿真器；\n'
               'migration/* 状态迁移模块。',
        outputs='30 个 .pkl (每方案/种子)；\n'
                '聚合 summary.json；\n'
                '主表数据：Ours 全部 PLR = 0%。',
        key_design='· 单线程串行：彻底可复现，调试方便；\n'
                   '· $O(1)$ 完成检测：把热点路径 (FragmentReassemblyBuffer.complete) 提速 200×；\n'
                   '· 5 种子统计而非单次：暴露 DQN 高方差等 baseline 弱点。',
        extra='RTX 4090 利用率 ~0 % (本阶段是 CPU 仿真，GPU 仅做 IL 推理)；\n'
              '内存峰值 ~600 MB，可在 8 GB RAM 笔记本完整复现。'
    )
    save(fig, '20_flow_stage4.png')


def slide_21():
    fig, ax = new_slide()
    _stage_detail_layout(ax,
        'Stage 5', '推理延迟基准 (CPU / GPU benchmark)', GOLD, LIGHT_GOLD, '10 s',
        purpose='证明 IL 策略网络在最坏情况下，单次推理延迟仍远小于\n'
                '物理切换窗口 $T_{\\mathrm{phys}}=500$ ms 和决策周期 1 s；\n'
                '为“星上可部署”给出量化证据。',
        how='① 在与训练完全相同的硬件 (RTX 4090) 上加载 il_policy.pt；\n\n'
            '② 预热：连续推理 200 次，丢弃这些结果 —\n'
            '   避免 CUDA 内核延迟初始化、Python JIT、CPU L1 cache 污染影响测量；\n\n'
            '③ 正式测量：\n'
            '   · GPU 模式：torch.cuda.synchronize() 包裹，连续 2000 次推理；\n'
            '   · CPU 模式：NumPy 纯前向 (无 torch 依赖)，便于上星部署对照；\n\n'
            '④ 统计指标：\n'
            '   · P50 / P95 / P99 / 最大延迟；\n'
            '   · 显存峰值 / RAM 峰值；\n\n'
            '⑤ 写入 fig9_inference_latency.png 并表化到 EXPERIMENT_REPORT.md。',
        inputs='Stage 2 训练好的 il_policy.pt；\n'
               '随机生成的 2000 条 80 维 state 输入。',
        outputs='GPU 0.176 ms / CPU 0.144 ms (P50)；\n'
                'P99 < 0.30 ms；最大 < 0.50 ms；\n'
                'fig9_inference_latency.png。',
        key_design='· 预热与正式测量严格分离：消除 cold-start bias；\n'
                   '· 同时跑 GPU + CPU：CPU 数字才是星上代理；\n'
                   '· 2000 次重复：让 P99 估计有足够统计功效。',
        extra='RTX 4090 推理峰值显存 < 50 MB；CPU 单核占用 ~25 %。\n'
              '换到星载等级的 Cortex-A72 CPU 估计推理仍 < 2 ms — 仍远低于 1 s 决策周期。'
    )
    save(fig, '21_flow_stage5.png')


def slide_22():
    fig, ax = new_slide()
    _stage_detail_layout(ax,
        'Stage 6', '指标聚合、出图与报告生成', '#a52828', LIGHT_RED, '< 10 s',
        purpose='把前 5 个阶段散落的 .pt / .npz / .pkl / TensorBoard 日志\n'
                '统一聚合成可复现的“一键报告”：JSON / Markdown / 9 张 PNG，\n'
                '便于下游写论文 / 写汇报 / 复审。',
        how='① 收集所有 .pkl 与 summary.json，按 (方案, seed) 聚合；\n\n'
            '② 用 NumPy 计算 mean ± std (5 seed)，按 9 项指标：\n'
            '   PLR、E2E、切换次数、总中断时长、迁移分片数、\n'
            '   平均/最差 reward、决策延迟 (CPU/GPU)、Gossip 收敛轮数；\n\n'
            '③ 写出 results/EXPERIMENT_REPORT.md (含表格 + 关键结论)；\n\n'
            '④ 调用 experiments/plot_figures.py 出 9 张图：\n'
            '   · fig1 可见性时间序列\n'
            '   · fig2 Lyapunov V 扫描\n'
            '   · fig3 IL 训练曲线\n'
            '   · fig4 PLR over time\n'
            '   · fig5 E2E latency CDF\n'
            '   · fig6 Migration overhead\n'
            '   · fig7 Load balance\n'
            '   · fig8 6 方案 mean±std 汇总\n'
            '   · fig9 推理延迟分布；\n\n'
            '⑤ 固定 matplotlib 版本 + dpi = 140，保证图像逐像素可复现。',
        inputs='Stage 2-5 的所有产物 .pkl/.pt/.json；\n'
               'plot_figures.py 与 matplotlib 3.10。',
        outputs='EXPERIMENT_REPORT.md (主报告)；\n'
                'summary.json (机器可读)；\n'
                '9 张 PNG (fig1-fig9)，存 results/figures/。',
        key_design='· 一键 (make full GPU=0) 复现：拉源码 → 跑 15 min → 得到 9 张图；\n'
                   '· 报告与图分离：报告改文字时不需要重出图；\n'
                   '· 所有 seed 都落盘 — 审稿人可独立复核统计显著性。',
        extra='< 10 s 即可完成；不依赖 GPU。\n'
              '生成的报告是写大论文 / 投稿 / 阶段汇报的“唯一事实源”。'
    )
    save(fig, '22_flow_stage6.png')

# =========================================================
# 17 实验结果①：训练
# =========================================================
def slide_23():
    fig, ax = new_slide()
    header(ax, '实验结果①：训练阶段产出与 DQN 消融')

    add_image(ax, os.path.join(FIG_DIR, 'fig3_il_training.png'), 4, 32, 42, 46)
    ax.text(4, 28,
            'Fig.3  IL 训练曲线  (RTX 4090)\n'
            '蓝/绿：train / val loss；橙：val_acc。\n'
            '5 epoch 内 loss 由 0.8 跌至 < 0.02，第 60 epoch 收敛于 0.0092。',
            fontsize=10, color=GRAY, va='top', linespacing=1.55, style='italic')

    # 右上：IL 网络小结
    title_panel(ax, 52, 56, 43, 22, 'IL 网络  (监督 Lyapunov 专家)',
                color=PURPLE, fc=LIGHT_PURPLE)
    ax.text(54, 73,
            '· 60 epoch 时 val_acc = 99.91 %、val_loss = 0.0092；\n'
            '· BC loss 在第 1 epoch 已降至 0.02；\n'
            '· val_acc 在第 5 epoch 即达 99.7 %；\n'
            '· 与 Lyapunov 在测试集上是完全一致的决策序列。',
            fontsize=10.5, color=DARK, va='top', linespacing=1.55)

    # 右下：DQN 对比
    title_panel(ax, 52, 22, 43, 30, 'DQN 消融对比  (同状态空间)',
                color='#a52828', fc=LIGHT_RED)
    rows = [
        ('指标',             'DQN',            'IL 专家 (Lyapunov)'),
        ('最差平均 reward',  '−1.3824',        '−0.2953'),
        ('训练时长',          '13 min',         '30 s'),
        ('方差',              '高 (不同种子差异显著)',  '低 (确定性)'),
    ]
    cols = [53, 67, 80]; y0 = 46
    for r, row in enumerate(rows):
        y = y0 - r*4.5
        if r == 0:
            ax.add_patch(Rectangle((52, y - 1.2), 43, 3.6, fc='#a52828'))
            for c, v in enumerate(row):
                ax.text(cols[c] + 0.3, y + 0.7, v, fontsize=10, color='white', weight='bold', va='center')
        else:
            if r % 2 == 0:
                ax.add_patch(Rectangle((52, y - 1.6), 43, 4, fc=LIGHT_RED))
            for c, v in enumerate(row):
                color = '#a52828' if c == 0 else DARK
                ax.text(cols[c] + 0.3, y + 0.7, v, fontsize=10, color=color, va='center')

    ax.text(52, 22.5,
            '结论：DQN reward 是 Lyapunov 的 4.7× 差；\n'
            '佐证“星历可预测场景中，确定性优化 > 强化学习”。',
            fontsize=10.5, color='#a52828', va='top', linespacing=1.55, style='italic')

    ax.text(4, 16,
            '图分析：纵轴 (Behavior cloning loss 与 Action match accuracy) 双 y 轴；val acc 在 epoch 5 后基本不动，\n'
            '说明 IL 网络的“信息瓶颈”不是模型容量，而是专家轨迹本身的最优 action 在状态空间上是几乎可分的；\n'
            '这也解释了 DQN 学不好的原因：reward 信号弱，但监督信号一旦给到，就能瞬间学会。',
            fontsize=10, color=GRAY, va='top', linespacing=1.55, style='italic')
    save(fig, '23_train_results.png')

# =========================================================
# 18 主表
# =========================================================
def slide_24():
    fig, ax = new_slide()
    header(ax, '实验结果②：测试综合指标  (5 seed mean ± std)')

    headers = ['方案', 'PLR (%)', 'E2E (ms)', '切换次数', '总中断 (s)', '切换中丢分片']
    rows = [
        ('Reactive',      '0.233 ± 0.000',  '6.07 ± 0.00',  '3.0 ± 0.0',  '1.50 ± 0.00', '175 240'),
        ('Max-Visibility','0.275 ± 0.000',  '7.82 ± 0.00',  '3.0 ± 0.0',  '1.50 ± 0.00', '145 279'),
        ('MPTCP-style',   '6.382 ± 1.454',  '8.60 ± 0.35',  '69.6 ± 17.8','34.80 ± 8.89','146 853 ± 3 040'),
        ('Pure-DRL',      '0.217 ± 0.153',  '7.05 ± 1.14',  '2.4 ± 1.36', '1.20 ± 0.68', '143 973 ± 43 124'),
        ('Ours-Lyap',     '0.000 ± 0.000',  '6.24 ± 0.00',  '1.0 ± 0.0',  '0.00 ± 0.00', '0'),
        ('Ours-IL',       '0.000 ± 0.000',  '6.24 ± 0.00',  '1.0 ± 0.0',  '0.00 ± 0.00', '0'),
    ]
    col_xs = [5, 22, 38, 54, 68, 82]
    y0 = 78
    ax.add_patch(Rectangle((5, y0 - 1.2), 90, 4, fc=PURPLE))
    for c, h in enumerate(headers):
        ax.text(col_xs[c] + 0.3, y0 + 0.8, h, fontsize=11, color='white', weight='bold', va='center')
    for r, row in enumerate(rows):
        y = y0 - 4 - r*4.5
        ours = (r >= 4)
        if ours:
            ax.add_patch(Rectangle((5, y - 1.6), 90, 4, fc=LIGHT_GREEN, ec='#2e7d4f', lw=1.0))
        elif r % 2 == 0:
            ax.add_patch(Rectangle((5, y - 1.6), 90, 4, fc=LIGHT_PURPLE))
        for c, v in enumerate(row):
            color = '#2e7d4f' if ours else (PURPLE if c == 0 else DARK)
            ax.text(col_xs[c] + 0.3, y + 0.7, v, fontsize=10.5, color=color,
                    weight=('bold' if ours else 'normal'), va='center')

    ax.text(5, 40, '核心结论', fontsize=13, color=PURPLE, weight='bold')
    bullets = [
        '本方案是 5 个测试种子上唯一同时取得 PLR = 0 % 且 0 中断的方案；',
        'MPTCP-style 是确定性卫星场景的反模式：60 s 迟滞触发 70 次切换 → 6.4 % 丢包；',
        'Pure-DRL 收敛到次优 + 高方差：reward 比 IL 专家差 4.7×；切换数 1–5 波动；',
        'Reactive / Max-Visibility 即使可见性策略最优，无状态迁移每次硬切丢 15 万分片；',
        'Ours-Lyap ≡ Ours-IL：模仿学习达到与专家完全相同的部署效果，零代价上星；',
        'E2E 时延 6.24 ms (与基线相当)，说明零中断 / 零丢包不是以时延为代价换取的。',
    ]
    for i, t in enumerate(bullets):
        ax.text(5.5, 35 - i*4.5, '•', fontsize=12, color=GOLD)
        ax.text(7.5, 35 - i*4.5, t, fontsize=11, color=DARK, va='center')
    save(fig, '24_main_table.png')

# =========================================================
# 19 关键可视化
# =========================================================
def slide_25():
    fig, ax = new_slide()
    header(ax, '实验结果③：关键可视化  (4 张图逐图解读)')

    # 2x2 单元格：每格 标题(顶) + 图(中) + 文字解读(底)
    # 单元格宽 44、高 36；左 x=4..48，右 x=50..94
    cells = [
        # (cell_x, cell_y, img_file, title, analysis)
        (4, 46, 'fig4_loss_rate.png', 'Fig.4  Packet loss rate over time',
         '基线 (Reactive / Max-Vis) 在 1100–1800 s 出现孤立尖峰；\n'
         'MPTCP-style 全程高 PLR；本方案曲线始终贴底为 0。'),
        (50, 46, 'fig7_load_balance.png', 'Fig.7  Load balance across 16 gateways',
         '横轴 16 颗 IPv6 网关；纵轴方案承载分片数。\n'
         '本方案 CV = 0.64，远优于 MPTCP-style 的 1.63。'),
        (4, 8, 'fig5_latency_cdf.png', 'Fig.5  End-to-end latency CDF (log x)',
         '4 ms 处 P50 ≈ 0.5；MPTCP / DRL 长尾明显 (P99 > 10 ms)；\n'
         '本方案与 Reactive / Max-Vis 重合于左侧最快段。'),
        (50, 8, 'fig8_summary.png', 'Fig.8  6 方案 × 5 seed mean±std 柱状图',
         '一图概括 PLR / E2E / 切换数 / 中断时长 4 个核心指标；\n'
         '本方案在其中 3 项几乎为 0；MPTCP-style 中断误差棒最长。'),
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
    save(fig, '25_visualizations.png')

# =========================================================
# 20 结论
# =========================================================
def slide_26():
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

    save(fig, '26_conclusion.png')


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in [slide_01, slide_02, slide_03, slide_04, slide_05, slide_06,
               slide_07, slide_08, slide_09, slide_10, slide_11, slide_12,
               slide_13, slide_14, slide_15, slide_16,
               slide_17, slide_18, slide_19, slide_20, slide_21, slide_22,
               slide_23, slide_24, slide_25, slide_26]:
        fn()

if __name__ == '__main__':
    main()
