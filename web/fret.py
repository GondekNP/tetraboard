"""A single fret position on a string.

Dataclass shell only -- no behavior. Not yet wired into String; that's
future work once selection/styling is ready to build.
"""

from dataclasses import dataclass


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
        sketch.set_fill("#303038")
        sketch.set_text_font("sans-serif", 14)
        sketch.set_text_align("center", "center")
        sketch.draw_text(
            self.pixel_origin[0] + self.pixel_width / 2,
            self.pixel_origin[1] + self.pixel_height / 2,
            self.note,
        )
        sketch.pop_style()
