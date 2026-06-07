"""
Baseline 1 — Reactive Hard Handoff（被动硬切换）：
  当前网关不可见才换；选当前可见且 ΔT 最大者；切换间不做状态迁移。
"""
from __future__ import annotations

import numpy as np

from orbit.topology import TopologySnapshot


def reactive_decision_fn(topo: TopologySnapshot):
    state = {"current_gw": None}

    def decide(t_idx: int) -> int:
        cur = state["current_gw"]
        if cur is None or not topo.visible[t_idx, cur]:
            rem = topo.remaining_visibility(t_idx)
            if rem.max() > 0:
                state["current_gw"] = int(np.argmax(rem))
            else:
                # 全不可见，硬选下一个有最高仰角的（极端情况）
                state["current_gw"] = int(np.argmax(topo.elevation_deg[t_idx]))
        return state["current_gw"]

    return decide
