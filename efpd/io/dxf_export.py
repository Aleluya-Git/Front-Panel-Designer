"""Exportación DXF (R12 / AC1009, ASCII). Compatible con prácticamente
cualquier CAM, cortadora láser o servicio de mecanizado.

Una capa DXF por proceso: CONTORNO, MECANIZADO, FRESADO, GRABADO, SERIGRAFIA,
COTAS (y opcionalmente REFERENCIA / HUELLA).
"""
from __future__ import annotations

from typing import Iterable

from ..core import geometry as G
from ..core.document import Document
from .common import DEFAULT_EXPORT_ROLES, ROLE_NAMES, collect

ACI = {"outline": 7, "cut": 1, "pocket": 30, "pocket_back": 34, "engrave": 5, "print": 8, "ref": 6, "footprint": 9, "dim": 3}


def _txt(s: str) -> str:
    return (s.replace("Ø", "%%c").replace("ø", "%%c").replace("°", "%%d").replace("±", "%%p"))


class _W:
    def __init__(self):
        self.lines = []

    def g(self, code, value):
        if isinstance(value, float):
            value = f"{value:.6f}".rstrip("0").rstrip(".") if value != 0 else "0.0"
        self.lines.append(f"{code:>3}\n{value}\n")

    def text(self):
        return "".join(self.lines)


def export_dxf(doc: Document, path: str, roles: Iterable[str] = DEFAULT_EXPORT_ROLES) -> int:
    items = collect(doc, roles)
    used = sorted({r for r, _p, _e in items}, key=lambda r: list(ACI).index(r) if r in ACI else 99)
    b = None
    for _r, pr, _e in items:
        b = G.bbox_union(b, G.prim_bbox(pr))
    b = b or (0, 0, 1, 1)
    w = _W()
    w.g(0, "SECTION"); w.g(2, "HEADER")
    w.g(9, "$ACADVER"); w.g(1, "AC1009")
    w.g(9, "$INSUNITS"); w.g(70, 4)
    w.g(9, "$EXTMIN"); w.g(10, float(b[0])); w.g(20, float(b[1])); w.g(30, 0.0)
    w.g(9, "$EXTMAX"); w.g(10, float(b[2])); w.g(20, float(b[3])); w.g(30, 0.0)
    w.g(0, "ENDSEC")
    w.g(0, "SECTION"); w.g(2, "TABLES")
    w.g(0, "TABLE"); w.g(2, "LTYPE"); w.g(70, 1)
    w.g(0, "LTYPE"); w.g(2, "CONTINUOUS"); w.g(70, 0); w.g(3, "Solid line"); w.g(72, 65); w.g(73, 0); w.g(40, 0.0)
    w.g(0, "ENDTAB")
    w.g(0, "TABLE"); w.g(2, "LAYER"); w.g(70, len(used) + 1)
    w.g(0, "LAYER"); w.g(2, "0"); w.g(70, 0); w.g(62, 7); w.g(6, "CONTINUOUS")
    for r in used:
        w.g(0, "LAYER"); w.g(2, ROLE_NAMES.get(r, r.upper())); w.g(70, 0); w.g(62, ACI.get(r, 7)); w.g(6, "CONTINUOUS")
    w.g(0, "ENDTAB")
    w.g(0, "TABLE"); w.g(2, "STYLE"); w.g(70, 1)
    w.g(0, "STYLE"); w.g(2, "STANDARD"); w.g(70, 0); w.g(40, 0.0); w.g(41, 1.0); w.g(50, 0.0); w.g(71, 0)
    w.g(42, 2.5); w.g(3, "txt"); w.g(4, "")
    w.g(0, "ENDTAB")
    w.g(0, "ENDSEC")
    w.g(0, "SECTION"); w.g(2, "ENTITIES")
    n = 0
    for role, pr, _e in items:
        L = ROLE_NAMES.get(role, role.upper())
        t = pr["t"]
        if t == "circle":
            w.g(0, "CIRCLE"); w.g(8, L); w.g(10, float(pr["c"][0])); w.g(20, float(pr["c"][1])); w.g(30, 0.0)
            w.g(40, float(pr["r"]))
        elif t == "poly":
            pts = pr["pts"]
            if len(pts) < 2:
                continue
            w.g(0, "POLYLINE"); w.g(8, L); w.g(66, 1); w.g(70, 1 if pr.get("closed", True) else 0)
            w.g(10, 0.0); w.g(20, 0.0); w.g(30, 0.0)
            for x, y in pts:
                w.g(0, "VERTEX"); w.g(8, L); w.g(10, float(x)); w.g(20, float(y)); w.g(30, 0.0)
            w.g(0, "SEQEND"); w.g(8, L)
        elif t == "text":
            x, y = pr["pos"]
            w.g(0, "TEXT"); w.g(8, L); w.g(10, float(x)); w.g(20, float(y)); w.g(30, 0.0)
            w.g(40, float(pr["h"])); w.g(1, _txt(pr["text"])); w.g(50, float(pr.get("angle", 0.0)))
            w.g(72, 1); w.g(11, float(x)); w.g(21, float(y)); w.g(31, 0.0)
        else:
            continue
        n += 1
    w.g(0, "ENDSEC")
    w.g(0, "EOF")
    with open(path, "w", encoding="cp1252", errors="replace", newline="\r\n") as f:
        f.write(w.text())
    return n
