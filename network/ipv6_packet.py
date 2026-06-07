"""
IPv6 + UDP 报文（对应图片右侧"星间 AOS+IPv6"嵌套）。
仿真层面只保留：版本号、流标签、跳数限制、源/目的 IPv6、payload 字节数。
"""
from __future__ import annotations

from dataclasses import dataclass

from config import CFG


@dataclass
class IPv6Packet:
    src_addr: str                     # 仿真用字符串地址
    dst_addr: str
    flow_label: int = 0
    hop_limit: int = 64
    next_header: int = 17             # UDP
    payload_bytes: int = 0            # 仅 payload，不含 IPv6 头
    timestamp_sec: float = 0.0

    # 元数据：来自哪个 AOS 帧（仅仿真追溯用）
    src_aos_frame_id: int = -1
    src_ccsds_pkt_id: int = -1
    priority: int = 0

    @property
    def total_bytes(self) -> int:
        return CFG.ipv6_header_bytes + CFG.udp_header_bytes + self.payload_bytes
