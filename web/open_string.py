"""A single string on the fretboard, comprised of frets."""

from dataclasses import dataclass

from config import FRET_HEIGHT, FRET_WIDTH, FRETBOARD_BORDER_X, FRETBOARD_BORDER_Y


@dataclass
class OpenString:
    """A single string on the fretboard."""

    note_identity: str
    n_frets: int
    fret_height: int = FRET_HEIGHT
    fret_width: int = FRET_WIDTH

    @property
    def y(self):
        return FRETBOARD_BORDER_Y + self.index * self.fret_height + self.fret_width / 2

    def draw(self, sketch):
        sketch.set_stroke("#303038")
        sketch.set_stroke_weight(2)

        for fret in range(self.n_frets):
            sketch.draw_rect(
                FRETBOARD_BORDER_X + fret * FRET_WIDTH,
                self.y - (self.fret_height / 2),
                FRET_WIDTH,
                FRET_HEIGHT,
            )
