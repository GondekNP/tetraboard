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

import controls
import js
import modes as modes_module
import sketchingpy
from config import (
    FRET_HEIGHT,
    FRET_WIDTH,
    FRETBOARD_BORDER_X,
    FRETBOARD_BORDER_Y,
    FRETBOARD_WIDTH,
    MODE_TRAY_HEIGHT,
    TOTAL_HEIGHT,
    TOTAL_WIDTH,
    get_scale_degree,
    get_scale_pitch_classes,
    pitch_class_semitone,
    semitone_distance,
)
from fretboard import TUNINGS, FretboardBuilder


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
_SELECTION_OUTLINE_COLOR = "#FBBF24"
_SELECTION_OUTLINE_WEIGHT = 3
_CONNECTION_COLOR = "#F472B6"
# The root/tonic note (see MainCanvas._is_tonic) renders as a solid opaque
# cell instead of the usual translucent piece color -- same treatment as
# export's black-root/gray-others split, so the root reads the same way in
# both places, and so two different-colored patterns meeting at a shared
# root don't fight over whose tint wins. The fret's own note-letter text
# would otherwise be fully hidden under that opaque fill, so it gets
# redrawn in white on top -- see Piece.draw.
_TONIC_CELL_FILL_COLOR = "#000000"
_TONIC_CELL_TEXT_COLOR = "#FFFFFF"

_DEFAULT_PATTERN_NAME = "tetraboard-export"
# Print-oriented: pure black/white throughout (no mode colors), heavier
# lines/text than the interactive board since these are meant to be printed
# small. Occupied cells are solid black with white text; the string-name
# labels and fret-position dots are deliberately faint/small (a light gray
# still prints fine in black & white) so they read as orientation context,
# not competing with the actual note content.
_EXPORT_CELL_BORDER_COLOR = "#000000"
_EXPORT_CELL_BORDER_WEIGHT = 2
_EXPORT_CELL_FILL_COLOR = "#000000"
# Non-root notes gray, root note stays solid black -- see
# MainCanvas._is_tonic/_auto_tonic_positions.
_EXPORT_NON_ROOT_FILL_COLOR = "#8A8A8A"
_EXPORT_CONNECTION_COLOR = "#000000"
_EXPORT_LABEL_COLOR = "#FFFFFF"
_EXPORT_LABEL_FONT_SIZE = 20
_EXPORT_STRING_LABEL_COLOR = "#888888"
_EXPORT_STRING_LABEL_FONT_SIZE = 12
_EXPORT_STRING_LABEL_MARGIN = 10
_EXPORT_FRET_MARKER_COLOR = "#888888"
_EXPORT_FRET_MARKER_RADIUS = 4
# Interval and fingering labels both draw from a small 1-4-ish vocabulary
# that's otherwise ambiguous with each other (a bare "2" could be a scale
# degree or a finger) -- interval gets a small ordinal suffix ("2nd"),
# fingering gets rendered as a letter instead of a digit at all, so the
# two views never look alike even at a glance.
_EXPORT_ORDINAL_SUFFIXES = {1: "st", 2: "nd", 3: "rd"}
_EXPORT_ORDINAL_SUFFIX_FONT_SIZE = 11
_EXPORT_ORDINAL_NUDGE = 5
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
        self, cells, color, col, row, mode_name=None, shape_name=None, annotations=None, name=None
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
        # None until the user right-clicks a board piece to rename it
        # (see MainCanvas._try_rename_piece) -- display_name falls back
        # to the shape's traditional name (e.g. "left", "zig") until
        # then. Stacking the same tray shape multiple times otherwise
        # gives every copy an identical, non-unique label, which is
        # exactly what renaming is for.
        self.name = name

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.shape_name:
            return self.shape_name
        return "piece"

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

    def draw(self, sketch, invalid=False, tonic_positions=None, strings_by_row=None):
        x, y = self.get_pixel_origin()
        sketch.set_stroke("#202020")
        sketch.set_stroke_weight(2)

        sketch.set_fill(_with_alpha(_GAP_CELL_COLOR))
        for dc, dr in self.gap_cells:
            sketch.draw_rect(
                x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT
            )

        # The root/tonic cell (see MainCanvas._is_tonic) draws opaque black
        # instead of this piece's usual translucent color -- deliberately
        # not just relying on two translucent pieces happening to stack
        # darker where they overlap (which is *always* where the root is,
        # by construction, but looked incidental and got weaker once a
        # finger badge or note letter needed to stay legible on top of it).
        # Redraw the fret's own note-name letter in white on top since the
        # opaque fill now fully covers Fret.draw's dark-on-light version of
        # that same text underneath.
        for dc, dr in self.cells:
            col = round(self.col) + dc
            row = round(self.row) + dr
            is_tonic = not invalid and tonic_positions is not None and (col, row) in tonic_positions
            sketch.set_fill(_INVALID_CELL_COLOR if invalid else (_TONIC_CELL_FILL_COLOR if is_tonic else self.color))
            sketch.draw_rect(
                x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT
            )
            if not is_tonic or strings_by_row is None:
                continue
            string = strings_by_row.get(row)
            if string is None or not (0 <= col < len(string.frets)):
                continue
            sketch.push_style()
            sketch.set_fill(_TONIC_CELL_TEXT_COLOR)
            sketch.clear_stroke()
            sketch.set_text_font("sans-serif", 14)
            sketch.set_text_align("center", "center")
            sketch.draw_text(
                x + dc * FRET_WIDTH + FRET_WIDTH / 2, y + dr * FRET_HEIGHT + FRET_HEIGHT / 2, string.frets[col].note
            )
            sketch.pop_style()

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
        # overriding _auto_tonic_positions()'s exactly-one-note-overlap
        # heuristic for that position.
        self.selected_cells: list[tuple[Piece, int, int]] = []
        self.connections: list[dict] = []
        self.tonic_overrides: dict[tuple[int, int], bool] = {}

        self._rebuild_from_controls()

        self.sketch.get_mouse().on_button_press(self._on_press)
        self.sketch.get_mouse().on_button_release(self._on_release)
        self.sketch.get_keyboard().on_key_press(self._on_key_press)
        self.sketch.on_step(self._step)
        controls.on_visible_modes_change(self._rebuild_trays)
        controls.on_validator_change(self._on_validator_change)
        controls.on_tuning_change(self._on_tuning_change)
        controls.on_accidental_type_change(self._on_accidental_type_change)
        controls.on_clear_board(self._clear_board)
        controls.on_annotate_toggle(self._on_annotate_toggle)
        controls.on_export_png(self._export_png)
        controls.on_save_state(self._serialize_state)
        controls.on_load_state(self._load_state)

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
        self.validation_enabled = controls.is_validation_enabled()
        self.scale_pitch_classes = get_scale_pitch_classes(self.key)

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

        # +1: OpenString now builds fret_index 0 (open) through n_frets
        # inclusive -- see open_string.py's _build_frets/total_width.
        self.grid_cols = self.n_frets + 1
        bottom_tray = self.tetra_trays[-1]
        self.grid_rows = int((bottom_tray.y + bottom_tray.height - FRETBOARD_BORDER_Y) / FRET_HEIGHT)

    def _serialize_piece(self, piece: "Piece") -> dict:
        return {
            "mode_name": piece.mode_name,
            "shape_name": piece.shape_name,
            "col": piece.col,
            "row": piece.row,
            "annotations": piece.annotations,
            "name": piece.name,
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
        """
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
        """Live update when the Key picker or Validate checkbox changes --
        same reasoning as _rebuild_trays: a control that silently does
        nothing until the next reload would just look broken."""
        self.key = controls.get_key()
        self.validation_enabled = controls.is_validation_enabled()
        self.scale_pitch_classes = get_scale_pitch_classes(self.key)

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

    def _auto_tonic_positions(self) -> set[tuple[int, int]]:
        """Absolute (col, row) positions where exactly two placed pieces'
        cell-sets intersect at exactly one cell -- two adjacent tetrachords
        of a 7-note scale always share exactly their pivot note, so an
        exactly-one-cell overlap is assumed to be that pattern's root.
        Recomputed on demand (not cached) -- trivial cost at this app's
        scale, same reasoning as piece_fits_scale being recomputed every
        frame per piece.
        """
        piece_cells = [
            {(round(piece.col) + dc, round(piece.row) + dr) for dc, dr in piece.cells}
            for piece in self.board_pieces
        ]
        positions: set[tuple[int, int]] = set()
        for i, cells_i in enumerate(piece_cells):
            for cells_j in piece_cells[i + 1 :]:
                overlap = cells_i & cells_j
                if len(overlap) == 1:
                    positions |= overlap
        return positions

    def _is_tonic(self, col: int, row: int) -> bool:
        if (col, row) in self.tonic_overrides:
            return self.tonic_overrides[(col, row)]
        return (col, row) in self._auto_tonic_positions()

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
        if not controls.is_annotate_enabled():
            return
        name = button.get_name()
        if name in _FINGER_HOTKEYS:
            self._assign_finger_to_selection(_FINGER_HOTKEYS[name])
        elif name == _CLEAR_FINGER_KEY:
            self._clear_finger_from_selection()
        elif name in _TECHNIQUE_HOTKEYS:
            self._apply_technique_to_selection(_TECHNIQUE_HOTKEYS[name])
        elif name == _TONIC_HOTKEY:
            self._toggle_tonic_for_selection()

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

        # Otherwise, clicking a tray template stamps a brand new clone
        # onto the board and starts dragging *that* -- the template stays
        # put, so the same shape can be dragged out any number of times.
        for template in reversed(self.tray_pieces):
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
        self.fretboard.draw(sketch_ref)
        draw_fret_markers(sketch_ref, self.fretboard, self.n_frets)
        if self.validation_enabled:
            draw_scale_highlights(sketch_ref, self.fretboard, self.scale_pitch_classes)

        for piece in self.tray_pieces:
            piece.draw(sketch_ref)

        tonic_positions = self._tonic_positions_for_board()
        for piece in self.board_pieces:
            invalid = self.validation_enabled and not piece_fits_scale(
                piece, self.strings_by_row, self.grid_cols, self.scale_pitch_classes
            )
            piece.draw(sketch_ref, invalid=invalid, tonic_positions=tonic_positions, strings_by_row=self.strings_by_row)

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
        handed to each Piece.draw call so the root renders as a solid
        opaque cell (see Piece.draw) instead of the usual translucent
        color. Restricted to cells that actually belong to a placed piece
        since that's the only context _is_tonic is ever asked about."""
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

        Returns (main_text, suffix_text): suffix_text is only non-empty for
        the interval view's ordinal suffix ("st"/"nd"/"rd"/"th", meant to
        be drawn smaller/raised next to the degree -- see _export_png),
        empty for every other view.
        """
        string = self.strings_by_row.get(row)
        if string is None:
            return "", ""

        if view == "interval":
            degree = get_scale_degree(self.key, string.frets[col].note)
            return (str(degree), _ordinal_suffix(degree)) if degree is not None else ("", "")

        if view == "fingering":
            return piece.annotations.get(f"{dc},{dr}", ""), ""

        return string.frets[col].note, ""  # vanilla (default)

    def _export_png(self):
        """Registered as the Export PNG callback -- see controls.on_export_png.

        Redraws a clean, high-contrast diagram of just the placed pieces
        (bounding box of board_pieces' actual cells, light background, no
        trays/dark editing chrome) directly onto the main canvas, saves it,
        then immediately redraws the normal interactive frame -- all inside
        this one synchronous call, so the browser never gets a chance to
        paint the intermediate export frame (see PLAN.md for why this
        doesn't need a second canvas or resizing the live one).
        """
        cell_map: dict[tuple[int, int], tuple[Piece, int, int]] = {}
        for piece in self.board_pieces:
            for dc, dr in piece.cells:
                col = round(piece.col) + dc
                row = round(piece.row) + dr
                if col < 0 or col >= self.grid_cols or row not in self.strings_by_row:
                    continue
                cell_map[(col, row)] = (piece, dc, dr)

        if not cell_map:
            js.window.alert("Nothing to export -- place a shape on the board first.")
            return

        view = controls.get_export_view()
        pattern_name = controls.get_pattern_name().strip() or _DEFAULT_PATTERN_NAME
        suffix = _EXPORT_VIEW_FILENAME_SUFFIXES[view]
        filename = f"{pattern_name}_{suffix}.png"
        cols = [c for c, _ in cell_map]
        rows = [r for _, r in cell_map]
        min_col, max_col = min(cols), max(cols)
        min_row, max_row = min(rows), max(rows)

        self.sketch.clear("#FFFFFF")
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                x = FRETBOARD_BORDER_X + col * FRET_WIDTH
                y = FRETBOARD_BORDER_Y + row * FRET_HEIGHT
                entry = cell_map.get((col, row))

                self.sketch.set_stroke(_EXPORT_CELL_BORDER_COLOR)
                self.sketch.set_stroke_weight(_EXPORT_CELL_BORDER_WEIGHT)
                # Solid black/white -- no mode colors -- and opaque (unlike
                # the translucent piece.color used on the interactive
                # board), since this is its own from-scratch print-oriented
                # redraw, not a screenshot. Occupied cells split further:
                # the root/tonic note (auto-detected from a two-piece
                # one-cell overlap, or an explicit override) stays solid
                # black, every other occupied cell goes gray.
                if entry is None:
                    fill = "#FFFFFF"
                elif self._is_tonic(col, row):
                    fill = _EXPORT_CELL_FILL_COLOR
                else:
                    fill = _EXPORT_NON_ROOT_FILL_COLOR
                self.sketch.set_fill(fill)
                self.sketch.draw_rect(x, y, FRET_WIDTH, FRET_HEIGHT)

                if entry is None:
                    continue
                piece, dc, dr = entry
                label, suffix = self._export_label(view, piece, dc, dr, col, row)
                if not label:
                    continue
                self.sketch.push_style()
                self.sketch.set_fill(_EXPORT_LABEL_COLOR)
                # See the finger-badge note in Piece.draw -- draw_text
                # strokes as well as fills, and the cell border's black
                # stroke is still active here; without clearing it the
                # white label gets fully swallowed by a black outline.
                self.sketch.clear_stroke()
                if suffix:
                    # Ordinal suffix (interval view): draw the digit and
                    # its small raised suffix as two separate draw_text
                    # calls sharing one split point -- draw_text has no
                    # text-measurement API to size a single mixed-font
                    # string, so the digit is right-aligned and the suffix
                    # left-aligned against the same x, with a small fixed
                    # nudge left of true center to roughly balance the
                    # suffix's extra width (good enough for 1-2 char
                    # suffixes at this cell size, not pixel-exact).
                    cx = x + FRET_WIDTH / 2 - _EXPORT_ORDINAL_NUDGE
                    cy = y + FRET_HEIGHT / 2
                    self.sketch.set_text_font("sans-serif", _EXPORT_LABEL_FONT_SIZE)
                    self.sketch.set_text_align("right", "center")
                    self.sketch.draw_text(cx, cy, label)
                    self.sketch.set_text_font("sans-serif", _EXPORT_ORDINAL_SUFFIX_FONT_SIZE)
                    self.sketch.set_text_align("left", "top")
                    self.sketch.draw_text(cx, cy - _EXPORT_LABEL_FONT_SIZE * 0.28, suffix)
                else:
                    self.sketch.set_text_font("sans-serif", _EXPORT_LABEL_FONT_SIZE)
                    self.sketch.set_text_align("center", "center")
                    self.sketch.draw_text(x + FRET_WIDTH / 2, y + FRET_HEIGHT / 2, label)
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
                points.append(
                    (FRETBOARD_BORDER_X + (col + 0.5) * FRET_WIDTH, FRETBOARD_BORDER_Y + (row + 0.5) * FRET_HEIGHT)
                )
            if in_bounds:
                draw_connection(self.sketch, connection["type"], points, _EXPORT_CONNECTION_COLOR)

        # String names to the left, one per row -- orientation context so
        # a pattern that starts mid-neck (e.g. 7th fret of the A string)
        # can still be placed on the right string, even where it plays
        # that string open (col 0 looks identical to any other fretted
        # cell otherwise, with nothing marking which string it belongs to).
        self.sketch.push_style()
        self.sketch.set_fill(_EXPORT_STRING_LABEL_COLOR)
        self.sketch.clear_stroke()
        self.sketch.set_text_font("sans-serif", _EXPORT_STRING_LABEL_FONT_SIZE)
        self.sketch.set_text_align("right", "center")
        label_x = FRETBOARD_BORDER_X + min_col * FRET_WIDTH - _EXPORT_STRING_LABEL_MARGIN
        for row in range(min_row, max_row + 1):
            string = self.strings_by_row[row]
            label_y = FRETBOARD_BORDER_Y + (row + 0.5) * FRET_HEIGHT
            self.sketch.draw_text(label_x, label_y, string.note_identity)
        self.sketch.pop_style()

        # Fret-position dots below the grid, same convention as the
        # interactive board's draw_fret_markers (single dot on 3/5/7/9,
        # double on 12, repeating per octave) -- restricted to this
        # export's own column range, fret 0 (open) never gets one.
        self.sketch.push_style()
        self.sketch.set_fill(_EXPORT_FRET_MARKER_COLOR)
        self.sketch.set_stroke(_EXPORT_FRET_MARKER_COLOR)
        marker_y = FRETBOARD_BORDER_Y + (max_row + 1) * FRET_HEIGHT + FRETBOARD_BORDER_Y / 2
        for col in range(max(min_col, 1), max_col + 1):
            cx = FRETBOARD_BORDER_X + col * FRET_WIDTH + FRET_WIDTH / 2
            if _is_double_marker_fret(col):
                self.sketch.draw_ellipse(
                    cx - FRET_WIDTH / 4, marker_y, _EXPORT_FRET_MARKER_RADIUS, _EXPORT_FRET_MARKER_RADIUS
                )
                self.sketch.draw_ellipse(
                    cx + FRET_WIDTH / 4, marker_y, _EXPORT_FRET_MARKER_RADIUS, _EXPORT_FRET_MARKER_RADIUS
                )
            elif _is_single_marker_fret(col):
                self.sketch.draw_ellipse(cx, marker_y, _EXPORT_FRET_MARKER_RADIUS, _EXPORT_FRET_MARKER_RADIUS)
        self.sketch.pop_style()

        self.sketch.save_image(filename)
        self._step(self.sketch)  # restore the normal interactive frame

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
