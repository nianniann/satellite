"""
基于 Skyfield + 真实 TLE 数据的卫星轨道仿真。

提供：
- 加载/缓存 CelesTrak 的 Starlink / Iridium TLE
- 计算任意时刻两颗卫星间的星间距离、相对仰角、可见性
- 解析星历得出未来 ΔT 秒的可见性窗口
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from skyfield.api import EarthSatellite, load, wgs84
from skyfield.timelib import Time

from config import CFG, EARTH_RADIUS_KM, SPEED_OF_LIGHT_KMS, TLE_DIR


CELESTRAK_URLS = {
    "starlink": "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle",
    "iridium": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium&FORMAT=tle",
    "iridium-next": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-NEXT&FORMAT=tle",
    "active": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
}


# 备用合成 TLE（无网络时使用）。覆盖 Starlink-like 与 Iridium-like 两类轨道。
# epoch=2024-01-01 00:00:00 UTC
_FALLBACK_TLE = """STARLINK-SIM-1
1 90001U 24001A   24001.00000000  .00000000  00000-0  00000-0 0  9999
2 90001  53.0000   0.0000 0001000   0.0000   0.0000 15.06000000    01
STARLINK-SIM-2
1 90002U 24001B   24001.00000000  .00000000  00000-0  00000-0 0  9998
2 90002  53.0000  45.0000 0001000  10.0000  20.0000 15.06000000    02
STARLINK-SIM-3
1 90003U 24001C   24001.00000000  .00000000  00000-0  00000-0 0  9997
2 90003  53.0000  90.0000 0001000  20.0000  40.0000 15.06000000    03
STARLINK-SIM-4
1 90004U 24001D   24001.00000000  .00000000  00000-0  00000-0 0  9996
2 90004  53.0000 135.0000 0001000  30.0000  60.0000 15.06000000    04
STARLINK-SIM-5
1 90005U 24001E   24001.00000000  .00000000  00000-0  00000-0 0  9995
2 90005  53.0000 180.0000 0001000  40.0000  80.0000 15.06000000    05
STARLINK-SIM-6
1 90006U 24001F   24001.00000000  .00000000  00000-0  00000-0 0  9994
2 90006  53.0000 225.0000 0001000  50.0000 100.0000 15.06000000    06
STARLINK-SIM-7
1 90007U 24001G   24001.00000000  .00000000  00000-0  00000-0 0  9993
2 90007  53.0000 270.0000 0001000  60.0000 120.0000 15.06000000    07
STARLINK-SIM-8
1 90008U 24001H   24001.00000000  .00000000  00000-0  00000-0 0  9992
2 90008  53.0000 315.0000 0001000  70.0000 140.0000 15.06000000    08
AOS-SIM-1
1 91001U 24002A   24001.00000000  .00000000  00000-0  00000-0 0  9999
2 91001  97.5000   0.0000 0001000  30.0000   0.0000 14.50000000    01
AOS-SIM-2
1 91002U 24002B   24001.00000000  .00000000  00000-0  00000-0 0  9998
2 91002  97.5000  60.0000 0001000  60.0000  30.0000 14.50000000    02
"""


@dataclass
class Satellite:
    """对 EarthSatellite 的轻封装，记录名字、NORAD ID、role。"""
    name: str
    sat: EarthSatellite
    role: str = "unknown"  # 'aos' 或 'ipv6_gateway'

    @property
    def norad_id(self) -> int:
        return self.sat.model.satnum


# --------------------------- TLE 下载 / 缓存 ---------------------------
def download_tle(group: str = "starlink", force: bool = False) -> Path:
    fp = TLE_DIR / f"{group}.tle"
    if fp.exists() and not force:
        return fp
    if group not in CELESTRAK_URLS:
        raise ValueError(f"未知 TLE 分组：{group}")
    try:
        print(f"[orbit] 下载 {group} TLE 中 ...")
        r = requests.get(CELESTRAK_URLS[group], timeout=15)
        r.raise_for_status()
        fp.write_text(r.text)
        print(f"[orbit] 已写入 {fp}")
        return fp
    except Exception as e:
        print(f"[orbit] 下载失败（{e}），将使用内置合成 TLE。")
        fp = TLE_DIR / "fallback.tle"
        fp.write_text(_FALLBACK_TLE)
        return fp


def load_satellites_from_file(fp: Path, limit: Optional[int] = None,
                              role: str = "unknown") -> list[Satellite]:
    ts = load.timescale()
    sats = []
    lines = fp.read_text().strip().splitlines()
    i = 0
    while i + 2 < len(lines) + 1:
        if i + 2 >= len(lines):
            break
        name = lines[i].strip()
        l1 = lines[i + 1].strip()
        l2 = lines[i + 2].strip()
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            i += 1
            continue
        try:
            sat = EarthSatellite(l1, l2, name, ts)
            sats.append(Satellite(name=name, sat=sat, role=role))
        except Exception:
            pass
        i += 3
        if limit and len(sats) >= limit:
            break
    return sats


def build_scenario(num_gateways: int = None,
                   num_aos: int = None,
                   use_fallback: bool = False) -> tuple[list[Satellite], list[Satellite]]:
    """
    返回 (aos_sats, gateway_sats)。
    - num_gateways: IPv6 网关数量；num_aos: AOS 卫星数量
    - use_fallback=True 时直接使用内置合成 TLE，避免联网
    """
    num_gateways = num_gateways or CFG.num_candidate_gateways
    num_aos = num_aos or CFG.num_aos_satellites

    if use_fallback:
        # 用程序生成的合成星座（轨道多样性比内置 _FALLBACK_TLE 更丰富）
        from orbit.synth_constellation import generate_constellation
        fb = TLE_DIR / "fallback.tle"
        tle_str = generate_constellation(num_gateways=max(num_gateways, 10))
        fb.write_text(tle_str)
        all_sats = load_satellites_from_file(fb)
        gw = [s for s in all_sats if s.name.startswith("IPV6-GW")][:num_gateways]
        aos = [s for s in all_sats if s.name.startswith("AOS")][:num_aos]
        for s in gw:
            s.role = "ipv6_gateway"
        for s in aos:
            s.role = "aos"
        return aos, gw

    # 真实数据：所有卫星均来自 Starlink，AOS 与网关都是星上节点（典型 LEO ISL 拓扑）
    # 为保证可见性丰富，AOS 与网关都用 Starlink，但 AOS 取较前的卫星，
    # 网关从全文件均匀抽样以覆盖不同轨道面。
    try:
        sl_fp = download_tle("starlink")
        all_sl = load_satellites_from_file(sl_fp, role="ipv6_gateway")
        if len(all_sl) < num_gateways + num_aos:
            raise RuntimeError("Starlink TLE 数量不足")
        # 候选网关：从整个 Starlink TLE 等间距抽样，覆盖不同轨道面
        stride_sl = max(1, len(all_sl) // num_gateways)
        gw = [all_sl[i * stride_sl] for i in range(num_gateways)]
        # AOS 卫星：选中间偏后的卫星，避免与网关重合
        aos_start = len(all_sl) // 2
        aos = []
        for i in range(num_aos):
            cand = all_sl[(aos_start + i * 17) % len(all_sl)]
            cand = Satellite(name=f"AOS-{cand.name}", sat=cand.sat, role="aos")
            aos.append(cand)
        return aos, gw
    except Exception as e:
        print(f"[orbit] 真实 TLE 加载失败 ({e})，切换到 fallback")
        return build_scenario(num_gateways, num_aos, use_fallback=True)


# --------------------------- 几何计算 ---------------------------
def _sat_position_km(sat: EarthSatellite, t: Time) -> np.ndarray:
    """返回地心惯性坐标（km）。"""
    geocentric = sat.at(t)
    return np.array(geocentric.position.km)


def distance_km(sat_a: Satellite, sat_b: Satellite, t: Time) -> float:
    pa = _sat_position_km(sat_a.sat, t)
    pb = _sat_position_km(sat_b.sat, t)
    return float(np.linalg.norm(pa - pb))


def elevation_deg(sat_aos: Satellite, sat_gw: Satellite, t: Time) -> float:
    """
    ISL 几何：返回两星连线相对"切线方向"的余隙角（grazing angle）。
    正值 = 连线高于地平切面（LOS 通畅）；负值 = 连线穿过地球。
    这是星间链路标准做法，与"地面站仰角"不同。
    """
    pa = _sat_position_km(sat_aos.sat, t)
    pb = _sat_position_km(sat_gw.sat, t)
    ra = float(np.linalg.norm(pa))
    rb = float(np.linalg.norm(pb))
    d = float(np.linalg.norm(pa - pb))
    if d < 1e-9:
        return 90.0
    # AOS 视线与其地心矢量的夹角（cos）
    cos_alpha = float(np.dot(pa, pb - pa)) / (ra * d)
    cos_alpha = max(-1.0, min(1.0, cos_alpha))
    # AOS 处的"地平切线"与视线夹角
    grazing_a = 90.0 - math.degrees(math.acos(cos_alpha))
    # 对 B 同样
    cos_beta = float(np.dot(pb, pa - pb)) / (rb * d)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    grazing_b = 90.0 - math.degrees(math.acos(cos_beta))
    # 取两端最小余隙，决定是否被地球挡住
    return min(grazing_a, grazing_b)


def has_line_of_sight(sat_a: Satellite, sat_b: Satellite, t: Time,
                      atmos_clearance_km: float = 100.0) -> bool:
    """
    判断两星之间连线是否被地球（+大气层）挡住。
    几何法：连线到地心的最近点距离 > R_earth + clearance。
    """
    pa = _sat_position_km(sat_a.sat, t)
    pb = _sat_position_km(sat_b.sat, t)
    ab = pb - pa
    L2 = float(np.dot(ab, ab))
    if L2 < 1e-9:
        return True
    # 投影系数 t* = -pa·ab / |ab|^2；若不在 [0,1] 则最近点在端点之外
    t_star = -float(np.dot(pa, ab)) / L2
    if 0.0 <= t_star <= 1.0:
        closest = pa + t_star * ab
        min_dist = float(np.linalg.norm(closest))
    else:
        min_dist = min(float(np.linalg.norm(pa)), float(np.linalg.norm(pb)))
    return min_dist > (EARTH_RADIUS_KM + atmos_clearance_km)


def is_visible(sat_aos: Satellite, sat_gw: Satellite, t: Time,
               max_range_km: float = None) -> bool:
    """ISL 可见性 = 距离不超限 AND 视线不被地球挡。"""
    max_range_km = max_range_km if max_range_km is not None else CFG.isl_max_range_km
    if distance_km(sat_aos, sat_gw, t) > max_range_km:
        return False
    return has_line_of_sight(sat_aos, sat_gw, t)


def predict_visibility_window(sat_aos: Satellite, sat_gw: Satellite,
                              t_start: Time, horizon_sec: float,
                              step_sec: float = 5.0) -> tuple[float, float]:
    """
    从 t_start 起步进采样，预测对网关 gw 的剩余可见时长 ΔT。
    返回 (delta_T_seconds, mean_elevation_deg)。
    """
    ts = load.timescale()
    n = int(horizon_sec / step_sec) + 1
    t0_utc = t_start.utc_datetime()
    elevs = []
    visible_until = 0.0
    currently_visible = is_visible(sat_aos, sat_gw, t_start)

    for k in range(n):
        sec = k * step_sec
        t_k = ts.utc(t0_utc.year, t0_utc.month, t0_utc.day,
                     t0_utc.hour, t0_utc.minute, t0_utc.second + sec)
        elev = elevation_deg(sat_aos, sat_gw, t_k)
        vis_k = is_visible(sat_aos, sat_gw, t_k)
        elevs.append(elev if vis_k else 0.0)

        if currently_visible and vis_k:
            visible_until = sec
        elif currently_visible and not vis_k:
            break
        elif not currently_visible and vis_k:
            # 当前不可见，未来要进入可见窗的话不算"剩余"
            break

    mean_elev = float(np.mean([e for e in elevs if e > 0])) if any(e > 0 for e in elevs) else 0.0
    return visible_until if currently_visible else 0.0, mean_elev


def isl_bandwidth_mbps(distance_km: float) -> float:
    """
    简化的 ISL 带宽模型：随距离线性递减。
    短距离接近最大带宽，远距离衰减到最小。
    """
    d_min, d_max = 500.0, CFG.isl_max_range_km
    b_min, b_max = CFG.isl_bandwidth_min_mbps, CFG.isl_bandwidth_max_mbps
    if distance_km <= d_min:
        return b_max
    if distance_km >= d_max:
        return b_min
    frac = (distance_km - d_min) / (d_max - d_min)
    return b_max - frac * (b_max - b_min)


def propagation_delay_ms(distance_km: float) -> float:
    return distance_km / SPEED_OF_LIGHT_KMS * 1000.0


# --------------------------- 自检 ---------------------------
if __name__ == "__main__":
    aos, gws = build_scenario(use_fallback=True)
    print(f"[orbit] 载入 {len(aos)} 颗 AOS 卫星, {len(gws)} 颗 IPv6 网关")
    ts = load.timescale()
    t0 = ts.utc(2024, 1, 1, 0, 0, 0)
    for gw in gws:
        d = distance_km(aos[0], gw, t0)
        e = elevation_deg(aos[0], gw, t0)
        v = is_visible(aos[0], gw, t0)
        dT, me = predict_visibility_window(aos[0], gw, t0, horizon_sec=600)
        b = isl_bandwidth_mbps(d)
        print(f"  {aos[0].name} -> {gw.name}: d={d:7.1f}km elev={e:6.2f}° "
              f"vis={v} ΔT={dT:5.1f}s B={b:5.1f}Mbps")
