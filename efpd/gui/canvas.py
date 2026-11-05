"""Lienzo CAD 2D: zoom, desplazamiento, rejilla, reglas, ajuste y herramientas."""
from __future__ import annotations

import math
from typing import List, Optional, Set, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from ..core import autodims
from ..core import geometry as G
from ..core.entities import (CircleEntity, DHoleEntity, DimensionEntity, EllipseEntity,
                             HoleEntity, OvalSlotEntity, PocketEntity, PolygonEntity, PolylineEntity,
                             RectEntity, RoundRectEntity, SlotEntity, TextEntity)
from ..i18n import N_, tr
from . import render
from .safepaint import safe_paint

RULER = 22

DRAG_TOOLS = {"rect", "roundrect", "slot", "pocket", "ellipse", "circle", "polygon", "oval"}
CLICK_TOOLS = {"hole", "hole_csk", "hole_thread", "dhole", "text", "component", "place"}
TOOL_HINTS = {
    "select": N_("Clic: seleccionar · Mayús: añadir · Arrastrar: mover / ventana de selección · Rueda: zoom · "
              "Botón central o Espacio: desplazar"),
    "pan": N_("Arrastre para desplazar la vista"),
    "rect": N_("Arrastre, o haga dos clics, de esquina a esquina"), "roundrect": N_("Arrastre, o haga dos clics, de esquina a esquina"),
    "slot": N_("Arrastre, o haga dos clics, de esquina a esquina"), "pocket": N_("Arrastre para definir el rebaje"),
    "ellipse": N_("Arrastre para definir los ejes"), "circle": N_("Clic en el centro y arrastre el radio"),
    "polygon": N_("Clic en el centro y arrastre al vértice"), "oval": N_("Arrastre de un extremo al otro"),
    "polyline": N_("Clic para añadir vértices · Doble clic o Intro para terminar · Esc cancela"),
    "hole": N_("Clic para colocar agujero de montaje"), "hole_csk": N_("Clic para colocar agujero avellanado"),
    "hole_thread": N_("Clic para colocar agujero roscado"), "dhole": N_("Clic para colocar agujero en D"),
    "text": N_("Clic para colocar texto"), "component": N_("Clic para colocar el componente · Esc para terminar"),
    "place": N_("Clic para colocar · Esc para cancelar"), "dimension": N_("Clic en el primer punto y en el segundo (se vinculan a centros)"),
    "measure": N_("Clic en dos puntos para medir"),
}


def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


class Canvas(QWidget):
    selectionChanged = Signal()
    cursorMoved = Signal(float, float)
    message = Signal(str)
    zoomChanged = Signal(float)

    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 300)
        self.s = 4.0
        self.ox, self.oy = 60.0, 500.0
        self.selected: Set[str] = set()
        self.flagged: Set[str] = set()
        self.tool = "select"
        self.place_entity = None      # entidad prototipo para 'component'/'place'
        self.show_ref = True
        self.show_footprint = False
        self.show_dims = True
        self.auto_dims = "size_all"   # size_all | all | selection | off
        self._dim_cache = (None, [])
        self._items = []
        self._items_rev = -1
        self._drag = None
        self._press_world = None
        self._cursor_w = (0.0, 0.0)
        self._snap_ref = None
        self._snap_mark = None
        self._poly_pts: List[Tuple[float, float]] = []
        self._click_pts: List[Tuple[Tuple[float, float], Optional[dict]]] = []
        self._measure: Optional[Tuple[Tuple[float, float], Tuple[float, float]]] = None
        self._space = False
        self._pan_last = None
        self._fitted = False

    # ------------------------------------------------------------ transformaciones
    @property
    def doc(self):
        return self.mw.doc

    def colors(self):
        return self.mw.colors

    def w2s(self, x, y) -> QPointF:
        return QPointF(self.ox + x * self.s, self.oy - y * self.s)

    def s2w(self, pt: QPointF) -> Tuple[float, float]:
        return ((pt.x() - self.ox) / self.s, (self.oy - pt.y()) / self.s)

    def fit_view(self):
        items = self.items()
        b = render.bounds(self.doc, items, margin=10.0)
        w, h = max(1.0, b[2] - b[0]), max(1.0, b[3] - b[1])
        aw, ah = max(50, self.width() - RULER - 20), max(50, self.height() - RULER - 20)
        self.s = max(0.05, min(aw / w, ah / h))
        self.ox = RULER + 10 + (aw - w * self.s) / 2 - b[0] * self.s
        self.oy = RULER + 10 + (ah - h * self.s) / 2 + b[3] * self.s
        self.zoomChanged.emit(self.s)
        self.update()

    def zoom(self, factor, at: Optional[QPointF] = None):
        at = at or QPointF(self.width() / 2, self.height() / 2)
        wx, wy = self.s2w(at)
        self.s = max(0.05, min(400.0, self.s * factor))
        self.ox = at.x() - wx * self.s
        self.oy = at.y() + wy * self.s
        self.zoomChanged.emit(self.s)
        self.update()

    def center_on(self, x, y):
        self.ox = self.width() / 2 - x * self.s
        self.oy = self.height() / 2 + y * self.s
        self.update()

    # ------------------------------------------------------------ datos
    def items(self):
        if self._items_rev != self.doc.revision:
            self._items = render.collect_items(self.doc)
            self._items_rev = self.doc.revision
        return self._items

    def invalidate(self):
        self._items_rev = -1
        self.update()

    def set_tool(self, tool: str, entity=None):
        if entity is None and tool == self.tool:
            entity = self.place_entity
        self.tool = tool
        self.place_entity = entity
        self._drag = None
        self._poly_pts = []
        self._click_pts = []
        if tool != "measure":
            self._measure = None
        self.setCursor(Qt.CursorShape.ArrowCursor if tool == "select" else
                       Qt.CursorShape.OpenHandCursor if tool == "pan" else Qt.CursorShape.CrossCursor)
        self.message.emit(tr(TOOL_HINTS.get(tool, "")))
        if hasattr(self.mw, "on_tool_changed"):
            self.mw.on_tool_changed(tool)
        if tool in ("place", "component"):
            self.cursor_to_current()
        self.update()

    def cursor_to_current(self):
        """Coloca el cursor de trabajo donde está el ratón (o en el centro de la vista) para que la pieza a
        colocar aparezca junto al cursor sin tener que moverlo."""
        from PySide6.QtGui import QCursor
        pt = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(pt):
            pt = self.rect().center()
        wx, wy = self.s2w(QPointF(pt))
        self._cursor_w = self.snap(wx, wy, objects=False)

    def set_selection(self, ids, emit=True):
        self.selected = set(ids)
        if emit:
            self.selectionChanged.emit()
        self.update()

    # ------------------------------------------------------------ ajuste
    def snap(self, wx, wy, objects=True):
        st = self.doc.settings
        self._snap_ref = None
        self._snap_mark = None
        if objects and st.get("snap_objects", True):
            tol = 10.0 / self.s
            best = None
            ev = self.doc.evaluator()
            W, H = ev.builtins["W"], ev.builtins["H"]
            cands = [((x, y), {"ref": "panel", "anchor": a}) for a, (x, y) in
                     {"bl": (0, 0), "br": (W, 0), "tl": (0, H), "tr": (W, H), "c": (W / 2, H / 2),
                      "b": (W / 2, 0), "t": (W / 2, H), "l": (0, H / 2), "r": (W, H / 2)}.items()]
            moving = self._moving_ids()
            start = self._drag.get("anchor") if moving else None
            for e in self.doc.entities:
                if e.HAS_POS and e.id not in moving:
                    x, y = e.v(ev, "x"), e.v(ev, "y")
                    # al arrastrar, no atraer al punto de partida (p. ej. la escala concéntrica de un
                    # potenciómetro): si no, el elemento parece pegado y vuelve a su sitio
                    if start is not None and abs(x - start[0]) < 1e-6 and abs(y - start[1]) < 1e-6:
                        continue
                    cands.append(((x, y), {"ref": e.id, "anchor": "c"}))
            for (x, y), ref in cands:
                d = math.hypot(x - wx, y - wy)
                if d < tol and (best is None or d < best[0]):
                    best = (d, x, y, ref)
            if best:
                self._snap_ref = best[3]
                self._snap_mark = (best[1], best[2])
                return best[1], best[2]
        if st.get("snap_grid", True):
            g = float(st.get("grid", 2.5)) or 1.0
            return round(wx / g) * g, round(wy / g) * g
        return wx, wy

    def _moving_ids(self):
        return self.selected if (self._drag and self._drag.get("kind") == "move") else ()

    # ------------------------------------------------------------ dibujo
    @safe_paint
    def paintEvent(self, _ev):
        c = self.colors()
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(c["canvas"]))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_grid(p, c)
        p.save()
        p.translate(self.ox, self.oy)
        p.scale(self.s, -self.s)
        render.paint_document(p, self.doc, self.items(), mode="edit", colors=c, selected=self.selected,
                              flagged=self.flagged, show_ref=self.show_ref, show_footprint=self.show_footprint,
                              show_dims=self.show_dims, px_per_mm=self.s)
        self._paint_preview(p, c)
        p.restore()
        if self.show_dims and self.auto_dims != "off":
            self._paint_auto_dims(p, c)
        self._paint_overlays(p, c)
        self._paint_rulers(p, c)
        p.end()

    def _grid_step(self):
        g = float(self.doc.settings.get("grid", 2.5)) or 1.0
        major = int(self.doc.settings.get("grid_major", 5)) or 5
        step = g
        while step * self.s < 7:
            step *= major
        return step, step * major

    def _paint_grid(self, p, c):
        step, major = self._grid_step()
        x0, y1 = self.s2w(QPointF(0, 0))
        x1, y0 = self.s2w(QPointF(self.width(), self.height()))
        for (st, col) in ((step, c["grid_minor"]), (major, c["grid_major"])):
            p.setPen(QPen(QColor(col), 1))
            i0, i1 = int(math.floor(x0 / st)), int(math.ceil(x1 / st))
            if i1 - i0 > 1500:
                continue
            for i in range(i0, i1 + 1):
                sx = self.ox + i * st * self.s
                p.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            j0, j1 = int(math.floor(y0 / st)), int(math.ceil(y1 / st))
            for j in range(j0, j1 + 1):
                sy = self.oy - j * st * self.s
                p.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
        # ejes del origen
        p.setPen(QPen(QColor(c["accent"]).darker(130), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(self.ox, 0), QPointF(self.ox, self.height()))
        p.drawLine(QPointF(0, self.oy), QPointF(self.width(), self.oy))

    def _preview_prims(self):
        """Primitivas temporales de la herramienta activa (coords. mundo)."""
        out = []
        cx, cy = self._cursor_w
        if self._drag and self._drag.get("kind") == "create":
            e = self._make_drag_entity(self._drag["p0"], (cx, cy))
            if e is not None:
                ev = self.doc.evaluator()
                out += [pr for _r, pr in e.geometry(self.doc, ev)]
        elif self.tool in CLICK_TOOLS:
            e = self._make_click_entity((cx, cy), preview=True)
            if e is not None:
                ev = self.doc.evaluator()
                out += [pr for _r, pr in e.geometry(self.doc, ev) if pr["t"] != "text"]
        if self.tool == "polyline" and self._poly_pts:
            out.append({"t": "poly", "pts": self._poly_pts + [(cx, cy)], "closed": False})
        if self.tool in ("dimension", "measure") and self._click_pts:
            out.append({"t": "poly", "pts": [self._click_pts[0][0], (cx, cy)], "closed": False})
        return out

    def _paint_preview(self, p, c):
        prims = self._preview_prims()
        if not prims:
            return
        closed, opened = QPainterPath(), QPainterPath()
        closed.setFillRule(Qt.FillRule.OddEvenFill)
        for pr in prims:
            render.add_prim(closed if (pr["t"] == "circle" or pr.get("closed", True)) else opened, pr)
        col = QColor(c["snap"])
        fill = QColor(col)
        fill.setAlpha(70)
        p.setPen(render.pen(col.name(), 2.0, True))
        p.setBrush(QBrush(fill))
        p.drawPath(closed)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(opened)

    def _preview_size_text(self):
        """Medida en vivo de la forma que se está creando."""
        d = self._drag
        if not (d and d.get("kind") == "create"):
            return None
        (x0, y0), (x1, y1) = d["p0"], self._cursor_w
        if self.tool in ("circle", "polygon"):
            return f"Ø {2 * math.hypot(x1 - x0, y1 - y0):.2f} mm"
        if self.tool == "oval":
            return f"{max(math.hypot(x1 - x0, y1 - y0), 5.0):.2f} mm"
        return f"{abs(x1 - x0):.2f} × {abs(y1 - y0):.2f} mm"

    # ------------------------------------------------------------ cotas automáticas
    def _dim_targets(self):
        """[(entidad, bbox_mecanizado, bbox_total, centro, diámetro|None)] — en caché por revisión."""
        key = (self.doc.revision, self.show_footprint)
        if self._dim_cache[0] == key:
            return self._dim_cache[1]
        out = autodims.targets(self.doc, self.doc.evaluator(), self.show_footprint)
        self._dim_cache = (key, out)
        return out

    def _dim_line(self, p, a, b, fa, fb, text, color):
        """Cota en pantalla: a-b línea de cota, fa/fb puntos de la pieza (líneas de referencia)."""
        pn = QPen(color, 1)
        p.setPen(pn)
        for f_, q in ((fa, a), (fb, b)):
            dx, dy = q.x() - f_.x(), q.y() - f_.y()
            L = math.hypot(dx, dy)
            if L > 1:
                ux, uy = dx / L, dy / L
                p.drawLine(QPointF(f_.x() + ux * 2, f_.y() + uy * 2), QPointF(q.x() + ux * 4, q.y() + uy * 4))
        p.drawLine(a, b)
        L = math.hypot(b.x() - a.x(), b.y() - a.y())
        if L < 2:
            return
        ux, uy = (b.x() - a.x()) / L, (b.y() - a.y()) / L
        al = min(7.0, L / 3)
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen)
        for tip, sg in ((a, 1), (b, -1)):
            bx, by = tip.x() + ux * al * sg, tip.y() + uy * al * sg
            p.drawPolygon(QPolygonF([tip, QPointF(bx - uy * 2.6, by + ux * 2.6), QPointF(bx + uy * 2.6, by - ux * 2.6)]))
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        fm = p.fontMetrics()
        tw, th = fm.horizontalAdvance(text) + 6, fm.height()
        mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
        p.save()
        p.translate(mid)
        if abs(uy) > abs(ux):
            p.rotate(-90)
        r = QRectF(-tw / 2, -th / 2, tw, th)
        bg = QColor(self.colors()["canvas"])
        bg.setAlpha(215)
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(r, 3, 3)
        p.setPen(color)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        p.restore()
        p.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_auto_dims(self, p, c):
        mode = self.auto_dims
        targets = self._dim_targets()
        if len(targets) > 400 and mode in ("all", "size_all"):
            mode = "selection"
        size_col = QColor([L.color for L in self.doc.layers if L.process == "dim"][0]
                          if any(L.process == "dim" for L in self.doc.layers) else "#2fb67c")
        pos_col = QColor(c["snap"])
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        for e, main, full, (cx, cy), dia in targets:
            sel = e.id in self.selected
            show_size = mode in ("all", "size_all") or (mode == "selection" and sel)
            show_pos = mode == "all" or sel
            if not (show_size or show_pos):
                continue
            # rectángulos en pantalla
            m0, m1 = self.w2s(main[0], main[1]), self.w2s(main[2], main[3])
            f0, f1 = self.w2s(full[0], full[1]), self.w2s(full[2], full[3])
            mx0, mx1, my_top, my_bot = m0.x(), m1.x(), m1.y(), m0.y()
            fx0, fx1, fy_top, fy_bot = f0.x(), f1.x(), f1.y(), f0.y()
            if mx1 - mx0 < 6 and my_bot - my_top < 6:
                show_size = False
            if show_size:
                yb = fy_bot + 12
                if dia is not None:
                    self._dim_line(p, QPointF(mx0, yb), QPointF(mx1, yb), QPointF(mx0, my_bot - (my_bot - my_top) / 2),
                                   QPointF(mx1, my_bot - (my_bot - my_top) / 2), f"Ø{dia:.2f}".rstrip("0").rstrip("."),
                                   size_col)
                else:
                    w_mm, h_mm = main[2] - main[0], main[3] - main[1]
                    self._dim_line(p, QPointF(mx0, yb), QPointF(mx1, yb), QPointF(mx0, my_bot), QPointF(mx1, my_bot),
                                   _num(w_mm), size_col)
                    xr = fx1 + 12
                    self._dim_line(p, QPointF(xr, my_bot), QPointF(xr, my_top), QPointF(mx1, my_bot),
                                   QPointF(mx1, my_top), _num(h_mm), size_col)
            if show_pos:
                cs = self.w2s(cx, cy)
                yt = fy_top - 12
                left = self.w2s(0, cy)
                self._dim_line(p, QPointF(left.x(), yt), QPointF(cs.x(), yt), QPointF(left.x(), yt + 8),
                               QPointF(cs.x(), cs.y()), "X " + _num(cx), pos_col)
                xl = fx0 - 12
                bot = self.w2s(cx, 0)
                self._dim_line(p, QPointF(xl, bot.y()), QPointF(xl, cs.y()), QPointF(xl + 8, bot.y()),
                               QPointF(cs.x(), cs.y()), "Y " + _num(cy), pos_col)

    def _paint_overlays(self, p, c):
        # ventana de selección
        if self._drag and self._drag.get("kind") == "band":
            a, b = self._drag["s0"], self._drag["s1"]
            r = QRectF(a, b).normalized()
            crossing = b.x() < a.x()
            col = QColor(c["accent"])
            p.setPen(QPen(col, 1, Qt.PenStyle.DashLine if crossing else Qt.PenStyle.SolidLine))
            col.setAlpha(35)
            p.setBrush(QBrush(col))
            p.drawRect(r)
        # medida en vivo durante la creación
        txt = self._preview_size_text()
        if txt:
            sp = self.w2s(*self._cursor_w)
            f = QFont()
            f.setPointSize(9)
            f.setBold(True)
            p.setFont(f)
            br = p.fontMetrics().boundingRect(txt)
            r = QRectF(sp.x() + 14, sp.y() + 14, br.width() + 12, br.height() + 6)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(c["panel"])))
            p.drawRoundedRect(r, 4, 4)
            p.setPen(QColor(c["snap"]))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, txt)
        # marca de ajuste
        if self._snap_mark and self.tool != "pan":
            sp = self.w2s(*self._snap_mark)
            p.setPen(QPen(QColor(c["snap"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(sp.x() - 5, sp.y() - 5, 10, 10))
        # medición
        if self._measure:
            a, b = self._measure
            sa, sb = self.w2s(*a), self.w2s(*b)
            p.setPen(QPen(QColor(c["snap"]), 1.5))
            p.drawLine(sa, sb)
            for s_ in (sa, sb):
                p.drawEllipse(s_, 3, 3)
            dx, dy = b[0] - a[0], b[1] - a[1]
            txt = f"{math.hypot(dx, dy):.3f} mm  (ΔX {dx:.3f}  ΔY {dy:.3f}  {math.degrees(math.atan2(dy, dx)):.1f}°)"  # noqa
            f = QFont()
            f.setPointSize(9)
            p.setFont(f)
            mid = QPointF((sa.x() + sb.x()) / 2 + 8, (sa.y() + sb.y()) / 2 - 8)
            br = p.fontMetrics().boundingRect(txt)
            p.fillRect(QRectF(mid.x() - 4, mid.y() - br.height(), br.width() + 8, br.height() + 6),
                       QColor(c["panel"]))
            p.setPen(QColor(c["text"]))
            p.drawText(mid, txt)
        # cruz del cursor en herramientas de dibujo
        if self.tool not in ("select", "pan") and self.underMouse():
            sp = self.w2s(*self._cursor_w)
            p.setPen(QPen(QColor(c["muted"]), 1, Qt.PenStyle.DotLine))
            p.drawLine(QPointF(sp.x(), RULER), QPointF(sp.x(), self.height()))
            p.drawLine(QPointF(RULER, sp.y()), QPointF(self.width(), sp.y()))

    def _paint_rulers(self, p, c):
        f = QFont()
        f.setPointSize(7)
        p.setFont(f)
        p.fillRect(QRectF(0, 0, self.width(), RULER), QColor(c["ruler"]))
        p.fillRect(QRectF(0, 0, RULER, self.height()), QColor(c["ruler"]))
        p.setPen(QPen(QColor(c["border"]), 1))
        p.drawLine(QPointF(0, RULER), QPointF(self.width(), RULER))
        p.drawLine(QPointF(RULER, 0), QPointF(RULER, self.height()))
        step = 1.0
        for cand in (0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
            step = cand
            if cand * self.s >= 55:
                break
        minor = step / 5
        p.setPen(QPen(QColor(c["ruler_text"]), 1))
        x0, _ = self.s2w(QPointF(RULER, 0))
        x1, _ = self.s2w(QPointF(self.width(), 0))
        i0, i1 = int(math.floor(x0 / minor)), int(math.ceil(x1 / minor))
        for i in range(i0, i1 + 1):
            x = i * minor
            sx = self.ox + x * self.s
            if sx < RULER:
                continue
            major = abs((x / step) - round(x / step)) < 1e-6
            p.drawLine(QPointF(sx, RULER - (9 if major else 4)), QPointF(sx, RULER))
            if major:
                p.drawText(QPointF(sx + 2, 9), f"{x:g}")
        _, y1 = self.s2w(QPointF(0, RULER))
        _, y0 = self.s2w(QPointF(0, self.height()))
        j0, j1 = int(math.floor(y0 / minor)), int(math.ceil(y1 / minor))
        for j in range(j0, j1 + 1):
            y = j * minor
            sy = self.oy - y * self.s
            if sy < RULER:
                continue
            major = abs((y / step) - round(y / step)) < 1e-6
            p.drawLine(QPointF(RULER - (9 if major else 4), sy), QPointF(RULER, sy))
            if major:
                p.save()
                p.translate(9, sy - 2)
                p.rotate(-90)
                p.drawText(QPointF(0, 0), f"{y:g}")
                p.restore()
        # posición del cursor
        sp = self.w2s(*self._cursor_w)
        p.setPen(QPen(QColor(c["accent"]), 1))
        if sp.x() > RULER:
            p.drawLine(QPointF(sp.x(), 0), QPointF(sp.x(), RULER))
        if sp.y() > RULER:
            p.drawLine(QPointF(0, sp.y()), QPointF(RULER, sp.y()))
        p.fillRect(QRectF(0, 0, RULER, RULER), QColor(c["ruler"]))

    # ------------------------------------------------------------ selección
    def hit_test(self, wx, wy) -> Optional[str]:
        from ..core.hittest import hit_test
        return hit_test(self.doc, self.items(), wx, wy, 5.0 / self.s, self.show_footprint)

    def band_select(self, a: QPointF, b: QPointF, add: bool):
        (x0, y0), (x1, y1) = self.s2w(a), self.s2w(b)
        rx0, rx1, ry0, ry1 = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
        crossing = b.x() < a.x()
        ev = self.doc.evaluator()
        sel = set(self.selected) if add else set()
        for e in self.doc.entities:
            L = self.doc.layer(e.layer)
            if L is not None and (L.locked or not L.visible):
                continue
            bb = e.bbox(self.doc, ev)
            inside = bb[0] >= rx0 and bb[2] <= rx1 and bb[1] >= ry0 and bb[3] <= ry1
            touch = not (bb[2] < rx0 or bb[0] > rx1 or bb[3] < ry0 or bb[1] > ry1)
            if inside or (crossing and touch):
                sel.add(e.id)
        self.set_selection(sel)

    # ------------------------------------------------------------ creación
    def _layer_for(self, e):
        if e.DEFAULT_LAYER in ("pocket", "print", "dim") and self.doc.layer(e.DEFAULT_LAYER):
            return e.DEFAULT_LAYER
        return self.mw.active_layer

    def _make_drag_entity(self, p0, p1):
        (x0, y0), (x1, y1) = p0, p1
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = abs(x1 - x0), abs(y1 - y0)
        r = math.hypot(x1 - x0, y1 - y0)
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        t = self.tool
        small = r < 0.3
        if t == "rect":
            return RectEntity(x=cx, y=cy, **({} if small else {"w": round(w, 4), "h": round(h, 4)}))
        if t == "roundrect":
            e = RoundRectEntity(x=cx, y=cy, **({} if small else {"w": round(w, 4), "h": round(h, 4)}))
            if not small:
                e.p["r"] = round(min(3.0, w / 4, h / 4), 3)
            return e
        if t == "slot":
            return SlotEntity(x=cx, y=cy, **({} if small else {"w": round(w, 4), "h": round(h, 4)}))
        if t == "pocket":
            return PocketEntity(x=cx, y=cy, **({} if small else {"w": round(w, 4), "h": round(h, 4)}))
        if t == "ellipse":
            return EllipseEntity(x=cx, y=cy, **({} if small else {"w": round(w, 4), "h": round(h, 4)}))
        if t == "circle":
            return CircleEntity(x=x0, y=y0, **({} if small else {"d": round(2 * r, 4)}))
        if t == "polygon":
            return PolygonEntity(x=x0, y=y0, **({} if small else {"d": round(2 * r, 4), "rot": round(ang - 90, 3)}))
        if t == "oval":
            e = OvalSlotEntity(x=cx, y=cy)
            if not small:
                e.p["l"] = round(max(r, 5.0), 4)
                e.p["rot"] = round(ang, 3)
            return e
        return None

    def _make_click_entity(self, pt, preview=False):
        x, y = pt
        t = self.tool
        if t == "hole":
            return HoleEntity(x=x, y=y, kind="montaje", screw="M3")
        if t == "hole_csk":
            return HoleEntity(x=x, y=y, kind="avellanado", screw="M3")
        if t == "hole_thread":
            return HoleEntity(x=x, y=y, kind="roscado", screw="M3")
        if t == "dhole":
            return DHoleEntity(x=x, y=y)
        if t == "text":
            return TextEntity(x=x, y=y, text="Texto") if preview else None
        if t in ("component", "place") and self.place_entity is not None:
            e = self.place_entity.clone()
            e.set_pos(x, y)
            return e
        return None

    def _commit_new(self, e, label):
        if e is None:
            return
        if not (self.tool == "place" and self.doc.layer(e.layer)):
            e.layer = self._layer_for(e) if e.TYPE not in ("image", "path") else (e.layer or self.mw.active_layer)
        self.mw.checkpoint(label)
        self.doc.add(e)
        self.mw.changed()
        self.set_selection([e.id])

    # ------------------------------------------------------------ eventos
    def mousePressEvent(self, ev):
        pos = ev.position()
        wx, wy = self.s2w(pos)
        btn = ev.button()
        if btn == Qt.MouseButton.MiddleButton or (btn == Qt.MouseButton.LeftButton and (self._space or self.tool == "pan")):
            self._pan_last = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if btn == Qt.MouseButton.RightButton:
            if self.tool == "polyline" and len(self._poly_pts) >= 2:
                self._finish_polyline()
                return
            if self.tool != "select":
                self.set_tool("select")
                return
            hit = self.hit_test(wx, wy)
            if hit and hit not in self.selected:
                self.set_selection([hit])
            self.mw.canvas_context_menu(ev.globalPosition().toPoint())
            return
        if btn != Qt.MouseButton.LeftButton:
            return
        sx, sy = self.snap(wx, wy)
        if self._drag and self._drag.get("kind") == "create" and self._drag.get("pending"):
            # segundo clic del modo «clic-clic»
            e = self._make_drag_entity(self._drag["p0"], (sx, sy))
            self._drag = None
            self._commit_new(e, tr("Añadir {n}").format(n=tr(e.LABEL).lower()) if e else "")
            self.update()
            return
        shift = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        t = self.tool
        if t == "select":
            hit = self.hit_test(wx, wy)
            if hit:
                if shift:
                    sel = set(self.selected)
                    sel ^= {hit}
                    self.set_selection(sel)
                    return
                if hit not in self.selected:
                    self.set_selection([hit])
                ref = self.doc.get(hit)
                ev_ = self.doc.evaluator()
                anchor = ref.anchor(self.doc, ev_, "c") if ref is not None else (wx, wy)
                self._drag = {"kind": "move", "start": (wx, wy), "anchor": anchor, "applied": (0.0, 0.0),
                              "started": False}
            else:
                self._drag = {"kind": "band", "s0": pos, "s1": pos, "add": shift}
        elif t in DRAG_TOOLS:
            self._drag = {"kind": "create", "p0": (sx, sy), "s0": pos, "pending": False}
        elif t in CLICK_TOOLS:
            if t == "text":
                self.mw.place_text(sx, sy)
                return
            e = self._make_click_entity((sx, sy))
            self._commit_new(e, f"Añadir {e.display_name() if e else ''}")
            if t == "place":
                self.set_tool("select")
        elif t == "polyline":
            self._poly_pts.append((sx, sy))
        elif t in ("dimension", "measure"):
            self._click_pts.append(((sx, sy), self._snap_ref))
            if len(self._click_pts) == 2:
                (a, ra), (b, rb) = self._click_pts
                self._click_pts = []
                if t == "measure":
                    self._measure = (a, b)
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    self.message.emit(tr("Distancia {d} mm · ΔX {dx} · ΔY {dy} · ángulo {a}°").format(
                        d=f"{math.hypot(dx, dy):.3f}", dx=f"{dx:.3f}", dy=f"{dy:.3f}",
                        a=f"{math.degrees(math.atan2(dy, dx)):.2f}"))
                else:
                    orient = "h" if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else "v"
                    d = DimensionEntity(orient=orient, offset=8.0 if orient == "h" else -8.0,
                                        a=ra or {"xy": list(a)}, b=rb or {"xy": list(b)})
                    self._commit_new(d, "Añadir cota")
        self.update()

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        if self._pan_last is not None:
            d = pos - self._pan_last
            self.ox += d.x()
            self.oy += d.y()
            self._pan_last = pos
            self.update()
            return
        wx, wy = self.s2w(pos)
        drag = self._drag
        if drag and drag["kind"] == "move":
            dx, dy = wx - drag["start"][0], wy - drag["start"][1]
            if not drag["started"] and math.hypot(dx, dy) * self.s < 3:
                return
            ax, ay = drag["anchor"]
            tx, ty = self.snap(ax + dx, ay + dy)
            dx, dy = tx - ax, ty - ay
            movable = [e for e in (self.doc.get(i) for i in self.selected) if e is not None and not e.locked
                       and not (self.doc.layer(e.layer) and self.doc.layer(e.layer).locked)]
            if not drag["started"]:
                drag["started"] = True
                self.mw.checkpoint("Mover")
            ddx, ddy = dx - drag["applied"][0], dy - drag["applied"][1]
            if abs(ddx) > 1e-9 or abs(ddy) > 1e-9:
                for e in movable:
                    e.move(ddx, ddy)
                drag["applied"] = (dx, dy)
                self.doc.touch()
            self._cursor_w = (tx, ty)
            self.cursorMoved.emit(tx, ty)
            self.update()
            return
        if drag and drag["kind"] == "band":
            drag["s1"] = pos
            self.update()
            return
        sx, sy = self.snap(wx, wy, objects=self.tool != "select")
        if self.tool == "select":
            self._snap_mark = None
        self._cursor_w = (sx, sy)
        self.cursorMoved.emit(sx, sy)
        self.update()

    def mouseReleaseEvent(self, ev):
        if self._pan_last is not None:
            self._pan_last = None
            self.setCursor(Qt.CursorShape.ArrowCursor if self.tool == "select" else
                           Qt.CursorShape.OpenHandCursor if self.tool == "pan" else Qt.CursorShape.CrossCursor)
            return
        drag = self._drag
        self._drag = None
        if not drag:
            return
        if drag["kind"] == "move":
            if drag["started"]:
                self.mw.changed(refresh_props=True)
        elif drag["kind"] == "band":
            a, b = drag["s0"], drag["s1"]
            if (a - b).manhattanLength() < 4:
                if not drag["add"]:
                    self.set_selection([])
            else:
                self.band_select(a, b, drag["add"])
        elif drag["kind"] == "create":
            if (ev.position() - drag["s0"]).manhattanLength() < 5:
                # clic sin arrastrar: la forma sigue al cursor hasta el segundo clic
                drag["pending"] = True
                self._drag = drag
                self.message.emit(tr("Haga clic en el segundo punto · Esc para cancelar"))
                self.update()
                return
            e = self._make_drag_entity(drag["p0"], self._cursor_w)
            self._commit_new(e, tr("Añadir {n}").format(n=tr(e.LABEL).lower()) if e else "")
        self.update()

    def mouseDoubleClickEvent(self, ev):
        if self.tool == "polyline":
            self._finish_polyline()
            return
        if self.tool == "select":
            wx, wy = self.s2w(ev.position())
            hit = self.hit_test(wx, wy)
            e = self.doc.get(hit) if hit else None
            if e is not None and e.TYPE == "text":
                self.mw.edit_text(e)
            elif e is not None and e.TYPE == "scale":
                self.mw.edit_scale(e)
            elif e is not None and e.TYPE == "stud":
                self.mw.edit_stud(e)

    def _finish_polyline(self):
        pts = G.dedupe(self._poly_pts)
        self._poly_pts = []
        if len(pts) >= 2:
            b = G.bbox(pts)
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            e = PolylineEntity(x=round(cx, 4), y=round(cy, 4),
                               pts=[[round(x - cx, 4), round(y - cy, 4)] for x, y in pts], closed=len(pts) >= 3)
            self._commit_new(e, "Añadir polígono")
        self.update()

    def wheelEvent(self, ev):
        d = ev.angleDelta().y()
        if d:
            self.zoom(1.15 ** (d / 120.0), ev.position())

    def keyPressEvent(self, ev):
        k = ev.key()
        mods = ev.modifiers()
        if k == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        if k == Qt.Key.Key_Escape:
            if self._drag and self._drag.get("kind") == "create":
                self._drag = None
            elif self._poly_pts or self._click_pts:
                self._poly_pts, self._click_pts = [], []
            elif self.tool != "select":
                self.set_tool("select")
            else:
                self.set_selection([])
            self._measure = None
            self.update()
            return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.tool == "polyline":
            self._finish_polyline()
            return
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.mw.delete_selected()
            return
        arrows = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0), Qt.Key.Key_Up: (0, 1), Qt.Key.Key_Down: (0, -1)}
        if k in arrows and self.selected:
            step = float(self.doc.settings.get("grid", 2.5))
            if mods & Qt.KeyboardModifier.ShiftModifier:
                step *= 10
            if mods & Qt.KeyboardModifier.ControlModifier:
                step = 0.1
            dx, dy = arrows[k]
            self.mw.nudge(dx * step, dy * step)
            return
        super().keyPressEvent(ev)

    def keyReleaseEvent(self, ev):
        if ev.key() == Qt.Key.Key_Space and not ev.isAutoRepeat():
            self._space = False
            self.set_tool(self.tool)
            return
        super().keyReleaseEvent(ev)

    def leaveEvent(self, _ev):
        self.update()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if not self._fitted and self.width() > 100:
            self._fitted = True
            self.fit_view()
