"""Contornos de texto con fuentes del sistema mediante QPainterPath."""
from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QFont, QFontDatabase, QFontMetricsF, QPainterPath

from ..core import textpath

_BASE_PX = 200  # se aplana a este tamaño (tolerancia de Qt ≈ 0.5 px) y luego se escala


def _poly_points(poly):
    try:
        return [(pt.x(), pt.y()) for pt in poly]
    except TypeError:
        return [(poly.at(i).x(), poly.at(i).y()) for i in range(poly.size())]


_WEIGHTS = [(150, "Thin"), (250, "ExtraLight"), (350, "Light"), (450, "Normal"), (550, "Medium"),
            (650, "DemiBold"), (750, "Bold"), (850, "ExtraBold")]  # 300 fina · 400 normal · 700 negrita


def make_font(family: str, bold=False, italic: bool = False, spacing: float = 100.0) -> QFont:
    f = QFont(family) if family else QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    f.setPixelSize(_BASE_PX)
    if isinstance(bold, bool) or not isinstance(bold, (int, float)) or bold <= 1:
        f.setBold(bool(bold))
    else:
        name = "Black"
        for limit, n in _WEIGHTS:
            if bold < limit:
                name = n
                break
        f.setWeight(getattr(QFont.Weight, name))
    f.setItalic(bool(italic))
    if abs(spacing - 100.0) > 0.01:
        f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, float(spacing))
    return f


def _raw(text, family, height, bold, italic, spacing=100.0):
    f = make_font(family, bold, italic, spacing)
    fm = QFontMetricsF(f)
    cap = fm.capHeight() or fm.ascent() * 0.7
    path = QPainterPath()
    path.addText(QPointF(0, 0), f, text)
    return path, height / cap, fm.horizontalAdvance(text)


def provider(text: str, family: str, height: float, bold, italic: bool, spacing: float = 100.0):
    path, k, adv = _raw(text, family, height, bold, italic, spacing)
    polys = []
    for sub in path.toSubpathPolygons():
        pts = [(x * k, -y * k) for x, y in _poly_points(sub)]
        if len(pts) >= 3:
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            polys.append(pts)
    return polys, adv * k


def install():
    textpath.set_provider(provider)
