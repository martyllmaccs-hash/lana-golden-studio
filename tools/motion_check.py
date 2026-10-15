#!/usr/bin/env python3
"""
Offline numeric check for the BRIEF-3 "motion 2x" pass: a numpy port of the
*dynamic* terms in studio/shaders/studio.frag (breathing beams, cloud
shadows, dust motes, floor sheen -- not the static day-grade LUT, which
tools/render_checks.py already covers) so the "is it actually more visible
now" question can be answered without a live GPU.

Not a pixel-perfect re-implementation (the 3x3 dust loop in particular is
reproduced in a vectorized form, not literally 9 shifted texture reads per
pixel), but every coefficient is copied verbatim from the shader so the
amplitude/rate math is the same. Renders two frames 5s apart at golden hour
(dayPhase=17, matching the P1 measurement in BRIEF-3), speed=1 (i.e. time
advances 1:1), motion=2.0 (new default), and reports the fraction of pixels
whose max-channel change exceeds 4/255 -- the same metric Martin's own
screenshot diff used. Target: >5%.

Usage: uv run --with pillow --with numpy python tools/motion_check.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "studio" / "assets"
OUT = ROOT / "checks"

# ---- grade LUT, copied from studio/shaders/studio.frag ----
ANCH_H     = [0.0,  5.0,  7.0,  12.0, 17.0, 19.5, 21.0, 24.0]
ANCH_TR    = [0.72, 0.72, 0.93, 1.00, 1.12, 1.08, 0.78, 0.72]
ANCH_TG    = [0.80, 0.80, 0.95, 1.00, 0.98, 0.82, 0.82, 0.80]
ANCH_TB    = [1.04, 1.04, 0.99, 1.00, 0.80, 0.78, 1.05, 1.04]
ANCH_EXP   = [0.44, 0.44, 0.80, 1.00, 1.06, 0.80, 0.52, 0.44]
ANCH_BEAM  = [0.20, 0.20, 0.68, 0.85, 1.00, 0.55, 0.28, 0.20]
ANCH_DUST  = [0.10, 0.10, 0.55, 0.78, 1.00, 0.68, 0.16, 0.10]
ANCH_NIGHT = [1.00, 1.00, 0.00, 0.00, 0.00, 0.40, 0.90, 1.00]


def smooth_t(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def grade_at(h):
    for i in range(len(ANCH_H) - 1):
        if ANCH_H[i] <= h <= ANCH_H[i + 1]:
            t = smooth_t((h - ANCH_H[i]) / (ANCH_H[i + 1] - ANCH_H[i]))
            lerp = lambda a: a[i] + (a[i + 1] - a[i]) * t
            tint = np.array([lerp(ANCH_TR), lerp(ANCH_TG), lerp(ANCH_TB)])
            return tint, lerp(ANCH_EXP), lerp(ANCH_BEAM), lerp(ANCH_DUST), lerp(ANCH_NIGHT)
    tint = np.array([ANCH_TR[0], ANCH_TG[0], ANCH_TB[0]])
    return tint, ANCH_EXP[0], ANCH_BEAM[0], ANCH_DUST[0], ANCH_NIGHT[0]


def _dot_yzx_plus(p3):
    # dot(p3, p3.yzx + 33.33) = p3.x*(p3.y+33.33) + p3.y*(p3.z+33.33) + p3.z*(p3.x+33.33)
    return (p3[..., 0] * (p3[..., 1] + 33.33) + p3[..., 1] * (p3[..., 2] + 33.33)
            + p3[..., 2] * (p3[..., 0] + 33.33))


def hash12(p):
    px, py = p[..., 0], p[..., 1]
    p3 = np.stack([px, py, px], axis=-1) * 0.1031
    p3 = p3 - np.floor(p3)
    p3 = p3 + _dot_yzx_plus(p3)[..., None]
    r = (p3[..., 0] + p3[..., 1]) * p3[..., 2]
    return r - np.floor(r)


def hash22(p):
    px, py = p[..., 0], p[..., 1]
    p3 = np.stack([px, py, px], axis=-1) * np.array([0.1031, 0.1030, 0.0973])
    p3 = p3 - np.floor(p3)
    p3 = p3 + _dot_yzx_plus(p3)[..., None]
    # fract((p3.xx + p3.yz) * p3.zy) -> component0: (p3.x+p3.y)*p3.z ; component1: (p3.x+p3.z)*p3.y
    c0 = (p3[..., 0] + p3[..., 1]) * p3[..., 2]
    c1 = (p3[..., 0] + p3[..., 2]) * p3[..., 1]
    out = np.stack([c0, c1], axis=-1)
    return out - np.floor(out)


def vnoise(p):
    i = np.floor(p)
    f = p - i
    a = hash12(i)
    b = hash12(i + np.array([1.0, 0.0]))
    c = hash12(i + np.array([0.0, 1.0]))
    d = hash12(i + np.array([1.0, 1.0]))
    u = f * f * (3.0 - 2.0 * f)
    ux, uy = u[..., 0], u[..., 1]
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm(p):
    v = np.zeros(p.shape[:-1], dtype=np.float32)
    amp = 0.55
    for _ in range(3):
        v = v + amp * vnoise(p)
        p = p * 2.03
        amp *= 0.5
    return v


def main():
    base = np.asarray(Image.open(ASSETS / "base.jpg").convert("RGB")).astype(np.float32) / 255.0
    light = np.asarray(Image.open(ASSETS / "light.png")).astype(np.float32) / 255.0
    floor = np.asarray(Image.open(ASSETS / "floor.png")).astype(np.float32) / 255.0
    windows = np.asarray(Image.open(ASSETS / "windows.png")).astype(np.float32) / 255.0
    air = np.asarray(Image.open(ASSETS / "air.png")).astype(np.float32) / 255.0

    H, W, _ = base.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    uv = np.stack([xx / (W - 1), yy / (H - 1)], axis=-1)
    aspect = W / H
    auv = uv.copy()
    auv[..., 0] *= aspect

    day_phase = 17.0
    motion = 2.0

    def frame(time):
        tint, exposure, beam_mul, dust_mul, night_blue = grade_at(day_phase)
        base_lum = 0.299 * base[..., 0] + 0.587 * base[..., 1] + 0.114 * base[..., 2]
        col = base.copy()

        # ---- 1. breathing light shafts ----
        light_dir = np.array([1.0, 0.35], dtype=np.float32)
        light_dir = light_dir / np.linalg.norm(light_dir)
        shimmer = fbm(auv * 3.1 - light_dir * (time * 0.040))
        breathe = 0.78 + 0.34 * shimmer
        ray_src = np.array([-0.05 * aspect, 0.08], dtype=np.float32)
        toP = auv - ray_src
        ang = np.arctan2(toP[..., 1], toP[..., 0])
        ray_sweep = np.radians(4.0) * np.sin(time * 0.015)
        ang_s = ang + ray_sweep
        ray0 = 1.0 - smooth_t((np.abs(np.sin((ang_s - 0.28) * 7.0 + time * 0.06)) - 0.0) / 0.32)
        ray1 = 1.0 - smooth_t((np.abs(np.sin((ang_s - 0.55) * 9.0 - time * 0.044)) - 0.0) / 0.27)
        rays = (ray0 + 0.7 * ray1) * smooth_t(light / 0.5)
        beam_strength = (0.65 * breathe + 0.5 * rays) * light * beam_mul
        beam_color = (1 - night_blue) * np.array([1.0, 0.93, 0.78]) + night_blue * np.array([0.80, 0.88, 1.0])
        beam_atten = (1.0 - base_lum) ** 2
        col = col + beam_color * (beam_strength * 0.22 * motion * beam_atten)[..., None]

        # ---- 2. cloud shadows ----
        cloud_dir = np.array([1.0, 0.18], dtype=np.float32)
        cloud_dir = cloud_dir / np.linalg.norm(cloud_dir)
        cloud_period = 30.0
        cloud = fbm(auv * 1.15 - cloud_dir * (time / cloud_period) * 1.4 + 11.0)
        cloud_shadow = np.minimum(smooth_t((cloud - 0.42) / 0.20) * 0.10 * motion, 0.6)
        col = col * (1.0 - cloud_shadow)[..., None]

        # ---- 3. dust motes (vectorized 3x3 cell loop) ----
        grid = np.array([14.0, 8.0], dtype=np.float32)
        cell0 = np.floor(uv * grid)
        dust = np.zeros((H, W), dtype=np.float32)
        twinkle_boost = 1.0  # sig == 0 away from the once-per-4-minutes signature moment
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                cell = cell0 + np.array([dx, dy], dtype=np.float32)
                seed = hash22(cell + 0.5)
                seed_x, seed_y = seed[..., 0], seed[..., 1]
                rise_speed = 0.020 + seed_x * 0.024
                y_local = (seed_y + time * rise_speed) % 1.0
                wander_phase = seed_x * 62.831853
                wx = 0.30 * np.sin(time * (0.10 + 0.08 * seed_y) + wander_phase)
                mote_u = (cell[..., 0] + 0.5 + wx) / grid[0]
                mote_v = (cell[..., 1] + (1.0 - y_local)) / grid[1]
                d0 = uv[..., 0] - mote_u
                d1 = uv[..., 1] - mote_v
                d0 = d0 * aspect
                size_hash = hash12(cell + 3.3)
                size_mul = np.where(size_hash > 0.80, 1.6 + (3.0 - 1.6) * (size_hash - 0.80) / 0.20, 1.0)
                size = (0.0016 + (0.0040 - 0.0016) * seed_y) * size_mul
                fall = np.exp(-(d0 * d0 + d1 * d1) / (size * size))
                twinkle = (0.55 + 0.45 * np.sin(time * (1.3 + seed_x * 1.6) + wander_phase)) * twinkle_boost
                twinkle = twinkle * np.where(size_mul > 1.0, 0.7, 1.0)
                dust = dust + fall * twinkle
        dust = np.minimum(dust, 1.4)
        mote_color = (1 - night_blue) * np.array([1.0, 0.86, 0.55]) + night_blue * np.array([0.75, 0.82, 0.95])
        col = col + mote_color * (dust * air * dust_mul * 0.55 * motion)[..., None]

        # ---- 4. floor sheen ----
        streak_dir = np.array([1.0, 0.22], dtype=np.float32)
        streak_dir = streak_dir / np.linalg.norm(streak_dir)
        sheen_wave = 0.5 + 0.5 * np.sin((auv[..., 0] * streak_dir[0] + auv[..., 1] * streak_dir[1]) * 26.0 - time * 0.24)
        sparkle = hash12(np.floor(auv * 180.0) + np.floor(time * 0.6))
        sheen = floor * (0.5 * sheen_wave + 0.5 * smooth_t((sparkle - 0.88) / 0.12))
        col = col + np.array([1.0, 0.94, 0.80]) * (sheen * 0.05 * beam_mul * motion)[..., None]

        # ---- 5. static day grade ----
        col = col * tint
        col = col * exposure
        col = col * (1.0 - night_blue * floor * 0.35)[..., None]
        moon_glow = np.array([0.55, 0.68, 0.95]) * (windows * night_blue * 0.30)[..., None]
        her_glow = np.array([1.0, 0.82, 0.58]) * (light * night_blue * 0.085)[..., None]
        col = col + moon_glow + her_glow

        return np.clip(col, 0.0, 1.0)

    f0 = frame(0.0)
    f1 = frame(5.0)  # speed=1 => 5 real seconds = +5.0 to `time`

    diff = np.abs(f1 - f0).max(axis=-1) * 255.0
    pct_changed = float((diff > 4.0).mean()) * 100.0
    print(f"golden hour (dayPhase={day_phase}), speed=1, motion={motion}:")
    print(f"  pixels changed >4/255 over 5s: {pct_changed:.2f}%  (target: >5%)")
    print(f"  mean abs diff: {diff.mean():.3f}/255   max: {diff.max():.1f}/255")
    print(f"  {'PASS' if pct_changed > 5.0 else 'FAIL'}")

    OUT.mkdir(exist_ok=True)
    Image.fromarray((f0 * 255).astype(np.uint8)).save(OUT / "motion-check-t0.jpg", quality=92)
    Image.fromarray((f1 * 255).astype(np.uint8)).save(OUT / "motion-check-t5.jpg", quality=92)
    diff_u8 = np.clip(diff * 4, 0, 255).astype(np.uint8)  # 4x boosted for visibility
    Image.fromarray(diff_u8, mode="L").save(OUT / "motion-check-diff.png")
    print(f"Wrote checks/motion-check-{{t0,t5,diff}} for visual inspection.")


if __name__ == "__main__":
    main()
