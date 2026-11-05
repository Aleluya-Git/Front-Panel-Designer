"""Vista previa 3D realista con renderizado por software (QPainter).

No requiere OpenGL: funciona igual en Windows, Linux y macOS, también en
máquinas virtuales o escritorios remotos. Modelo: extrusión del panel según su
espesor, huecos pasantes, rebajes con profundidad, grabado y serigrafía en la
cara superior. Iluminación direccional + especular para metales.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget)

from ..core.document import MATERIALS
from ..io import mesh as M
from ..i18n import tr
from ..io.common import collect
from .safepaint import safe_paint


def _norm(v):
    L = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
    return (v[0] / L, v[1] / L, v[2] / L)


LIGHT = _norm((-0.45, 0.55, 0.85))
HALF = _norm((LIGHT[0], LIGHT[1], LIGHT[2] + 1.0))


class View3D(QWidget):
    def __init__(self, doc=None):
        super().__init__()
        self.setMinimumSize(480, 360)
        self.yaw, self.pitch, self.zoom_k = -18.0, -58.0, 1.0
        self.pan = QPointF(0, 0)
        self.show_marks = True
        self._last = None
        self.model = None
        self.doc = None
        if doc is not None:
            self.set_doc(doc)

    def set_doc(self, doc):
        self.doc = doc
        self.model = M.build_view_model(doc)
        ev = doc.evaluator()
        self.W, self.H, self.T, _r = doc.panel_dims(ev)
        self.marks = [(role, pr) for role, pr, _e in collect(doc, ("engrave", "print"))]
        self.update()

    def set_view(self, yaw, pitch):
        self.yaw, self.pitch = yaw, pitch
        self.pan = QPointF(0, 0)
        self.zoom_k = 1.0
        self.update()

    # ------------------------------------------------------------ proyección
    def _setup(self):
        self._cy, self._sy = math.cos(math.radians(self.yaw)), math.sin(math.radians(self.yaw))
        self._cp, self._sp = math.cos(math.radians(self.pitch)), math.sin(math.radians(self.pitch))
        diag = math.hypot(self.W, self.H) or 1.0
        self._k = min(self.width(), self.height()) * 0.85 / diag * self.zoom_k
        self._c = (self.W / 2, self.H / 2, self.T / 2)

    def _rot(self, v):
        x1 = v[0] * self._cy - v[1] * self._sy
        y1 = v[0] * self._sy + v[1] * self._cy
        z1 = v[2]
        return (x1, y1 * self._cp - z1 * self._sp, y1 * self._sp + z1 * self._cp)

    def project(self, x, y, z):
        r = self._rot((x - self._c[0], y - self._c[1], z - self._c[2]))
        return QPointF(self.width() / 2 + self.pan.x() + r[0] * self._k,
                       self.height() / 2 + self.pan.y() - r[1] * self._k), r[2]

    def _shade(self, base: QColor, n, metal: bool, alpha: float) -> QColor:
        d = max(0.0, n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2])
        k = 0.38 + 0.62 * d
        spec = (max(0.0, n[0] * HALF[0] + n[1] * HALF[1] + n[2] * HALF[2]) ** (28 if metal else 60)) * (0.55 if metal else 0.25)
        r = min(255, int(base.red() * k + 255 * spec))
        g = min(255, int(base.green() * k + 255 * spec))
        b = min(255, int(base.blue() * k + 255 * spec))
        return QColor(r, g, b, int(255 * alpha))

    # ------------------------------------------------------------ dibujo
    @safe_paint
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0, 0, 0, self.height())
        g.setColorAt(0, QColor("#3a4049"))
        g.setColorAt(1, QColor("#16181c"))
        p.fillRect(self.rect(), QBrush(g))
        if not self.model:
            p.end()
            return
        self._setup()
        mat = MATERIALS.get(self.doc.panel.material, MATERIALS["Aluminio"])
        metal = mat.get("metal", False) and self.doc.panel.finish not in ("Pintado mate", "Pintado brillo", "Lacado")
        alpha = mat.get("alpha", 1.0)
        base = QColor(self.doc.panel.color)
        edge_base = base.darker(115) if self.doc.panel.finish == "Anodizado" else base
        top_n = self._rot((0, 0, 1))
        top_visible = top_n[2] > 0
        # sombra
        sh = QPainterPath()
        for x, y in self.model["bottom"][0]:
            pt, _z = self.project(x, y, -self.T * 0.0)
            if sh.elementCount() == 0:
                sh.moveTo(pt + QPointF(10, 14))
            else:
                sh.lineTo(pt + QPointF(10, 14))
        sh.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawPath(sh)
        # cara oculta (inferior o superior)
        far_polys = self.model["bottom"] if top_visible else self.model["top"]
        far_z = 0.0 if top_visible else self.T
        if alpha < 1.0:
            self._cap(p, far_polys, far_z, self._shade(base, self._rot((0, 0, -1 if top_visible else 1)), metal, alpha))
        # suelos de rebaje
        if top_visible:
            for polys, z in self.model["floors"]:
                self._cap(p, polys, z, self._shade(base.darker(108), top_n, metal, alpha))
        else:
            for polys, z in self.model.get("floors_back", []):
                self._cap(p, polys, z, self._shade(base.darker(108), self._rot((0, 0, -1)), metal, alpha))
        # paredes ordenadas por profundidad
        walls = []
        for a, b, c, d, group in self.model["walls"]:
            nx, ny = (b[1] - a[1]), -(b[0] - a[0])
            n = self._rot(_norm((nx, ny, 0.0)))
            if n[2] <= 0 and alpha >= 1.0:
                continue
            pts, zs = [], 0.0
            for v in (a, b, c, d):
                q, z = self.project(*v)
                pts.append(q)
                zs += z
            walls.append((zs / 4, pts, n, group))
        walls.sort(key=lambda w: w[0])
        for _z, pts, n, group in walls:
            col = self._shade(edge_base if group == "panel" else base.darker(110), n, metal, alpha)
            p.setPen(QPen(col, 0.6))
            p.setBrush(col)
            p.drawPolygon(QPolygonF(pts))
        # cara visible
        near_polys = self.model["top"] if top_visible else self.model["bottom"]
        near_z = self.T if top_visible else 0.0
        near_n = top_n if top_visible else self._rot((0, 0, -1))
        self._cap(p, near_polys, near_z, self._shade(base, near_n, metal, alpha), outline=True)
        if top_visible and self.show_marks:
            self._marks(p)
        # rótulo
        p.setPen(QColor("#c8cdd4"))
        f = QFont()
        f.setPointSize(9)
        p.setFont(f)
        mat_name = self.doc.panel.material_name or tr(self.doc.panel.material)
        p.drawText(QPointF(12, self.height() - 12),
                   f"{self.W:.1f} × {self.H:.1f} × {self.T:.2f} mm · {mat_name} · {tr(self.doc.panel.finish)}   ("
                   + tr("arrastrar: girar · botón derecho: mover · rueda: zoom · doble clic: restablecer") + ")")
        p.end()

    def _cap(self, p, polys, z, color, outline=False):
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.OddEvenFill)
        for poly in polys:
            first = True
            for x, y in poly:
                q, _ = self.project(x, y, z)
                if first:
                    path.moveTo(q)
                    first = False
                else:
                    path.lineTo(q)
            path.closeSubpath()
        p.setPen(QPen(color.darker(125), 0.8) if outline else Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawPath(path)

    def _marks(self, p):
        z = self.T + 0.01
        pc = QColor(self.doc.panel.print_color)
        ec = QColor(40, 42, 46)
        groups = []
        for role in ("engrave", "print"):
            for col in sorted({pr.get("color") or "" for r, pr in self.marks if r == role}):
                groups.append((role, col))
        for role, colkey in groups:
            closed = QPainterPath()
            closed.setFillRule(Qt.FillRule.OddEvenFill)
            opened = QPainterPath()
            for r, pr in self.marks:
                if r != role or (pr.get("color") or "") != colkey:
                    continue
                if pr["t"] == "circle":
                    from ..core import geometry as G
                    pts, is_closed = G.circle_poly(pr["c"][0], pr["c"][1], pr["r"], 0.05), True
                elif pr["t"] == "poly":
                    pts, is_closed = pr["pts"], pr.get("closed", True)
                else:
                    continue
                path = closed if is_closed else opened
                for i, (x, y) in enumerate(pts):
                    q, _ = self.project(x, y, z)
                    if i == 0:
                        path.moveTo(q)
                    else:
                        path.lineTo(q)
                if is_closed:
                    path.closeSubpath()
            col = QColor(colkey) if colkey else (ec if role == "engrave" else pc)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(col)
            p.drawPath(closed)
            pen = QPen(col, max(1.0, 0.35 * self._k))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(opened)

    # ------------------------------------------------------------ ratón
    def mousePressEvent(self, e):
        self._last = (e.position(), e.button())

    def mouseMoveEvent(self, e):
        if not self._last:
            return
        pos, btn = self._last
        d = e.position() - pos
        if btn == Qt.MouseButton.LeftButton:
            self.yaw -= d.x() * 0.5
            self.pitch = max(-179.0, min(179.0, self.pitch - d.y() * 0.5))
        else:
            self.pan += d
        self._last = (e.position(), btn)
        self.update()

    def mouseReleaseEvent(self, _e):
        self._last = None

    def mouseDoubleClickEvent(self, _e):
        self.set_view(-18.0, -58.0)

    def wheelEvent(self, e):
        self.zoom_k = max(0.1, min(30.0, self.zoom_k * 1.15 ** (e.angleDelta().y() / 120.0)))
        self.update()


class View3DDialog(QDialog):
    def __init__(self, parent, doc, export_stl_cb):
        super().__init__(parent)
        self.setWindowTitle(tr("Vista previa 3D"))
        self.resize(1000, 700)
        v = QVBoxLayout(self)
        self.view = View3D(doc)
        v.addWidget(self.view, 1)
        row = QHBoxLayout()
        for text, yaw, pitch in ((tr("Isométrica"), -18.0, -58.0), (tr("Frontal"), 0.0, 0.0), (tr("Rasante"), 0.0, -80.0),
                                 (tr("Lateral"), -90.0, -20.0), (tr("Trasera"), 180.0, 45.0)):
            b = QPushButton(text)
            b.clicked.connect(lambda _c=False, y=yaw, pt=pitch: self.view.set_view(y, pt))
            row.addWidget(b)
        cb = QCheckBox(tr("Grabado / serigrafía"))
        cb.setChecked(True)
        cb.toggled.connect(lambda v_: (setattr(self.view, "show_marks", v_), self.view.update()))
        row.addWidget(cb)
        row.addStretch(1)
        b1 = QPushButton(tr("Capturar PNG…"))
        b1.clicked.connect(self._shot)
        b2 = QPushButton(tr("Exportar STL…"))
        b2.clicked.connect(export_stl_cb)
        b3 = QPushButton(tr("Cerrar"))
        b3.clicked.connect(self.accept)
        for b in (b1, b2, b3):
            row.addWidget(b)
        v.addLayout(row)

    def _shot(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("Guardar captura"), "panel_3d.png", "PNG (*.png)")
        if path:
            self.view.grab().save(path)
