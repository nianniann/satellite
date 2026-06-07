"""
SimPy 事件驱动仿真环境：

实体：
  - AOSSender:     AOS 卫星，以 rate_pps 速率持续产 AOS 帧，发往当前服务网关
  - IPv6Gateway:   协议转换网关，吸收 AOS 帧 → 重组 CCSDS → 封装 IPv6 → 出端口
  - HandoffController: 每 decision_interval 触发一次决策；执行两阶段迁移

度量：
  per-frame: 是否成功转换、端到端延迟、是否在切换中丢失
  per-switch: outcome、sync_time、dropped fragments
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import simpy

from config import CFG
from migration.consistency import (
    GatewayReplicaStore, OptimisticReplicationPlan,
    plan_replication, replicate_static, run_gossip_round,
)
from migration.context import (
    DynamicContext, StaticContext, TranslationContext,
    IPv6Mapping, VCIDQueueState,
)
from migration.two_phase import (
    MigrationOutcome, MigrationReport, precopy, stop_and_copy,
)
from network.aos_packet import AOSFrame, make_aos_frame_stream, vcid_to_priority
from network.ipv6_packet import IPv6Packet
from orbit.topology import TopologySnapshot


# --------------------------- 事件记录 ---------------------------
@dataclass
class FrameRecord:
    frame_id: int
    sent_at_sec: float
    delivered_at_sec: Optional[float] = None
    dropped: bool = False
    drop_reason: str = ""
    gateway_id: int = -1
    vcid: int = 0


@dataclass
class SwitchRecord:
    decision_at_sec: float
    from_gw: int
    to_gw: int
    outcome: str
    sync_time_sec: float
    interrupt_sec: float
    fragments_migrated: int
    fragments_dropped: int


@dataclass
class SimResults:
    frames: list[FrameRecord] = field(default_factory=list)
    switches: list[SwitchRecord] = field(default_factory=list)
    total_frames: int = 0
    dropped_frames: int = 0

    # 时序统计（每秒一个桶）
    per_second_dropped: dict = field(default_factory=dict)
    per_second_sent: dict = field(default_factory=dict)
    per_second_gw_load: dict = field(default_factory=dict)
    # 用于 load balance 图
    gateway_usage_count: dict = field(default_factory=dict)

    # 一致性 / 副本统计
    gossip_rounds: int = 0
    gossip_evictions: int = 0
    static_replicas_installed: int = 0
    static_bytes_replicated: int = 0

    def packet_loss_rate(self) -> float:
        if self.total_frames == 0:
            return 0.0
        return self.dropped_frames / self.total_frames

    def avg_e2e_latency_ms(self) -> float:
        lats = [(r.delivered_at_sec - r.sent_at_sec) * 1000
                for r in self.frames if not r.dropped and r.delivered_at_sec is not None]
        return float(np.mean(lats)) if lats else 0.0

    def loss_rate_timeseries(self, bin_sec: float = 1.0,
                             duration: float = None) -> tuple[np.ndarray, np.ndarray]:
        if not self.frames:
            return np.array([]), np.array([])
        if duration is None:
            duration = max(r.sent_at_sec for r in self.frames) + 1.0
        n = int(duration / bin_sec) + 1
        sent = np.zeros(n)
        drop = np.zeros(n)
        for r in self.frames:
            b = int(r.sent_at_sec / bin_sec)
            if 0 <= b < n:
                sent[b] += 1
                if r.dropped:
                    drop[b] += 1
        rate = np.divide(drop, sent, out=np.zeros_like(drop), where=sent > 0)
        return np.arange(n) * bin_sec, rate


# --------------------------- 网关 ---------------------------
class IPv6Gateway:
    """网关：持有 TranslationContext，处理来自 AOS 的报文流。"""

    def __init__(self, env: simpy.Environment, gid: int,
                 base_load: float, capacity_pps: float = None):
        self.env = env
        self.gid = gid
        self.base_load = base_load
        self.capacity_pps = capacity_pps or CFG.gateway_cpu_capacity_pps
        # 协议转换上下文
        self.tc = TranslationContext(
            static=StaticContext(mappings={}, aos_scid_list=[]),
            dynamic=DynamicContext(),
        )
        # 处理队列（一个 simpy.Store 模拟入站缓冲）
        self.in_buffer = simpy.Store(env, capacity=1024)
        # 出站 IPv6 报文（仿真层无外发，只统计）
        self.delivered: list[IPv6Packet] = []
        self.is_active = False                       # 是否正在为 AOS 服务
        self.process = env.process(self._run())
        # 协议转换吞吐受 base_load 影响
        self._service_time = lambda: 1.0 / (
            self.capacity_pps * max(0.05, 1.0 - self.base_load)
        )

    def install_mapping(self, scid: int, vcid: int, ipv6_addr: str):
        self.tc.static.mappings[(scid, vcid)] = IPv6Mapping(ipv6_addr, qos_dscp=vcid * 4)
        if scid not in self.tc.static.aos_scid_list:
            self.tc.static.aos_scid_list.append(scid)

    def ensure_queue(self, scid: int, vcid: int):
        key = (scid, vcid)
        if key not in self.tc.dynamic.queues:
            self.tc.dynamic.queues[key] = VCIDQueueState()

    def submit(self, frame: AOSFrame):
        """AOS 帧入站。返回 True 表示成功入队。"""
        if len(self.in_buffer.items) >= self.in_buffer.capacity:
            return False
        self.in_buffer.put(frame)
        return True

    def _run(self):
        """主处理循环：取一帧 → 重组 → 封装 IPv6 → 出。"""
        while True:
            frame = yield self.in_buffer.get()
            yield self.env.timeout(self._service_time())
            self._process_frame(frame)

    def _process_frame(self, frame: AOSFrame):
        scid, vcid = frame.scid, frame.vcid
        self.ensure_queue(scid, vcid)
        q = self.tc.dynamic.queues[(scid, vcid)]

        # 把碎片塞入重组缓存
        for frag in frame.mpdu.fragments:
            self.tc.dynamic.frag_buffer.add(scid, vcid, frag, self.env.now)
        self.tc.dynamic.bump_version(self.env.now)

        # 重组完成的 CCSDS 包 → 封装为 IPv6 包"出"
        for key in self.tc.dynamic.frag_buffer.complete_packets():
            frags = self.tc.dynamic.frag_buffer.pop_complete(key)
            payload_bytes = sum(f.payload_bytes for f in frags)
            mapping = self.tc.static.lookup(scid, vcid)
            if mapping is None:
                continue
            ipv6 = IPv6Packet(
                src_addr=self.tc.static.gateway_ipv6_addr,
                dst_addr=mapping.ipv6_addr,
                flow_label=vcid * 100 + (q.sequence_no & 0xFFFFF),
                hop_limit=64,
                payload_bytes=payload_bytes,
                timestamp_sec=self.env.now,
                src_aos_frame_id=frame.frame_id,
                src_ccsds_pkt_id=frags[0].ccsds_pkt_id,
                priority=vcid_to_priority(vcid),
            )
            q.sequence_no += 1
            q.last_dequeue_sec = self.env.now
            q.queue_len = max(0, q.queue_len - 1)
            q.queued_bytes = max(0, q.queued_bytes - frame.size_bytes)
            self.delivered.append(ipv6)

        # 入队统计
        q.queue_len += 1
        q.queued_bytes += frame.size_bytes


# --------------------------- AOS 发送方 ---------------------------
class AOSSender:
    def __init__(self, env: simpy.Environment, scid: int,
                 rate_pps: float, results: SimResults,
                 gateway_selector: Callable[[float], Optional[int]],
                 gateways: list[IPv6Gateway],
                 isl_props_ms: Callable[[float, int], float],
                 sim_duration: float):
        self.env = env
        self.scid = scid
        self.rate_pps = rate_pps
        self.results = results
        self.gateway_selector = gateway_selector
        self.gateways = gateways
        self.isl_props_ms = isl_props_ms
        self.sim_duration = sim_duration
        self.process = env.process(self._run())

    def _run(self):
        dt = 1.0 / self.rate_pps
        vcids = [0, 1, 2, 3]
        vc_counts = {v: 0 for v in vcids}
        k = 0
        while self.env.now < self.sim_duration:
            v = vcids[k % len(vcids)]
            vc_counts[v] += 1
            frames = make_aos_frame_stream(self.scid, 1, self.env.now, self.rate_pps,
                                           vcids=[v])
            frame = frames[0]
            k += 1
            # 选当前网关
            gw_id = self.gateway_selector(self.env.now)
            self.results.total_frames += 1
            rec = FrameRecord(frame_id=frame.frame_id, sent_at_sec=self.env.now,
                              vcid=v, gateway_id=gw_id if gw_id is not None else -1)
            if gw_id is None or gw_id < 0 or gw_id >= len(self.gateways):
                rec.dropped = True
                rec.drop_reason = "no_gateway"
                self.results.dropped_frames += 1
                self.results.frames.append(rec)
            else:
                gw = self.gateways[gw_id]
                if not gw.is_active:
                    rec.dropped = True
                    rec.drop_reason = "gateway_inactive"
                    self.results.dropped_frames += 1
                    self.results.frames.append(rec)
                else:
                    # 模拟传播延迟到达
                    prop_ms = self.isl_props_ms(self.env.now, gw_id)
                    yield self.env.timeout(prop_ms / 1000.0)
                    ok = gw.submit(frame)
                    if not ok:
                        rec.dropped = True
                        rec.drop_reason = "buffer_overflow"
                        self.results.dropped_frames += 1
                    else:
                        rec.delivered_at_sec = self.env.now
                        # 网关使用统计
                        self.results.gateway_usage_count[gw_id] = \
                            self.results.gateway_usage_count.get(gw_id, 0) + 1
                    self.results.frames.append(rec)
            yield self.env.timeout(dt)


# --------------------------- 切换控制器 ---------------------------
class HandoffController:
    """
    每隔 decision_interval 触发一次决策。
    decision_fn(t_sec) -> 目标网关 id；若 != 当前 → 触发两阶段迁移。
    """

    def __init__(self, env: simpy.Environment,
                 gateways: list[IPv6Gateway],
                 topo: TopologySnapshot, loads: np.ndarray,
                 decision_fn: Callable[[int], int],
                 results: SimResults,
                 decision_interval_sec: float = None,
                 pre_copy_lead_sec: float = None,
                 physical_switch_sec: float = None,
                 do_two_phase: bool = True,
                 enable_consistency: bool = False,
                 replica_top_m: int = 2,
                 gossip_interval_sec: float = 10.0):
        self.env = env
        self.gateways = gateways
        self.topo = topo
        self.loads = loads
        self.decision_fn = decision_fn
        self.results = results
        self.decision_interval = decision_interval_sec or CFG.decision_interval_sec
        self.pre_copy_lead = pre_copy_lead_sec or CFG.pre_copy_lead_sec
        self.physical_switch_sec = physical_switch_sec or CFG.physical_switch_sec
        self.do_two_phase = do_two_phase
        self.current_gw: Optional[int] = None
        # 多网关一致性
        self.enable_consistency = enable_consistency
        self.replica_top_m = replica_top_m
        self.gossip_interval = gossip_interval_sec
        self.replica_stores: dict[int, GatewayReplicaStore] = {
            j: GatewayReplicaStore(j) for j in range(len(gateways))
        }
        self.process = env.process(self._run())
        if enable_consistency:
            self.gossip_process = env.process(self._gossip_loop())

    def get_current_gw(self, t_sec: float) -> Optional[int]:
        return self.current_gw

    def _t_idx(self, t_sec: float) -> int:
        dt = float(self.topo.times_sec[1] - self.topo.times_sec[0])
        return min(int(t_sec / dt), self.topo.num_steps - 1)

    def _run(self):
        # 初始网关：可见且 ΔT 最大者
        idx0 = 0
        rem0 = self.topo.remaining_visibility(idx0)
        if rem0.max() > 0:
            self.current_gw = int(np.argmax(rem0))
        else:
            self.current_gw = 0
        self.gateways[self.current_gw].is_active = True
        # 安装映射（让当前网关知道 AOS 的 SCID/VCID 翻译规则）
        self._install_mappings(self.gateways[self.current_gw])

        while self.env.now < self.topo.times_sec[-1]:
            t_idx = self._t_idx(self.env.now)
            target = self.decision_fn(t_idx)
            target = int(target) if target is not None else self.current_gw

            if target != self.current_gw and 0 <= target < len(self.gateways):
                yield self.env.process(self._do_handoff(self.current_gw, target, t_idx))

            yield self.env.timeout(self.decision_interval)

    def _gossip_loop(self):
        """周期性运行 gossip 协议，淘汰陈旧副本。"""
        while True:
            yield self.env.timeout(self.gossip_interval)
            info = run_gossip_round(self.replica_stores, now_sec=self.env.now)
            self.results.gossip_rounds += 1
            self.results.gossip_evictions += info["evicted"]

    def _install_mappings(self, gw: IPv6Gateway):
        # 1 SCID × 4 VCID
        scid = 10
        for v in range(4):
            gw.install_mapping(scid, v, f"2001:db8::{v:x}")

    def _do_handoff(self, from_gw: int, to_gw: int, t_idx: int):
        if not self.do_two_phase:
            # Hard handoff: 直接切，但有 physical_switch_sec 中断
            self.gateways[from_gw].is_active = False
            yield self.env.timeout(self.physical_switch_sec)
            self.gateways[to_gw].is_active = True
            self._install_mappings(self.gateways[to_gw])
            # 只统计 "未完成" 的分片（已完成的早就出去了，不算丢）
            partial_lost = self.gateways[from_gw].tc.dynamic.frag_buffer.num_partial()
            self.results.switches.append(SwitchRecord(
                decision_at_sec=self.env.now, from_gw=from_gw, to_gw=to_gw,
                outcome="hard", sync_time_sec=0.0,
                interrupt_sec=self.physical_switch_sec,
                fragments_migrated=0,
                fragments_dropped=partial_lost,
            ))
            self.gateways[from_gw].tc.dynamic = DynamicContext()
            self.current_gw = to_gw
            return

        # —— 两阶段路径
        # Pre-copy 阶段：lead_sec 之前
        bw = float(self.topo.isl_bw_mbps[t_idx, to_gw])
        prop = float(self.topo.prop_delay_ms[t_idx, to_gw])
        if bw <= 1e-6:
            # 目标网关此刻不可见 → 不能预拷贝，回退到硬切
            self.gateways[from_gw].is_active = False
            yield self.env.timeout(self.physical_switch_sec)
            self.gateways[to_gw].is_active = True
            self._install_mappings(self.gateways[to_gw])
            partial_lost = self.gateways[from_gw].tc.dynamic.frag_buffer.num_partial()
            self.results.switches.append(SwitchRecord(
                decision_at_sec=self.env.now, from_gw=from_gw, to_gw=to_gw,
                outcome="hard_fallback", sync_time_sec=0.0,
                interrupt_sec=self.physical_switch_sec,
                fragments_migrated=0,
                fragments_dropped=partial_lost,
            ))
            self.gateways[from_gw].tc.dynamic = DynamicContext()
            self.current_gw = to_gw
            return

        pre_result = precopy(self.gateways[from_gw].tc, isl_bw_mbps=bw,
                             isl_prop_ms=prop, lead_sec=self.pre_copy_lead)

        # 乐观复制：把 C_static 并行推给 Top-M 候选（含 to_gw）
        if self.enable_consistency:
            rem = self.topo.remaining_visibility(t_idx)
            plan = plan_replication(
                remaining_visibility=list(rem),
                loads=list(self.loads[t_idx]),
                current_gw=from_gw,
                M=self.replica_top_m,
                min_remaining_sec=self.pre_copy_lead + 2.0,
            )
            # 确保 to_gw 在副本计划中
            if to_gw not in plan.top_m_gateways:
                plan.top_m_gateways = [to_gw] + plan.top_m_gateways[:self.replica_top_m - 1]
            ttls = {j: float(rem[j]) for j in plan.top_m_gateways}
            info = replicate_static(
                self.gateways[from_gw].tc, plan, self.replica_stores,
                now_sec=self.env.now, ttls_sec=ttls,
                dynamic_version=self.gateways[from_gw].tc.dynamic.version,
            )
            self.results.static_replicas_installed += len(info["installed_gateways"])
            self.results.static_bytes_replicated += info["static_bytes_total"]

        # 在 lead_sec 内继续服务，最后做 stop-and-copy
        # 这里我们等待 lead_sec - pre_copy_time（Pre-copy 不会阻塞业务），
        # 然后冻结 → 同步增量 → 切换
        yield self.env.timeout(max(0.0, self.pre_copy_lead - pre_result.pre_copy_time_sec))

        # Stop-and-copy
        rep = stop_and_copy(self.gateways[from_gw].tc, pre_result,
                            isl_bw_mbps=bw, isl_prop_ms=prop,
                            physical_switch_sec=self.physical_switch_sec)

        # 把映射安装到 B（来自 static 拷贝）
        self._install_mappings(self.gateways[to_gw])
        # 业务连续性：根据 outcome 决定中断时长
        interrupt = rep.interrupt_sec
        if rep.outcome == MigrationOutcome.SEAMLESS:
            # 几乎零中断；不切断 A，B 上线后 A 下线
            self.gateways[to_gw].is_active = True
            yield self.env.timeout(0.0)
            self.gateways[from_gw].is_active = False
        elif rep.outcome == MigrationOutcome.DEGRADED:
            # 部分丢弃但服务不中断
            self.gateways[to_gw].is_active = True
            yield self.env.timeout(0.0)
            self.gateways[from_gw].is_active = False
        else:
            # FAILED → 等同硬切
            self.gateways[from_gw].is_active = False
            yield self.env.timeout(self.physical_switch_sec)
            self.gateways[to_gw].is_active = True
            interrupt = self.physical_switch_sec

        # 迁移 dynamic（已选中的分片+队列）
        # 简化：直接把 from_gw.dynamic 复制到 to_gw.dynamic（按 outcome 选择是否完整）
        if rep.outcome == MigrationOutcome.SEAMLESS:
            self.gateways[to_gw].tc.dynamic = self.gateways[from_gw].tc.dynamic.snapshot()
        elif rep.outcome == MigrationOutcome.DEGRADED:
            # 只保留高优先级 VCID
            new_dyn = DynamicContext()
            for k, q in self.gateways[from_gw].tc.dynamic.queues.items():
                if k[1] <= 1:
                    new_dyn.queues[k] = q
            for k, frags in self.gateways[from_gw].tc.dynamic.frag_buffer.buf.items():
                if k[1] <= 1 and frags and len(frags) / frags[0].frag_total >= 0.5:
                    new_dyn.frag_buffer.buf[k] = frags
            self.gateways[to_gw].tc.dynamic = new_dyn
        else:
            self.gateways[to_gw].tc.dynamic = DynamicContext()
        self.gateways[from_gw].tc.dynamic = DynamicContext()

        self.results.switches.append(SwitchRecord(
            decision_at_sec=self.env.now,
            from_gw=from_gw, to_gw=to_gw,
            outcome=rep.outcome.value,
            sync_time_sec=rep.sync_time_sec,
            interrupt_sec=interrupt,
            fragments_migrated=rep.fragments_migrated,
            fragments_dropped=rep.fragments_dropped,
        ))
        self.current_gw = to_gw


# --------------------------- 顶层运行器 ---------------------------
def run_simulation(topo: TopologySnapshot, loads: np.ndarray,
                   decision_fn: Callable[[int], int],
                   sim_duration: float = None,
                   aos_rate_pps: float = None,
                   do_two_phase: bool = True,
                   pre_copy_lead_sec: float = None,
                   physical_switch_sec: float = None,
                   enable_consistency: bool = False,
                   replica_top_m: int = 2,
                   seed: int = 0) -> SimResults:
    sim_duration = sim_duration or float(topo.times_sec[-1])
    aos_rate_pps = aos_rate_pps or CFG.aos_rate_pps

    env = simpy.Environment()
    results = SimResults()

    # 创建网关
    rng = np.random.default_rng(seed)
    gateways = []
    for j in range(topo.num_gateways):
        base = float(loads[0, j])  # 用 t=0 时刻的负载作为基线
        gateways.append(IPv6Gateway(env, gid=j, base_load=base))

    # 切换控制器
    ctrl = HandoffController(
        env, gateways, topo, loads, decision_fn=decision_fn,
        results=results,
        do_two_phase=do_two_phase,
        pre_copy_lead_sec=pre_copy_lead_sec,
        physical_switch_sec=physical_switch_sec,
        enable_consistency=enable_consistency,
        replica_top_m=replica_top_m,
    )

    # AOS 发送方
    def selector(t_sec):
        return ctrl.get_current_gw(t_sec)

    def isl_prop(t_sec, gw_id):
        dt = float(topo.times_sec[1] - topo.times_sec[0])
        idx = min(int(t_sec / dt), topo.num_steps - 1)
        return float(topo.prop_delay_ms[idx, gw_id])

    AOSSender(env, scid=10, rate_pps=aos_rate_pps, results=results,
              gateway_selector=selector, gateways=gateways,
              isl_props_ms=isl_prop, sim_duration=sim_duration)

    env.run(until=sim_duration)
    return results


if __name__ == "__main__":
    from orbit.topology import get_or_build_topology
    from optimizer.lyapunov_solver import (
        lyapunov_online, synthesize_gateway_loads,
    )

    topo, _, _ = get_or_build_topology("smoke", 300.0, step_sec=1.0, use_fallback_tle=True)
    rng = np.random.default_rng(0)
    loads = synthesize_gateway_loads(topo.num_gateways, topo.num_steps, rng)
    traj = lyapunov_online(topo, loads)
    actions = traj.actions

    def decision_fn(t_idx):
        return int(actions[t_idx])

    res = run_simulation(topo, loads, decision_fn=decision_fn,
                         sim_duration=300.0, aos_rate_pps=200.0)
    print(f"frames={res.total_frames} dropped={res.dropped_frames} "
          f"PLR={res.packet_loss_rate()*100:.2f}% "
          f"e2e={res.avg_e2e_latency_ms():.2f}ms "
          f"switches={len(res.switches)}")
    print(f"gateway usage: {res.gateway_usage_count}")
