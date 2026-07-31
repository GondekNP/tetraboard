# fretboard-lab

Local dev loop for iterating on a Sketchingpy-based fretboard diagram
editor, without fighting the online editor's embedded-canvas quirks.

## Why this shape

The app runs entirely client-side (Pyodide/PyScript in your browser),
so the dev container only needs to host plain static files -- no GUI
passthrough, no X11 forwarding, no pygame. `web/index.html` +
`web/main.py` are served as-is; you edit `main.py`, refresh the
browser tab, done.

This also sidesteps the pointer-offset bug we hit in the online
editor: that came from the canvas being squeezed into a resizable
split-pane with its own CSS scaling. Here the canvas renders at native
size in a plain page, so clicks should line up 1:1. If it ever drifts
again, flip `DEBUG_POINTER = True` in `main.py` for a crosshair that
shows exactly where Sketchingpy thinks your pointer is.

## Getting started

1. Open this folder in VS Code and "Reopen in Container" (or `docker
   build`/`docker run` it yourself -- the Dockerfile has no surprises).
2. Inside the container: `make serve` (or `python scripts/serve.py`).
3. On your host machine, open `http://localhost:8000`. VS Code should
   also offer to forward/open the port automatically.
4. Edit `web/main.py`, save, refresh the tab.

No `pip install` of Sketchingpy is needed on your machine -- the
browser loads PyScript from the pyscript.net CDN and Sketchingpy from
PyPI, both declared in `web/index.html`. If you want a fully offline
setup later, swap that for the self-host bundle (see Sketchingpy's
self-host guide -- you'll need to mirror the whole `third_party/`
directory PyScript ships, not just `core.js`, since it dynamically
loads several other chunk files) and point
`.devcontainer` at serving those files too.

## Where `web/main.py` is right now

It's the drag-and-snap scaffold from earlier, unchanged in mechanics:
a handful of shapes you can drag from their spawn spots and drop onto
a grid, where they snap into place. That interaction is structurally
what you'll want for dragging diagram components out of a "drawer" and
onto a fretboard -- swap `SHAPES` for real components and `Piece` for
whatever a diagram element needs to know about itself (string, fret,
finger, label text, etc).

## Things you'll probably want to design next

Left entirely to you, since you want to drive this part -- just noting
the shape of a couple of decisions so they're not a surprise later:

- **Panes/drawers**: could be as simple as several off-board spawn
  regions (like the current shapes) grouped by category, with tabs or
  a scroll to "shuffle through" which region is visible.
- **Save format**: since this is a static, serverless page, the
  natural fit is a "Save" button that serializes your diagram state
  (e.g. with `struct`/`pickle`/`msgpack` -- whatever binary shape you
  want) and triggers a browser download, plus an "Open" file input to
  load it back. No backend needed either way.
- **SVG copy/paste**: two directions worth weighing --
  (a) keep the canvas renderer for interaction and write a small,
  separate function that walks your diagram state and emits an SVG
  string for export, or
  (b) render the fretboard itself as real SVG DOM elements (via
  PyScript's `js`/`document.createElementNS` interop) instead of
  canvas, which would make "copy as SVG" nearly free (serialize
  `outerHTML`) at the cost of losing Sketchingpy's drawing API for
  that part. Worth a quick prototype of each before committing.
