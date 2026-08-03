"""The fretboard, comprised of strings."""

from dataclasses import dataclass, field
from enum import Enum

from config import AccidentalType
from open_string import OpenString


class TUNINGS(Enum):
    """Available bass guitar tunings. Values match the <option> values in
    index.html's #control-tuning select -- see main.py's _resolve_tuning()
    for where the two get bridged."""

    STANDARD_4 = ["E1", "A1", "D2", "G2"]
    STANDARD_5 = ["B0", "E1", "A1", "D2", "G2"]
    STANDARD_6 = ["B0", "E1", "A1", "D2", "G2", "C3"]


@dataclass
class Fretboard:
    """The fret grid: its own bounds, background, and grid lines."""

    canvas_pos_x: int
    canvas_pos_y: int
    strings: list[OpenString]

    @property
    def width(self):
        return self.strings[0].total_width

    @property
    def height(self):
        return sum([string.fret_width for string in self.strings])

    def draw(self, sketch):
        sketch.set_fill("#EEEEEE")
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(1)

        sketch.draw_rect(self.canvas_pos_x, self.canvas_pos_y, self.width, self.height)

        for string in self.strings:
            string.draw(sketch)


@dataclass
class FretboardBuilder:
    """A fluent builder for Fretboard -- this is where controls.py's
    get_string_count()/get_tuning()/get_fret_count() are meant to plug in
    once you're ready (see DEVELOPING.md's "portal" section)."""

    canvas_pos_x: int = 0
    canvas_pos_y: int = 0
    tuning: TUNINGS = TUNINGS.STANDARD_6
    n_frets: int = 24
    n_strings: int = 6
    accidental_type: AccidentalType = AccidentalType.SHARP
    strings: list[OpenString] = field(default_factory=list)

    def set_position(self, x: int, y: int) -> "FretboardBuilder":
        self.canvas_pos_x = x
        self.canvas_pos_y = y
        return self

    def set_tuning(self, tuning: TUNINGS) -> "FretboardBuilder":
        if not isinstance(tuning, TUNINGS):
            raise TypeError(f"tuning must be a TUNINGS member, got {tuning!r}")
        self.tuning = tuning
        return self

    def set_n_frets(self, n_frets: int) -> "FretboardBuilder":
        if not isinstance(n_frets, int) or n_frets <= 0:
            raise ValueError(f"n_frets must be a positive integer, got {n_frets!r}")
        self.n_frets = n_frets
        return self

    def set_n_strings(self, n_strings: int) -> "FretboardBuilder":
        if not isinstance(n_strings, int) or n_strings <= 0:
            raise ValueError(f"n_strings must be a positive integer, got {n_strings!r}")
        self.n_strings = n_strings
        return self

    def set_accidental_type(
        self, accidental_type: AccidentalType
    ) -> "FretboardBuilder":
        if not isinstance(accidental_type, AccidentalType):
            raise TypeError(
                f"accidental_type must be an AccidentalType member, got {accidental_type!r}"
            )
        self.accidental_type = accidental_type
        return self

    def build_string(self, note_identity: str, index: int, n_frets: int) -> OpenString:
        new_string = OpenString(
            note_identity=note_identity,
            index=index,
            n_frets=n_frets,
            accidental_type=self.accidental_type,
        )
        return new_string

    def build(self) -> Fretboard:
        """Assemble self.strings from self.tuning, then build the Fretboard."""

        # self.tuning.value is low-to-high (e.g. ["B0", ..., "C3"]), but the
        # lowest-pitched string is drawn at the bottom (index counts down
        # from the top row) -- standard tab/diagram convention: highest
        # string on top, lowest on the bottom.
        n_strings = len(self.tuning.value)
        self.strings = [
            self.build_string(note_identity=note, index=n_strings - 1 - i, n_frets=self.n_frets)
            for i, note in enumerate(self.tuning.value)
        ]

        return Fretboard(
            canvas_pos_x=self.canvas_pos_x,
            canvas_pos_y=self.canvas_pos_y,
            strings=self.strings,
        )
