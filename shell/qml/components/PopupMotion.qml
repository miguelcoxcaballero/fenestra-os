// SPDX-License-Identifier: GPL-3.0-or-later
// Open/close motion of a shell popup, as Windows 11 (design/Motion.qml; frames, fits and assumptions
// in design/motion.json). The popup puts `shift` in the transform of what moves, calls enter() when
// it shows and leave() when it should hide, and hides its window on gone().
//   taskbar       rises from behind the taskbar's top edge; travel = height + gap   (measured: Start, Quick settings)
//   edge          in from the right screen edge; travel = width + margin           (measured: Notification Center)
//   menu          reveals upwards from travel × 0.5 with a quick fade                (assumption: WinUI MenuFlyout)
//   fade          opacity only                                                       (assumption)
//   page-forward  page in from the right (40 px) with a fade; page-back from the left (assumption)
//   none          no motion
// The surface's own edge clips the motion: taskbar popups reach down to the taskbar's top edge.
import QtQuick
import Fenestra.Shell

Item {
    id: m
    visible: false
    // Whose opacity fades (menu, fade, page); the moving part is whatever carries `shift`.
    property Item target: m
    property string kind: "taskbar"
    property real travel: 0
    readonly property Translate shift: Translate {}
    readonly property bool busy: enterAnim.running || leaveAnim.running
    signal gone()

    readonly property bool horizontal: kind === "edge" || kind === "page-forward" || kind === "page-back"
    readonly property real from: kind === "taskbar" || kind === "edge" ? travel
                               : kind === "menu" ? Math.round(travel * Motion.menuRatio)
                               : kind === "page-forward" ? Motion.pageOffset
                               : kind === "page-back" ? -Motion.pageOffset : 0
    readonly property bool fades: kind === "menu" || kind === "fade" || kind === "page-forward" || kind === "page-back"
    readonly property int moveDuration: kind === "taskbar" ? Motion.taskbarOpen : kind === "edge" ? Motion.edgeOpen
                                      : kind === "menu" ? Motion.menuOpen : horizontal ? Motion.pageOpen : 0
    readonly property int fadeDuration: kind === "menu" ? Motion.menuFade : kind === "fade" ? Motion.fadeOpen
                                      : horizontal ? Motion.pageFade : 0
    // Closing: taskbar and edge popups slide back out, menus and fades fade; pages do not close.
    readonly property bool leavesMoving: kind === "taskbar" || kind === "edge"
    readonly property int leaveFade: kind === "menu" ? Motion.menuFade : kind === "fade" ? Motion.fadeClose : 0

    function reset() {
        enterAnim.stop(); leaveAnim.stop()
        shift.x = 0; shift.y = 0
        target.opacity = 1
    }
    function enter() {
        leaveAnim.stop()
        if (Motion.reduced || kind === "none") { reset(); return }
        shift.x = horizontal ? from : 0
        shift.y = horizontal ? 0 : from
        target.opacity = fades ? 0 : 1
        enterAnim.restart()
    }
    function leave() {
        enterAnim.stop()
        if (Motion.reduced || kind === "none" || (!leavesMoving && leaveFade === 0)) { gone(); return }
        leaveAnim.restart()
    }

    ParallelAnimation {
        id: enterAnim
        NumberAnimation { target: m.shift; property: m.horizontal ? "x" : "y"; to: 0; duration: m.moveDuration
                          easing.type: Easing.BezierSpline; easing.bezierCurve: m.kind === "edge" ? Motion.decelerateEdge : Motion.decelerate }
        NumberAnimation { target: m.target; property: "opacity"; to: 1; duration: m.fadeDuration }
    }
    SequentialAnimation {
        id: leaveAnim
        ParallelAnimation {
            NumberAnimation { target: m.shift; property: m.horizontal ? "x" : "y"; to: m.leavesMoving ? m.from : 0
                              duration: !m.leavesMoving ? 0 : m.kind === "edge" ? Motion.closeEdge : Motion.closeTaskbar
                              easing.type: Easing.BezierSpline; easing.bezierCurve: Motion.accelerate }
            NumberAnimation { target: m.target; property: "opacity"; to: m.leaveFade > 0 ? 0 : 1; duration: m.leaveFade }
        }
        ScriptAction { script: m.gone() }
    }
}
