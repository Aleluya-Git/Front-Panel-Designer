"""Alineación, distribución y matrices de controles."""
from __future__ import annotations

from typing import List

from .document import Document
from .entities import Entity


def _boxes(doc: Document, ents: List[Entity]):
    ev = doc.evaluator()
    return ev, [e.bbox(doc, ev) for e in ents]


def align(doc: Document, ents: List[Entity], mode: str) -> None:
    """mode: left, right, top, bottom, hcenter, vcenter.

    Con una sola entidad se alinea respecto al panel.
    """
    ents = [e for e in ents if e.HAS_POS and not e.locked]
    if not ents:
        return
    ev, boxes = _boxes(doc, ents)
    if len(ents) == 1:
        W, H = ev.builtins["W"], ev.builtins["H"]
        ref = (0.0, 0.0, W, H)
    else:
        ref = (min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes))
    for e, b in zip(ents, boxes):
        dx = dy = 0.0
        if mode == "left":
            dx = ref[0] - b[0]
        elif mode == "right":
            dx = ref[2] - b[2]
        elif mode == "bottom":
            dy = ref[1] - b[1]
        elif mode == "top":
            dy = ref[3] - b[3]
        elif mode == "hcenter":
            dx = (ref[0] + ref[2]) / 2 - (b[0] + b[2]) / 2
        elif mode == "vcenter":
            dy = (ref[1] + ref[3]) / 2 - (b[1] + b[3]) / 2
        e.move(dx, dy)
    doc.touch()


def distribute(doc: Document, ents: List[Entity], axis: str = "h") -> None:
    """Reparte los centros a intervalos iguales entre el primero y el último."""
    ents = [e for e in ents if e.HAS_POS and not e.locked]
    if len(ents) < 3:
        return
    ev, boxes = _boxes(doc, ents)
    k = 0 if axis == "h" else 1
    centers = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in boxes]
    pos = {e.id: n for n, e in enumerate(doc.entities)}
    order = sorted(range(len(ents)), key=lambda i: (round(centers[i][k], 6), pos.get(ents[i].id, 0)))
    c0, c1 = centers[order[0]][k], centers[order[-1]][k]
    step = (c1 - c0) / (len(ents) - 1)
    for n, i in enumerate(order):
        target = c0 + n * step
        d = target - centers[i][k]
        ents[i].move(d if k == 0 else 0.0, d if k == 1 else 0.0)
    doc.touch()


def distribute_on_panel(doc: Document, ents: List[Entity], axis: str = "h",
                        margin: float = 15.0, linked: bool = True) -> None:
    """Distribución automática a lo ancho (o alto) del panel.

    Con ``linked=True`` las posiciones se escriben como expresiones que
    dependen de W/H y de la variable 'margen_dist', de modo que al cambiar el
    tamaño del panel los controles se redistribuyen solos.
    """
    ents = [e for e in ents if e.HAS_POS and not e.locked]
    n = len(ents)
    if n == 0:
        return
    ev = doc.evaluator()
    k = "x" if axis == "h" else "y"
    pos = {e.id: n for n, e in enumerate(doc.entities)}
    ents.sort(key=lambda e: (round(e.v(ev, k), 6), pos.get(e.id, 0)))  # empates: orden del dibujo
    size = "W" if axis == "h" else "H"
    var = "margen_dist" if axis == "h" else "margen_dist_v"
    if linked:
        doc.variables.setdefault(var, float(margin))
    for i, e in enumerate(ents):
        if n == 1:
            expr = f"={size}/2"
            num = ev.builtins[size] / 2
        else:
            expr = f"={var} + {i}*({size} - 2*{var})/{n - 1}"
            num = margin + i * (ev.builtins[size] - 2 * margin) / (n - 1)
        e.p[k] = expr if linked else round(num, 4)
    doc.touch()


def make_array(doc: Document, ents: List[Entity], cols: int, rows: int,
               dx: float, dy: float) -> List[Entity]:
    """Matriz rectangular de copias. Devuelve las nuevas entidades."""
    new = []
    for r in range(max(1, rows)):
        for c in range(max(1, cols)):
            if r == 0 and c == 0:
                continue
            for e in ents:
                n = e.clone()
                n.move(c * dx, r * dy)
                doc.add(n)
                new.append(n)
    return new


def mirror_h(doc: Document, ents: List[Entity]) -> None:
    """Simetría horizontal respecto al eje central vertical del panel."""
    ev = doc.evaluator()
    W = ev.builtins["W"]
    for e in ents:
        if e.HAS_POS and not e.locked:
            x = e.v(ev, "x")
            e.move(W - 2 * x, 0.0)
            e.p["rot"] = round(-e.v(ev, "rot"), 6)
            if e.TYPE == "path":
                e.p["mirror"] = not e.p.get("mirror", False)
    doc.touch()


def auto_dimension(doc: Document, ents: List[Entity], gap: float = 6.0) -> List[Entity]:
    """Acotación automática de centros respecto a la esquina inferior izquierda.

    Crea cotas horizontales bajo el panel y verticales a su izquierda,
    vinculadas a las entidades (se actualizan solas al moverlas).
    """
    from .entities import DimensionEntity
    ev = doc.evaluator()
    targets = [e for e in ents if e.HAS_POS and e.TYPE not in ("dimension",)]
    xs, ys = {}, {}
    for e in targets:
        cx, cy = e.anchor(doc, ev, "c")
        xs.setdefault(round(cx, 3), e)
        ys.setdefault(round(cy, 3), e)
    new = []
    for i, (x, e) in enumerate(sorted(xs.items())):
        if abs(x) < 1e-6:
            continue
        d = DimensionEntity(orient="h", offset=-(gap + i * gap * 0.9),
                            a={"ref": "panel", "anchor": "bl"}, b={"ref": e.id, "anchor": "c"})
        doc.add(d)
        new.append(d)
    for i, (y, e) in enumerate(sorted(ys.items())):
        if abs(y) < 1e-6:
            continue
        d = DimensionEntity(orient="v", offset=-(gap + i * gap * 0.9),
                            a={"ref": "panel", "anchor": "bl"}, b={"ref": e.id, "anchor": "c"})
        doc.add(d)
        new.append(d)
    return new


def panel_dimensions(doc: Document) -> List[Entity]:
    """Cotas de ancho y alto totales del panel."""
    from .entities import DimensionEntity
    ev = doc.evaluator()
    H = ev.builtins["H"]
    a = DimensionEntity(orient="h", offset=round(8.0, 3), a={"ref": "panel", "anchor": "tl"},
                        b={"ref": "panel", "anchor": "tr"})
    b = DimensionEntity(orient="v", offset=8.0, a={"ref": "panel", "anchor": "br"},
                        b={"ref": "panel", "anchor": "tr"})
    del H
    doc.add(a)
    doc.add(b)
    return [a, b]
