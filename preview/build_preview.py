#!/usr/bin/env python3
"""
Inline studio/assets/*.{jpg,png} into preview/index.html as base64 data
URIs, producing a single self-contained preview/studio-preview.html that
needs no relative files to open and view.

Usage: python3 preview/build_preview.py   (no extra deps; stdlib only)
"""
import base64
import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "studio" / "assets"
SRC_HTML = Path(__file__).resolve().parent / "index.html"
OUT_HTML = Path(__file__).resolve().parent / "studio-preview.html"

ASSET_FILES = {
    "base": "base.jpg",
    "light": "light.png",
    "floor": "floor.png",
    "windows": "windows.png",
    "air": "air.png",
}


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def main():
    html = SRC_HTML.read_text(encoding="utf-8")

    uris = {}
    for key, filename in ASSET_FILES.items():
        p = ASSETS / filename
        if not p.exists():
            raise SystemExit(f"missing asset: {p} (run tools/make_masks.py first)")
        uris[key] = data_uri(p)
        print(f"  embedded {filename}: {len(uris[key])} chars")

    import json
    script_tag = (
        '<script id="embedded-assets" type="application/json">'
        + json.dumps(uris)
        + "</script>"
    )

    marker = "<!-- EMBEDDED_ASSETS_PLACEHOLDER -->"
    if marker not in html:
        raise SystemExit(f"marker {marker!r} not found in {SRC_HTML}")
    html = html.replace(marker, script_tag)

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"wrote {OUT_HTML} ({OUT_HTML.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
