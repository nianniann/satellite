"""单元测试：协议转换上下文。"""
import pytest

from migration.context import (
    DynamicContext, FragmentReassemblyBuffer, IPv6Mapping,
    StaticContext, TranslationContext, VCIDQueueState,
)
from network.aos_packet import CCSDSFragment


def _make_frag(pkt_id, fi, total=4, size=232):
    return CCSDSFragment(ccsds_pkt_id=pkt_id, frag_index=fi,
                         frag_total=total, payload_bytes=size,
                         is_last=(fi == total - 1))


def test_static_context_lookup_and_size():
    s = StaticContext(mappings={
        (10, v): IPv6Mapping(f"2001:db8::{v:x}") for v in range(4)
    }, aos_scid_list=[10])
    assert s.lookup(10, 0).ipv6_addr == "2001:db8::0"
    assert s.lookup(10, 99) is None
    # size 应随条目线性增长
    s2 = StaticContext(mappings={(10, v): IPv6Mapping(f"2001:db8::{v:x}")
                                  for v in range(8)})
    assert s2.size_bytes() > s.size_bytes()


def test_static_context_fingerprint_stable():
    s1 = StaticContext(mappings={(10, 0): IPv6Mapping("a"),
                                  (10, 1): IPv6Mapping("b")})
    s2 = StaticContext(mappings={(10, 1): IPv6Mapping("b"),
                                  (10, 0): IPv6Mapping("a")})  # 顺序不同
    assert s1.fingerprint() == s2.fingerprint()


def test_frag_buffer_add_and_complete():
    fb = FragmentReassemblyBuffer()
    for fi in range(3):
        fb.add(10, 0, _make_frag(1, fi, total=4), t_sec=fi * 0.01)
    assert fb.complete_packets() == []
    fb.add(10, 0, _make_frag(1, 3, total=4), t_sec=0.04)
    done = fb.complete_packets()
    assert len(done) == 1
    frags = fb.pop_complete(done[0])
    assert len(frags) == 4


def test_frag_buffer_num_partial():
    fb = FragmentReassemblyBuffer()
    fb.add(10, 0, _make_frag(1, 0, total=4), 0.0)  # 部分
    fb.add(10, 0, _make_frag(2, 0, total=2), 0.0)  # 部分
    fb.add(10, 0, _make_frag(2, 1, total=2), 0.0)  # 完整
    assert fb.num_partial() == 1


def test_dynamic_context_diff_after_snapshot():
    dyn = DynamicContext()
    dyn.frag_buffer.add(10, 0, _make_frag(1, 0), 0.0)
    snap = dyn.snapshot()
    # 新增分片
    dyn.frag_buffer.add(10, 0, _make_frag(2, 0), 0.1)
    dyn.frag_buffer.add(10, 0, _make_frag(2, 1), 0.2)
    diff = dyn.diff_bytes_since(snap)
    # 增加了 2 个 fragment（每个 232+16 = 248 字节）
    assert diff >= 2 * (232 + 16)


def test_dynamic_context_version_bump():
    dyn = DynamicContext()
    v0 = dyn.version
    dyn.bump_version(1.5)
    assert dyn.version == v0 + 1
    assert dyn.timestamp_sec == 1.5


def test_translation_context_total_size():
    s = StaticContext(mappings={(10, v): IPv6Mapping(f"::{v}") for v in range(4)})
    d = DynamicContext()
    d.queues[(10, 0)] = VCIDQueueState(queue_len=3, queued_bytes=768)
    tc = TranslationContext(static=s, dynamic=d)
    assert tc.total_size_bytes() == s.size_bytes() + d.size_bytes()
