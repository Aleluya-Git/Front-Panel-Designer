"""Verificación de interferencias y reglas de fabricación."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from . import geometry as G
from ..i18n import tr
from .document import Document


@dataclass
class Issue:
    level: str          # "error" | "aviso" | "info"
    message: str
    ids: Tuple[str, ...]
    where: Optional[Tuple[float, float]] = None


def _shapes(doc: Document, ev, roles):
    """Agrupa por entidad las primitivas cerradas de los roles indicados."""
    out = {}
    for e, role, pr in doc.geometry(ev):
        if role not in roles or pr["t"] == "text":
            continue
        polys = [p for p, closed in G.prim_polys(pr, 0.05) if closed and len(p) >= 3]
        if polys:
            ent = out.setdefault(e.id, (e, []))
            ent[1].extend(polys)
    return out


def check(doc: Document) -> List[Issue]:
    ev = doc.evaluator()
    issues: List[Issue] = []
    W, H, T, _r = doc.panel_dims(ev)
    outline = doc.panel_outline(ev)
    min_edge = float(doc.settings.get("min_edge", 2.0))
    min_web = float(doc.settings.get("min_web", 1.5))

    cuts = _shapes(doc, ev, ("cut", "pocket", "pocket_back"))
    # 1) Bordes del panel
    for eid, (e, polys) in cuts.items():
        for poly in polys:
            if not G.poly_contains_poly(outline, poly):
                b = G.bbox(poly)
                issues.append(Issue("error", tr("«{a}» se sale del panel").format(a=e.display_name()), (eid,),
                                    ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)))
                break
            d = G.poly_distance(outline, poly, boundary_only=True)
            if d < min_edge:
                b = G.bbox(poly)
                issues.append(Issue("aviso", tr("«{a}» a {d} mm del borde (mín. {m})").format(a=e.display_name(), d=f"{d:.2f}", m=min_edge),
                                    (eid,), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)))
                break

    # 2) Entre mecanizados de entidades distintas (un hueco pasante dentro de un rebaje es válido)
    pocket_ids = set(_shapes(doc, ev, ("pocket", "pocket_back")))
    items = [(eid, e, polys, G.bbox([p for poly in polys for p in poly])) for eid, (e, polys) in cuts.items()]
    for i in range(len(items)):
        ida, ea, pa, ba = items[i]
        for j in range(i + 1, len(items)):
            idb, eb, pb, bb = items[j]
            if (bb[0] - ba[2] > min_web or ba[0] - bb[2] > min_web or
                    bb[1] - ba[3] > min_web or ba[1] - bb[3] > min_web):
                continue
            if (ida in pocket_ids) != (idb in pocket_ids):
                inner, outer = (pa, pb) if idb in pocket_ids else (pb, pa)
                if all(any(G.poly_contains_poly(o, x) for o in outer) for x in inner):
                    continue
            dmin = min(G.poly_distance(x, y) for x in pa for y in pb)
            if dmin <= 1e-9:
                issues.append(Issue("error", tr("«{a}» y «{b}» se solapan").format(a=ea.display_name(), b=eb.display_name()),
                                    (ida, idb), _mid(ba, bb)))
            elif dmin < min_web:
                issues.append(Issue("aviso", tr("Puente de {d} mm entre «{a}» y «{b}» (mín. {m})").format(
                                    d=f"{dmin:.2f}", a=ea.display_name(), b=eb.display_name(), m=min_web), (ida, idb), _mid(ba, bb)))

    # 3) Huellas traseras de componentes
    fps = _shapes(doc, ev, ("footprint",))
    fl = list(fps.items())
    for i in range(len(fl)):
        for j in range(i + 1, len(fl)):
            (ida, (ea, pa)), (idb, (eb, pb)) = fl[i], fl[j]
            if min(G.poly_distance(x, y) for x in pa for y in pb) <= 1e-9:
                issues.append(Issue("aviso", tr("Los cuerpos traseros de «{a}» y «{b}» chocan").format(
                                    a=ea.display_name(), b=eb.display_name()), (ida, idb)))
    for eid, (e, polys) in fps.items():
        if any(not G.poly_contains_poly(outline, p) for p in polys):
            issues.append(Issue("info", tr("El cuerpo de «{a}» sobresale del contorno del panel").format(a=e.display_name()),
                                (eid,)))

    # 4) Rebajes demasiado profundos
    for e in doc.entities:
        if e.TYPE == "pocket" and e.v(ev, "depth") >= T:
            issues.append(Issue("error", tr("El rebaje «{a}» atraviesa el panel ({d} ≥ {t} mm)").format(
                                    a=e.display_name(), d=f"{e.v(ev, 'depth'):.2f}", t=f"{T:.2f}"), (e.id,)))
    # 5) Pernos y casquillos a presión
    from .stud import StudEntity
    for e in doc.entities:
        if not isinstance(e, StudEntity):
            continue
        dat = e.data()
        if doc.panel.material in ("Metacrilato", "PVC"):
            issues.append(Issue("aviso", tr("«{a}»: los elementos roscados a presión necesitan un panel metálico").format(
                a=e.display_name()), (e.id,)))
        if T < dat["min_t"]:
            issues.append(Issue("aviso", tr("«{a}»: espesor de panel {t} mm menor que el mínimo {m} mm").format(
                a=e.display_name(), t=f"{T:.2f}", m=dat["min_t"]), (e.id,)))
        if e.is_blind(ev) and e.v(ev, "depth_offset") >= T - 0.3:
            issues.append(Issue("error", tr("«{a}»: el offset de profundidad no deja material para el agujero ciego").format(
                a=e.display_name()), (e.id,)))
    # 6) Textos, escalas y rótulos de componentes
    issues += _check_marks(doc, ev, outline, cuts, pocket_ids)
    if not issues:
        issues.append(Issue("info", tr("Sin interferencias detectadas"), ()))
    return issues


MARK_ROLES = ("engrave", "print")


def _marks(doc: Document, ev):
    """Trazos de textos, escalas y rótulos de componentes que se imprimen o graban.

    Devuelve {clave: (entidad, nombre, [(pts, cerrado, bbox)], bbox_total)}."""
    out = {}

    def put(key, e, name, pr):
        for pts, closed in G.prim_polys(pr, 0.05):
            if len(pts) < 2:
                continue
            item = out.setdefault(key, [e, name, [], None])
            b = G.bbox(pts)
            item[2].append((pts, bool(closed) and len(pts) >= 3, b))
            item[3] = G.bbox_union(item[3], b)

    for e, role, pr in doc.geometry(ev):
        if e.TYPE in ("text", "scale") and role in MARK_ROLES:
            put(e.id, e, _mark_name(e, ev), pr)
    from .entities import transform_prim
    for e in doc.entities:
        if e.TYPE != "component" or not e.p.get("label"):
            continue
        L = doc.layer(e.layer)
        if L is not None and L.process == "ref":
            continue
        x, y = e.v(ev, "x"), e.v(ev, "y")
        name = tr("Rótulo de «{a}»").format(a=e.display_name())
        for role, pr in e.local_prims(doc, ev):
            if role == "label":
                put(e.id + "#rotulo", e, name, transform_prim(pr, x, y, 0.0))
    return {k: tuple(v) for k, v in out.items()}


def _mark_name(e, ev) -> str:
    if e.p.get("name"):
        return f"«{e.p['name']}»"
    if e.TYPE == "text":
        t = " ".join(str(e.p.get("text", "")).split())
        return tr("Texto «{t}»").format(t=t if len(t) <= 24 else t[:23] + "…")
    return tr("Escala en ({x}, {y})").format(x=f"{e.v(ev, 'x'):g}", y=f"{e.v(ev, 'y'):g}")


def _gap(a, b) -> float:
    """Cota inferior de la distancia entre dos rectángulos envolventes."""
    return max(0.0, b[0] - a[2], a[0] - b[2], b[1] - a[3], a[1] - b[3])


def _closest(A, B, limit):
    """Distancia mínima entre dos listas de trazos (pts, cerrado, bbox); se detiene en el primer contacto."""
    best, where = float("inf"), None
    for pa, ca, ba in A:
        for pb, cb, bb in B:
            if _gap(ba, bb) >= min(best, limit):
                continue
            d = G.poly_distance(pa, pb, ca, cb)
            if d < best:
                best, where = d, _mid(ba, bb)
                if best <= 1e-9:
                    return 0.0, where
    return best, where


def _as_strokes(polys):
    return [(p, True, G.bbox(p)) for p in polys]


def _check_marks(doc: Document, ev, outline, cuts, pocket_ids) -> List[Issue]:
    issues: List[Issue] = []
    marks = _marks(doc, ev)
    if not marks:
        return issues
    gap_min = float(doc.settings.get("min_text_gap", 0.5))
    edge_min = float(doc.settings.get("min_text_edge", 1.0))
    outline_s = [(outline, True, G.bbox(outline))]
    cut_items = [(eid, e, _as_strokes(polys)) for eid, (e, polys) in cuts.items()]
    cut_items = [(eid, e, st, G.bbox([pt for p, _c, _b in st for pt in p])) for eid, e, st in cut_items]
    # siluetas visibles de los componentes (mandos, biseles...)
    sil = {}
    for e, role, pr in doc.geometry(ev):
        if e.TYPE == "component" and role == "ref":
            for p, closed in G.prim_polys(pr, 0.05):
                if closed and len(p) >= 3 and abs(G.area(p)) > 1.0:
                    sil.setdefault(e.id, (e, []))[1].append(p)
    sil_items = [(eid, e, _as_strokes(polys)) for eid, (e, polys) in sil.items()]
    sil_items = [(eid, e, st, G.bbox([pt for p, _c, _b in st for pt in p])) for eid, e, st in sil_items]

    keys = list(marks)
    for k in keys:
        e, name, strokes, mb = marks[k]
        # a) borde del panel
        out_of_panel = any(not all(G.point_in_poly(pt, outline) for pt in p) for p, _c, _b in strokes)
        if out_of_panel:
            issues.append(Issue("error", tr("{a} se sale del panel").format(a=name), (e.id,), _mid(mb, mb)))
        else:
            d, w = _closest(strokes, [(outline, False, G.bbox(outline))], edge_min)
            if d < edge_min:
                issues.append(Issue("aviso", tr("{a} está a {d} mm del borde (mín. {m})").format(
                    a=name, d=f"{d:.2f}", m=edge_min), (e.id,), w))
        # b) huecos pasantes y rebajes
        for cid, ce, cst, cb in cut_items:
            if _gap(mb, cb) >= gap_min:
                continue
            if cid == e.id and k == e.id:
                continue  # un texto en una capa de corte ya se comprueba como mecanizado
            if cid in pocket_ids:
                d, w = _closest(strokes, cst, 1e-6)
                if d <= 1e-9:
                    inside = all(any(G.poly_contains_poly(pp, p) for pp, _c, _b in cst) for p, _cl, _b in strokes)
                    if not inside:
                        issues.append(Issue("aviso", tr("{a} cruza el borde del rebaje «{b}»").format(
                            a=name, b=ce.display_name()), (e.id, cid), w))
                continue
            d, w = _closest(strokes, cst, gap_min)
            if d <= 1e-9:
                issues.append(Issue("error", tr("{a} invade el hueco «{b}»").format(
                    a=name, b=ce.display_name()), (e.id, cid), w))
            elif d < gap_min:
                issues.append(Issue("aviso", tr("{a} está a {d} mm del hueco «{b}» (mín. {m})").format(
                    a=name, d=f"{d:.2f}", b=ce.display_name(), m=gap_min), (e.id, cid), w))
        # c) tapado por la silueta de un componente
        for sid, se, sst, sb in sil_items:
            if _gap(mb, sb) > 0:
                continue
            d, w = _closest(strokes, sst, 1e-6)
            if d <= 1e-9:
                issues.append(Issue("aviso", tr("{a} queda debajo de «{b}» y no se verá").format(
                    a=name, b=se.display_name()), (e.id, sid), w))
    # d) textos y escalas entre sí
    for i in range(len(keys)):
        ea, na, sa, ba = marks[keys[i]]
        for j in range(i + 1, len(keys)):
            eb, nb, sb_, bb = marks[keys[j]]
            if _gap(ba, bb) > 0:
                continue
            d, w = _closest(sa, sb_, 1e-6)
            if d <= 1e-9:
                ids = (ea.id,) if ea.id == eb.id else (ea.id, eb.id)
                issues.append(Issue("aviso", tr("{a} y {b} se solapan").format(a=na, b=nb), ids, w))
    return issues


def _mid(a, b):
    return ((min(a[0], b[0]) + max(a[2], b[2])) / 2, (min(a[1], b[1]) + max(a[3], b[3])) / 2)


def measure_between(doc: Document, ea, eb):
    """(distancia entre centros, holgura mínima entre contornos)."""
    ev = doc.evaluator()
    ca, cb = ea.anchor(doc, ev, "c"), eb.anchor(doc, ev, "c")
    pa = [p for _e, _r, pr in doc.geometry(ev, entities=[ea]) for p, c in G.prim_polys(pr, 0.05) if c]
    pb = [p for _e, _r, pr in doc.geometry(ev, entities=[eb]) for p, c in G.prim_polys(pr, 0.05) if c]
    gap = min((G.poly_distance(x, y) for x in pa for y in pb), default=float("nan"))
    return G.dist(ca, cb), gap, ca, cb
