"""A single fret position on a string, drawn as one cell of the
fretboard grid (see OpenString/Fretboard)."""

from dataclasses import dataclass

from config import estimate_text_width, split_note_octave

_LABEL_COLOR = "#303038"
_LABEL_FONT_SIZE = 15
# The vanilla export view's octave digit (see main.py's _export_label)
# gets the same de-emphasized treatment for the same reason: the octave
# number matters far less than the letter for reading a pattern at a
# glance, so it's smaller rather than drawn at equal weight.
_LABEL_OCTAVE_FONT_SIZE = 9
# No text-measurement API is available (see config.estimate_text_width),
# so the letter/octave split point is estimated from character count
# instead of exact pixel width -- tuned by eye for this font/size, same
# technique as the export's own EXPORT_TEXT_WIDTH_FACTOR (main.py), just
# a separate constant since that one's tuned for a different font size.
_LABEL_WIDTH_FACTOR = 0.6


@dataclass
class Fret:
    """A single fret position on a string."""

    index: int
    note: str = ""
    selected: bool = False
    pixel_origin: tuple[int, int] = (0, 0)
    pixel_width: int = 0
    pixel_height: int = 0

    def draw(self, sketch):
        """Draw this fret on the sketch."""
        sketch.draw_rect(
            self.pixel_origin[0],
            self.pixel_origin[1],
            self.pixel_width,
            self.pixel_height,
        )

        # push_style/pop_style scope the fill/font/align changes below to
        # just this text draw -- sketchingpy's style state is otherwise
        # sticky, so without this every fret drawn after this one would
        # inherit this dark fill for its own rect background too.
        sketch.push_style()
        sketch.set_fill(_LABEL_COLOR)

        cx = self.pixel_origin[0] + self.pixel_width / 2
        cy = self.pixel_origin[1] + self.pixel_height / 2
        letter, octave = split_note_octave(self.note)
        if octave:
            letter_width = estimate_text_width(letter, _LABEL_FONT_SIZE, _LABEL_WIDTH_FACTOR)
            octave_width = estimate_text_width(octave, _LABEL_OCTAVE_FONT_SIZE, _LABEL_WIDTH_FACTOR)
            split_x = cx + (letter_width - octave_width) / 2
            sketch.set_text_font("sans-serif", _LABEL_FONT_SIZE)
            sketch.set_text_align("right", "center")
            sketch.draw_text(split_x, cy, letter)
            sketch.set_text_font("sans-serif", _LABEL_OCTAVE_FONT_SIZE)
            sketch.set_text_align("left", "center")
            sketch.draw_text(split_x, cy, octave)
        else:
            sketch.set_text_font("sans-serif", _LABEL_FONT_SIZE)
            sketch.set_text_align("center", "center")
            sketch.draw_text(cx, cy, self.note)
        sketch.pop_style()
