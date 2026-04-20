"""
ui/tokens.py — Design tokens: colours, fonts, and shared constants.

Colour roles (use by role, not by hue):
  BG / CARD / CARD2 / INPUT   — surface hierarchy, darkest → lightest
  BORDER / BORDER_ACTIVE      — structural lines
  ACCENT*                     — primary action (blue)
  SUCCESS*                    — positive state (green)
  WARNING*                    — secondary action / caution (amber)
  DANGER*                     — error / exclusion (red)
  TEXT / TEXT_DIM / TEXT_MUTED — typography hierarchy
"""

# ---------------------------------------------------------------------------
# Surfaces  (3-stop depth stack — enough contrast without going flat)
# ---------------------------------------------------------------------------

BG           = "#0b0d10"   # page background — darkest
CARD         = "#13161c"   # primary card surface
CARD2        = "#1a1e26"   # nested / hover surface
INPUT        = "#1e222b"   # input fields, scrollable areas

# ---------------------------------------------------------------------------
# Borders
# ---------------------------------------------------------------------------

BORDER        = "#2a2f3a"   # default structural border
BORDER_ACTIVE = "#3d4455"   # focused / active border

# ---------------------------------------------------------------------------
# Accent — primary action (blue)
# ---------------------------------------------------------------------------

ACCENT       = "#4d9cf8"   # bright, readable on dark surfaces
ACCENT_DIM   = "#162847"   # tinted surface behind accent elements
ACCENT_GLOW  = "#3b82f6"   # solid fill for primary CTA button

# ---------------------------------------------------------------------------
# Success — ready / done (green)
# ---------------------------------------------------------------------------

SUCCESS      = "#34d058"   # stronger green, clears WCAG AA on CARD
SUCCESS_DIM  = "#0b2a18"

# ---------------------------------------------------------------------------
# Warning — secondary action / in-progress (amber)
# ---------------------------------------------------------------------------

WARNING      = "#e3a020"   # amber — Preview Backup button, scanning state
WARNING_DIM  = "#2c1e00"

# ---------------------------------------------------------------------------
# Danger — errors / exclusions (red)
# ---------------------------------------------------------------------------

DANGER       = "#f0524f"
DANGER_DIM   = "#2e1010"

# ---------------------------------------------------------------------------
# Typography colours  (3-level hierarchy)
# ---------------------------------------------------------------------------

TEXT         = "#dde3ec"   # primary — titles, values, active labels
TEXT_DIM     = "#7c8799"   # secondary — paths, helper text, subtitles
TEXT_MUTED   = "#40464f"   # tertiary — placeholders, empty-state copy

# ---------------------------------------------------------------------------
# Fonts  (strict role-based scale — don't mix sizes ad-hoc)
#
#  FONT_TITLE   page/section heading
#  FONT_HEAD    card header, stat value
#  FONT_BODY    standard prose / form labels
#  FONT_SMALL   helper text, pill labels, timestamps
#  FONT_MONO    file paths, code, numeric values
#  FONT_LABEL   all-caps micro-labels (section headings inside cards)
# ---------------------------------------------------------------------------

FONT_TITLE   = ("Segoe UI",  17, "bold")
FONT_HEAD    = ("Segoe UI",  12, "bold")
FONT_BODY    = ("Segoe UI",  12)
FONT_SMALL   = ("Segoe UI",  10)
FONT_MONO    = ("Consolas",  10)
FONT_LABEL   = ("Segoe UI",   8, "bold")
