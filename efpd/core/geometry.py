"""Geometría 2D pura (sin dependencias).

Convenciones:
  * Unidades: milímetros. Origen del panel abajo-izquierda, Y hacia arriba.
  * Un polígono es una lista de tuplas (x, y) SIN repetir el primer punto.
  * Primitivas ("prims") que intercambian las entidades con exportadores:
        {"t": "circle", "c": (x, y), "r": r}
        {"t": "poly", "pts": [(x, y), ...], "closed": bool}
        {"t": "text", "pos": (x, y), "h": alto, "text": str, "angle": grados}
"""
from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

Pt = Tuple[float, float]
Poly = List[Pt]

CHORD_TOL = 0.02  # mm, error máximo de cuerda al aproximar arcos


# ----------------------------------------------------------------- básicos
def dist(a: Pt, b: Pt) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def rotate_pt(p: Pt, deg: float, origin: Pt = (0.0, 0.0)) -> Pt:
    if not deg:
        return p
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y = p[0] - origin[0], p[1] - origin[1]
    return (origin[0] + x * c - y * s, origin[1] + x * s + y * c)


def transform_pts(pts: Iterable[Pt], dx: float, dy: float, deg: float = 0.0,
                  sx: float = 1.0, sy: float = 1.0) -> Poly:
    """Escala, rota (alrededor del origen local) y traslada."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    out = []
    for x, y in pts:
        x *= sx
        y *= sy
        out.append((dx + x * c - y * s, dy + x * s + y * c))
    return out


def segments_for(r: float, sweep: float = 2 * math.pi, tol: float = CHORD_TOL) -> int:
    if r <= tol:
        return 8
    step = 2 * math.acos(max(-1.0, min(1.0, 1 - tol / r)))
    n = int(math.ceil(abs(sweep) / max(step, 1e-6)))
    full = abs(sweep) / (2 * math.pi)
    return max(int(8 * full) or 2, min(n, int(256 * full) + 2))


def arc_pts(cx: float, cy: float, r: float, a0: float, a1: float,
            tol: float = CHORD_TOL, include_end: bool = True) -> Poly:
    """Puntos de un arco de a0 a a1 (radianes, sentido según signo)."""
    n = segments_for(r, a1 - a0, tol)
    rng = range(n + 1) if include_end else range(n)
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n),
             cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in rng]


def circle_poly(cx: float, cy: float, r: float, tol: float = CHORD_TOL) -> Poly:
    return arc_pts(cx, cy, r, 0.0, 2 * math.pi, tol, include_end=False)


def ellipse_poly(cx, cy, rx, ry, deg=0.0, tol=CHORD_TOL) -> Poly:
    n = segments_for(max(rx, ry), 2 * math.pi, tol)
    pts = [(rx * math.cos(2 * math.pi * i / n), ry * math.sin(2 * math.pi * i / n))
           for i in range(n)]
    return transform_pts(pts, cx, cy, deg)


def rect_poly(w: float, h: float, r: float = 0.0) -> Poly:
    """Rectángulo centrado en el origen, con radio de esquina opcional (CCW)."""
    w2, h2 = w / 2.0, h / 2.0
    r = max(0.0, min(r, w2, h2))
    if r <= 1e-9:
        return [(-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)]
    pts: Poly = []
    for cx, cy, a0 in ((w2 - r, -h2 + r, -90), (w2 - r, h2 - r, 0),
                       (-w2 + r, h2 - r, 90), (-w2 + r, -h2 + r, 180)):
        pts += arc_pts(cx, cy, r, math.radians(a0), math.radians(a0 + 90))
    return dedupe(pts)


def obround_poly(length: float, width: float) -> Poly:
    """Ranura ovalada (oblonga) horizontal centrada: length total, width = diámetro."""
    r = width / 2.0
    length = max(length, width)
    a = length / 2.0 - r
    pts = arc_pts(a, 0, r, -math.pi / 2, math.pi / 2)
    pts += arc_pts(-a, 0, r, math.pi / 2, 3 * math.pi / 2)
    return dedupe(pts)


def dhole_poly(d: float, flat: float) -> Poly:
    """Agujero en D: círculo de diámetro d con un plano a distancia 'flat' del centro (eje +X)."""
    r = d / 2.0
    flat = max(-r * 0.99, min(flat, r * 0.999))
    a = math.acos(flat / r)
    return dedupe(arc_pts(0, 0, r, a, 2 * math.pi - a))


def regular_poly(n: int, d: float) -> Poly:
    n = max(3, int(n))
    r = d / 2.0
    return [(r * math.cos(math.pi / 2 + 2 * math.pi * i / n),
             r * math.sin(math.pi / 2 + 2 * math.pi * i / n)) for i in range(n)]


def dedupe(pts: Sequence[Pt], eps: float = 1e-9) -> Poly:
    out: Poly = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append((p[0], p[1]))
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= eps and abs(out[0][1] - out[-1][1]) <= eps:
        out.pop()
    return out


# ------------------------------------------------------------ polígonos
def area(poly: Sequence[Pt]) -> float:
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def orient(poly: Sequence[Pt], ccw: bool = True) -> Poly:
    p = list(poly)
    if (area(p) > 0) != ccw:
        p.reverse()
    return p


def bbox(pts: Iterable[Pt]) -> Tuple[float, float, float, float]:
    xs, ys = [], []
    for x, y in pts:
        xs.append(x)
        ys.append(y)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def bbox_union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def point_in_poly(p: Pt, poly: Sequence[Pt]) -> bool:
    x, y = p
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xc = xi + (y - yi) * (xj - xi) / (yj - yi)
            if x < xc:
                inside = not inside
        j = i
    return inside


def seg_point_dist(p: Pt, a: Pt, b: Pt) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    if L <= 1e-18:
        return dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _ccw(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segs_intersect(a, b, c, d) -> bool:
    d1, d2 = _ccw(c, d, a), _ccw(c, d, b)
    d3, d4 = _ccw(a, b, c), _ccw(a, b, d)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def seg_seg_dist(a, b, c, d) -> float:
    if segs_intersect(a, b, c, d):
        return 0.0
    return min(seg_point_dist(a, c, d), seg_point_dist(b, c, d),
               seg_point_dist(c, a, b), seg_point_dist(d, a, b))


def poly_distance(A: Sequence[Pt], B: Sequence[Pt], closed_a=True, closed_b=True,
                  boundary_only: bool = False) -> float:
    """Distancia mínima entre contornos; 0 si se solapan (uno dentro de otro incluido).

    Con ``boundary_only`` se mide sólo entre bordes (p. ej. hueco ↔ borde del panel)."""
    if not boundary_only:
        if closed_b and A and point_in_poly(A[0], B):
            return 0.0
        if closed_a and B and point_in_poly(B[0], A):
            return 0.0
    na, nb = len(A), len(B)
    ea = na if closed_a else na - 1
    eb = nb if closed_b else nb - 1
    best = float("inf")
    for i in range(ea):
        a0, a1 = A[i], A[(i + 1) % na]
        for j in range(eb):
            dd = seg_seg_dist(a0, a1, B[j], B[(j + 1) % nb])
            if dd < best:
                best = dd
                if best == 0.0:
                    return 0.0
    return best


def poly_contains_poly(outer: Sequence[Pt], inner: Sequence[Pt]) -> bool:
    """True si 'inner' queda completamente dentro de 'outer' sin cruzar bordes."""
    if not all(point_in_poly(p, outer) for p in inner):
        return False
    n, m = len(outer), len(inner)
    for i in range(n):
        for j in range(m):
            if segs_intersect(outer[i], outer[(i + 1) % n], inner[j], inner[(j + 1) % m]):
                return False
    return True


def offset_poly(poly: Sequence[Pt], d: float, miter_limit: float = 4.0) -> Poly:
    """Desplazamiento simple con inglete. d>0 hacia fuera (para polígono CCW).

    Suficiente para contornos de mecanizado básicos (convexos o ligeramente
    cóncavos). Devuelve [] si el contorno colapsa.
    """
    p = orient(dedupe(poly), True)
    n = len(p)
    if n < 3:
        return []
    out = []
    for i in range(n):
        p0, p1, p2 = p[i - 1], p[i], p[(i + 1) % n]
        e0 = (p1[0] - p0[0], p1[1] - p0[1])
        e1 = (p2[0] - p1[0], p2[1] - p1[1])
        l0, l1 = math.hypot(*e0) or 1e-12, math.hypot(*e1) or 1e-12
        n0 = (e0[1] / l0, -e0[0] / l0)  # normal exterior (derecha) para CCW
        n1 = (e1[1] / l1, -e1[0] / l1)
        bx, by = n0[0] + n1[0], n0[1] + n1[1]
        bl = math.hypot(bx, by)
        if bl < 1e-9:
            out.append((p1[0] + n0[0] * d, p1[1] + n0[1] * d))
            continue
        bx, by = bx / bl, by / bl
        cosh = bx * n0[0] + by * n0[1]
        k = d / max(cosh, 1.0 / miter_limit)
        out.append((p1[0] + bx * k, p1[1] + by * k))
    a0, a1 = area(p), area(out)
    if a1 <= 1e-9 or (d < 0 and a1 > a0):
        return []
    return out


# ------------------------------------------------------- primitivas
def prim_polys(prim: dict, tol: float = CHORD_TOL) -> List[Tuple[Poly, bool]]:
    """Convierte una primitiva a [(polilínea, cerrada)]."""
    t = prim["t"]
    if t == "circle":
        return [(circle_poly(prim["c"][0], prim["c"][1], prim["r"], tol), True)]
    if t == "poly":
        return [(list(prim["pts"]), bool(prim.get("closed", True)))]
    return []


def prim_bbox(prim: dict):
    t = prim["t"]
    if t == "circle":
        (x, y), r = prim["c"], prim["r"]
        return (x - r, y - r, x + r, y + r)
    if t == "poly":
        return bbox(prim["pts"])
    if t == "text":
        x, y = prim["pos"]
        w = len(prim["text"]) * prim["h"] * 0.6
        return (x - w / 2, y, x + w / 2, y + prim["h"])
    return None


def prim_point_dist(prim: dict, p: Pt) -> float:
    """Distancia de un punto a la primitiva (0 si está dentro de una figura cerrada)."""
    t = prim["t"]
    if t == "circle":
        d = dist(p, prim["c"]) - prim["r"]
        return max(0.0, d)
    if t == "poly":
        pts = prim["pts"]
        closed = prim.get("closed", True)
        if closed and len(pts) > 2 and point_in_poly(p, pts):
            return 0.0
        n = len(pts)
        m = n if closed else n - 1
        if n == 1:
            return dist(p, pts[0])
        return min(seg_point_dist(p, pts[i], pts[(i + 1) % n]) for i in range(m))
    if t == "text":
        b = prim_bbox(prim)
        if b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]:
            return 0.0
        return 1e9
    return 1e9


# ---------------------------------------------- descomposición en trapecios
def trapezoids(polys: Sequence[Sequence[Pt]]):
    """Relleno par-impar de un conjunto de polígonos mediante barrido en Y.

    Devuelve lista de trapecios (y0, y1, xl0, xl1, xr0, xr1): lado izquierdo de
    (xl0,y0) a (xl1,y1) y derecho de (xr0,y0) a (xr1,y1). Robusto y sin
    dependencias; se usa para tapas del modelo 3D y STL.
    """
    edges = []
    ys = set()
    for poly in polys:
        n = len(poly)
        for i in range(n):
            (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
            ys.add(y0)
            if abs(y1 - y0) < 1e-12:
                continue
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            edges.append((y0, y1, x0, x1))
    if not edges:
        return []
    edges.sort()
    ylist = sorted(ys)
    # fusionar ys casi iguales
    yu = [ylist[0]]
    for y in ylist[1:]:
        if y - yu[-1] > 1e-9:
            yu.append(y)
    out = []
    active = []
    k = 0
    ne = len(edges)
    for bi in range(len(yu) - 1):
        ya, yb = yu[bi], yu[bi + 1]
        ym = (ya + yb) / 2.0
        while k < ne and edges[k][0] <= ym:
            active.append(edges[k])
            k += 1
        active = [e for e in active if e[1] > ym]
        xs = []
        for (ey0, ey1, ex0, ex1) in active:
            if ey0 <= ym <= ey1:
                f = (ex1 - ex0) / (ey1 - ey0)
                xs.append((ex0 + (ym - ey0) * f, ex0 + (ya - ey0) * f, ex0 + (yb - ey0) * f))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            L, R = xs[j], xs[j + 1]
            out.append((ya, yb, L[1], L[2], R[1], R[2]))
    return out


def arc_slot_poly(r: float, w: float, a0_deg: float, a1_deg: float, tol: float = CHORD_TOL) -> Poly:
    """Ranura curvada: arco de radio medio r y ancho w, de a0 a a1 (grados, CCW), extremos redondeados."""
    a0, a1 = math.radians(a0_deg), math.radians(a1_deg)
    if a1 < a0:
        a0, a1 = a1, a0
    h = w / 2.0
    ro, ri = r + h, max(1e-3, r - h)
    pts = arc_pts(0, 0, ro, a0, a1, tol)
    e1 = (r * math.cos(a1), r * math.sin(a1))
    pts += arc_pts(e1[0], e1[1], h, a1, a1 + math.pi, tol)[1:]
    pts += arc_pts(0, 0, ri, a1, a0, tol)[1:]
    e0 = (r * math.cos(a0), r * math.sin(a0))
    pts += arc_pts(e0[0], e0[1], h, a0 + math.pi, a0 + 2 * math.pi, tol)[1:]
    return dedupe(pts)
