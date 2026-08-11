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
# With Grayscale unchecked (see controls.get_grayscale), the root/tonic
# note keeps its own piece color instead of being darkened -- per direct
# user feedback, the color is semantic (which mode/tetrachord this note
# belongs to) and darkening it both hides that meaning and reads as hard
# to make out. Root status still needs to read at a glance, so it gets
# this heavier outline instead -- same idea as the live board's own
# _TONIC_BORDER_WEIGHT in main.py, just for the export's badge outline.
# Grayscale keeps its original solid-black-fill treatment for the root
# untouched (see EXPORT_CELL_FILL_COLOR) -- that scheme has no color to
# preserve, so darkening was never the readability problem there.
EXPORT_TONIC_OUTLINE_WEIGHT = 4

# A note badge shared by two pieces (their pivot -- see MainCanvas.
# _is_tonic) hatches between both contributing colors instead of picking
# one arbitrarily (see MainCanvas._export_png's cell_pieces) -- the same
# _draw_diagonal_hatch mechanism as an accidental's own black-on-gray
# hatch, just with the other piece's color standing in for the fixed
# black. Not the same spacing/weight, though: two actual mode colors
# need to each read clearly as their own color, where accidental's hatch
# only ever needs its black stripes to read against gray -- per direct
# user feedback the accidental spacing's finer stripes made two real
# colors blend into a muddier, harder-to-place-either-color texture at a
# glance, so this is roughly double both values (half as many stripes,
# same proportion of fill to stripe within each one). Only relevant with
# Grayscale unchecked -- see controls.get_grayscale -- since a grayscale
# badge's fill carries no piece-identity information to hatch in the
# first place.
EXPORT_PIVOT_STRIPE_SPACING = 16
EXPORT_PIVOT_STRIPE_WEIGHT = 6

# "Played only" export option (see MainCanvas._export_png/controls.
# get_played_only): a note that isn't played (see Piece.is_played --
# no fingering *and* not explicitly right-click-marked played) gets its
# badge fill, outline, accidental hatch, and label all swapped for
# these flat, opaque colors instead of drawn at full strength. This
# used to be done with alpha transparency instead of a distinct solid
# color, which reads fine in isolation but -- per direct user feedback
# -- badly on an actual pattern: since the badge sits *on top of* the
# footprint/pipe shading (see EXPORT_FOOTPRINT_FILL_COLOR), a
# translucent badge lets that gray pipe bleed straight through it,
# muddying the fill into something hard to tell apart from a played
# note's own gray. A flat opaque color has no such blending -- it
# simply overwrites the pipe the same way every other badge already
# does, and reads as unambiguously lighter than a played note's own
# fill/outline/label at a glance. Label color needs to go dark instead
# of white here specifically because the fill itself is now light,
# not because "faded" implies it -- white-on-light-gray would be
# unreadable.
EXPORT_UNPLAYED_FILL_COLOR = "#E5E5E5"
EXPORT_UNPLAYED_OUTLINE_COLOR = "#BFBFBF"
EXPORT_UNPLAYED_STRIPE_COLOR = "#BFBFBF"
EXPORT_UNPLAYED_LABEL_COLOR = "#A0A0A0"

# The "pipe" -- every cell that's part of some placed piece's footprint (a
# real note *or* a skipped-fret gap), plus every cross-string connector
# bridging two of a piece's own notes on adjacent strings -- gets this
# background with Grayscale on. Darker than a faint tint so the
# connectivity it shows reads clearly at print scale, but still lighter
# than EXPORT_NON_ROOT_FILL_COLOR so a gray non-root badge still stands out
# against it. See this file's docstring for how the two insets below relate.
EXPORT_FOOTPRINT_FILL_COLOR = "#C9C9C9"
EXPORT_FOOTPRINT_INSET = 11
EXPORT_NOTE_INSET = 7
# With Grayscale unchecked, the pipe uses the owning piece's own mode color
# instead of the flat gray above -- per direct user feedback, this makes it
# far more obvious at a glance which pipe belongs to which pattern when
# several sit on adjacent strings. Darkened (not the plain mode color) so
# it still reads as background sitting behind/around the badges, which
# keep the undarkened color -- same figure/ground relationship the flat
# gray pipe already had relative to a colored badge.
EXPORT_PIPE_DARKEN_FACTOR = 0.75

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
# The interval view's quality-prefixed label ("Aug4", "dim5", "M3") runs up
# to 4 characters, wider than any other view's label -- smaller than
# EXPORT_LABEL_FONT_SIZE so the widest labels (Lydian's Aug4, Locrian's
# dim5) stay inside the note badge instead of overflowing it.
EXPORT_INTERVAL_LABEL_FONT_SIZE = 14

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

# No text-measurement API is available (see _estimate_text_width in
# main.py), so the vanilla view's letter+octave split point is estimated
# from character count instead of exact pixel width -- this is that
# estimate's average per-character width, as a fraction of font size. Tuned
# by eye; real character widths vary; a 2-character main part like "F#" no
# longer visibly overflows its cell with this in place, which a fixed
# offset (this constant's predecessor) couldn't account for.
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

# The exported PNG is cropped to just this content -- the pattern's own
# grid plus its markers/labels -- instead of the full interactive canvas
# (which includes both mode trays and would otherwise dwarf a small
# pattern in a sea of blank space). This is the padding kept around that
# content on every side, since there's no text-measurement API (see
# EXPORT_TEXT_WIDTH_FACTOR above) to compute the string labels' and nut's
# exact pixel extent -- generous enough to never clip a label, at the
# cost of a small, deliberately unused margin rather than a razor-tight
# crop that risks cutting something off.
EXPORT_CANVAS_PADDING = 30
