"""Mode/tetra definitions, loaded from modes.yaml.

Pure data -- describes what can be dragged onto the fretboard (a name,
a color, and a shape made of cell offsets) with no knowledge of
Fret/OpenString/Fretboard or sketchingpy. main.py is what turns a Tetra
into a draggable Piece positioned somewhere.
"""

from dataclasses import dataclass

import yaml


@dataclass
class Tetra:
    """A single draggable shape: a name plus [col, row] cell offsets."""

    name: str
    cells: list[tuple[int, int]]


@dataclass
class Mode:
    """One mode's tray: its display color and the tetras it offers."""

    name: str
    color: str
    tetras: list[Tetra]


def load_modes(path: str = "modes.yaml") -> list[Mode]:
    """Load mode/tetra definitions from a YAML file (see modes.yaml)."""
    with open(path) as handle:
        raw = yaml.safe_load(handle)

    return [
        Mode(
            name=mode["name"],
            color=mode["color"],
            tetras=[
                Tetra(name=tetra["name"], cells=[tuple(cell) for cell in tetra["cells"]])
                for tetra in mode["tetras"]
            ],
        )
        for mode in raw["modes"]
    ]
