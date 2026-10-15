#version 440

// Golden Hour Studio -- living wallpaper fragment shader.
//
// Single full-screen pass over the base photograph. Nothing ever displaces
// qt_TexCoord0 -- the dancer is sampled at her exact photographed position,
// every frame, so she can never warp. All motion is additive light, soft
// multiplicative shadow, and procedural particles layered on top.

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;            // seconds, monotonic, already includes the speed multiplier
    float dayPhase;         // hours 0..24, wraps at 24
    float signatureStart;    // `time` value when the signature moment fired; -1000 = idle
    vec2 resolution;        // render target size, px
    float motion;           // amplitude scalar, separate from `time`'s rate; default 2.0
};

layout(binding = 1) uniform sampler2D baseTex;
layout(binding = 2) uniform sampler2D lightTex;
layout(binding = 3) uniform sampler2D floorTex;
layout(binding = 4) uniform sampler2D windowsTex;
layout(binding = 5) uniform sampler2D airTex;

// ---------------------------------------------------------------- noise --
float hash12(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float amp = 0.55;
    for (int i = 0; i < 3; i++) {
        v += amp * vnoise(p);
        p *= 2.03;
        amp *= 0.5;
    }
    return v;
}

// ------------------------------------------------- cyclic day-grade LUT --
// hour -> tint RGB, exposure, beam intensity, dust visibility, night-blue amount.
// Explicit per-phase tints (rather than one warm<->cool scalar) so morning
// reads as pale cream, golden hour as amber, dusk as rose-amber and night
// as moonlit blue -- four distinct hues, not one axis.
const int NANCH = 8;
const float ANCH_H[8]  = float[8](0.0,  5.0,  7.0,  12.0, 17.0, 19.5, 21.0, 24.0);
const float ANCH_TR[8] = float[8](0.72, 0.72, 0.93, 1.00, 1.12, 1.08, 0.78, 0.72);
const float ANCH_TG[8] = float[8](0.80, 0.80, 0.95, 1.00, 0.98, 0.82, 0.82, 0.80);
const float ANCH_TB[8] = float[8](1.04, 1.04, 0.99, 1.00, 0.80, 0.78, 1.05, 1.04);
const float ANCH_EXP[8]   = float[8](0.44, 0.44, 0.80, 1.00, 1.06, 0.80, 0.52, 0.44);
const float ANCH_BEAM[8]  = float[8](0.20, 0.20, 0.68, 0.85, 1.00, 0.55, 0.28, 0.20);
const float ANCH_DUST[8]  = float[8](0.10, 0.10, 0.55, 0.78, 1.00, 0.68, 0.16, 0.10);
const float ANCH_NIGHT[8] = float[8](1.00, 1.00, 0.00, 0.00, 0.00, 0.40, 0.90, 1.00);

void gradeAt(float h, out vec3 tint, out float exposure, out float beamMul, out float dustMul, out float nightBlue) {
    tint = vec3(ANCH_TR[0], ANCH_TG[0], ANCH_TB[0]);
    exposure = ANCH_EXP[0]; beamMul = ANCH_BEAM[0];
    dustMul = ANCH_DUST[0]; nightBlue = ANCH_NIGHT[0];
    for (int i = 0; i < NANCH - 1; i++) {
        if (h >= ANCH_H[i] && h <= ANCH_H[i + 1]) {
            float t = (h - ANCH_H[i]) / max(ANCH_H[i + 1] - ANCH_H[i], 0.0001);
            t = t * t * (3.0 - 2.0 * t);
            tint = vec3(
                mix(ANCH_TR[i], ANCH_TR[i + 1], t),
                mix(ANCH_TG[i], ANCH_TG[i + 1], t),
                mix(ANCH_TB[i], ANCH_TB[i + 1], t)
            );
            exposure = mix(ANCH_EXP[i], ANCH_EXP[i + 1], t);
            beamMul = mix(ANCH_BEAM[i], ANCH_BEAM[i + 1], t);
            dustMul = mix(ANCH_DUST[i], ANCH_DUST[i + 1], t);
            nightBlue = mix(ANCH_NIGHT[i], ANCH_NIGHT[i + 1], t);
            return;
        }
    }
}

void main() {
    vec2 uv = qt_TexCoord0;
    float aspect = resolution.x / max(resolution.y, 1.0);
    vec2 auv = vec2(uv.x * aspect, uv.y);

    vec4 baseColor = texture(baseTex, uv);
    float lightMask = texture(lightTex, uv).r;
    float floorMask = texture(floorTex, uv).r;
    float windowsMask = texture(windowsTex, uv).r;
    float airMask = texture(airTex, uv).r;
    float baseLum = dot(baseColor.rgb, vec3(0.299, 0.587, 0.114));

    float h = mod(dayPhase, 24.0);
    vec3 gradeTint;
    float exposure, beamMul, dustMul, nightBlue;
    gradeAt(h, gradeTint, exposure, beamMul, dustMul, nightBlue);

    vec3 col = baseColor.rgb;

    // ---- 6a. signature envelope (computed early so other effects can lean on it) ----
    float sig = 0.0;
    float sweepD = 0.0;
    {
        const float dur = 6.5;
        float elapsed = time - signatureStart;
        if (elapsed >= 0.0 && elapsed <= dur) {
            float prog = elapsed / dur;
            float envelope = smoothstep(0.0, 0.18, prog) * (1.0 - smoothstep(0.80, 1.0, prog));
            float sweepX = mix(-0.30, 1.30, prog);
            float d = (uv.x + 0.16 * uv.y) - sweepX;
            float band = exp(-(d * d) / (2.0 * 0.05 * 0.05));
            sig = band * envelope;
            sweepD = envelope;
        }
    }

    // ---- 1. breathing light shafts: thin-cloud shimmer + soft radiating rays ----
    // Drift rates doubled vs the original subtle pass (BRIEF-3 motion-2x); `motion`
    // (final multiplier below) separately doubles the *visible amplitude*, so the
    // two read as "twice as fast AND twice as strong", not just faster.
    vec2 lightDir = normalize(vec2(1.0, 0.35));
    float shimmer = fbm(auv * 3.1 - lightDir * time * 0.040);
    float breathe = 0.78 + 0.34 * shimmer;
    vec2 raySrc = vec2(-0.05 * aspect, 0.08);
    vec2 toP = auv - raySrc;
    float ang = atan(toP.y, toP.x);
    // a genuine bounded sweep (a few degrees, ~7 min period) layered under the
    // faster shimmer-phase drift already in ray0/ray1 below.
    float raySweep = radians(4.0) * sin(time * 0.015);
    float angS = ang + raySweep;
    float ray0 = 1.0 - smoothstep(0.0, 0.32, abs(sin((angS - 0.28) * 7.0 + time * 0.06)));
    float ray1 = 1.0 - smoothstep(0.0, 0.27, abs(sin((angS - 0.55) * 9.0 - time * 0.044)));
    float rays = (ray0 + 0.7 * ray1) * smoothstep(0.0, 0.5, lightMask);
    float beamStrength = (0.65 * breathe + 0.5 * rays) * lightMask * beamMul;
    vec3 beamColor = mix(vec3(1.0, 0.93, 0.78), vec3(0.80, 0.88, 1.0), nightBlue);
    // Already-blown-out highlights (the windows) can't get any brighter without
    // clipping flat, so additive beam light fades out where the photo is already
    // near-white.
    float beamAtten = pow(1.0 - baseLum, 2.0);
    col += beamColor * beamStrength * 0.22 * motion * beamAtten;
    col += vec3(1.0, 0.95, 0.82) * sig * (0.28 + 0.5 * lightMask); // sun-break sweep glow

    // ---- 2. cloud shadows: large soft dapple drifting left -> right ----
    vec2 cloudDir = normalize(vec2(1.0, 0.18));
    const float cloudPeriod = 30.0; // seconds -- halved (doubled rate) for motion-2x
    float cloud = fbm(auv * 1.15 - cloudDir * (time / cloudPeriod) * 1.4 + 11.0);
    float cloudShadow = min(smoothstep(0.42, 0.62, cloud) * 0.10 * motion, 0.6); // ~20% at default motion
    col *= (1.0 - cloudShadow);

    // ---- 3. dust motes: hash-based procedural particles, 3x3 grid-cell lookup ----
    // airMask is a much wider, lower-threshold "lit volume" than lightMask (see
    // tools/make_masks.py) -- it already carries a ~15% floor at its own darkest,
    // so motes read faintly through the whole sunlit side of the room, not just
    // inside the tight beam cores.
    float dust = 0.0;
    {
        vec2 grid = vec2(14.0, 8.0); // 112 cells ~= mote count target
        vec2 cell0 = floor(uv * grid);
        float twinkleBoost = 1.0 + 0.6 * sig;
        for (int dy = -1; dy <= 1; dy++) {
            for (int dx = -1; dx <= 1; dx++) {
                vec2 cell = cell0 + vec2(float(dx), float(dy));
                vec2 seed = hash22(cell + 0.5);
                float riseSpeed = 0.020 + seed.x * 0.024;
                float yLocal = fract(seed.y + time * riseSpeed);
                float wanderPhase = seed.x * 62.831853;
                float wx = 0.30 * sin(time * (0.10 + 0.08 * seed.y) + wanderPhase);
                vec2 moteUV;
                moteUV.x = (cell.x + 0.5 + wx) / grid.x;
                moteUV.y = (cell.y + (1.0 - yLocal)) / grid.y;
                vec2 d = uv - moteUV;
                d.x *= aspect;
                float sizeHash = hash12(cell + 3.3);
                // most motes stay small; roughly one in five blooms into a
                // soft bokeh disc up to ~3x the base size.
                float sizeMul = sizeHash > 0.80 ? mix(1.6, 3.0, (sizeHash - 0.80) / 0.20) : 1.0;
                float size = mix(0.0016, 0.0040, seed.y) * sizeMul;
                float fall = exp(-dot(d, d) / (size * size));
                float twinkle = (0.55 + 0.45 * sin(time * (1.3 + seed.x * 1.6) + wanderPhase)) * twinkleBoost;
                twinkle *= mix(1.0, 0.7, step(1.0, sizeMul)); // bigger bokeh motes read calmer
                dust += fall * twinkle;
            }
        }
        dust = min(dust, 1.4);
    }
    vec3 moteColor = mix(vec3(1.0, 0.86, 0.55), vec3(0.75, 0.82, 0.95), nightBlue);
    col += moteColor * dust * airMask * dustMul * 0.55 * motion;

    // ---- 4. floor sheen: faint shimmer along existing wood highlights ----
    vec2 streakDir = normalize(vec2(1.0, 0.22));
    float sheenWave = 0.5 + 0.5 * sin(dot(auv, streakDir) * 26.0 - time * 0.24);
    float sparkle = hash12(floor(auv * 180.0) + floor(time * 0.6));
    float sheen = floorMask * (0.5 * sheenWave + 0.5 * smoothstep(0.88, 1.0, sparkle));
    col += vec3(1.0, 0.94, 0.80) * sheen * 0.05 * beamMul * motion;

    // ---- 5. time-of-day colour grade ----
    col *= gradeTint;
    col *= exposure;

    // the photo's own baked-in sunbeam patch on the floor recedes at night too
    col *= (1.0 - nightBlue * floorMask * 0.35);

    // moonlit windows + a kept warm glow on her so she stays the focus at night
    vec3 moonGlow = vec3(0.55, 0.68, 0.95) * windowsMask * nightBlue * 0.30;
    vec3 herGlow = vec3(1.0, 0.82, 0.58) * lightMask * nightBlue * 0.085;
    col += moonGlow + herGlow;

    col = clamp(col, 0.0, 1.0);
    fragColor = vec4(col, baseColor.a) * qt_Opacity;
}
