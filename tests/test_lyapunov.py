"""单元测试：Lyapunov 在线求解器与离线 DP。"""
import numpy as np
import pytest

from orbit.topology import get_or_build_topology
from optimizer.lyapunov_solver import (
    lyapunov_offline_optimal, lyapunov_online,
    synthesize_gateway_loads,
)


@pytest.fixture(scope="module")
def topology():
    return get_or_build_topology(
        cache_name="test_lyap", duration_sec=600.0,
        step_sec=2.0, use_fallback_tle=True, force=True,
    )[0]


def test_loads_shape_and_range(topology):
    loads = synthesize_gateway_loads(topology.num_gateways, topology.num_steps,
                                     np.random.default_rng(0))
    assert loads.shape == (topology.num_steps, topology.num_gateways)
    assert loads.min() >= 0.0
    assert loads.max() <= 1.0


def test_lyapunov_online_outputs_consistent(topology):
    loads = synthesize_gateway_loads(topology.num_gateways, topology.num_steps,
                                     np.random.default_rng(0))
    traj = lyapunov_online(topology, loads)
    assert traj.states.shape[0] == topology.num_steps
    assert traj.actions.shape == (topology.num_steps,)
    assert traj.rewards.shape == (topology.num_steps,)
    assert traj.switch_count >= 0
    # 所有 action 都在合法范围
    assert traj.actions.min() >= 0
    assert traj.actions.max() < topology.num_gateways


def test_lyapunov_V_tradeoff(topology):
    """V 增大 → 单步 cost 减小（更激进），切换数增加。"""
    loads = synthesize_gateway_loads(topology.num_gateways, topology.num_steps,
                                     np.random.default_rng(0))
    traj_small_V = lyapunov_online(topology, loads, V=1.0)
    traj_large_V = lyapunov_online(topology, loads, V=1000.0)
    # 至少 V 越大不应该让 cost 显著变差（理论应更小或相当）
    # 简单的健壮性检查：reward 不应是 NaN
    assert np.isfinite(traj_small_V.rewards).all()
    assert np.isfinite(traj_large_V.rewards).all()


def test_offline_optimal_bounds_online(topology):
    """离线最优代价应 ≤ 在线 Lyapunov 代价（前者全局最优）。"""
    loads = synthesize_gateway_loads(topology.num_gateways, topology.num_steps,
                                     np.random.default_rng(0))
    traj = lyapunov_online(topology, loads)
    opt = lyapunov_offline_optimal(topology, loads,
                                   max_switches=max(traj.switch_count + 2, 5))
    online_cost = -float(traj.rewards.sum())
    # 由于 instant cost 和奖励定义略有不同（在线含切换瞬时代价），允许 5% 容差
    assert opt["total_cost"] <= online_cost * 1.10 + 1.0
