#!/usr/bin/env python3
"""Regenerate the bundled UI icons (data/icons/ui) from Microsoft's Fluent UI System
Icons (MIT, @fluentui/svg-icons), the same source tools/generate-assets.py uses.

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
    "nav": "navigation_20_regular",
    "processes": "data_treemap_20_regular",
    "performance": "pulse_square_20_regular",
    "history": "history_20_regular",
    "startup": "top_speed_20_regular",
    "users": "people_20_regular",
    "details": "text_bullet_list_ltr_20_regular",
    "services": "puzzle_piece_20_regular",
    "settings": "settings_20_regular",
    "search": "search_20_regular",
    "run": "apps_add_in_20_regular",
    "end": "prohibited_20_regular",
    "leaf": "leaf_two_20_regular",
    "leaf-filled": "leaf_two_20_filled",
    "more": "more_horizontal_20_regular",
    "play": "play_20_regular",
    "stop": "stop_20_regular",
    "restart": "arrow_clockwise_20_regular",
    "open-services": "window_settings_20_regular",
    "check": "checkmark_20_regular",
    "properties": "document_text_20_regular",
    "disconnect": "plug_disconnected_20_regular",
    "manage-users": "people_settings_20_regular",
    "palette": "color_20_regular",
    "start-page": "window_text_20_regular",
    "speed": "top_speed_20_regular",
    "windows": "window_multiple_20_regular",
    "options": "text_bullet_list_ltr_20_regular",
    "pause": "pause_circle_20_regular",
    "copy": "copy_20_regular",
    "folder": "folder_open_20_regular",
    "info": "info_20_regular",
    "person": "person_20_regular",
    "dismiss": "dismiss_20_regular",
    "chevron-down": "chevron_down_20_regular",
    "chevron-up": "chevron_up_20_regular",
    "chevron-right": "chevron_right_20_regular",
    "expand": "arrow_expand_20_regular",
    "collapse": "arrow_minimize_20_regular",
    "web": "globe_search_20_regular",
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, src in ICONS.items():
        path = os.path.join(SRC, src + ".svg")
        if not os.path.exists(path):
            path = os.path.join(SRC, src + ".svg")
        if not os.path.exists(path):
            print("missing", src)
            continue
        svg = open(path).read()
        svg = re.sub(r'fill="#[0-9a-fA-F]{3,6}"', 'fill="#ffffff"', svg)
        with open(os.path.join(OUT, f"tm-{name}-symbolic.svg"), "w") as f:
            f.write(svg)
    print("wrote", len(ICONS), "icons to", OUT)


if __name__ == "__main__":
    main()
