"""Mode/tetrachord definitions, loaded from modes.yaml.

A tetrachord is defined once per mode as a semitone interval pattern
(e.g. Major = 2,2,1). Each mode offers a handful of fingering Shapes for
that same tetrachord -- "straight" (no string jump), "right"/"left" (the
'fundamental axiom' string-jump applied early vs. late) -- generated
from the interval pattern plus which note index the jump happens
before. This keeps the YAML tuning-agnostic: how many semitones a
string-jump is actually worth depends on the tuning in use, so it's
supplied by the caller (main.py) at generation time, not baked into the
data. See modes.yaml's header comment for the full derivation.

A Shape can also carry explicit `cells` instead of `jumps`, as an escape
hatch for one-off shapes that don't fit the generation rule (e.g. a
3-string-crossing shape someone hand-authors for a specific passage).

Pure data/math -- no knowledge of Fret/OpenString/Fretboard or
sketchingpy. main.py is what turns a Shape's resolved cells into a
draggable Piece positioned somewhere.
"""

from dataclasses import dataclass, field

import yaml


@dataclass
class Shape:
    """One fingering for a mode's tetrachord: a name plus how to build it.

    Either `jumps` (generate cells from the mode's interval pattern) or
    `cells` (use these exact offsets, bypassing generation) -- not both.
    """

    name: str
    jumps: list[int] = field(default_factory=list)
    cells: list[tuple[int, int]] | None = None

    def resolve_cells(self, intervals: list[int], string_interval: int) -> list[tuple[int, int]]:
        """This shape's (col, row) cells for a specific tuning.

        `intervals` are the tetrachord's cumulative semitone steps (e.g.
        Major's 2,2,1 -> notes at 0,2,4,5 semitones from the root).
        `jumps` lists the note indices (0-based) that start being
        fretted on the next string up -- e.g. jumps=[1] means note 0
        stays on the anchor string and notes 1-3 move to the adjacent
        (higher-pitched) string. `string_interval` is how many
        semitones that adjacent string actually sits above the anchor
        string in the current tuning (5 for standard bass's perfect
        4ths) -- moving a note there means subtracting that many frets
        to land on the same relative interval.

        Cells are normalized so the shape's own bounding box starts at
        (0, 0), same as a hand-authored shape would -- the "root" note
        isn't necessarily cell (0, 0) once a jump has happened.
        """
        if self.cells is not None:
            return self.cells

        cumulative = [0]
        for step in intervals:
            cumulative.append(cumulative[-1] + step)

        jump_notes = sorted(self.jumps)
        raw = []
        for note_index, semitones in enumerate(cumulative):
            strings_jumped = sum(1 for jump_at in jump_notes if jump_at <= note_index)
            col = semitones - strings_jumped * string_interval
            row = -strings_jumped
            raw.append((col, row))

        min_col = min(c for c, _ in raw)
        min_row = min(r for _, r in raw)
        return [(c - min_col, r - min_row) for c, r in raw]


@dataclass
class Mode:
    """One mode's tray: its display color, tetrachord, and fingering shapes."""

    name: str
    color: str
    intervals: list[int]
    shapes: list[Shape]


def load_modes(path: str = "modes.yaml") -> list[Mode]:
    """Load mode/tetrachord definitions from a YAML file (see modes.yaml)."""
    with open(path) as handle:
        raw = yaml.safe_load(handle)

    return [
        Mode(
            name=mode["name"],
            color=mode["color"],
            intervals=list(mode["intervals"]),
            shapes=[
                Shape(
                    name=shape["name"],
                    jumps=list(shape.get("jumps", [])),
                    cells=[tuple(cell) for cell in shape["cells"]] if "cells" in shape else None,
                )
                for shape in mode["shapes"]
            ],
        )
        for mode in raw["modes"]
    ]
