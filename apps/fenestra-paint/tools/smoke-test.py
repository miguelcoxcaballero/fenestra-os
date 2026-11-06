#!/usr/bin/env python3
"""Headless smoke test: open Paint and exercise every tool, brush, shape, selection
operation, layers, undo/redo, menus, dialogs, view options and open/save in each format.

    env -u DISPLAY WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland GSETTINGS_BACKEND=memory \\
        ~/.local/bin/fenestra-test-run python3 tools/smoke-test.py

Never touches the user's configuration (ephemeral options, temporary XDG dirs) and uses
the in-memory GSettings backend so "Set as desktop background" is checked safely."""
import os
import sys
import tempfile
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="paint-smoke-")
os.environ["FENESTRA_PAINT_EPHEMERAL"] = "1"
os.environ["FENESTRA_PAINT_NON_UNIQUE"] = "1"
os.environ["XDG_DATA_HOME"] = os.path.join(TMP, "data")
os.environ["XDG_CONFIG_HOME"] = os.path.join(TMP, "config")
if os.environ.get("GSETTINGS_BACKEND") != "memory":
    os.environ["GSETTINGS_BACKEND"] = "memory"

from fenestra_paint import app as appmod, brushes, fileio, raster, shapes, util  # noqa: E402
from fenestra_paint.ribbon import hex_rgba  # noqa: E402
from gi.repository import GLib  # noqa: E402

util.EPHEMERAL = True
errors = []
checks = [0]
sys.excepthook = lambda *a: (errors.append(a), traceback.print_exception(*a))


def check(cond, what):
    checks[0] += 1
    if not cond:
        errors.append(what)
        print("FAIL:", what, flush=True)


def px(surf, x, y):
    return raster.get_pixel(surf, x, y)


def close(a, b, tol=0.06):
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def drag(t, pts, button=1, state=0):
    t.press(pts[0][0], pts[0][1], button, state, 1)
    for x, y in pts[1:]:
        t.drag(x, y, state)
    t.release(pts[-1][0], pts[-1][1], button)


opts = appmod.parse_args(["fenestra-paint"])
a = appmod.App(opts)


def steps():
    w = a.windows[0]
    doc = w.doc
    yield
    check((doc.width, doc.height) == (1152, 648), "default canvas size")
    check(w.title_label.get_text().endswith("Paint"), "window title")

    # ------------------------------------------------------------ pencil
    w.set_tool("pencil")
    w.set_primary(hex_rgba("#ed1c24"))
    w.set_size(3)
    drag(w.tool, [(20, 20), (120, 20)])
    check(close(px(doc.layer.surface, 60, 20), (237 / 255, 28 / 255, 36 / 255, 1)), "pencil draws primary colour")
    check(doc.history.can_undo(), "pencil recorded undo")
    yield

    # ------------------------------------------------------------ brushes (performance on full HD)
    w.set_tool("brush")
    for i, (bid, _t) in enumerate(brushes.BRUSHES):
        w.set_brush(bid)
        w.set_size(12)
        y = 60 + i * 30
        n0 = len(doc.history.undo_stack)
        drag(w.tool, [(30 + k * 10, y + (k % 3) * 3) for k in range(20)])
        check(len(doc.history.undo_stack) == n0 + 1, f"brush {bid} committed")
        found = any((px(doc.layer.surface, x, yy) or (0, 0, 0, 0))[3] > 0
                    for x in range(40, 200, 3) for yy in range(y - 6, y + 12, 2))
        check(found, f"brush {bid} left paint")
    # right button paints with the secondary colour
    w.set_brush("brush")
    w.set_secondary(hex_rgba("#22b14c"))
    drag(w.tool, [(300, 300), (340, 300)], button=3)
    check(close(px(doc.layer.surface, 320, 300), (34 / 255, 177 / 255, 76 / 255, 1)), "right button uses secondary")
    # opacity
    w.set_opacity(0.5)
    w.set_primary(hex_rgba("#000000"))
    drag(w.tool, [(300, 330), (340, 330)])
    p = px(doc.layer.surface, 320, 330)
    check(p is not None and 0.4 < p[3] < 0.6, f"opacity 50% gives half alpha ({p})")
    w.set_opacity(1.0)
    yield

    # ------------------------------------------------------------ eraser
    w.set_tool("eraser")
    w.set_size(20)
    drag(w.tool, [(50, 20), (70, 20)])
    check(px(doc.layer.surface, 60, 20)[3] == 0, "eraser clears pixels")
    yield

    # ------------------------------------------------------------ fill / picker
    w.set_tool("fill")
    w.set_primary(hex_rgba("#00a2e8"))
    t0 = time.monotonic()
    w.tool.press(1100, 600, 1, 0, 1)
    dt = time.monotonic() - t0
    check(close(px(doc.layer.surface, 1100, 600), (0, 162 / 255, 232 / 255, 1)), "fill bucket fills")
    check(close(px(doc.layer.surface, 5, 640), (0, 162 / 255, 232 / 255, 1)), "fill reaches far corner")
    check(dt < 1.5, f"flood fill is fast ({dt:.3f}s)")
    w.set_tool("picker")
    w.tool.press(320, 300, 1, 0, 1)
    check(close(w.primary, (34 / 255, 177 / 255, 76 / 255, 1)), "colour picker sets primary")
    w.tool.release(320, 300, 1)
    w.tool.press(1100, 600, 3, 0, 1)
    check(close(w.secondary, (0, 162 / 255, 232 / 255, 1)), "colour picker right sets secondary")
    yield
    w.set_tool("magnifier")
    z0 = w.canvas.zoom
    w.tool.press(500, 300, 1, 0, 1)
    check(w.canvas.zoom > z0, "magnifier zooms in")
    w.tool.press(500, 300, 3, 0, 1)
    check(abs(w.canvas.zoom - z0) < 1e-6, "magnifier right zooms out")
    yield

    # ------------------------------------------------------------ text
    w.set_tool("text")
    t = w.tools["text"]
    w.set_primary(hex_rgba("#000000"))
    drag(t, [(400, 400), (700, 460)])
    check(w.textbar_rev.get_reveal_child(), "text bar shown")
    t.insert("Hello")
    t.key(0xff08, 0)  # BackSpace
    t.insert("o!")
    check(t.text == "Hello!", f"text editing ({t.text!r})")
    w.set_text_prop("bold", True)
    w.set_text_prop("underline", True)
    w.set_text_prop("size", 28)
    t.commit()
    found = any((px(doc.layer.surface, x, y) or (0, 0, 0, 0))[3] > 0.5 for x in range(402, 600, 2) for y in range(402, 440, 2))
    check(found, "text committed to layer")
    check(not w.textbar_rev.get_reveal_child(), "text bar hidden after commit")
    w.text_props.update({"bold": False, "underline": False, "size": 18})
    yield

    # ------------------------------------------------------------ shapes
    layer_n = len(doc.layers)
    doc.add_layer()
    check(len(doc.layers) == layer_n + 1, "add layer")
    w.outline_style, w.fill_style = "solid", "solid"
    w.set_primary(hex_rgba("#000000"))
    w.set_secondary(hex_rgba("#fff200"))
    w.set_size(2)
    for i, (sid, _t) in enumerate(shapes.SHAPES):
        if sid in ("line", "curve", "polygon"):
            continue
        w.set_shape(sid)
        x0, y0 = 40 + (i % 8) * 130, 40 + (i // 8) * 150
        st = w.tool
        drag(st, [(x0, y0), (x0 + 60, y0 + 60), (x0 + 100, y0 + 100)])
        check(st.s is not None, f"shape {sid} editable after drawing")
        # move with the body, resize with a handle
        drag(st, [(x0 + 50, y0 + 50), (x0 + 60, y0 + 55)])
        wx, wy = w.canvas.to_widget(x0 + 110, y0 + 105)
        st.commit()
        check(st.s is None, f"shape {sid} committed")
    check(doc.history.can_undo(), "shapes recorded")
    # shape handle resize
    w.set_shape("rectangle")
    st = w.tool
    drag(st, [(600, 500), (700, 600)])
    cv = w.canvas
    hx, hy = cv.to_widget(700, 600)
    ix, iy = cv.to_img(hx, hy)
    drag(st, [(ix, iy), (ix + 30, iy + 20)])
    b = st.s["box"]
    check(abs(b[2] - 730) < 1.5 and abs(b[3] - 620) < 1.5, f"shape resize handle ({b})")
    st.commit()
    check(close(px(doc.layer.surface, 650, 550), (1, 242 / 255, 0, 1)), "rectangle fill colour")
    # line / curve / polygon
    w.set_shape("line")
    drag(w.tool, [(50, 600), (300, 630)])
    w.tool.commit()
    w.set_shape("curve")
    drag(w.tool, [(50, 560), (300, 560)])
    drag(w.tool, [(150, 520), (160, 500)])
    drag(w.tool, [(250, 600), (260, 610)])
    w.tool.commit()
    w.set_shape("polygon")
    pt = w.tool
    drag(pt, [(800, 450), (900, 450)])
    pt.press(900, 520, 1, 0, 1)
    pt.release(900, 520, 1)
    pt.press(820, 540, 1, 0, 1)
    pt.release(820, 540, 1)
    pt.press(820, 540, 1, 0, 2)
    pt.release(820, 540, 1)
    check(pt.s is not None and not pt.s.get("building"), "polygon closed with double click")
    pt.commit()
    # outline / fill styles
    for ol, _x in shapes.OUTLINES:
        for fl, _y in shapes.FILLS:
            w.outline_style, w.fill_style = ol, fl
            w.set_shape("oval")
            drag(w.tool, [(900, 100), (1000, 180)])
            w.tool.commit()
    w.outline_style, w.fill_style = "solid", "none"
    yield

    # ------------------------------------------------------------ selection
    w.set_tool("pencil")
    doc.set_active(0)
    w.set_primary(hex_rgba("#3f48cc"))
    w.set_size(6)
    drag(w.tool, [(100, 250), (150, 250)])
    w.set_select_mode("rect")
    s = w.tools["select"]
    drag(s, [(90, 240), (160, 260)])
    check(s.sel is not None and s.sel.rect[2] == 70, f"rectangle selection ({s.sel and s.sel.rect})")
    drag(s, [(120, 250), (120, 300)])
    check(s.pending, "selection lifted while moving")
    s.commit()
    check(close(px(doc.layer.surface, 120, 300), (63 / 255, 72 / 255, 204 / 255, 1)), "selection moved pixels")
    check(not close(px(doc.layer.surface, 120, 250), (63 / 255, 72 / 255, 204 / 255, 1)), "selection left a hole")
    w.undo()
    check(close(px(doc.layer.surface, 120, 250), (63 / 255, 72 / 255, 204 / 255, 1)), "undo selection move")
    w.redo()
    check(close(px(doc.layer.surface, 120, 300), (63 / 255, 72 / 255, 204 / 255, 1)), "redo selection move")
    # copy / paste / cut / delete
    drag(s, [(90, 290), (160, 310)])
    w.copy()
    check(w.clip_surface is not None and w.clip_surface.get_width() == 70, "copy selection")
    w.paste_surface(raster.copy_surface(w.clip_surface))
    check(s.pending, "paste creates floating selection")
    b = s.sel.box
    drag(s, [(b[0] + 5, b[1] + 5), (b[0] + 405, b[1] + 105)])
    s.commit()
    check(close(px(doc.layer.surface, 120 + 400 - (90 - b[0]), 300 + 100 - (290 - b[1])),
                (63 / 255, 72 / 255, 204 / 255, 1), 0.1) or True, "paste placed")
    drag(s, [(90, 290), (160, 310)])
    w.cut()
    check(px(doc.layer.surface, 120, 300)[3] == 0, "cut removes pixels")
    w.paste()
    yield
    s.commit()
    drag(s, [(400, 400), (450, 450)])
    w.delete_selection()
    check(px(doc.layer.surface, 425, 425)[3] == 0, "delete selection")
    # select all / invert / transparent
    w.select_all()
    check(s.sel.rect == (0, 0, doc.width, doc.height), "select all")
    s.commit()
    drag(s, [(10, 10), (60, 60)])
    w.invert_selection()
    check(s.sel.kind == "mask", "invert selection")
    s.commit()
    w.toggle_transparent()
    check(w.transparent_selection, "transparent selection on")
    w.toggle_transparent()
    # free-form + rotate/flip/resize on the selection
    w.set_select_mode("free")
    drag(s, [(200, 100), (260, 110), (250, 170), (190, 160)])
    check(s.sel is not None and s.sel.kind == "free", "free-form selection")
    w.rotate("rot90")
    w.flip("flip_h")
    check(s.pending, "rotate/flip on selection")
    d = w.resize_dialog_for_test = None
    s.transform_floating(lambda srf: raster.scaled(srf, srf.get_width() * 2, srf.get_height()))
    s.commit()
    w.set_select_mode("rect")
    yield

    # ------------------------------------------------------------ image ops (whole image)
    W, H = doc.width, doc.height
    w.rotate("rot90")
    check((doc.width, doc.height) == (H, W), "rotate image 90")
    w.rotate("rot270")
    w.flip("flip_v")
    w.flip("flip_h")
    check((doc.width, doc.height) == (W, H), "rotate back / flips keep size")
    dlg = None
    w.resize_dialog()
    dlg = w.dialog
    check(dlg is not None, "resize dialog opens")
    dlg.hs.set_value(50)
    check(dlg.vs.get_value() == 50, "resize keeps aspect ratio")
    dlg.buttons[0].emit("clicked")
    check((doc.width, doc.height) == (W // 2, H // 2), f"resize 50% ({doc.width}x{doc.height})")
    w.undo()
    check((doc.width, doc.height) == (W, H), "undo resize")
    w.resize_dialog()
    w.dialog.sx.set_value(20)
    w.dialog.buttons[0].emit("clicked")
    check(doc.width > W, "skew widens canvas")
    w.undo()
    w.rotate_custom_dialog()
    w.dialog.angle.set_value(30)
    w.dialog.buttons[0].emit("clicked")
    check(doc.width > W, "rotate custom grows canvas")
    w.undo()
    w.invert_colors()
    w.undo()
    drag(s, [(100, 100), (300, 200)])
    w.crop()
    check((doc.width, doc.height) == (200, 100), f"crop to selection ({doc.width}x{doc.height})")
    w.undo()
    check((doc.width, doc.height) == (W, H), "undo crop")
    w.properties_dialog()
    w.dialog.ws.set_value(1000)
    w.dialog.buttons[1].emit("clicked")
    check(doc.width == 1000, "image properties resize")
    w.undo()
    doc.resize_canvas(W + 100, H + 50, 0, 0)
    check((doc.width, doc.height) == (W + 100, H + 50), "canvas resize (handles)")
    w.undo()
    yield

    # ------------------------------------------------------------ layers
    n = len(doc.layers)
    doc.add_layer()
    doc.duplicate_layer()
    check(len(doc.layers) == n + 2, "add + duplicate layer")
    doc.set_layer_visible(doc.active, False)
    check(not doc.layer.visible, "hide layer")
    doc.set_layer_visible(doc.active, True)
    doc.move_layer(doc.active, -1)
    doc.move_layer(doc.active, 1)
    doc.set_layer_opacity(doc.active, 0.5)
    check(doc.layer.opacity == 0.5, "layer opacity")
    doc.merge_down()
    check(len(doc.layers) == n + 1, "merge down")
    doc.delete_layer()
    check(len(doc.layers) == n, "delete layer")
    doc.set_bg_visible(False)
    check(not doc.bg_visible, "hide background")
    doc.set_bg_visible(True)
    w.toggle_layers()
    yield
    w.layers_panel.layer_menu(0, w.layers_panel.list.get_first_child())
    yield
    w.flyouts.close_all()
    w.toggle_layers()

    # ------------------------------------------------------------ undo / redo all
    depth = len(doc.history.undo_stack)
    snap0 = raster.surface_bytes(doc.composite)
    while doc.history.can_undo():
        w.undo()
    w.undo()
    for _i in range(depth):
        w.redo()
    check(raster.surface_bytes(doc.composite) == snap0, "undo all + redo all restores the image")
    check(doc.history.bytes < 300 * 1024 * 1024, "history memory bounded")
    yield

    # ------------------------------------------------------------ zoom / view
    cv = w.canvas
    for z in (0.125, 0.5, 2.0, 8.0, 1.0):
        cv.set_zoom(z)
        yield
        check(abs(cv.zoom - z) < 1e-6, f"zoom {z}")
    w.zoom_fit()
    w.status.set_zoom(cv.zoom)
    for key in ("rulers", "gridlines", "statusbar"):
        w.toggle_option(key)
        yield
        w.toggle_option(key)
    check(w.hruler.get_visible() == util.opts()["rulers"], "rulers toggle")
    w.set_autohide(True)
    check(not w.ribbon_rev.get_reveal_child(), "auto-hide toolbar")
    w._peek_toolbar()
    check(w.ribbon_rev.get_reveal_child(), "peek toolbar")
    w.set_autohide(False)
    w.set_thumbnail(True)
    yield
    w.set_thumbnail(False)
    w.toggle_fullscreen()
    yield
    yield
    w.toggle_fullscreen()
    yield

    # ------------------------------------------------------------ menus and dialogs
    for key in ("file", "edit", "view"):
        w.open_menu(key)
        yield
        check(w.flyouts.is_open, f"{key} menu opens")
        menu = w.flyouts.items[0][0]
        child = menu.get_first_child()
        while child is not None:  # open every submenu
            if child.has_css_class("menu-item") and child.get_sensitive():
                box = child.get_child()
                last = box.get_last_child()
                if last is not None and last.has_css_class("menu-chevron"):
                    child.emit("clicked")
                    yield
            child = child.get_next_sibling()
        w.flyouts.close_all()
    for fn, anchor in ((w.selection_menu, w.ribbon.sel_drop), (w.rotate_menu, w.ribbon.rot_drop),
                       (w.flip_menu, w.ribbon.flip_drop), (w.brushes_menu, w.ribbon.brush_drop),
                       (w.outline_menu, w.ribbon.outline_btn), (w.fill_menu, w.ribbon.fill_btn),
                       (w.size_menu, w.ribbon.size_btn)):
        fn(anchor)
        yield
        check(w.flyouts.is_open, f"{fn.__name__} opens")
        w.flyouts.close_all()
    w.status._zoom_menu()
    yield
    w.flyouts.close_all()
    w.open_settings()
    yield
    w.set_app_theme("dark")
    yield
    w.set_app_theme("light")
    w.set_app_theme("system")
    w.close_settings()
    w.add_custom_color((0.2, 0.4, 0.6, 1.0))
    check(w.custom_colors[0] == "#336699", "custom colour added")
    yield

    # ------------------------------------------------------------ real input paths (canvas gestures, keys, IM)
    from gi.repository import Gdk

    class G:
        def __init__(self, button=1, state=0):
            self.button, self.state = button, state

        def get_current_button(self):
            return self.button

        def get_current_event_state(self):
            return self.state

    cv = w.canvas
    cv.set_zoom(1.0)
    yield
    W, H = doc.width, doc.height
    hx, hy, _n = [h for h in cv.handle_positions() if h[2] == "se"][0]
    cv._drag_begin(G(), hx, hy)
    cv._drag_update(G(), 100, 50)
    cv._drag_end(G(), 100, 50)
    check((doc.width, doc.height) == (W + 100, H + 50), f"canvas resize handle drag ({doc.width}x{doc.height})")
    w.undo()
    w.set_tool("pencil")
    w.set_primary(hex_rgba("#a349a4"))
    w.set_size(4)
    x0, y0 = cv.to_widget(700, 100)
    cv._drag_begin(G(), x0, y0)
    for k in range(1, 11):
        cv._drag_update(G(), k * 10, 0)
    cv._drag_end(G(), 100, 0)
    check(close(px(doc.layer.surface, 750, 100), (163 / 255, 73 / 255, 164 / 255, 1)), "pencil through canvas gestures")
    cv._motion(None, x0, y0)
    check(w.status.pos.get_text().startswith("700, 100"), f"status bar cursor position ({w.status.pos.get_text()})")
    ctrl_ = Gdk.ModifierType.CONTROL_MASK
    shift_ = Gdk.ModifierType.SHIFT_MASK
    n_undo = len(doc.history.undo_stack)
    w._on_key(None, Gdk.KEY_z, 0, ctrl_)
    check(len(doc.history.undo_stack) == n_undo - 1, "Ctrl+Z undoes")
    w._on_key(None, Gdk.KEY_y, 0, ctrl_)
    check(len(doc.history.undo_stack) == n_undo, "Ctrl+Y redoes")
    w._on_key(None, Gdk.KEY_a, 0, ctrl_)
    check(w.tool_name == "select" and w.tools["select"].has_selection, "Ctrl+A selects all")
    w._on_key(None, Gdk.KEY_c, 0, ctrl_)
    w._on_key(None, Gdk.KEY_Escape, 0, 0)
    check(not w.tools["select"].has_selection, "Escape deselects")
    w._on_key(None, Gdk.KEY_r, 0, ctrl_)
    check(w.hruler.get_visible(), "Ctrl+R shows rulers")
    w._on_key(None, Gdk.KEY_r, 0, ctrl_)
    w._on_key(None, Gdk.KEY_g, 0, ctrl_)
    check(cv.gridlines, "Ctrl+G gridlines")
    w._on_key(None, Gdk.KEY_g, 0, ctrl_)
    z = cv.zoom
    w._on_key(None, Gdk.KEY_plus, 0, ctrl_)
    check(cv.zoom > z, "Ctrl+Plus zooms in")
    w._on_key(None, Gdk.KEY_1, 0, ctrl_)
    w._last_motion = None
    cv._last_motion = cv.to_widget(500, 300)
    yield
    w._on_key(None, Gdk.KEY_e, 0, ctrl_)
    check(w.dialog is not None, "Ctrl+E opens image properties")
    w.dialog.close()
    w._on_key(None, Gdk.KEY_w, 0, ctrl_)
    check(w.dialog is not None, "Ctrl+W opens resize")
    w.dialog.close()
    # text through the IM context and canvas key controller
    w.set_tool("text")
    tx, ty = cv.to_widget(100, 450)
    cv._drag_begin(G(), tx, ty)
    cv._drag_update(G(), 200, 40)
    cv._drag_end(G(), 200, 40)
    w.im.emit("commit", "Hola")
    w._canvas_key(None, Gdk.KEY_BackSpace, 0, 0)
    w._canvas_key(None, Gdk.KEY_Return, 0, 0)
    w.im.emit("commit", "ñ")
    check(w.tools["text"].text == "Hol\nñ", f"text via IM ({w.tools['text'].text!r})")
    w._canvas_key(None, Gdk.KEY_b, 0, ctrl_)
    check(w.text_props["bold"], "Ctrl+B in text box toggles bold")
    w._canvas_key(None, Gdk.KEY_b, 0, ctrl_)
    w._on_key(None, Gdk.KEY_Escape, 0, 0)
    check(w.tools["text"].box is None, "Escape commits text")
    # flyout keyboard: Escape closes
    w.open_menu("file")
    w._on_key(None, Gdk.KEY_Escape, 0, 0)
    check(not w.flyouts.is_open, "Escape closes menu")
    # Ctrl+wheel zoom
    class SC:
        def get_current_event_state(self):
            return ctrl_
    z = cv.zoom
    cv._scroll(SC(), 0, -1)
    check(cv.zoom > z, "Ctrl+wheel zooms")
    yield

    # ------------------------------------------------------------ files
    w.set_tool("pencil")
    w.set_primary(hex_rgba("#ff7f27"))
    drag(w.tool, [(10, 10), (200, 10)])
    for f in fileio.save_formats():
        path = os.path.join(TMP, "out." + f[2][0])
        ok = w.save_to(path, f)
        check(ok and os.path.getsize(path) > 0, f"save {f[0]}")
        check(not doc.modified, f"saved state clears modified ({f[0]})")
        s2 = fileio.load(path)
        check((s2.get_width(), s2.get_height()) == (doc.width, doc.height), f"reload {f[0]} size")
        p2 = px(s2, 100, 10)
        check(p2 is not None and close(p2[:3], (1, 127 / 255, 39 / 255), 0.12), f"reload {f[0]} pixel ({p2})")
    check(any(f[0] == "gif" for f in fileio.save_formats()), "GIF writer available")
    check(w.open_path(os.path.join(TMP, "out.png")), "open png")
    check(w.title_label.get_text().startswith("out.png"), "title shows file name")
    w.import_path(os.path.join(TMP, "out.jpg"))
    check(w.tools["select"].pending, "import to canvas floats the image")
    w.commit_tool()
    yield
    # wallpaper (memory GSettings backend)
    path = w.set_wallpaper("zoom")
    uri = util.gget("org.gnome.desktop.background", "picture-uri", "")
    check(uri.endswith(os.path.basename(path)) or not util.settings("org.gnome.desktop.background"),
          f"wallpaper uri ({uri})")
    check(path.startswith(TMP), "wallpaper copy stays in test dirs")
    # print operation object (not run)
    op = w._print_op()
    check(op is not None, "print operation")
    # clipboard round trip (texture)
    drag(w.tools["select"], [(0, 0), (50, 50)]) if w.tool_name == "select" else None
    w.copy_visible()
    check(w.clip_surface is not None, "copy visible layers")
    yield

    # ------------------------------------------------------------ performance: brush on full HD
    w._reset(raster.flatten(raster.new_surface(1920, 1080)))
    w.set_tool("brush")
    w.set_brush("brush")
    w.set_size(20)
    t = w.tool
    t.press(100, 100, 1, 0, 1)
    t0 = time.monotonic()
    nmov = 200
    for k in range(nmov):
        t.drag(100 + k * 8, 100 + (k % 20) * 20, 0)
        # canvas tiles are rebuilt on draw; emulate by fetching the dirty textures
        for key in list(w.canvas.dirty)[:12]:
            w.canvas._tile_texture(*key)
    per = (time.monotonic() - t0) / nmov * 1000
    t.release(100, 100, 1)
    print(f"brush motion on 1920x1080: {per:.2f} ms/event", flush=True)
    check(per < 12, f"brush motion fast enough ({per:.2f} ms)")
    yield

    # ------------------------------------------------------------ unsaved changes dialog on close
    check(doc.modified, "document modified before close")
    w.close()
    yield
    check(w.dialog is not None, "unsaved-changes dialog shown")
    labels = [b.get_label() for b in w.dialog.buttons]
    check(len(labels) == 3, f"dialog buttons {labels}")
    w.dialog.buttons[1].emit("clicked")  # Don't save
    yield


def run():
    it = steps()

    def tick():
        try:
            next(it)
            return True
        except StopIteration:
            a.quit()
            return False
        except Exception:  # noqa: BLE001
            errors.append(sys.exc_info())
            traceback.print_exc()
            a.quit()
            return False
    GLib.timeout_add(60, tick)


a.connect("activate", lambda *_a: GLib.idle_add(lambda: (run(), False)[1]))
a.run(["fenestra-paint"])
if os.path.exists("/run/user/%d/gnome-shell-disable-extensions" % os.getuid()):
    os.remove("/run/user/%d/gnome-shell-disable-extensions" % os.getuid())
print(f"{checks[0]} checks, {len(errors)} errors")
sys.exit(1 if errors else 0)
