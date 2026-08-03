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

    def __init__(self, cells, color, col, row):
        self.cells = cells
        self.gap_cells = _compute_gap_cells(cells)
        self.color = color
        self.col = col  # can be fractional while being dragged
        self.row = row
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.in_tray = True  # False once dropped -- see MainCanvas._on_release

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

    def draw(self, sketch):
        x, y = self.get_pixel_origin()
        sketch.set_stroke("#202020")
        sketch.set_stroke_weight(2)

        sketch.set_fill(_with_alpha(_GAP_CELL_COLOR))
        for dc, dr in self.gap_cells:
            sketch.draw_rect(
                x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT
            )

        sketch.set_fill(self.color)
        for dc, dr in self.cells:
            sketch.draw_rect(
                x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT
            )


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
        pieces.append(Piece(cells, color, col, tray_row))
        max_col_offset = max(c for c, _ in cells)
        col += max_col_offset + 2  # one empty column of gap between shapes
    return pieces


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

        # Note: controls.get_string_count() isn't read here -- build()
        # derives string count from len(tuning) directly, so a string
        # count that doesn't match the selected tuning's preset has no
        # effect right now. Worth deciding how those two controls should
        # relate once you're back in fretboard.py.
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

        # Only show the two trays picked in the control panel (decluttering
        # the palette) -- anything already dragged onto the board stays
        # regardless of this filter, since self.pieces below is built from
        # this already-filtered self.modes.
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

        self.pieces = [
            piece
            for mode, tray in zip(self.modes, self.tetra_trays)
            for piece in build_pieces_for_mode(mode, tray, self.string_interval)
        ]
        self.drag_state = {"active": None}

        # +1: OpenString now builds fret_index 0 (open) through n_frets
        # inclusive -- see open_string.py's _build_frets/total_width.
        self.grid_cols = self.n_frets + 1
        bottom_tray = self.tetra_trays[-1]
        self.grid_rows = int((bottom_tray.y + bottom_tray.height - FRETBOARD_BORDER_Y) / FRET_HEIGHT)

        self.sketch.get_mouse().on_button_press(self._on_press)
        self.sketch.get_mouse().on_button_release(self._on_release)
        self.sketch.on_step(self._step)
        controls.on_visible_modes_change(self._rebuild_trays)

    def _rebuild_trays(self):
        """Re-populate the (fixed, always-2) tray slots when Tray A/B change.

        Fires live from controls.py's change listener rather than waiting
        for the next main.py hot-swap -- a filter control that silently
        does nothing until an unrelated save/reload would just look
        broken. Only replaces still-in-tray pieces; anything already
        dragged onto the board (piece.in_tray is False) is left alone.
        """
        self.modes = _load_visible_modes()

        for tray, mode in zip(self.tetra_trays, self.modes):
            tray.mode_name = mode.name
            tray.color = mode.color

        self.pieces = [piece for piece in self.pieces if not piece.in_tray]
        for mode, tray in zip(self.modes, self.tetra_trays):
            self.pieces.extend(build_pieces_for_mode(mode, tray, self.string_interval))

    def _on_press(self, button):
        mouse = self.sketch.get_mouse()
        px = mouse.get_pointer_x()
        py = mouse.get_pointer_y()

        for piece in reversed(self.pieces):
            if piece.contains_point(px, py):
                piece.dragging = True
                x, y = piece.get_pixel_origin()
                piece.drag_offset_x = px - x
                piece.drag_offset_y = py - y

                self.pieces.remove(piece)
                self.pieces.append(piece)  # bring to front

                self.drag_state["active"] = piece
                break

    def _on_release(self, button):
        piece = self.drag_state["active"]
        if piece is not None:
            piece.dragging = False
            piece.snap_to_grid(self.grid_cols, self.grid_rows)
            # "In the tray" is wherever it actually lands, not whether it
            # was touched -- a click or a drop-back-in-place shouldn't
            # count as "placed on the board" and get skipped by the next
            # tray rebuild.
            piece.in_tray = piece.row >= len(self.fretboard.strings)
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

        for piece in self.pieces:
            piece.draw(sketch_ref)

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
