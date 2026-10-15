#!/usr/bin/env python3
"""
Offline sanity check (not a full shader reimplementation -- optional per the
brief). Applies the shader's static color-grade LUT (gradeAt in
studio/shaders/studio.frag) plus a flat overlay of the light/floor/windows
masks to the base photo, for three times of day. This verifies: the masks
align with the photo, the day-phase grade anchors produce sane/tasteful
colors, and nothing here can warp the image (every operation is per-pixel,
same grid as the source -- no UV displacement).

Usage: uv run --with pillow --with numpy python tools/render_checks.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "studio" / "assets"
OUT = ROOT / "checks"

# Mirrors ANCH_* tables in studio/shaders/studio.frag
ANCH_H     = [0.0,  5.0,  7.0,  12.0, 17.0, 19.5, 21.0, 24.0]
ANCH_TR    = [0.72, 0.72, 0.93, 1.00, 1.12, 1.08, 0.78, 0.72]
ANCH_TG    = [0.80, 0.80, 0.95, 1.00, 0.98, 0.82, 0.82, 0.80]
ANCH_TB    = [1.04, 1.04, 0.99, 1.00, 0.80, 0.78, 1.05, 1.04]
ANCH_EXP   = [0.44, 0.44, 0.80, 1.00, 1.06, 0.80, 0.52, 0.44]
ANCH_BEAM  = [0.20, 0.20, 0.68, 0.85, 1.00, 0.55, 0.28, 0.20]
ANCH_DUST  = [0.10, 0.10, 0.55, 0.78, 1.00, 0.68, 0.16, 0.10]
ANCH_NIGHT = [1.00, 1.00, 0.00, 0.00, 0.00, 0.40, 0.90, 1.00]


def smooth_t(t):
    t = max(0.0, min(1.0, t))
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


def render(hour, label):
    base = np.asarray(Image.open(ASSETS / "base.jpg").convert("RGB")).astype(np.float32) / 255.0
    light = np.asarray(Image.open(ASSETS / "light.png")).astype(np.float32) / 255.0
    floor = np.asarray(Image.open(ASSETS / "floor.png")).astype(np.float32) / 255.0
    windows = np.asarray(Image.open(ASSETS / "windows.png")).astype(np.float32) / 255.0

    tint, exposure, beam, dust, night = grade_at(hour)
    print(f"  {label:11s} h={hour:5.1f} tint=({tint[0]:.2f},{tint[1]:.2f},{tint[2]:.2f}) "
          f"exposure={exposure:.2f} beam={beam:.2f} dust={dust:.2f} nightBlue={night:.2f}")

    col = base.copy()
    # static stand-ins for the animated beam/dust/sheen terms: a flat
    # fraction of each mask, scaled the same way the shader scales them.
    beam_color = (1.0 - night) * np.array([1.0, 0.93, 0.78]) + night * np.array([0.80, 0.88, 1.0])
    col += beam_color * (light[..., None] * beam * 0.5 * 0.22)
    col += np.array([1.0, 0.94, 0.80]) * (floor[..., None] * beam * 0.5 * 0.05)

    col *= tint
    col *= exposure

    col *= (1.0 - night * floor[..., None] * 0.35)

    moon_glow = np.array([0.55, 0.68, 0.95]) * (windows[..., None] * night * 0.30)
    her_glow = np.array([1.0, 0.82, 0.58]) * (light[..., None] * night * 0.085)
    col += moon_glow + her_glow

    col = np.clip(col, 0.0, 1.0)
    out = Image.fromarray((col * 255).astype(np.uint8))
    OUT.mkdir(exist_ok=True)
    out.save(OUT / f"composite-{label}.jpg", quality=92)


def main():
    print("Rendering grade check composites:")
    render(7.0, "morning")
    render(17.0, "golden-hour")
    render(19.5, "dusk")
    render(23.0, "night")
    print(f"Wrote composites to {OUT}")


if __name__ == "__main__":
    main()
