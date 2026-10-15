import QtQuick

// The living studio wallpaper as a reusable, self-contained Item: no
// PanelWindow, no window-management API, just "fills its parent, animates
// itself". Used by studio/shell.qml (one instance per screen) and dropped
// into holo-golden/shell.qml in place of holo's static background Image
// (BRIEF-2/BRIEF-3: the gold-holo merge) -- same shader, same masks, same
// motion, just a component instead of a whole config.
//
// Fully self-contained: owns its own clock/day/signature Timers
// (NumberAnimation/SequentialAnimation do not run in this Quickshell build,
// as discovered building studio/ originally), so dropping it in is a true
// one-line replacement with sane real-clock defaults -- no external wiring
// required. An owning shell's own IpcHandler can still reach in and drive
// `forcedPhase`/`speed`/`motion`/`fps` by simple property binding, and fan a
// single IPC `signature()` call out to several instances (e.g. one per
// monitor) via the bindable `signatureTrigger` counter: each instance fires
// its *own* envelope against its *own* local `time`, so instances never need
// a shared clock to stay correct.
Item {
    id: root
    anchors.fill: parent

    property real fps: 24
    property real speed: 1.0
    property real motion: 2.0
    property real forcedPhase: -1
    // apply a forced phase immediately, not on the next 30 s clock tick
    onForcedPhaseChanged: dayPhase = forcedPhase >= 0 ? forcedPhase : currentHours()
    property real dayPhase: 12.0
    property real time: 0
    property real signatureStart: -1000
    property int signatureTrigger: 0

    readonly property real wrapAt: 100000

    function currentHours() {
        var d = new Date()
        return d.getHours() + d.getMinutes() / 60.0 + d.getSeconds() / 3600.0
    }

    function signature() {
        root.signatureStart = root.time
    }

    onSignatureTriggerChanged: root.signature()

    Timer {
        id: clockTimer
        interval: Math.max(8, Math.round(1000 / root.fps))
        running: true
        repeat: true
        onTriggered: {
            root.time += (interval / 1000.0) * root.speed
            if (root.time > root.wrapAt) {
                root.time -= root.wrapAt
                if (root.signatureStart > -999)
                    root.signatureStart -= root.wrapAt
            }
        }
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

    // Every ~4 minutes, let the room have its quiet moment on its own;
    // signature() (direct call, or the bindable signatureTrigger counter)
    // can also trigger it on demand.
    Timer {
        id: signatureTimer
        interval: 240000
        running: true
        repeat: true
        onTriggered: root.signature()
    }

    // Texture sources for the shader. Invisible, laid out to fill this Item,
    // resolved relative to THIS file's location (Qt.resolvedUrl resolves
    // against the QML file it's written in) -- so wherever StudioBackdrop.qml
    // is copied to, it finds its own local assets/shaders/ alongside it.
    Image {
        id: baseImage
        anchors.fill: parent
        visible: false
        asynchronous: true
        smooth: true
        fillMode: Image.PreserveAspectCrop
        source: Qt.resolvedUrl("assets/base.jpg")
    }
    Image {
        id: lightImage
        anchors.fill: parent
        visible: false
        smooth: true
        fillMode: Image.PreserveAspectCrop
        source: Qt.resolvedUrl("assets/light.png")
    }
    Image {
        id: floorImage
        anchors.fill: parent
        visible: false
        smooth: true
        fillMode: Image.PreserveAspectCrop
        source: Qt.resolvedUrl("assets/floor.png")
    }
    Image {
        id: windowsImage
        anchors.fill: parent
        visible: false
        smooth: true
        fillMode: Image.PreserveAspectCrop
        source: Qt.resolvedUrl("assets/windows.png")
    }
    Image {
        id: airImage
        anchors.fill: parent
        visible: false
        smooth: true
        fillMode: Image.PreserveAspectCrop
        source: Qt.resolvedUrl("assets/air.png")
    }

    ShaderEffect {
        id: effect
        anchors.fill: parent

        property var baseTex: baseImage
        property var lightTex: lightImage
        property var floorTex: floorImage
        property var windowsTex: windowsImage
        property var airTex: airImage

        property real time: root.time
        property real dayPhase: root.dayPhase
        property real signatureStart: root.signatureStart
        property vector2d resolution: Qt.vector2d(width, height)
        property real motion: root.motion

        fragmentShader: Qt.resolvedUrl("shaders/studio.frag.qsb")
    }
}
