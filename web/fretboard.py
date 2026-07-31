"""The fretboard, comprised of strings."""

from dataclasses import dataclass
from enum import Enum
from open_string import OpenString


class TUNINGS(Enum):
    """Available bass guitar tuning."""

    STANDARD = ["B0", "E1", "A1", "D2", "G2", "C3"]


@dataclass
class Fretboard:
    """The fret grid: its own bounds, background, and grid lines."""

    canvas_pos_x: int
    canvas_pos_y: int
    strings: list[OpenString]

    @property
    def width(self):
        return self.strings[0].get_total_width() if self.strings else 0

    @property
    def height(self):
        return self.strings[0].get_total_height() if self.strings else 0

    def draw(self, sketch):
        sketch.set_fill("#EEEEEE")
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(1)

        sketch.draw_rect(self.canvas_pos_x, self.canvas_pos_y, self.width, self.height)

        for string in self.strings:
            string.draw(sketch)


class FretboardBuilder:
    """A builder for the fretboard."""

    def set_tuning(self, tuning: TUNINGS) -> "FretboardBuilder":
        self.tuning = tuning
        return self

    def build_string(
        self, starting_note: str, string_number: int, num_frets: int
    ) -> OpenString:
        return OpenString(
            starting_note=starting_note,
            string_number=string_number,
            num_frets=num_frets,
        )

    def build(self) -> Fretboard:

        return Fretboard(
            canvas_pos_x=self.canvas_pos_x,
            canvas_pos_y=self.canvas_pos_y,
            strings=self.strings,
        )
