"""
合成星座生成器：当真实 TLE 不可获取时，生成一个轨道多样性足够的合成星座，
保证测试场景中 AOS 卫星会穿过 5-10 个不同 IPv6 网关的可见窗口。

设计：
  - AOS 卫星：1 颗，极地圆轨道（i≈97°），高度 ~500km
  - IPv6 网关：N 颗，分布在多个 RAAN 与 inclination 的"网格"上，
    高度 ~550km，确保 AOS 在半小时内能"换星"3-5 次。
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from skyfield.api import EarthSatellite, load


# TLE 字段写入：使用 SGP4 兼容的格式
def _checksum(line: str) -> str:
    s = 0
    for ch in line[:68]:
        if ch.isdigit():
            s += int(ch)
        elif ch == "-":
            s += 1
    return str(s % 10)


def _format_tle_line1(satnum: int, epoch_year: int, epoch_day: float) -> str:
    """简化的 line1，几乎全零。"""
    year2 = epoch_year % 100
    line = f"1 {satnum:05d}U 24001A   {year2:02d}{epoch_day:012.8f}  .00000000  00000-0  00000-0 0  999"
    return line[:68] + _checksum(line)


def _format_tle_line2(satnum: int, inclination_deg: float, raan_deg: float,
                      ecc: float, argp_deg: float, mean_anom_deg: float,
                      mean_motion_revs_per_day: float, rev_num: int = 1) -> str:
    ecc_str = f"{int(round(ecc * 1e7)):07d}"
    line = (
        f"2 {satnum:05d} {inclination_deg:8.4f} {raan_deg:8.4f} {ecc_str} "
        f"{argp_deg:8.4f} {mean_anom_deg:8.4f} {mean_motion_revs_per_day:11.8f}{rev_num:5d}"
    )
    return line[:68] + _checksum(line)


def altitude_to_mean_motion(altitude_km: float) -> float:
    """开普勒第三定律：T = 2π√(a³/μ)，n = revs/day。"""
    mu = 398600.4418  # km^3/s^2
    a_km = 6371.0 + altitude_km
    T_sec = 2 * math.pi * math.sqrt(a_km ** 3 / mu)
    return 86400.0 / T_sec


def generate_constellation(num_gateways: int = 10,
                           gateway_altitude_km: float = 1200.0,
                           aos_altitude_km: float = 380.0,
                           epoch_year: int = 2024,
                           epoch_day: float = 1.0,
                           seed: int = 0) -> str:
    """
    生成合成 TLE 字符串。返回多颗卫星的 TLE 拼接。

    为获得丰富的相对运动 (handover 频繁)：
      AOS 在极低 LEO（高度差大 → 周期差大 → 相对漂移快）
      网关在较高 LEO，inclination/RAAN 分散覆盖
    """
    lines = []
    rng = np.random.default_rng(seed)

    # 1) AOS 卫星：低 LEO、近极地
    n_aos = altitude_to_mean_motion(aos_altitude_km)
    lines += ["AOS-SIM-1",
              _format_tle_line1(91001, epoch_year, epoch_day),
              _format_tle_line2(91001, inclination_deg=87.0,
                                raan_deg=0.0, ecc=0.0001,
                                argp_deg=0.0, mean_anom_deg=0.0,
                                mean_motion_revs_per_day=n_aos)]

    # 2) IPv6 网关：较高 LEO，混合多个 inclination 与 RAAN
    n_gw = altitude_to_mean_motion(gateway_altitude_km)
    inclinations = [53.0, 75.0, 87.5]
    # 把 num_gateways 划分到 (inclination × RAAN 网格)
    per_inc = max(1, num_gateways // len(inclinations) + 1)
    sat_id = 90001
    count = 0
    for inc in inclinations:
        for k in range(per_inc):
            if count >= num_gateways:
                break
            raan = (k * (360.0 / per_inc) + inc * 7.0) % 360.0
            mean_anom = (k * 137.508 + inc * 13.0) % 360.0
            lines += [f"IPV6-GW-{sat_id - 90000:02d}",
                      _format_tle_line1(sat_id, epoch_year, epoch_day),
                      _format_tle_line2(sat_id, inclination_deg=inc,
                                        raan_deg=raan, ecc=0.0001,
                                        argp_deg=0.0, mean_anom_deg=mean_anom,
                                        mean_motion_revs_per_day=n_gw)]
            sat_id += 1
            count += 1
        if count >= num_gateways:
            break

    return "\n".join(lines) + "\n"


def validate_tle_string(tle_str: str) -> int:
    """用 Skyfield 解析以验证 TLE 合法性。返回成功解析的卫星数。"""
    ts = load.timescale()
    lines = tle_str.strip().splitlines()
    ok = 0
    i = 0
    while i + 2 < len(lines) + 1:
        if i + 2 >= len(lines):
            break
        try:
            EarthSatellite(lines[i + 1], lines[i + 2], lines[i], ts)
            ok += 1
        except Exception as e:
            print(f"  TLE parse error @ {lines[i]}: {e}")
        i += 3
    return ok


if __name__ == "__main__":
    s = generate_constellation(num_gateways=12)
    n_ok = validate_tle_string(s)
    print(f"Generated {n_ok} satellites")
    print(s[:600])
