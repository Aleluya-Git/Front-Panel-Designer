"""Vista previa de componentes: widget, miniaturas y tooltip con imagen."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from ..core import geometry as G
from ..core.entities import shape_prims, text_prims
from ..i18n import tr
from . import render
from .safepaint import safe_paint

STYLES = {"footprint": ("#8a8f98", Qt.PenStyle.DotLine, QColor(140, 145, 152, 30)),
          "reference": ("#9a8cff", Qt.PenStyle.DashLine, None),
          "cutouts": ("#e5484d", Qt.PenStyle.SolidLine, QColor(229, 72, 77, 55)),
          "graphics": ("#e3e6ea", Qt.PenStyle.SolidLine, None)}


def _groups(comp):
    groups = {k: [] for k in STYLES}
    b = None
    for key in groups:
        for s in comp.get(key, []) or []:
            try:
                if s.get("shape") == "text":
                    prs = text_prims(s.get("text", ""), "", float(s.get("size", 2.5)), False, False, "centro", 1.0,
                                     float(s.get("x", 0)), float(s.get("y", 0)))
                else:
                    prs = shape_prims(s)
            except (TypeError, ValueError, KeyError):
                continue
            for pr in prs:
                groups[key].append(pr)
                b = G.bbox_union(b, G.prim_bbox(pr))
    return groups, b


def paint_component(p: QPainter, comp: dict, w: int, h: int, bg="#262a31", legend=True, panel="#c9cdd2"):
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.fillRect(QRectF(0, 0, w, h), QColor(bg))
    if not comp:
        return
    groups, b = _groups(comp)
    if b is None:
        return
    bw, bh = max(1.0, b[2] - b[0]), max(1.0, b[3] - b[1])
    pad_b = 22 if legend else 8
    s = min((w - 16) / bw, (h - 8 - pad_b) / bh)
    p.save()
    p.translate(w / 2 - (b[0] + b[2]) / 2 * s, (h - pad_b + 8) / 2 + (b[1] + b[3]) / 2 * s)
    p.scale(s, -s)
    # chapa de fondo con los huecos
    plate = QPainterPath()
    plate.setFillRule(Qt.FillRule.OddEvenFill)
    m = max(bw, bh) * 0.08
    plate.addRect(QRectF(b[0] - m, b[1] - m, bw + 2 * m, bh + 2 * m))
    for pr in groups["cutouts"]:
        render.add_prim(plate, pr)
    p.setPen(Qt.PenStyle.NoPen)
    col = QColor(panel)
    col.setAlpha(45)
    p.setBrush(QBrush(col))
    p.drawPath(plate)
    for key in ("footprint", "reference", "cutouts", "graphics"):
        path = QPainterPath()
        for pr in groups[key]:
            render.add_prim(path, pr)
        c, style, fill = STYLES[key]
        pn = QPen(QColor(c), 1.4)
        pn.setCosmetic(True)
        pn.setStyle(style)
        p.setPen(pn)
        p.setBrush(QBrush(fill) if fill else Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    p.restore()
    if legend:
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        p.setPen(QColor("#c0c6ce"))
        p.drawText(QRectF(6, h - 20, w - 12, 18), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"{bw:.1f} × {bh:.1f} mm")
        x = w - 6
        for key, label in (("footprint", tr("cuerpo")), ("reference", tr("referencia")), ("cutouts", tr("mecanizado"))):
            fm = p.fontMetrics()
            tw = fm.horizontalAdvance(label)
            x -= tw
            p.setPen(QColor(STYLES[key][0]))
            p.drawText(QPointF(x, h - 7), label)
            x -= 10


def thumbnail(comp: dict, w: int = 240, h: int = 180, legend=True) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(QColor("#262a31"))
    p = QPainter(pm)
    try:
        paint_component(p, comp, w, h, legend=legend)
    except Exception:  # noqa: BLE001
        from .safepaint import report
        report("miniatura")
    finally:
        p.end()
    return pm


class ComponentPreview(QWidget):
    def __init__(self, min_h=200):
        super().__init__()
        self.comp = None
        self.setMinimumSize(220, min_h)

    def set_comp(self, comp):
        self.comp = comp
        self.update()

    @safe_paint
    def paintEvent(self, _e):
        p = QPainter(self)
        paint_component(p, self.comp, self.width(), self.height())
        if not self.comp:
            p.setPen(QColor("#8a94a3"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("Seleccione un componente"))
        p.end()


class ThumbTip(QFrame):
    """Tooltip propio con miniatura (los tooltips de Qt sólo muestran texto)."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("ThumbTip { background: #1b1e23; border: 1px solid #3d8bfd; border-radius: 6px; }"
                           "QLabel { color: #e3e6ea; background: transparent; }")
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        self.img = QLabel()
        self.txt = QLabel()
        self.txt.setWordWrap(True)
        self.txt.setMaximumWidth(260)
        v.addWidget(self.img)
        v.addWidget(self.txt)
        self.key = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_for(self, key, comp, html, gpos: QPoint):
        if key != self.key:
            self.key = key
            self.img.setPixmap(thumbnail(comp, 260, 190))
            self.txt.setText(html)
            self.adjustSize()
        scr = self.screen().availableGeometry() if self.screen() else None
        pos = gpos + QPoint(18, 18)
        if scr is not None:
            if pos.x() + self.width() > scr.right():
                pos.setX(gpos.x() - self.width() - 12)
            if pos.y() + self.height() > scr.bottom():
                pos.setY(scr.bottom() - self.height())
        self.move(pos)
        self.show()
        self._hide_timer.start(10000)

    def hide_tip(self):
        self.key = None
        self.hide()
