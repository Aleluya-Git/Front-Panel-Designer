"""Selección por clic (sin Qt)."""
from __future__ import annotations

from typing import Optional

from . import geometry as G


def hit_test(doc, items, wx, wy, tol, show_footprint=False) -> Optional[str]:
    """Entidad bajo el cursor.

    «Dentro» se calcula par-impar por entidad y rol, de modo que los huecos interiores (el ojo de un «0»,
    el agujero de una arandela) no cuentan como relleno. Gana lo que contiene el punto con menor
    superficie, salvo que el clic caiga sobre un trazo (dentro de la tolerancia), que tiene prioridad.
    Las líneas de referencia (rol «ref», p. ej. la cruz de centro de una escala) tienen la prioridad más baja,
    para que una escala concéntrica no impida seleccionar el potenciómetro de debajo.
    """
    p = (wx, wy)
    per = {}  # eid -> {"par": {rol: n}, "d": distancia mínima a un borde, "bb": caja}
    for eid, role, pr in items:
        if role == "footprint" and not show_footprint:
            continue
        e = doc.get(eid)
        if e is None:
            continue
        L = doc.layer(e.layer)
        if L is not None and L.locked:
            continue
        st = per.setdefault(eid, {"par": {}, "d": float("inf"), "dref": float("inf"), "bb": None})
        st["bb"] = G.bbox_union(st["bb"], G.prim_bbox(pr))
        if pr["t"] == "circle":
            d = abs(G.dist(p, pr["c"]) - pr["r"])
            inside = G.dist(p, pr["c"]) <= pr["r"]
        elif pr["t"] == "poly":
            pts = pr["pts"]
            closed = pr.get("closed", True) and len(pts) > 2
            n = len(pts)
            m = n if closed else n - 1
            d = min((G.seg_point_dist(p, pts[i], pts[(i + 1) % n]) for i in range(m)),
                    default=G.dist(p, pts[0]) if pts else float("inf"))
            inside = closed and G.point_in_poly(p, pts)
        else:
            continue
        if role == "ref":     # líneas guía (cruz de centro de una escala…): no tapan a lo que hay debajo
            st["dref"] = min(st["dref"], d)
        else:
            st["d"] = min(st["d"], d)
        if inside:
            st["par"][role] = st["par"].get(role, 0) + 1
    best = None
    for eid, st in per.items():
        inside = any(n % 2 == 1 for n in st["par"].values())
        b = st["bb"] or (0, 0, 0, 0)
        area = (b[2] - b[0]) * (b[3] - b[1])
        if st["d"] <= tol:          # clic sobre un trazo: prioridad (como en los CAD)
            score = (0, st["d"], area)
        elif inside:                # clic en el relleno: gana el elemento más pequeño
            score = (1, area, 0.0)
        elif st["dref"] <= tol:     # sólo sobre una línea de referencia
            score = (2, st["dref"], area)
        else:
            continue
        if best is None or score < best[0]:
            best = (score, eid)
    return best[1] if best else None
