# Brief: "Golden Hour Studio" — a living wallpaper

## Source
`ref/wallpaper-2k.jpg` (2752x1536) and `ref/wallpaper-1080p.jpg` (1920x1080): a dancer in a white slip
holding a standing split, centre-left, in a brick ballet studio. Tall windows at left, mirror wall and barre,
honey wood floor. Strong warm side light from the left → hazy beams, long floor shadows. Palette: amber,
terracotta, honey, cream highlights. Mood: serene, graceful, intimate. Empty space: right side and floor.

## Goal
Turn it into an *active* desktop background that looks like the same photograph, alive. Restraint is the
aesthetic: someone glancing should feel the room breathing, not see "effects". Never distort or warp the
dancer — she stays a still photograph. Motion lives in the light and the air.

## Effects (all subtle, all slow)
1. **Breathing light shafts** — the window beams brighten/soften slowly, as if thin cloud passes the sun
   (low-frequency noise scrolling in the light direction). Volumetric haze: a few soft rays radiating from the
   window side, additive, masked to where the photo is already bright/hazy.
2. **Cloud shadows** — very soft, large dappled shadows drifting across floor and walls (multiply, max ~10%
   darkening), direction consistent with the light (moving left → right). Period ~40–90 s.
3. **Dust motes** — sparse floating particles (gold/cream), lazy brownian drift with slight upward float,
   visible ONLY inside lit areas (multiply by the light mask), gentle twinkle when they catch the beam,
   depth via size/blur. Few, not snow. ~60–120 motes.
4. **Floor sheen** — faint slow shimmer along the existing floor highlights (the polished wood reflections).
5. **Time of day grade** (driven by the real local clock, smooth): morning = cooler cream, midday = neutral,
   late afternoon/golden hour = richer amber (closest to the original), dusk = deep rose-amber with beams
   lower-intensity, night (≈21:00–06:00) = moonlit: overall darker, cooler blue in windows/shadows,
   beams faint and silvery, dust barely visible, a warm low glow kept on her so she remains the focus.
   Keep it tasteful — night must still be readable and lovely, not just "darkened".
6. **One "signature" moment, creative**: e.g. every few minutes a slow sweep of brighter light glides across
   the mirror wall (sun breaking through), or a ripple of motes lifts as if she just moved. Your call — make it
   rare, quiet, and delightful.

## Precomputed masks (offline, Python + Pillow/numpy via `uv run --with pillow --with numpy python ...`)
Write `tools/make_masks.py` producing PNGs in `studio/assets/` from the 2k image at 1920x1080 (and keep
2k-capable code): `base.jpg` (1920x1080 copy, high quality), `light.png` (where beams/haze/bright light are —
smooth, blurred luminance+warmth mask, single channel), `floor.png` (lower floor region with highlights, for
sheen), `windows.png` (window glass area, top-left, for night tint). Derive heuristically from luminance,
saturation and position; blur generously. Also export a small `masks-preview.png` contact sheet.

## Deliverables
A. `studio/` — a **Quickshell 0.3.1 / Qt 6.11** config to run with `quickshell -n -p ~/.config/quickshell/studio`:
   - `shell.qml`: `ShellRoot` + `Variants { model: Quickshell.screens; PanelWindow {...} }` with
     `WlrLayershell.layer: WlrLayer.Background`, `WlrLayershell.namespace: "lana-studio"`,
     `exclusionMode: ExclusionMode.Ignore`, `WlrLayershell.keyboardFocus: WlrKeyboardFocus.None`,
     anchors all four edges, `color: "black"`. Must also set an empty input mask so it never steals clicks
     (e.g. `mask: Region {}`), so the Omarchy background below keeps its double-click handlers irrelevant —
     clicks pass through.
   - Rendering: a `ShaderEffect` over the base image + mask textures (`Image` items with `visible:false`,
     `layer`/`ShaderEffectSource` as needed). Fragment shader(s) in `studio/shaders/*.frag` written in
     Qt6 GLSL (`#version 440`, `layout(location=0) in vec2 qt_TexCoord0; layout(location=0) out vec4 fragColor;
     layout(std140, binding=0) uniform buf { mat4 qt_Matrix; float qt_Opacity; float time; ... };`,
     samplers at binding 1..N). Reference them as `shaders/name.frag.qsb`. I will compile with
     `/usr/lib/qt6/bin/qsb --glsl "100es,120,150" --hlsl 50 --msl 12 -o x.frag.qsb x.frag` on the target;
     provide `build.sh` doing that for every .frag.
   - Dust motes: do them in-shader (hash-based procedural particles in cells) — no QML particle system.
   - **Animation clock: use a `Timer` (interval ~42 ms, repeat, running) that updates a `time` property.**
     `NumberAnimation`/`SequentialAnimation on <prop>` is known NOT to run in this Quickshell build. Also a
     slower timer (every 30 s) updating `dayPhase` from `new Date()` (hours as float 0–24).
   - Cheap: one full-screen pass, ≤ ~60 texture samples/pixel worst case; the GPU is an Intel UHD 630 (laptop),
     battery matters. Provide a `fps` property (default 24).
   - IpcHandler `target: "studio"` with functions: `phase(h: real)` to force time of day (use -1 to return to
     the real clock), `speed(s: real)` multiplier, `signature()` to trigger the signature moment now,
     `status(): string` returning JSON {time, dayPhase, forcedPhase, fps}.
   - Keep everything inside `studio/` self-contained (relative asset paths resolved from the qml file's
     location, e.g. `Qt.resolvedUrl("assets/base.jpg")`).
B. `preview/index.html` — a self-contained WebGL2 preview using the SAME shader logic (port, keep in sync),
   loading `../studio/assets/*` by relative path, with a small unobtrusive control strip: time-of-day slider,
   "real clock" toggle, speed, and a "signature" button. Images can be embedded as base64 if needed so the
   single file works standalone — write `preview/build_preview.py` that inlines the assets into
   `preview/studio-preview.html`.
C. `README.md` — what each effect does, how to tune, IPC commands.

## Verification you must do here (no Wayland/Quickshell in this container)
- Run `tools/make_masks.py`, confirm masks exist with sane value ranges (print stats).
- Statically check the QML for obvious syntax errors (balanced braces, imports). If `glslangValidator` or
  similar isn't available, at least check shader structure carefully against the Qt6 template above.
- For the preview: if node/a headless browser is available, sanity-check the JS parses
  (`node --check` on an extracted script). Don't install heavy stuff.
- Render 3 still frames offline with numpy (a CPU re-implementation of the shader is NOT required; instead,
  produce `checks/` composites of base × masks) only if cheap. Optional.

Do not touch anything outside this directory. Report at the end: file list, what you verified, what you
could not verify.
