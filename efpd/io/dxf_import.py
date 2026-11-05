"""Importación DXF (ASCII) sin dependencias.

Soporta LINE, ARC, CIRCLE, LWPOLYLINE (con abombamientos), POLYLINE/VERTEX,
ELLIPSE, SPLINE, SOLID y bloques INSERT (con escala, rotación y traslación).
Los segmentos sueltos se encadenan en contornos cerrados cuando sus extremos
coinciden (tolerancia 0.01 mm).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from ..core import geometry as G
from ..core.entities import PathEntity

UNIT_SCALE = {0: 1.0, 1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0000254, 9: 0.0254}


def _pairs(text: str):
    lines = text.splitlines()
    for i in range(0, len(lines) - 1, 2):
        try:
            code = int(lines[i].strip())
        except ValueError:
            continue
        yield code, lines[i + 1].strip()


def _bulge_pts(p0, p1, bulge):
    if abs(bulge) < 1e-9:
        return [p1]
    (x0, y0), (x1, y1) = p0, p1
    c = G.dist(p0, p1)
    if c < 1e-12:
        return [p1]
    theta = 4 * math.atan(bulge)
    r = c / (2 * math.sin(theta / 2))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    h = r * math.cos(theta / 2)
    ux, uy = (x1 - x0) / c, (y1 - y0) / c
    cx, cy = mx - uy * h, my + ux * h
    a0 = math.atan2(y0 - cy, x0 - cx)
    pts = G.arc_pts(cx, cy, abs(r), a0, a0 + theta)
    return pts[1:]


def _deboor(ctrl, knots, degree, n=64):
    if len(ctrl) <= degree or len(knots) < len(ctrl) + degree + 1:
        return ctrl
    t0, t1 = knots[degree], knots[len(ctrl)]
    out = []
    for s in range(n + 1):
        t = t0 + (t1 - t0) * s / n
        k = degree
        for i in range(degree, len(ctrl)):
            if knots[i] <= t < knots[i + 1]:
                k = i
        if t >= t1:
            k = len(ctrl) - 1
        d = [list(ctrl[j + k - degree]) for j in range(degree + 1)]
        for r in range(1, degree + 1):
            for j in range(degree, r - 1, -1):
                i = j + k - degree
                den = knots[i + 1 + degree - r] - knots[i]
                a = 0.0 if den == 0 else (t - knots[i]) / den
                d[j] = [(1 - a) * d[j - 1][0] + a * d[j][0], (1 - a) * d[j - 1][1] + a * d[j][1]]
        out.append((d[degree][0], d[degree][1]))
    return out


def _parse_entities(pairs, start, stop_names):
    """Lee entidades hasta encontrar (0, ENDSEC/ENDBLK). Devuelve lista de dicts y índice."""
    ents = []
    cur = None
    i = start
    while i < len(pairs):
        code, val = pairs[i]
        if code == 0:
            if val in stop_names:
                if cur:
                    ents.append(cur)
                return ents, i
            if cur:
                ents.append(cur)
            cur = {"type": val, "g": []}
        elif cur is not None:
            cur["g"].append((code, val))
        i += 1
    if cur:
        ents.append(cur)
    return ents, i


def _f(g, code, default=0.0):
    for c, v in g:
        if c == code:
            try:
                return float(v)
            except ValueError:
                return default
    return default


def _s(g, code, default=""):
    for c, v in g:
        if c == code:
            return v
    return default


def _geom(ents, blocks, depth=0):
    """Convierte entidades DXF a (cerrados, abiertos) en coordenadas del dibujo."""
    closed: List[List[Tuple[float, float]]] = []
    opened: List[List[Tuple[float, float]]] = []
    i = 0
    while i < len(ents):
        e = ents[i]
        t, g = e["type"], e["g"]
        if t == "LINE":
            opened.append([(_f(g, 10), _f(g, 20)), (_f(g, 11), _f(g, 21))])
        elif t == "CIRCLE":
            closed.append(G.circle_poly(_f(g, 10), _f(g, 20), _f(g, 40)))
        elif t == "ARC":
            a0, a1 = math.radians(_f(g, 50)), math.radians(_f(g, 51))
            if a1 <= a0:
                a1 += 2 * math.pi
            opened.append(G.arc_pts(_f(g, 10), _f(g, 20), _f(g, 40), a0, a1))
        elif t == "ELLIPSE":
            cx, cy, mx, my = _f(g, 10), _f(g, 20), _f(g, 11), _f(g, 21)
            ratio, s0, s1 = _f(g, 40, 1.0), _f(g, 41, 0.0), _f(g, 42, 2 * math.pi)
            a = math.hypot(mx, my)
            rot = math.atan2(my, mx)
            if s1 <= s0:
                s1 += 2 * math.pi
            n = G.segments_for(a, s1 - s0)
            pts = []
            for k in range(n + 1):
                tt = s0 + (s1 - s0) * k / n
                x, y = a * math.cos(tt), a * ratio * math.sin(tt)
                pts.append((cx + x * math.cos(rot) - y * math.sin(rot), cy + x * math.sin(rot) + y * math.cos(rot)))
            if abs(s1 - s0 - 2 * math.pi) < 1e-6:
                closed.append(G.dedupe(pts))
            else:
                opened.append(pts)
        elif t == "LWPOLYLINE":
            flag = int(_f(g, 70))
            verts = []
            for c, v in g:
                if c == 10:
                    verts.append([float(v), 0.0, 0.0])
                elif c == 20 and verts:
                    verts[-1][1] = float(v)
                elif c == 42 and verts:
                    verts[-1][2] = float(v)
            pts = _poly_with_bulges(verts, flag & 1)
            (closed if flag & 1 else opened).append(pts)
        elif t == "POLYLINE":
            flag = int(_f(g, 70))
            verts = []
            i += 1
            while i < len(ents) and ents[i]["type"] == "VERTEX":
                vg = ents[i]["g"]
                verts.append([_f(vg, 10), _f(vg, 20), _f(vg, 42)])
                i += 1
            pts = _poly_with_bulges(verts, flag & 1)
            if pts:
                (closed if flag & 1 else opened).append(pts)
            continue  # SEQEND se ignora en la siguiente vuelta
        elif t == "SPLINE":
            degree = int(_f(g, 71, 3))
            knots = [float(v) for c, v in g if c == 40]
            ctrl, fit = [], []
            for c, v in g:
                if c == 10:
                    ctrl.append([float(v), 0.0])
                elif c == 20 and ctrl:
                    ctrl[-1][1] = float(v)
                elif c == 11:
                    fit.append([float(v), 0.0])
                elif c == 21 and fit:
                    fit[-1][1] = float(v)
            pts = _deboor([tuple(p) for p in ctrl], knots, degree) if ctrl else [tuple(p) for p in fit]
            if int(_f(g, 70)) & 1:
                closed.append(G.dedupe(pts))
            else:
                opened.append(pts)
        elif t == "SOLID":
            pts = [(_f(g, 10), _f(g, 20)), (_f(g, 11), _f(g, 21)), (_f(g, 13), _f(g, 23)), (_f(g, 12), _f(g, 22))]
            closed.append(G.dedupe(pts))
        elif t == "INSERT" and depth < 8:
            name = _s(g, 2)
            if name in blocks:
                bx, by = blocks[name]["base"]
                sx, sy = _f(g, 41, 1.0), _f(g, 42, 1.0)
                rot = _f(g, 50)
                ix, iy = _f(g, 10), _f(g, 20)
                c2, o2 = _geom(blocks[name]["ents"], blocks, depth + 1)
                tr = lambda P: G.transform_pts([(x - bx, y - by) for x, y in P], ix, iy, rot, sx, sy)  # noqa: E731
                closed += [tr(p) for p in c2]
                opened += [tr(p) for p in o2]
        i += 1
    return closed, opened


def _poly_with_bulges(verts, is_closed):
    if not verts:
        return []
    pts = [(verts[0][0], verts[0][1])]
    n = len(verts)
    last = n if is_closed else n - 1
    for k in range(last):
        p0 = (verts[k][0], verts[k][1])
        p1 = (verts[(k + 1) % n][0], verts[(k + 1) % n][1])
        pts += _bulge_pts(p0, p1, verts[k][2])
    return G.dedupe(pts) if is_closed else pts


def chain(segments: List[List[Tuple[float, float]]], tol: float = 0.01):
    """Une polilíneas abiertas por sus extremos. Devuelve (cerradas, abiertas)."""
    segs = [list(s) for s in segments if len(s) >= 2]
    closed, opened = [], []
    while segs:
        cur = segs.pop()
        changed = True
        while changed:
            changed = False
            for k, s in enumerate(segs):
                if G.dist(cur[-1], s[0]) <= tol:
                    cur += s[1:]
                elif G.dist(cur[-1], s[-1]) <= tol:
                    cur += list(reversed(s))[1:]
                elif G.dist(cur[0], s[-1]) <= tol:
                    cur = s[:-1] + cur
                elif G.dist(cur[0], s[0]) <= tol:
                    cur = list(reversed(s))[:-1] + cur
                else:
                    continue
                segs.pop(k)
                changed = True
                break
        if len(cur) > 2 and G.dist(cur[0], cur[-1]) <= tol:
            closed.append(G.dedupe(cur))
        else:
            opened.append(cur)
    return closed, opened


def read_dxf(path: str):
    """Devuelve (lista de {'pts','closed'}, escala aplicada)."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith(b"AutoCAD Binary DXF"):
        raise ValueError("DXF binario no soportado: guárdelo como DXF ASCII")
    text = raw.decode("utf-8", errors="replace") if b"$DWGCODEPAGE" not in raw else raw.decode("cp1252", "replace")
    pairs = list(_pairs(text))
    units = 4
    for k, (c, v) in enumerate(pairs):
        if c == 9 and v == "$INSUNITS" and k + 1 < len(pairs):
            try:
                units = int(pairs[k + 1][1])
            except ValueError:
                pass
            break
    scale = UNIT_SCALE.get(units, 1.0) or 1.0
    blocks: Dict[str, dict] = {}
    ents = []
    i = 0
    while i < len(pairs):
        c, v = pairs[i]
        if c == 0 and v == "SECTION" and i + 1 < len(pairs):
            name = pairs[i + 1][1]
            if name == "ENTITIES":
                ents, i = _parse_entities(pairs, i + 2, ("ENDSEC",))
            elif name == "BLOCKS":
                j = i + 2
                while j < len(pairs) and not (pairs[j][0] == 0 and pairs[j][1] == "ENDSEC"):
                    if pairs[j][0] == 0 and pairs[j][1] == "BLOCK":
                        hdr, j2 = _parse_entities(pairs, j, ("ENDBLK", "ENDSEC"))
                        if hdr:
                            g = hdr[0]["g"]
                            bname = _s(g, 2)
                            blocks[bname] = {"base": (_f(g, 10), _f(g, 20)), "ents": hdr[1:]}
                        j = j2 + 1
                    else:
                        j += 1
                i = j
        i += 1
    closed, opened = _geom(ents, blocks)
    c2, o2 = chain(opened)
    closed += c2
    paths = [{"pts": [(x * scale, y * scale) for x, y in p], "closed": True} for p in closed if len(p) >= 3]
    paths += [{"pts": [(x * scale, y * scale) for x, y in p], "closed": False} for p in o2 if len(p) >= 2]
    return paths, scale


def paths_to_entity(paths, source: str, keep_position: bool = False, center=(0.0, 0.0)) -> PathEntity:
    """Crea una PathEntity centrada (o en su posición original)."""
    allp = [pt for p in paths for pt in p["pts"]]
    b = G.bbox(allp)
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    local = [{"pts": [[round(x - cx, 5), round(y - cy, 5)] for x, y in p["pts"]], "closed": p["closed"]}
             for p in paths]
    x, y = (cx, cy) if keep_position else center
    import os
    return PathEntity(x=round(x, 4), y=round(y, 4), paths=local, source=os.path.basename(source),
                      name=os.path.splitext(os.path.basename(source))[0])


def import_dxf(path: str, keep_position: bool = False, center=(0.0, 0.0)) -> PathEntity:
    paths, _ = read_dxf(path)
    if not paths:
        raise ValueError("El DXF no contiene geometría compatible")
    return paths_to_entity(paths, path, keep_position, center)
