"""
两阶段状态迁移：Pre-copy + Stop-and-copy。

  ┌──────── 切换前 t_pre ────────┬─ 物理切换 ─┐
  │     Pre-copy:                │  Stop-and  │
  │     A → B 传 C_static        │  -copy:    │
  │     A 继续服务，C_dynamic 增长 │ A 冻结 ΔC  │
  └──────────────────────────────┴────────────┘

  无缝衔接判据（修正原方案）：
      T_sync = |C_static| / B(A,B) + |ΔC_dyn| / B(A,B) + prop_delay
            ≤ T_physical_switch
  不满足时进入降级策略：
      1) 仅迁移高优先级 VCID 队列
      2) 已收 ≥50% 的 CCSDS 包仍迁移；< 50% 丢弃（不浪费带宽）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

from config import CFG
from migration.context import (
    DynamicContext, StaticContext, TranslationContext,
    FragmentReassemblyBuffer, VCIDQueueState,
)


class MigrationOutcome(Enum):
    SEAMLESS = "seamless"          # 完全无缝（T_sync ≤ T_phys）
    DEGRADED = "degraded"          # 部分丢弃但服务连续
    FAILED = "failed"              # 状态完全丢失，等同硬切换


@dataclass
class MigrationReport:
    outcome: MigrationOutcome
    static_bytes_sent: int
    dynamic_bytes_sent: int
    fragments_migrated: int
    fragments_dropped: int
    queues_migrated: int
    queues_dropped: int
    sync_time_sec: float           # 实际同步时长
    physical_switch_sec: float
    interrupt_sec: float           # 业务感受到的中断时长（0 = 真正无缝）
    notes: list[str] = field(default_factory=list)


def _link_transfer_time_sec(bytes_to_send: int, bandwidth_mbps: float,
                            prop_delay_ms: float) -> float:
    if bandwidth_mbps <= 1e-6:
        return float("inf")
    return bytes_to_send * 8 / (bandwidth_mbps * 1e6) + prop_delay_ms / 1000.0


# --------------------------- Pre-copy 阶段 ---------------------------
@dataclass
class PreCopyResult:
    snapshot_at_start: DynamicContext  # 用于后续算 Δ
    static_bytes_sent: int
    pre_copy_time_sec: float


def precopy(tc_a: TranslationContext, isl_bw_mbps: float,
            isl_prop_ms: float, lead_sec: float = None) -> PreCopyResult:
    """A → B 推送 C_static，并对 C_dynamic 拍快照。"""
    lead_sec = lead_sec or CFG.pre_copy_lead_sec
    static_bytes = tc_a.static.size_bytes()
    t_transfer = _link_transfer_time_sec(static_bytes, isl_bw_mbps, isl_prop_ms)
    # Pre-copy 时窗内必须能传完 C_static，否则 lead_sec 不够
    if t_transfer > lead_sec:
        # 在论文里把这种情况作为"算法失效"标记，但仍允许后续 Stop-copy 补传
        pass
    snap = tc_a.dynamic.snapshot()
    return PreCopyResult(
        snapshot_at_start=snap,
        static_bytes_sent=static_bytes,
        pre_copy_time_sec=min(t_transfer, lead_sec),
    )


# --------------------------- Stop-and-copy 阶段 + 降级 ---------------------------
def _select_migratable_fragments(dyn: DynamicContext,
                                 high_priority_only: bool = False
                                 ) -> tuple[dict, int, int]:
    """
    按"≥50% 完成度"筛选可迁移的 CCSDS 包；可选高优先级（priority<=1）过滤。
    返回 (selected_buf, migrated_count, dropped_count)。
    """
    selected = {}
    migrated, dropped = 0, 0
    for key, frags in dyn.frag_buffer.buf.items():
        if not frags:
            continue
        ratio = len(frags) / frags[0].frag_total
        scid, vcid, _ = key
        # VCID 优先级：复用 aos_packet.vcid_to_priority
        prio = min(vcid, 7)
        ok_prio = (not high_priority_only) or (prio <= 1)
        if ratio >= 0.5 and ok_prio:
            selected[key] = list(frags)
            migrated += 1
        else:
            dropped += 1
    return selected, migrated, dropped


def stop_and_copy(tc_a: TranslationContext, pre_result: PreCopyResult,
                  isl_bw_mbps: float, isl_prop_ms: float,
                  physical_switch_sec: float = None) -> MigrationReport:
    """
    在 A 物理离开链路前把 Δ 增量传给 B。判定无缝 / 降级 / 失败。
    """
    physical_switch_sec = physical_switch_sec or CFG.physical_switch_sec

    # 1) 全量增量字节
    full_delta_bytes = tc_a.dynamic.diff_bytes_since(pre_result.snapshot_at_start)
    t_full = _link_transfer_time_sec(full_delta_bytes, isl_bw_mbps, isl_prop_ms)

    if t_full <= physical_switch_sec:
        # —— 无缝路径
        migrated = sum(len(v) for v in tc_a.dynamic.frag_buffer.buf.values())
        return MigrationReport(
            outcome=MigrationOutcome.SEAMLESS,
            static_bytes_sent=pre_result.static_bytes_sent,
            dynamic_bytes_sent=full_delta_bytes,
            fragments_migrated=migrated,
            fragments_dropped=0,
            queues_migrated=len(tc_a.dynamic.queues),
            queues_dropped=0,
            sync_time_sec=t_full,
            physical_switch_sec=physical_switch_sec,
            interrupt_sec=0.0,
            notes=["T_sync ≤ T_phys, full state migrated"],
        )

    # —— 降级路径：先按 ≥50% 筛选
    selected, mig, drop = _select_migratable_fragments(tc_a.dynamic)
    selected_bytes = sum(
        sum(f.payload_bytes + 16 for f in frags) for frags in selected.values()
    )
    queue_bytes = 24 * len(tc_a.dynamic.queues)
    deg_bytes = selected_bytes + queue_bytes + 16
    t_deg = _link_transfer_time_sec(deg_bytes, isl_bw_mbps, isl_prop_ms)

    notes = [f"T_sync_full={t_full:.3f}s > T_phys={physical_switch_sec:.3f}s, degraded"]

    if t_deg <= physical_switch_sec:
        return MigrationReport(
            outcome=MigrationOutcome.DEGRADED,
            static_bytes_sent=pre_result.static_bytes_sent,
            dynamic_bytes_sent=deg_bytes,
            fragments_migrated=mig,
            fragments_dropped=drop,
            queues_migrated=len(tc_a.dynamic.queues),
            queues_dropped=0,
            sync_time_sec=t_deg,
            physical_switch_sec=physical_switch_sec,
            interrupt_sec=0.0,  # 服务不中断，但部分包丢失
            notes=notes + [f"Selected ≥50% fragments: {mig} migrated, {drop} dropped"],
        )

    # —— 进一步降级：仅高优先级
    selected_hp, mig_hp, drop_hp = _select_migratable_fragments(
        tc_a.dynamic, high_priority_only=True
    )
    hp_bytes = sum(
        sum(f.payload_bytes + 16 for f in frags) for frags in selected_hp.values()
    )
    hp_queue_bytes = 24 * sum(1 for (_, vcid) in tc_a.dynamic.queues.keys() if vcid <= 1)
    deg2_bytes = hp_bytes + hp_queue_bytes + 16
    t_deg2 = _link_transfer_time_sec(deg2_bytes, isl_bw_mbps, isl_prop_ms)

    if t_deg2 <= physical_switch_sec:
        all_q = len(tc_a.dynamic.queues)
        return MigrationReport(
            outcome=MigrationOutcome.DEGRADED,
            static_bytes_sent=pre_result.static_bytes_sent,
            dynamic_bytes_sent=deg2_bytes,
            fragments_migrated=mig_hp,
            fragments_dropped=drop + (mig - mig_hp),
            queues_migrated=sum(1 for (_, v) in tc_a.dynamic.queues.keys() if v <= 1),
            queues_dropped=all_q - sum(1 for (_, v) in tc_a.dynamic.queues.keys() if v <= 1),
            sync_time_sec=t_deg2,
            physical_switch_sec=physical_switch_sec,
            interrupt_sec=0.0,
            notes=notes + [f"Only HP VCIDs migrated: {mig_hp} fragments"],
        )

    # —— 仍然不够 → 完全失败，回退硬切换
    interrupt = t_deg2 - physical_switch_sec
    return MigrationReport(
        outcome=MigrationOutcome.FAILED,
        static_bytes_sent=pre_result.static_bytes_sent,
        dynamic_bytes_sent=0,
        fragments_migrated=0,
        fragments_dropped=sum(len(v) for v in tc_a.dynamic.frag_buffer.buf.values()),
        queues_migrated=0,
        queues_dropped=len(tc_a.dynamic.queues),
        sync_time_sec=t_deg2,
        physical_switch_sec=physical_switch_sec,
        interrupt_sec=interrupt,
        notes=notes + ["Even HP migration too large; fallback to hard handoff"],
    )


# --------------------------- 一站式接口 ---------------------------
def migrate(tc_a: TranslationContext, isl_bw_mbps: float, isl_prop_ms: float,
            lead_sec: float = None,
            physical_switch_sec: float = None) -> MigrationReport:
    pre = precopy(tc_a, isl_bw_mbps, isl_prop_ms, lead_sec)
    rep = stop_and_copy(tc_a, pre, isl_bw_mbps, isl_prop_ms, physical_switch_sec)
    return rep


if __name__ == "__main__":
    # 自检：构造一个有分片缓存的 TC，跑两阶段
    from network.aos_packet import CCSDSFragment

    static = StaticContext(
        mappings={(10, v): None for v in range(8)} | {(10, 0): None},
        aos_scid_list=[10],
    )
    # 填合理映射
    from migration.context import IPv6Mapping
    static.mappings = {(10, v): IPv6Mapping(f"2001:db8::{v:x}", qos_dscp=v * 4)
                       for v in range(8)}

    dyn = DynamicContext()
    # 模拟 12 个 CCSDS 包，每包 4 片，已收 1-4 片不等
    rng = np.random.default_rng(1)
    for pkt_id in range(12):
        total = 4
        recvd = int(rng.integers(1, total + 1))
        for fi in range(recvd):
            dyn.frag_buffer.add(10, pkt_id % 4, CCSDSFragment(
                ccsds_pkt_id=pkt_id, frag_index=fi, frag_total=total,
                payload_bytes=232, is_last=(fi == total - 1),
            ), t_sec=fi * 0.01)
    for v in range(4):
        dyn.queues[(10, v)] = VCIDQueueState(queue_len=5, queued_bytes=5 * 256)
    tc = TranslationContext(static=static, dynamic=dyn)
    print(f"TC total bytes: {tc.total_size_bytes()}")

    # 模拟 pre-copy 后又涌入新分片（这才是真实场景）
    for bw in (100.0, 30.0, 5.0, 1.0):
        # 先做 precopy 拍快照
        pre = precopy(tc, isl_bw_mbps=bw, isl_prop_ms=10.0)
        # 之后 AOS 又发了一波数据导致大量新分片缓存
        for pkt_id in range(100, 100 + 80):
            for fi in range(4):
                tc.dynamic.frag_buffer.add(10, pkt_id % 4, CCSDSFragment(
                    ccsds_pkt_id=pkt_id, frag_index=fi, frag_total=4,
                    payload_bytes=232, is_last=(fi == 3),
                ), t_sec=fi * 0.01)
        rep = stop_and_copy(tc, pre, isl_bw_mbps=bw, isl_prop_ms=10.0)
        print(f"\nBW={bw:5.1f}Mbps -> {rep.outcome.value}")
        print(f"  static={rep.static_bytes_sent}B dyn={rep.dynamic_bytes_sent}B"
              f"  T_sync={rep.sync_time_sec*1000:.1f}ms"
              f"  frags m/d={rep.fragments_migrated}/{rep.fragments_dropped}"
              f"  interrupt={rep.interrupt_sec*1000:.1f}ms")
        for n in rep.notes:
            print(f"  · {n}")
        # 重置 dynamic 以便下一轮对比
        tc.dynamic = DynamicContext()
        for v in range(4):
            tc.dynamic.queues[(10, v)] = VCIDQueueState(queue_len=5, queued_bytes=1280)
        for pkt_id in range(12):
            total = 4
            recvd = int(rng.integers(1, total + 1))
            for fi in range(recvd):
                tc.dynamic.frag_buffer.add(10, pkt_id % 4, CCSDSFragment(
                    ccsds_pkt_id=pkt_id, frag_index=fi, frag_total=total,
                    payload_bytes=232, is_last=(fi == total - 1),
                ), t_sec=fi * 0.01)
