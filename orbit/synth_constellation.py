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
                           gateway_altitude_km: float = 550.0,
                           aos_altitude_km: float = 400.0,
                           epoch_year: int = 2024,
                           epoch_day: float = 1.0,
                           seed: int = 0) -> str:
    """
    生成合成 TLE 字符串。返回多颗卫星的 TLE 拼接。

    目标：30 分钟仿真窗口里产生 8-20 次切换机会。
    设计：
      - AOS 在 ~400km（类 ISS 高度）低 LEO，i=51.6°
      - 网关在 ~550km（类 Starlink 一壳）LEO，i=53°
      - 高度差 ~150km → AOS 比网关每圈快 ~3 分钟 → 相对漂移快
      - 网关分布在 ``num_gateways`` 个不同 RAAN 上，使 AOS sweep 时依次进入视场
      - 每个轨道面再放 1 颗相位错开的卫星，触发同面内的"换星"
    """
    lines = []

    # 1) AOS 卫星：极地轨道，与 i=53° 的网关面有较大角差 → 持续穿越多个网关视场
    n_aos = altitude_to_mean_motion(aos_altitude_km)
    lines += ["AOS-SIM-1",
              _format_tle_line1(91001, epoch_year, epoch_day),
              _format_tle_line2(91001, inclination_deg=87.0,
                                raan_deg=45.0, ecc=0.0001,
                                argp_deg=0.0, mean_anom_deg=0.0,
                                mean_motion_revs_per_day=n_aos)]

    # 2) 网关：RAAN 等间距填满 360°
    n_gw_rev = altitude_to_mean_motion(gateway_altitude_km)
    sat_id = 90001
    for k in range(num_gateways):
        raan = (k * (360.0 / num_gateways)) % 360.0
        # 相邻 RAAN 上的卫星相位错开 180°/N，提高短期内的可见多样性
        mean_anom = (k * (180.0 / max(1, num_gateways))) % 360.0
        lines += [f"IPV6-GW-{sat_id - 90000:02d}",
                  _format_tle_line1(sat_id, epoch_year, epoch_day),
                  _format_tle_line2(sat_id, inclination_deg=53.0,
                                    raan_deg=raan, ecc=0.0001,
                                    argp_deg=0.0, mean_anom_deg=mean_anom,
                                    mean_motion_revs_per_day=n_gw_rev)]
        sat_id += 1

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
