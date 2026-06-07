"""单元测试：轨道几何与拓扑张量。"""
import numpy as np
import pytest
from skyfield.api import load

from orbit.skyfield_sim import (
    build_scenario, distance_km, elevation_deg, has_line_of_sight,
    is_visible, isl_bandwidth_mbps, predict_visibility_window,
    propagation_delay_ms,
)
from orbit.topology import get_or_build_topology


def test_distance_symmetry():
    aos, gws = build_scenario(use_fallback=True)
    ts = load.timescale()
    t = ts.utc(2024, 1, 1, 0, 0, 0)
    for gw in gws[:3]:
        d1 = distance_km(aos[0], gw, t)
        d2 = distance_km(gw, aos[0], t)
        assert abs(d1 - d2) < 1e-6


def test_los_with_earth_block():
    """如果两星正好在地球两侧，LOS 应被挡。"""
    aos, gws = build_scenario(use_fallback=True)
    ts = load.timescale()
    t = ts.utc(2024, 1, 1, 0, 0, 0)
    los_results = [has_line_of_sight(aos[0], gw, t) for gw in gws]
    # 至少有一颗被挡（合成星座设计上保证有覆盖死角）
    assert any(not r for r in los_results)


def test_isl_bandwidth_decreases_with_distance():
    b_near = isl_bandwidth_mbps(500.0)
    b_mid = isl_bandwidth_mbps(2500.0)
    b_far = isl_bandwidth_mbps(5000.0)
    assert b_near >= b_mid >= b_far


def test_prop_delay_linear_in_distance():
    assert propagation_delay_ms(1000.0) == pytest.approx(1000.0 / 299792.458 * 1000)
    assert propagation_delay_ms(0.0) == 0.0


def test_topology_remaining_visibility_nonneg():
    topo, _, _ = get_or_build_topology(
        cache_name="test_orbit", duration_sec=300.0, step_sec=2.0,
        use_fallback_tle=True, force=True,
    )
    for k in range(0, topo.num_steps, 10):
        rem = topo.remaining_visibility(k)
        assert rem.shape == (topo.num_gateways,)
        assert (rem >= 0).all()


def test_topology_visibility_consistent_with_distance():
    topo, _, _ = get_or_build_topology(
        cache_name="test_orbit", duration_sec=300.0, step_sec=2.0,
        use_fallback_tle=True,
    )
    # 不可见时带宽应为 0
    invisible = ~topo.visible
    assert (topo.isl_bw_mbps[invisible] == 0).all()
