# Developing tetraboard

How the pieces fit together, and specifically where the line is between
"scaffolding you can treat as done" and "the part you're building."

## The split

Everything here falls into one of two buckets:

**Yours to build** -- the actual fretboard, drawn with Sketchingpy:

- `web/fret.py` -- `Fret` (a single fret position)
- `web/open_string.py` -- `OpenString` (a string, made of frets)
- `web/fretboard.py` -- `Fretboard` (the board, made of strings)
- `web/main.py` -- wires the above into a `Sketch2D`, owns the draw loop
  and canvas-level interaction (dragging, selection, whatever comes next)

This is deliberately where all the sketchingpy-API decisions live. Nothing
described below reaches into these files or tells you how to structure
them -- see `TUTORIAL.md` for the abstraction reference if you want it, but
the OOP shape is yours.

**Scaffolding** -- the surrounding chrome that isn't about learning
sketchingpy's API, built so you don't have to stop and build it yourself:

- `web/index.html` -- page shell, the `<py-config>` block, and a plain-HTML
  control panel (string count / tuning / fret count pickers, Export PNG,
  Save State, Load State)
- `web/controls.py` -- reads the control panel and exposes it to Python
- `web/config.py` -- shared layout constants (fret size, board position, ...)
- `web/devreload.py` -- hot-reload harness (see its own docstring)
- `scripts/serve.py` -- the dev server
- `mypy.ini`, `requirements-dev.txt`, `Makefile` -- `make lint` / `make
  typecheck` tooling

## The portal: `web/controls.py`

Sketchingpy has no dropdown/button/widget abstraction of its own (checked
directly against its source and its own example site -- `TUTORIAL.md`
section 3 has the receipts). So the control panel is plain HTML sitting
next to the canvas in `index.html`, and `controls.py` is the one place that
touches those DOM elements. It knows nothing about `Fret`/`OpenString`/
`Fretboard` -- it only does two things:

1. **Read the pickers**, on demand, whenever your code asks:

   ```python
   import controls

   controls.get_string_count()   # -> int, e.g. 6
   controls.get_tuning()          # -> list[str], e.g. ["B0", "E1", "A1", "D2", "G2", "C3"]
   controls.get_fret_count()      # -> int, e.g. 24
   ```

2. **Fire callbacks you register**, for the three buttons/inputs it can't
   act on by itself because it doesn't know what "your state" or "your
   canvas" means:

   ```python
   controls.on_export_png(callback)   # callback() -> None
   controls.on_save_state(callback)   # callback() -> JSON-serializable object
   controls.on_load_state(callback)   # callback(state: Any) -> None
   ```

   `on_export_png`'s callback should do whatever it takes to export your
   live sketch -- e.g. `sketch.save_image("fretboard.png")` (PNG only; see
   `TUTORIAL.md` section 7 for why). `on_save_state`'s callback returns
   whatever you want serialized (a plain dict is simplest); `controls.py`
   turns that into a downloaded `.json` file itself. `on_load_state`'s
   callback receives that same object back, already parsed from whatever
   file was picked, and should restore your state from it however that
   implies for your object graph.

Wire these up wherever you construct your top-level canvas object -- e.g.
in `main.py`'s equivalent of `MainCanvas.__init__`:

```python
import controls

class MainCanvas:
    def __init__(self):
        self.sketch = sketchingpy.Sketch2D(...)
        # ... build your fretboard using controls.get_string_count() etc ...

        controls.on_export_png(lambda: self.sketch.save_image("fretboard.png"))
        controls.on_save_state(self._serialize_state)
        controls.on_load_state(self._restore_state)
```

Nothing about `controls.py` requires you to call any of this. The pickers
and buttons exist and are wired up on the HTML side regardless -- until you
register a callback, clicking Export/Save silently does nothing, and
Load's callback is simply never invoked.

## Why `controls.py` isn't hot-reloaded

`main.py` gets the fast hot-swap path (`web/devreload.py` swaps it in
without a full Pyodide reboot -- see that file's docstring). `controls.py`
deliberately does not: it calls `addEventListener` once, on page load, the
same way sketchingpy's own canvas input handling does. Re-running that on
every save would stack a second, third, fourth listener onto the same
buttons -- exactly the bug `devreload.py` swaps the canvas element out to
avoid on the sketchingpy side. So editing `controls.py` (or `index.html`)
triggers a full page reload instead, same as always; only `main.py` saves
skip the reboot.

## Running it

Same as `README.md`: `make serve` inside the devcontainer, open
`http://localhost:8000`. Edit `main.py` and save -- no refresh needed.
Editing anything else reloads the page.

```
make lint        # ruff, checks web/
make typecheck    # mypy, checks web/ -- see mypy.ini for why js/pyscript/
                   # pyodide/sketchingpy are configured as untyped imports
```

`make typecheck` will currently flag real mismatches in `fretboard.py`
(`FretboardBuilder` referencing fields it never declares, `OpenString`
being called with kwargs it doesn't have) -- that's mypy doing its job on
code that's mid-refactor, not a scaffolding problem.
