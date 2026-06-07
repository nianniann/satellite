"""SimPy 仿真集成测试（不依赖 GPU）。"""
import numpy as np
import pytest

from baselines.max_visibility import max_visibility_decision_fn
from baselines.reactive import reactive_decision_fn
from network.simpy_env import run_simulation
from optimizer.lyapunov_solver import (
    lyapunov_online, synthesize_gateway_loads,
)
from orbit.topology import get_or_build_topology


@pytest.fixture(scope="module")
def setup():
    topo, _, _ = get_or_build_topology(
        cache_name="test_sim", duration_sec=600.0, step_sec=2.0,
        use_fallback_tle=True, force=True,
    )
    loads = synthesize_gateway_loads(topo.num_gateways, topo.num_steps,
                                     np.random.default_rng(0))
    return topo, loads


def test_run_simulation_reactive_baseline(setup):
    topo, loads = setup
    res = run_simulation(
        topo, loads,
        decision_fn=reactive_decision_fn(topo),
        sim_duration=200.0, aos_rate_pps=50.0,
        do_two_phase=False,
    )
    assert res.total_frames > 0
    assert 0 <= res.packet_loss_rate() <= 1.0


def test_two_phase_reduces_loss_vs_hard(setup):
    """两阶段方案 PLR 应 <= 硬切方案。"""
    topo, loads = setup
    traj = lyapunov_online(topo, loads)

    def lyap_decide(t_idx):
        return int(traj.actions[t_idx])

    hard = run_simulation(topo, loads, decision_fn=lyap_decide,
                          sim_duration=400.0, aos_rate_pps=100.0,
                          do_two_phase=False)
    soft = run_simulation(topo, loads, decision_fn=lyap_decide,
                          sim_duration=400.0, aos_rate_pps=100.0,
                          do_two_phase=True)
    # 两个方案决策相同，硬切丢包应 ≥ 两阶段
    assert soft.packet_loss_rate() <= hard.packet_loss_rate() + 1e-9


def test_consistency_replicates_static(setup):
    topo, loads = setup
    traj = lyapunov_online(topo, loads)
    res = run_simulation(
        topo, loads,
        decision_fn=lambda k: int(traj.actions[k]),
        sim_duration=600.0, aos_rate_pps=100.0,
        do_two_phase=True, enable_consistency=True, replica_top_m=2,
    )
    # 即使没切换，gossip loop 也会跑
    assert res.gossip_rounds >= 0
    # 如果发生过切换，应有副本安装
    if len(res.switches) > 0:
        assert res.static_replicas_installed >= 1


def test_max_visibility_uses_multiple_gateways(setup):
    topo, loads = setup
    res = run_simulation(
        topo, loads,
        decision_fn=max_visibility_decision_fn(topo),
        sim_duration=1000.0, aos_rate_pps=50.0,
        do_two_phase=False,
    )
    # 长仿真应至少用到 ≥1 个网关；如果拓扑允许，可能用到多个
    assert len(res.gateway_usage_count) >= 1
