// KWin script: puts the bench windows at fixed logical positions, by caption.
const slots = { "Qt SSD": [20, 20], "GTK3 SSD": [620, 20], "X11 SSD": [1220, 20],
                "GTK4 Adw": [20, 400], "GTK4 HeaderBar": [620, 400], "GTK3 CSD": [1220, 400],
                // APPS=1 (H 2700 or more): Chromium with the GTK frame, Electron with its overlay buttons.
                "Brave": [20, 780], "Claude": [700, 780] };
function place(w) {
    if (w.caption === "Backdrop") {  // the "wallpaper": the user's sage green, below everything
        w.keepBelow = true; w.noBorder = true; w.skipTaskbar = true;
        w.frameGeometry = { x: 0, y: 0, width: workspace.virtualScreenSize.width, height: workspace.virtualScreenSize.height };
        return;
    }
    const s = slots[w.caption];
    if (!s) return;
    const g = w.frameGeometry;
    w.frameGeometry = { x: s[0], y: s[1], width: g.width, height: g.height };
}
workspace.windowAdded.connect(w => { place(w); w.captionChanged.connect(() => place(w)); });
workspace.windowList().forEach(place);
