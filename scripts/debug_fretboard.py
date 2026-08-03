"""Local debug harness for the fretboard domain logic.

Runs under regular CPython on your machine -- no browser, no Pyodide.
fret.py/open_string.py/fretboard.py/config.py have no dependency on
js/pyscript/sketchingpy except inside the .draw(sketch) methods, which this
deliberately never calls -- constructing the objects and inspecting their
state doesn't touch any of that, so a normal VS Code breakpoint works
exactly like it would in any other Python project.

Set a breakpoint anywhere in web/*.py (e.g. the first line of
OpenString._build_frets), then run this file via the "Debug fretboard
harness" launch config (.vscode/launch.json), or just open it and use
VS Code's Run/Debug on the active file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web"))

from fretboard import TUNINGS, FretboardBuilder  # noqa: E402


def main():
    builder = FretboardBuilder().set_position(0, 0).set_tuning(TUNINGS.STANDARD_6)

    # build_string() bypasses FretboardBuilder.build()'s still-in-progress
    # loop and constructs an OpenString directly -- exactly the level
    # OpenString._build_frets() operates at, so this is the right place to
    # set a breakpoint for that stub specifically.
    for index, note in enumerate(TUNINGS.STANDARD_6.value):
        string = builder.build_string(note, index, n_frets=24)
        print(f"{note} (string {index}): {len(string.frets)} frets")
        for fret in string.frets[:3]:
            print(" ", fret)

    __fretboard = builder.build()


if __name__ == "__main__":
    main()
