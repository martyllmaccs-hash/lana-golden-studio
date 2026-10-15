// HoloNode — one agent in the orchestration lattice: a glowing disc, a name, a state
// word, and the numbers behind it. Idle nodes are dim; working nodes breathe.
// Patched for holo-golden (BRIEF-2/BRIEF-3): warm brass/amber accents in place of
// cyan, cooling towards moonlit silver-blue at night via `nightAmount`. UNLINKED
// stays a static alarm red regardless of time of day -- errors shouldn't soften.
import QtQuick
import "Renderer.js" as Renderer

Item {
  id: node

  property string label: ""
  property string word: ""
  property string state: "UNKNOWN"      // ACTIVE | TOOLING | THINKING | IDLE | OFFLINE | UNLINKED
  property string detail: ""
  property string role: ""
  property string machine: ""
  property real ageS: -1
  property var tokens: null
  property var calls5h: null
  property var apiCalls: null
  property var lease: null
  property var alive: null
  property real activity: 0          // 0..1 reported effort: scales breathing/glow beyond the plain working flag
  property bool toolActive: false    // a dispatched tool call is genuinely in flight right now
  property real flash: 0             // 1.0 right after a handoff lands on this node
  property real breathe: 0           // 0..1 from the shell's 40 ms timer
  property real phase: 0             // per-node offset so the fleet does not pulse in lockstep
  property string glowSprite: ""
  property real disc: 54
  property bool labelOnLeft: false
  property real nightAmount: 0       // 0 (day) .. 1 (deep night), from the shell's studio-backdrop phase
  property real impactT: -1          // 0..1 progress of a pulse landing here, -1 = none
  // sharp attack (~85 ms), soft quadratic release over the rest of 1.2 s
  readonly property real impact: impactT < 0 ? 0 : (impactT < 0.07 ? impactT / 0.07 : Math.pow(1 - impactT, 2))
  readonly property color impactColor: node.mixColor("#fff2da", node.nightSilver, node.nightAmount * 0.7)

  property bool working: state === "ACTIVE" || state === "TOOLING" || state === "THINKING" || state === "WORKING"
  readonly property real beat: 0.5 + 0.5 * Math.sin((node.breathe + node.phase) * 6.283185)
  readonly property color nightSilver: "#8cadf2"
  function mixColor(a, b, t) {
    return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t,
                    a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t)
  }
  readonly property color accent: {
    if (state === "UNLINKED") return "#7a3030"   // alarm red stays put at any hour
    var base = (state === "OFFLINE" || state === "IDLE") ? "#a8674a"   // soft terracotta
      : state === "UNKNOWN" ? "#9c8a5a"                                 // warm olive
      : state === "THINKING" ? "#f3d3a5"                                // pale warm gold
      : "#e8a84c"                                                       // ember/amber -- working
    return node.mixColor(base, node.nightSilver, node.nightAmount)
  }
  readonly property real lit: working ? 1.0 : (state === "IDLE" ? 0.42 : 0.30)

  property real layoutScale: 1
  implicitWidth: 300
  implicitHeight: 110
  transformOrigin: Item.TopLeft

  // halo — a working node's glow swells and brightens with how hard it is
  // reported to be working, not just a flat on/off.
  Image {
    anchors.centerIn: parent
    anchors.horizontalCenterOffset: node.labelOnLeft ? 95 : -95
    source: node.glowSprite
    width: node.disc * (node.working ? 3.6 + 0.9 * node.activity : 2.8)
    height: width
    opacity: node.lit * (0.55 + 0.25 * node.flash + 0.2 * node.activity)
    smooth: true
    Behavior on width { NumberAnimation { duration: 400 } }
    Behavior on opacity { NumberAnimation { duration: 500 } }
  }

  // breathing on the working nodes — timer-driven, not a property animation:
  // `SequentialAnimation on <prop>` silently never ran in this Quickshell build.
  scale: node.layoutScale * Renderer.breathScale(node.alive, node.working, node.state, node.beat, node.activity)

  // disc
  Rectangle {
    id: disc
    x: (node.labelOnLeft ? 245 : 55) - node.disc / 2
    y: (parent.height - node.disc) / 2
    width: node.disc
    height: node.disc
    radius: node.disc / 2
    color: "#140d08"
    border.width: node.working ? 2 : 1
    border.color: Qt.rgba(node.accent.r, node.accent.g, node.accent.b, 0.35 + 0.65 * node.lit)
    Behavior on border.color { ColorAnimation { duration: 400 } }
  }
  Rectangle {
    anchors.centerIn: disc
    width: node.disc * 0.44
    height: width
    radius: width / 2
    color: node.accent
    opacity: node.lit * (node.state === "OFFLINE" ? 0.35 : 0.9)
    Behavior on opacity { NumberAnimation { duration: 400 } }
  }
  // ---- impact: the node fires briefly when a pulse lands on it ----------
  // No Behaviors here on purpose: they would smear a 1.2 s event.
  Image {                                    // flare: halo swells and brightens
    anchors.centerIn: disc
    source: node.glowSprite
    width: node.disc * (2.6 + 2.2 * node.impact)
    height: width
    opacity: 0.95 * node.impact
    visible: node.impact > 0.01
    smooth: true
  }
  Rectangle {                                // shockwave: one thin ring expands and fades
    anchors.centerIn: disc
    width: node.disc * (1.0 + 1.9 * Math.max(0, node.impactT))
    height: width
    radius: width / 2
    color: "transparent"
    border.width: 1.5
    border.color: node.impactColor
    opacity: node.impactT < 0 ? 0 : 0.85 * (1 - node.impactT)
    visible: node.impactT >= 0
  }
  Rectangle {                                // core flashes cream-white
    anchors.centerIn: disc
    width: node.disc * (0.44 + 0.16 * node.impact)
    height: width
    radius: width / 2
    color: node.impactColor
    opacity: node.impact
    visible: node.impact > 0.01
  }

  // lease ring: a turn is held on this node right now
  Rectangle {
    anchors.centerIn: disc
    width: node.disc + 14
    height: width
    radius: width / 2
    color: "transparent"
    border.width: 1
    border.color: node.mixColor(Qt.rgba(1.0, 0.890, 0.678, 1.0), node.nightSilver, node.nightAmount)
    opacity: node.lease === true ? 0.35 + 0.45 * node.beat : 0.0
    visible: node.lease === true
  }
  // tool-activity ring: a dispatched tool call is genuinely running right now,
  // independent of any lease -- the signal that used to go dark mid-task.
  Rectangle {
    anchors.centerIn: disc
    width: node.disc + 24
    height: width
    radius: width / 2
    color: "transparent"
    border.width: 2
    border.color: node.accent
    opacity: node.toolActive === true ? 0.25 + 0.4 * node.beat : 0.0
    visible: node.toolActive === true
  }

  Column {
    x: node.labelOnLeft ? 6 : 95
    width: 199
    y: 14
    spacing: 1
    Text {
      width: parent.width
      horizontalAlignment: node.labelOnLeft ? Text.AlignRight : Text.AlignLeft
      elide: Text.ElideRight
      text: node.label
      color: node.working ? "#fff6e8" : "#c9a688"
      font.family: "Noto Sans Mono"; font.pixelSize: 17; font.bold: true; font.letterSpacing: 2
    }
    Text {
      width: parent.width
      horizontalAlignment: node.labelOnLeft ? Text.AlignRight : Text.AlignLeft
      elide: Text.ElideRight
      text: node.word + (node.role === "ORCHESTRATOR" ? "  ◆" : "")
      color: node.accent
      font.family: "Noto Sans Mono"; font.pixelSize: 13; font.letterSpacing: 2
      opacity: 0.55 + 0.45 * node.lit
    }
    Text {
      width: parent.width
      horizontalAlignment: node.labelOnLeft ? Text.AlignRight : Text.AlignLeft
      elide: Text.ElideRight
      text: {
        var bits = []
        if (node.calls5h === null) bits.push("--/5H CALLS")
        else bits.push(node.calls5h + "/5H CALLS")
        bits.push(node.tokens === null ? "? TOK" : (node.tokens / 1000).toFixed(0) + "K TOK")
        if (node.alive === null) bits.push("LIVE ?")
        return bits.join(" · ")
      }
      color: "#a08060"
      font.family: "Noto Sans Mono"; font.pixelSize: 10; font.letterSpacing: 1
    }
  }
}
