"""
Baseline 2 — Max-Visibility Heuristic：
  每个决策时刻都选可见且 ΔT 最大的网关；不考虑负载、不限制切换次数。
  可作为"贪心可见性"的对照（容易过度切换）。
"""
from __future__ import annotations

import numpy as np

from orbit.topology import TopologySnapshot


def max_visibility_decision_fn(topo: TopologySnapshot):
    def decide(t_idx: int) -> int:
        rem = topo.remaining_visibility(t_idx)
        if rem.max() > 0:
            return int(np.argmax(rem))
        return int(np.argmax(topo.elevation_deg[t_idx]))
    return decide
