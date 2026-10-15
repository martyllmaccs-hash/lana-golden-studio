// holo-golden — the orchestration lattice, re-themed to match the living studio
// wallpaper behind it: a holographic view of the agent fleet across both machines,
// live from the Hermes session stores, now in warm brass/candle-gold instead of
// cyan (BRIEF-2/BRIEF-3's "gold-holo merge"). Patched copy of holo-ref/shell.qml --
// see DIFF.patch for the exact diff; data plumbing (fleet/beacon reads, Renderer.js,
// Drift.js, the `drift`/`sweep` IPC) is untouched.
//
// Data: ~/.local/state/holo/fleet.json (this machine, written by
// holo-collector.service) plus, when the local collector has not merged it yet,
// ~/.local/state/holo/beacon-vps.json (pushed from the runtime every minute).
//
// Every animation here is timer-driven. `SequentialAnimation on <property>` silently never
// ran in this Quickshell build, so motion comes from one 40 ms timer feeding wall time and
// `breathe`, which the items bind to.
import Quickshell
import Quickshell.Wayland
import Quickshell.Io
import QtQuick
import "Renderer.js" as Renderer
import "Drift.js" as Drift

ShellRoot {
  id: root

  readonly property string home: Quickshell.env("HOME")
  readonly property string stateDir: home + "/.local/state/holo/"
  readonly property string fleetPath: stateDir + "fleet.json"
  readonly property string beaconPath: stateDir + "beacon-vps.json"
  readonly property string assetDir: "file://" + home + "/.config/quickshell/holo-golden/assets/"

  property var fleet: null
  property var beacon: null
  property var view: []
  property var linkView: []
  property var particleView: []
  property var pulseState: null
  // Arrival "fire": every pulse lands at displayAt + 6 s (Renderer.pulseProgress).
  // Remember each landing (eventId -> {key, at}) so the receiving node can flare
  // briefly on impact, even after the particle itself has been retired.
  property var arrivals: ({})
  readonly property real impactDuration: 1.2
  onParticleViewChanged: {
    var next = {}, now = root.pulseNow
    for (var id in root.arrivals)
      if (now - root.arrivals[id].at < 3) next[id] = root.arrivals[id]
    for (var i = 0; i < root.particleView.length; i++) {
      var p = root.particleView[i]
      if (typeof p.eventId !== "string" || next[p.eventId]) continue
      var start = typeof p.displayAt === "number" ? p.displayAt : p.eventAt
      next[p.eventId] = {key: p.toId, at: start + 6}
    }
    root.arrivals = next
  }
  // 0..1 progress through the most recent impact on this node, or -1 if none.
  function impactFor(key) {
    var best = -1, now = root.pulseNow
    for (var id in root.arrivals) {
      var a = root.arrivals[id]
      if (a.key !== key) continue
      var t = (now - a.at) / root.impactDuration
      if (t >= 0 && t < 1 && (best < 0 || t < best)) best = t
    }
    return best
  }
  property var handoffView: []
  property var totals: ({})
  property real beaconAge: -1
  property bool everRead: false
  property int badReads: 0
  property int rev: 0
  property real pulseNow: Date.now() / 1000 // one non-looping traversal per event timestamp
  property real breathe: 0           // 0..1, 1.7 s cycle — drives node breathing
  property real driftT: 0            // decorative drift, independent of reported activity
  property bool vpsStale: true
  property bool localFresh: false
  property int omitted: 0
  property int collisions: 0

  // ---- warm palette (BRIEF-2/BRIEF-3 gold-holo merge) --------------------
  // Picked from ref/wallpaper-1080p.jpg's own light (sampled with Pillow --
  // see README "Palette picks" for the exact regions/hex output this is
  // drawn from): brass/amber in place of cyan, cream in place of cyan-pale.
  // Pulses, the link lines and every node's lit-state accent all cool
  // towards `nightSilver` as the room itself goes to moonlight, via
  // `nightAmount` below -- everything else (labels, stats, headers) stays a
  // static warm tone so small text never fights for legibility at night.
  readonly property color gold: "#e8a84c"         // ember/amber -- working glow (was cyan #7ff0ff)
  readonly property color dim: "#a8674a"          // soft terracotta -- idle/dim (was #3d6f7d / #2f7c8c)
  readonly property color lineGold: "#b8864a"      // thin gilded link threads (was rgba(47,124,140,.55))
  readonly property color pulseCream: "#fff2da"    // cream-white -- the standard (handoff) pulse
  readonly property color pulsePale: "#f3d3a5"     // pale warm gold -- a2a pulses (was #d8f6ff)
  readonly property color pulseHilite: "#ffe3ad"   // bright pale gold -- message pulses + totals text
  readonly property color nightSilver: "#8cadf2"   // moonlit silver-blue -- == studio's own moonGlow tint

  // 0 (day) .. 1 (deep night), same keyframes as studio.frag's ANCH_NIGHT
  // column, so the fleet's gold cools in lockstep with the room behind it.
  function nightAmountAt(h) {
    var H = [0.0, 5.0, 7.0, 12.0, 17.0, 19.5, 21.0, 24.0]
    var N = [1.00, 1.00, 0.00, 0.00, 0.00, 0.40, 0.90, 1.00]
    h = ((h % 24) + 24) % 24
    for (var i = 0; i < H.length - 1; i++) {
      if (h >= H[i] && h <= H[i + 1]) {
        var t = (h - H[i]) / Math.max(H[i + 1] - H[i], 0.0001)
        t = t * t * (3.0 - 2.0 * t)
        return N[i] + (N[i + 1] - N[i]) * t
      }
    }
    return N[0]
  }
  function mixColor(a, b, t) {
    return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t,
                    a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t)
  }
  function rgbaStr(c, a) {
    return "rgba(" + Math.round(c.r * 255) + "," + Math.round(c.g * 255) + ","
         + Math.round(c.b * 255) + "," + a + ")"
  }

  property real nightAmount: nightAmountAt(backdrop.dayPhase)
  readonly property color goldNow: mixColor(root.gold, root.nightSilver, root.nightAmount)
  readonly property color lineGoldNow: mixColor(root.lineGold, root.nightSilver, root.nightAmount)
  readonly property color pulseCreamNow: mixColor(root.pulseCream, root.nightSilver, root.nightAmount)
  readonly property color pulsePaleNow: mixColor(root.pulsePale, root.nightSilver, root.nightAmount)
  readonly property color pulseHiliteNow: mixColor(root.pulseHilite, root.nightSilver, root.nightAmount)
  readonly property color dimNow: mixColor(root.dim, root.nightSilver, root.nightAmount)

  function value(v) { return v === null || v === undefined ? "?" : v }
  // Pulse tint by event kind -- every colour already exists elsewhere in the
  // fleet's own (now warm) palette: handoff is the standard cream-white
  // pulse, a2a/message/smoke-test get their own existing accent so the
  // pulse stream still reads apart by kind, just within the gold family.
  function pulseColor(kind) {
    if (kind === "handoff") return root.pulseCreamNow
    if (kind === "a2a") return root.pulsePaleNow
    if (kind === "smoke_test") return root.dimNow
    return root.pulseHiliteNow
  }

  // Same backdrop control surface as the standalone studio/ config (just one
  // instance here, so no fan-out is needed -- see StudioBackdrop.qml).
  IpcHandler {
    target: "studio"

    function phase(h: real) { backdrop.forcedPhase = h }
    function speed(s: real) { backdrop.speed = s }
    function motion(m: real) { backdrop.motion = m }
    function signature() { backdrop.signature() }
    function status(): string {
      return JSON.stringify({
        time: backdrop.time, dayPhase: backdrop.dayPhase,
        forcedPhase: backdrop.forcedPhase, motion: backdrop.motion, fps: backdrop.fps
      })
    }
  }

  // Read-only runtime proof: actual transformed centres versus drawn endpoints.
  IpcHandler {
    target: "drift"
    function sample(): string {
      var samples = []
      for (var i = 0; i < root.view.length; i++) {
        var n = root.view[i], item = nodeItems.itemAt(i)
        if (!item) continue
        var pt = item.mapToItem(canvas, n.labelOnLeft ? 245 : 55, 55)
        samples.push({key:n.key, x:item.x, y:item.y,
                      actual:[pt.x,pt.y], endpoint:[root.cx(n),root.cy(n)]})
      }
      return JSON.stringify({time:root.driftT,nodes:samples})
    }
    function pulses(): string {
      return JSON.stringify({now:root.pulseNow,particles:root.particleView.map(function(e){
        return {id:e.eventId,from:e.fromId,to:e.toId,progress:Renderer.pulseProgress(e,root.pulseNow),
                point:root.pulsePoint(e,Renderer.pulseProgress(e,root.pulseNow)||0)};
      })})
    }
    function sweep(): string {
      var now=root.pulseNow, evs=[];
      for(var i=0;i<root.linkView.length;i++){var l=root.linkView[i];
        evs.push({eventId:"sweep:"+now+":"+i,eventAt:now,active:true,fromId:l.fromId,toId:l.toId,kind:"smoke_test",crossMachine:!!l.crossMachine});}
      root.pulseState=Renderer.advancePulses(root.pulseState,evs,now,root.view.map(function(n){return n.key;}));
      root.particleView=root.pulseState.particles;
      return "fired "+evs.length+" links";
    }
    function probe(): string {
      var now=root.pulseNow, a=Renderer.key("vps","default"), b=Renderer.key("p1","p1-mila");
      var e={eventId:"visual-probe:"+now,eventAt:now-3,active:true,fromId:a,toId:b,kind:"smoke_test",crossMachine:true};
      root.pulseState=Renderer.advancePulses(root.pulseState,[e],now,root.view.map(function(n){return n.key;}));
      root.particleView=root.pulseState.particles;
      return e.eventId
    }
  }

  function ageStr(s) {
    if (s === null || s === undefined || s < 0) return "--"
    if (s < 90) return Math.round(s) + "S"
    if (s < 5400) return Math.round(s / 60) + "M"
    return (s / 3600).toFixed(1) + "H"
  }

  // Keep observed journeys; deleting an endpoint still deletes its effects.
  function ingest(text, fromBeacon, exitOk) {
    var snapshot = Renderer.ingest(text, fromBeacon ? root.beacon : root.fleet,
                                   fromBeacon, Date.now() / 1000, exitOk)
    if (!snapshot.valid) root.badReads++
    if (fromBeacon) root.beacon = snapshot
    else root.fleet = snapshot
    root.everRead = root.everRead || snapshot.valid
    root.rebuild()
  }
  function rebuild() {
    var result = Renderer.build(root.fleet, root.beacon, Date.now() / 1000, panel.width)
    root.view = result.view
    root.linkView = result.links
    root.pulseState = Renderer.advancePulses(root.pulseState, result.particles, root.pulseNow,
      result.view.map(function(n){return n.key;}))
    root.particleView = root.pulseState.particles
    root.handoffView = result.handoffs
    root.totals = result.totals
    root.beaconAge = result.beaconAge
    root.vpsStale = result.vpsStale
    root.localFresh = result.localFresh
    root.omitted = result.omitted
    root.collisions = result.collisions
    root.rev++
    canvas.requestPaint()
  }

  Process {
    id: fleetProc
    command: ["cat", root.fleetPath]
    stdout: StdioCollector { id: fleetOut }
    onExited: (exitCode, exitStatus) => root.ingest(fleetOut.text, false, exitCode === 0)
  }
  Process {
    id: beaconProc
    command: ["cat", root.beaconPath]
    stdout: StdioCollector { id: beaconOut }
    onExited: (exitCode, exitStatus) => root.ingest(beaconOut.text, true, exitCode === 0)
  }

  Timer {
    interval: 2000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: {
      if (!fleetProc.running) fleetProc.running = true
      if (!beaconProc.running) beaconProc.running = true
    }
  }
  Timer {
    interval: 40
    running: true
    repeat: true
    onTriggered: {
      root.pulseNow = Date.now() / 1000
      root.breathe = (root.breathe + 0.016 / 1.7) % 1.0
      root.driftT += 0.04
      canvas.requestPaint()
    }
  }
  Timer {
    interval: 1000
    running: true
    repeat: true
    onTriggered: root.rebuild()      // flash decay + beacon staleness keep moving
  }

  function nodeById(id) {
    for (var i = 0; i < root.view.length; i++) if (root.view[i].key === id) return root.view[i]
    return null
  }
  function drift(n) { return Drift.offset(n.key, root.driftT) }
  function nodeScale(n) {
    var i = root.view.indexOf(n)
    var beat = 0.5 + 0.5 * Math.sin((root.breathe + (i % 7) * 0.14) * 6.283185)
    return n.layoutScale * Renderer.breathScale(n.alive, n.working, n.state, beat, n.activity)
  }
  function cx(n) { return n.x + root.drift(n)[0] + (n.labelOnLeft ? 245 : 55) * root.nodeScale(n) }
  function cy(n) { return n.y + root.drift(n)[1] + 55 * root.nodeScale(n) }
  function linkControl(l, a, b) {
    if(l.peer || l.crossMachine) return [(root.cx(a)+root.cx(b))/2, -80]
    return [a.machine === "vps" ? 30 : panel.width-30, (root.cy(a)+root.cy(b))/2]
  }
  function pulsePoint(l, t) {
    var a = root.nodeById(l.fromId), b = root.nodeById(l.toId)
    if (!a || !b) return [0, 0]
    var x0 = root.cx(a), y0 = root.cy(a), x2 = root.cx(b), y2 = root.cy(b)
    var control = root.linkControl(l,a,b)
    var x1 = control[0], y1 = control[1]
    var u = 1 - t
    return [u * u * x0 + 2 * u * t * x1 + t * t * x2, u * u * y0 + 2 * u * t * y1 + t * t * y2]
  }

  // ================================================================ surface
  // The living studio backdrop is a SEPARATE full-screen Background-layer
  // window, created first so it paints below the nodes panel. holo's node
  // panel measures ~1887x1045 (not full screen -- see BRIEF-3's finding),
  // but Martin loved the studio extending edge-to-edge under his transparent
  // top bar, so the backdrop gets its own window sized by anchors alone
  // (no implicitWidth/Height override) instead of matching the node panel's
  // narrower geometry. Node layout is completely unaffected: `panel` below
  // keeps its exact original anchors/size/content, just without its own
  // background fill.
  PanelWindow {
    id: backdropPanel

    anchors { top: true; bottom: true; left: true; right: true }
    color: "black"
    exclusionMode: ExclusionMode.Ignore
    mask: Region {}

    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.namespace: "holo-golden-backdrop"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    StudioBackdrop {
      id: backdrop
      anchors.fill: parent
    }
  }

  PanelWindow {
    id: panel

    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    exclusiveZone: 0
    implicitWidth: 1920
    implicitHeight: 1045

    // Background layer, the same slot the Soviet panel used: above the wallpaper,
    // behind every normal window, so it reads as a live desktop background rather
    // than an overlay sitting on top of the user's work.
    WlrLayershell.layer: WlrLayer.Background
    WlrLayershell.namespace: "holo-golden"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    mask: Region {}

    // The live studio backdrop (backdropPanel, above) now supplies the
    // background photo + light/motion across the full screen; this panel
    // stays transparent and only carries the fleet overlay.

    // ------------------------------------------------------------- links
    Canvas {
      id: canvas
      anchors.fill: parent
      renderStrategy: Canvas.Cooperative
      Connections { target: root; function onRevChanged() { canvas.requestPaint() } }
      onPaint: {
        var ctx = getContext("2d")
        ctx.clearRect(0, 0, width, height)
        ctx.lineWidth = 1
        for (var i = 0; i < root.linkView.length; i++) {
          var l = root.linkView[i]
          var a = root.nodeById(l.fromId), b = root.nodeById(l.toId)
          if (!a || !b) continue
          var x0 = root.cx(a), y0 = root.cy(a), x2 = root.cx(b), y2 = root.cy(b)
          // The inter-machine arc runs high across the black band, above her head.
          var control = root.linkControl(l,a,b)
          var x1 = control[0], y1 = control[1]
          ctx.beginPath()
          ctx.moveTo(x0, y0)
          ctx.quadraticCurveTo(x1, y1, x2, y2)
          // Quiet solid topology lines; inference stays in metadata, not dashes.
          // Thin gilded threads in the haze -- cools to moonlit silver with the room.
          ctx.strokeStyle = root.rgbaStr(root.lineGoldNow, 0.55)
          ctx.setLineDash([])
          ctx.stroke()
          ctx.setLineDash([])
        }
      }
    }

    // One crisp sprite per link, no echo copies. Observation starts a full journey.
    Repeater {
      model: root.particleView
      Item {
        id: pulseItem
        property var evt: modelData
        property var eventProgress: Renderer.pulseProgress(evt, root.pulseNow)
        property string kind: typeof evt.kind === "string" ? evt.kind : "message"
        property color tint: root.pulseColor(kind)
        property var pt: root.pulsePoint(evt, eventProgress === null ? 0 : eventProgress)
        visible: eventProgress !== null
        x: 0; y: 0

        Image {
          source: root.assetDir + "glow-pulse.png"
          width: 34; height: 34
          smooth: true
          opacity: 0.95
          x: pulseItem.pt[0] - width / 2
          y: pulseItem.pt[1] - height / 2
        }
      }
    }

    // ------------------------------------------------------------- nodes
    Repeater {
      id: nodeItems
      model: root.view
      HoloNode {
        x: modelData.x + root.drift(modelData)[0]
        y: modelData.y + root.drift(modelData)[1]
        label: modelData.label; word: modelData.word; state: modelData.state
        detail: modelData.detail; role: modelData.role; machine: modelData.machine
        ageS: modelData.ageS === null ? -1 : modelData.ageS
        tokens: modelData.tokens; calls5h: modelData.calls5h; apiCalls: modelData.apiCalls
        lease: modelData.lease; alive: modelData.alive; flash: modelData.flash
        working: modelData.working
        activity: modelData.activity === undefined || modelData.activity === null ? 0 : modelData.activity
        toolActive: modelData.toolActive === true
        disc: modelData.disc
        layoutScale: modelData.layoutScale
        labelOnLeft: modelData.labelOnLeft === true
        breathe: root.breathe
        phase: (index % 7) * 0.14
        glowSprite: root.assetDir + "glow-node.png"
        nightAmount: root.nightAmount
        impactT: root.impactFor(modelData.key)
      }
    }

    // ------------------------------------------------------------ headers
    // Static warm brass (not night-blended): small UI text stays legible and
    // steady regardless of time of day, only the fleet's own glow cools.
    Text {
      x: 395 - width / 2; y: 120
      text: "VPS · RUNTIME"
      color: "#c9975f"
      font.family: "Noto Sans Mono"; font.pixelSize: 14; font.letterSpacing: 4
    }
    Text {
      x: panel.width - 395 - width / 2; y: 120
      text: "P1 · WORKSTATION"
      color: "#c9975f"
      font.family: "Noto Sans Mono"; font.pixelSize: 14; font.letterSpacing: 4
    }
    // totals
    Column {
      x: (panel.width - width) / 2; y: 20
      spacing: 2
      Text {
        text: "NODES " + root.value(root.totals.nodes_online)
              + "/" + root.value(root.totals.nodes_total)
              + "   WORKING " + (root.value(root.totals.working) + (root.totals.working_unknown ? " +?" : ""))
        color: "#ffe3ad"
        font.family: "Noto Sans Mono"; font.pixelSize: 13; font.letterSpacing: 2
      }
      Text {
        text: "VISIBLE TOKENS " + (root.totals.tokens_today !== undefined && root.totals.tokens_today !== null ? (root.totals.tokens_today / 1e6).toFixed(1) + "M" : "-")
              + "   BEACON " + (root.beaconAge >= 0 ? root.ageStr(root.beaconAge) : "NONE")
        color: root.vpsStale ? "#d46a2b" : "#c9975f"
        font.family: "Noto Sans Mono"; font.pixelSize: 12; font.letterSpacing: 2
      }
    }


  }
}
