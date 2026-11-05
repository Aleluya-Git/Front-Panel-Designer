"""Importación SVG (logotipos, contornos) sin dependencias.

Soporta path (M L H V C S Q T A Z, absolutos y relativos), rect (con rx/ry),
circle, ellipse, line, polyline, polygon, grupos anidados y atributos
transform (matrix, translate, scale, rotate, skewX, skewY). Las curvas se
aproximan con tolerancia ~0.05 mm. Las unidades se convierten a milímetros a
partir de width/height/viewBox (por defecto 96 ppp).
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from typing import List, Tuple

from ..core import geometry as G
from .dxf_import import paths_to_entity

Mat = Tuple[float, float, float, float, float, float]  # a b c d e f
IDENT: Mat = (1, 0, 0, 1, 0, 0)
UNITS = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6, "px": 25.4 / 96, "": 25.4 / 96}


def mmul(m: Mat, n: Mat) -> Mat:
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f)


def apply(m: Mat, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def parse_transform(s: str) -> Mat:
    m = IDENT
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(x) for x in re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", args)]
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            r = (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0, 0)
            if len(v) == 3:
                t = mmul(mmul((1, 0, 0, 1, v[1], v[2]), r), (1, 0, 0, 1, -v[1], -v[2]))
            else:
                t = r
        elif name == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        m = mmul(m, t)
    return m


def _len(s: str, ref: float = 0.0) -> Tuple[float, str]:
    m = re.match(r"\s*([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)\s*(mm|cm|in|pt|pc|px|%)?", s or "")
    if not m:
        return 0.0, ""
    v, u = float(m.group(1)), m.group(2) or ""
    if u == "%":
        return v * ref / 100.0, "px"
    return v, u


_NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


class _Tok:
    def __init__(self, d: str):
        self.s = d
        self.i = 0

    def skip(self):
        while self.i < len(self.s) and self.s[self.i] in " \t\r\n,":
            self.i += 1

    def cmd(self):
        self.skip()
        if self.i < len(self.s) and self.s[self.i].isalpha():
            self.i += 1
            return self.s[self.i - 1]
        return None

    def has_num(self):
        self.skip()
        return self.i < len(self.s) and (self.s[self.i].isdigit() or self.s[self.i] in "+-.")

    def num(self):
        self.skip()
        m = _NUM.match(self.s, self.i)
        if not m:
            raise ValueError(f"Número esperado en la posición {self.i}")
        self.i = m.end()
        return float(m.group(0))

    def flag(self):
        self.skip()
        c = self.s[self.i]
        self.i += 1
        return c == "1"


def _bez(p0, p1, p2, p3=None, n=None):
    if p3 is None:  # cuadrática → cúbica
        p1, p2, p3 = ((p0[0] + 2 * p1[0]) / 3, (p0[1] + 2 * p1[1]) / 3), \
                     ((p2[0] + 2 * p1[0]) / 3, (p2[1] + 2 * p1[1]) / 3), p2
    L = G.dist(p0, p1) + G.dist(p1, p2) + G.dist(p2, p3)
    n = n or max(4, min(64, int(L / 0.6) + 1))
    out = []
    for k in range(1, n + 1):
        t = k / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def _arc(p0, rx, ry, phi, large, sweep, p1):
    if rx == 0 or ry == 0:
        return [p1]
    rx, ry = abs(rx), abs(ry)
    cp, sp = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        co = -co
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    cx = cp * cx1 - sp * cy1 + (p0[0] + p1[0]) / 2
    cy = sp * cx1 + cp * cy1 + (p0[1] + p1[1]) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a
    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(4, int(abs(dt) / (2 * math.pi) * 64) + 1)
    out = []
    for k in range(1, n + 1):
        t = t1 + dt * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cp * x - sp * y + cx, sp * x + cp * y + cy))
    return out


def parse_path(d: str) -> List[Tuple[List[Tuple[float, float]], bool]]:
    tk = _Tok(d)
    subs = []
    cur: List[Tuple[float, float]] = []
    pos = (0.0, 0.0)
    start = pos
    last_c = None
    last_q = None
    cmd = None
    while True:
        c = tk.cmd()
        if c is None:
            if cmd is None or not tk.has_num():
                break
            c = {"M": "L", "m": "l"}.get(cmd, cmd)
        cmd = c
        rel = c.islower()
        C_ = c.upper()
        ox, oy = pos if rel else (0.0, 0.0)
        if C_ == "Z":
            if cur:
                subs.append((cur, True))
            cur = []
            pos = start
            last_c = last_q = None
            continue
        if C_ == "M":
            if cur:
                subs.append((cur, False))
            pos = (ox + tk.num(), oy + tk.num())
            start = pos
            cur = [pos]
            last_c = last_q = None
            continue
        if not cur:
            cur = [pos]
        if C_ == "L":
            pos = (ox + tk.num(), oy + tk.num())
            cur.append(pos)
            last_c = last_q = None
        elif C_ == "H":
            pos = ((pos[0] if rel else 0.0) + tk.num(), pos[1])
            cur.append(pos)
            last_c = last_q = None
        elif C_ == "V":
            pos = (pos[0], (pos[1] if rel else 0.0) + tk.num())
            cur.append(pos)
            last_c = last_q = None
        elif C_ == "C":
            p1 = (ox + tk.num(), oy + tk.num())
            p2 = (ox + tk.num(), oy + tk.num())
            p3 = (ox + tk.num(), oy + tk.num())
            cur += _bez(pos, p1, p2, p3)
            last_c, last_q, pos = p2, None, p3
        elif C_ == "S":
            p1 = (2 * pos[0] - last_c[0], 2 * pos[1] - last_c[1]) if last_c else pos
            p2 = (ox + tk.num(), oy + tk.num())
            p3 = (ox + tk.num(), oy + tk.num())
            cur += _bez(pos, p1, p2, p3)
            last_c, last_q, pos = p2, None, p3
        elif C_ == "Q":
            p1 = (ox + tk.num(), oy + tk.num())
            p2 = (ox + tk.num(), oy + tk.num())
            cur += _bez(pos, p1, p2)
            last_q, last_c, pos = p1, None, p2
        elif C_ == "T":
            p1 = (2 * pos[0] - last_q[0], 2 * pos[1] - last_q[1]) if last_q else pos
            p2 = (ox + tk.num(), oy + tk.num())
            cur += _bez(pos, p1, p2)
            last_q, last_c, pos = p1, None, p2
        elif C_ == "A":
            rx, ry, phi = tk.num(), tk.num(), tk.num()
            large, sweep = tk.flag(), tk.flag()
            p1 = (ox + tk.num(), oy + tk.num())
            cur += _arc(pos, rx, ry, phi, large, sweep, p1)
            pos = p1
            last_c = last_q = None
        else:
            raise ValueError(f"Comando de trazado no soportado: {c}")
    if len(cur) > 1:
        subs.append((cur, False))
    return subs


def _shape(el, tag):
    g = el.get
    num = lambda k, d=0.0: _len(g(k, str(d)))[0]  # noqa: E731
    if tag == "path":
        return parse_path(g("d", ""))
    if tag == "rect":
        x, y, w, h = num("x"), num("y"), num("width"), num("height")
        rx = num("rx", 0) or num("ry", 0)
        pts = G.transform_pts(G.rect_poly(w, h, rx), x + w / 2, y + h / 2)
        return [(pts, True)]
    if tag == "circle":
        return [(G.circle_poly(num("cx"), num("cy"), num("r"), 0.02), True)]
    if tag == "ellipse":
        return [(G.ellipse_poly(num("cx"), num("cy"), num("rx"), num("ry")), True)]
    if tag == "line":
        return [([(num("x1"), num("y1")), (num("x2"), num("y2"))], False)]
    if tag in ("polyline", "polygon"):
        v = [float(x) for x in _NUM.findall(g("points", ""))]
        pts = list(zip(v[0::2], v[1::2]))
        return [(pts, tag == "polygon")]
    return []


def read_svg(path: str):
    tree = ET.parse(path)
    root = tree.getroot()
    vb = [float(x) for x in _NUM.findall(root.get("viewBox", ""))]
    wv, wu = _len(root.get("width", ""))
    hv, hu = _len(root.get("height", ""))
    if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
        sx = (wv * UNITS.get(wu, 25.4 / 96)) / vb[2] if wv else 25.4 / 96
        sy = (hv * UNITS.get(hu, 25.4 / 96)) / vb[3] if hv else sx
        base = (sx, 0, 0, sy, -vb[0] * sx, -vb[1] * sy)
    else:
        s = 25.4 / 96
        base = (s, 0, 0, s, 0, 0)
    paths = []

    def walk(el, m):
        tag = el.tag.split("}")[-1]
        if tag in ("defs", "clipPath", "mask", "symbol", "metadata", "title", "desc", "style", "marker"):
            return
        st = (el.get("style") or "") + ";" + (el.get("display") or "")
        if "display:none" in st.replace(" ", "") or el.get("display") == "none":
            return
        m2 = mmul(m, parse_transform(el.get("transform", "")))
        for pts, closed in _shape(el, tag):
            tp = [apply(m2, p) for p in pts]
            tp = [(x, -y) for x, y in tp]  # SVG Y hacia abajo → panel Y hacia arriba
            if closed:
                tp = G.dedupe(tp)
            if len(tp) >= 2:
                paths.append({"pts": tp, "closed": closed and len(tp) >= 3})
        for ch in el:
            walk(ch, m2)

    walk(root, base)
    return paths


def import_svg(path: str, keep_position: bool = False, center=(0.0, 0.0)):
    paths = read_svg(path)
    if not paths:
        raise ValueError("El SVG no contiene geometría compatible")
    return paths_to_entity(paths, path, keep_position, center)
