import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Io

ShellRoot {
    id: root

    // ---- shared control surface ------------------------------------------
    // The actual animation clock now lives inside each StudioBackdrop
    // instance (one per screen, see Variants below) so the component is a
    // true drop-in elsewhere (holo-golden/). These properties are bound
    // one-way into every instance so one IPC call still reaches every
    // screen; `time`/`dayPhase` here are a lightweight redundant copy kept
    // only so `status()` has something to report without reaching into a
    // specific screen's instance.
    property real fps: 24
    property real time: 0
    property real dayPhase: 12.0
    property real forcedPhase: -1
    property real speed: 1.0
    property real motion: 2.0
    property int signatureTrigger: 0

    function currentHours() {
        var d = new Date()
        return d.getHours() + d.getMinutes() / 60.0 + d.getSeconds() / 3600.0
    }

    Timer {
        id: clockTimer
        interval: Math.max(8, Math.round(1000 / root.fps))
        running: true
        repeat: true
        onTriggered: root.time += (interval / 1000.0) * root.speed
    }

    Timer {
        id: dayTimer
        interval: 30000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: {
            root.dayPhase = root.forcedPhase >= 0 ? root.forcedPhase : root.currentHours()
        }
    }

    IpcHandler {
        target: "studio"

        function phase(h: real) {
            root.forcedPhase = h
            root.dayPhase = h >= 0 ? h : root.currentHours()
        }

        function speed(s: real) {
            root.speed = s
        }

        function motion(m: real) {
            root.motion = m
        }

        function signature() {
            root.signatureTrigger += 1
        }

        function status(): string {
            return JSON.stringify({
                time: root.time,
                dayPhase: root.dayPhase,
                forcedPhase: root.forcedPhase,
                motion: root.motion,
                fps: root.fps
            })
        }
    }

    Variants {
        model: Quickshell.screens

        PanelWindow {
            id: panel
            required property var modelData
            screen: modelData

            anchors {
                top: true
                bottom: true
                left: true
                right: true
            }

            color: "black"
            exclusionMode: ExclusionMode.Ignore
            mask: Region {}

            WlrLayershell.layer: WlrLayer.Background
            WlrLayershell.namespace: "lana-studio"
            WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

            StudioBackdrop {
                anchors.fill: parent
                fps: root.fps
                forcedPhase: root.forcedPhase
                speed: root.speed
                motion: root.motion
                signatureTrigger: root.signatureTrigger
            }
        }
    }
}
