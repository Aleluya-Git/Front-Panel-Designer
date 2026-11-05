"""Dibujo del documento con QPainter (lienzo, PDF y PNG comparten este código).

El QPainter debe llegar ya transformado a coordenadas de panel en mm con Y
hacia arriba.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen

from ..core import geometry as G
from ..core import textpath
from ..core.document import Document, MATERIALS

Item = Tuple[str, str, dict]  # (entity_id, role, prim)


def collect_items(doc: Document, ev=None) -> List[Item]:
    ev = ev or doc.evaluator()
    out: List[Item] = []
    for e, role, pr in doc.geometry(ev, visible_only=True):
        if pr["t"] == "text":
            for q in text_prim_polys(pr):
                out.append((e.id, role, q))
        else:
            out.append((e.id, role, pr))
    return out


def text_prim_polys(pr) -> List[dict]:
    polys, width = textpath.outlines(pr["text"], "", float(pr["h"]), False, False)
    ang = pr.get("angle", 0.0)
    x, y = pr["pos"]
    out = []
    for pts, closed in polys:
        loc = [(px - width / 2, py) for px, py in pts]
        out.append({"t": "poly", "pts": G.transform_pts(loc, x, y, ang), "closed": closed})
    return out


def add_prim(path: QPainterPath, pr: dict) -> None:
    t = pr["t"]
    if t == "circle":
        path.addEllipse(QPointF(*pr["c"]), pr["r"], pr["r"])
    elif t == "poly":
        pts = pr["pts"]
        if not pts:
            return
        path.moveTo(QPointF(*pts[0]))
        for q in pts[1:]:
            path.lineTo(QPointF(*q))
        if pr.get("closed", True):
            path.closeSubpath()


_ANY = object()


def _paths(items: Iterable[Item], role: str, closed_only: Optional[bool] = None, color=_ANY) -> QPainterPath:
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.OddEvenFill)
    for _eid, r, pr in items:
        if r != role:
            continue
        if color is not _ANY and (pr.get("color") or None) != color:
            continue
        is_closed = pr["t"] == "circle" or pr.get("closed", True)
        if closed_only is True and not is_closed:
            continue
        if closed_only is False and is_closed:
            continue
        add_prim(path, pr)
    return path


_img_cache: Dict[Tuple[str, int], QImage] = {}


def entity_image(e) -> Optional[QImage]:
    data = e.p.get("data") or ""
    if not data:
        return None
    key = (e.id, hash(data))
    img = _img_cache.get(key)
    if img is None:
        img = QImage.fromData(QByteArray.fromBase64(data.encode("ascii")))
        if img.isNull():
            return None
        _img_cache[key] = img
    return img


def pen(color, width, cosmetic=True, style=Qt.PenStyle.SolidLine) -> QPen:
    pn = QPen(QColor(color), width)
    pn.setCosmetic(cosmetic)
    pn.setStyle(style)
    pn.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pn.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pn


AUTOPOS_COLOR = "#e07b00"


def with_auto_dims(doc: Document, items: List[Item], mode: str = "off", selected: Iterable[str] = (),
                   ev=None) -> List[Item]:
    """Añade a la lista de dibujo las cotas automáticas en mm (para PNG/PDF)."""
    if not mode or mode == "off":
        return items
    from ..core import autodims
    extra = [("auto", role, pr) for role, pr in autodims.build(doc, ev, mode, selected)]
    return list(items) + extra


def paint_document(p: QPainter, doc: Document, items: Optional[List[Item]] = None, *, mode: str = "edit",
                   colors: Optional[dict] = None, selected: Iterable[str] = (), flagged: Iterable[str] = (),
                   show_ref: bool = True, show_footprint: bool = False, show_dims: bool = True,
                   px_per_mm: float = 4.0) -> None:
    """mode: 'edit' (lienzo), 'visual' (aspecto final), 'fab' (trazos por proceso, PDF técnico)."""
    colors = colors or {}
    ev = doc.evaluator()
    items = items if items is not None else collect_items(doc, ev)
    cosm = mode == "edit"
    lw = 1.0 if cosm else 0.12  # px cosméticos o mm
    hole_color = colors.get("hole", "#14161a") if mode == "edit" else None
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    outline = doc.panel_outline(ev)
    mat = MATERIALS.get(doc.panel.material, MATERIALS["Aluminio"])
    panel_col = QColor(doc.panel.color)
    if mode == "edit" and mat.get("alpha", 1.0) < 1.0:
        panel_col.setAlphaF(max(0.35, mat["alpha"]))
    # ---- 1. panel con huecos
    if mode != "fab":
        pp = QPainterPath()
        pp.setFillRule(Qt.FillRule.OddEvenFill)
        add_prim(pp, {"t": "poly", "pts": outline, "closed": True})
        for _eid, r, pr in items:
            if r == "cut" and (pr["t"] == "circle" or pr.get("closed", True)):
                add_prim(pp, pr)
        if hole_color:
            hp = _paths(items, "cut", closed_only=True)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(hole_color)))
            p.drawPath(hp)
        p.setPen(pen("#4a4f57" if mode == "edit" else "#555555", lw * 1.2, cosm))
        p.setBrush(QBrush(panel_col))
        p.drawPath(pp)
        if mode == "edit":
            _brushed_sheen(p, outline, doc)
    else:
        p.setBrush(Qt.BrushStyle.NoBrush)
        op = QPainterPath()
        add_prim(op, {"t": "poly", "pts": outline, "closed": True})
        p.setPen(pen("#000000", lw, cosm))
        p.drawPath(op)

    lay_col = {L.process: L.color for L in doc.layers}
    # ---- 2. rebajes
    pk = _paths(items, "pocket")
    if not pk.isEmpty():
        p.setPen(pen(lay_col.get("pocket", "#f5a524") if mode != "visual" else "#555", lw, cosm))
        p.setBrush(QBrush(QColor(0, 0, 0, 45)) if mode != "fab" else Qt.BrushStyle.NoBrush)
        p.drawPath(pk)
    if mode != "visual":
        pb = _paths(items, "pocket_back")
        if not pb.isEmpty():
            p.setPen(pen("#b77a12", lw, cosm, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(pb)
    # ---- 3. imágenes
    if mode != "fab":
        for e in doc.entities:
            if e.TYPE != "image":
                continue
            L = doc.layer(e.layer)
            if L is not None and not L.visible:
                continue
            img = entity_image(e)
            if img is None:
                continue
            x, y, w, h, rot = e.v(ev, "x"), e.v(ev, "y"), e.v(ev, "w"), e.v(ev, "h"), e.v(ev, "rot")
            p.save()
            p.translate(x, y)
            p.rotate(rot)
            p.scale(1, -1)
            p.drawImage(QRectF(-w / 2, -h / 2, w, h), img)
            p.restore()
    # ---- 4. grabado y serigrafía (cada elemento puede tener su propio color)
    print_col = doc.panel.print_color
    for role, fill0 in (("engrave", "#2b2f36" if mode != "fab" else None), ("print", print_col if mode != "fab" else None)):
        elem_colors = sorted({pr.get("color") or None for _e, r, pr in items if r == role}, key=lambda c: c or "")
        for col in elem_colors:
            fill = fill0
            if mode == "edit" and role == "engrave":
                fill = lay_col.get("engrave", "#3e9bff")
            if col and mode != "fab":
                fill = col
            closed = _paths(items, role, closed_only=True, color=col)
            opened = _paths(items, role, closed_only=False, color=col)
            stroke_col = lay_col.get(role, "#333") if mode != "visual" else (fill or "#333")
            if not closed.isEmpty():
                p.setPen(pen(stroke_col, lw * 0.6, cosm) if mode not in ("visual", "edit") or (mode == "edit" and not col)
                         else Qt.PenStyle.NoPen)
                if mode == "visual":
                    p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(fill)) if fill else Qt.BrushStyle.NoBrush)
                p.drawPath(closed)
            if not opened.isEmpty():
                stroke_w = 0.35 if not cosm else max(1.0, 0.35 * px_per_mm)
                p.setPen(pen(fill or stroke_col, stroke_w, cosm))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawPath(opened)
    # ---- 5. contornos de mecanizado (edición / fabricación)
    if mode in ("edit", "fab"):
        cp = _paths(items, "cut")
        p.setPen(pen(lay_col.get("cut", "#e5484d"), lw, cosm))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(cp)
    # ---- 6. referencias y huellas
    if show_ref and mode != "visual":
        rp = _paths(items, "ref")
        if not rp.isEmpty():
            p.setPen(pen(lay_col.get("ref", "#9a8cff"), lw * 0.8, cosm, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(rp)
    if show_footprint:
        fp = _paths(items, "footprint")
        if not fp.isEmpty():
            p.setPen(pen("#888888", lw * 0.8, cosm, Qt.PenStyle.DotLine))
            p.setBrush(QBrush(QColor(128, 128, 128, 25)))
            p.drawPath(fp)
    # ---- 7. cotas (de usuario y automáticas para exportar)
    dc = lay_col.get("dim", "#2fb67c")
    for role, col, on in (("dim", dc, show_dims), ("autodim", dc, True), ("autopos", AUTOPOS_COLOR, True)):
        if not on:
            continue
        lines = _paths(items, role, closed_only=False)
        heads = _paths(items, role, closed_only=True)
        if lines.isEmpty() and heads.isEmpty():
            continue
        p.setPen(pen(col, lw * 0.8, cosm))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(lines)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(col)))
        p.drawPath(heads)
    # ---- 8. resaltados
    flagged = set(flagged)
    if flagged and mode == "edit":
        fpth = QPainterPath()
        for eid, _r, pr in items:
            if eid in flagged:
                add_prim(fpth, pr)
        p.setPen(pen(colors.get("issue", "#ff4d4f"), 2.4, True))
        p.setBrush(QBrush(QColor(255, 77, 79, 40)))
        p.drawPath(fpth)
    selected = set(selected)
    if selected and mode == "edit":
        sp = QPainterPath()
        for eid, _r, pr in items:
            if eid in selected:
                add_prim(sp, pr)
        p.setPen(pen(colors.get("sel", "#3d8bfd"), 2.0, True))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(sp)


def _brushed_sheen(p: QPainter, outline, doc: Document):
    """Sutil degradado para sugerir el material en el lienzo."""
    if doc.panel.finish not in ("Cepillado", "Anodizado", "Natural"):
        return
    b = G.bbox(outline)
    from PySide6.QtGui import QLinearGradient
    g = QLinearGradient(QPointF(b[0], b[3]), QPointF(b[2], b[1]))
    g.setColorAt(0.0, QColor(255, 255, 255, 26))
    g.setColorAt(0.5, QColor(255, 255, 255, 0))
    g.setColorAt(1.0, QColor(0, 0, 0, 22))
    path = QPainterPath()
    add_prim(path, {"t": "poly", "pts": outline, "closed": True})
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawPath(path)


def world_transform_for_page(W_mm: float, H_mm: float, x0: float, y0: float, dev_per_mm: float):
    """Transformación mm (Y arriba) → dispositivo (Y abajo) para PDF/PNG."""
    from PySide6.QtGui import QTransform
    t = QTransform()
    t.scale(dev_per_mm, -dev_per_mm)
    t.translate(-x0, -(y0 + H_mm))
    return t


def bounds(doc: Document, items: List[Item], margin: float = 5.0):
    ev = doc.evaluator()
    W, H, _T, _r = doc.panel_dims(ev)
    b = (0.0, 0.0, W, H)
    for _e, _r2, pr in items:
        b = G.bbox_union(b, G.prim_bbox(pr))
    return (b[0] - margin, b[1] - margin, b[2] + margin, b[3] + margin)


def export_pdf(doc: Document, path: str, mode: str = "visual", show_dims: bool = True,
               auto_dims: str = "off", selected: Iterable[str] = ()) -> None:
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter
    items = with_auto_dims(doc, collect_items(doc), auto_dims, selected)
    b = bounds(doc, items if show_dims else [i for i in items if i[1] != "dim"])
    w, h = b[2] - b[0], b[3] - b[1]
    wr = QPdfWriter(path)
    wr.setTitle(str(doc.meta.get("title", "Panel")))
    wr.setCreator("Electronic Front Panel Designer")
    wr.setPageSize(QPageSize(QSizeF(w, h), QPageSize.Unit.Millimeter, "Panel"))
    wr.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Millimeter)
    wr.setResolution(1200)
    dpmm = 1200 / 25.4
    p = QPainter(wr)
    try:
        # y0 se toma desde abajo: la página empieza en b[3]
        p.setTransform(world_transform_for_page(w, h, b[0], b[1], dpmm))
        paint_document(p, doc, items, mode=mode, show_dims=show_dims, show_ref=(mode == "fab"),
                       px_per_mm=dpmm)
    finally:
        p.end()


def render_image(doc: Document, dpi: float = 300, mode: str = "visual", show_dims: bool = False,
                 transparent: bool = False, auto_dims: str = "off", selected: Iterable[str] = ()) -> QImage:
    items = with_auto_dims(doc, collect_items(doc), auto_dims, selected)
    has_dims = show_dims or (auto_dims and auto_dims != "off")
    b = bounds(doc, items if show_dims else [i for i in items if i[1] != "dim"], margin=5.0 if has_dims else 2.0)
    dpmm = dpi / 25.4
    wpx, hpx = max(1, int(math.ceil((b[2] - b[0]) * dpmm))), max(1, int(math.ceil((b[3] - b[1]) * dpmm)))
    img = QImage(wpx, hpx, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0) if transparent else QColor("#ffffff"))
    img.setDotsPerMeterX(int(dpi / 0.0254))
    img.setDotsPerMeterY(int(dpi / 0.0254))
    p = QPainter(img)
    try:
        p.setTransform(world_transform_for_page(b[2] - b[0], b[3] - b[1], b[0], b[1], dpmm))
        paint_document(p, doc, items, mode=mode, show_dims=show_dims, show_ref=False, px_per_mm=dpmm)
    finally:
        p.end()
    return img
