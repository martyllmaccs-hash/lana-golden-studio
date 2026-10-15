# Addendum: the studio becomes the holo fleet's backdrop

Finding: Martin's live desktop background is the **holo** Quickshell overlay (copy in `holo-ref/`, read-only
reference — do not edit it). It draws a static photo (`assets/background.jpg`, Image at
`x: -parent.width*0.025`, Stretch) and on top of it the bot fleet: quadratic link curves (Canvas,
`rgba(47,124,140,0.55)`), a single glow-pulse sprite per message, and HoloNode items — all in a cyan
palette (`#7ff0ff`, `#3d6f7d`, `#d8f6ff`, `#2f7c8c`, `#a8f7ff`). Its panel is ~1887x1045, not full screen.

Add, without breaking anything already built:

1. `studio/StudioBackdrop.qml` — the living studio as a reusable `Item` (fills its parent, no window), with
   the same properties (`fps`, `speed`, `forcedPhase`, `dayPhase`, `signature()`) so it can replace holo's
   static `Image` in one line. Have `studio/shell.qml` use it, so there is one implementation.
   Asset/shader URLs must resolve relative to StudioBackdrop.qml itself.
2. `holo-golden/` — a **patched copy** of holo-ref as a new config (`quickshell -n -p .../holo-golden`):
   - copy StudioBackdrop.qml + shaders + assets in, and replace the static photo with it;
   - re-theme the fleet to match the studio: warm brass/candle-gold lines, cream-white pulse,
     ember/amber working glow, soft terracotta for idle/dim. Pick concrete hex values from the
     wallpaper's own palette (sample `ref/wallpaper-1080p.jpg` with Pillow and justify the picks in README).
     Lines should read like thin gilded threads in the haze. Pulses remain ONE crisp point of light, no
     trails or echoes (Martin's standing rule). Working nodes must visibly light up.
   - holo's PNG sprites (glow-node/glow-pulse/cone) are cyan: generate warm recoloured versions in
     `holo-golden/assets/` via a Pillow script (`tools/recolor_sprites.py`) — you don't have the originals
     here, so write the script to recolour whatever PNGs it's given (hue-shift/tint preserving alpha), and
     list which files must be copied from the P1's `~/.config/quickshell/holo/assets/` before running it.
   - Night phase: the gold lines cool towards moonlit silver-blue along with the room.
   - Keep the diff minimal and well-commented; keep the IPC `drift` handler and `sweep` intact.
   - Produce `holo-golden/DIFF.patch` (unified diff vs holo-ref).
3. Update `preview/` so the preview can optionally overlay a few fake fleet nodes + links + one pulse in the
   new palette, so Martin can judge the combination in a browser.

Same verification rules as before. Report file list, verified vs unverified.
