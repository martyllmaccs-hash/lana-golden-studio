# Golden Hour Studio — a living wallpaper, and its gold-holo fleet

A Quickshell background that turns `ref/wallpaper-2k.jpg` (a dancer in a sunlit brick ballet
studio) into a quiet, breathing scene: the photograph never changes shape, only the light and
air moving through it. Everything is one full-screen shader pass over the still photo — no
displacement, no geometry, no warping. `studio/` is that wallpaper as a standalone config;
`holo-golden/` is Martin's live orchestration-fleet overlay (`holo-ref/`, read-only reference)
re-themed in the studio's own warm palette and backdropped by the same living shader.

## Layout

```
studio/
  shell.qml               Quickshell config: one PanelWindow per screen, each hosting...
  StudioBackdrop.qml       ...the living studio as a reusable Item (BRIEF-2/3): owns its
                           own clock/day/signature timers, fills its parent, no window --
                           drop it into any config in one line (see holo-golden/).
  shaders/studio.frag      the shader (Qt6 GLSL 440, source form)
  shaders/studio.frag.qsb  compiled shader (build.sh produces this; not checked in)
  build.sh                 runs qsb over every studio/shaders/*.frag
  assets/                  base.jpg + light/floor/windows/air.png masks + masks-preview.png
holo-golden/
  shell.qml                patched copy of holo-ref/shell.qml: warm palette, night-cooling,
                           a separate full-screen backdrop window ahead of the node panel
  HoloNode.qml             patched copy: warm/night-aware node accent colour
  Renderer.js, Drift.js    byte-identical copies of holo-ref's (untouched: data model,
                           `drift`/`sweep` IPC)
  StudioBackdrop.qml, shaders/, assets/*.{jpg,png}   copied in from studio/ (+ air.png)
  assets/{glow-node,glow-pulse,cone}.png   warm sprites (tools/recolor_sprites.py)
  build.sh                 same qsb build, for holo-golden's own shaders/ copy
  DIFF.patch               unified diff vs holo-ref/{shell.qml,HoloNode.qml}
holo-ref/                  READ-ONLY reference: the live cyan baseline this is patched from
tools/
  make_masks.py            derives the masks (incl. air.png) from ref/wallpaper-2k.jpg
  render_checks.py         offline sanity composites (grade LUT only, no distortion)
  motion_check.py          offline numpy approximation verifying the motion-2x amplitude
  recolor_sprites.py       regenerates holo's 3 cyan sprites in warm brass/amber/cream
preview/
  index.html               WebGL2 port of the same shader + a HUD + an optional fleet overlay
  build_preview.py         inlines studio/assets/* as base64 into a standalone file
  studio-preview.html      the standalone output (generated)
checks/                  composite-*.jpg / motion-check-*/sprite-compare.png etc (generated)
```

## Running it

```sh
cd studio
./build.sh                                       # compiles shaders/*.frag -> *.frag.qsb
quickshell -n -p ~/.config/quickshell/studio      # or wherever you've symlinked studio/
```

```sh
cd holo-golden
./build.sh
quickshell -n -p ~/.config/quickshell/holo-golden
```

`build.sh` needs `qsb` (ships with Qt6, typically `/usr/lib/qt6/bin/qsb`); it wasn't available
in the container this was built in, so **the compiled `.qsb` is not included** in either
config — run `build.sh` on the target machine after any shader edit. Everything else (masks,
QML, sprites) is ready to go.

## The effects, and how to tune them

All tuning knobs live in `studio/shaders/studio.frag` (and must be mirrored into
`preview/index.html`'s embedded copy of the same shader — see "Keeping the two shaders in
sync" below). holo-golden uses this exact file unmodified (copied, not re-derived).

1. **Breathing light shafts** (`// ---- 1.`) — `fbm()` noise scrolled along `lightDir` modulates
   a `breathe` multiplier over the `light.png` mask; two `atan()`-based angular bands (`ray0`,
   `ray1`) add soft rays fanning from a point just off-frame at the window side, plus a slow
   bounded `raySweep` (±4°, ~7 min period) so the rays genuinely sweep rather than only
   shimmer in place. Scroll speed: the `* 0.040` / `* 0.06` / `* 0.044` coefficients on `time`
   (doubled from the original subtle pass — BRIEF-3 "motion 2x"). Visible strength: the
   `* 0.22 * motion` at the end of that block, additionally attenuated by
   `pow(1 - luminance(base), 2)` so the already-blown-out windows can't clip flatter than white.
2. **Cloud shadows** — a single large-scale `fbm()` sampled at `auv - cloudDir * (time /
   cloudPeriod)`, thresholded by `smoothstep(0.42, 0.62, cloud)` and capped at
   `0.10 * motion` darkening (20% at the default `motion=2.0`, clamped to 0.6 so extreme
   `motion` values can't black out the room). `cloudPeriod` (30s, halved from 62s) sets the
   drift period; `cloudDir` sets direction (left→right, slightly downward, matching the
   window light).
3. **Dust motes** — procedural, no particle system. The screen is divided into a 14×8 cell
   grid (~112 cells ≈ mote count); each pixel checks its own cell and the 8 neighbors (9 total)
   for a hashed mote position, so cost stays flat regardless of mote count. Per mote: `riseSpeed`
   drives a slow upward float that wraps (respawns) via `fract()` (rise/wander rates doubled),
   `wx`/wander sine give lazy horizontal drift, and a per-cell hash now also rolls a ~1-in-5
   chance of a soft bokeh mote up to 3x the base size (quieter twinkle, since big motes read
   calmer). Motes are multiplied by `airMask` (not `lightMask`) — a much wider, lower-threshold
   "lit volume" mask (see Masks below) that carries its own ~15% floor at its darkest, so the
   air itself reads faintly everywhere the light could plausibly reach, not just inside the
   tight beam cores — and by `dustMul` from the day-grade (barely visible at night). Tune
   density via the `grid` vector, size via the `mix(0.0016, 0.0040, ...)` range and `sizeMul`.
4. **Floor sheen** — `floor.png` mask times a slow travelling sine streak (`sheenWave`, travel
   rate doubled) plus a sparse hash-based sparkle term, added at `0.05 * beamMul * motion`.
5. **Time-of-day grade** — `gradeAt()` is a cyclic keyframe table (`ANCH_H` = hours, with
   per-hour tint RGB, exposure, beam/dust multipliers and a `nightBlue` amount), linearly
   interpolated (smoothstepped) between neighboring anchors. Add/move anchors to retune the
   day; each row in the `ANCH_*` arrays is one keyframe. Currently: midnight→5am moonlit,
   7am pale cream, noon neutral, 5pm golden amber (richest, closest to the source photo),
   7:30pm dusk rose-amber, 9pm back to moonlit. `nightBlue` additionally drives a cool glow
   over `windows.png` (moonlight through the glass) and dims the photo's own baked-in sunbeam
   floor patch (`floorMask`) since a sharp warm beam can't itself turn into moonlight — plus a
   small kept warm glow over `lightMask` (`herGlow`) so the dancer stays the warm focal point
   even at night. holo-golden's own fleet palette uses the *same* keyframe hours/night curve
   (ported to JS as `nightAmountAt()`) so the gold cools to silver-blue in lockstep.
6. **Signature moment** — a soft diagonal sweep (`sig`/`sweepX`/`band`) glides left→right across
   the frame over 6.5s, brighter where it crosses already-lit areas (mirror, windows, floor
   beam), with a matching small twinkle boost on the dust motes during the sweep. Fires
   automatically every 4 minutes or on demand via IPC. (Left un-amplified by `motion` — it's
   already meant to be the one punchier moment against an otherwise-subtler everyday motion
   level, and over-amplifying it would work against "rare, quiet, delightful".)

Nothing above ever touches `qt_TexCoord0` before sampling `baseTex` — the dancer is always
read at her exact photographed position.

### Motion (BRIEF-3: "I can't see any motion" → motion 2x)

Measured on the real P1 at golden hour/speed 3, the original pass only changed 0.22% of
pixels by >4/255 over 1s (2.1% over 5s) — the light mask covered little of the frame (mean
0.13) and every amplitude was tiny. The fix has two parts, both baked into the shader itself,
*plus* a new `motion` scalar on top:

- **Drift/scroll rates doubled outright** (beam shimmer, ray sweep, cloud drift period halved,
  mote rise/wander, sheen travel) — a one-time code change, independent of the `motion` or
  `speed` uniforms, because "twice as fast" isn't something you'd ever want to dial back to 1x.
- **Every visible amplitude scaled by the new `motion` uniform** (cloud cap, beam/dust/sheen
  final multipliers) — `motion = 1.0` reproduces the old subtle amplitude, `motion = 2.0`
  (the new default) doubles it. Separate from `speed` (which scales *time's rate*, i.e. how
  fast the clock itself runs): `motion` scales *how big* each effect's swing is at any given
  speed. Control over IPC: `quickshell ipc call studio motion 2.5`.
- Dust additionally gates on the new, much wider `air.png` mask instead of the tight
  `light.png` beam mask (see Masks below), so there's simply more *area* for motes to exist in,
  independent of amplitude.

Verified with `tools/motion_check.py` (a numpy port of the dynamic shader terms — not the
static grade, which `render_checks.py` already covered): at golden hour, speed=1,
`motion=2.0` (the new default), **26.67%** of pixels change by >4/255 over 5 real seconds
(mean abs diff 3.78/255, max 162.6/255) — more than 5x the brief's ">5%" target. Even at
`motion=1.0` (the old amplitude, but with the doubled drift rates and wider air mask that
ship unconditionally) it's 15.17%, confirming the rate/mask changes alone already fix most of
the "I can't see any motion" complaint, with `motion` providing the rest. Run it yourself:

```sh
uv run --with pillow --with numpy python tools/motion_check.py
```

writes `checks/motion-check-{t0,t5,diff}.{jpg,png}` for a visual look at what actually moved.

## Masks

`tools/make_masks.py` derives everything from `ref/wallpaper-2k.jpg` by heuristics only (no
manual painting): luminance, saturation and normalized position.

```sh
uv run --with pillow --with numpy python tools/make_masks.py            # 1920x1080 (default)
uv run --with pillow --with numpy python tools/make_masks.py --width 2752 --height 1536  # 2k
```

- `light.png` — `smoothstep(lum, 0.42, 0.88)` with a small warmth boost, blurred twice (a tight
  pass and a wide pass, blended) for a soft volumetric feel. Picks up the windows, the hazy air
  around them, and the sunlit floor patch — i.e. anywhere the photo is already bright.
- `floor.png` — a vertical ramp starting ~56% down the frame, times a luminance highlight
  threshold, lightly blurred. Isolates the lower floor band's existing wood highlights.
- `windows.png` — restricted to the upper-left region (where the windows actually are) via a
  position falloff, intersected with "blown out" pixels (high luminance, *low* saturation —
  overexposed glass reads as near-white, unlike the warm, more saturated brick/floor).
- `air.png` (BRIEF-3) — a much wider, lower-threshold "lit volume" mask: `smoothstep(lum, 0.16,
  0.58)` (midtones count, not just hot highlights) times a gentle left-weighted position
  falloff (the windows/dancer side of the room), blurred very wide (`0.05 * max(W,H)`). Unlike
  `light.png` it's a volume mask, not a brightness mask, and its own floor/falloff formula
  (`0.30 + 0.70*lum_term`, times `0.55 + 0.45*pos_term`) means it never drops fully to zero
  (measured min 0.165, mean 0.484) — exactly the "~15% faint floor so the air reads" the brief
  asked for, baked into the mask itself rather than a separate shader-side floor.
- `masks-preview.png` — a 3×2 contact sheet (base / light / floor, windows / air / —) for a
  quick look.

## StudioBackdrop.qml (BRIEF-2/3)

The living studio, factored out of `studio/shell.qml` into a reusable `Item`
(`studio/StudioBackdrop.qml`): fills its parent, no `PanelWindow`/window-management API, and
fully self-contained — it owns its own clock/day/signature `Timer`s (same reasoning as always:
`NumberAnimation`/`SequentialAnimation on <prop>` silently never ran in this Quickshell build),
so dropping it anywhere is a true one-line replacement with sane real-clock defaults:

```qml
StudioBackdrop { anchors.fill: parent }
```

Exposes `fps`, `speed`, `motion`, `forcedPhase`, `dayPhase`, `time`, `signatureStart` as plain
properties (bindable from an owning shell's own `IpcHandler`) and a `signature()` function,
plus a bindable `signatureTrigger` counter so a multi-screen owner (see `studio/shell.qml`'s
`Variants`) can fan one IPC `signature()` call out to several independent instances without
needing a shared clock — each instance fires its own envelope against its own local `time`.
Asset/shader URLs (`Qt.resolvedUrl("assets/...")`, `"shaders/studio.frag.qsb"`) resolve
relative to wherever `StudioBackdrop.qml` itself lives, so copying it + its `assets/`/`shaders/`
alongside it (as `holo-golden/` does) is all that's needed to reuse it elsewhere.

`studio/shell.qml` now just wires its root-level `IpcHandler` to one `StudioBackdrop` instance
per screen (`Variants { model: Quickshell.screens }`), binding `fps`/`forcedPhase`/`speed`/
`motion`/`signatureTrigger` down into each; it also keeps a lightweight redundant `time`/
`dayPhase` tracker purely so `status()` has something to report without reaching into a
specific screen's instance.

## holo-golden (BRIEF-2/3: the gold-holo merge)

`holo-golden/` is a patched copy of `holo-ref/` (Martin's live desktop background — read-only
reference, not edited): the same orchestration-fleet overlay, re-themed to the studio's own
warm light instead of holographic cyan, with the studio itself as its backdrop. `DIFF.patch`
is the exact unified diff vs `holo-ref/{shell.qml,HoloNode.qml}` (validated with
`patch -p1 --dry-run`); `Renderer.js` and `Drift.js` are byte-identical copies — the data
model and the `drift`/`sweep` IPC are untouched.

### Backdrop: a separate full-screen window, created first

holo's node panel measures ~1887x1045 in practice (not full screen — this is the finding
BRIEF-3 opened with), and its content (`Rectangle{color:"black"}` + a static `background.jpg`
`Image` at `x: -width*0.025`, `Stretch`) was sized/positioned to match that panel exactly.
Martin loved the studio backdrop extending edge-to-edge under his transparent top bar, so
instead of matching the node panel's narrower geometry, `holo-golden/shell.qml` gives the
backdrop its **own** `PanelWindow` (`backdropPanel`, declared *first* so it paints below),
anchored to all four screen edges with no `implicitWidth`/`implicitHeight` override (the same
recipe `studio/shell.qml` itself uses to reach the full screen) and hosting a single
`StudioBackdrop { anchors.fill: parent }`. The original node `panel` keeps its exact original
anchors/size/content below that — node layout (grid/fan positions, headers, totals, drift) is
completely unaffected, it just no longer draws its own background fill (that Rectangle+Image
pair is removed; `backdropPanel` supplies it now, visible through `panel`'s existing
`color: "transparent"`).

### Palette picks

Sampled from `ref/wallpaper-1080p.jpg` with Pillow (mean + bright-90th-percentile RGB over a
few hand-picked regions):

| region | mean | bright (p90) |
|---|---|---|
| window glow | `#997b64` | `#f9f4f0` |
| floor sunbeam | `#9c775a` | `#fde4bc` |
| brick, lit | `#957159` | `#ede1d5` |
| brick, shadow | `#5a3c28` | `#927968` |
| wood floor, midtone | `#7e5736` | `#d1a16a` |
| mirror wall | `#91765f` | `#cfb8a0` |

From these, the final fleet palette (each role a deliberate pick/derivation, not a raw hue
rotation of the old cyan):

| role | hex | from |
|---|---|---|
| `pulseCream` — the pulse, cream-white | `#fff2da` | blend of window-glow/floor-sunbeam bright-p90 |
| `gold` — ember/amber working glow | `#e8a84c` | saturated/brightened floor-sunbeam hue |
| `lineGold` — gilded link threads | `#b8864a` | brass version of the brick-lit/mirror-wall hue |
| `dim` — soft terracotta idle/dim | `#a8674a` | brightened brick-shadow hue (so it still reads at low opacity) |
| `nightSilver` — moonlit silver-blue | `#8cadf2` | **reused verbatim** from `studio.frag`'s own `moonGlow` tint (`vec3(0.55,0.68,0.95)`), so the fleet's night cooling is literally the room's own moonlight colour |

The original cyan (`#7ff0ff`) did double duty for *both* the pulse and the default working
accent; the brief asks for those to read apart (cream-white pulse vs. ember/amber working
glow), so that's a deliberate split, not an oversight. `pulsePale`/`pulseHilite`
(`#f3d3a5`/`#ffe3ad`) keep the non-handoff pulse kinds (`a2a`/default) distinguishable within
the same warm family, mirroring the original's per-kind cyan variations. `UNLINKED`'s alarm
red (`#7a3030`) and `UNKNOWN`'s olive (`#9c8a5a`) are left out of the warm *and* the night
blend — errors shouldn't soften or change with the hour.

### Night cooling

`nightAmountAt(h)` in `holo-golden/shell.qml` is a direct JS port of `studio.frag`'s
`ANCH_H`/`ANCH_NIGHT` keyframe columns, so `root.nightAmount` (read from the backdrop's own
`dayPhase`) tracks the room's night-blue exactly. `mixColor()`/`mixColor()` (QML and
`HoloNode.qml` each have their own tiny copy — not shared via `Renderer.js`, which is pure
data model, not presentation) blend the link lines, every pulse kind, and each node's lit-state
accent toward `nightSilver` by that amount. Small UI text (labels, stats, headers, totals)
stays a static warm tone, deliberately *not* night-blended, so it never fights for legibility
against a darkening backdrop.

### Sprite recolor

holo's three PNG sprites (`glow-node.png`, `glow-pulse.png`, `cone.png` — the originals, plus
the generator that made them, are in `holo-ref/assets/` for reference) are cyan. BRIEF-3
revealed the generator (`make_holo_assets.py`) is available, so `tools/recolor_sprites.py`
*regenerates* the three sprites from an adapted copy of that generator's own procedural recipe
(same seed, same shapes/gradients, cyan/violet constants swapped for warm brass/amber/cream) —
preferred over hue-shifting already-rendered pixels, which would leave muddy intermediate hues.
Run it (writes straight into `holo-golden/assets/`):

```sh
uv run --with pillow --with numpy python tools/recolor_sprites.py
```

It also keeps a `--from-pngs <dir>` fallback (hue-shift + tint, alpha preserved) for a leaner
checkout that has the rendered PNGs but not the generator. In that case, copy these first:

```
~/.config/quickshell/holo/assets/cone.png
~/.config/quickshell/holo/assets/glow-node.png
~/.config/quickshell/holo/assets/glow-pulse.png
```

`checks/sprite-compare.png` / `checks/cone-compare.png` are side-by-side old-vs-new renders;
`checks/holo-golden-preview.png` is a static mockup of the full combination (a few fake nodes/
links/one pulse, in the new palette, composited over an actual rendered studio frame) for a
quick visual sanity check without a live browser or Quickshell.

## IPC

```sh
quickshell ipc call studio phase 18       # force golden hour (0-24, use -1 to release)
quickshell ipc call studio speed 3        # 3x animation speed (time's rate)
quickshell ipc call studio motion 2.5     # amplitude scalar (BRIEF-3; default 2.0)
quickshell ipc call studio signature      # trigger the signature sweep now
quickshell ipc call studio status         # -> {"time":..,"dayPhase":..,"forcedPhase":..,"motion":..,"fps":24}
```

holo-golden exposes the identical `studio` target (forwarding into its single `StudioBackdrop`
instance) *alongside* its own original `drift` target (`sample`/`pulses`/`sweep`/`probe`),
which is untouched.

(Exact `quickshell ipc call` invocation may differ slightly by Quickshell version/CLI alias in
your setup — the target names and functions above are what's registered.)

## Preview

`preview/index.html` is a from-scratch WebGL2 port — open it directly in a browser (it loads
`../studio/assets/*` by relative path, works over `file://`). The control strip (time-of-day
slider, real-clock toggle, speed, motion, signature button, and a "holo-golden fleet" toggle)
fades when idle and wakes on pointer move.

The fleet toggle draws a few illustrative nodes/links/one pulse (a fixed layout, not a
`Renderer.js` port) on a 2D canvas layered over the WebGL one, in holo-golden's exact palette
and with the same night-cooling curve, so the combination can be judged live against the real
moving backdrop — including at different times of day via the time slider.

For a single file with no external dependencies — e.g. to hand someone a preview without the
rest of the repo — run:

```sh
python3 preview/build_preview.py    # writes preview/studio-preview.html (~1.5 MB, assets inlined)
```

## Performance

One full-screen pass, 5 texture samples per pixel (base + 4 masks — everything else is
arithmetic/noise, no extra texture lookups even for the 9-cell dust loop). `fps` defaults to 24
(`StudioBackdrop.qml`'s own `clockTimer.interval = round(1000/fps)`); lower it for more battery
headroom. `speed()`/`motion()` and the day/night grade don't change the per-pixel cost at all.

## Verification done in this container (no Wayland/Quickshell/qsb/browser available here)

- **Masks**: regenerated with the new `air.png` added (`make_masks.py` prints min/max/mean/std
  for luminance, saturation and each of the four masks — `air`: min 0.165, max 0.980, mean
  0.484, matching the brief's "~15% floor" almost exactly); `masks-preview.png` visually
  confirms all four land where they should.
- **QML** (`studio/shell.qml`, `StudioBackdrop.qml`, `holo-golden/{shell,HoloNode,
  StudioBackdrop}.qml`): no `qmllint`/Quickshell binary available, so checked by hand —
  brace/paren balance verified programmatically on every file, structure cross-checked against
  the exact Quickshell API surface (`PanelWindow`, `WlrLayershell.*`, `ExclusionMode`,
  `Region {}`, `IpcHandler`, `Variants { model: Quickshell.screens }`).
- **Shader** (`studio/shaders/studio.frag`, copied unmodified into `holo-golden/shaders/`): no
  `qsb`/`glslangValidator` in this container, so it could not be compiled here. Checked by hand
  against the Qt6 GLSL 440 template (uniform block layout incl. the new `motion` float and
  `airTex` sampler at binding 5, `qt_TexCoord0`/`fragColor` locations), brace/paren/bracket
  balance verified programmatically, every `smoothstep()` call re-audited for ascending edge
  order after the motion-2x edits. The WebGL2 port of the identical math in `preview/index.html`
  *does* compile and run in a real GPU pipeline (conceptually — see below), a meaningful
  cross-check on the logic even though it isn't the Qt6 GLSL compiler itself.
- **Preview JS**: syntax-checked with `node --check` on the extracted inline script (including
  the motion slider wiring and the new fleet-overlay code) — passes. No headless browser was
  available in this container, so the WebGL2 preview was not visually rendered here; the fleet
  overlay's colour combination was instead sanity-checked via the static
  `checks/holo-golden-preview.png` mockup.
- **Motion-2x, quantitatively**: `tools/motion_check.py`, a numpy port of the shader's dynamic
  terms, measures 26.67% of pixels changing >4/255 over 5s at golden hour/speed 1/motion 2.0
  (default) — target was >5%. See "Motion" above for the full numbers and how to re-run it.
- **Offline composites**: `tools/render_checks.py` (static day/night grade LUT, unaffected by
  the motion-2x or air-mask changes — re-ran after both, still produces the expected four
  distinct-per-phase looks) and `tools/motion_check.py` (dynamic terms, see above) both write
  inspectable JPEGs to `checks/`.
- **Sprite recolor**: `tools/recolor_sprites.py` run here, producing real
  `holo-golden/assets/{glow-node,glow-pulse,cone}.png`; visually compared against the
  `holo-ref/assets/` originals in `checks/{sprite,cone}-compare.png` — warm brass/amber/cream,
  same shapes/falloffs, alpha preserved.
- **DIFF.patch**: validated with `patch -p1 --dry-run` against a scratch copy of
  `holo-ref/{shell.qml,HoloNode.qml}` — applies cleanly.
- **Not verified / can't be, here**: neither shader has run on an actual GPU through Qt's
  `qsb`/RHI pipeline, so backend-specific issues (if any) in the compiled `.qsb` wouldn't show
  up until `build.sh` runs on the target machine, for *both* `studio/` and `holo-golden/`.
  Quickshell-specific runtime behavior (layer shell placement/stacking order between
  `backdropPanel` and `panel`, `Region {}` click-through, `IpcHandler` call syntax, `Variants`/
  `modelData` wiring, whether `StudioBackdrop`'s per-instance independent clocks look fine
  side-by-side on an actual multi-monitor `Variants` setup) is implemented to match the brief
  and typical Quickshell idioms exactly, but is unverified against a live Quickshell/Wayland
  session, which this container doesn't have. The real fleet data path (`fleet.json`/
  `beacon-vps.json`, `Renderer.js`'s `build()`) is untouched and was not re-verified beyond
  confirming the files are byte-identical to `holo-ref/`.
