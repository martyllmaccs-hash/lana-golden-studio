# Brief 3 — motion 2x, then the gold-holo merge (BRIEF-2.md)

## Measured on the real P1 (Intel UHD 630, 1920x1080, golden hour phase 17.5, speed 3)
Screenshots 1 s apart: only 0.22% of pixels changed by >4/255; over 5 s, 2.1%. Martin, looking at the
screen: "I can't see any motion". The light mask covers little (mean 0.13; only 17% of pixels >0.3),
so beams and dust exist only in a small area, and amplitudes are tiny (beam add *0.22, cloud max 10%,
sheen *0.05, dust size 0.0016-0.004).

## Fix first: Martin asked for "motion 2x"
Make the motion clearly perceptible at speed 1, still elegant (no strobing, no fast flicker):
- Double the *visible amplitude* of every effect, and roughly double drift rates (beam shimmer,
  cloud drift, mote rise/wander, sheen travel). Cloud shadows: up to ~20% darkening, period ~30 s.
- Dust: more visible. Bigger range of sizes (some soft bokeh motes up to ~3x current), a slightly wider
  lit region for them (use a softened/expanded version of the light mask, e.g. a `pow(mask, 0.5)` or a
  separately generated wider "air" mask from make_masks.py covering the whole sunlit volume between the
  windows and her), and keep a faint floor of visibility outside the beams (~15%) so the air reads.
- Beams: make the radiating rays readable as volumetric god-rays in the haze, slowly sweeping a few
  degrees. Avoid adding to already-white areas (left windows are blown out): attenuate additive light
  by `(1 - luminance(base))^2` or similar so highlights don't clip flat.
- Add a `motion` uniform/property (default 2.0 = this new level; 1.0 ≈ old subtle level scaled) controlled
  over IPC `studio motion <x>` — it scales amplitudes, separate from `speed` (time rate).
- Mirror the same in preview/ and rebuild preview/studio-preview.html.
- Verify numerically with an offline numpy approximation or at least reason it through; target on the real
  screen: >5% of pixels changing >4/255 over 5 s at golden hour, speed 1.

## Then: do BRIEF-2.md (gold-holo merge)
The original cyan sprites are now in `holo-ref/assets/` (cone.png, glow-node.png, glow-pulse.png, plus
`make_holo_assets.py` which generated them — prefer adapting that generator to warm colours over hue-
shifting). holo's background Image previously sat at x: -width*0.025 with Stretch; the studio backdrop
should simply fill the panel. holo's panel is ~1887 px wide; make the studio backdrop extend to the full
screen width if that can be done without changing node layout (e.g. a separate full-screen Background
layer window for the backdrop inside the same config, nodes in the existing panel above it, both on
WlrLayer.Background, backdrop created first). Martin loved that the studio extends under his transparent
top bar — keep that.

Report: files changed, verified vs unverified.
