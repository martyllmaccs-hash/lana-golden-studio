#!/usr/bin/env python3
"""
Derive the Golden Hour Studio wallpaper masks from the 2k reference photo.

Usage:
    uv run --with pillow --with numpy python tools/make_masks.py [--width 1920] [--height 1080]

Produces (in studio/assets/):
    base.jpg            resized copy of the source photo, high quality
    light.png            single-channel mask: beams / haze / bright warm light
    floor.png            single-channel mask: lower floor band, weighted by wood highlights
    windows.png           single-channel mask: window glass area (top-left), for night tint
    air.png              single-channel mask: wide soft "lit air volume" between the windows
                         and her -- broader/lower-threshold than light.png, for dust motes
                         to drift through (motion-2x pass, BRIEF-3)
    masks-preview.png     contact sheet of base + the four masks, for a quick sanity look

Everything is derived heuristically from luminance, saturation and position in the
source photo -- no manual masking/painting. Code is resolution-agnostic: pass
--width/--height to regenerate at 2k (2752x1536) or any other size; the source
2k image is always used so downsampling quality stays high.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ref" / "wallpaper-2k.jpg"
OUT_DIR = ROOT / "studio" / "assets"


def smoothstep(x, edge0, edge1):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def to_gray_u8(arr01):
    return (np.clip(arr01, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def blur(img_u8, radius_px):
    if radius_px <= 0:
        return img_u8
    im = Image.fromarray(img_u8, mode="L")
    im = im.filter(ImageFilter.GaussianBlur(radius=radius_px))
    return np.asarray(im)


def stats(name, arr01):
    print(f"  {name:10s} min={arr01.min():.3f} max={arr01.max():.3f} "
          f"mean={arr01.mean():.3f} std={arr01.std():.3f}")


def make_masks(width: int, height: int):
    print(f"Loading {SRC} ...")
    src = Image.open(SRC).convert("RGB")
    print(f"  source size: {src.size}")

    # High-quality resize (Lanczos) down to the target render resolution.
    base = src.resize((width, height), Image.LANCZOS)

    a = np.asarray(base).astype(np.float32) / 255.0
    H, W, _ = a.shape
    r, g, b = a[..., 0], a[..., 1], a[..., 2]

    lum = 0.299 * r + 0.587 * g + 0.114 * b
    mx = a.max(axis=-1)
    mn = a.min(axis=-1)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    warm = np.clip(r - b, 0.0, 1.0)  # amber/orange bias

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = xx / (W - 1)  # 0..1 left->right
    ny = yy / (H - 1)  # 0..1 top->bottom

    # ------------------------------------------------------------------
    # light.png -- beams, haze, bright warm light. The photo's own bright
    # areas (windows, hazy air, sunlit floor patches) ARE the light source,
    # so this is mostly a smooth luminance threshold with a slight warmth
    # boost, blurred generously to turn hard highlights into soft volumes.
    # ------------------------------------------------------------------
    light_raw = smoothstep(lum, 0.42, 0.88)
    light_raw = light_raw * (0.75 + 0.25 * warm / max(warm.max(), 1e-6))
    light_raw = np.clip(light_raw, 0.0, 1.0)
    light_u8 = blur(to_gray_u8(light_raw), radius_px=max(W, H) * 0.012)
    # re-blur once more, larger, for the soft volumetric haze component,
    # and blend it under the sharper pass so beams keep a defined core.
    light_u8_wide = blur(to_gray_u8(light_raw), radius_px=max(W, H) * 0.035)
    light_u8 = to_gray_u8(
        0.65 * (light_u8.astype(np.float32) / 255.0)
        + 0.35 * (light_u8_wide.astype(np.float32) / 255.0)
    )

    # ------------------------------------------------------------------
    # floor.png -- lower floor band, weighted toward existing wood
    # highlights/reflections, for the sheen shimmer effect.
    # ------------------------------------------------------------------
    floor_band = smoothstep(ny, 0.56, 0.68)  # ramps in starting ~56% down
    floor_highlight = smoothstep(lum, 0.22, 0.6)
    floor_raw = floor_band * floor_highlight
    floor_u8 = blur(to_gray_u8(floor_raw), radius_px=max(W, H) * 0.006)

    # ------------------------------------------------------------------
    # windows.png -- window glass, top-left. Glass here is blown out:
    # high luminance AND low saturation (near-white), restricted to the
    # region where the windows actually sit.
    # ------------------------------------------------------------------
    region = smoothstep(nx, 0.46, 0.22) * smoothstep(ny, 0.72, 0.40)
    glass = smoothstep(lum, 0.45, 0.85) * (1.0 - smoothstep(sat, 0.12, 0.42))
    windows_raw = np.clip(region * glass, 0.0, 1.0)
    windows_u8 = blur(to_gray_u8(windows_raw), radius_px=max(W, H) * 0.01)

    # ------------------------------------------------------------------
    # air.png -- a much wider, softer version of "where the light reaches"
    # than light.png: a low luminance threshold (so midtones count as air,
    # not just hot highlights) times a gentle left-weighted position
    # falloff (the windows/dancer side of the room), blurred very wide.
    # This is NOT a brightness mask -- it is a volume mask, so dust motes
    # can drift through the whole sunlit side of the room, not just the
    # tight beam cores, while still reading as "this is where the light
    # is" rather than snow everywhere (BRIEF-3 motion-2x pass).
    # ------------------------------------------------------------------
    air_lum = smoothstep(lum, 0.16, 0.58)
    air_pos = smoothstep(nx, 1.05, -0.10)  # near-full width, gently fading at the far right
    air_raw = np.clip(0.30 + 0.70 * air_lum, 0.0, 1.0) * (0.55 + 0.45 * air_pos)
    air_u8 = blur(to_gray_u8(air_raw), radius_px=max(W, H) * 0.05)

    print("Mask stats:")
    stats("lum", lum)
    stats("sat", sat)
    stats("light", light_u8.astype(np.float32) / 255.0)
    stats("floor", floor_u8.astype(np.float32) / 255.0)
    stats("windows", windows_u8.astype(np.float32) / 255.0)
    stats("air", air_u8.astype(np.float32) / 255.0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base.save(OUT_DIR / "base.jpg", quality=95, subsampling=0)
    Image.fromarray(light_u8, mode="L").save(OUT_DIR / "light.png")
    Image.fromarray(floor_u8, mode="L").save(OUT_DIR / "floor.png")
    Image.fromarray(windows_u8, mode="L").save(OUT_DIR / "windows.png")
    Image.fromarray(air_u8, mode="L").save(OUT_DIR / "air.png")
    print(f"Wrote base.jpg, light.png, floor.png, windows.png, air.png to {OUT_DIR}")

    # Contact sheet: base + the four masks (as RGB previews), 3x2.
    thumb_w = 480
    thumb_h = int(thumb_w * H / W)

    def thumb_rgb(img):
        return img.resize((thumb_w, thumb_h), Image.LANCZOS)

    sheet = Image.new("RGB", (thumb_w * 3, thumb_h * 2), "black")
    sheet.paste(thumb_rgb(base), (0, 0))
    sheet.paste(thumb_rgb(Image.fromarray(light_u8).convert("RGB")), (thumb_w, 0))
    sheet.paste(thumb_rgb(Image.fromarray(floor_u8).convert("RGB")), (thumb_w * 2, 0))
    sheet.paste(thumb_rgb(Image.fromarray(windows_u8).convert("RGB")), (0, thumb_h))
    sheet.paste(thumb_rgb(Image.fromarray(air_u8).convert("RGB")), (thumb_w, thumb_h))
    sheet.save(OUT_DIR / "masks-preview.png")
    print(f"Wrote masks-preview.png (base | light | floor / windows | air | -)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    args = ap.parse_args()
    make_masks(args.width, args.height)


if __name__ == "__main__":
    main()
