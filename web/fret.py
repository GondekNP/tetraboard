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

    def draw(self, canvas):
        """Draw the fret on the given canvas."""
        x, y = self.pixel_origin
        canvas.create_rectangle(
            x,
            y,
            x + self.pixel_width,
            y + self.pixel_height,
            fill="white" if not self.selected else "blue",
            outline="black",
        )
        if self.note:
            canvas.create_text(
                x + self.pixel_width / 2,
                y + self.pixel_height / 2,
                text=self.note,
                fill="black",
            )
