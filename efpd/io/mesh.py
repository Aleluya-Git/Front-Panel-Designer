"""Generación del modelo 3D del panel (extrusión) y exportación STL.

El panel se extruye según su espesor; los mecanizados pasantes se restan y
los rebajes (fresados) se modelan como cavidades con su profundidad. Se usa
una descomposición en trapecios (relleno par-impar), sin dependencias.
"""
from __future__ import annotations

import math
import struct
from typing import List, Tuple

from ..core import geometry as G
from ..core.document import Document

V3 = Tuple[float, float, float]
Tri = Tuple[V3, V3, V3]


def _closed_polys(pr) -> List[G.Poly]:
    return [p for p, closed in G.prim_polys(pr, 0.03) if closed and len(p) >= 3]


def _cap(polys, z, up=True) -> List[Tri]:
    tris: List[Tri] = []
    for (ya, yb, xl0, xl1, xr0, xr1) in G.trapezoids(polys):
        bl, br, tr, tl = (xl0, ya, z), (xr0, ya, z), (xr1, yb, z), (xl1, yb, z)
        for t in ((bl, br, tr), (bl, tr, tl)):
            if abs((t[1][0] - t[0][0]) * (t[2][1] - t[0][1]) - (t[2][0] - t[0][0]) * (t[1][1] - t[0][1])) < 1e-12:
                continue
            tris.append(t if up else (t[0], t[2], t[1]))
    return tris


def _walls(poly: G.Poly, z0: float, z1: float, outer: bool) -> List[Tri]:
    p = G.orient(poly, ccw=outer)
    tris: List[Tri] = []
    n = len(p)
    for i in range(n):
        (x0, y0), (x1, y1) = p[i], p[(i + 1) % n]
        a, b, c, d = (x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)
        tris.append((a, b, c))
        tris.append((a, c, d))
    return tris


def build_mesh(doc: Document):
    """Devuelve dict con listas de triángulos por grupo: panel, pocket."""
    ev = doc.evaluator()
    _W, _H, T, _r = doc.panel_dims(ev)
    outline = G.orient(doc.panel_outline(ev), True)
    cuts: List[G.Poly] = []
    pockets: List[Tuple[G.Poly, float]] = []
    back: List[Tuple[G.Poly, float]] = []
    for e, role, pr in doc.geometry(ev):
        if role == "cut":
            for p in _closed_polys(pr):
                if G.poly_contains_poly(outline, p):
                    cuts.append(p)
        elif role == "pocket":
            depth = min(max(0.05, e.v(ev, "depth", 0.8) if "depth" in e.p else 0.5), T * 0.95)
            for p in _closed_polys(pr):
                if G.poly_contains_poly(outline, p):
                    pockets.append((p, depth))
        elif role == "pocket_back":
            depth = min(e.blind_depth(ev, T) if hasattr(e, "blind_depth") else T * 0.5, T * 0.95)
            back += [(p, depth) for p in _closed_polys(pr) if G.poly_contains_poly(outline, p)]
    panel: List[Tri] = []
    pocket_tris: List[Tri] = []
    panel += _cap([outline] + cuts + [p for p, _d in pockets], T, up=True)
    panel += _cap([outline] + cuts + [p for p, _d in back], 0.0, up=False)
    for p, d in back:
        pocket_tris += _cap([p], d, up=False)
        pocket_tris += _walls(p, 0.0, d, outer=False)
    panel += _walls(outline, 0.0, T, outer=True)
    for c in cuts:
        panel += _walls(c, 0.0, T, outer=False)
    for p, d in pockets:
        inner = [c for c in cuts if all(G.point_in_poly(q, p) for q in c)]
        pocket_tris += _cap([p] + inner, T - d, up=True)
        pocket_tris += _walls(p, T - d, T, outer=False)
    return {"panel": panel, "pocket": pocket_tris, "thickness": T}


def _normal(t: Tri):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / L, ny / L, nz / L


def export_stl(doc: Document, path: str) -> int:
    m = build_mesh(doc)
    tris = m["panel"] + m["pocket"]
    with open(path, "wb") as f:
        hdr = b"Electronic Front Panel Designer - STL (mm)"
        f.write(hdr.ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for t in tris:
            f.write(struct.pack("<3f", *_normal(t)))
            for v in t:
                f.write(struct.pack("<3f", *v))
            f.write(b"\x00\x00")
    return len(tris)


def build_view_model(doc: Document):
    """Modelo ligero para el visor 3D: tapas como conjuntos de polígonos (relleno
    par-impar), paredes como cuadriláteros y suelos de rebaje."""
    ev = doc.evaluator()
    _W, _H, T, _r = doc.panel_dims(ev)
    outline = G.orient(doc.panel_outline(ev), True)
    cuts, pockets, back = [], [], []
    for e, role, pr in doc.geometry(ev):
        if role == "cut":
            cuts += [p for p in _closed_polys(pr) if G.poly_contains_poly(outline, p)]
        elif role == "pocket":
            depth = min(max(0.05, e.v(ev, "depth", 0.8) if "depth" in e.p else 0.5), T * 0.95)
            pockets += [(p, depth) for p in _closed_polys(pr) if G.poly_contains_poly(outline, p)]
        elif role == "pocket_back":
            depth = min(e.blind_depth(ev, T) if hasattr(e, "blind_depth") else T * 0.5, T * 0.95)
            back += [(p, depth) for p in _closed_polys(pr) if G.poly_contains_poly(outline, p)]
    walls = []

    def add_walls(poly, z0, z1, outer, group):
        p = G.orient(poly, ccw=outer)
        n = len(p)
        for i in range(n):
            (x0, y0), (x1, y1) = p[i], p[(i + 1) % n]
            walls.append(((x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1), group))
    add_walls(outline, 0.0, T, True, "panel")
    for c in cuts:
        add_walls(c, 0.0, T, False, "panel")
    floors = []
    for p, d in pockets:
        add_walls(p, T - d, T, False, "pocket")
        inner = [c for c in cuts if all(G.point_in_poly(q, p) for q in c)]
        floors.append(([p] + inner, T - d))
    floors_back = []
    for p, d in back:
        add_walls(p, 0.0, d, False, "pocket")
        floors_back.append(([p], d))
    return {"top": [outline] + cuts + [p for p, _d in pockets], "bottom": [outline] + cuts + [p for p, _d in back],
            "walls": walls, "floors": floors, "floors_back": floors_back, "T": T}
