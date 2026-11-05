"""Utilidades compartidas por los exportadores."""
from __future__ import annotations

from typing import Iterable, List, Tuple

from ..core.document import Document

ROLE_ORDER = ["outline", "cut", "pocket", "pocket_back", "engrave", "print", "ref", "footprint", "dim"]
ROLE_NAMES = {"outline": "CONTORNO", "cut": "MECANIZADO", "pocket": "FRESADO", "pocket_back": "FRESADO_TRASERO", "engrave": "GRABADO",
              "print": "SERIGRAFIA", "ref": "REFERENCIA", "footprint": "HUELLA", "dim": "COTAS"}
DEFAULT_EXPORT_ROLES = ("outline", "cut", "pocket", "pocket_back", "engrave", "print", "dim")


def collect(doc: Document, roles: Iterable[str] = DEFAULT_EXPORT_ROLES,
            visible_only: bool = True) -> List[Tuple[str, dict, object]]:
    """Lista de (rol, prim, entidad) incluyendo el contorno del panel."""
    roles = set(roles)
    ev = doc.evaluator()
    out: List[Tuple[str, dict, object]] = []
    if "outline" in roles:
        out.append(("outline", {"t": "poly", "pts": doc.panel_outline(ev), "closed": True}, None))
    for e, role, pr in doc.geometry(ev, visible_only=visible_only):
        if role in roles:
            out.append((role, pr, e))
    out.sort(key=lambda t: ROLE_ORDER.index(t[0]) if t[0] in ROLE_ORDER else 99)
    return out


def hex_to_rgb(h: str):
    h = (h or "#000000").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)
