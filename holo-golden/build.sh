#!/usr/bin/env bash
# Compile every studio/shaders/*.frag into the .qsb form Quickshell/Qt Quick
# expects, targeting GLSL (ES 100/120/150), HLSL 50 and MSL 1.2 so the same
# .qsb works across backends. Run this on the target machine (where qsb
# ships with Qt 6) after editing any .frag file.
set -euo pipefail

cd "$(dirname "$0")"

QSB="${QSB:-/usr/lib/qt6/bin/qsb}"

if ! command -v "$QSB" >/dev/null 2>&1; then
    echo "error: qsb not found at '$QSB' (set QSB=/path/to/qsb to override)" >&2
    exit 1
fi

shopt -s nullglob
frags=(shaders/*.frag)
if [ ${#frags[@]} -eq 0 ]; then
    echo "no .frag files found in shaders/" >&2
    exit 1
fi

for f in "${frags[@]}"; do
    out="${f}.qsb"
    echo "compiling $f -> $out"
    "$QSB" --glsl "100es,120,150" --hlsl 50 --msl 12 -o "$out" "$f"
done

echo "done."
