from enum import Enum

# --------------------------------------------------------------------------

# Board / grid configuration
# --------------------------------------------------------------------------
# FRET_SIZE = 40
FRET_WIDTH = 70
FRET_HEIGHT = 40

FRETBOARD_COLS = 25
FRETBOARD_ROWS = 10
FRETBOARD_BORDER_X = 40
FRETBOARD_BORDER_Y = 40

FRETBOARD_WIDTH = FRETBOARD_BORDER_X * 2 + (FRETBOARD_COLS * FRET_SIZE)
FRETBOARD_HEIGHT = FRETBOARD_BORDER_Y * 2 + (FRETBOARD_ROWS * FRET_SIZE)

TETRA_TRAY_HEIGHT = 200  # space below the fretboard for draggable pieces
TETRA_TRAY_WIDTH = FRETBOARD_WIDTH  # same width as the fretboard

TOTAL_HEIGHT = FRETBOARD_HEIGHT + TETRA_TRAY_HEIGHT + (2 * FRETBOARD_BORDER_Y)
TOTAL_WIDTH = FRETBOARD_WIDTH  # same width as the fretboard


class AccidentalType(Enum):
    SHARP = 1
    FLAT = 2


CHROMATIC_SCALE_SHARPS = [
    "A",
    "A#",
    "B",
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
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
]

CHROMATIC_SCALE_FLATS = [
    "A",
    "Bb",
    "B",
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
    "C",
    "Db",
    "D",
    "Eb",
    "E",
    "F",
    "Gb",
    "G",
    "Ab",
]


def get_chromatic_scale(open_string: str, accidental_type: AccidentalType):
    if accidental_type == AccidentalType.SHARP:
        first_index = CHROMATIC_SCALE_SHARPS.index(open_string)
        return (
            CHROMATIC_SCALE_SHARPS[first_index:] + CHROMATIC_SCALE_SHARPS[:first_index]
        )
    elif accidental_type == AccidentalType.FLAT:
        first_index = CHROMATIC_SCALE_FLATS.index(open_string)
        return CHROMATIC_SCALE_FLATS[first_index:] + CHROMATIC_SCALE_FLATS[:first_index]
    else:
        raise ValueError("Invalid accidental type")
