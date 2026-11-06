# SPDX-License-Identifier: GPL-3.0-or-later
"""Every size and colour of the print dialog, in one place.

Measured on the reference modern print dialog (visual/reference branch,
design/reference/measurements.json, sections print_dialog / print_dialog_menus).
The reference gives positions relative to the window's outer top-left, which
includes a 1 px frame; GTK draws that frame outside the window content (CSD), so
the positions below are CONTENT coordinates = reference - WINDOW_FRAME.
Nothing else in the package hard-codes a pixel or a colour.
"""

# ------------------------------------------------------------------ window
WINDOW_FRAME = 1                 # the 1 px outline GTK draws around the content
WINDOW_WIDTH = 852               # outer, frame included (reference 852 × 734)
WINDOW_HEIGHT = 734
CONTENT_WIDTH = WINDOW_WIDTH - 2 * WINDOW_FRAME     # 850
CONTENT_HEIGHT = WINDOW_HEIGHT - 2 * WINDOW_FRAME   # 732

# ------------------------------------------------------------------ title row (drag area)
HEADER_HEIGHT = 79               # body top to the preview box / first label
TITLE_X = 24                     # label box; ink starts 1 px right (ref ink x 26 outer)
TITLE_Y = 24                     # label box; baseline 38 (ref 39 outer)
HEADING_SIZE = 14                # the title is body-size semibold, not a display heading
HEADING_WEIGHT = 600
CLOSE_BOX = (804, 0, 46, 33)     # x, y, w, h (ref hover box 805,0 47×34 outer, frame included)
CLOSE_GLYPH = 10                 # the × is 10 × 10 px (ref 823..832 × 12..21 outer)
# preview header: prev / next page carets and the fit-to-page button, glyph boxes
PREV_GLYPH = (488, 43, 6, 8)
NEXT_GLYPH = (584, 43, 6, 8)
FIT_GLYPH = (643, 41, 16, 12)
HEADER_BUTTON = 32               # hit box around each glyph (hover background)

# ------------------------------------------------------------------ settings column
LEFT_COLUMN_WIDTH = 315          # = preview box x
LEFT_PADDING = (0, 24, 16, 24)   # top, right, bottom, left (labels start at the column top)
CONTROL_WIDTH = 267
TEXT_SIZE = 14                   # every text in the dialog is 14 px
LINE_HEIGHT = 17                 # 14 px text: label box 17 px, baseline at 14
TEXT_NUDGE = 1                   # Selawik's baseline sits 1 px higher than the reference font's:
                                 # labels move down 1 px inside the same layout boxes
SUMMARY_SIZE = 14
LABEL_GAP = 11                   # label box bottom -> control top (ref baseline 94 -> combo 108)
FIELD_GAP = 16                   # control bottom -> next label box (ref combo 242 -> baseline 272)
LINK_GAP_ABOVE = 13              # printer combo -> "Add a printer" link box
LINK_GAP_BELOW = 1               # link box -> next label box
CONTROL_HEIGHT = 32              # printer combo, copies, pages, colour, buttons
ICON_CONTROL_HEIGHT = 38         # orientation combo (has a page icon)
CONTROL_RADIUS = 4
CONTROL_PAD_X = 12               # text starts 13 px inside the combo (ref ink x 38 for combo x 25)
ICON_CONTROL_PAD_X = 11          # the page icon starts 14 px inside (ref icon x 39)
TEXT_RAISE = 1                   # combo text sits 1.5 px above centre (ref baseline 128 in 108..140)
ICON_TEXT_RAISE = 5              # 3.5 px in the 38 px combo (ref baseline 225 in 204..242)
ICON_GAP = 11                    # page icon -> text in the orientation combo
CHEVRON_PAD = 11                 # chevron icon (16 px, glyph 8 × 5) from the right inner edge
FOCUS_RING = 2                   # ring 2 px + gap 2 px, outside the control
FOCUS_GAP = 2
FOCUS_PILL = (3, 16)             # accent pill on the left of a focused combo (ref 4 × 16 incl. AA)
LINK_HEIGHT = 22                 # "Add a printer" hover box (icon link); text link is 19
TEXT_LINK_HEIGHT = 19
LINK_ICON = 13                   # the "+" glyph
LINK_ICON_GAP = 11               # "+" -> text
TOGGLE_LABEL_GAP = 16            # "Print to file" label box -> switch
TOGGLE_SIZE = (40, 20)
TOGGLE_KNOB = 12                 # knob x 29 -> 49 (outer) = 4 px inset each side
TOGGLE_KNOB_HOVER = 14
TOGGLE_TEXT_GAP = 12             # switch -> "Off"/"On"
HINT_GAP = 10                    # switch -> hint label box
MORE_GAP = 19                    # hint label box -> "More settings" link box

# ------------------------------------------------------------------ footer
FOOTER_HEIGHT = 81               # 1 px separator + 24 + 32 + 24 (ref 82 incl. bottom frame)
FOOTER_PADDING = 24
BUTTON_X = 433                   # Print button left edge (content)
BUTTON_WIDTHS = (193, 192)       # Print, Cancel (ref 434..627 and 635..827 outer)
BUTTON_MIN_WIDTH = 192
BUTTON_GAP = 8
CHECK_SIZE = 20
CHECK_TEXT_GAP = 8               # check box -> wrapped label (ref ink x 54 outer)
CHECK_LINE_HEIGHT = 18           # two-line label, baselines 692 / 710
CHECK_Y = 7                      # check box top below the buttons' top (ref 684 vs 677)

# ------------------------------------------------------------------ preview
PREVIEW_BOX = (315, 79, 511, 548)   # x, y, w, h; border 1 px, radius 4
PREVIEW_MARGIN = 32              # space around the sheet inside the preview box
PREVIEW_SHADOW = 8               # blur-ish offset of the sheet shadow
PREVIEW_NUP_GAP = 0.04           # gap between pages on one sheet, fraction of the sheet's short side
PREVIEW_PLACEHOLDER_LINES = True # faint text-line hints when a sheet has no page content

# Colours of the preview drawing per theme (sheet, shadow, page outline, hint lines).
PREVIEW_LIGHT = {
    "background": (0.976, 0.976, 0.976),
    "sheet": (1.0, 1.0, 1.0),
    "shadow": (0.0, 0.0, 0.0, 0.16),
    "outline": (0.0, 0.0, 0.0, 0.10),
    "hint": (0.0, 0.0, 0.0, 0.07),
    "margin": (0.0, 0.40, 0.75, 0.25),
}
PREVIEW_DARK = {
    "background": (0.157, 0.157, 0.157),
    "sheet": (1.0, 1.0, 1.0),
    "shadow": (0.0, 0.0, 0.0, 0.45),
    "outline": (0.0, 0.0, 0.0, 0.25),
    "hint": (0.0, 0.0, 0.0, 0.07),
    "margin": (0.30, 0.76, 1.0, 0.35),
}

# ------------------------------------------------------------------ pop-up menus (combo lists)
MENU_RADIUS = 8                  # ref 7 (first differing pixel)
MENU_PAD = (4, 5)                # vertical, horizontal inside the 1 px border
MENU_ROW_MARGIN = 2              # above and below each row: rows 44 / 37 px apart
MENU_ROW_HEIGHT = 33             # printer list row (ref highlight 33)
MENU_ICON_ROW_HEIGHT = 40        # orientation list row (ref highlight 40)
MENU_PILL = (3, 16)
MENU_PILL_X = 1                  # pill inset from the row's left edge
MENU_ROW_PAD_X = 12              # row content inset (ref icon x 45 / text x 70 in a row at x 31)
MENU_POPUP_GAP = 6               # GTK leaves this much between a popover and its anchor
MENU_ROW_SHIFT = 1               # selected row top - combo top (ref printer list: 109 vs 108)
MENU_ICON_ROW_SHIFT = -3         # same for the icon list (ref orientation list: 201 vs 204)              # accent pill of the selected row

# ------------------------------------------------------------------ palette
ACCENTS = {
    "blue": ("#0067c0", "#4cc2ff"), "teal": ("#00777a", "#3fd5d9"), "green": ("#107c10", "#6ccb5f"),
    "yellow": ("#8a6100", "#ffd04a"), "orange": ("#c24e00", "#ff9e5e"), "red": ("#c42b1c", "#ff99a4"),
    "pink": ("#bf0077", "#ff8ad8"), "purple": ("#744da9", "#c8a8ff"), "slate": ("#4a5a70", "#a9b8cc"),
}
# Link text per accent (light, dark); other accents use the accent itself.
ACCENT_TEXT = {"blue": ("#003e92", "#99ebff")}

DARK = {
    "bg": "#282828", "footer": "#202020", "footer-border": "#373737", "frame": "#3e3e3e",
    "fg": "#ffffff", "fg-ctl": "#ffffff", "fg2": "#c5c5c5", "fg3": "#9d9d9d", "fg-disabled": "#767676",
    "ctl": "#353535", "ctl-hover": "#3a3a3a", "ctl-press": "#2f2f2f", "ctl-focus": "#414141", "ctl-focus-hover": "#464646",
    "ctl-focus-border": "#484848", "ctl-focus-border-bottom": "#434343",
    "ctl-border": "#373737", "ctl-border-top": "#3c3c3c", "ctl-border-bottom": "#373737",
    "btn": "#2d2d2d", "btn-hover": "#323232", "btn-press": "#272727",
    "btn-border": "#303030", "btn-border-top": "#353535", "btn-border-bottom": "#303030",
    "input-focus": "#1f1f1f", "input-bottom": "rgba(255,255,255,0.54)",
    "subtle-hover": "#353535", "subtle-press": "#303030", "divider": "#3c3c3c",
    "preview-border": "#3c3c3c",
    "popover": "#2c2c2c", "popover-border": "#202020", "menu-select": "#343434", "menu-hover": "#343434",
    "shadow": "rgba(0,0,0,0.30)",
    "toggle-off": "#242424", "toggle-off-hover": "#313131", "toggle-outline": "#9b9b9b", "knob-off": "#cdcdcd",
    "check-off": "#242424", "check-outline": "#9b9b9b",
    "focus": "#ffffff", "focus-gap": "#353535", "chevron": "#c5c5c5",
    "danger": "#ff99a4", "close-hover": "#c42b1c",
}

LIGHT = {
    "bg": "#f9f9f9", "footer": "#f3f3f3", "footer-border": "#eaeaea", "frame": "#adadad",
    "fg": "#1a1a1a", "fg-ctl": "#1b1b1b", "fg2": "#5f5f5f", "fg3": "#8a8a8a", "fg-disabled": "#9f9f9f",
    "ctl": "#fdfdfd", "ctl-hover": "#f9f9f9", "ctl-press": "#f9f9f9", "ctl-focus": "#fefefe", "ctl-focus-hover": "#fbfbfb",
    "ctl-focus-border": "#eeeeee", "ctl-focus-border-bottom": "#d4d4d4",
    "ctl-border": "#eaeaea", "ctl-border-top": "#eaeaea", "ctl-border-bottom": "#d1d1d1",
    "btn": "#fbfbfb", "btn-hover": "#f6f6f6", "btn-press": "#f5f5f5",
    "btn-border": "#e5e5e5", "btn-border-top": "#e5e5e5", "btn-border-bottom": "#cccccc",
    "input-focus": "#ffffff", "input-bottom": "rgba(0,0,0,0.45)",
    "subtle-hover": "#f0f0f0", "subtle-press": "#ebebeb", "divider": "#eaeaea",
    "preview-border": "#d1d1d1",
    "popover": "#f9f9f9", "popover-border": "#eaeaea", "menu-select": "#f3f3f3", "menu-hover": "#f3f3f3",
    "shadow": "rgba(0,0,0,0.14)",
    "toggle-off": "#f3f3f3", "toggle-off-hover": "#eaeaea", "toggle-outline": "#8a8a8a", "knob-off": "#5c5c5c",
    "check-off": "#f3f3f3", "check-outline": "#8a8a8a",
    "focus": "#1a1a1a", "focus-gap": "#fdfdfd", "chevron": "#5f5f5f",
    "danger": "#c42b1c", "close-hover": "#c42b1c",
}

FONT_TEXT = '"Segoe UI Variable Text", "Segoe UI", "Selawik", "Inter", sans-serif'
FONT_DISPLAY = FONT_TEXT

# ------------------------------------------------------------------ print defaults
MARGIN_PRESETS = ("normal", "narrow", "none")   # normal = the paper's default margins
NARROW_MARGIN_MM = 3.2
PAGES_PER_SHEET = (1, 2, 4, 6, 9, 16)
PAPER_SIZES = ("iso_a4", "na_letter", "na_legal", "iso_a3", "iso_a5", "iso_b5", "na_executive")
TOKEN_LIFETIME_S = 3600          # PreparePrint tokens are forgotten after an hour
