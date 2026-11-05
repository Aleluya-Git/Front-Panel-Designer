"""Proveedor de contornos de texto.

El núcleo no depende de Qt. La GUI registra un proveedor basado en
QPainterPath (fuentes del sistema). Sin proveedor (pruebas sin GUI) se usa una
fuente de trazos mínima integrada, suficiente para cotas y grabado básico.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Callable, List, Optional, Tuple

Poly = List[Tuple[float, float]]
# provider(text, family, height_mm, weight, italic, spacing%) -> (polilíneas cerradas, ancho)
# 'weight' es bool (negrita sí/no) o un peso CSS/Qt numérico (300 fina … 900 gruesa).
_provider: Optional[Callable] = None


def set_provider(fn: Optional[Callable]) -> None:
    global _provider
    _provider = fn
    outlines.cache_clear()


def has_real_fonts() -> bool:
    return _provider is not None


@lru_cache(maxsize=512)
def outlines(text: str, family: str, height: float, bold, italic: bool, spacing: float = 100.0):
    """Contornos del texto con la línea base en y=0, empezando en x=0.

    Devuelve (tuple de (tuple de puntos, cerrado)), ancho.
    """
    if _provider is not None:
        try:
            polys, width = _provider(text, family, height, bold, italic, spacing)
            return tuple((tuple(p), True) for p in polys), width
        except Exception:  # noqa: BLE001 - nunca romper el dibujo por una fuente
            pass
    return _stroke_font(text, height, spacing)


# Fuente de trazos 4x6 (líneas abiertas) para el modo sin Qt.
_GLYPHS = {
    "0": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0), (4, 6)]], "1": [[(1, 5), (2, 6), (2, 0)], [(1, 0), (3, 0)]],
    "2": [[(0, 6), (4, 6), (4, 3), (0, 3), (0, 0), (4, 0)]], "3": [[(0, 6), (4, 6), (4, 0), (0, 0)], [(1, 3), (4, 3)]],
    "4": [[(0, 6), (0, 3), (4, 3)], [(3, 6), (3, 0)]], "5": [[(4, 6), (0, 6), (0, 3), (4, 3), (4, 0), (0, 0)]],
    "6": [[(4, 6), (0, 6), (0, 0), (4, 0), (4, 3), (0, 3)]], "7": [[(0, 6), (4, 6), (1, 0)]],
    "8": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)], [(0, 3), (4, 3)]], "9": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 3), (4, 3)]],
    "A": [[(0, 0), (2, 6), (4, 0)], [(1, 3), (3, 3)]], "B": [[(0, 0), (0, 6), (3, 6), (4, 5), (3, 3), (4, 1), (3, 0), (0, 0)], [(0, 3), (3, 3)]],
    "C": [[(4, 6), (0, 6), (0, 0), (4, 0)]], "D": [[(0, 0), (0, 6), (3, 6), (4, 4), (4, 2), (3, 0), (0, 0)]],
    "E": [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]], "F": [[(4, 6), (0, 6), (0, 0)], [(0, 3), (3, 3)]],
    "G": [[(4, 6), (0, 6), (0, 0), (4, 0), (4, 3), (2, 3)]], "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(1, 6), (3, 6)], [(2, 6), (2, 0)], [(1, 0), (3, 0)]], "J": [[(4, 6), (4, 0), (0, 0), (0, 2)]],
    "K": [[(0, 0), (0, 6)], [(4, 6), (0, 3), (4, 0)]], "L": [[(0, 6), (0, 0), (4, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]], "N": [[(0, 0), (0, 6), (4, 0), (4, 6)]],
    "O": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)]], "P": [[(0, 0), (0, 6), (4, 6), (4, 3), (0, 3)]],
    "Q": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)], [(2, 2), (4, -1)]], "R": [[(0, 0), (0, 6), (4, 6), (4, 3), (0, 3), (4, 0)]],
    "S": [[(4, 6), (0, 6), (0, 3), (4, 3), (4, 0), (0, 0)]], "T": [[(0, 6), (4, 6)], [(2, 6), (2, 0)]],
    "U": [[(0, 6), (0, 0), (4, 0), (4, 6)]], "V": [[(0, 6), (2, 0), (4, 6)]],
    "W": [[(0, 6), (1, 0), (2, 3), (3, 0), (4, 6)]], "X": [[(0, 0), (4, 6)], [(0, 6), (4, 0)]],
    "Y": [[(0, 6), (2, 3), (4, 6)], [(2, 3), (2, 0)]], "Z": [[(0, 6), (4, 6), (0, 0), (4, 0)]],
    ".": [[(2, 0), (2, 0.5)]], ",": [[(2, 0.5), (1.5, -1)]], "-": [[(1, 3), (3, 3)]], "+": [[(1, 3), (3, 3)], [(2, 2), (2, 4)]],
    "/": [[(0, 0), (4, 6)]], ":": [[(2, 1), (2, 1.5)], [(2, 4), (2, 4.5)]], "(": [[(3, 6), (2, 4), (2, 2), (3, 0)]],
    ")": [[(1, 6), (2, 4), (2, 2), (1, 0)]], "=": [[(1, 2), (3, 2)], [(1, 4), (3, 4)]], "%": [[(0, 0), (4, 6)], [(0, 5), (1, 5)], [(3, 1), (4, 1)]],
    "Ø": [[(0, 0), (4, 0), (4, 6), (0, 6), (0, 0)], [(0, -1), (4, 7)]], "°": [[(1, 5), (2, 6), (3, 5), (2, 4), (1, 5)]],
    "±": [[(1, 4), (3, 4)], [(2, 3), (2, 5)], [(1, 1), (3, 1)]], "x": [[(1, 0), (3, 3)], [(1, 3), (3, 0)]],
}


def _stroke_font(text: str, height: float, spacing: float = 100.0):
    import unicodedata
    text = "".join(c if c in _GLYPHS else unicodedata.normalize("NFD", c)[0] for c in text).replace("−", "-")
    s = height / 6.0
    adv = 5.5 * s * max(0.3, spacing / 100.0)
    polys = []
    x = 0.0
    for ch in text:
        g = _GLYPHS.get(ch.upper()) if ch not in _GLYPHS else _GLYPHS[ch]
        if g:
            for stroke in g:
                polys.append((tuple((x + px * s, py * s) for px, py in stroke), False))
        x += adv
    width = max(0.0, x - 1.5 * s)
    return tuple(polys), width
