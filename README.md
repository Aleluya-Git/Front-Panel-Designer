<img width="255" height="275" alt="jpeg" src="https://github.com/user-attachments/assets/7f0727f9-37a1-493d-85f6-8608486a240b" />

# Electronic Front Panel Designer

**English** · [Español](README.es.md) · [Deutsch](README.de.md) · [Français](README.fr.md)
Desktop application (Windows, Linux, macOS) for designing front and rear panels of electronic equipment:
power supplies, amplifiers, instruments, Eurorack modules, Hammond enclosures, 19" rack panels and any other
boxed device. Draw the panel, drop in real components from the library, add text, scales and graphics,
check for interferences and export ready-to-manufacture files (DXF, SVG, PDF, PNG, STL, G-code, HPGL).

The interface is available in Spanish, English, German and French, and new languages can be added from a JSON file.

<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/f4160162-5d39-476f-833f-6bc74736f2b6" />

Written in Python with PySide6 (Qt 6). 

## Download

Ready-to-install versions for **Windows** (installer `.exe`) and **macOS** (`.dmg`, Apple Silicon and Intel)
are on the [Releases page](https://github.com/Aleluya-Git/Front-Panel-Designer/releases/latest). They are not
code-signed: on Windows click *More info → Run anyway* if SmartScreen warns; on macOS, the first time, go to
*System Settings → Privacy & Security → Open Anyway*.

## Running from source


| System | Install | Run | Self-test |
|---|---|---|---|
| Windows | `install.bat` | `run.bat` | `autoprueba.bat` |
| Linux / macOS | `./install.sh` | `./run.sh` | `./autoprueba.sh` |

Requires Python 3.10 or newer. The only dependency is **PySide6**.

```bash
git clone https://github.com/Aleluya-Git/Front-Panel-Designer.git
cd Front-Panel-Designer
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

`autoprueba` runs the core unit tests and an unattended walk-through of the whole interface (mouse-driven
drawing, component placement, exports in every format, screenshots, 3D view). The report is written to
`autoprueba_resultado.txt` and the generated files to `autoprueba_salida/`. Unit tests alone:
`python -m unittest tests.test_core`.

Example projects are in `ejemplos/`: a lab power supply, a 12HP Eurorack VCO and the rear panel of a 2U rack
amplifier.

## Features

- **2D CAD canvas** in millimetres (origin bottom-left, Y up): zoom, pan, grid, snap to grid and to objects,
  rulers, AutoCAD-style window/crossing selection, layers with visibility, lock, colour and process
  (through cut, pocket, engraving, silkscreen, dimensions, reference). Shapes are previewed while you draw them.
- **Shapes and machining**: rectangle, rounded rectangle, circle, ellipse, regular and free polygons,
  rectangular and oval slots, D-holes, mounting / countersunk / threaded holes (metric table M2–M8), pockets
  with depth, DXF and SVG outline import.
- **Component library** with 60+ parts (each with machining, visible outline and rear body): rotary and slide
  potentiometers, faders, encoders, switches, push buttons, LEDs, LCD/OLED/TFT displays, meters, banana, BNC,
  RCA, XLR, Speakon, 3.5/6.35 mm jacks, DC, USB-A/B/C, RJ45, IEC inlets, fuse holders, D-Sub, MIDI, terminals,
  fans and 80+ fan grilles. Thumbnails and image tooltips; custom components saved to new or existing
  libraries that can be exported and shared.
- **Text and graphics**: multi-line text with system fonts, size, weight, italic, underline, strikeout,
  colour, alignment, spacing and rotation; automatic component labels; SVG/DXF logos and PNG/JPG images.
- **Scale generator** for rotary and slide potentiometers: start/end angle, radius or length, marks (lines,
  dots, any character or none), minor marks, numbering (start, end, step, every N marks, decimals,
  prefix/suffix) or custom texts, text size, gap, position and rotation, colours for marks and minor marks,
  single-line mode for CNC engraving, live preview and 11 presets.
- **Self-clinching threaded studs and standoffs** (PEM style, M2–M6), front or rear, with blind holes and a
  dimensioned cross-section.
- **Panel**: presets (19" rack 1U–4U, Eurorack 3U, Hammond 1590B/BB/XX, instrument cases), material,
  thickness, corner radius, panel and silkscreen colours, finish.
- **Dimensions and checks**: automatic dimensions next to each element, associative user dimensions,
  measuring tool, and a design-rule checker for parts outside the panel, edge distance, minimum web between
  holes, overlaps, rear-body collisions, pockets that break through, and text, scales and labels that run into
  holes, cross pocket edges, sit under a knob or overlap each other.
- **Parametric design**: every value accepts expressions (`=W/2`, `=margin + 2*pitch`) with global variables
  and built-ins W, H, T, HP (5.08) and U (44.45); linked auto-distribution, align, distribute, arrays,
  mirror and rotate.
- **Export**: layered DXF R12, SVG (manufacturing or realistic, Inkscape layers), vector PDF (realistic or 1:1
  drilling template), PNG with selectable resolution and optional user/automatic dimensions, STL for 3D
  printing, G-code (engraving, pocketing, drilling, arcs, tool radius compensation, Z passes, outline) and HPGL.
- **3D preview** rendered in software (no OpenGL needed) with materials and lighting.
- **Projects**: `.efpd` files (ZIP with readable JSON), unlimited undo/redo with a browsable history, change
  log, autosave with crash recovery, recent files, light and dark themes, configurable toolbars and docks.

Library dimensions are indicative: always check the manufacturer's datasheet before machining.

## Project layout

```
efpd/core   geometry, entities, document, expressions, library, checks, scales, studs (no Qt)
efpd/io     DXF/SVG import and export, STL mesh, G-code/HPGL, project files
efpd/gui    PySide6 interface: main window, canvas, dialogs, 3D view, themes, icons
efpd/lang   translations (en, de, fr)
tests       unit tests and a Qt-free paint simulation
tools       self-test, example and translation generators
packaging   PyInstaller spec, Windows installer (Inno Setup) and macOS disk image scripts
```

See [ARQUITECTURA.md](ARQUITECTURA.md) (Spanish) for the architecture notes.

## License

Copyright © 2026 Aleluya-Git.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General
Public License version 3 as published by the Free Software Foundation (see [LICENSE](LICENSE)). It is
distributed in the hope that it will be useful, but **without any warranty**; without even the implied warranty
of merchantability or fitness for a particular purpose.
