"""
全局配置：常量、路径、超参数。所有模块从这里取值，避免散落。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DATA_DIR = ROOT / "data"
TLE_DIR = DATA_DIR / "tle"
RESULTS_DIR = ROOT / "results"
FIG_DIR = RESULTS_DIR / "figures"
TB_DIR = RESULTS_DIR / "tensorboard"
CKPT_DIR = RESULTS_DIR / "checkpoints"

for _p in (DATA_DIR, TLE_DIR, RESULTS_DIR, FIG_DIR, TB_DIR, CKPT_DIR):
    _p.mkdir(parents=True, exist_ok=True)


# ----------------------------- 物理常量 -----------------------------
EARTH_RADIUS_KM = 6371.0
SPEED_OF_LIGHT_KMS = 299792.458


# ----------------------------- 仿真参数 -----------------------------
@dataclass
class SimConfig:
    # 时间
    sim_duration_sec: float = 3600.0          # 仿真总时长（60 分钟，足够 LEO 切换多次）
    decision_interval_sec: float = 1.0        # 决策时隙长度
    expert_train_horizon_sec: float = 7200.0  # 离线生成专家轨迹的时长（2 小时）

    # 几何
    min_elevation_deg: float = 10.0           # 最小通信仰角
    isl_max_range_km: float = 3500.0          # 星间链路最大距离（限小 → 切换频繁）

    # 候选网关
    num_candidate_gateways: int = 16          # 候选 IPv6 网关数量
    num_aos_satellites: int = 1               # AOS 卫星数量（单条业务流）

    # 报文/协议
    aos_frame_bytes: int = 256                # 一帧AOS长度
    aos_data_field_bytes: int = 236
    ipv6_header_bytes: int = 40
    udp_header_bytes: int = 8
    aos_rate_pps: float = 500.0               # AOS帧发送速率（pkt/s）
    ccsds_fragments_per_pkt: int = 4          # 每个CCSDS包平均分成几片M_PDU

    # 网关与负载
    gateway_cpu_capacity_pps: float = 2000.0  # 网关协议转换能力（pkt/s）
    gateway_base_load_range: tuple = (0.1, 0.6)  # 网关其他业务的基础负载占比

    # ISL带宽（Mbps），随距离与几何变化
    isl_bandwidth_max_mbps: float = 100.0
    isl_bandwidth_min_mbps: float = 10.0

    # 切换物理参数
    physical_switch_sec: float = 0.5          # 天线转向+链路重建窗口
    pre_copy_lead_sec: float = 3.0            # 提前 t_pre 秒开始Pre-copy

    # Lyapunov
    V_lyapunov: float = 50.0                  # V参数（utility-delay权衡）
    switch_budget_per_sec: float = 1.0 / 120  # 平均每120秒最多切换一次
    alpha: float = 1.0                        # 中断惩罚权重
    beta: float = 0.3                         # 负载惩罚权重

    # 模仿学习
    il_hidden_dim: int = 64
    il_num_layers: int = 3
    il_learning_rate: float = 1e-3
    il_batch_size: int = 256
    il_epochs: int = 50
    il_dropout: float = 0.1

    # 随机种子
    seed: int = 42


CFG = SimConfig()


def get_device():
    """优先选 CUDA，其次 MPS，否则 CPU。

    支持通过环境变量 ``SAT_GPU_INDEX`` 选择具体的 GPU 索引（默认 0），
    这样在多卡机器上只占用一张 GPU。``CUDA_VISIBLE_DEVICES`` 也可单独控制。
    """
    import torch
    if torch.cuda.is_available():
        idx = int(os.environ.get("SAT_GPU_INDEX", "0"))
        idx = max(0, min(idx, torch.cuda.device_count() - 1))
        return torch.device(f"cuda:{idx}")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")
