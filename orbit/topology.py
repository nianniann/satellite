"""
时变拓扑：批量计算 AOS 卫星与所有候选 IPv6 网关在采样网格上的状态张量。
缓存到 .npz 避免重复重算。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from skyfield.api import load
from tqdm import tqdm

from config import CFG, DATA_DIR
from orbit.skyfield_sim import (
    Satellite, build_scenario,
    distance_km, elevation_deg, is_visible,
    isl_bandwidth_mbps, propagation_delay_ms,
)


@dataclass
class TopologySnapshot:
    """单个 AOS 卫星对所有候选网关的时变状态张量。"""
    times_sec: np.ndarray              # (T,) 仿真起点起的秒数
    epoch_utc: datetime                # 仿真起点 UTC
    distance_km: np.ndarray            # (T, N)
    elevation_deg: np.ndarray          # (T, N)
    visible: np.ndarray                # (T, N) bool
    isl_bw_mbps: np.ndarray            # (T, N)
    prop_delay_ms: np.ndarray          # (T, N)
    gateway_names: list[str]
    aos_name: str

    @property
    def num_gateways(self) -> int:
        return len(self.gateway_names)

    @property
    def num_steps(self) -> int:
        return len(self.times_sec)

    def remaining_visibility(self, t_idx: int) -> np.ndarray:
        """
        从 t_idx 出发，每个网关的剩余连续可见时长（秒）。
        若 t_idx 时刻不可见，则为 0。
        """
        dt = float(self.times_sec[1] - self.times_sec[0])
        N = self.num_gateways
        rem = np.zeros(N, dtype=float)
        for j in range(N):
            if not self.visible[t_idx, j]:
                continue
            k = t_idx
            while k < self.num_steps and self.visible[k, j]:
                k += 1
            rem[j] = (k - t_idx) * dt
        return rem

    def save(self, fp: Path):
        np.savez_compressed(
            fp,
            times_sec=self.times_sec,
            epoch_utc=np.array(self.epoch_utc.isoformat()),
            distance_km=self.distance_km,
            elevation_deg=self.elevation_deg,
            visible=self.visible,
            isl_bw_mbps=self.isl_bw_mbps,
            prop_delay_ms=self.prop_delay_ms,
            gateway_names=np.array(self.gateway_names),
            aos_name=np.array(self.aos_name),
        )

    @staticmethod
    def load(fp: Path) -> "TopologySnapshot":
        data = np.load(fp, allow_pickle=False)
        return TopologySnapshot(
            times_sec=data["times_sec"],
            epoch_utc=datetime.fromisoformat(str(data["epoch_utc"])),
            distance_km=data["distance_km"],
            elevation_deg=data["elevation_deg"],
            visible=data["visible"],
            isl_bw_mbps=data["isl_bw_mbps"],
            prop_delay_ms=data["prop_delay_ms"],
            gateway_names=list(data["gateway_names"]),
            aos_name=str(data["aos_name"]),
        )


def compute_topology(aos: Satellite, gateways: list[Satellite],
                     duration_sec: float,
                     step_sec: float = 1.0,
                     epoch_utc: Optional[datetime] = None,
                     show_progress: bool = True) -> TopologySnapshot:
    """以 step_sec 步长采样，得到 AOS↔每个网关 的几何/链路状态张量。"""
    ts = load.timescale()
    if epoch_utc is None:
        epoch_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    n_steps = int(duration_sec / step_sec) + 1
    n_gw = len(gateways)
    times_sec = np.arange(n_steps, dtype=float) * step_sec

    D = np.zeros((n_steps, n_gw), dtype=float)
    E = np.zeros((n_steps, n_gw), dtype=float)
    V = np.zeros((n_steps, n_gw), dtype=bool)
    B = np.zeros((n_steps, n_gw), dtype=float)
    P = np.zeros((n_steps, n_gw), dtype=float)

    iterator = range(n_steps)
    if show_progress:
        iterator = tqdm(iterator, desc=f"topology({aos.name})")

    for k in iterator:
        sec_offset = times_sec[k]
        t_k_utc = epoch_utc + timedelta(seconds=float(sec_offset))
        t_k = ts.utc(t_k_utc.year, t_k_utc.month, t_k_utc.day,
                     t_k_utc.hour, t_k_utc.minute,
                     t_k_utc.second + t_k_utc.microsecond * 1e-6)
        for j, gw in enumerate(gateways):
            d = distance_km(aos, gw, t_k)
            e = elevation_deg(aos, gw, t_k)
            v = is_visible(aos, gw, t_k)
            D[k, j] = d
            E[k, j] = e
            V[k, j] = v
            B[k, j] = isl_bandwidth_mbps(d) if v else 0.0
            P[k, j] = propagation_delay_ms(d)

    return TopologySnapshot(
        times_sec=times_sec, epoch_utc=epoch_utc,
        distance_km=D, elevation_deg=E, visible=V,
        isl_bw_mbps=B, prop_delay_ms=P,
        gateway_names=[g.name for g in gateways],
        aos_name=aos.name,
    )


def get_or_build_topology(cache_name: str,
                          duration_sec: float,
                          step_sec: float = 1.0,
                          use_fallback_tle: bool = False,
                          force: bool = False) -> tuple[TopologySnapshot, list[Satellite], list[Satellite]]:
    cache_fp = DATA_DIR / f"topo_{cache_name}.npz"
    aos_list, gws = build_scenario(use_fallback=use_fallback_tle)

    if cache_fp.exists() and not force:
        topo = TopologySnapshot.load(cache_fp)
        # 简单一致性校验
        if (topo.num_gateways == len(gws)
                and abs(topo.times_sec[-1] - duration_sec) < step_sec * 2):
            return topo, aos_list, gws

    topo = compute_topology(aos_list[0], gws, duration_sec, step_sec)
    topo.save(cache_fp)
    return topo, aos_list, gws


if __name__ == "__main__":
    topo, aos, gws = get_or_build_topology(
        cache_name="smoke",
        duration_sec=600.0,
        step_sec=2.0,
        use_fallback_tle=True,
    )
    print(f"shape: D={topo.distance_km.shape} V={topo.visible.shape}")
    print(f"avg visibility per gateway: {topo.visible.mean(axis=0)}")
    print(f"avg distance (km): {topo.distance_km.mean(axis=0)}")
    print(f"remaining visibility @t=0: {topo.remaining_visibility(0)}")
