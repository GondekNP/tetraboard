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
        return CHROMATIC_SCALE_FLATS_WITH_OCTAVE[
            first_index : first_index + n_frets + 1
        ]
    else:
        raise ValueError("Invalid accidental type")


def semitone_distance(note_a: str, note_b: str) -> int:
    """Semitones from note_a up to note_b, e.g. the gap between two
    adjacent open strings in a tuning -- used to generate tetrachord
    string-jump shapes without baking a specific tuning into them (see
    modes.py's Shape.resolve_cells).
    """
    return CHROMATIC_SCALE_SHARPS_WITH_OCTAVE.index(
        note_b
    ) - CHROMATIC_SCALE_SHARPS_WITH_OCTAVE.index(note_a)


# Ionian (major scale) whole/half step pattern -- the "parent scale" the
# validator checks against. Every mode tray (Major/Minor/Phrygian/Lydian)
# is, by construction, a tetrachord lifted straight from some mode of this
# same parent scale (Major = Ionian's own lower tetrachord rooted on the
# key; Lydian's tetrachord is the Ionian pattern's own 4th-degree
# tetrachord; etc) -- so the *pitch classes* valid for any of them, in a
# given key, are always exactly this one 7-note set. That's what makes the
# "simple" validation approach simple: don't bother deriving a different
# scale per mode, just check every dropped piece's notes against this one
# key's Ionian pitch-class set, regardless of which tray it came from.
IONIAN_INTERVALS = [2, 2, 1, 2, 2, 2, 1]


_PITCH_CLASS_TO_SEMITONE = {
    name: index
    for scale in (CHROMATIC_SCALE_SHARPS, CHROMATIC_SCALE_FLATS)
    for index, name in enumerate(scale)
}


def pitch_class_semitone(note: str) -> int:
    """The 0-11 semitone class of a note (octave-qualified like "A1"/"Db3"
    or bare like "A"/"Db"), independent of whether it's spelled with
    sharps or flats.

    Scale-membership checks need this rather than a name comparison --
    get_notes_for_string spells a fret's note using whichever
    AccidentalType is currently selected, so "C#" and "Db" must compare
    equal here even though they're different strings.
    """
    bare = note.rstrip("0123456789")
    return _PITCH_CLASS_TO_SEMITONE[bare]


def get_scale_pitch_classes(root: str, intervals: list[int] = IONIAN_INTERVALS) -> set[int]:
    """The semitone classes (0-11, see pitch_class_semitone) of the scale
    built from `root` using `intervals` (cumulative semitone steps,
    wrapping at the octave).

    `root` must be a bare pitch class (e.g. "A", "C#", "Db") -- not an
    octave-qualified note like "A1".
    """
    cumulative = [0]
    for step in intervals[:-1]:
        cumulative.append(cumulative[-1] + step)

    root_semitone = pitch_class_semitone(root)
    return {(root_semitone + semitones) % 12 for semitones in cumulative}
