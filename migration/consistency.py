"""
多网关覆盖下的状态副本一致性。

场景：AOS 卫星同时被 k≥2 颗 IPv6 候选网关 G = {g₁..g_k} 覆盖。
为了让 Pre-copy 阶段不必赌"将来选谁"，在 Top-M 候选上并行推送 C_static
（开销 = M × |C_static|，可控）。Stop-and-copy 仅向真正选中者推 C_dynamic。

落选副本通过 Gossip 消息淘汰：
  ──> 每个网关周期性广播 (scid, version, ttl) 摘要
  ──> 收到 version 比自己新或自己 TTL 过期 → 丢弃旧副本

实现要点：
  - 每个副本带版本号 + 写入时间戳
  - Lamport 时钟保证 partial order
  - TTL = 网关本次可见窗口剩余时长（来自星历预测）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from migration.context import StaticContext, TranslationContext


# --------------------------- 副本与一致性管理 ---------------------------
@dataclass
class StaticReplica:
    scid: int                  # 该副本服务的 AOS 卫星
    static: StaticContext
    version: int               # 来源 A 的 dynamic.version 快照
    written_at_sec: float
    ttl_sec: float             # 这个副本何时变陈旧（= 网关可见窗剩余时长）

    def is_stale(self, now_sec: float) -> bool:
        return now_sec - self.written_at_sec > self.ttl_sec


@dataclass
class GossipMessage:
    """
    Gossip 摘要：宣告 "我手里 (scid, version) 的副本"。
    其他网关收到后比较版本，淘汰陈旧或请求新版本。
    """
    sender_gateway: int
    scid: int
    version: int
    written_at_sec: float
    lamport: int


class GatewayReplicaStore:
    """每颗网关维护的副本仓库。"""

    def __init__(self, gateway_id: int):
        self.gateway_id = gateway_id
        # (scid) → StaticReplica
        self.replicas: dict[int, StaticReplica] = {}
        self.lamport: int = 0

    def install(self, replica: StaticReplica):
        self.lamport += 1
        cur = self.replicas.get(replica.scid)
        if cur is None or replica.version > cur.version:
            self.replicas[replica.scid] = replica

    def evict_stale(self, now_sec: float) -> list[int]:
        evicted = []
        for scid in list(self.replicas.keys()):
            if self.replicas[scid].is_stale(now_sec):
                evicted.append(scid)
                del self.replicas[scid]
        return evicted

    def gossip_announce(self) -> list[GossipMessage]:
        self.lamport += 1
        return [
            GossipMessage(
                sender_gateway=self.gateway_id, scid=scid,
                version=r.version, written_at_sec=r.written_at_sec,
                lamport=self.lamport,
            )
            for scid, r in self.replicas.items()
        ]

    def on_gossip(self, msg: GossipMessage) -> Optional[str]:
        """
        收到他人 gossip。返回动作描述：
          - None: 无操作
          - "evict": 我比对方旧，淘汰本地副本
          - "request_update": 我比对方旧，可请求新版本
        """
        self.lamport = max(self.lamport, msg.lamport) + 1
        cur = self.replicas.get(msg.scid)
        if cur is None:
            return None
        if cur.version < msg.version:
            # 比对方旧 → 标记并丢弃
            del self.replicas[msg.scid]
            return "evict"
        return None


# --------------------------- Top-M 乐观复制控制器 ---------------------------
@dataclass
class OptimisticReplicationPlan:
    """决定本次 Pre-copy 阶段把 C_static 推给哪几颗候选。"""
    top_m_gateways: list[int]
    rationale: dict


def plan_replication(remaining_visibility: list[float],
                     loads: list[float],
                     current_gw: int,
                     M: int = 2,
                     min_remaining_sec: float = 30.0) -> OptimisticReplicationPlan:
    """
    根据可见时长 + 负载，选 Top-M 候选乐观复制。
    规则：可见时长足够 + 负载较低，排除当前网关（它已有 full state）。
    """
    candidates = []
    for j, (dt, l) in enumerate(zip(remaining_visibility, loads)):
        if j == current_gw:
            continue
        if dt < min_remaining_sec:
            continue
        # 综合分：可见时长越长越好，负载越低越好
        score = dt - 50.0 * l
        candidates.append((j, score, dt, l))
    candidates.sort(key=lambda x: -x[1])
    selected = [c[0] for c in candidates[:M]]
    return OptimisticReplicationPlan(
        top_m_gateways=selected,
        rationale={"candidates": candidates, "M": M},
    )


def replicate_static(tc_a: TranslationContext, plan: OptimisticReplicationPlan,
                     stores: dict[int, GatewayReplicaStore],
                     now_sec: float, ttls_sec: dict[int, float],
                     dynamic_version: int = 0) -> dict:
    """对 plan 里的所有网关安装一份 static 副本。"""
    installed = []
    bytes_sent_total = 0
    for gw_id in plan.top_m_gateways:
        replica = StaticReplica(
            scid=tc_a.static.aos_scid_list[0] if tc_a.static.aos_scid_list else 0,
            static=tc_a.static,
            version=dynamic_version,
            written_at_sec=now_sec,
            ttl_sec=ttls_sec.get(gw_id, 0.0),
        )
        stores[gw_id].install(replica)
        installed.append(gw_id)
        bytes_sent_total += tc_a.static.size_bytes()
    return {
        "installed_gateways": installed,
        "static_bytes_total": bytes_sent_total,
    }


def run_gossip_round(stores: dict[int, GatewayReplicaStore], now_sec: float) -> dict:
    """一轮 gossip：每颗网关向其他网关广播摘要 → 收集淘汰统计。"""
    all_msgs = []
    for gw_id, store in stores.items():
        all_msgs.extend(store.gossip_announce())

    evicted_count = 0
    for msg in all_msgs:
        for gw_id, store in stores.items():
            if gw_id == msg.sender_gateway:
                continue
            r = store.on_gossip(msg)
            if r == "evict":
                evicted_count += 1
    # 还可能因 TTL 过期淘汰
    for store in stores.values():
        evicted_count += len(store.evict_stale(now_sec))
    return {"evicted": evicted_count, "n_msgs": len(all_msgs)}


if __name__ == "__main__":
    # 自检：3 网关、1 AOS 卫星、3 轮 gossip
    from migration.context import IPv6Mapping

    static = StaticContext(
        mappings={(10, v): IPv6Mapping(f"2001:db8::{v:x}") for v in range(4)},
        aos_scid_list=[10],
    )
    dyn = type("D", (), {"version": 7})()  # 极简
    tc = type("TC", (), {"static": static})()
    stores = {gid: GatewayReplicaStore(gid) for gid in range(3)}

    plan = plan_replication(
        remaining_visibility=[120.0, 200.0, 80.0],
        loads=[0.2, 0.4, 0.7], current_gw=0, M=2,
    )
    print(f"Plan: replicate to gateways {plan.top_m_gateways}")
    rep_info = replicate_static(tc, plan, stores,
                                now_sec=0.0,
                                ttls_sec={1: 200, 2: 80},
                                dynamic_version=7)
    print(f"Replicated: {rep_info}")
    for gid, s in stores.items():
        print(f"  gw{gid}: replicas={list(s.replicas.keys())}")

    # 安装一个更新的副本到 gw1，gossip 后 gw2 应淘汰旧版
    stores[1].install(StaticReplica(scid=10, static=static, version=12,
                                    written_at_sec=10.0, ttl_sec=200))
    g = run_gossip_round(stores, now_sec=11.0)
    print(f"Gossip round: {g}")
