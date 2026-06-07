"""
AOS 帧结构（对应图片"存量 AOS 卫星：AOS帧结构"）：
  256 Bytes 总长 =
    同步头(4) + 主导头(6) + 路由信息域(3) + 可靠传输域(5) +
    数据域(236) + CRC(2)
  主导头含：版本号(2b) | SCID(8b) | VCID(6b) | 虚拟信道帧计数(...)
  数据域内承载 M_PDU：M_PDU头(2B,含首导指针 11bit) + CCSDS包碎片

为减少模拟开销，这里不做比特级编码，只保留报文携带的"语义字段"。
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional

from config import CFG

# 全局自增帧号生成器（避免每个 AOS 卫星重复维护）
_FRAME_COUNTER = itertools.count(1)
_CCSDS_PKT_COUNTER = itertools.count(1)


@dataclass
class CCSDSFragment:
    """单个 CCSDS 包的一片碎片。一个 CCSDS 包跨多个 M_PDU 时会被切成多片。"""
    ccsds_pkt_id: int              # 该 CCSDS 包的全局 ID（用于重组）
    frag_index: int                # 0..n-1
    frag_total: int                # n（总片数）
    payload_bytes: int             # 本片有效字节数
    is_last: bool = False

    @property
    def is_first(self) -> bool:
        return self.frag_index == 0


@dataclass
class MPDU:
    """M_PDU = 一个 AOS 数据域里的承载单元。"""
    first_header_pointer: int = 0  # 首导指针，11bit，指出第一个 CCSDS 包起点
    fragments: list[CCSDSFragment] = field(default_factory=list)


@dataclass
class AOSFrame:
    """AOS 帧（仿真用语义字段，不做比特级序列化）。"""
    scid: int                      # 卫星标识符 8bit
    vcid: int                      # 虚拟信道 id 6bit (QoS 区分)
    vc_frame_count: int            # 虚拟信道帧计数
    mpdu: MPDU
    frame_id: int = field(default_factory=lambda: next(_FRAME_COUNTER))
    timestamp_sec: float = 0.0
    priority: int = 0              # 由 VCID 推断的 QoS 优先级 0=高 ~ 7=低
    size_bytes: int = CFG.aos_frame_bytes


def make_aos_frame(scid: int, vcid: int, vc_frame_count: int,
                   timestamp_sec: float,
                   fragments_per_ccsds: int = None) -> AOSFrame:
    """
    构造一帧 AOS。单帧的 236B 数据域里包含一个 CCSDS 包的若干片。
    我们简化为：一个 AOS 帧承载一个 CCSDS 包的 1/N 分片（前 N-1 片各 ~232B，末片末尾标记）。
    """
    fragments_per_ccsds = fragments_per_ccsds or CFG.ccsds_fragments_per_pkt
    pkt_id = next(_CCSDS_PKT_COUNTER)
    # 这里只放第一片以简化；分片在网关重组时按 (pkt_id, frag_index) 索引
    # 为了让"碎片缓存"有意义，我们循环生成 N 片
    frag = CCSDSFragment(
        ccsds_pkt_id=pkt_id,
        frag_index=0,
        frag_total=fragments_per_ccsds,
        payload_bytes=CFG.aos_data_field_bytes,
        is_last=(fragments_per_ccsds == 1),
    )
    return AOSFrame(
        scid=scid, vcid=vcid, vc_frame_count=vc_frame_count,
        mpdu=MPDU(first_header_pointer=0, fragments=[frag]),
        timestamp_sec=timestamp_sec,
        priority=vcid_to_priority(vcid),
    )


def vcid_to_priority(vcid: int) -> int:
    """简化映射：VCID 0=遥测高优先，1=遥控，2=载荷数据，3+=普通。"""
    return min(vcid, 7)


def make_aos_frame_stream(scid: int, num_frames: int, start_sec: float,
                          rate_pps: float, vcids: Optional[list[int]] = None) -> list[AOSFrame]:
    """生成一段连续 AOS 帧流（用于 SimPy 注入）。"""
    vcids = vcids or [0, 1, 2, 3]
    dt = 1.0 / rate_pps
    frames = []
    vc_counts = {v: 0 for v in vcids}
    for k in range(num_frames):
        v = vcids[k % len(vcids)]
        vc_counts[v] += 1
        frames.append(make_aos_frame(scid, v, vc_counts[v], start_sec + k * dt))
    return frames
