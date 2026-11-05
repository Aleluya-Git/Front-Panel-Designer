"""Exportación SVG en milímetros reales (1:1).

Dos estilos:
  * "fabricacion": sólo trazos, un grupo/capa por proceso (Inkscape compatible).
  * "visual": aspecto realista (panel coloreado, huecos transparentes, serigrafía rellena).
"""
from __future__ import annotations

from typing import Iterable
from xml.sax.saxutils import escape

from ..core.document import Document
from .common import DEFAULT_EXPORT_ROLES, ROLE_NAMES, collect

STROKE = {"outline": "#000000", "cut": "#e5484d", "pocket": "#f5a524", "pocket_back": "#b77a12", "engrave": "#1e6fd9",
          "print": "#111111", "ref": "#9a8cff", "footprint": "#888888", "dim": "#2fb67c"}


def _f(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def prim_path_d(pr: dict) -> str:
    t = pr["t"]
    if t == "circle":
        (x, y), r = pr["c"], pr["r"]
        return (f"M{_f(x - r)},{_f(y)} A{_f(r)},{_f(r)} 0 1,0 {_f(x + r)},{_f(y)} "
                f"A{_f(r)},{_f(r)} 0 1,0 {_f(x - r)},{_f(y)} Z")
    if t == "poly":
        pts = pr["pts"]
        if not pts:
            return ""
        d = "M" + " L".join(f"{_f(x)},{_f(y)}" for x, y in pts)
        return d + (" Z" if pr.get("closed", True) else "")
    return ""


def _text_el(pr, color):
    x, y = pr["pos"]
    return (f'<text transform="translate({_f(x)},{_f(y)}) scale(1,-1) rotate({_f(-pr.get("angle", 0.0))})" '
            f'font-family="Arial, sans-serif" font-size="{_f(pr["h"] * 1.4)}" text-anchor="middle" '
            f'fill="{color}">{escape(pr["text"])}</text>')


def build_svg(doc: Document, roles: Iterable[str] = DEFAULT_EXPORT_ROLES, style: str = "fabricacion",
              margin: float = 5.0) -> str:
    ev = doc.evaluator()
    W, H, _T, _r = doc.panel_dims(ev)
    roles = list(roles)
    items = collect(doc, roles)
    from ..core import geometry as G
    b = (0.0, 0.0, W, H)
    for _ro, pr, _e in items:
        b = G.bbox_union(b, G.prim_bbox(pr))
    x0, y0 = b[0] - margin, b[1] - margin
    w, h = b[2] - b[0] + 2 * margin, b[3] - b[1] + 2 * margin
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
           f'width="{_f(w)}mm" height="{_f(h)}mm" viewBox="{_f(x0)} {_f(-y0 - h)} {_f(w)} {_f(h)}">',
           f'<title>{escape(str(doc.meta.get("title", "Panel")))}</title>',
           '<g transform="scale(1,-1)">']
    if style == "visual":
        ds = [prim_path_d({"t": "poly", "pts": doc.panel_outline(ev), "closed": True})]
        ds += [prim_path_d(pr) for ro, pr, _e in items if ro == "cut"]
        out.append(f'<path d="{" ".join(ds)}" fill="{doc.panel.color}" fill-rule="evenodd" '
                   f'stroke="#555" stroke-width="0.15"/>')
        pk = [prim_path_d(pr) for ro, pr, _e in items if ro == "pocket"]
        if pk:
            out.append(f'<path d="{" ".join(pk)}" fill="#000" fill-opacity="0.18" stroke="#444" stroke-width="0.1"/>')
        # imágenes
        out += _images(doc, ev)
        groups = []
        for role, base, width in (("engrave", "#333", 0.12), ("print", doc.panel.print_color, 0.0)):
            cols = sorted({pr.get("color") or "" for ro, pr, _e in items if ro == role})
            groups += [(role, c, c or base, width) for c in cols]
        for role, key, color, width in groups:
            sel = [pr for ro, pr, _e in items if ro == role and (pr.get("color") or "") == key]
            closed = [prim_path_d(pr) for pr in sel if pr["t"] != "text" and (pr["t"] == "circle" or pr.get("closed", True))]
            opened = [prim_path_d(pr) for pr in sel if pr["t"] == "poly" and not pr.get("closed", True)]
            if closed:
                out.append(f'<path d="{" ".join(closed)}" fill="{color}" fill-rule="evenodd" '
                           f'stroke="{color}" stroke-width="{width}"/>')
            if opened:
                out.append(f'<path d="{" ".join(opened)}" fill="none" stroke="{color}" stroke-width="0.35" '
                           f'stroke-linecap="round" stroke-linejoin="round"/>')
        if "dim" in roles:
            out.append(_layer_group("dim", items))
    else:
        for role in dict.fromkeys(r for r, _p, _e in items):
            out.append(_layer_group(role, items))
        if "print" in roles:
            out += _images(doc, ev)
    out.append("</g></svg>")
    return "\n".join(out)


def _layer_group(role, items):
    color = STROKE.get(role, "#000")
    parts = [f'<g id="{ROLE_NAMES.get(role, role)}" inkscape:groupmode="layer" '
             f'inkscape:label="{ROLE_NAMES.get(role, role)}" fill="none" stroke="{color}" stroke-width="0.1">']
    geo = [pr for ro, pr, _e in items if ro == role and pr["t"] != "text"]
    if role == "dim":  # líneas abiertas + flechas (polígonos cerrados) rellenas
        lines = [prim_path_d(pr) for pr in geo if pr["t"] == "poly" and not pr.get("closed", True)]
        arrows = [prim_path_d(pr) for pr in geo if pr["t"] == "poly" and pr.get("closed", True)]
        if lines:
            parts.append(f'<path d="{" ".join(lines)}"/>')
        if arrows:
            parts.append(f'<path d="{" ".join(arrows)}" fill="{color}" stroke="none"/>')
    elif geo:
        parts.append(f'<path d="{" ".join(prim_path_d(pr) for pr in geo)}"/>')
    for ro, pr, _e in items:
        if ro == role and pr["t"] == "text":
            parts.append(_text_el(pr, color))
    parts.append("</g>")
    return "".join(parts)


def _images(doc, ev):
    out = []
    for e in doc.entities:
        if e.TYPE == "image" and e.p.get("data"):
            L = doc.layer(e.layer)
            if L is not None and not L.visible:
                continue
            x, y, w, h, rot = e.v(ev, "x"), e.v(ev, "y"), e.v(ev, "w"), e.v(ev, "h"), e.v(ev, "rot")
            out.append(f'<g transform="translate({_f(x)},{_f(y)}) rotate({_f(rot)}) scale(1,-1)">'
                       f'<image x="{_f(-w / 2)}" y="{_f(-h / 2)}" width="{_f(w)}" height="{_f(h)}" '
                       f'preserveAspectRatio="none" xlink:href="data:image/png;base64,{e.p["data"]}"/></g>')
    return out


def export_svg(doc: Document, path: str, roles: Iterable[str] = DEFAULT_EXPORT_ROLES,
               style: str = "fabricacion") -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_svg(doc, roles, style))
