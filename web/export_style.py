"""Visual tuning knobs for the exported PNG (MainCanvas._export_png in
main.py) -- colors, insets, weights, font sizes. Deliberately kept separate
from main.py's drawing *logic* (which cells get shaded, which edges go
flush, where labels/markers get positioned) so the look of an export can be
tweaked here without touching anything that computes piece connectivity.

Not used by the live interactive board at all -- that has its own separate
constants near the top of main.py (_ACCIDENTAL_COLOR, _FINGER_BADGE_COLOR,
etc), since the board's translucent mode-colored pieces and this export's
solid black/white/gray print scheme are intentionally different palettes
(see the big comment above _EXPORT_FOOTPRINT_FILL_COLOR in main.py for why).

To restyle the export, just change values here and reload -- nothing else
needs to change. A few notes on what each group actually controls:

- The two insets below control the "pipe" effect from the note badge
  outward: _EXPORT_FOOTPRINT_INSET is the buffer between the shaded
  "footprint" background and a cell's true edge wherever that edge *isn't*
  shared with another cell of the same placed piece (a flush/shared edge
  always extends the shading all the way to the true edge, regardless of
  this constant -- that's the connectivity effect itself, not something
  this inset governs). _EXPORT_NOTE_INSET is the buffer between the note
  badge itself and the cell edge, applied on all four sides always,
  independent of neighbors. Per direct user feedback, the badge should
  read as the bigger, more prominent shape and the footprint shading as a
  slimmer background band peeking out only where two same-piece cells
  actually connect -- so _EXPORT_NOTE_INSET should stay smaller than
  _EXPORT_FOOTPRINT_INSET (a bigger badge, a comparatively tighter pipe).
- _EXPORT_NOTE_OUTLINE_COLOR/_WEIGHT give the note badge its own border,
  separating it visually from the footprint shading sitting behind it even
  where the two colors are close in value.
"""

# Print-oriented: pure black/white/gray throughout (no mode colors),
# heavier lines/text than the interactive board since these are meant to
# be printed small. The string-name labels and fret-position dots are
# deliberately faint/small (a light gray still prints fine in black &
# white) so they read as orientation context, not competing with the
# actual note content.
EXPORT_CELL_BORDER_COLOR = "#D0D0D0"
EXPORT_CELL_BORDER_WEIGHT = 2

# The note badge itself: root/tonic notes stay solid black, every other
# note goes gray -- see MainCanvas._is_tonic/_auto_tonic_positions.
EXPORT_CELL_FILL_COLOR = "#000000"
EXPORT_NON_ROOT_FILL_COLOR = "#8A8A8A"
# Accidental cells (see Piece.is_accidental) get a diagonal black-and-
# white hatch instead of the root/non-root fill split above -- being
# off-scale by construction is the more specific fact worth flagging on
# export, and per direct user feedback the export's whole point is
# staying legible in pure black and white (print, photocopy, grayscale
# scan), which a distinct *color* (purple, this constant's predecessor)
# doesn't survive -- it reads identically to EXPORT_NON_ROOT_FILL_COLOR's
# plain gray once color drops out. Same base gray as that non-root fill on
# purpose; the stripes are what set it apart, not a different shade.
EXPORT_ACCIDENTAL_FILL_COLOR = "#8A8A8A"
EXPORT_ACCIDENTAL_STRIPE_COLOR = "#000000"
EXPORT_ACCIDENTAL_STRIPE_SPACING = 8
EXPORT_ACCIDENTAL_STRIPE_WEIGHT = 3
# A thin border around the note badge so it reads as its own distinct
# shape sitting on top of the footprint shading, even where the two
# colors are close (e.g. a non-root gray badge over the gray-ish pipe).
EXPORT_NOTE_OUTLINE_COLOR = "#000000"
EXPORT_NOTE_OUTLINE_WEIGHT = 2

# The "pipe" -- every cell that's part of some placed piece's footprint (a
# real note *or* a skipped-fret gap) gets this background. Darker than a
# faint tint so the connectivity it shows reads clearly at print scale, but
# still lighter than EXPORT_NON_ROOT_FILL_COLOR so a gray non-root badge
# still stands out against it. See this file's docstring for how the two
# insets below relate.
EXPORT_FOOTPRINT_FILL_COLOR = "#C9C9C9"
EXPORT_FOOTPRINT_INSET = 10
EXPORT_NOTE_INSET = 5

# Technique connection glyphs (slide/hammer-on/pull-off/roll/barre -- see
# draw_connection in main.py).
EXPORT_CONNECTION_COLOR = "#000000"

# The label text drawn inside each note badge (note name / interval /
# finger letter, depending on the selected export view).
EXPORT_LABEL_COLOR = "#FFFFFF"
EXPORT_LABEL_FONT_SIZE = 20
# The vanilla view's note name ("C#2") splits into a letter part ("C#") at
# the usual EXPORT_LABEL_FONT_SIZE and a trailing octave digit ("2") at
# this smaller size -- the octave number matters far less than the letter,
# so it's de-emphasized rather than drawn at equal weight (see
# _split_note_octave in main.py).
EXPORT_NOTE_OCTAVE_FONT_SIZE = 10

# String names, anchored at the true open-string column (see main.py's
# _export_png) -- which can mean sitting on top of a note badge/footprint
# shading rather than on blank canvas whenever a piece overhangs past the
# open string, so this gets a white halo to stay legible either way. Built
# from offset copies (see EXPORT_STRING_LABEL_HALO_OFFSETS), not a stroke
# on the text itself -- a stroke there doesn't draw a clean outline in this
# renderer, it swallows the fill entirely (confirmed visually).
EXPORT_STRING_LABEL_COLOR = "#888888"
EXPORT_STRING_LABEL_FONT_SIZE = 12
EXPORT_STRING_LABEL_MARGIN = 10
EXPORT_STRING_LABEL_OUTLINE_COLOR = "#FFFFFF"
EXPORT_STRING_LABEL_HALO_OFFSETS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]

# Standard inlay dots below the fretboard (3/5/7/9/12...), plus the open
# string's own "O" marker (see the fret-marker loop's comment in main.py
# for why fret 0 needs a distinct glyph instead of just no dot).
EXPORT_FRET_MARKER_COLOR = "#888888"
EXPORT_FRET_MARKER_RADIUS = 4
EXPORT_OPEN_STRING_MARKER_FONT_SIZE = 14

# The interval view's small raised ordinal suffix ("2nd", "3rd", ...) --
# see _export_label/_ordinal_suffix in main.py for the digit-to-suffix
# text mapping itself (that's data/logic, not a style knob, so it stays in
# main.py); this one just controls how that suffix is drawn (its position
# comes from EXPORT_TEXT_WIDTH_FACTOR below, not a fixed offset).
EXPORT_ORDINAL_SUFFIX_FONT_SIZE = 11
# No text-measurement API is available (see _estimate_text_width in
# main.py), so a main+suffix label's split point (interval's digit+
# ordinal-suffix, vanilla's letter+octave) is estimated from character
# count instead of exact pixel width -- this is that estimate's average
# per-character width, as a fraction of font size. Tuned by eye; real
# character widths vary; a 2-character main part like "F#" no longer
# visibly overflows its cell with this in place, which a fixed offset
# (this constant's predecessor) couldn't account for.
EXPORT_TEXT_WIDTH_FACTOR = 0.6

# The physical "nut" -- the board's edge just before column 0 -- drawn as
# a solid bar sitting behind every other layer (grid, footprint shading,
# badges) so it reads as a structural landmark, not another piece of note
# content. Only drawn when the export's own column range actually reaches
# column 0 (mirrors the open-string "O" marker's own guard in
# _export_png), positioned at that column's left edge and overhanging the
# fretboard's own top/bottom edges slightly, the way a real nut is a bit
# larger than the strings crossing it -- makes it immediately visible
# which column is the open string, and that nothing to its left (an
# overhanging piece past the open string, see Piece.snap_to_grid) is
# actually playable.
EXPORT_NUT_COLOR = "#000000"
EXPORT_NUT_WIDTH = 8
EXPORT_NUT_OVERHANG = 8
