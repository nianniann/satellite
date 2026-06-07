"""单元测试：多网关一致性 Gossip 协议。"""
import pytest

from migration.consistency import (
    GatewayReplicaStore, GossipMessage, StaticReplica,
    plan_replication, replicate_static, run_gossip_round,
)
from migration.context import IPv6Mapping, StaticContext


def _mk_static():
    return StaticContext(
        mappings={(10, v): IPv6Mapping(f"::{v:x}") for v in range(4)},
        aos_scid_list=[10],
    )


def test_replica_store_install_keeps_latest():
    store = GatewayReplicaStore(0)
    s = _mk_static()
    store.install(StaticReplica(scid=10, static=s, version=1,
                                written_at_sec=0, ttl_sec=100))
    store.install(StaticReplica(scid=10, static=s, version=3,
                                written_at_sec=1, ttl_sec=100))
    # 旧版应该不覆盖新版
    store.install(StaticReplica(scid=10, static=s, version=2,
                                written_at_sec=2, ttl_sec=100))
    assert store.replicas[10].version == 3


def test_replica_evict_stale():
    store = GatewayReplicaStore(0)
    s = _mk_static()
    store.install(StaticReplica(scid=10, static=s, version=1,
                                written_at_sec=0, ttl_sec=5))
    evicted = store.evict_stale(now_sec=10.0)
    assert evicted == [10]
    assert 10 not in store.replicas


def test_plan_replication_excludes_current():
    plan = plan_replication(
        remaining_visibility=[100.0, 200.0, 80.0, 300.0],
        loads=[0.1, 0.2, 0.3, 0.4],
        current_gw=2, M=2,
    )
    assert 2 not in plan.top_m_gateways
    assert len(plan.top_m_gateways) == 2


def test_plan_replication_respects_min_remaining():
    plan = plan_replication(
        remaining_visibility=[5.0, 200.0, 8.0, 300.0],
        loads=[0.1, 0.2, 0.3, 0.4],
        current_gw=0, M=2, min_remaining_sec=30.0,
    )
    # gw 0, 2 不达标，只剩 1 和 3
    assert set(plan.top_m_gateways).issubset({1, 3})


def test_gossip_evicts_older_replica():
    s = _mk_static()
    stores = {gid: GatewayReplicaStore(gid) for gid in range(3)}
    # gw1 持新版，gw2 持旧版
    stores[1].install(StaticReplica(scid=10, static=s, version=10,
                                    written_at_sec=0, ttl_sec=1000))
    stores[2].install(StaticReplica(scid=10, static=s, version=5,
                                    written_at_sec=0, ttl_sec=1000))
    info = run_gossip_round(stores, now_sec=1.0)
    # gw2 应被淘汰，gw1 保留
    assert 10 not in stores[2].replicas
    assert 10 in stores[1].replicas
    assert info["evicted"] >= 1


def test_replicate_static_writes_all_targets():
    s = _mk_static()
    tc = type("TC", (), {"static": s})()
    stores = {gid: GatewayReplicaStore(gid) for gid in range(4)}
    plan = plan_replication(
        remaining_visibility=[120.0, 200.0, 80.0, 300.0],
        loads=[0.2, 0.4, 0.7, 0.3], current_gw=0, M=2,
    )
    info = replicate_static(tc, plan, stores, now_sec=0.0,
                            ttls_sec={g: 100.0 for g in plan.top_m_gateways},
                            dynamic_version=7)
    assert info["installed_gateways"] == plan.top_m_gateways
    for gid in plan.top_m_gateways:
        assert 10 in stores[gid].replicas
