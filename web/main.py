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

import random
import sketchingpy
from dataclasses import dataclass

from config import (
    FRETBOARD_BORDER_X,
    FRETBOARD_BORDER_Y,
    FRETBOARD_COLS,
    FRETBOARD_ROWS,
    FRET_WIDTH,
    FRET_HEIGHT,
    FRETBOARD_WIDTH,
    TOTAL_WIDTH,
    TOTAL_HEIGHT,
    TETRA_TRAY_HEIGHT,
    get_chromatic_scale,
)


# --------------------------------------------------------------------------
# Placeholder draggable pieces: cell offsets (col, row) from the piece's
# origin. Swap these for real diagram components (finger dots, barres,
# fret/string labels, whatever a fretboard diagram needs) whenever you're
# ready -- the drag/snap plumbing below doesn't care what a "piece" means.
# --------------------------------------------------------------------------
SHAPES = {
    "I": {"cells": [(0, 0), (1, 0), (2, 0), (3, 0)], "color": "#31C7EF"},
    "O": {"cells": [(0, 0), (1, 0), (0, 1), (1, 1)], "color": "#F7D308"},
    "T": {"cells": [(0, 0), (1, 0), (2, 0), (1, 1)], "color": "#FF14F3"},
    "S": {"cells": [(1, 0), (2, 0), (0, 1), (1, 1)], "color": "#00FF00"},
    "Z": {"cells": [(0, 0), (1, 0), (1, 1), (2, 1)], "color": "#EF2029"},
    "J": {"cells": [(0, 0), (0, 1), (1, 1), (2, 1)], "color": "#5A65AD"},
    "L": {"cells": [(2, 0), (0, 1), (1, 1), (2, 1)], "color": "#EF7921"},
}


class Piece:
    """A draggable item living on a grid coordinate system."""

    def __init__(self, shape_key, col, row):
        shape = SHAPES[shape_key]
        self.shape_key = shape_key
        self.cells = shape["cells"]
        self.color = shape["color"]
        self.col = col  # can be fractional while being dragged
        self.row = row
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

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
        for dc, dr in self.cells:
            cx = x + dc * FRET_WIDTH
            cy = y + dr * FRET_HEIGHT
            if cx <= px <= cx + FRET_WIDTH and cy <= py <= cy + FRET_HEIGHT:
                return True
        return False

    def snap_to_grid(self):
        self.col = round(self.col)
        self.row = round(self.row)

        max_col_offset = max(c for c, _ in self.cells)
        max_row_offset = max(r for _, r in self.cells)
        max_col = FRETBOARD_COLS - (max_col_offset + 1)
        max_row = FRETBOARD_ROWS - (max_row_offset + 1)

        self.col = max(0, min(self.col, max_col))
        self.row = max(0, min(self.row, max_row))

    def draw(self, sketch):
        x, y = self.get_pixel_origin()
        sketch.set_stroke("#202020")
        sketch.set_stroke_weight(2)
        sketch.set_fill(self.color)
        for dc, dr in self.cells:
            sketch.draw_rect(
                x + dc * FRET_WIDTH, y + dr * FRET_HEIGHT, FRET_WIDTH, FRET_HEIGHT
            )


def build_pieces():
    keys = list(SHAPES.keys())
    random.shuffle(keys)
    spawn_positions = [(0, 0), (4, 0), (8, 0), (0, 5), (4, 5), (8, 5), (2, 10)]
    return [Piece(key, col, row) for key, (col, row) in zip(keys, spawn_positions)]


@dataclass
class Fretboard:
    """The fret grid: its own bounds, background, and grid lines."""

    x: int
    y: int
    cols: int
    rows: int
    fret_width: int
    fret_height: int
    open_strings: list[str]
    n_frets: int

    def __postinit__(self, open_strings=None):
        self.strings = [String(open_string, n_frets) for open_string in open_strings]

    @property
    def width(self):
        return self.cols * self.fret_width

    @property
    def height(self):
        return self.rows * self.fret_height

    def draw(self, sketch):
        sketch.set_fill("#EEEEEE")
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(1)

        sketch.draw_rect(self.x, self.y, self.width, self.height)

        # for c in range(self.cols + 1):
        #     x = self.x + c * self.fret_size
        #     sketch.draw_line(x, self.y, x, self.y + self.height)
        # for r in range(self.rows + 1):
        #     y = self.y + r * self.fret_size
        #     sketch.draw_line(self.x, y, self.x + self.width, y)


@dataclass
class String:
    """A single string on the fretboard."""

    note_identity: str
    n_frets: int
    fret_height: int = FRET_HEIGHT
    fret_width: int = FRET_WIDTH

    @property
    def y(self):
        return FRETBOARD_BORDER_Y + self.index * self.fret_height + self.fret_width / 2

    def draw(self, sketch):
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(2)

        for fret in self.n_frets:
            sketch.draw_rect(
                FRETBOARD_BORDER_X + fret * FRET_WIDTH,
                self.y - (self.fret_height / 2),
                FRET_WIDTH,
                FRET_HEIGHT,
            )


class TetraTray:
    """The draggable-piece tray below the fretboard: bounds + background."""

    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def draw(self, sketch):
        sketch.set_fill("#EEEEEE")
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(1)
        sketch.draw_rect(self.x, self.y, self.width, self.height)


class MainCanvas:
    """Owns the Sketchingpy sketch, wires input, and drives the draw loop."""

    def __init__(self):
        self.sketch = sketchingpy.Sketch2D(TOTAL_WIDTH, TOTAL_HEIGHT)
        self.sketch.set_title("tetraboard")
        self.sketch.set_rect_mode("corner")

        self.fretboard = Fretboard(
            FRETBOARD_BORDER_X,
            FRETBOARD_BORDER_Y,
            FRETBOARD_COLS,
            FRETBOARD_ROWS,
            FRET_SIZE,
        )
        self.tetra_tray = TetraTray(
            0,
            FRETBOARD_BORDER_Y + self.fretboard.height + FRETBOARD_BORDER_Y,
            FRETBOARD_WIDTH,
            TETRA_TRAY_HEIGHT,
        )

        self.pieces = build_pieces()
        self.drag_state = {"active": None}

        self.sketch.get_mouse().on_button_press(self._on_press)
        self.sketch.get_mouse().on_button_release(self._on_release)
        self.sketch.on_step(self._step)

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
            piece.snap_to_grid()
            self.drag_state["active"] = None

    def _step(self, sketch_ref):
        active = self.drag_state["active"]
        if active is not None:
            mouse = sketch_ref.get_mouse()
            px = mouse.get_pointer_x()
            py = mouse.get_pointer_y()
            active.col = (px - active.drag_offset_x - FRETBOARD_BORDER_X) / FRET_SIZE
            active.row = (py - active.drag_offset_y - FRETBOARD_BORDER_Y) / FRET_SIZE

        self.tetra_tray.draw(sketch_ref)
        self.fretboard.draw(sketch_ref)

        for piece in self.pieces:
            piece.draw(sketch_ref)

    def show(self):
        self.sketch.show()
        return self.sketch


def main():
    canvas = MainCanvas()
    return canvas.show()


if __name__ == "__main__":
    main()
