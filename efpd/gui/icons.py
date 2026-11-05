"""Iconos vectoriales en color generados en tiempo de ejecución (sin archivos externos).

Se dibujan sobre una rejilla de 32×32 y se rasterizan a 32/48/64/96 px, de modo
que se ven nítidos a cualquier tamaño de barra. Los colores son de categoría y
funcionan sobre tema claro y oscuro.
"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap)

_cache = {}

BLUE, LBLUE = "#2f81f7", "#9cc7ff"
RED, ORANGE, AMBER = "#f0484e", "#ff8a3d", "#f5b52a"
GREEN, TEAL, PURPLE, PINK = "#2fb67c", "#16b3b3", "#9b6bff", "#ec5fa8"
GREY, STEEL = "#8a94a3", "#c5ccd6"

FORMAT_COLORS = {"DXF": "#e5484d", "SVG": "#ff8a3d", "PDF": "#d6336c", "PNG": "#2fb67c", "STL": "#9b6bff",
                 "NC": "#16b3b3", "PLT": "#b0793b", "IMG": "#ec5fa8", "EFPD": "#2f81f7"}

RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resources")


def app_icon() -> QIcon:
    p = os.path.join(RESOURCES, "icon.png")
    ic = QIcon()
    if os.path.exists(p):
        pm = QPixmap(p)
        for s in (16, 24, 32, 48, 64, 128, 256, 512):
            ic.addPixmap(pm.scaled(s, s, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
    return ic


def app_pixmap(size: int = 128) -> QPixmap:
    p = os.path.join(RESOURCES, "icon.png")
    pm = QPixmap(p) if os.path.exists(p) else QPixmap(size, size)
    return pm.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


# ------------------------------------------------------------ utilidades de dibujo
def _c(col, a=255):
    c = QColor(col)
    c.setAlpha(a)
    return c


def _pen(col, w=2.0):
    pn = QPen(_c(col), w)
    pn.setCapStyle(Qt.PenCapStyle.RoundCap)
    pn.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pn


def _shape(p, path, col, fill_alpha=80, w=2.0, fill=None):
    p.setPen(_pen(col, w))
    p.setBrush(QBrush(_c(fill or col, fill_alpha)) if fill_alpha else Qt.BrushStyle.NoBrush)
    p.drawPath(path)


def _poly(pts, close=True):
    path = QPainterPath(QPointF(*pts[0]))
    for q in pts[1:]:
        path.lineTo(QPointF(*q))
    if close:
        path.closeSubpath()
    return path


def _rect(x, y, w, h, r=0.0):
    path = QPainterPath()
    if r:
        path.addRoundedRect(QRectF(x, y, w, h), r, r)
    else:
        path.addRect(QRectF(x, y, w, h))
    return path


def _ell(cx, cy, rx, ry=None):
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), rx, ry if ry is not None else rx)
    return path


def _text(p, rect, txt, col, px, bold=True):
    f = QFont()
    f.setPixelSize(px)
    f.setBold(bold)
    f.setStretch(87)  # semicondensada
    p.setFont(f)
    p.setPen(_c(col))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)


def _crosshair(p, cx, cy, col=GREY):
    p.setPen(_pen(col, 1.2))
    p.drawLine(QPointF(cx, cy - 13), QPointF(cx, cy + 13))
    p.drawLine(QPointF(cx - 13, cy), QPointF(cx + 13, cy))


def _file_badge(p, label, fg, arrow):
    """Documento con banda de color y el nombre del formato; flecha de importar/exportar."""
    col = FORMAT_COLORS.get(label, BLUE)
    doc = _poly([(6, 2), (21, 2), (27, 8), (27, 30), (6, 30)])
    g = QLinearGradient(0, 2, 0, 30)
    g.setColorAt(0, QColor("#ffffff"))
    g.setColorAt(1, QColor("#dfe4ea"))
    p.setPen(_pen("#5b6573", 1.3))
    p.setBrush(QBrush(g))
    p.drawPath(doc)
    p.setBrush(QBrush(QColor("#c4cbd4")))
    p.drawPath(_poly([(21, 2), (21, 8), (27, 8)]))
    band = _rect(1.5, 14, 29, 11, 2.5)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(_c(col)))
    p.drawPath(band)
    _text(p, QRectF(1.5, 14, 29, 11), label, "#ffffff", 9 if len(label) <= 3 else 7)
    # flecha
    p.setPen(_pen(col, 2.4))
    if arrow == "out":
        p.drawLine(QPointF(14, 11), QPointF(14, 4))
        p.drawPath(_poly([(10.5, 7.5), (14, 4), (17.5, 7.5)], False))
    else:
        p.drawLine(QPointF(14, 4), QPointF(14, 11))
        p.drawPath(_poly([(10.5, 7.5), (14, 11), (17.5, 7.5)], False))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _align(p, k):
    shapes = {
        "align_left": ((6, 7, 16, 7), (6, 18, 23, 7), "v", 5),
        "align_right": ((10, 7, 16, 7), (3, 18, 23, 7), "v", 27),
        "align_hcenter": ((8, 7, 16, 7), (4.5, 18, 23, 7), "v", 16),
        "align_top": ((7, 6, 7, 16), (18, 6, 7, 23), "h", 5),
        "align_bottom": ((7, 10, 7, 16), (18, 3, 7, 23), "h", 27),
        "align_vcenter": ((7, 8, 7, 16), (18, 4.5, 7, 23), "h", 16),
    }
    if k in shapes:
        a, b, orient, pos = shapes[k]
        _shape(p, _rect(*a, 1.5), ORANGE, 110, 1.6)
        _shape(p, _rect(*b, 1.5), AMBER, 110, 1.6)
        p.setPen(_pen(BLUE, 2.2))
        if orient == "v":
            p.drawLine(QPointF(pos, 2), QPointF(pos, 30))
        else:
            p.drawLine(QPointF(2, pos), QPointF(30, pos))
        return True
    if k == "dist_h":
        for x in (3, 13, 23):
            _shape(p, _rect(x, 9, 6, 14, 1.5), ORANGE, 110, 1.6)
        p.setPen(_pen(BLUE, 1.6))
        for x in (10.5, 20.5):
            p.drawLine(QPointF(x, 27), QPointF(x + 1, 27))
        return True
    if k == "dist_v":
        for y in (3, 13, 23):
            _shape(p, _rect(9, y, 14, 6, 1.5), ORANGE, 110, 1.6)
        return True
    if k == "dist_panel":
        _shape(p, _rect(2, 7, 28, 18, 2), STEEL, 90, 1.6, "#9aa6b5")
        for x in (8, 16, 24):
            _shape(p, _ell(x, 16, 3.2), ORANGE, 160, 1.6)
        p.setPen(_pen(BLUE, 1.4))
        p.drawLine(QPointF(2, 28.5), QPointF(30, 28.5))
        return True
    return False


def _draw(p: QPainter, key: str, fg: QColor):
    k = key
    fgn = fg.name()
    if k.startswith("exp_") or k.startswith("imp_"):
        _file_badge(p, k[4:], fgn, "out" if k.startswith("exp_") else "in")
        return
    if _align(p, k):
        return
    if k == "select":
        path = _poly([(8, 3), (8, 25), (13.5, 19.5), (17.5, 28), (21, 26.5), (17, 18.5), (24.5, 18.5)])
        p.setPen(_pen("#1b2330", 1.4))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawPath(path)
    elif k == "pan":
        p.setPen(_pen(BLUE, 2.2))
        for a in range(4):
            p.save()
            p.translate(16, 16)
            p.rotate(a * 90)
            p.drawLine(QPointF(0, -3), QPointF(0, -12))
            p.drawPath(_poly([(-3.5, -8.5), (0, -12.5), (3.5, -8.5)], False))
            p.restore()
        _shape(p, _ell(16, 16, 3), BLUE, 255, 1)
    elif k == "rect":
        _shape(p, _rect(4, 8, 24, 16), BLUE, 70)
    elif k == "roundrect":
        _shape(p, _rect(4, 8, 24, 16, 5), BLUE, 70)
    elif k == "slot":
        _shape(p, _rect(3, 12, 26, 8), RED, 70)
    elif k == "circle":
        _shape(p, _ell(16, 16, 11), BLUE, 70)
        _shape(p, _ell(16, 16, 1.3), BLUE, 255, 1)
    elif k == "ellipse":
        _shape(p, _ell(16, 16, 13, 8), BLUE, 70)
    elif k == "polygon":
        _shape(p, _poly([(16 + 12 * math.cos(math.radians(90 + i * 60)), 16 - 12 * math.sin(math.radians(90 + i * 60)))
                         for i in range(6)]), PURPLE, 70)
    elif k == "polyline":
        _shape(p, _poly([(4, 26), (8, 7), (18, 13), (28, 5), (26, 26)]), PURPLE, 60)
        p.setBrush(QBrush(QColor("#ffffff")))
        p.setPen(_pen(PURPLE, 1.4))
        for x, y in ((4, 26), (8, 7), (18, 13), (28, 5), (26, 26)):
            p.drawRect(QRectF(x - 2, y - 2, 4, 4))
    elif k == "oval":
        _shape(p, _rect(2, 10.5, 28, 11, 5.5), RED, 70)
    elif k in ("hole", "hole_csk", "hole_thread"):
        if k == "hole_csk":
            _shape(p, _ell(16, 16, 12), ORANGE, 70)
        _shape(p, _ell(16, 16, 6.5), RED, 130)
        if k == "hole_thread":
            pn = QPen(_c(RED), 1.6, Qt.PenStyle.DashLine)
            p.setPen(pn)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(16, 16), 10.5, 10.5)
        _crosshair(p, 16, 16, fgn)
    elif k == "dhole":
        path = QPainterPath()
        path.moveTo(21, 6.5)
        path.arcTo(QRectF(5, 5, 22, 22), 60, 240)
        path.closeSubpath()
        _shape(p, path, RED, 110)
    elif k == "pocket":
        _shape(p, _rect(3, 7, 26, 18, 3), AMBER, 200, 1.6, AMBER)
        _shape(p, _rect(7, 11, 18, 10, 2), "#a86b00", 120, 1.2, "#7a4e00")
    elif k == "text":
        _shape(p, _rect(3, 3, 26, 26, 5), PURPLE, 200, 1.2, PURPLE)
        _text(p, QRectF(0, 0, 32, 32), "T", "#ffffff", 22)
    elif k == "image":
        _shape(p, _rect(3, 5, 26, 22, 3), PINK, 40)
        _shape(p, _poly([(5, 25), (12, 15), (17, 21), (21, 17), (27, 25)]), GREEN, 200, 1.4)
        _shape(p, _ell(22, 11, 3), AMBER, 255, 1)
    elif k in ("dimension", "autodim", "show_dims"):
        p.setPen(_pen(GREEN, 2))
        p.drawLine(QPointF(4, 7), QPointF(4, 27))
        p.drawLine(QPointF(28, 7), QPointF(28, 27))
        p.drawLine(QPointF(5, 20), QPointF(27, 20))
        p.setBrush(QBrush(_c(GREEN)))
        p.drawPath(_poly([(5, 20), (10, 17), (10, 23)]))
        p.drawPath(_poly([(27, 20), (22, 17), (22, 23)]))
        if k == "autodim":
            _text(p, QRectF(6, 1, 20, 15), "A", BLUE, 13)
        elif k == "show_dims":
            _text(p, QRectF(6, 1, 20, 15), "25", GREEN, 11)
    elif k == "measure":
        p.save()
        p.translate(16, 16)
        p.rotate(-35)
        _shape(p, _rect(-14, -5, 28, 10, 1.5), AMBER, 230, 1.4, AMBER)
        p.setPen(_pen("#5b3b00", 1.3))
        for i in range(-10, 12, 4):
            p.drawLine(QPointF(i, -5), QPointF(i, -1 if i % 8 else 1))
        p.restore()
    elif k == "component":
        _shape(p, _ell(16, 16, 12), STEEL, 230, 1.4, "#e4e8ee")
        _shape(p, _ell(16, 16, 7), "#3a4351", 255, 1.2, "#3a4351")
        p.setPen(_pen("#ffffff", 2))
        p.drawLine(QPointF(16, 16), QPointF(16, 10))
        p.setPen(_pen(BLUE, 1.6))
        for a in range(-135, 136, 45):
            r = math.radians(a - 90)
            p.drawLine(QPointF(16 + 13.5 * math.cos(r), 16 + 13.5 * math.sin(r)),
                       QPointF(16 + 15.5 * math.cos(r), 16 + 15.5 * math.sin(r)))
    elif k == "new":
        _shape(p, _poly([(7, 3), (20, 3), (26, 9), (26, 29), (7, 29)]), "#5b6573", 255, 1.4, "#ffffff")
        _shape(p, _ell(23, 23, 6.5), GREEN, 255, 1, GREEN)
        p.setPen(_pen("#ffffff", 2.2))
        p.drawLine(QPointF(23, 19.5), QPointF(23, 26.5))
        p.drawLine(QPointF(19.5, 23), QPointF(26.5, 23))
    elif k == "open":
        _shape(p, _poly([(3, 7), (12, 7), (14.5, 10), (28, 10), (28, 26), (3, 26)]), "#b7791f", 255, 1.4, "#f0b429")
        _shape(p, _poly([(3, 26), (7, 14), (31, 14), (28, 26)]), "#b7791f", 255, 1.4, "#fcd34d")
    elif k == "save":
        _shape(p, _poly([(4, 4), (24, 4), (28, 8), (28, 28), (4, 28)]), "#1d4f9c", 255, 1.4, BLUE)
        _shape(p, _rect(9, 4, 13, 8, 1), "#1d4f9c", 255, 1, "#dbe9ff")
        _shape(p, _rect(8, 17, 16, 11, 1), "#1d4f9c", 255, 1, "#ffffff")
    elif k in ("undo", "redo"):
        p.save()
        if k == "redo":
            p.translate(32, 0)
            p.scale(-1, 1)
        col = PURPLE if k == "undo" else TEAL
        path = QPainterPath(QPointF(9, 13))
        path.cubicTo(QPointF(15, 6), QPointF(29, 9), QPointF(26, 23))
        p.setPen(_pen(col, 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setBrush(QBrush(_c(col)))
        p.setPen(_pen(col, 1))
        p.drawPath(_poly([(4, 8), (13, 7), (8, 16)]))
        p.restore()
    elif k == "delete":
        _shape(p, _poly([(8, 10), (24, 10), (22, 29), (10, 29)]), RED, 200, 1.4, RED)
        p.setPen(_pen(RED, 2.4))
        p.drawLine(QPointF(5, 9), QPointF(27, 9))
        p.drawLine(QPointF(12.5, 5), QPointF(19.5, 5))
        p.setPen(_pen("#ffffff", 1.6))
        for x in (13, 16, 19):
            p.drawLine(QPointF(x, 14), QPointF(x, 25))
    elif k == "duplicate":
        _shape(p, _rect(4, 4, 16, 16, 2), BLUE, 60)
        _shape(p, _rect(12, 12, 16, 16, 2), BLUE, 180, 2, BLUE)
    elif k == "view3d":
        top = _poly([(16, 3), (28, 9.5), (16, 16), (4, 9.5)])
        left = _poly([(4, 9.5), (16, 16), (16, 29), (4, 22.5)])
        right = _poly([(16, 16), (28, 9.5), (28, 22.5), (16, 29)])
        for path, col in ((top, "#9cc7ff"), (left, BLUE), (right, "#1d4f9c")):
            _shape(p, path, "#173a70", 255, 1.2, col)
    elif k == "check":
        _shape(p, _ell(16, 16, 13), GREEN, 255, 1, GREEN)
        p.setPen(_pen("#ffffff", 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(_poly([(9.5, 16.5), (14, 21), (23, 11)], False))
    elif k == "zoom_fit":
        p.setPen(_pen(GREY, 1.6))
        for a, b in (((3, 9), (3, 3)), ((3, 3), (9, 3)), ((23, 3), (29, 3)), ((29, 3), (29, 9)),
                     ((3, 23), (3, 29)), ((3, 29), (9, 29)), ((29, 23), (29, 29)), ((29, 29), (23, 29))):
            p.drawLine(QPointF(*a), QPointF(*b))
        _shape(p, _ell(14.5, 14.5, 6.5), BLUE, 60, 2.2)
        p.setPen(_pen(BLUE, 3))
        p.drawLine(QPointF(19.5, 19.5), QPointF(25, 25))
    elif k == "array":
        for i in range(3):
            for j in range(3):
                _shape(p, _ell(7 + i * 9, 7 + j * 9, 3), TEAL, 160 if (i + j) % 2 else 70, 1.5)
    elif k == "mirror":
        _shape(p, _poly([(3, 25), (13, 7), (13, 25)]), TEAL, 170, 1.5)
        _shape(p, _poly([(29, 25), (19, 7), (19, 25)]), TEAL, 50, 1.5)
        p.setPen(QPen(_c(BLUE), 1.6, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(16, 2), QPointF(16, 30))
    elif k == "rotate":
        p.setPen(_pen(TEAL, 3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(QRectF(5, 5, 22, 22), 40 * 16, 270 * 16)
        p.setBrush(QBrush(_c(TEAL)))
        p.setPen(_pen(TEAL, 1))
        p.drawPath(_poly([(20, 2.5), (27.5, 8.5), (19, 11)]))
    elif k == "snap_grid":
        p.setPen(_pen(GREY, 1.2))
        for i in range(4, 30, 6):
            p.drawLine(QPointF(i, 3), QPointF(i, 29))
            p.drawLine(QPointF(3, i), QPointF(29, i))
        _shape(p, _ell(16, 16, 3.5), AMBER, 255, 1.2, AMBER)
    elif k == "snap_obj":  # imán
        pn = QPen(_c(RED), 6.5)
        pn.setCapStyle(Qt.PenCapStyle.FlatCap)
        p.setPen(pn)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawLine(QPointF(9, 4), QPointF(9, 16))
        p.drawLine(QPointF(23, 4), QPointF(23, 16))
        p.drawArc(QRectF(9, 9, 14, 14), 180 * 16, 180 * 16)
        pn.setColor(QColor("#dfe3e8"))
        p.setPen(pn)
        p.drawLine(QPointF(9, 3), QPointF(9, 8))
        p.drawLine(QPointF(23, 3), QPointF(23, 8))
    elif k == "stud":  # casquillo roscado en sección
        _shape(p, _rect(2, 7, 28, 5, 0), "#5b6573", 255, 1, STEEL)
        _shape(p, _rect(8, 4, 16, 3.5, 0.8), "#1b2330", 255, 1.2, "#e8eaed")
        _shape(p, _rect(11, 7, 10, 21, 1), "#1b2330", 255, 1.2, "#e8eaed")
        p.setPen(QPen(_c(ORANGE), 1.6, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(13.5, 9), QPointF(13.5, 27))
        p.drawLine(QPointF(18.5, 9), QPointF(18.5, 27))
    elif k == "scale":  # escala de potenciómetro
        p.setPen(_pen(PURPLE, 1.8))
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(11):
            a = math.radians(-60 + i * 30)
            ux, uy = -math.cos(a), -math.sin(a)
            r0, r1 = (9.5, 14.5) if i % 2 == 0 else (10.5, 13.0)
            p.drawLine(QPointF(16 + ux * r0, 19 + uy * r0), QPointF(16 + ux * r1, 19 + uy * r1))
        _shape(p, _ell(16, 19, 6.5), "#3a4351", 255, 1.2, STEEL)
        p.setPen(_pen("#1b2330", 2))
        p.drawLine(QPointF(16, 19), QPointF(20.5, 14.5))
    elif k == "variables":
        _shape(p, _rect(2, 5, 28, 22, 4), TEAL, 200, 1, TEAL)
        _text(p, QRectF(0, 3, 32, 26), "f(x)", "#ffffff", 12)
    elif k == "panel":
        _shape(p, _rect(2, 6, 28, 20, 2), "#5b6573", 255, 1.2, STEEL)
        _shape(p, _ell(10, 16, 3.5), "#3a4351", 255, 1, "#3a4351")
        _shape(p, _rect(17, 12, 9, 8, 1), "#3a4351", 255, 1, "#3a4351")
    elif k == "layers":
        for dy, col in ((12, "#1d4f9c"), (6, BLUE), (0, LBLUE)):
            _shape(p, _poly([(16, 6 + dy), (29, 11 + dy), (16, 16 + dy), (3, 11 + dy)]), "#173a70", 255, 1, col)
    elif k == "library":
        for i, col in enumerate((BLUE, ORANGE, GREEN)):
            _shape(p, _rect(4 + i * 8, 5, 7, 23, 1.5), "#2b3340", 255, 1, col)
    elif k == "language":
        _shape(p, _ell(16, 16, 13), BLUE, 255, 1.2, BLUE)
        p.setPen(_pen("#ffffff", 1.4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(16, 16), 5.5, 13)
        p.drawLine(QPointF(3, 16), QPointF(29, 16))
        p.drawLine(QPointF(5, 9.5), QPointF(27, 9.5))
        p.drawLine(QPointF(5, 22.5), QPointF(27, 22.5))
    elif k == "settings":
        _shape(p, _ell(16, 16, 10), GREY, 255, 1, GREY)
        p.setPen(_pen(GREY, 4))
        for a in range(0, 360, 45):
            r = math.radians(a)
            p.drawLine(QPointF(16 + 9 * math.cos(r), 16 + 9 * math.sin(r)),
                       QPointF(16 + 13 * math.cos(r), 16 + 13 * math.sin(r)))
        _shape(p, _ell(16, 16, 4), "#ffffff", 255, 1, "#ffffff")
    else:
        _shape(p, _rect(6, 6, 20, 20, 3), GREY, 80)


def icon(key: str, fg: str = "#d0d4da", accent: str = "#3d8bfd") -> QIcon:
    ck = (key, fg)
    if ck in _cache:
        return _cache[ck]
    ic = QIcon()
    for size in (32, 48, 64, 96):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.scale(size / 32.0, size / 32.0)
        try:
            _draw(p, key, QColor(fg))
        except Exception:  # noqa: BLE001
            from .safepaint import report
            report(f"icono {key}")
        finally:
            p.end()
        ic.addPixmap(pm)
    _cache[ck] = ic
    return ic


def clear_cache():
    _cache.clear()
