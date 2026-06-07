"""
Baseline 3 — MPTCP-style Soft Handoff：
  借鉴地面多路径思想，同时维护到 2 个候选网关的"虚链路"。
  决策侧：优先保留当前网关，当且仅当出现"更好"候选（综合分高出阈值）时才切。
  没有真正的两阶段状态迁移，但发包侧"软"，瞬时切换损失略低于 Reactive。

仿真层面：返回选定的主网关 id；其连续性表现略好于 reactive。
"""
from __future__ import annotations

import numpy as np

from orbit.topology import TopologySnapshot


def mptcp_style_decision_fn(topo: TopologySnapshot, loads: np.ndarray,
                            hysteresis: float = 60.0):
    """
    hysteresis: 切换"惯性"阈值（秒）；新候选 ΔT 比当前多出该值才切。
    """
    state = {"current_gw": None}

    def decide(t_idx: int) -> int:
        rem = topo.remaining_visibility(t_idx)
        L = loads[t_idx]
        # 综合分：ΔT - 50*L
        scores = rem - 50.0 * L
        cur = state["current_gw"]
        if cur is None:
            state["current_gw"] = int(np.argmax(scores))
            return state["current_gw"]
        # 当前不可见 → 必切
        if not topo.visible[t_idx, cur]:
            state["current_gw"] = int(np.argmax(scores))
            return state["current_gw"]
        best = int(np.argmax(scores))
        if best != cur and scores[best] - scores[cur] > hysteresis:
            state["current_gw"] = best
        return state["current_gw"]

    return decide
