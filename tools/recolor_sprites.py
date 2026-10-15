#!/usr/bin/env python3
"""
Warm recolour of holo's three UI sprites (glow-node.png, glow-pulse.png,
cone.png) for the gold-holo merge (BRIEF-2/BRIEF-3).

Two modes:

  regenerate (default, preferred -- BRIEF-3 explicitly asks for this over
  hue-shifting now that the original generator is available):
      python3 tools/recolor_sprites.py
  Re-runs holo-ref/assets/make_holo_assets.py's own procedural recipe for
  exactly these three sprites, with its cyan/violet palette constants
  swapped for warm brass/amber/cream ones. Same seed -> byte-identical
  shapes/gradients to the originals, just recoloured at the source instead
  of hue-rotated after the fact (no muddy intermediate hues from rotating
  already-rendered cyan pixels).

  --from-pngs <dir>:
      python3 tools/recolor_sprites.py --from-pngs ~/.config/quickshell/holo/assets
  Fallback for when only the rendered PNGs are available (no generator):
  hue-shifts + warm-tints whatever cone.png/glow-node.png/glow-pulse.png it
  finds in <dir>, preserving each pixel's alpha and relative luminance.
  Needed input files (copy from the P1 before running this mode):
      ~/.config/quickshell/holo/assets/cone.png
      ~/.config/quickshell/holo/assets/glow-node.png
      ~/.config/quickshell/holo/assets/glow-pulse.png

Output in both modes: holo-golden/assets/{cone,glow-node,glow-pulse}.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "holo-golden" / "assets"
W, H = 1920, 1080
DEFAULT_SEED = 20260923

# --------------------------------------------------------------------------- #
# warm palette -- sampled from the wallpaper's own light (see holo-golden's
# README for the sampling script/output this is drawn from): brass/amber in
# place of cyan, warm cream in place of cyan-pale.
# --------------------------------------------------------------------------- #
GOLD      = np.array([232, 168, 76], np.float32)   # ember/amber -- was CYAN
GOLD_PALE = np.array([255, 230, 185], np.float32)  # warm cream -- was CYAN_PALE
CREAM     = np.array([255, 246, 232], np.float32)  # near-white warm -- was STAR_WHITE
CONE_LO   = np.array([201, 140, 62], np.float32)   # was [86, 214, 255]
CONE_HI   = np.array([255, 214, 158], np.float32)  # was [168, 244, 255]

TAGS = {"glow_node": 44, "glow_pulse": 55, "cone": 77}


def rng_for(seed: int, tag: int) -> np.random.Generator:
    return np.random.default_rng([int(seed), int(tag)])


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _radial(size):
    c = (size - 1) / 2.0
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / (size / 2.0)
    return r


def _grid_noise(shape, res, rng):
    gh, gw = max(2, int(round(res[0]))), max(2, int(round(res[1])))
    g = rng.random((gh, gw), dtype=np.float32)
    im = Image.fromarray(g).resize((shape[1], shape[0]), Image.BICUBIC)
    return np.clip(np.asarray(im, dtype=np.float32), 0.0, 1.0)


def fbm(shape, rng, octaves=4, res=(5, 8), gain=0.5, lac=2.0):
    out = np.zeros(shape, np.float32)
    amp, norm = 1.0, 0.0
    gw, gh = float(res[1]), float(res[0])
    for _ in range(octaves):
        out += amp * _grid_noise(shape, (gh, gw), rng)
        norm += amp
        amp *= gain
        gw *= lac
        gh *= lac
    return out / norm


def coords():
    yy, xx = np.mgrid[0:H, 0:W]
    return xx.astype(np.float32), yy.astype(np.float32)


def to_u8(arr):
    return np.clip(np.rint(arr), 0, 255).astype(np.uint8)


def save(path, rgb, alpha):
    rgba = np.dstack([to_u8(rgb), to_u8(alpha)]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(path)
    return rgba


# --------------------------------------------------------------------------- #
# regenerate mode -- adapted 1:1 from holo-ref/assets/make_holo_assets.py's
# make_glow_node / make_glow_pulse / make_cone, cyan/violet -> warm.
# --------------------------------------------------------------------------- #
def make_glow_node(rng):
    size = 512
    r = _radial(size)
    core = np.exp(-(r / 0.17) ** 2)
    glow = np.exp(-(r / 0.40) ** 1.75)
    halo = np.exp(-(r / 0.74) ** 2) * 0.34
    a = np.clip(core * 1.05 + glow * 0.80 + halo, 0.0, 1.0) * smoothstep((1.0 - r) / 0.20)
    heat = np.clip(core + glow * 0.55, 0.0, 1.0)[:, :, None]
    rgb = GOLD[None, None, :] * (1.0 - heat) + CREAM[None, None, :] * heat
    a *= 255.0
    a[a < 1.0] = 0.0
    return rgb, a


def make_glow_pulse(rng):
    size = 256
    r = _radial(size)
    core = np.exp(-(r / 0.12) ** 2)
    glow = np.exp(-(r / 0.30) ** 2.0)
    halo = np.exp(-(r / 0.56) ** 2) * 0.30
    a = np.clip(core * 1.15 + glow * 0.90 + halo, 0.0, 1.0) * smoothstep((1.0 - r) / 0.20)
    heat = np.clip(core * 1.25 + glow * 0.60, 0.0, 1.0)[:, :, None]
    # one crisp point of light: slightly hotter core than glow-node's, no echo
    rgb = np.array([255, 214, 140], np.float32)[None, None, :] * (1.0 - heat) \
        + np.array([255, 250, 240], np.float32)[None, None, :] * heat
    a *= 255.0
    a[a < 1.0] = 0.0
    return rgb, a


def make_cone(rng):
    xx, yy = coords()
    dy = (H - 1) - yy
    half = 26.0 + 660.0 * (dy / H) ** 1.12
    d = np.abs(xx - W / 2.0) / half

    rim = smoothstep((1.0 - d) / 0.55)
    lat = np.exp(-(d / 0.78) ** 2)
    vfall = np.exp(-dy / (H * 0.52))
    grain = 0.86 + 0.28 * fbm((H, W), rng, 4, (5, 8))

    inten = rim * vfall * (0.30 + 0.70 * lat) * grain
    inten = np.clip(inten, 0.0, None)
    inten /= max(float(inten.max()), 1e-6)

    heat = np.clip(vfall * 1.15, 0.0, 1.0)[:, :, None]
    rgb = CONE_LO[None, None, :] * (1.0 - heat) + CONE_HI[None, None, :] * heat
    rgb += rng.normal(0.0, 0.35, (H, W, 3)).astype(np.float32)
    return rgb, inten * 132.0


def regenerate(seed: int, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("glow-node.png", "glow_node", make_glow_node),
        ("glow-pulse.png", "glow_pulse", make_glow_pulse),
        ("cone.png", "cone", make_cone),
    ]
    print(f"recolor_sprites.py (regenerate)  seed={seed}  out={out_dir}")
    for fname, tag, fn in jobs:
        rng = rng_for(seed, TAGS[tag])
        rgb, alpha = fn(rng)
        rgba = save(out_dir / fname, rgb, alpha)
        print(f"  wrote {fname:16s} {rgba.shape[1]}x{rgba.shape[0]} RGBA  mean alpha {float(rgba[:, :, 3].mean()):.1f}")


# --------------------------------------------------------------------------- #
# fallback mode -- hue-shift/tint whatever PNGs are handed to it, preserving
# alpha and relative luminance (for when only the rendered sprites, not the
# generator, are available).
# --------------------------------------------------------------------------- #
def hueshift_tint(rgb01, target_hue_deg=38.0, sat_scale=1.0):
    """Replace each pixel's hue with a fixed warm hue, keep its own
    saturation (scaled) and value, so gradients/falloffs are preserved."""
    import colorsys
    h, w, _ = rgb01.shape
    flat = rgb01.reshape(-1, 3)
    out = np.empty_like(flat)
    target_h = target_hue_deg / 360.0
    for i in range(flat.shape[0]):
        r, g, b = flat[i]
        _, s, v = colorsys.rgb_to_hsv(r, g, b)
        nr, ng, nb = colorsys.hsv_to_rgb(target_h, min(1.0, s * sat_scale), v)
        out[i] = (nr, ng, nb)
    return out.reshape(h, w, 3)


def from_pngs(src_dir: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    names = ["cone.png", "glow-node.png", "glow-pulse.png"]
    for name in names:
        src = src_dir / name
        if not src.exists():
            print(f"  skipping {name}: not found in {src_dir}")
            continue
        im = Image.open(src).convert("RGBA")
        arr = np.asarray(im).astype(np.float32) / 255.0
        rgb, alpha = arr[..., :3], arr[..., 3] * 255.0
        warm_rgb = hueshift_tint(rgb, target_hue_deg=38.0, sat_scale=0.9) * 255.0
        save(out_dir / name, warm_rgb, alpha)
        print(f"  wrote {name} (hue-shifted from {src})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--from-pngs", default=None, metavar="DIR",
                     help="fallback: hue-shift PNGs found in DIR instead of regenerating")
    args = ap.parse_args()

    out_dir = Path(args.out)
    if args.from_pngs:
        from_pngs(Path(args.from_pngs).expanduser(), out_dir)
    else:
        regenerate(args.seed, out_dir)


if __name__ == "__main__":
    main()
