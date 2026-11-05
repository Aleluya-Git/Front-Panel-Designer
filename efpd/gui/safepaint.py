"""Protección del dibujado.

Si un ``paintEvent`` lanza una excepción con un QPainter abierto, PySide6 la
propaga y el pintor se destruye más tarde, cuando su dispositivo ya no existe:
Qt aborta el proceso («Fatal Python error: Aborted» / access violation). Este
decorador captura el error dentro del propio paintEvent, cierra los pintores
abiertos, lo anota en ``errores.log`` y lo deja en ``ERRORS`` para la
autoprueba. El programa sigue funcionando y el error queda registrado.
"""
from __future__ import annotations

import datetime
import functools
import os
import sys
import traceback

from PySide6.QtGui import QPainter

ERRORS: list = []        # (widget, texto) de los errores de dibujado de esta sesión
_seen: set = set()


def _log_path():
    try:
        from ..core.library import user_library_dir
        return os.path.join(os.path.dirname(user_library_dir()), "errores.log")
    except Exception:  # noqa: BLE001
        return None


def close_painters(tb):
    """Cierra cualquier QPainter activo en los marcos de la traza."""
    while tb is not None:
        for v in list(tb.tb_frame.f_locals.values()):
            if isinstance(v, QPainter):
                try:
                    if v.isActive():
                        v.end()
                except RuntimeError:
                    pass
        tb = tb.tb_next


def report(where: str, exc_info=None):
    etype, value, tb = exc_info or sys.exc_info()
    text = "".join(traceback.format_exception(etype, value, tb))
    ERRORS.append((where, text))
    key = (where, text)
    if key in _seen:
        return
    _seen.add(key)
    sys.stderr.write(f"[dibujado: {where}]\n{text}")
    p = _log_path()
    if p:
        try:
            with open(p, "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.datetime.now().isoformat(timespec='seconds')} · dibujado {where}\n{text}")
        except OSError:
            pass


def safe_paint(fn):
    @functools.wraps(fn)
    def wrapper(self, ev):
        try:
            return fn(self, ev)
        except Exception:  # noqa: BLE001 - nunca abortar por un fallo de dibujado
            info = sys.exc_info()
            close_painters(info[2])
            report(type(self).__name__, info)
            del info
    return wrapper
