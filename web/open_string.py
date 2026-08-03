"""A single string on the fretboard, comprised of frets."""

from dataclasses import dataclass, field

from config import (
    FRET_HEIGHT,
    FRET_WIDTH,
    FRETBOARD_BORDER_X,
    FRETBOARD_BORDER_Y,
    AccidentalType,
    get_notes_for_string,
)
from fret import Fret


@dataclass
class OpenString:
    """A single string on the fretboard."""

    note_identity: str
    index: int
    n_frets: int = 24
    accidental_type: AccidentalType = AccidentalType.SHARP
    fret_height: int = FRET_HEIGHT
    fret_width: int = FRET_WIDTH
    frets: list[Fret] = field(default_factory=list)

    def __post_init__(self):
        self.frets = self._build_frets()

    @property
    def y(self):
        return FRETBOARD_BORDER_Y + self.index * self.fret_height + self.fret_height / 2

    @property
    def total_width(self):
        # +1: fret_index 0 is the open string, fret_index n_frets is the
        # last actual fret -- n_frets+1 columns total (see _build_frets).
        return self.fret_width * (self.n_frets + 1)

    def _build_frets(self) -> list[Fret]:
        """Build this string's Frets: fret_index 0 (open) through n_frets."""
        string_notes = get_notes_for_string(
            self.note_identity, self.n_frets, self.accidental_type
        )

        return [
            Fret(
                index=fret_index,
                note=string_notes[fret_index],
                selected=False,
                pixel_origin=(
                    FRETBOARD_BORDER_X + fret_index * self.fret_width,
                    self.y - self.fret_height / 2,
                ),
                pixel_width=self.fret_width,
                pixel_height=self.fret_height,
            )
            for fret_index in range(self.n_frets + 1)
        ]

    def draw(self, sketch):
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(2)

        for fret in self.frets:
            fret.draw(sketch)
