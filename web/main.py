"""
fretboard-lab starting point.

This keeps the same drag-and-snap mechanics we already validated
(pieces -> a grid, released -> snapped into place), because that's
structurally the same interaction you'll want for the real app:

    tetromino  -> diagram component (a note dot, a barre, a label, ...)
    "board"    -> fretboard
    spawn area -> a "drawer" of draggable components

Treat this as scaffolding to reshape, not a finished design. Ideas for
where to take it from here are in the README.

Requires nothing server-side -- this file is fetched and executed by
PyScript/Pyodide in the browser. Edit, save: devreload.py hot-swaps it
in place, no manual refresh or Pyodide reboot needed.
"""

import asyncio

import controls
import js
import modes as modes_module
import sketchingpy
from config import (
    CHROMATIC_SCALE_FLATS_WITH_OCTAVE,
    CHROMATIC_SCALE_SHARPS_WITH_OCTAVE,
    FRET_HEIGHT,
    FRET_WIDTH,
    FRETBOARD_BORDER_X,
    FRETBOARD_BORDER_Y,
    FRETBOARD_WIDTH,
    MODE_INTERVALS,
    MODE_TRAY_HEIGHT,
    TOTAL_HEIGHT,
    TOTAL_WIDTH,
    AccidentalType,
    get_scale_degree,
    get_scale_pitch_classes,
    pitch_class_semitone,
    semitone_distance,
)
from export_style import (
    EXPORT_ACCIDENTAL_FILL_COLOR,
    EXPORT_ACCIDENTAL_STRIPE_COLOR,
    EXPORT_ACCIDENTAL_STRIPE_SPACING,
    EXPORT_ACCIDENTAL_STRIPE_WEIGHT,
    EXPORT_CANVAS_PADDING,
    EXPORT_CELL_BORDER_COLOR,
    EXPORT_CELL_BORDER_WEIGHT,
    EXPORT_CELL_FILL_COLOR,
    EXPORT_CONNECTION_COLOR,
    EXPORT_FOOTPRINT_FILL_COLOR,
    EXPORT_FOOTPRINT_INSET,
    EXPORT_FRET_MARKER_COLOR,
    EXPORT_FRET_MARKER_RADIUS,
    EXPORT_LABEL_COLOR,
    EXPORT_LABEL_FONT_SIZE,
    EXPORT_NON_ROOT_FILL_COLOR,
    EXPORT_NOTE_INSET,
    EXPORT_NOTE_OCTAVE_FONT_SIZE,
    EXPORT_NOTE_OUTLINE_COLOR,
    EXPORT_NOTE_OUTLINE_WEIGHT,
    EXPORT_NUT_COLOR,
    EXPORT_NUT_OVERHANG,
    EXPORT_NUT_WIDTH,
    EXPORT_OPEN_STRING_MARKER_FONT_SIZE,
    EXPORT_ORDINAL_SUFFIX_FONT_SIZE,
    EXPORT_STRING_LABEL_COLOR,
    EXPORT_STRING_LABEL_FONT_SIZE,
    EXPORT_STRING_LABEL_HALO_OFFSETS,
    EXPORT_STRING_LABEL_MARGIN,
    EXPORT_STRING_LABEL_OUTLINE_COLOR,
    EXPORT_TEXT_WIDTH_FACTOR,
    EXPORT_UNPLAYED_FILL_COLOR,
    EXPORT_UNPLAYED_LABEL_COLOR,
    EXPORT_UNPLAYED_OUTLINE_COLOR,
    EXPORT_UNPLAYED_STRIPE_COLOR,
)
from fretboard import TUNINGS, FretboardBuilder
from open_string import OpenString
from pyodide.ffi import JsException, create_proxy, to_js


def _resolve_tuning(notes: list[str]) -> TUNINGS:
    """Bridge controls.get_tuning()'s raw note list back to a TUNINGS member.

    controls.py is deliberately domain-agnostic (see its docstring) -- it
    just reads the <select> value as text, so it hands back
    ["B0", "E1", ...], not a TUNINGS member. This is the one place that
    gets translated back into something FretboardBuilder.set_tuning()
    (which enforces a real TUNINGS member) will accept.
    """
    for tuning in TUNINGS:
        if tuning.value == notes:
            return tuning
    raise ValueError(f"No TUNINGS preset matches {notes!r}")


def _load_visible_modes() -> list["modes_module.Mode"]:
    """The two Modes currently picked (Tray A, then Tray B), in that order.

    Order matters here -- Tray A is meant to be the top tray, Tray B the
    bottom one, so this has to preserve the picker order rather than
    filtering modes.yaml's own canonical list (which would silently put
    whichever mode comes first in the file on top, regardless of which
    picker actually chose it).
    """
    visible_names = controls.get_visible_modes()
    modes_by_name = {mode.name: mode for mode in modes_module.load_modes("modes.yaml")}
    return [modes_by_name[name] for name in visible_names if name in modes_by_name]


def _with_alpha(hex_color: str, alpha_hex: str = "80") -> str:
    """Append an alpha channel to a "#RRGGBB" color (default ~50% opaque).

    Lets a Piece's fill stay translucent (so the fret's note letter shows
    through underneath it) without baking rendering concerns into
    modes.yaml/modes.py, which only deal in opaque mode colors.
    """
    return hex_color + alpha_hex


def _darken(hex_color: str, factor: float = 0.55) -> str:
    """Scale a "#RRGGBB" (or "#RRGGBBAA") color's RGB channels down toward
    black -- factor=1 keeps it unchanged, 0 -> black -- leaving any alpha
    suffix untouched. Used to mark the root/tonic cell as a visibly darker
    shade of the piece's own translucent color (see Piece.draw) rather than
    overriding it with an unrelated opaque fill.
    """
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    suffix = hex_color[7:]
    r, g, b = (max(0, min(255, int(channel * factor))) for channel in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}{suffix}"


# A single always-available 1x1 piece for chromatic/off-scale notes that
# don't belong to either mode tray's tetrachord -- see MainCanvas
# .accidental_piece and Piece.is_accidental. Purple doesn't collide with
# any mode color in modes.yaml (green/blue/pink/orange), the invalid-cell
# red, the selection-outline amber, or the connection pink.
_ACCIDENTAL_COLOR = "#7C3AED"
_GAP_CELL_COLOR = "#9CA3AF"
_INVALID_CELL_COLOR = "#EF4444C0"
_SCALE_HIGHLIGHT_COLOR = "#22C55E80"
_SCALE_HIGHLIGHT_RADIUS = 6
_FINGER_BADGE_COLOR = "#202020"
_FINGER_BADGE_TEXT_COLOR = "#EEEEEE"
# A right triangle tucked into the cell's own bottom-right corner (legs
# along that cell's bottom/right edges, apex at the shared corner point)
# instead of a circle centered exactly on that shared corner -- a circle
# straddled up to 4 cells equally and gave no clue which one it actually
# belonged to; the triangle's body sits strictly inside just the one cell.
_FINGER_BADGE_SIZE = 22
# White halo drawn behind the triangle (a larger copy of the same shape)
# so the badge stays visible even sitting on top of a tonic/root cell's
# now-opaque black fill (see Piece.draw / _TONIC_CELL_FILL_COLOR) -- same
# technique as draw_connection's glyph outlines.
_FINGER_BADGE_OUTLINE_COLOR = "#FFFFFF"
_FINGER_BADGE_OUTLINE_EXTRA = 3
# The played marker (see Piece.is_played) sits in the opposite corner
# from the finger badge (top-left, not bottom-right) so a note can show
# both without overlapping -- same dark-fill/white-halo styling as that
# badge, just a circle instead of a triangle, since there's no letter to
# fit inside it.
_PLAYED_MARKER_RADIUS = 6
_PLAYED_MARKER_OUTLINE_EXTRA = 3
_SELECTION_OUTLINE_COLOR = "#FBBF24"
_SELECTION_OUTLINE_WEIGHT = 3
_CONNECTION_COLOR = "#F472B6"
# The root/tonic note (see MainCanvas._is_tonic) stays the same translucent
# piece color as every other cell -- just a visibly darker shade plus a
# heavier border, rather than an opaque override that needs its own
# special-cased text color (see Piece.draw). Reserving "solid, high
# contrast, no color-coding" for the print-oriented export instead (see
# EXPORT_CELL_FILL_COLOR/EXPORT_NON_ROOT_FILL_COLOR).
_TONIC_DARKEN_FACTOR = 0.55
_TONIC_BORDER_WEIGHT = 4

_DEFAULT_PATTERN_NAME = "tetraboard-export"
# Every export color/inset/font-size knob (border, footprint "pipe" shading,
# note badge, labels, fret markers, ...) lives in export_style.py, not here
# -- see that file's own docstring for what each one controls and how the
# footprint/note insets relate. This file only has the *logic*: which cells
# get shaded, which edges go flush, what text each label shows -- see
# _export_png and _export_piece_footprints/_export_flush below for how
# export_style's constants get used.
_EXPORT_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}
# View filename suffixes, appended to the pattern-name field's value --
# see MainCanvas._export_png.
_EXPORT_VIEW_FILENAME_SUFFIXES = {"vanilla": "notes", "interval": "intervals", "fingering": "fingering"}

# Annotate-mode hotkeys (see MainCanvas._on_key_press): digits assign a
# finger letter to every selected cell, letters in _TECHNIQUE_HOTKEYS
# toggle a connection between the selected cells, and _TONIC_HOTKEY flips
# tonic status on the selection. No digit/letter collides across the three
# groups -- there's no dedicated hotkey for thumb, since "t" is claimed by
# tonic.
_FINGER_HOTKEYS = {"1": "i", "2": "m", "3": "r", "4": "p"}
_TECHNIQUE_HOTKEYS = {
    "s": "slide",
    "h": "hammer_on",
    "p": "pull_off",
    "r": "roll",
    "b": "barre",
}
_TONIC_HOTKEY = "t"
_CLEAR_FINGER_KEY = "backspace"
# Which technique types connect notes on the same string (different frets)
# vs the same fret (different strings) -- see _apply_technique_to_selection.
_SAME_STRING_TECHNIQUES = {"slide", "hammer_on", "pull_off"}
_SAME_FRET_TECHNIQUES = {"roll", "barre"}
_CONNECTION_LABELS = {"hammer_on": "H", "pull_off": "P"}


def _ordinal_suffix(degree: int) -> str:
    return _EXPORT_ORDINAL_SUFFIXES.get(degree, "th")


def _note_at_fret(string: "OpenString", col: int) -> str:
    """The note name `col` frets above `string`'s open note, computed
    directly from the full chromatic scale table rather than
    `string.frets` (only built for the playable range 0..n_frets).

    Piece.snap_to_grid already lets a placed piece overhang past the open
    string or the last fret on purpose (an unreachable pattern is still
    worth drawing) -- export needs to be able to label those overhanging
    cells too, so this indexes the underlying chromatic scale directly
    instead of `string.frets[col]`, which would either raise (col too
    large) or silently wrap around to the wrong note (col negative).
    """
    table = (
        CHROMATIC_SCALE_SHARPS_WITH_OCTAVE
        if string.accidental_type == AccidentalType.SHARP
        else CHROMATIC_SCALE_FLATS_WITH_OCTAVE
    )
    return table[table.index(string.note_identity) + col]


def _split_note_octave(note: str) -> tuple[str, str]:
    """Split a note name like "C#2" into its letter/accidental part ("C#")
    and trailing octave digits ("2") -- see _export_label's vanilla view,
    which draws the octave smaller/de-emphasized next to the letter (the
    octave number matters far less than the letter for reading a pattern
    at a glance).
    """
    split = len(note)
    while split > 0 and note[split - 1].isdigit():
        split -= 1
    return note[:split], note[split:]


def _estimate_text_width(text: str, font_size: float) -> float:
    """Rough pixel width of `text` at `font_size` -- draw_text has no real
    text-measurement API to size a main+suffix label exactly (see
    _export_png's badge-label drawing), so this per-character estimate is
    what the split point between the two parts gets centered against
    instead. Not exact (real character widths vary), but good enough to
    keep a two-character main part like "F#" from visibly overflowing its
    cell the way a fixed split point (tuned only for single characters)
    did.
    """
    return len(text) * font_size * EXPORT_TEXT_WIDTH_FACTOR


def _compute_gap_cells(cells):
    """Cells skipped between two notes on the same row of a tetra shape.

    E.g. a "straight" major tetra at cols [0, 2, 4, 5] skips cols 1 and 3
    -- those aren't extra notes or accidentals, just frets passed over,
    but they're still part of the shape, so they get a cell too (drawn
    gray in Piece.draw) rather than leaving a confusing hole.
    """
    cols_by_row: dict = {}
    for c, r in cells:
        cols_by_row.setdefault(r, []).append(c)

    gaps = []
    for r, cols in cols_by_row.items():
        for c in range(min(cols), max(cols) + 1):
            if c not in cols:
                gaps.append((c, r))
    return gaps


class Piece:
    """A draggable item living on a grid coordinate system."""

    def __init__(
        self,
        cells,
        color,
        col,
        row,
        mode_name=None,
        shape_name=None,
        annotations=None,
        name=None,
        is_accidental=False,
        played=None,
    ):
        self.cells = cells
        self.gap_cells = _compute_gap_cells(cells)
        self.color = color
        self.col = col  # can be fractional while being dragged
        self.row = row
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        # mode_name/shape_name identify which tray shape this piece came
        # from (e.g. "Major"/"right") -- not needed to draw or drag a
        # piece, but it's what Save State serializes instead of raw
        # cells, so Load State can regenerate correct cells even if the
        # tuning (and therefore string_interval) differs at load time.
        self.mode_name = mode_name
        self.shape_name = shape_name
        # Per-cell finger assignment: "dc,dr" -> a finger letter
        # (i/m/r/p -- see _FINGER_HOTKEYS), only present for cells that
        # have one. Set via MainCanvas._assign_finger_to_selection while
        # Annotate mode is on.
        self.annotations = annotations if annotations is not None else {}
        # Cells explicitly marked "played" via MainCanvas.
        # _toggle_played_at_point (right-click a cell while Annotate is
        # on), as "dc,dr" strings -- independent of self.annotations, so
        # a note can be marked played with no fingering at all (an open
        # string, or any fretted note obvious enough not to bother
        # annotating a finger for). See is_played for how this combines
        # with a fingering to answer "is this cell actually played".
        self.played = set(played) if played is not None else set()
        # None until the user right-clicks a board piece to rename it
        # (see MainCanvas._try_rename_piece) -- display_name falls back
        # to the shape's traditional name (e.g. "left", "zig") until
        # then. Stacking the same tray shape multiple times otherwise
        # gives every copy an identical, non-unique label, which is
        # exactly what renaming is for.
        self.name = name
        # True only for clones of MainCanvas.accidental_piece -- a single
        # 1x1 piece, always available regardless of which two modes Tray
        # A/B currently show, for a chromatic/off-scale note that isn't
        # part of either tray's tetrachord. Distinct color (see
        # _ACCIDENTAL_COLOR/EXPORT_ACCIDENTAL_FILL_COLOR), and skipped by
        # the scale validator (see MainCanvas._step) -- an accidental is
        # off-scale by definition, so flagging it "invalid" would defeat
        # the point of having it.
        self.is_accidental = is_accidental

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.is_accidental:
            return "accidental"
        if self.shape_name:
            return self.shape_name
        return "piece"

    def is_played(self, dc: int, dr: int) -> bool:
        """Whether this cell counts as actually played, for the "Played
        only" export option (see controls.get_played_only) and the live
        board's own played marker (see draw below) -- true if it has an
        explicit played mark (self.played), *or* a fingering at all
        (self.annotations) -- assigning one to a note you don't intend to
        play would be pointless, so that alone is enough without also
        requiring the explicit mark.
        """
        key = f"{dc},{dr}"
        return key in self.played or key in self.annotations

    def clone(self) -> "Piece":
        """A fresh, independent copy at the same position -- used to stamp
        a new board piece out of a tray template without disturbing the
        template itself (see MainCanvas._on_press: the template is an
        unlimited supply, not a single draggable instance)."""
        return Piece(
            self.cells,
            self.color,
            self.col,
            self.row,
            self.mode_name,
            self.shape_name,
            dict(self.annotations),
            self.name,
            self.is_accidental,
            set(self.played),
        )

    def get_pixel_origin(self):
        x = FRETBOARD_BORDER_X + self.col * FRET_WIDTH
        y = FRETBOARD_BORDER_Y + self.row * FRET_HEIGHT
        return x, y

    def get_pixel_center(self):
        x = FRETBOARD_BORDER_X + (self.col + 0.5) * FRET_WIDTH
        y = FRETBOARD_BORDER_Y + (self.row + 0.5) * FRET_HEIGHT
        return x, y

    def contains_point(self, px, py):
        x, y = self.get_pixel_origin()
        for dc, dr in self.cells + self.gap_cells:
            cx = x + dc * FRET_WIDTH
            cy = y + dr * FRET_HEIGHT
            if cx <= px <= cx + FRET_WIDTH and cy <= py <= cy + FRET_HEIGHT:
                return True
        return False

    def cell_at_point(self, px, py):
        """Which of this piece's own note cells (dc, dr) contains (px, py),
        or None -- like contains_point, but tells you *which* cell instead
        of just whether one matched. Only searches self.cells (the real
        notes), not gap_cells -- a gap is a fret passed over, not a note,
        so it isn't annotatable (see MainCanvas._handle_annotate_click).
        """
        x, y = self.get_pixel_origin()
        for dc, dr in self.cells:
            cx = x + dc * FRET_WIDTH
            cy = y + dr * FRET_HEIGHT
            if cx <= px <= cx + FRET_WIDTH and cy <= py <= cy + FRET_HEIGHT:
                return (dc, dr)
        return None

    def snap_to_grid(self, grid_cols, grid_rows):
        """Round to the nearest cell; clamp rows, but only lightly clamp columns.

        Rows are clamped to [0, grid_rows) as before -- bounds are passed
        in rather than read from static config since both the fret count
        and the drawable area (fretboard + however many mode trays are
        stacked below it) are dynamic, so a fixed FRETBOARD_COLS/ROWS
        would either let pieces be dragged off the visible board or,
        worse, silently yank a piece sitting in a lower tray back up on
        release.

        Columns are handled differently: a tetra is allowed to overhang
        either edge of the board (representing a pattern that starts
        mid-shape, e.g. only the last two notes are reachable near the
        nut). The one hard rule is that at least one of its note cells
        must land on a real playable fret, where fret 0 (open string)
        counts as playable -- so the clamp only kicks in once the whole
        piece would otherwise drift entirely off one edge.
        """
        self.col = round(self.col)
        self.row = round(self.row)

        min_cell_col = min(c for c, _ in self.cells)
        max_cell_col = max(c for c, _ in self.cells)
        max_row_offset = max(r for _, r in self.cells)

        last_fret = grid_cols - 1  # grid_cols spans fret 0 (open) .. last_fret inclusive
        min_col = -max_cell_col  # piece's rightmost cell must reach fret 0 at worst
        max_col = last_fret - min_cell_col  # piece's leftmost cell must reach the last fret at worst
        max_row = grid_rows - (max_row_offset + 1)

        self.col = max(min_col, min(self.col, max_col))
        self.row = max(0, min(self.row, max_row))

    def draw(self, sketch, invalid=False, tonic_positions=None):
        x, y = self.get_pixel_origin()
        sketch.set_stroke("#202020")
        sketch.set_stroke_weight(2)

        sketch.set_fill(_with_alpha(_GAP_CELL_COLOR))
        for dc, dr in self.gap_cells:
            sketch.draw_rect(
                x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT
            )

        # The root/tonic cell (see MainCanvas._is_tonic) stays this piece's
        # own translucent color -- just a darker shade of it, plus a
        # heavier border -- rather than an opaque override. The fret's own
        # note-letter text (drawn underneath, before any piece) still shows
        # through a translucent fill exactly like it does on every other
        # occupied cell, so there's no need to redraw it here.
        for dc, dr in self.cells:
            col = round(self.col) + dc
            row = round(self.row) + dr
            is_tonic = not invalid and tonic_positions is not None and (col, row) in tonic_positions
            if invalid:
                fill = _INVALID_CELL_COLOR
            elif is_tonic:
                fill = _darken(self.color, _TONIC_DARKEN_FACTOR)
            else:
                fill = self.color
            sketch.set_fill(fill)
            sketch.set_stroke_weight(_TONIC_BORDER_WEIGHT if is_tonic else 2)
            sketch.draw_rect(
                x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT
            )
        sketch.set_stroke_weight(2)

        # Small always-on badge for any cell with an assigned finger letter,
        # so annotate mode isn't a write-only interaction -- see
        # MainCanvas._assign_finger_to_selection for how these get set. A
        # right triangle tucked into this cell's own bottom-right corner
        # (not a circle centered on that corner -- see _FINGER_BADGE_SIZE)
        # so it's visually unambiguous which cell it belongs to.
        for dc, dr in self.cells:
            finger = self.annotations.get(f"{dc},{dr}")
            if not finger:
                continue
            corner_x = x + (dc + 1) * FRET_WIDTH
            corner_y = y + (dr + 1) * FRET_HEIGHT
            sketch.push_style()
            sketch.clear_stroke()

            for size, fill in (
                (_FINGER_BADGE_SIZE + _FINGER_BADGE_OUTLINE_EXTRA, _FINGER_BADGE_OUTLINE_COLOR),
                (_FINGER_BADGE_SIZE, _FINGER_BADGE_COLOR),
            ):
                shape = sketch.start_shape(corner_x, corner_y)
                shape.add_line_to(corner_x - size, corner_y)
                shape.add_line_to(corner_x, corner_y - size)
                shape.close()
                sketch.set_fill(fill)
                sketch.draw_shape(shape)

            # Centroid of the triangle, nudged toward its interior rather
            # than sitting right on the (thin, apex) shared corner point.
            label_x = corner_x - _FINGER_BADGE_SIZE / 3
            label_y = corner_y - _FINGER_BADGE_SIZE / 3
            sketch.set_fill(_FINGER_BADGE_TEXT_COLOR)
            sketch.set_text_font("sans-serif", 11)
            sketch.set_text_align("center", "center")
            sketch.draw_text(label_x, label_y, str(finger))
            sketch.pop_style()

        # Small always-on marker for any played cell (see Piece.
        # is_played) -- a circle in this cell's own top-left corner, so
        # "this note is actually played" stays visible even for a cell
        # marked played with no fingering at all (an open string, or any
        # fretted note obvious enough not to bother annotating a finger
        # for -- see MainCanvas._toggle_played_at_point, right-click
        # while Annotate is on).
        for dc, dr in self.cells:
            if not self.is_played(dc, dr):
                continue
            corner_x = x + dc * FRET_WIDTH
            corner_y = y + dr * FRET_HEIGHT
            sketch.push_style()
            sketch.clear_stroke()
            sketch.set_fill(_FINGER_BADGE_OUTLINE_COLOR)
            sketch.draw_ellipse(
                corner_x,
                corner_y,
                _PLAYED_MARKER_RADIUS + _PLAYED_MARKER_OUTLINE_EXTRA,
                _PLAYED_MARKER_RADIUS + _PLAYED_MARKER_OUTLINE_EXTRA,
            )
            sketch.set_fill(_FINGER_BADGE_COLOR)
            sketch.draw_ellipse(corner_x, corner_y, _PLAYED_MARKER_RADIUS, _PLAYED_MARKER_RADIUS)
            sketch.pop_style()


# Fractions of FRET_WIDTH/FRET_HEIGHT used to position each technique's
# glyph relative to its endpoint cell centers -- tuned by eye against a
# screenshot (same "not pixel-exact, tuned to look right" precedent as the
# export ordinal-suffix nudge), not derived from anything exact.
_SLIDE_Y_OFFSET = 0.32
_ARC_HEIGHT_FRACTION = 0.34
_ARC_ROW_OFFSET = 0.12
_SIDE_MARK_X_OFFSET = 0.34
_ROLL_ZIGZAG_AMPLITUDE_FRACTION = 0.16
_ROLL_ZIGZAG_SEGMENTS = 4
_BARRE_STROKE_WEIGHT = 7
# Every glyph gets a white halo drawn first (same shape, wider stroke)
# before its real color on top -- without it, a black export glyph (or a
# live-board one sitting over a now-opaque-black tonic/root cell, see
# Piece.draw) can render fully invisible against a same-colored cell.
_CONNECTION_OUTLINE_COLOR = "#FFFFFF"
_CONNECTION_OUTLINE_EXTRA_WEIGHT = 4


def _draw_diagonal_hatch(sketch, x: float, y: float, w: float, h: float, spacing: float) -> None:
    """Diagonal stripes filling the box (x, y, w, h), for the accidental
    note badge (see EXPORT_ACCIDENTAL_STRIPE_COLOR) -- a black-and-white-
    safe way to mark a badge as visually distinct that still works once
    color drops out (print, photocopy, grayscale scan), unlike a fill
    color would.

    Each stripe is a line of constant `rel_x + rel_y` in the box's own
    local coordinates -- clipped to the box by construction (every
    endpoint computed already falls inside [0, w] x [0, h]), so this
    doesn't need a separate clip region the way a naive full-diagonal
    line would. Caller sets fill/stroke color and weight beforehand (see
    _export_png's badge-drawing pass) -- this only computes geometry.
    """
    c = 0.0
    while c <= w + h:
        y0 = max(0.0, c - w)
        y1 = min(h, c)
        if y0 < y1:
            sketch.draw_line(x + c - y0, y + y0, x + c - y1, y + y1)
        c += spacing


def draw_connection(sketch, technique: str, points: list[tuple[float, float]], color: str) -> None:
    """Draw one technique connection's glyph between/across `points`
    (already-resolved pixel centers of its endpoint cells) in `color`.

    Shared between the live board (MainCanvas._draw_connections, called
    once per frame) and PNG export (same call, different color/context) so
    a technique reads as the same shape in both places. Module-level and
    pixel-only (no Piece/MainCanvas access) specifically so both call
    sites can reuse it without either owning the other's coordinate
    system.
    """
    ordered = sorted(points)
    x1, y1 = ordered[0]
    x2, y2 = ordered[-1]

    sketch.push_style()
    sketch.clear_fill()

    def _stroked_line(x_a, y_a, x_b, y_b, weight):
        sketch.set_stroke(_CONNECTION_OUTLINE_COLOR)
        sketch.set_stroke_weight(weight + _CONNECTION_OUTLINE_EXTRA_WEIGHT)
        sketch.draw_line(x_a, y_a, x_b, y_b)
        sketch.set_stroke(color)
        sketch.set_stroke_weight(weight)
        sketch.draw_line(x_a, y_a, x_b, y_b)

    if technique == "slide":
        # A gentle diagonal directly above the row -- tab notation's "/",
        # not a flat line straight between the two note centers (which,
        # being same-row, would otherwise just be horizontal).
        offset = FRET_HEIGHT * _SLIDE_Y_OFFSET
        _stroked_line(x1, y1 - offset * 0.6, x2, y2 - offset, 3)
    elif technique in _CONNECTION_LABELS:  # hammer_on, pull_off
        # Shallow upward slur ("hump") over the row, via the top half of
        # an ellipse (draw_arc's default "radius" mode: x1,y1 = center,
        # x2,y2 = radius_x,radius_y; angle 0 = up, increasing clockwise --
        # -90..90 sweeps left -> top -> right, i.e. exactly the top half).
        mid_x = (x1 + x2) / 2
        row_y = min(y1, y2)
        radius_x = max(abs(x2 - x1) / 2, 1)
        radius_y = FRET_HEIGHT * _ARC_HEIGHT_FRACTION
        center_y = row_y - FRET_HEIGHT * _ARC_ROW_OFFSET
        sketch.set_stroke(_CONNECTION_OUTLINE_COLOR)
        sketch.set_stroke_weight(2 + _CONNECTION_OUTLINE_EXTRA_WEIGHT)
        sketch.draw_arc(mid_x, center_y, radius_x, radius_y, -90, 90)
        sketch.set_stroke(color)
        sketch.set_stroke_weight(2)
        sketch.draw_arc(mid_x, center_y, radius_x, radius_y, -90, 90)
        # Tiny label at the arc's apex -- real tab notation draws hammer-on
        # and pull-off as the same slur shape too; direction/label is what
        # actually disambiguates them, not curve shape. draw_text fills
        # then strokes (see the finger-badge note in Piece.draw), so
        # stroking it here in the halo color doubles as a readable text
        # outline rather than needing a separate pass.
        sketch.set_fill(color)
        sketch.set_stroke(_CONNECTION_OUTLINE_COLOR)
        sketch.set_stroke_weight(3)
        sketch.set_text_font("sans-serif", 11)
        sketch.set_text_align("center", "bottom")
        sketch.draw_text(mid_x, center_y - radius_y - 2, _CONNECTION_LABELS[technique])
    elif technique == "barre":
        # Thick vertical bar just left of the fret column, spanning every
        # involved string -- matches the reference image directly.
        bar_x = x1 - FRET_WIDTH * _SIDE_MARK_X_OFFSET
        _stroked_line(bar_x, y1, bar_x, y2, _BARRE_STROKE_WEIGHT)
    elif technique == "roll":
        # A small vertical zigzag/squiggle (closer to the reference's
        # hand-drawn scribble than a smooth loop, which at this size just
        # read as a plain circle), also left of the fret column, spanning
        # the endpoints' full row range.
        zig_x = x1 - FRET_WIDTH * _SIDE_MARK_X_OFFSET
        amplitude = FRET_WIDTH * _ROLL_ZIGZAG_AMPLITUDE_FRACTION
        top_y, bottom_y = min(y1, y2), max(y1, y2)
        if bottom_y - top_y < 1:
            half_span = FRET_HEIGHT * 0.4
            top_y, bottom_y = top_y - half_span, top_y + half_span
        prev_x, prev_y = zig_x, top_y
        for i in range(1, _ROLL_ZIGZAG_SEGMENTS + 1):
            step_y = top_y + (bottom_y - top_y) * i / _ROLL_ZIGZAG_SEGMENTS
            step_x = zig_x + (amplitude if i % 2 else -amplitude)
            _stroked_line(prev_x, prev_y, step_x, step_y, 2)
            prev_x, prev_y = step_x, step_y

    sketch.pop_style()


def piece_fits_scale(piece: "Piece", strings_by_row, grid_cols: int, scale_pitch_classes: set) -> bool:
    """Whether every note cell of `piece` (its actual notes, not the gray
    gap cells) is a member of `scale_pitch_classes`.

    This is the whole validator: every mode tray's tetrachord is, by
    construction, some mode's tetrachord lifted from the same parent
    Ionian scale (see config.get_scale_pitch_classes' docstring) -- so
    there's no need to derive a different scale per mode. A piece is
    "legal" if the pitch classes it actually lands on, wherever it's been
    dragged, all belong to the current key's one 7-note set.

    Cells that overhang off the board (no real fret/string there) are
    skipped rather than failing the check -- overhang is allowed by
    Piece.snap_to_grid already, and there's no note to validate there.

    piece.col/row are floats while the piece is actively being dragged
    (see MainCanvas._step) -- rounded to the nearest cell here so this
    can be called every frame, including on the piece currently under
    the mouse, without indexing `frets` with a float.
    """
    for dc, dr in piece.cells:
        col = round(piece.col) + dc
        row = round(piece.row) + dr
        string = strings_by_row.get(row)
        if string is None or col < 0 or col >= grid_cols:
            continue
        if pitch_class_semitone(string.frets[col].note) not in scale_pitch_classes:
            return False
    return True


def draw_scale_highlights(sketch, fretboard, scale_pitch_classes: set):
    """Mark every fret across the whole board whose note belongs to
    `scale_pitch_classes` -- the "generate the valid placements" half of
    the validator, drawn under the pieces so a dragged tetra still shows
    on top of it.
    """
    sketch.push_style()
    sketch.set_fill(_SCALE_HIGHLIGHT_COLOR)
    sketch.set_stroke(_SCALE_HIGHLIGHT_COLOR)
    for string in fretboard.strings:
        for fret in string.frets:
            if pitch_class_semitone(fret.note) in scale_pitch_classes:
                cx = fret.pixel_origin[0] + fret.pixel_width / 2
                cy = fret.pixel_origin[1] + fret.pixel_height / 2
                sketch.draw_ellipse(cx, cy, _SCALE_HIGHLIGHT_RADIUS, _SCALE_HIGHLIGHT_RADIUS)
    sketch.pop_style()


def build_pieces_for_mode(
    mode: "modes_module.Mode", tray: "TetraTray", string_interval: int
) -> list[Piece]:
    """Lay out one Piece per shape in `mode`, left to right inside `tray`.

    Pieces use the same (col, row) grid Fret cells live on (see
    Piece.get_pixel_origin), so tray_row is tray.y expressed in that same
    grid -- keeping this in the grid's units (not raw pixels) is what
    makes a snapped-and-dragged piece land exactly on a real fret cell.

    string_interval (semitones between adjacent strings in the active
    tuning) is what lets a shape's `jumps` resolve into concrete cells
    without modes.yaml knowing anything about the current tuning -- see
    modes.py's Shape.resolve_cells.
    """
    tray_row = (tray.y - FRETBOARD_BORDER_Y) / FRET_HEIGHT + 0.5
    color = _with_alpha(mode.color)

    pieces = []
    col = 1
    for shape in mode.shapes:
        cells = shape.resolve_cells(mode.intervals, string_interval)
        pieces.append(Piece(cells, color, col, tray_row, mode_name=mode.name, shape_name=shape.name))
        max_col_offset = max(c for c, _ in cells)
        col += max_col_offset + 2  # one empty column of gap between shapes
    return pieces


def _find_shape(mode: "modes_module.Mode", shape_name: str) -> "modes_module.Shape | None":
    """Look up one of `mode`'s shapes by name -- used to regenerate a
    board piece's cells from Load State's (mode_name, shape_name) pair."""
    for shape in mode.shapes:
        if shape.name == shape_name:
            return shape
    return None


_FRET_MARKER_RADIUS = 5
_FRET_MARKER_COLOR = "#EEEEEE"


def _is_double_marker_fret(fret_number):
    return fret_number % 12 == 0


def _is_single_marker_fret(fret_number):
    return fret_number % 12 in (3, 5, 7, 9)


def draw_fret_markers(sketch, fretboard, n_frets):
    """Draw standard inlay markers below the fretboard: a single dot on
    frets 3/5/7/9, a double dot on 12 -- repeating every octave for
    boards with more than 12 frets (15/17/19/21 single, 24 double, ...).
    """
    marker_y = fretboard.canvas_pos_y + fretboard.height + FRETBOARD_BORDER_Y / 2

    sketch.push_style()
    sketch.set_fill(_FRET_MARKER_COLOR)
    sketch.set_stroke(_FRET_MARKER_COLOR)
    for fret_number in range(1, n_frets + 1):
        cx = FRETBOARD_BORDER_X + fret_number * FRET_WIDTH + FRET_WIDTH / 2
        if _is_double_marker_fret(fret_number):
            sketch.draw_ellipse(cx - FRET_WIDTH / 4, marker_y, _FRET_MARKER_RADIUS, _FRET_MARKER_RADIUS)
            sketch.draw_ellipse(cx + FRET_WIDTH / 4, marker_y, _FRET_MARKER_RADIUS, _FRET_MARKER_RADIUS)
        elif _is_single_marker_fret(fret_number):
            sketch.draw_ellipse(cx, marker_y, _FRET_MARKER_RADIUS, _FRET_MARKER_RADIUS)
    sketch.pop_style()


class TetraTray:
    """One mode's draggable-piece tray: bounds, background, label, color."""

    def __init__(self, mode_name, color, x, y, width, height):
        self.mode_name = mode_name
        self.color = color
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def draw(self, sketch):
        sketch.set_fill("#EEEEEE")
        sketch.set_stroke(self.color)
        sketch.set_stroke_weight(2)
        sketch.draw_rect(self.x, self.y, self.width, self.height)

        # Scoped so the label's fill/font/align don't leak into whatever
        # draws next (see the same push_style/pop_style note in Fret.draw).
        sketch.push_style()
        sketch.set_fill(self.color)
        sketch.set_text_font("sans-serif", 16)
        sketch.set_text_align("left", "top")
        sketch.draw_text(self.x + 10, self.y + 8, self.mode_name)
        sketch.pop_style()


def _to_js_options(**kwargs):
    """Convert keyword args into a plain JS object, for the handful of
    browser APIs below that take an options object (showSaveFilePicker,
    showDirectoryPicker, FileSystemHandle.*Permission) -- pyodide doesn't
    auto-convert a Python dict into a JS object on its own.
    """
    return to_js(kwargs, dict_converter=js.Object.fromEntries)


def _await_request(request):
    """Wrap an IndexedDB request in an awaitable Promise.

    IndexedDB predates Promises entirely and is callback-only (an
    onsuccess/onerror pair fired on the request object), so this is the
    standard bridge needed to `await` it the same way every other
    browser API in this file is awaited.
    """

    def executor(resolve, reject):
        request.onsuccess = create_proxy(lambda event: resolve(request.result))
        request.onerror = create_proxy(lambda event: reject(request.error))

    return js.Promise.new(create_proxy(executor))


_EXPORT_FOLDER_DB_NAME = "tetraboard"
_EXPORT_FOLDER_DB_STORE = "handles"
_EXPORT_FOLDER_DB_KEY = "exportDirectory"


async def _open_export_folder_db():
    """The one IndexedDB database used to remember a chosen export
    folder's directory handle across page reloads (see MainCanvas.
    _choose_export_folder/_restore_export_folder). File System Access
    API handles are structured-cloneable, so IndexedDB is the standard
    way to persist one across sessions -- localStorage only holds
    strings, and a real filesystem path isn't something the browser
    ever exposes to script anyway (see _save_export_canvas).
    """
    request = js.window.indexedDB.open(_EXPORT_FOLDER_DB_NAME, 1)

    def upgrade(event):
        db = request.result
        if not db.objectStoreNames.contains(_EXPORT_FOLDER_DB_STORE):
            db.createObjectStore(_EXPORT_FOLDER_DB_STORE)

    request.onupgradeneeded = create_proxy(upgrade)
    return await _await_request(request)


async def _get_remembered_export_folder():
    db = await _open_export_folder_db()
    store = db.transaction(_EXPORT_FOLDER_DB_STORE, "readonly").objectStore(_EXPORT_FOLDER_DB_STORE)
    return await _await_request(store.get(_EXPORT_FOLDER_DB_KEY))


async def _remember_export_folder(handle) -> None:
    db = await _open_export_folder_db()
    store = db.transaction(_EXPORT_FOLDER_DB_STORE, "readwrite").objectStore(_EXPORT_FOLDER_DB_STORE)
    await _await_request(store.put(handle, _EXPORT_FOLDER_DB_KEY))


async def _blob_from_data_url(data_url: str):
    """A data: URL -> an awaitable Blob, via a same-document fetch --
    canvases have no direct synchronous Blob getter (toBlob is
    callback-based, not Promise-based), and this avoids hand-decoding
    the base64 payload.
    """
    response = await js.fetch(data_url)
    return await response.blob()


class MainCanvas:
    """Owns the Sketchingpy sketch, wires input, and drives the draw loop."""

    def __init__(self):
        self.sketch = sketchingpy.Sketch2D(TOTAL_WIDTH, TOTAL_HEIGHT)
        self.sketch.set_title("tetraboard")
        self.sketch.set_rect_mode("corner")
        self._fix_canvas_sharpness()
        # index.html's tabindex="0" on #sketch-canvas doesn't survive dev
        # hot-reload -- devreload.py's _fresh_canvas() swaps in a brand new
        # <canvas> with only `id` carried over, dropping every other
        # attribute (see its docstring). Setting it here instead means it's
        # always correct regardless of that swap, since main() re-runs
        # MainCanvas.__init__ on every reload too. Needed so the canvas can
        # receive keydown events at all -- see _on_press's focus() call.
        self.sketch.get_native().setAttribute("tabindex", "0")

        # All modes (not just the two currently visible trays) -- kept
        # around so Load State can regenerate a piece whose mode_name
        # isn't one of the two trays currently picked in the panel (e.g.
        # a saved board included a Phrygian piece, but Tray A/B are
        # currently Major/Minor).
        self.all_modes_by_name = {
            mode.name: mode for mode in modes_module.load_modes("modes.yaml")
        }

        self.board_pieces: list[Piece] = []
        self.drag_state = {"active": None}

        # Annotate-mode-only state -- see _handle_annotate_click/_on_key_press.
        # selected_cells: (piece, dc, dr) triples currently highlighted.
        # connections: technique markers (slide/hammer_on/pull_off/roll/
        # barre), each {"type": str, "endpoints": [(piece, dc, dr), ...]}.
        # tonic_overrides: absolute (col, row) -> explicit True/False,
        # overriding _is_tonic()'s key/mode-derived root detection for
        # that position.
        self.selected_cells: list[tuple[Piece, int, int]] = []
        self.connections: list[dict] = []
        self.tonic_overrides: dict[tuple[int, int], bool] = {}

        # Tracks whether Shift is currently held, so _on_key_press can
        # tell a genuine press (transition from up to down) apart from
        # the browser's own key-repeat while it stays held -- without
        # this, holding Shift for even a moment would toggle Annotate
        # back and forth repeatedly instead of once. Reset by
        # _on_key_release.
        self._shift_held = False

        # A remembered export folder (see _choose_export_folder) -- None
        # until either the user picks one this session or a previous
        # session's choice is restored from IndexedDB (see
        # _restore_export_folder, scheduled as a background task just
        # below since __init__ itself can't be async). _save_export_canvas
        # writes straight here with no dialog whenever this is set and
        # still has permission; falls back to the usual Save-As dialog
        # otherwise.
        self._export_directory_handle = None

        self._rebuild_from_controls()

        self.sketch.get_mouse().on_button_press(self._on_press)
        self.sketch.get_mouse().on_button_release(self._on_release)
        self.sketch.get_keyboard().on_key_press(self._on_key_press)
        self.sketch.get_keyboard().on_key_release(self._on_key_release)
        self.sketch.on_step(self._step)
        controls.on_visible_modes_change(self._rebuild_trays)
        controls.on_validator_change(self._on_validator_change)
        controls.on_tuning_change(self._on_tuning_change)
        controls.on_accidental_type_change(self._on_accidental_type_change)
        controls.on_clear_board(self._clear_board)
        controls.on_annotate_toggle(self._on_annotate_toggle)
        controls.on_export_png(self._export_png)
        controls.on_set_export_folder(self._choose_export_folder)
        controls.on_save_state(self._serialize_state)
        controls.on_load_state(self._load_state)
        asyncio.ensure_future(self._restore_export_folder())

    def _rebuild_from_controls(self):
        """(Re-)derive every piece of state that depends on the control
        panel's pickers -- fretboard, key/validator, trays -- from
        whatever those pickers currently read.

        Used both by __init__ (building for the first time) and by
        _load_state (after Load State has pushed restored values into
        the picker DOM elements, see controls.set_tuning() etc.) --
        keeping this as one method means a restored save can't drift
        from what a real page load would produce. Deliberately does not
        touch board_pieces -- that's a separate list Load State
        overwrites itself, and _clear_board()/stacking already rely on
        it never being reset by a rebuild.
        """
        self.n_frets = controls.get_fret_count()
        tuning = _resolve_tuning(controls.get_tuning())
        self.fretboard = (
            FretboardBuilder()
            .set_position(FRETBOARD_BORDER_X, FRETBOARD_BORDER_Y)
            .set_tuning(tuning)
            .set_n_frets(self.n_frets)
            .set_accidental_type(controls.get_accidental_type())
            .build()
        )
        # Assumes a uniform interval between every adjacent string pair
        # (true of every current tuning preset -- all perfect 4ths). A
        # non-uniform tuning (e.g. guitar's major 3rd between G and B)
        # would need this looked up per string pair instead of once.
        self.string_interval = semitone_distance(tuning.value[0], tuning.value[1])

        # Row -> OpenString lookup for the validator (piece_fits_scale) --
        # fretboard.strings is ordered low-to-high-note (tuning order), not
        # by drawn row, so this has to be keyed off each string's own
        # .index (0 = top/highest string, same convention Piece.row uses).
        self.strings_by_row = {string.index: string for string in self.fretboard.strings}

        self.key = controls.get_key()
        self.key_mode = controls.get_key_mode()
        self.validation_enabled = controls.is_validation_enabled()
        self.scale_pitch_classes = get_scale_pitch_classes(self.key, MODE_INTERVALS[self.key_mode])

        # Only show the two trays picked in the control panel (decluttering
        # the palette) -- anything already dragged onto the board stays
        # regardless of this filter, since board_pieces is a wholly
        # separate list from the tray templates built from self.modes.
        self.modes = _load_visible_modes()

        trays_top = FRETBOARD_BORDER_Y + self.fretboard.height + FRETBOARD_BORDER_Y
        self.tetra_trays = [
            TetraTray(
                mode.name,
                mode.color,
                0,
                trays_top + i * MODE_TRAY_HEIGHT,
                FRETBOARD_WIDTH,
                MODE_TRAY_HEIGHT,
            )
            for i, mode in enumerate(self.modes)
        ]

        # Tray pieces are fixed templates -- clicking one stamps a fresh
        # Piece.clone() onto the board rather than moving the template
        # itself, so a shape is never "used up" and can be stacked as many
        # times as you like (see _on_press). board_pieces holds every
        # clone that's actually been dropped onto the board.
        self.tray_pieces = [
            piece
            for mode, tray in zip(self.modes, self.tetra_trays)
            for piece in build_pieces_for_mode(mode, tray, self.string_interval)
        ]

        # A single always-available 1x1 "Accidental" piece, in its own tray
        # below the two mode trays -- unlike tray_pieces, not tied to
        # whichever two modes Tray A/B currently show (see Piece
        # .is_accidental), since an accidental is off-scale by definition
        # and isn't "in" any mode to begin with.
        accidental_tray_y = trays_top + len(self.modes) * MODE_TRAY_HEIGHT
        self.accidental_tray = TetraTray(
            "Accidental", _ACCIDENTAL_COLOR, 0, accidental_tray_y, FRETBOARD_WIDTH, MODE_TRAY_HEIGHT
        )
        accidental_row = (accidental_tray_y - FRETBOARD_BORDER_Y) / FRET_HEIGHT + 0.5
        self.accidental_piece = Piece(
            [(0, 0)], _with_alpha(_ACCIDENTAL_COLOR), 1, accidental_row, is_accidental=True
        )

        # +1: OpenString now builds fret_index 0 (open) through n_frets
        # inclusive -- see open_string.py's _build_frets/total_width.
        self.grid_cols = self.n_frets + 1
        bottom_tray = self.accidental_tray
        self.grid_rows = int((bottom_tray.y + bottom_tray.height - FRETBOARD_BORDER_Y) / FRET_HEIGHT)

    def _serialize_piece(self, piece: "Piece") -> dict:
        return {
            "mode_name": piece.mode_name,
            "shape_name": piece.shape_name,
            "is_accidental": piece.is_accidental,
            "col": piece.col,
            "row": piece.row,
            "annotations": piece.annotations,
            "name": piece.name,
            # Sorted for a stable/diffable save file -- a set has no
            # inherent order, and JSON has no set type anyway, so this is
            # a plain list either way (see Piece.played).
            "played": sorted(piece.played),
        }

    def _build_piece_from_state(self, entry: dict) -> "Piece | None":
        """The inverse of _serialize_piece -- regenerates a board Piece's
        cells from its (mode_name, shape_name) pair against the *current*
        string_interval, rather than trusting raw cells from the save
        file. This is what lets a save made under one tuning still
        resolve to correct frets if loaded after switching tunings.
        Silently drops any entry whose mode/shape no longer exists
        (e.g. modes.yaml changed since the file was saved) rather than
        failing the whole load.

        An accidental piece (see Piece.is_accidental) has no mode/shape to
        look up at all -- its single (0, 0) cell is fixed -- so it's
        handled separately, up front.
        """
        if entry.get("is_accidental"):
            return Piece(
                [(0, 0)],
                _with_alpha(_ACCIDENTAL_COLOR),
                entry.get("col", 0),
                entry.get("row", 0),
                annotations=entry.get("annotations", {}),
                name=entry.get("name"),
                is_accidental=True,
                played=entry.get("played", []),
            )

        mode = self.all_modes_by_name.get(entry.get("mode_name"))
        if mode is None:
            return None
        shape = _find_shape(mode, entry.get("shape_name", ""))
        if shape is None:
            return None
        cells = shape.resolve_cells(mode.intervals, self.string_interval)
        return Piece(
            cells,
            _with_alpha(mode.color),
            entry.get("col", 0),
            entry.get("row", 0),
            mode_name=mode.name,
            shape_name=shape.name,
            annotations=entry.get("annotations", {}),
            name=entry.get("name"),
            played=entry.get("played", []),
        )

    def _serialize_state(self) -> dict:
        """Registered as the Save State callback -- see controls.on_save_state.

        `version` is bumped whenever this shape changes incompatibly, so
        a future _load_state can tell an old save apart from a new one
        rather than guessing from which keys happen to be present. v2:
        `annotations` values became plain finger-letter strings (were
        `{"finger": ..., "text": ...}` dicts), and `connections`/
        `tonic_overrides` were added -- no migration from v1, per the user
        (an old save's annotations/connections just won't come back).

        `connections` endpoints reference pieces by their *index in
        board_pieces at save time* -- the only JSON-safe way to point at a
        specific placed piece without adding a persistent Piece.id.
        `tonic_overrides` needs no such mapping since its keys are already
        absolute board positions, not piece references.

        `controls.key_mode` and each piece's `is_accidental` are both
        purely additive fields on top of v2 (not a version bump) -- an old
        save without them just leaves the Key Mode picker at its default
        and treats every piece as a normal mode piece, same graceful-
        fallback pattern as fret_count/accidental_type.
        """
        piece_index = {piece: i for i, piece in enumerate(self.board_pieces)}
        return {
            "version": 2,
            "controls": {
                "tuning": controls.get_tuning(),
                "fret_count": self.n_frets,
                "accidental_type": controls.get_accidental_type().name,
                "visible_modes": controls.get_visible_modes(),
                "key": self.key,
                "key_mode": self.key_mode,
                "validation_enabled": self.validation_enabled,
            },
            "board_pieces": [self._serialize_piece(piece) for piece in self.board_pieces],
            "connections": [
                {
                    "type": connection["type"],
                    "endpoints": [
                        [piece_index[piece], dc, dr] for piece, dc, dr in connection["endpoints"]
                    ],
                }
                for connection in self.connections
            ],
            "tonic_overrides": [
                [col, row, is_tonic] for (col, row), is_tonic in self.tonic_overrides.items()
            ],
        }

    def _load_state(self, data: dict):
        """Registered as the Load State callback -- see controls.on_load_state.

        Pushes each restored value into its picker's DOM element first
        (so the panel actually reflects what got loaded, and so
        get_tuning()/get_key()/etc keep agreeing with what's on screen),
        then does one full _rebuild_from_controls() rather than relying
        on each picker's own live-update callback (on_visible_modes_change
        etc) to fire -- those are wired to real user `change` events,
        which controls.set_*() deliberately doesn't dispatch, so this
        would otherwise be a silent no-op.
        """
        control_settings = data.get("controls", {})

        tuning = control_settings.get("tuning")
        if tuning:
            controls.set_tuning(tuning)

        fret_count = control_settings.get("fret_count")
        if fret_count:
            controls.set_fret_count(fret_count)

        accidental_type = control_settings.get("accidental_type")
        if accidental_type:
            controls.set_accidental_type(accidental_type)

        visible_modes = control_settings.get("visible_modes")
        if visible_modes and len(visible_modes) == 2:
            controls.set_visible_modes(*visible_modes)

        key = control_settings.get("key")
        if key:
            controls.set_key(key)

        key_mode = control_settings.get("key_mode")
        if key_mode:
            controls.set_key_mode(key_mode)

        if "validation_enabled" in control_settings:
            controls.set_validation_enabled(control_settings["validation_enabled"])

        self._rebuild_from_controls()

        # Keep the raw-order (including Nones for dropped stale entries)
        # list around just long enough to resolve connections' saved
        # indices against it -- board_pieces itself is the None-filtered
        # version, and dropping a stale entry would otherwise shift every
        # index after it.
        raw_entries = data.get("board_pieces", [])
        built = [self._build_piece_from_state(entry) for entry in raw_entries]
        self.board_pieces = [piece for piece in built if piece is not None]

        self.connections = []
        for connection in data.get("connections", []):
            endpoints = []
            valid = True
            for endpoint in connection.get("endpoints", []):
                index, dc, dr = endpoint
                if index < 0 or index >= len(built) or built[index] is None:
                    valid = False
                    break
                endpoints.append((built[index], dc, dr))
            if valid and len(endpoints) >= 2:
                self.connections.append({"type": connection.get("type"), "endpoints": endpoints})

        self.tonic_overrides = {
            (col, row): is_tonic for col, row, is_tonic in data.get("tonic_overrides", [])
        }
        self.selected_cells = []

    def _clear_board(self):
        """Wipe every piece placed on the board, leaving the tray
        templates (and their infinite supply) untouched. Connections and
        tonic overrides are position/piece-anchored, so they're wiped
        alongside -- nothing survives pieces disappearing out from under
        them."""
        self.board_pieces = []
        self.connections = []
        self.tonic_overrides = {}
        self.selected_cells = []

    def _on_validator_change(self):
        """Live update when the Key picker, Key Mode picker, or Validate
        checkbox changes -- same reasoning as _rebuild_trays: a control
        that silently does nothing until the next reload would just look
        broken."""
        self.key = controls.get_key()
        self.key_mode = controls.get_key_mode()
        self.validation_enabled = controls.is_validation_enabled()
        self.scale_pitch_classes = get_scale_pitch_classes(self.key, MODE_INTERVALS[self.key_mode])

    def _on_tuning_change(self):
        """Live update when the Tuning picker changes.

        A new tuning can change the fretboard's string count, which
        would strand any board piece placed on a row that no longer
        exists -- rather than trying to salvage pieces that still fit,
        this clears the board outright before rebuilding. Tuning
        changes aren't expected to be a frequent, mid-arrangement
        action, so losing placed pieces here is an acceptable trade for
        not having to reason about partial survival.
        """
        self._clear_board()
        self._rebuild_from_controls()

    def _on_accidental_type_change(self):
        """Live update when the sharps/flats picker changes.

        Unlike _on_tuning_change, this doesn't touch string count or fret
        count, so board pieces stay exactly where they are -- only the
        fretboard's own displayed note names (Fret.note, rebuilt fresh
        inside _rebuild_from_controls) change.
        """
        self._rebuild_from_controls()

    def _rebuild_trays(self):
        """Re-populate the (fixed, always-2) tray slots when Tray A/B change.

        Fires live from controls.py's change listener rather than waiting
        for the next main.py hot-swap -- a filter control that silently
        does nothing until an unrelated save/reload would just look
        broken. Only replaces the tray templates -- board_pieces (already
        stamped out onto the board) are a separate list entirely, so a
        tray filter change never touches anything already placed.
        """
        self.modes = _load_visible_modes()

        for tray, mode in zip(self.tetra_trays, self.modes):
            tray.mode_name = mode.name
            tray.color = mode.color

        self.tray_pieces = [
            piece
            for mode, tray in zip(self.modes, self.tetra_trays)
            for piece in build_pieces_for_mode(mode, tray, self.string_interval)
        ]

    def _start_dragging(self, piece):
        # Connections and tonic overrides are anchored to wherever a piece
        # currently sits -- the moment it starts moving, both stop meaning
        # anything, so they're dropped right here rather than trying to
        # keep them correct across the drag (per the user's own call:
        # "if any of the pieces are moving... we will just clear them and
        # re-add them if needed").
        self.connections = [
            connection
            for connection in self.connections
            if not any(p is piece for p, dc, dr in connection["endpoints"])
        ]
        occupied = {(round(piece.col) + dc, round(piece.row) + dr) for dc, dr in piece.cells}
        self.tonic_overrides = {
            position: value
            for position, value in self.tonic_overrides.items()
            if position not in occupied
        }

        mouse = self.sketch.get_mouse()
        px = mouse.get_pointer_x()
        py = mouse.get_pointer_y()
        piece.dragging = True
        x, y = piece.get_pixel_origin()
        piece.drag_offset_x = px - x
        piece.drag_offset_y = py - y
        self.drag_state["active"] = piece

    def _try_rename_piece(self, px, py):
        """Right-click a board piece to rename it via a native prompt().

        Only while Annotate is off -- right-click means something else
        while it's on (see _toggle_played_at_point), the same way
        left-click already means something else there (see
        _handle_annotate_click vs. the plain drag-pickup below).

        Only board_pieces are renameable, not tray templates -- a tray
        shape's name ("Major straight") is already unique within its
        tray by construction; it's stacking the *same* shape onto the
        board more than once that produces indistinguishable copies,
        which is what this is for (see Piece.display_name). Prompt is
        pre-filled with the current display name so confirming with no
        changes is a no-op, and clearing the field reverts to the shape's
        traditional default name (e.g. "left", "zig") rather than storing
        "".
        """
        for piece in reversed(self.board_pieces):
            if piece.contains_point(px, py):
                new_name = js.window.prompt("Rename this shape:", piece.display_name)
                if new_name is not None:
                    piece.name = new_name.strip() or None
                return

    def _toggle_played_at_point(self, px, py):
        """Right-click a board piece's note cell while Annotate is on --
        toggles that cell's explicit "played" mark (see Piece.is_played),
        independent of any fingering.

        This is the only way to mark a note played with no fingering at
        all: per direct user feedback, plenty of notes don't need a
        fingering written down (an open string has no fretting finger to
        note in the first place; plenty of fretted notes are "obvious"
        enough not to bother) but should still be countable as played for
        the "Played only" export option -- previously "played" was
        entirely inferred from having a fingering, which left no way to
        mark either of those. Same topmost-hit-wins order as
        _handle_annotate_click/_try_rename_piece; a miss is a silent
        no-op, matching _try_rename_piece's own miss behavior.
        """
        for piece in reversed(self.board_pieces):
            cell = piece.cell_at_point(px, py)
            if cell is not None:
                key = f"{cell[0]},{cell[1]}"
                if key in piece.played:
                    piece.played.discard(key)
                else:
                    piece.played.add(key)
                return

    def _is_ctrl_held(self) -> bool:
        # Expected sketchingpy.const.KEYBOARD_CTRL_BUTTON ("ctrl") here, but
        # its own _map_key checks `target in KEY_MAP` without lowercasing
        # first, and the browser's real KeyboardEvent.key for this key is
        # "Control" (capital C) -- since KEY_MAP's keys are all lowercase,
        # that containment check always misses, so it falls through to
        # `target.lower()` and reports the raw name "control" instead.
        # Checking both covers it either way if that quirk ever gets fixed
        # upstream.
        pressed = {button.get_name() for button in self.sketch.get_keyboard().get_keys_pressed()}
        return "control" in pressed or sketchingpy.const.KEYBOARD_CTRL_BUTTON in pressed

    def _handle_annotate_click(self, px, py):
        """Left-click a board piece's note cell while Annotate is on --
        replaces the old per-cell prompt() with pure selection. Assigning a
        finger/technique/tonic happens afterward via _on_key_press.

        Plain click: selection becomes just the hit cell (or clears
        entirely on a miss). Ctrl+click: toggles the hit cell in/out of
        the current selection, leaving the rest alone; a ctrl+click miss is
        a no-op so it doesn't nuke an in-progress multi-select. Same
        topmost-hit-wins order as _try_rename_piece/_on_press's drag
        pickup.
        """
        ctrl_held = self._is_ctrl_held()

        hit = None
        for piece in reversed(self.board_pieces):
            cell = piece.cell_at_point(px, py)
            if cell is not None:
                hit = (piece, cell[0], cell[1])
                break

        if hit is None:
            if not ctrl_held:
                self.selected_cells = []
            return

        if ctrl_held:
            if hit in self.selected_cells:
                self.selected_cells.remove(hit)
            else:
                self.selected_cells.append(hit)
        else:
            self.selected_cells = [hit]

    def _assign_finger_to_selection(self, finger: str):
        for piece, dc, dr in self.selected_cells:
            piece.annotations[f"{dc},{dr}"] = finger

    def _clear_finger_from_selection(self):
        for piece, dc, dr in self.selected_cells:
            piece.annotations.pop(f"{dc},{dr}", None)

    def _toggle_connection(self, technique: str, cells: list[tuple["Piece", int, int]]):
        """Create, retype, or remove a connection spanning exactly `cells`.

        Matching is by endpoint *set* (order-independent -- which cell was
        clicked first doesn't matter). Pressing the same technique's hotkey
        again on an identical selection removes it (undo); pressing a
        different technique's hotkey retypes it in place. This is the only
        way to remove a connection -- no separate delete hotkey.
        """
        cell_set = set(cells)
        for connection in self.connections:
            if set(connection["endpoints"]) == cell_set:
                if connection["type"] == technique:
                    self.connections.remove(connection)
                else:
                    connection["type"] = technique
                return
        self.connections.append({"type": technique, "endpoints": list(cells)})

    def _apply_technique_to_selection(self, technique: str):
        """Validate the current selection's shape for `technique`, then
        toggle a connection across it -- see _toggle_connection. An
        invalid selection (wrong count/shape for this technique) is a
        silent no-op, not an alert -- keeps the hotkey flow fast.

        Absolute board position (round(piece.col)+dc, round(piece.row)+dr)
        is what "same string"/"same fret" actually means here, so this
        works identically whether the selected cells belong to one placed
        piece or two.
        """
        cells = self.selected_cells
        positions = [(round(piece.col) + dc, round(piece.row) + dr) for piece, dc, dr in cells]

        if technique in _SAME_STRING_TECHNIQUES:
            if len(cells) != 2:
                return
            (col1, row1), (col2, row2) = positions
            if row1 != row2 or col1 == col2:
                return
        elif technique in _SAME_FRET_TECHNIQUES:
            if len(cells) < 2:
                return
            cols = {col for col, row in positions}
            rows = {row for col, row in positions}
            if len(cols) != 1 or len(rows) < 2:
                return
        else:
            return

        self._toggle_connection(technique, cells)

    def _is_tonic(self, col: int, row: int) -> bool:
        """Whether (col, row) is the pattern's root/tonic.

        Deterministic from the selected Key + Mode: a cell is the root
        exactly when its actual note shares the key's pitch class,
        computed straight from MODE_INTERVALS -- no longer inferred from
        how two placed pieces happen to overlap (that heuristic assumed
        every pattern was built from two tetrachords meeting at their
        shared pivot note, which isn't true in general -- e.g. two Minor
        tetrachords sharing a root aren't that shape at all -- and it also
        couldn't say anything about a single placed piece). `t` can still
        override this per cell either way (see tonic_overrides above);
        nothing enforces the override is musically correct.
        """
        if (col, row) in self.tonic_overrides:
            return self.tonic_overrides[(col, row)]
        string = self.strings_by_row.get(row)
        if string is None or not (0 <= col < len(string.frets)):
            return False
        return pitch_class_semitone(string.frets[col].note) == pitch_class_semitone(self.key)

    def _toggle_tonic_for_selection(self):
        """`t` hotkey: flip each selected cell's tonic status independently
        (based on its own current resolved value, auto or override), into
        an explicit override -- nothing here enforces the result is
        musically correct."""
        for piece, dc, dr in self.selected_cells:
            col = round(piece.col) + dc
            row = round(piece.row) + dr
            self.tonic_overrides[(col, row)] = not self._is_tonic(col, row)

    def _on_key_press(self, button):
        name = button.get_name()

        # Works regardless of Annotate's current state -- flipping that
        # state is the whole point -- and ahead of the is_annotate_enabled
        # guard below, which only gates the annotate-mode-only hotkeys.
        # Guarded by _shift_held so the browser's own key-repeat while
        # Shift stays physically held doesn't toggle it back and forth.
        if name == sketchingpy.const.KEYBOARD_SHIFT_BUTTON:
            if not self._shift_held:
                self._shift_held = True
                controls.toggle_annotate()
            return

        if not controls.is_annotate_enabled():
            return
        if name in _FINGER_HOTKEYS:
            self._assign_finger_to_selection(_FINGER_HOTKEYS[name])
        elif name == _CLEAR_FINGER_KEY:
            self._clear_finger_from_selection()
        elif name in _TECHNIQUE_HOTKEYS:
            self._apply_technique_to_selection(_TECHNIQUE_HOTKEYS[name])
        elif name == _TONIC_HOTKEY:
            self._toggle_tonic_for_selection()

    def _on_key_release(self, button):
        if button.get_name() == sketchingpy.const.KEYBOARD_SHIFT_BUTTON:
            self._shift_held = False

    def _on_annotate_toggle(self):
        """Live update when the Annotate checkbox changes (either
        direction) -- see controls.on_annotate_toggle. A leftover
        selection would otherwise sit highlighted (or silently receive
        hotkeys) after the mode that gives it meaning has been switched
        off, or stay stale from before it was switched back on."""
        self.selected_cells = []

    def _on_press(self, button):
        # The keyboard listener only fires while the canvas element itself
        # has focus (see index.html's tabindex on #sketch-canvas -- a
        # canvas isn't natively focusable without one), so every click
        # re-focuses it, letting a hotkey work immediately after any
        # interaction with no separate "focus the board" step.
        self.sketch.get_native().focus()

        mouse = self.sketch.get_mouse()
        px = mouse.get_pointer_x()
        py = mouse.get_pointer_y()

        if button.get_name() == sketchingpy.const.MOUSE_RIGHT_BUTTON:
            if controls.is_annotate_enabled():
                self._toggle_played_at_point(px, py)
            else:
                self._try_rename_piece(px, py)
            return

        if controls.is_annotate_enabled():
            self._handle_annotate_click(px, py)
            return

        # Board pieces take priority (topmost/most-recently-placed first)
        # so an already-placed piece can be picked back up and moved.
        for piece in reversed(self.board_pieces):
            if piece.contains_point(px, py):
                self.board_pieces.remove(piece)
                self.board_pieces.append(piece)  # bring to front
                self._start_dragging(piece)
                return

        # Otherwise, clicking a tray template (including the single
        # always-available accidental_piece) stamps a brand new clone onto
        # the board and starts dragging *that* -- the template stays put,
        # so the same shape can be dragged out any number of times.
        for template in reversed([*self.tray_pieces, self.accidental_piece]):
            if template.contains_point(px, py):
                clone = template.clone()
                self.board_pieces.append(clone)
                self._start_dragging(clone)
                return

    def _on_release(self, button):
        piece = self.drag_state["active"]
        if piece is not None:
            piece.dragging = False
            piece.snap_to_grid(self.grid_cols, self.grid_rows)
            # Dropping a piece back into the tray area discards it --
            # there's no reason to keep a redundant copy sitting on top of
            # the template it was stamped from.
            if piece.row >= len(self.fretboard.strings) and piece in self.board_pieces:
                self.board_pieces.remove(piece)
            self.drag_state["active"] = None

    def _step(self, sketch_ref):
        # Nothing else paints the buffer margins around the board/trays
        # opaquely every frame, so without this a piece dragged through
        # that space leaves a trail of un-erased previous frames behind
        # it (only became visible once overhang past the board edges
        # became unlimited, rather than a single fixed buffer column).
        sketch_ref.clear("#202020")

        active = self.drag_state["active"]
        if active is not None:
            mouse = sketch_ref.get_mouse()
            px = mouse.get_pointer_x()
            py = mouse.get_pointer_y()
            active.col = (px - active.drag_offset_x - FRETBOARD_BORDER_X) / FRET_WIDTH
            active.row = (py - active.drag_offset_y - FRETBOARD_BORDER_Y) / FRET_HEIGHT

        for tray in self.tetra_trays:
            tray.draw(sketch_ref)
        self.accidental_tray.draw(sketch_ref)
        self.fretboard.draw(sketch_ref)
        draw_fret_markers(sketch_ref, self.fretboard, self.n_frets)
        if self.validation_enabled:
            draw_scale_highlights(sketch_ref, self.fretboard, self.scale_pitch_classes)

        for piece in self.tray_pieces:
            piece.draw(sketch_ref)
        self.accidental_piece.draw(sketch_ref)

        tonic_positions = self._tonic_positions_for_board()
        for piece in self.board_pieces:
            # An accidental note is off-scale by definition -- flagging it
            # invalid would defeat the point of having a dedicated way to
            # place one (see Piece.is_accidental).
            invalid = (
                self.validation_enabled
                and not piece.is_accidental
                and not piece_fits_scale(piece, self.strings_by_row, self.grid_cols, self.scale_pitch_classes)
            )
            piece.draw(sketch_ref, invalid=invalid, tonic_positions=tonic_positions)

        self._draw_connections(sketch_ref, _CONNECTION_COLOR)
        self._draw_selection(sketch_ref)

    def _draw_selection(self, sketch):
        if not self.selected_cells:
            return
        sketch.push_style()
        sketch.clear_fill()
        sketch.set_stroke(_SELECTION_OUTLINE_COLOR)
        sketch.set_stroke_weight(_SELECTION_OUTLINE_WEIGHT)
        for piece, dc, dr in self.selected_cells:
            x, y = piece.get_pixel_origin()
            sketch.draw_rect(x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT)
        sketch.pop_style()

    def _tonic_positions_for_board(self) -> set[tuple[int, int]]:
        """Absolute (col, row) positions, across every placed board piece,
        that currently resolve as tonic/root -- computed once per frame and
        handed to each Piece.draw call so the root renders as a darker
        shade with a heavier border (see Piece.draw) instead of the usual
        plain translucent color. Restricted to cells that actually belong
        to a placed piece since that's the only context _is_tonic is ever
        asked about."""
        return {
            (round(piece.col) + dc, round(piece.row) + dr)
            for piece in self.board_pieces
            for dc, dr in piece.cells
            if self._is_tonic(round(piece.col) + dc, round(piece.row) + dr)
        }

    def _draw_connections(self, sketch, color):
        for connection in self.connections:
            points = []
            for piece, dc, dr in connection["endpoints"]:
                x, y = piece.get_pixel_origin()
                points.append((x + (dc + 0.5) * FRET_WIDTH, y + (dr + 0.5) * FRET_HEIGHT))
            draw_connection(sketch, connection["type"], points, color)

    def _export_label(
        self, view: str, piece: "Piece", dc: int, dr: int, col: int, row: int
    ) -> tuple[str, str]:
        """The text to draw in one occupied export cell, per the selected
        view mode (see controls.get_export_view) -- wholesale replaces the
        note label, never combines more than one axis at once.

        Returns (main_text, suffix_text): suffix_text is non-empty for the
        interval view's ordinal suffix ("st"/"nd"/"rd"/"th", drawn smaller
        and raised next to the degree) and for the vanilla view's octave
        digit (drawn smaller, same baseline, next to the note letter) --
        see _export_png for how those two get told apart and drawn
        differently. Empty suffix for fingering, and for every view on a
        cell outside the real playable board (col < 0 or col >=
        self.grid_cols): a piece is allowed to overhang past the open
        string or the last fret (see Piece.snap_to_grid), but there's no
        real note there to label -- the footprint shading/badge still
        draws for those cells (see _export_png), just without text, so the
        shape reads as continuous without claiming a note exists where one
        doesn't.
        """
        if col < 0 or col >= self.grid_cols:
            return "", ""

        string = self.strings_by_row.get(row)
        if string is None:
            return "", ""

        if view == "interval":
            degree = get_scale_degree(self.key, _note_at_fret(string, col), MODE_INTERVALS[self.key_mode])
            return (str(degree), _ordinal_suffix(degree)) if degree is not None else ("", "")

        if view == "fingering":
            return piece.annotations.get(f"{dc},{dr}", ""), ""

        return _split_note_octave(_note_at_fret(string, col))  # vanilla (default)

    def _export_piece_footprints(self) -> list[set[tuple[int, int]]]:
        """One absolute-(col, row) footprint set per placed piece -- both
        its real note cells and its gray gap cells (see
        _compute_gap_cells), since a skipped-fret gap is still visually
        part of that piece's shape, not a break in it. Kept per-piece
        (rather than flattened into one combined set) so _export_png can
        tell whether two neighboring footprint cells belong to the *same*
        piece -- see EXPORT_FOOTPRINT_FILL_COLOR's comment for why that
        distinction now matters again.

        Column isn't bounds-checked against grid_cols -- Piece.snap_to_grid
        already allows a piece to overhang past the open string or the
        last fret on purpose (see its docstring), and export should still
        draw that overhanging part of the shape rather than silently
        cropping it, even though it's not actually reachable. Row still is
        checked, since there's no such thing as an out-of-range string.
        """
        footprints: list[set[tuple[int, int]]] = []
        for piece in self.board_pieces:
            footprint: set[tuple[int, int]] = set()
            for dc, dr in piece.cells + piece.gap_cells:
                col = round(piece.col) + dc
                row = round(piece.row) + dr
                if row not in self.strings_by_row:
                    continue
                footprint.add((col, row))
            footprints.append(footprint)
        return footprints

    @staticmethod
    def _export_flush(
        cell: tuple[int, int],
        neighbor: tuple[int, int],
        piece_footprints: list[set[tuple[int, int]]],
    ) -> bool:
        """True if some single piece's footprint contains both `cell` and
        `neighbor` -- i.e. the shading rects for those two cells should
        extend flush to their shared edge rather than each keeping its own
        inward buffer there. Two adjacent tetrachords that share a root
        note both contain that shared cell, so this naturally reads as one
        continuous shape across the pair -- no special-casing needed for
        that overlap case.
        """
        return any(cell in footprint and neighbor in footprint for footprint in piece_footprints)

    async def _export_png(self):
        """Registered as the Export PNG callback -- see controls.on_export_png.

        Redraws a clean, high-contrast diagram of just the placed pieces
        (bounding box of board_pieces' actual cells, transparent
        background, no trays/dark editing chrome) directly onto the main
        canvas, crops that down to just the drawn content into a small
        offscreen canvas (see _export_crop_canvas), and immediately
        redraws the normal interactive frame -- all synchronous, so the
        browser never gets a chance to paint the intermediate export
        frame (see PLAN.md for why this doesn't need a second canvas or
        resizing the live one). Only *after* the live view is back does
        this await actually saving the crop (see _save_export_canvas) --
        that step can involve a native "Save As" dialog staying open for
        as long as the user takes to respond, and the interactive frame
        needs to already be showing underneath it by then, not the export
        art frozen behind a dialog that has nothing to do with it.
        """
        # Column isn't bounds-checked -- see _export_piece_footprints'
        # docstring: a piece is allowed to overhang past the open string
        # or the last fret, and export still draws that part of the shape
        # rather than cropping it, even though it's not actually
        # reachable there.
        cell_map: dict[tuple[int, int], tuple[Piece, int, int]] = {}
        for piece in self.board_pieces:
            for dc, dr in piece.cells:
                col = round(piece.col) + dc
                row = round(piece.row) + dr
                if row not in self.strings_by_row:
                    continue
                cell_map[(col, row)] = (piece, dc, dr)

        if not cell_map:
            js.window.alert("Nothing to export -- place a shape on the board first.")
            return

        view = controls.get_export_view()
        played_only = controls.get_played_only()
        pattern_name = controls.get_pattern_name().strip() or _DEFAULT_PATTERN_NAME
        suffix = _EXPORT_VIEW_FILENAME_SUFFIXES[view]
        filename = f"{pattern_name}_{suffix}.png"

        piece_footprints = self._export_piece_footprints()
        footprint_cells: set[tuple[int, int]] = set().union(*piece_footprints) if piece_footprints else set()

        # The full footprint (every piece's real notes *and* gap cells),
        # not just cell_map's actual note positions -- a piece is free to
        # overhang past the open string (or the last fret), and this range
        # drives both the drawn area and where col_x below anchors column
        # 0 of it, so an overhanging piece no longer gets cropped off the
        # left edge of the export the way it would if this were still
        # keyed off cell_map's notes-only columns.
        cols = [c for c, _ in footprint_cells]
        rows = [r for _, r in footprint_cells]
        min_col, max_col = min(cols), max(cols)
        min_row, max_row = min(rows), max(rows)

        # Column positions are relative to min_col, not absolute -- so
        # however far left (or right) a piece overhangs, the export's own
        # leftmost drawn column always starts at the same fixed on-canvas
        # margin instead of at a fixed *board* position that can land
        # off-canvas (negative x) once min_col goes negative. Rows don't
        # need this: Piece.snap_to_grid already keeps every row on-board.
        def col_x(col: int) -> float:
            return FRETBOARD_BORDER_X + (col - min_col) * FRET_WIDTH

        def row_y(row: int) -> float:
            return FRETBOARD_BORDER_Y + row * FRET_HEIGHT

        # Transparent, not opaque white -- sketchingpy's own clear() always
        # paints a solid fillRect after clearing (see its source), so
        # getting a transparent background means reaching past it to the
        # canvas's own 2D context and clearing without that fill. This is
        # meant to be pasted directly over other documents (sheet music,
        # tab, slides) -- see the pattern's own grid cells just below,
        # which skip a fill for the same reason.
        self.sketch.get_native().getContext("2d").clearRect(0, 0, TOTAL_WIDTH, TOTAL_HEIGHT)

        # Pass 1: the plain grid -- every cell in range, occupied or not,
        # full size. Drawn first so the shading (pass 2) lands on top of
        # it. No fill (just the border) -- see the transparency comment
        # above.
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                self.sketch.set_stroke(EXPORT_CELL_BORDER_COLOR)
                self.sketch.set_stroke_weight(EXPORT_CELL_BORDER_WEIGHT)
                self.sketch.clear_fill()
                self.sketch.draw_rect(col_x(col), row_y(row), FRET_WIDTH, FRET_HEIGHT)

        # The nut: a solid bar standing in for the real physical boundary
        # of the fretboard -- drawn here, behind everything that follows
        # (shading, badges), so it reads as a structural landmark rather
        # than another piece of note content. Only relevant when the
        # export's own column range actually reaches column 0 (same
        # condition the open-string "O" marker below already uses) -- a
        # pattern fretted entirely higher up the neck has no open string
        # in frame to mark.
        #
        # Sits at column 0's *right* edge (the boundary with column 1),
        # not its left -- the nut is what you fret *against* starting at
        # fret 1, not something column 0 (the open, unfretted string) is
        # pressed up against. Placing it on column 0's left edge instead
        # (this pass's first cut) put a fret-like wire on the wrong side
        # of the open string and made it look frettable, which it isn't:
        # per direct user feedback, an open string is never pressed down
        # anywhere, let alone against a wire to its own left.
        if min_col <= 0 <= max_col:
            self.sketch.push_style()
            self.sketch.clear_stroke()
            self.sketch.set_fill(EXPORT_NUT_COLOR)
            nut_x = col_x(1)
            nut_y = row_y(min_row) - EXPORT_NUT_OVERHANG
            nut_height = (max_row - min_row + 1) * FRET_HEIGHT + 2 * EXPORT_NUT_OVERHANG
            self.sketch.draw_rect(nut_x, nut_y, EXPORT_NUT_WIDTH, nut_height)
            self.sketch.pop_style()

        # Pass 2: the shading (gray content, biased inward except on
        # edges shared with a same-piece neighbor -- see _export_flush)
        # plus each real note's badge and label. No separate backing/
        # outline layer underneath this -- see EXPORT_FOOTPRINT_FILL_COLOR's
        # comment for why that was tried and dropped; the flush-biased
        # shading below is the entire mechanism for showing connectivity.
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                x = col_x(col)
                y = row_y(row)
                entry = cell_map.get((col, row))

                if (col, row) in footprint_cells:
                    # This rect only ever insets left/right -- top/bottom
                    # always stay inset here, even when two rows are
                    # flush (a piece's own root lining up with a
                    # string-jumped note directly above/below it, see
                    # modes.yaml). That connection is real and does get
                    # drawn, just not via this rect: it sits *behind* the
                    # opaque note badge, which nearly fills the cell, so a
                    # flush top/bottom edge here only ever peeks out
                    # wherever this row's *unrelated* left/right insets
                    # happen to leave a gap -- a thin, oddly-placed sliver
                    # rather than a real connector. The actual bridge is
                    # drawn as its own small rect after every badge, right
                    # below this loop, sized to match the badge instead of
                    # the whole cell.
                    left = 0 if self._export_flush((col, row), (col - 1, row), piece_footprints) else EXPORT_FOOTPRINT_INSET
                    right = 0 if self._export_flush((col, row), (col + 1, row), piece_footprints) else EXPORT_FOOTPRINT_INSET
                    top = EXPORT_FOOTPRINT_INSET
                    bottom = EXPORT_FOOTPRINT_INSET
                    self.sketch.push_style()
                    self.sketch.clear_stroke()
                    self.sketch.set_fill(EXPORT_FOOTPRINT_FILL_COLOR)
                    self.sketch.draw_rect(
                        x + left,
                        y + top,
                        FRET_WIDTH - left - right,
                        FRET_HEIGHT - top - bottom,
                    )
                    self.sketch.pop_style()

                if entry is None:
                    continue
                piece, dc, dr = entry

                # The actual note: a smaller rect biased inward from the
                # cell's own edges (see EXPORT_NOTE_INSET) so it reads as
                # a distinct "badge" sitting on top of the footprint
                # shading, rather than just another edge-to-edge cell
                # indistinguishable from a gap -- bigger and more prominent
                # than that shading (EXPORT_NOTE_INSET < EXPORT_FOOTPRINT_
                # INSET, see export_style.py's docstring), with its own
                # outline so it stays visually distinct even where the two
                # colors are close in value. Solid/opaque, no mode colors
                # -- unlike the translucent piece.color used on the
                # interactive board, since this is its own from-scratch
                # print-oriented redraw, not a screenshot. An accidental
                # note (see Piece.is_accidental) gets its own color
                # regardless of root status -- being off-scale is the more
                # specific fact worth flagging here. Otherwise, the
                # root/tonic note (its pitch class matching the selected
                # Key, or an explicit override) stays solid black, every
                # other note goes gray.
                if piece.is_accidental:
                    note_fill = EXPORT_ACCIDENTAL_FILL_COLOR
                elif self._is_tonic(col, row):
                    note_fill = EXPORT_CELL_FILL_COLOR
                else:
                    note_fill = EXPORT_NON_ROOT_FILL_COLOR
                outline_color = EXPORT_NOTE_OUTLINE_COLOR
                stripe_color = EXPORT_ACCIDENTAL_STRIPE_COLOR
                label_color = EXPORT_LABEL_COLOR

                # "Played only" (see controls.get_played_only): a note
                # that isn't played (see Piece.is_played -- a fingering,
                # *or* an explicit right-click mark for notes that don't
                # need one, e.g. an open string) gets these flat colors
                # instead of drawn at full strength -- see
                # EXPORT_UNPLAYED_FILL_COLOR's comment for why solid
                # colors, not alpha transparency.
                if played_only and not piece.is_played(dc, dr):
                    note_fill = EXPORT_UNPLAYED_FILL_COLOR
                    outline_color = EXPORT_UNPLAYED_OUTLINE_COLOR
                    stripe_color = EXPORT_UNPLAYED_STRIPE_COLOR
                    label_color = EXPORT_UNPLAYED_LABEL_COLOR

                self.sketch.push_style()
                self.sketch.set_stroke(outline_color)
                self.sketch.set_stroke_weight(EXPORT_NOTE_OUTLINE_WEIGHT)
                self.sketch.set_fill(note_fill)
                badge_x = x + EXPORT_NOTE_INSET
                badge_y = y + EXPORT_NOTE_INSET
                badge_w = FRET_WIDTH - 2 * EXPORT_NOTE_INSET
                badge_h = FRET_HEIGHT - 2 * EXPORT_NOTE_INSET
                self.sketch.draw_rect(badge_x, badge_y, badge_w, badge_h)
                if piece.is_accidental:
                    self.sketch.set_stroke(stripe_color)
                    self.sketch.set_stroke_weight(EXPORT_ACCIDENTAL_STRIPE_WEIGHT)
                    _draw_diagonal_hatch(
                        self.sketch, badge_x, badge_y, badge_w, badge_h, EXPORT_ACCIDENTAL_STRIPE_SPACING
                    )
                self.sketch.pop_style()

                label, suffix = self._export_label(view, piece, dc, dr, col, row)
                if not label:
                    continue
                self.sketch.push_style()
                self.sketch.set_fill(label_color)
                # See the finger-badge note in Piece.draw -- draw_text
                # strokes as well as fills, and the cell border's black
                # stroke is still active here; without clearing it the
                # white label gets fully swallowed by a black outline.
                self.sketch.clear_stroke()
                if suffix and view == "interval":
                    # Ordinal suffix: draw the digit and its small raised
                    # suffix as two separate draw_text calls sharing one
                    # split point -- draw_text has no text-measurement API
                    # to size a single mixed-font string, so the split
                    # point is estimated from character count instead (see
                    # _estimate_text_width) and centered so the *combined*
                    # two-part label lands in the middle of the cell,
                    # rather than a fixed offset tuned only for a single
                    # digit (which let a wider main part, e.g. "F#" in the
                    # vanilla view below, push its suffix past the cell's
                    # edge).
                    suffix_font_size = EXPORT_ORDINAL_SUFFIX_FONT_SIZE
                    main_width = _estimate_text_width(label, EXPORT_LABEL_FONT_SIZE)
                    suffix_width = _estimate_text_width(suffix, suffix_font_size)
                    cx = x + FRET_WIDTH / 2 + (main_width - suffix_width) / 2
                    cy = y + FRET_HEIGHT / 2
                    self.sketch.set_text_font("sans-serif", EXPORT_LABEL_FONT_SIZE)
                    self.sketch.set_text_align("right", "center")
                    self.sketch.draw_text(cx, cy, label)
                    self.sketch.set_text_font("sans-serif", suffix_font_size)
                    self.sketch.set_text_align("left", "top")
                    self.sketch.draw_text(cx, cy - EXPORT_LABEL_FONT_SIZE * 0.28, suffix)
                elif suffix:
                    # Vanilla view's octave digit: same split-point
                    # technique as the ordinal suffix above, but same
                    # baseline as the letter (not raised) and smaller
                    # rather than merely small -- the octave number is
                    # secondary information, not a distinct unit like an
                    # ordinal suffix is.
                    suffix_font_size = EXPORT_NOTE_OCTAVE_FONT_SIZE
                    main_width = _estimate_text_width(label, EXPORT_LABEL_FONT_SIZE)
                    suffix_width = _estimate_text_width(suffix, suffix_font_size)
                    cx = x + FRET_WIDTH / 2 + (main_width - suffix_width) / 2
                    cy = y + FRET_HEIGHT / 2
                    self.sketch.set_text_font("sans-serif", EXPORT_LABEL_FONT_SIZE)
                    self.sketch.set_text_align("right", "center")
                    self.sketch.draw_text(cx, cy, label)
                    self.sketch.set_text_font("sans-serif", suffix_font_size)
                    self.sketch.set_text_align("left", "center")
                    self.sketch.draw_text(cx, cy, suffix)
                else:
                    self.sketch.set_text_font("sans-serif", EXPORT_LABEL_FONT_SIZE)
                    self.sketch.set_text_align("center", "center")
                    self.sketch.draw_text(x + FRET_WIDTH / 2, y + FRET_HEIGHT / 2, label)
                self.sketch.pop_style()

        # Cross-string "same fret" bridge: when a piece's own root and one
        # of its string-jumped notes land in the same column (see
        # modes.yaml -- Major/Minor/Phrygian's tetrachord spans exactly
        # one string's tuning interval, so the *last* note on the
        # jumped-to string always lines up with the root's own fret), draw
        # a small connector directly between their two badges. This can't
        # reuse the footprint shading rect above the way a same-row gap
        # connection does: that rect's flush edge sits *behind* the note
        # badge, and a badge is opaque and nearly cell-sized, so across
        # rows it swallows almost all of the connecting band, leaving only
        # a sliver peeking out wherever that row's own unrelated left/right
        # insets happen to leave a gap -- confirmed by exporting a "right"
        # shape and finding its root/last-note connector rendered as a
        # thin, oddly-clipped strip rather than a clean bridge. Drawn here,
        # after every badge in pass 2 above, so it sits on top instead of
        # underneath one.
        for row in range(min_row, max_row):
            for col in range(min_col, max_col + 1):
                if (col, row) not in cell_map or (col, row + 1) not in cell_map:
                    continue
                if not self._export_flush((col, row), (col, row + 1), piece_footprints):
                    continue
                # Stop short of each badge's own outline rather than
                # meeting it exactly -- draw_rect's stroke is centered on
                # the rect's mathematical edge, so it extends a half-
                # weight beyond that edge into whatever's drawn next; a
                # bridge reaching all the way to the edge painted over
                # (and visibly notched) the outer half of that border.
                border_margin = EXPORT_NOTE_OUTLINE_WEIGHT / 2
                self.sketch.push_style()
                self.sketch.clear_stroke()
                self.sketch.set_fill(EXPORT_FOOTPRINT_FILL_COLOR)
                self.sketch.draw_rect(
                    col_x(col) + EXPORT_NOTE_INSET,
                    row_y(row) + FRET_HEIGHT - EXPORT_NOTE_INSET + border_margin,
                    FRET_WIDTH - 2 * EXPORT_NOTE_INSET,
                    2 * EXPORT_NOTE_INSET - 2 * border_margin,
                )
                self.sketch.pop_style()

        # Technique connections (slide/hammer-on/pull-off/roll/barre) --
        # same glyphs as the live board (draw_connection), black instead
        # of the live board's accent color to match this export's B&W
        # palette. Drawn in every view (vanilla/interval/fingering) --
        # they're playing technique/structure, not note identity, same
        # reasoning as the string labels and fret markers below being
        # view-independent. A connection is skipped whole if any endpoint
        # falls outside this export's own bounding box -- no partial
        # glyphs half-drawn off the edge.
        for connection in self.connections:
            points = []
            in_bounds = True
            for piece, dc, dr in connection["endpoints"]:
                col = round(piece.col) + dc
                row = round(piece.row) + dr
                if (col, row) not in cell_map:
                    in_bounds = False
                    break
                points.append((col_x(col) + FRET_WIDTH / 2, row_y(row) + FRET_HEIGHT / 2))
            if in_bounds:
                draw_connection(self.sketch, connection["type"], points, EXPORT_CONNECTION_COLOR)

        # String names to the left, one per row -- orientation context so
        # a pattern that starts mid-neck (e.g. 7th fret of the A string)
        # can still be placed on the right string, even where it plays
        # that string open (col 0 looks identical to any other fretted
        # cell otherwise, with nothing marking which string it belongs to).
        #
        # Anchored at the true open-string column (col 0), not at the
        # render's own leftmost column -- a piece overhanging past the
        # open string (see Piece.snap_to_grid) pushes min_col left of 0,
        # and pinning the label to min_col would drag it away from the
        # real nut and out over cells that were never playable to begin
        # with (per direct user feedback: those cells "aren't even real",
        # see _export_label's col-range guard above). Clamping to
        # max(min_col, 0) instead means the label sits right at/over the
        # real start of the pattern in that case, and is unchanged from
        # today (label_col == min_col) whenever there's no left overhang.
        self.sketch.push_style()
        self.sketch.clear_stroke()
        # A stroke on draw_text doesn't draw a clean outline here -- it
        # swallows the fill entirely (same failure mode the finger-badge
        # comment in Piece.draw warns about with an *inherited* stroke;
        # this hits the same wall setting one on purpose). So the halo is
        # built the older, renderer-agnostic way instead: the label drawn
        # several times at small pixel offsets in the halo color first,
        # then once more dead center in the real color on top -- this
        # label can now land on top of a note badge or footprint shading
        # (see the anchoring comment above), not just blank canvas, and
        # its own gray would otherwise all but disappear against either.
        self.sketch.set_text_font("sans-serif", EXPORT_STRING_LABEL_FONT_SIZE)
        self.sketch.set_text_align("right", "center")
        label_x = col_x(max(min_col, 0)) - EXPORT_STRING_LABEL_MARGIN
        for row in range(min_row, max_row + 1):
            # Skip whenever this row's own open string is already showing
            # as a real note badge at column 0 -- that badge already spells
            # out this string's identity (e.g. "E1"), on top of the nut
            # right beside it marking where fretting starts, so a separate
            # faint label here would be pure redundancy. Still shown for
            # any row that doesn't include the open string, where it's the
            # only thing saying which string this is.
            if (0, row) in cell_map:
                continue
            string = self.strings_by_row[row]
            label_y = row_y(row) + FRET_HEIGHT / 2
            self.sketch.set_fill(EXPORT_STRING_LABEL_OUTLINE_COLOR)
            for ox, oy in EXPORT_STRING_LABEL_HALO_OFFSETS:
                self.sketch.draw_text(label_x + ox, label_y + oy, string.note_identity)
            self.sketch.set_fill(EXPORT_STRING_LABEL_COLOR)
            self.sketch.draw_text(label_x, label_y, string.note_identity)
        self.sketch.pop_style()

        # Fret-position dots below the grid, same convention as the
        # interactive board's draw_fret_markers (single dot on 3/5/7/9,
        # double on 12, repeating per octave) -- restricted to this
        # export's own column range, fret 0 (open) never gets one (it gets
        # its own "O" marker below instead).
        self.sketch.push_style()
        self.sketch.set_fill(EXPORT_FRET_MARKER_COLOR)
        self.sketch.set_stroke(EXPORT_FRET_MARKER_COLOR)
        marker_y = row_y(max_row + 1) + FRETBOARD_BORDER_Y / 2
        for col in range(max(min_col, 1), max_col + 1):
            cx = col_x(col) + FRET_WIDTH / 2
            if _is_double_marker_fret(col):
                self.sketch.draw_ellipse(
                    cx - FRET_WIDTH / 4, marker_y, EXPORT_FRET_MARKER_RADIUS, EXPORT_FRET_MARKER_RADIUS
                )
                self.sketch.draw_ellipse(
                    cx + FRET_WIDTH / 4, marker_y, EXPORT_FRET_MARKER_RADIUS, EXPORT_FRET_MARKER_RADIUS
                )
            elif _is_single_marker_fret(col):
                self.sketch.draw_ellipse(cx, marker_y, EXPORT_FRET_MARKER_RADIUS, EXPORT_FRET_MARKER_RADIUS)
        self.sketch.pop_style()

        # Open string marker: a plain "O" below fret 0, whenever this
        # export's column range actually reaches it (see
        # EXPORT_OPEN_STRING_MARKER_FONT_SIZE) -- a piece overhanging
        # left of the open string (see the cell_map/footprint comments
        # above) can still push min_col past 0, so this isn't simply
        # "always at the left edge."
        if min_col <= 0 <= max_col:
            self.sketch.push_style()
            self.sketch.set_fill(EXPORT_FRET_MARKER_COLOR)
            self.sketch.clear_stroke()
            self.sketch.set_text_font("sans-serif", EXPORT_OPEN_STRING_MARKER_FONT_SIZE)
            self.sketch.set_text_align("center", "center")
            self.sketch.draw_text(col_x(0) + FRET_WIDTH / 2, marker_y, "O")
            self.sketch.pop_style()

        # Crop down to just this content -- see EXPORT_CANVAS_PADDING's
        # comment for why the padding is generous rather than exact, and
        # _export_png's own docstring for why the interactive frame gets
        # restored (right below) before the actual save is awaited, not
        # after. Top also backs off by the nut's own overhang (only
        # relevant when the nut is actually drawn, but harmless padding
        # otherwise) so its rounded ends never land right on the crop
        # edge.
        crop_left = max(0.0, col_x(min_col) - EXPORT_CANVAS_PADDING)
        crop_top = max(0.0, row_y(min_row) - EXPORT_NUT_OVERHANG - EXPORT_CANVAS_PADDING)
        crop_right = min(TOTAL_WIDTH, col_x(max_col) + FRET_WIDTH + EXPORT_CANVAS_PADDING)
        crop_bottom = min(TOTAL_HEIGHT, row_y(max_row + 1) + FRETBOARD_BORDER_Y + EXPORT_CANVAS_PADDING)

        crop_canvas = self._export_crop_canvas(
            crop_left, crop_top, crop_right - crop_left, crop_bottom - crop_top
        )
        self._step(self.sketch)  # restore the normal interactive frame
        await self._save_export_canvas(crop_canvas, filename)

    def _export_crop_canvas(self, x: float, y: float, width: float, height: float):
        """A new offscreen canvas holding just (x, y, width, height) of the
        live canvas (in the same logical/CSS pixel space every other
        _export_png coordinate is already in) -- see _export_png's
        docstring for why the export needs cropping down from the full
        app canvas at all rather than saving it whole.

        Copied at the live canvas's own backing-store resolution (see
        _fix_canvas_sharpness) instead of a naive 1:1 logical-pixel copy,
        so a HiDPI export comes out just as sharp as the interactive
        board already is -- drawImage's source rectangle addresses actual
        bitmap pixels, not the logical ones the 2D context's own scale()
        transform maps drawing calls through.
        """
        dpr = js.window.devicePixelRatio or 1
        source = self.sketch.get_native()
        crop = js.document.createElement("canvas")
        crop.width = width * dpr
        crop.height = height * dpr
        context = crop.getContext("2d")
        context.drawImage(
            source,
            x * dpr,
            y * dpr,
            width * dpr,
            height * dpr,
            0,
            0,
            width * dpr,
            height * dpr,
        )
        return crop

    async def _save_export_canvas(self, canvas, filename: str) -> None:
        """Save an offscreen canvas (see _export_crop_canvas) as a PNG.

        Three ways to actually get the file out, tried in order:

        1. A remembered export folder (see _choose_export_folder) -- if
           one's set and still grants write permission, write straight
           into it under `filename`, no dialog at all. This is the path
           that makes batch-exporting many patterns painless: pick the
           folder once, then every export after that just lands there.
        2. The File System Access API's native "Save As" dialog
           (Chromium browsers) -- lets the file land wherever the user
           picks for *this* export, rather than always going to the
           browser's fixed Downloads folder the way a plain synthetic
           `<a download>` click always does.
        3. That exact synthetic-click mechanism -- the same one
           sketchingpy's own save_image uses internally (see
           TUTORIAL.md section 7) -- wherever neither of the above is
           available (Firefox/Safari as of this writing) or applicable.

        Does nothing at all (no download) if the user cancels a picker
        dialog along the way, same as Save State's cancelled filename
        prompt already does.
        """
        data_url = canvas.toDataURL("image/png")

        if self._export_directory_handle is not None:
            try:
                permission = await self._export_directory_handle.requestPermission(
                    _to_js_options(mode="readwrite")
                )
                if permission == "granted":
                    file_handle = await self._export_directory_handle.getFileHandle(
                        filename, _to_js_options(create=True)
                    )
                    writable = await file_handle.createWritable()
                    await writable.write(await _blob_from_data_url(data_url))
                    await writable.close()
                    return
            except JsException:
                pass  # permission lost / folder moved -- fall through below

        if hasattr(js.window, "showSaveFilePicker"):
            options = _to_js_options(
                suggestedName=filename,
                types=[{"description": "PNG image", "accept": {"image/png": [".png"]}}],
            )
            try:
                handle = await js.window.showSaveFilePicker(options)
            except JsException:
                return  # user cancelled the picker -- no download
            writable = await handle.createWritable()
            await writable.write(await _blob_from_data_url(data_url))
            await writable.close()
            return

        link = js.document.createElement("a")
        link.download = filename
        link.href = data_url
        link.click()

    async def _choose_export_folder(self) -> None:
        """Registered as the "Set export folder" callback -- see
        controls.on_set_export_folder.

        Lets the user pick a folder once via the File System Access
        API's native directory picker; every export after that (see
        _save_export_canvas) writes straight into it with no dialog,
        until this is called again to pick a different one. Persisted to
        IndexedDB (see _remember_export_folder) so the choice survives a
        page reload, not just this session.
        """
        try:
            handle = await js.window.showDirectoryPicker(_to_js_options(mode="readwrite"))
        except JsException:
            return  # user cancelled the picker
        self._export_directory_handle = handle
        controls.set_export_folder_label(handle.name)
        try:
            await _remember_export_folder(handle)
        except JsException:
            pass  # this session can still export straight to it either way

    async def _restore_export_folder(self) -> None:
        """Runs once at startup (see __init__, scheduled as a background
        task since __init__ itself can't be async) to reload whatever
        folder a previous session remembered via _choose_export_folder --
        without this, IndexedDB would be write-only and every fresh page
        load would silently fall back to the picker/download path no
        matter what was chosen before.

        Only silently re-checks permission (queryPermission, no user
        gesture needed) rather than re-requesting it (requestPermission,
        which does) -- there's no gesture available this early during
        startup, but one always is by the time an actual export happens
        (the button click itself), so _save_export_canvas re-requests it
        there instead if this leaves it not yet granted.
        """
        try:
            handle = await _get_remembered_export_folder()
        except JsException:
            return
        if handle is None:
            return
        try:
            await handle.queryPermission(_to_js_options(mode="readwrite"))
        except JsException:
            return
        self._export_directory_handle = handle
        controls.set_export_folder_label(handle.name)

    def _fix_canvas_sharpness(self):
        """Match the canvas's backing-store resolution to the display's
        actual pixel density.

        Sketch2DWeb sets canvas.width/height directly to the logical pixel
        size we pass it (see its __init__ in the sketchingpy source) with
        no devicePixelRatio awareness. On a HiDPI/Retina display that
        leaves the canvas with fewer physical pixels than the screen can
        show in that box, so the browser has to upscale it -- text is the
        most sensitive to this, which is why it reads as soft/pixelated
        and heavier than it should. Standard fix: make the backing store
        `dpr` times bigger than the CSS size, pin the CSS size back down
        explicitly so it still displays at the intended size, and scale
        the drawing context so sketchingpy's existing logical-pixel
        drawing calls still land in the right place.
        """
        dpr = js.window.devicePixelRatio or 1
        if dpr == 1:
            return

        canvas = self.sketch.get_native()
        canvas.style.width = f"{TOTAL_WIDTH}px"
        canvas.style.height = f"{TOTAL_HEIGHT}px"
        canvas.width = TOTAL_WIDTH * dpr
        canvas.height = TOTAL_HEIGHT * dpr
        canvas.getContext("2d").scale(dpr, dpr)

    def show(self):
        self.sketch.show()
        return self.sketch


def main():
    canvas = MainCanvas()
    return canvas.show()


if __name__ == "__main__":
    main()
