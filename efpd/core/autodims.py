"""Cotas automáticas (las que el lienzo dibuja junto a cada elemento) como geometría en mm.

El lienzo las dibuja en píxeles de pantalla; para exportar (PNG, PDF…) se generan aquí como
primitivas en milímetros: líneas de cota y de referencia (abiertas), flechas y textos (cerrados).
"""
from __future__ import annotations

from typing import Iterable, List, Tuple

from . import geometry as G
from .entities import text_prims

MODES = ("off", "size_all", "all", "selection")
SKIP_TYPES = ("text", "image", "dimension")


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def targets(doc, ev=None, show_footprint: bool = False):
    """[(entidad, bbox_mecanizado, bbox_total, centro, diámetro|None)] de los elementos acotables."""
    ev = ev or doc.evaluator()
    out = []
    for e in doc.entities:
        if not e.HAS_POS or e.TYPE in SKIP_TYPES:
            continue
        L = doc.layer(e.layer)
        if L is not None and not L.visible:
            continue
        proc = L.process if L else "cut"
        main = full = None
        circles = []
        for _e, role, pr in doc.geometry(ev, entities=[e]):
            if role == "footprint" and not show_footprint:
                continue
            bb = G.prim_bbox(pr)
            full = G.bbox_union(full, bb)
            if role == proc:
                main = G.bbox_union(main, bb)
                if pr["t"] == "circle":
                    circles.append(pr["r"] * 2)
        if main is None:
            main = full
        if main is None:
            continue
        dia = max(circles) if e.TYPE in ("circle", "hole") and circles else None
        out.append((e, main, full, e.anchor(doc, ev, "c"), dia))
    return out


def _dim(a, b, fa, fb, text, h) -> List[dict]:
    """Cota entre a y b (línea de cota), con líneas de referencia desde fa/fb y el texto encima."""
    prims: List[dict] = []
    gap, over = 0.4 * h, 0.6 * h
    for f_, q in ((fa, a), (fb, b)):
        dx, dy = q[0] - f_[0], q[1] - f_[1]
        L = (dx * dx + dy * dy) ** 0.5
        if L > gap * 1.5:
            ux, uy = dx / L, dy / L
            prims.append({"t": "poly", "pts": [(f_[0] + ux * gap, f_[1] + uy * gap), (q[0] + ux * over, q[1] + uy * over)],
                          "closed": False})
    prims.append({"t": "poly", "pts": [a, b], "closed": False})
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = (dx * dx + dy * dy) ** 0.5
    if L < 1e-6:
        return prims
    ux, uy = dx / L, dy / L
    al = min(h * 0.9, L / 3)
    hw = al * 0.32
    for tip, sg in ((a, 1), (b, -1)):
        bx, by = tip[0] + ux * al * sg, tip[1] + uy * al * sg
        prims.append({"t": "poly", "pts": [tip, (bx - uy * hw, by + ux * hw), (bx + uy * hw, by - ux * hw)], "closed": True})
    vertical = abs(uy) > abs(ux)
    tq = text_prims(text, "", h, False, False, "centro", 1.0, 0.0, 0.0)
    tb = None
    for q in tq:
        tb = G.bbox_union(tb, G.prim_bbox(q))
    tw = (tb[2] - tb[0]) if tb else 0.0
    shift = 0.0
    if tw + 2 * al + h * 0.4 > L:  # no cabe entre las flechas: el texto va junto al extremo final
        shift = L / 2 + al * 0.3 + tw / 2 + h * 0.3
        if (not vertical and b[0] < a[0]) or (vertical and b[1] < a[1]):
            shift = -shift
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    for q in tq:
        pts = [(x + shift, y + gap) for x, y in q["pts"]]  # encima de la línea
        if vertical:
            pts = G.transform_pts(pts, mx, my, 90.0)  # se lee desde la derecha, a la izquierda de la línea
        else:
            pts = [(x + mx, y + my) for x, y in pts]
        prims.append({"t": "poly", "pts": pts, "closed": q.get("closed", True)})
    return prims


def build(doc, ev=None, mode: str = "size_all", selected: Iterable[str] = (), show_footprint: bool = False,
          text_h: float = 0.0) -> List[Tuple[str, dict]]:
    """Primitivas de las cotas automáticas: [("autodim" | "autopos", prim)].

    mode: 'size_all' tamaños de todo y posición de la selección · 'all' tamaños y posiciones de todo ·
    'selection' sólo de la selección · 'off' ninguna."""
    if mode not in MODES or mode == "off":
        return []
    ev = ev or doc.evaluator()
    h = text_h or float(doc.settings.get("dim_text_h", 2.5))
    off = h * 1.8
    selected = set(selected)
    out: List[Tuple[str, dict]] = []
    for e, main, full, (cx, cy), dia in targets(doc, ev, show_footprint):
        sel = e.id in selected
        show_size = mode in ("all", "size_all") or (mode == "selection" and sel)
        show_pos = mode == "all" or sel
        mx0, my0, mx1, my1 = main
        fx0, fy0, fx1, fy1 = full
        if mx1 - mx0 < 0.5 and my1 - my0 < 0.5:
            show_size = False
        if show_size:
            yb = fy0 - off
            if dia is not None:
                ym = (my0 + my1) / 2
                out += [("autodim", p) for p in _dim((mx0, yb), (mx1, yb), (mx0, ym), (mx1, ym), "Ø" + _num(dia), h)]
            else:
                out += [("autodim", p) for p in _dim((mx0, yb), (mx1, yb), (mx0, my0), (mx1, my0), _num(mx1 - mx0), h)]
                xr = fx1 + off
                out += [("autodim", p) for p in _dim((xr, my0), (xr, my1), (mx1, my0), (mx1, my1), _num(my1 - my0), h)]
        if show_pos:
            yt = fy1 + off
            out += [("autopos", p) for p in _dim((0.0, yt), (cx, yt), (0.0, yt - off * 0.6), (cx, cy), "X " + _num(cx), h)]
            xl = fx0 - off
            out += [("autopos", p) for p in _dim((xl, 0.0), (xl, cy), (xl + off * 0.6, 0.0), (cx, cy), "Y " + _num(cy), h)]
    return out
