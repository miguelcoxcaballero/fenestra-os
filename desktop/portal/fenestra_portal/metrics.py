# SPDX-License-Identifier: GPL-3.0-or-later
"""Every size and colour of the print dialog, in one place.

The layout follows the reference modern print dialog (settings column on the left,
preview on the right, buttons bottom right). Values here are estimates until the
measurements file arrives; nothing else in the package hard-codes a pixel or a colour.
"""

# ------------------------------------------------------------------ window
WINDOW_WIDTH = 860
WINDOW_HEIGHT = 640
MIN_WIDTH = 720
MIN_HEIGHT = 520

# ------------------------------------------------------------------ settings column
LEFT_COLUMN_WIDTH = 360          # whole column, padding included
LEFT_PADDING = (24, 24, 16, 24)  # top, right, bottom, left
HEADING_SIZE = 28                # "Print" heading, px
SUMMARY_SIZE = 12                # "Total: N sheets of paper"
LABEL_GAP = 6                    # label -> control
FIELD_GAP = 18                   # control -> next label
CONTROL_HEIGHT = 32

# ------------------------------------------------------------------ footer
FOOTER_HEIGHT = 80
FOOTER_PADDING = 24
BUTTON_MIN_WIDTH = 120
BUTTON_GAP = 8

# ------------------------------------------------------------------ preview
PREVIEW_MARGIN = 40              # space around the sheet inside the preview area
PREVIEW_SHADOW = 8               # blur-ish offset of the sheet shadow
PREVIEW_NUP_GAP = 0.04           # gap between pages on one sheet, fraction of the sheet's short side
PREVIEW_PLACEHOLDER_LINES = True # faint text-line hints on the blank PreparePrint page
PAGER_HEIGHT = 48

# Colours of the preview area per theme (sheet, background, shadow, page outline, hint lines).
PREVIEW_LIGHT = {
    "background": (0.886, 0.886, 0.886),
    "sheet": (1.0, 1.0, 1.0),
    "shadow": (0.0, 0.0, 0.0, 0.16),
    "outline": (0.0, 0.0, 0.0, 0.10),
    "hint": (0.0, 0.0, 0.0, 0.07),
    "margin": (0.0, 0.40, 0.75, 0.25),
}
PREVIEW_DARK = {
    "background": (0.125, 0.125, 0.125),
    "sheet": (1.0, 1.0, 1.0),
    "shadow": (0.0, 0.0, 0.0, 0.45),
    "outline": (0.0, 0.0, 0.0, 0.25),
    "hint": (0.0, 0.0, 0.0, 0.07),
    "margin": (0.30, 0.76, 1.0, 0.35),
}

# ------------------------------------------------------------------ palette (same tokens as Fenestra Settings/Store)
ACCENTS = {
    "blue": ("#0067c0", "#4cc2ff"), "teal": ("#00777a", "#3fd5d9"), "green": ("#107c10", "#6ccb5f"),
    "yellow": ("#8a6100", "#ffd04a"), "orange": ("#c24e00", "#ff9e5e"), "red": ("#c42b1c", "#ff99a4"),
    "pink": ("#bf0077", "#ff8ad8"), "purple": ("#744da9", "#c8a8ff"), "slate": ("#4a5a70", "#a9b8cc"),
}

DARK = {
    "bg": "#202020", "pane": "#272727", "footer": "#202020",
    "fg": "#ffffff", "fg2": "#c5c5c5", "fg3": "#7e7e7e",
    "ctl": "rgba(255,255,255,0.061)", "ctl-hover": "rgba(255,255,255,0.084)", "ctl-press": "rgba(255,255,255,0.033)",
    "ctl-border": "rgba(255,255,255,0.07)", "ctl-border-bottom": "rgba(255,255,255,0.05)",
    "input": "rgba(255,255,255,0.061)", "input-focus": "#1f1f1f", "input-bottom": "rgba(255,255,255,0.54)",
    "subtle-hover": "rgba(255,255,255,0.061)", "subtle-press": "rgba(255,255,255,0.042)",
    "subtle-select": "rgba(255,255,255,0.061)", "divider": "rgba(255,255,255,0.084)",
    "popover": "#2c2c2c", "popover-border": "rgba(0,0,0,0.35)", "shadow": "rgba(0,0,0,0.30)",
    "danger": "#ff99a4", "close-hover": "#c42b1c",
}

LIGHT = {
    "bg": "#f3f3f3", "pane": "#f9f9f9", "footer": "#f3f3f3",
    "fg": "#1b1b1b", "fg2": "#5d5d5d", "fg3": "#a0a0a0",
    "ctl": "rgba(255,255,255,0.70)", "ctl-hover": "rgba(249,249,249,0.50)", "ctl-press": "rgba(249,249,249,0.30)",
    "ctl-border": "rgba(0,0,0,0.073)", "ctl-border-bottom": "rgba(0,0,0,0.16)",
    "input": "rgba(255,255,255,0.70)", "input-focus": "#ffffff", "input-bottom": "rgba(0,0,0,0.45)",
    "subtle-hover": "rgba(0,0,0,0.037)", "subtle-press": "rgba(0,0,0,0.024)", "subtle-select": "rgba(0,0,0,0.055)",
    "divider": "rgba(0,0,0,0.08)", "popover": "#f9f9f9", "popover-border": "rgba(0,0,0,0.12)",
    "shadow": "rgba(0,0,0,0.14)", "danger": "#c42b1c", "close-hover": "#c42b1c",
}

FONT_TEXT = '"Segoe UI Variable Text", "Segoe UI", "Selawik", "Inter", sans-serif'
FONT_DISPLAY = '"Segoe UI Variable Display", "Segoe UI Variable Text", "Segoe UI", "Selawik", "Inter", sans-serif'

# ------------------------------------------------------------------ print defaults
MARGIN_PRESETS = ("normal", "narrow", "none")   # normal = the paper's default margins
NARROW_MARGIN_MM = 3.2
PAGES_PER_SHEET = (1, 2, 4, 6, 9, 16)
PAPER_SIZES = ("iso_a4", "na_letter", "na_legal", "iso_a3", "iso_a5", "iso_b5", "na_executive")
TOKEN_LIFETIME_S = 3600          # PreparePrint tokens are forgotten after an hour
