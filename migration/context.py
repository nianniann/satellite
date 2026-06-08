"""
协议转换上下文（Translation Context, TC）的数据结构。

C = C_static ∪ C_dynamic
  C_static:  (SCID, VCID) → IPv6 地址映射表；QoS 策略表
  C_dynamic: 分片重组缓存 C_frag；VCID 优先级队列状态 C_qos；
             协议转换序列号水位 C_seq；版本号 / 时间戳

这是创新点三相对 VM Live Migration 的本质差异点：
分片重组状态和 VCID 队列状态是卫星场景独有的"协议级"状态。
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

from network.aos_packet import CCSDSFragment


# --------------------------- C_static ---------------------------
@dataclass
class IPv6Mapping:
    ipv6_addr: str
    qos_dscp: int = 0           # 区分服务码点
    bandwidth_quota_kbps: int = 0


@dataclass
class StaticContext:
    """SCID/VCID ↔ IPv6 地址映射 + QoS 策略。"""
    mappings: dict[tuple[int, int], IPv6Mapping] = field(default_factory=dict)
    # 网关 → AOS 卫星的反向映射
    gateway_ipv6_addr: str = "fe80::1"
    aos_scid_list: list[int] = field(default_factory=list)

    def lookup(self, scid: int, vcid: int) -> Optional[IPv6Mapping]:
        return self.mappings.get((scid, vcid))

    def size_bytes(self) -> int:
        """传输该上下文需要的字节数估算。一条映射 ~64B。"""
        return 64 * len(self.mappings) + 32

    def fingerprint(self) -> str:
        s = json.dumps(
            sorted([(k, v.ipv6_addr, v.qos_dscp, v.bandwidth_quota_kbps)
                    for k, v in self.mappings.items()]),
            sort_keys=True,
        )
        return hashlib.sha1(s.encode()).hexdigest()[:12]


# --------------------------- C_dynamic ---------------------------
@dataclass
class FragmentReassemblyBuffer:
    """
    分片重组缓存：(scid, vcid, ccsds_pkt_id) → [已收到的碎片]
    这是 VM Live Migration 里没有的协议级状态。

    性能注意：``_complete_set`` 在 ``add()`` 时增量维护已完成包的 key 集合，
    使 ``complete_packets()`` 从 O(buf 大小) 降到 O(完成集合大小)。
    """
    buf: dict[tuple[int, int, int], list[CCSDSFragment]] = field(default_factory=dict)
    last_update_sec: float = 0.0
    _complete_set: set = field(default_factory=set)

    def add(self, scid: int, vcid: int, frag: CCSDSFragment, t_sec: float):
        key = (scid, vcid, frag.ccsds_pkt_id)
        frags = self.buf.setdefault(key, [])
        frags.append(frag)
        if len(frags) == frags[0].frag_total:
            self._complete_set.add(key)
        self.last_update_sec = t_sec

    def complete_packets(self) -> list[tuple]:
        """返回已收齐所有片的 CCSDS 包 key 列表。"""
        return list(self._complete_set)

    def pop_complete(self, key: tuple) -> list[CCSDSFragment]:
        self._complete_set.discard(key)
        return self.buf.pop(key)

    def size_bytes(self) -> int:
        """碎片总字节数 + 索引开销。"""
        total = 0
        for frags in self.buf.values():
            for f in frags:
                total += f.payload_bytes + 16  # 16B 索引
        return total

    def num_partial(self) -> int:
        return sum(1 for frags in self.buf.values()
                   if 0 < len(frags) < (frags[0].frag_total if frags else 1))

    def fragments_completion_ratio(self) -> dict[tuple, float]:
        """每个未完成 CCSDS 包的完成度。"""
        return {k: len(frags) / frags[0].frag_total for k, frags in self.buf.items()}


@dataclass
class VCIDQueueState:
    """每个 (scid, vcid) 队列的状态：队列长度、累计字节、上次出队时间。"""
    queue_len: int = 0
    queued_bytes: int = 0
    last_dequeue_sec: float = 0.0
    sequence_no: int = 0          # 已发送出去的 IPv6 报文序号水位


@dataclass
class DynamicContext:
    """动态上下文。需要在切换时通过 Pre-copy + Stop-and-copy 迁移。"""
    frag_buffer: FragmentReassemblyBuffer = field(default_factory=FragmentReassemblyBuffer)
    queues: dict[tuple[int, int], VCIDQueueState] = field(default_factory=dict)
    version: int = 0              # 用于乐观复制的版本号
    timestamp_sec: float = 0.0

    def size_bytes(self) -> int:
        frag_sz = self.frag_buffer.size_bytes()
        # 每个 VCID 队列状态 ~24B
        queue_sz = 24 * len(self.queues)
        return frag_sz + queue_sz + 16

    def bump_version(self, t_sec: float):
        self.version += 1
        self.timestamp_sec = t_sec

    def snapshot(self) -> "DynamicContext":
        """快照（深拷贝）。Pre-copy 阶段用。"""
        return copy.deepcopy(self)

    def diff_bytes_since(self, other: "DynamicContext") -> int:
        """
        相对一个旧快照的增量字节数。
        简化估算：新增分片数 × 平均分片大小 + 变化队列条目数 × 24。
        """
        old_keys = set(other.frag_buffer.buf.keys())
        new_keys = set(self.frag_buffer.buf.keys())
        added_keys = new_keys - old_keys
        added_frag_bytes = sum(
            sum(f.payload_bytes + 16 for f in self.frag_buffer.buf[k])
            for k in added_keys
        )
        # 同 key 但新增了 frag
        common = new_keys & old_keys
        for k in common:
            old_n = len(other.frag_buffer.buf.get(k, []))
            new_n = len(self.frag_buffer.buf[k])
            if new_n > old_n:
                added_frag_bytes += (new_n - old_n) * (
                    self.frag_buffer.buf[k][0].payload_bytes + 16
                )
        # 队列状态变化
        q_changed = sum(
            1 for k, v in self.queues.items()
            if k not in other.queues or other.queues[k] != v
        )
        return added_frag_bytes + 24 * q_changed + 16


# --------------------------- 完整 TC ---------------------------
@dataclass
class TranslationContext:
    static: StaticContext
    dynamic: DynamicContext

    def total_size_bytes(self) -> int:
        return self.static.size_bytes() + self.dynamic.size_bytes()
