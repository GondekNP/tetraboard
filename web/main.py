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
PyScript/Pyodide in the browser. Edit, save, refresh the browser tab.
"""

import random
import sketchingpy

# Flip this on if drag hit-testing ever feels misaligned again (it should
# NOT be needed here since we're serving a plain, unscaled canvas locally,
# unlike the squeezed embed in the online editor where we first saw it).
DEBUG_POINTER = False

# --------------------------------------------------------------------------
# Board / grid configuration
# --------------------------------------------------------------------------
CELL_SIZE = 40
BOARD_COLS = 12
BOARD_ROWS = 14
BOARD_X = 40
BOARD_Y = 40

WIDTH = BOARD_X * 2 + BOARD_COLS * CELL_SIZE
HEIGHT = BOARD_Y * 2 + BOARD_ROWS * CELL_SIZE

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
        x = BOARD_X + self.col * CELL_SIZE
        y = BOARD_Y + self.row * CELL_SIZE
        return x, y

    def contains_point(self, px, py):
        x, y = self.get_pixel_origin()
        for dc, dr in self.cells:
            cx = x + dc * CELL_SIZE
            cy = y + dr * CELL_SIZE
            if cx <= px <= cx + CELL_SIZE and cy <= py <= cy + CELL_SIZE:
                return True
        return False

    def snap_to_grid(self):
        self.col = round(self.col)
        self.row = round(self.row)

        max_col_offset = max(c for c, _ in self.cells)
        max_row_offset = max(r for _, r in self.cells)
        max_col = BOARD_COLS - (max_col_offset + 1)
        max_row = BOARD_ROWS - (max_row_offset + 1)

        self.col = max(0, min(self.col, max_col))
        self.row = max(0, min(self.row, max_row))

    def draw(self, sketch):
        x, y = self.get_pixel_origin()
        sketch.set_stroke("#202020")
        sketch.set_stroke_weight(2)
        sketch.set_fill(self.color)
        for dc, dr in self.cells:
            sketch.draw_rect(
                x + dc * CELL_SIZE, y + dr * CELL_SIZE, CELL_SIZE, CELL_SIZE
            )


def build_pieces():
    keys = list(SHAPES.keys())
    random.shuffle(keys)
    spawn_positions = [(0, 0), (4, 0), (8, 0), (0, 5), (4, 5), (8, 5), (2, 10)]
    return [Piece(key, col, row) for key, (col, row) in zip(keys, spawn_positions)]


def main():
    sketch = sketchingpy.Sketch2D(WIDTH, HEIGHT)
    sketch.set_title("tetraboard")
    sketch.set_rect_mode("corner")

    pieces = build_pieces()
    drag_state = {"active": None}

    def draw_board():
        sketch.clear("#101014")

        sketch.set_fill("#181820")
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(1)
        sketch.draw_rect(
            BOARD_X, BOARD_Y, BOARD_COLS * CELL_SIZE, BOARD_ROWS * CELL_SIZE
        )

        for c in range(BOARD_COLS + 1):
            x = BOARD_X + c * CELL_SIZE
            sketch.draw_line(x, BOARD_Y, x, BOARD_Y + BOARD_ROWS * CELL_SIZE)
        for r in range(BOARD_ROWS + 1):
            y = BOARD_Y + r * CELL_SIZE
            sketch.draw_line(BOARD_X, y, BOARD_X + BOARD_COLS * CELL_SIZE, y)

    def on_press(button):
        mouse = sketch.get_mouse()
        px = mouse.get_pointer_x()
        py = mouse.get_pointer_y()

        for piece in reversed(pieces):
            if piece.contains_point(px, py):
                piece.dragging = True
                x, y = piece.get_pixel_origin()
                piece.drag_offset_x = px - x
                piece.drag_offset_y = py - y

                pieces.remove(piece)
                pieces.append(piece)  # bring to front

                drag_state["active"] = piece
                break

    def on_release(button):
        piece = drag_state["active"]
        if piece is not None:
            piece.dragging = False
            piece.snap_to_grid()
            drag_state["active"] = None

    def step(sketch_ref):
        active = drag_state["active"]
        if active is not None:
            mouse = sketch_ref.get_mouse()
            px = mouse.get_pointer_x()
            py = mouse.get_pointer_y()
            active.col = (px - active.drag_offset_x - BOARD_X) / CELL_SIZE
            active.row = (py - active.drag_offset_y - BOARD_Y) / CELL_SIZE

        draw_board()
        for piece in pieces:
            piece.draw(sketch_ref)

        if DEBUG_POINTER:
            mouse = sketch_ref.get_mouse()
            dx = mouse.get_pointer_x()
            dy = mouse.get_pointer_y()
            sketch_ref.set_stroke("#FF00FF")
            sketch_ref.set_stroke_weight(2)
            sketch_ref.draw_line(dx - 8, dy, dx + 8, dy)
            sketch_ref.draw_line(dx, dy - 8, dx, dy + 8)

    sketch.get_mouse().on_button_press(on_press)
    sketch.get_mouse().on_button_release(on_release)
    sketch.on_step(step)
    sketch.show()


if __name__ == "__main__":
    main()
