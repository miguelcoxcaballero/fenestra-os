#!/usr/bin/env python3
"""Regenerate the bundled UI icons (data/icons/ui) from Fluent UI System Icons
(MIT, @fluentui/svg-icons; licence in LICENSES/), the same source the other Fenestra apps use.

    python3 tools/gen-icons.py [path/to/fluent/package/icons]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data", "icons", "ui")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/.cache/fenestra-build/fluent-1.1.345/package/icons")

ICONS = {
    "add": "add_16_regular",
    "list": "text_bullet_list_ltr_20_regular",
    "numbered": "text_number_list_ltr_20_regular",
    "bold": "text_bold_20_regular",
    "italic": "text_italic_20_regular",
    "strike": "text_strikethrough_20_regular",
    "link": "link_20_regular",
    "table": "table_20_regular",
    "table-edit": "table_edit_20_regular",
    "clear-format": "text_clear_formatting_20_regular",
    "settings": "settings_20_regular",
    "search": "search_16_regular",
    "arrow-down": "arrow_down_20_regular",
    "arrow-up": "arrow_up_20_regular",
    "arrow-left": "arrow_left_16_regular",
    "options": "options_20_regular",
    "dismiss": "dismiss_16_regular",
    "dismiss-20": "dismiss_20_regular",
    "chevron-down": "chevron_down_16_regular",
    "chevron-down-20": "chevron_down_20_regular",
    "chevron-up-20": "chevron_up_20_regular",
    "chevron-right": "chevron_right_16_regular",
    "check": "checkmark_16_regular",
    "cut": "cut_20_regular",
    "copy": "copy_20_regular",
    "paste": "clipboard_paste_20_regular",
    "select-all": "select_all_on_20_regular",
    "delete": "delete_20_regular",
    "undo": "arrow_undo_20_regular",
    "palette": "color_20_regular",
    "font": "text_font_20_regular",
    "wrap": "text_wrap_20_regular",
    "format": "text_edit_style_20_regular",
    "open": "open_20_regular",
    "window": "window_20_regular",
    "history": "history_20_regular",
    "heading": "text_header_1_20_regular",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for name, src in ICONS.items():
        path = os.path.join(SRC, src + ".svg")
        if not os.path.exists(path):
            print("missing", src)
            continue
        svg = open(path).read()
        svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', 'fill="#ffffff"', svg)
        with open(os.path.join(OUT, f"np-{name}-symbolic.svg"), "w") as f:
            f.write(svg)
        n += 1
    print("wrote", n, "icons to", OUT)


if __name__ == "__main__":
    main()
