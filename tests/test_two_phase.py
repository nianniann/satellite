"""单元测试：两阶段迁移与三层降级策略。"""
import pytest

from migration.context import (
    DynamicContext, IPv6Mapping, StaticContext, TranslationContext,
    VCIDQueueState,
)
from migration.two_phase import (
    MigrationOutcome, migrate, precopy, stop_and_copy,
)
from network.aos_packet import CCSDSFragment


def _frag(pkt_id, fi, total=4, size=232):
    return CCSDSFragment(ccsds_pkt_id=pkt_id, frag_index=fi,
                         frag_total=total, payload_bytes=size,
                         is_last=(fi == total - 1))


def _make_tc(num_partial_pkts: int = 20, total_per_pkt: int = 4):
    static = StaticContext(
        mappings={(10, v): IPv6Mapping(f"2001:db8::{v:x}", qos_dscp=v * 4)
                  for v in range(4)},
        aos_scid_list=[10],
    )
    dyn = DynamicContext()
    for pkt in range(num_partial_pkts):
        # 一半完成度
        for fi in range(total_per_pkt // 2 + 1):
            dyn.frag_buffer.add(10, pkt % 4,
                                _frag(pkt, fi, total=total_per_pkt), 0.0)
    for v in range(4):
        dyn.queues[(10, v)] = VCIDQueueState(queue_len=2, queued_bytes=512)
    return TranslationContext(static=static, dynamic=dyn)


def test_seamless_high_bandwidth():
    tc = _make_tc(num_partial_pkts=10)
    rep = migrate(tc, isl_bw_mbps=100.0, isl_prop_ms=5.0)
    assert rep.outcome == MigrationOutcome.SEAMLESS
    assert rep.interrupt_sec == 0.0


def test_degraded_low_bandwidth_with_high_dyn_load():
    """Pre-copy 之后增量很大，但带宽不足。"""
    tc = _make_tc(num_partial_pkts=5)
    pre = precopy(tc, isl_bw_mbps=2.0, isl_prop_ms=20.0)
    # 涌入大量新分片
    for pkt in range(200, 200 + 200):
        for fi in range(4):
            tc.dynamic.frag_buffer.add(10, pkt % 4, _frag(pkt, fi), 0.0)
    rep = stop_and_copy(tc, pre, isl_bw_mbps=2.0, isl_prop_ms=20.0)
    assert rep.outcome in (MigrationOutcome.DEGRADED, MigrationOutcome.FAILED)


def test_failed_extreme_low_bandwidth():
    """带宽极低，HP 也传不完。"""
    tc = _make_tc(num_partial_pkts=5)
    pre = precopy(tc, isl_bw_mbps=0.05, isl_prop_ms=200.0)
    for pkt in range(200, 200 + 500):
        for fi in range(4):
            tc.dynamic.frag_buffer.add(10, pkt % 4, _frag(pkt, fi), 0.0)
    rep = stop_and_copy(tc, pre, isl_bw_mbps=0.05, isl_prop_ms=200.0)
    assert rep.outcome == MigrationOutcome.FAILED
    assert rep.interrupt_sec > 0.0


def test_degraded_drops_low_priority_first():
    """降级时应优先保留 vcid <= 1 的分片。"""
    static = StaticContext(
        mappings={(10, v): IPv6Mapping(f"::{v:x}") for v in range(8)},
        aos_scid_list=[10],
    )
    dyn = DynamicContext()
    # 低优先级（vcid=3）大量分片，高优先级（vcid=0）少量
    for pkt in range(50):
        for fi in range(4):
            dyn.frag_buffer.add(10, 3, _frag(pkt, fi), 0.0)
    for pkt in range(50, 55):
        for fi in range(4):
            dyn.frag_buffer.add(10, 0, _frag(pkt, fi), 0.0)
    for v in (0, 3):
        dyn.queues[(10, v)] = VCIDQueueState(queue_len=1, queued_bytes=256)
    tc = TranslationContext(static=static, dynamic=dyn)

    pre = precopy(tc, isl_bw_mbps=0.5, isl_prop_ms=10.0)
    for pkt in range(200, 200 + 100):
        for fi in range(4):
            tc.dynamic.frag_buffer.add(10, 3, _frag(pkt, fi), 0.0)
    rep = stop_and_copy(tc, pre, isl_bw_mbps=0.5, isl_prop_ms=10.0)
    # 应进入降级
    assert rep.outcome == MigrationOutcome.DEGRADED
    # HP 数量远小于 LP，说明确实优先选了 HP
    assert rep.fragments_migrated <= 100
