from enum import Enum

# --------------------------------------------------------------------------

# Board / grid configuration
# --------------------------------------------------------------------------
FRET_WIDTH = 70
FRET_HEIGHT = 40

FRETBOARD_COLS = 25
FRETBOARD_ROWS = 10

# Extra draggable columns left of the open string (fret column 0), so a
# tetra shape can be positioned covering the open string and beyond even
# though nothing playable actually exists there -- see main.py's
# Piece.snap_to_grid.
OPEN_STRING_BUFFER_COLS = 1

FRETBOARD_BORDER_X = 40 + (OPEN_STRING_BUFFER_COLS * FRET_WIDTH)
FRETBOARD_BORDER_Y = 40

FRETBOARD_WIDTH = FRETBOARD_BORDER_X * 2 + (FRETBOARD_COLS * FRET_WIDTH)
FRETBOARD_HEIGHT = FRETBOARD_BORDER_Y * 2 + (FRETBOARD_ROWS * FRET_HEIGHT)

MODE_TRAY_HEIGHT = 130  # height of a single mode's tray (Major/Minor/Phrygian/Lydian)
MODE_TRAY_COUNT = 4

TETRA_TRAY_HEIGHT = MODE_TRAY_HEIGHT * MODE_TRAY_COUNT  # stacked mode trays
TETRA_TRAY_WIDTH = FRETBOARD_WIDTH  # same width as the fretboard

TOTAL_HEIGHT = FRETBOARD_HEIGHT + TETRA_TRAY_HEIGHT + (2 * FRETBOARD_BORDER_Y)
TOTAL_WIDTH = FRETBOARD_WIDTH  # same width as the fretboard


class AccidentalType(Enum):
    SHARP = 1
    FLAT = 2


CHROMATIC_SCALE_SHARPS = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
]

CHROMATIC_SCALE_SHARPS_WITH_OCTAVE = [
    letter + str(number) for number in range(9) for letter in CHROMATIC_SCALE_SHARPS
]

CHROMATIC_SCALE_FLATS = [
    "C",
    "Db",
    "D",
    "Eb",
    "E",
    "F",
    "Gb",
    "G",
    "Ab",
    "A",
    "Bb",
    "B",
]

CHROMATIC_SCALE_FLATS_WITH_OCTAVE = [
    letter + str(number) for number in range(9) for letter in CHROMATIC_SCALE_FLATS
]


def get_notes_for_string(
    starting_note: str, n_frets: int, accidental_type: AccidentalType
):
    if accidental_type == AccidentalType.SHARP:
        first_index = CHROMATIC_SCALE_SHARPS_WITH_OCTAVE.index(starting_note)
        return CHROMATIC_SCALE_SHARPS_WITH_OCTAVE[
            first_index : first_index + n_frets + 1
        ]
    elif accidental_type == AccidentalType.FLAT:
        first_index = CHROMATIC_SCALE_FLATS_WITH_OCTAVE.index(starting_note)
        return CHROMATIC_SCALE_SHARPS_WITH_OCTAVE[
            first_index : first_index + n_frets + 1
        ]
    else:
        raise ValueError("Invalid accidental type")
