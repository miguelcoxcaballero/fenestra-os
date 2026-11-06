#!/usr/bin/env python3
"""Regenerate the bundled UI icons (data/icons/ui) from Microsoft's Fluent UI System
Icons (MIT, @fluentui/svg-icons), the same source tools/generate-assets.py uses.

    python3 tools/gen-icons.py [path/to/fluent/package/icons]

Every icon is written as a GTK symbolic icon (recoloured from CSS).  Icons listed in
TWO_TONE also get a "-fill" variant (the filled glyph) that the app draws underneath the
outline in a tint colour, which gives the two-tone look of the Paint toolbar.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "icons", "ui")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/.cache/fenestra-build/fluent-1.1.345/package/icons")

ICONS = {
    # menu bar / file
    "save": "save", "undo": "arrow_undo", "redo": "arrow_redo", "settings": "settings",
    "new": "document", "open": "folder_open", "import": "arrow_import", "recent": "history",
    "saveas": "save_edit", "print": "print", "wallpaper": "desktop", "props": "image_edit",
    "exit": "dismiss", "picture": "image", "page-setup": "document_settings",
    # edit
    "cut": "cut", "copy": "copy", "paste": "clipboard_paste", "copy-layers": "copy_select",
    # view
    "zoom": "zoom_in", "zoom-in": "zoom_in", "zoom-out": "zoom_out", "full-screen": "arrow_maximize",
    "thumbnail": "picture_in_picture", "fit": "scale_fit", "actual-size": "zoom_fit",
    # selection
    "rect-select": "select_object", "lasso": "lasso", "select-all": "select_all_on",
    "invert-sel": "select_all_off", "delete": "delete",
    # image
    "crop": "crop", "rotate-right": "arrow_rotate_clockwise",
    "rotate-left": "arrow_rotate_counterclockwise", "rotate-180": "arrow_sync",
    "rotate-custom": "arrow_clockwise", "flip-h": "flip_horizontal", "flip-v": "flip_vertical",
    "resize": "resize_image", "invert-colors": "dark_theme", "rotate": "rotate_right",
    "flip": "flip_vertical",
    # tools
    "pencil": "edit", "bucket": "paint_bucket", "text": "text_font", "eraser": "eraser",
    "picker": "eyedropper", "magnifier": "zoom_in", "brush": "paint_brush",
    "outline": "color_line", "fill": "color_fill", "size": "line_thickness", "opacity": "drop",
    "layers": "layer", "add-circle": "add_circle", "add": "add",
    # misc
    "chevron-down": "chevron_down", "chevron-right": "chevron_right", "chevron-up": "chevron_up",
    "check": "checkmark", "cursor": "cursor", "select-size": "select_object",
    "canvas-size": "square", "back": "arrow_left", "eye": "eye", "eye-off": "eye_off",
    "more": "more_horizontal", "arrow-up": "arrow_up", "arrow-down": "arrow_down",
    "merge": "arrow_download", "duplicate": "copy_add", "bold": "text_bold",
    "italic": "text_italic", "underline": "text_underline", "strike": "text_strikethrough",
    "align-left": "text_align_left", "align-center": "text_align_center",
    "align-right": "text_align_right", "text-bg": "color_background", "dismiss": "dismiss",
    "info": "info", "theme": "paint_brush", "layer-props": "options",
}

# icons that also need the filled glyph for the two-tone look
TWO_TONE = ["pencil", "bucket", "eraser", "picker", "rotate", "flip", "resize", "crop",
            "rotate-right", "rotate-left", "flip-h", "flip-v", "brush", "layers", "fill",
            "outline", "opacity", "size"]


def load(name, style):
    path = os.path.join(SRC, f"{name}_20_{style}.svg")
    if not os.path.exists(path):
        return None
    svg = open(path).read()
    svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', "", svg)
    return svg.replace("<path ", '<path fill="#ffffff" ')


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for name, src in ICONS.items():
        svg = load(src, "regular")
        if svg is None:
            print("missing", src)
            continue
        with open(os.path.join(OUT, f"pt-{name}-symbolic.svg"), "w") as f:
            f.write(svg)
        n += 1
        if name in TWO_TONE:
            fill = load(src, "filled")
            if fill:
                with open(os.path.join(OUT, f"pt-{name}-fill-symbolic.svg"), "w") as f:
                    f.write(fill)
                n += 1
    print("wrote", n, "icons to", OUT)


if __name__ == "__main__":
    main()
