"""Entidades del diseño.

Cada entidad guarda sus parámetros "brutos" en ``self.p`` (números o
expresiones '=...'). La geometría se calcula bajo demanda con un Evaluator.

``geometry(doc, ev)`` devuelve una lista de ``(rol, prim)`` en coordenadas de
panel. Roles:
    main      -> se sustituye por el proceso de la capa (cut/pocket/engrave/print/ref/dim)
    ref       -> referencia visual (no se mecaniza)
    footprint -> huella trasera del componente (verificación de interferencias)
    print     -> serigrafía (p. ej. rótulo de componente)
"""
from __future__ import annotations

import copy
import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import geometry as G
from . import textpath
from ..i18n import tr
from .expr import Evaluator, is_expr


@dataclass
class Field:
    name: str
    label: str
    kind: str = "num"  # num,int,str,text,bool,choice,font,color,pts,readonly
    default: Any = 0.0
    options: List[str] = field(default_factory=list)
    tip: str = ""
    group: str = ""  # posicion | tamano | caracteristicas | opciones ("" = automático)


COMMON = [Field("name", "Nombre", "str", ""), Field("x", "X (mm)", "num", 0.0),
          Field("y", "Y (mm)", "num", 0.0), Field("rot", "Rotación (°)", "num", 0.0)]

# Tablas de tornillería métrica (mm)
SCREWS = ["—", "M2", "M2.5", "M3", "M4", "M5", "M6", "M8"]
CLEARANCE = {"M2": 2.4, "M2.5": 2.9, "M3": 3.4, "M4": 4.5, "M5": 5.5, "M6": 6.6, "M8": 9.0}
TAP_DRILL = {"M2": 1.6, "M2.5": 2.05, "M3": 2.5, "M4": 3.3, "M5": 4.2, "M6": 5.0, "M8": 6.8}
CSK_HEAD = {"M2": 3.8, "M2.5": 4.7, "M3": 6.7, "M4": 9.0, "M5": 11.2, "M6": 13.4, "M8": 17.9}

TYPES: Dict[str, type] = {}


def register(cls):
    TYPES[cls.TYPE] = cls
    return cls


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def _shift_raw(raw, delta: float):
    """Desplaza un valor bruto conservando su expresión si la tiene."""
    if abs(delta) < 1e-12:
        return raw
    if is_expr(raw):
        m = re.match(r"^(=.*?)\s*([+-]\s*\d+(?:\.\d+)?)$", raw.strip())
        if m and m.group(1).strip() != "=":
            base, k = m.group(1), float(m.group(2).replace(" ", ""))
            k += delta
            return f"{base}{k:+.4f}".rstrip("0").rstrip(".") if abs(k) > 1e-9 else base
        return f"{raw.strip()}{delta:+.4f}".rstrip("0").rstrip(".")
    try:
        return round(float(raw) + delta, 6)
    except (TypeError, ValueError):
        return delta


def transform_prim(prim: dict, x: float, y: float, rot: float) -> dict:
    t = prim["t"]
    if t == "circle":
        q = dict(prim)
        q["c"] = G.transform_pts([prim["c"]], x, y, rot)[0]
        return q
    if t == "poly":
        q = dict(prim)
        q["pts"] = G.transform_pts(prim["pts"], x, y, rot)
        q["closed"] = prim.get("closed", True)
        return q
    if t == "text":
        pos = G.transform_pts([prim["pos"]], x, y, rot)[0]
        q = dict(prim)
        q["pos"] = pos
        q["angle"] = prim.get("angle", 0.0) + rot
        return q
    return prim


def shape_prims(s: dict, ev: Optional[Evaluator] = None) -> List[dict]:
    """Primitivas locales de una forma de biblioteca/componente.

    s = {"shape": circle|rect|oval|dhole|poly, "x":.., "y":.., "rot":.., ...}
    """
    val = (lambda k, d=0.0: ev.safe(s.get(k, d), d)) if ev else (lambda k, d=0.0: float(s.get(k, d) or 0.0))
    sh = s.get("shape", "circle")
    x, y, rot = val("x"), val("y"), val("rot")
    if sh == "circle":
        return [{"t": "circle", "c": (x, y), "r": val("d", 3.0) / 2.0}]
    if sh == "rect":
        pts = G.rect_poly(val("w", 10), val("h", 10), val("r", 0))
    elif sh == "oval":
        pts = G.obround_poly(val("l", 10), val("w", 4))
    elif sh == "dhole":
        pts = G.dhole_poly(val("d", 9.5), val("flat", 4.0))
    elif sh == "ellipse":
        pts = G.ellipse_poly(0, 0, val("w", 10) / 2, val("h", 6) / 2)
    elif sh == "arcslot":
        pts = G.arc_slot_poly(val("r", 10), val("w", 3), val("a0", 0), val("a1", 60))
    elif sh == "poly":
        pts = [tuple(map(float, p)) for p in s.get("pts", [])]
        if len(pts) < 2:
            return []
        return [{"t": "poly", "pts": G.transform_pts(pts, x, y, rot), "closed": s.get("closed", True)}]
    else:
        return []
    return [{"t": "poly", "pts": G.transform_pts(pts, x, y, rot), "closed": True}]


class Entity:
    TYPE = "base"
    LABEL = "Entidad"
    FIELDS: List[Field] = []
    HAS_POS = True
    DEFAULT_LAYER = "cut"

    def __init__(self, **params):
        self.id: str = params.pop("id", None) or new_id()
        self.layer: str = params.pop("layer", None) or self.DEFAULT_LAYER
        self.locked: bool = bool(params.pop("locked", False))
        self.p: Dict[str, Any] = {}
        for f in self.all_fields():
            self.p[f.name] = copy.deepcopy(f.default)
        self.p.update(params)

    # ---- descripción
    @classmethod
    def all_fields(cls) -> List[Field]:
        return (COMMON if cls.HAS_POS else [COMMON[0]]) + cls.FIELDS

    def v(self, ev: Evaluator, name: str, default: float = 0.0) -> float:
        return ev.safe(self.p.get(name), default)

    def display_name(self) -> str:
        return self.p.get("name") or tr(self.LABEL)

    # ---- geometría
    def local_prims(self, doc, ev) -> List[Tuple[str, dict]]:
        return []

    def geometry(self, doc, ev) -> List[Tuple[str, dict]]:
        x, y, rot = self.v(ev, "x"), self.v(ev, "y"), self.v(ev, "rot")
        return [(role, transform_prim(pr, x, y, rot)) for role, pr in self.local_prims(doc, ev)]

    def bbox(self, doc, ev):
        b = None
        for _role, pr in self.geometry(doc, ev):
            b = G.bbox_union(b, G.prim_bbox(pr))
        if b is None:
            x, y = self.v(ev, "x"), self.v(ev, "y")
            b = (x, y, x, y)
        return b

    def anchor(self, doc, ev, name: str):
        if name == "c" and self.HAS_POS:
            return (self.v(ev, "x"), self.v(ev, "y"))
        b = self.bbox(doc, ev)
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        return {"c": (cx, cy), "l": (b[0], cy), "r": (b[2], cy), "b": (cx, b[1]), "t": (cx, b[3]),
                "bl": (b[0], b[1]), "br": (b[2], b[1]), "tl": (b[0], b[3]), "tr": (b[2], b[3])}.get(name, (cx, cy))

    # ---- edición
    def move(self, dx: float, dy: float) -> None:
        if self.HAS_POS:
            self.p["x"] = _shift_raw(self.p.get("x", 0.0), dx)
            self.p["y"] = _shift_raw(self.p.get("y", 0.0), dy)

    def rotate_by(self, deg: float) -> None:
        if self.HAS_POS:
            self.p["rot"] = _shift_raw(self.p.get("rot", 0.0), deg)

    def set_pos(self, x: float, y: float) -> None:
        if self.HAS_POS:
            self.p["x"] = round(x, 6)
            self.p["y"] = round(y, 6)

    # ---- serialización
    def to_dict(self) -> dict:
        return {"type": self.TYPE, "id": self.id, "layer": self.layer, "locked": self.locked,
                "p": copy.deepcopy(self.p)}

    def clone(self, keep_id=False) -> "Entity":
        d = self.to_dict()
        if not keep_id:
            d["id"] = new_id()
        return entity_from_dict(d)


def entity_from_dict(d: dict) -> Entity:
    cls = TYPES.get(d.get("type"), None)
    if cls is None:
        raise ValueError(f"Tipo de entidad desconocido: {d.get('type')}")
    e = cls(id=d.get("id"), layer=d.get("layer"), locked=d.get("locked", False))
    e.p.update(copy.deepcopy(d.get("p", {})))
    return e


# =================================================================== formas
@register
class RectEntity(Entity):
    TYPE, LABEL = "rect", "Rectángulo"
    FIELDS = [Field("w", "Ancho", "num", 20.0), Field("h", "Alto", "num", 10.0),
              Field("r", "Radio esquina", "num", 0.0)]

    def local_prims(self, doc, ev):
        return [("main", {"t": "poly", "pts": G.rect_poly(self.v(ev, "w"), self.v(ev, "h"), self.v(ev, "r")),
                          "closed": True})]


@register
class RoundRectEntity(RectEntity):
    TYPE, LABEL = "roundrect", "Rectángulo redondeado"
    FIELDS = [Field("w", "Ancho", "num", 30.0), Field("h", "Alto", "num", 15.0),
              Field("r", "Radio esquina", "num", 3.0)]


@register
class SlotEntity(RectEntity):
    TYPE, LABEL = "slot", "Ranura rectangular"
    FIELDS = [Field("w", "Largo", "num", 20.0), Field("h", "Ancho", "num", 3.0),
              Field("r", "Radio esquina", "num", 0.0, tip="Radio mínimo = radio de la fresa")]


@register
class CircleEntity(Entity):
    TYPE, LABEL = "circle", "Círculo"
    FIELDS = [Field("d", "Diámetro", "num", 10.0)]

    def local_prims(self, doc, ev):
        return [("main", {"t": "circle", "c": (0.0, 0.0), "r": max(0.0, self.v(ev, "d")) / 2})]


@register
class EllipseEntity(Entity):
    TYPE, LABEL = "ellipse", "Elipse"
    FIELDS = [Field("w", "Eje X", "num", 20.0), Field("h", "Eje Y", "num", 12.0)]

    def local_prims(self, doc, ev):
        return [("main", {"t": "poly", "pts": G.ellipse_poly(0, 0, self.v(ev, "w") / 2, self.v(ev, "h") / 2),
                          "closed": True})]


@register
class PolygonEntity(Entity):
    TYPE, LABEL = "polygon", "Polígono regular"
    FIELDS = [Field("n", "Lados", "int", 6), Field("d", "Diámetro circunscrito", "num", 12.0)]

    def local_prims(self, doc, ev):
        return [("main", {"t": "poly", "pts": G.regular_poly(int(self.v(ev, "n", 6)), self.v(ev, "d")),
                          "closed": True})]


@register
class PolylineEntity(Entity):
    TYPE, LABEL = "polyline", "Polígono libre"
    FIELDS = [Field("pts", "Vértices (x,y; ...)", "pts", []), Field("closed", "Cerrado", "bool", True)]

    def local_prims(self, doc, ev):
        pts = [(float(a), float(b)) for a, b in self.p.get("pts", [])]
        if len(pts) < 2:
            return []
        return [("main", {"t": "poly", "pts": pts, "closed": bool(self.p.get("closed", True))})]


@register
class OvalSlotEntity(Entity):
    TYPE, LABEL = "oval", "Ranura ovalada"
    FIELDS = [Field("l", "Largo total", "num", 16.0), Field("w", "Ancho", "num", 5.0)]

    def local_prims(self, doc, ev):
        return [("main", {"t": "poly", "pts": G.obround_poly(self.v(ev, "l"), self.v(ev, "w")), "closed": True})]


@register
class DHoleEntity(Entity):
    TYPE, LABEL = "dhole", "Agujero en D"
    FIELDS = [Field("d", "Diámetro", "num", 9.5), Field("flat", "Distancia al plano", "num", 4.3)]

    def local_prims(self, doc, ev):
        return [("main", {"t": "poly", "pts": G.dhole_poly(self.v(ev, "d"), self.v(ev, "flat")), "closed": True})]


@register
class HoleEntity(Entity):
    TYPE, LABEL = "hole", "Agujero"
    KINDS = ["montaje", "avellanado", "roscado"]
    FIELDS = [Field("kind", "Tipo", "choice", "montaje", KINDS),
              Field("screw", "Tornillo", "choice", "M3", SCREWS),
              Field("d", "Diámetro (si '—')", "num", 3.2),
              Field("csk_d", "Ø avellanado (si '—')", "num", 6.5),
              Field("csk_angle", "Ángulo avellanado", "num", 90.0)]

    def diameters(self, ev) -> Tuple[float, float]:
        """(diámetro taladro, diámetro visible/nominal)"""
        kind, screw = self.p.get("kind", "montaje"), self.p.get("screw", "—")
        d = self.v(ev, "d", 3.2)
        if screw in CLEARANCE:
            if kind == "roscado":
                return TAP_DRILL[screw], float(screw[1:])
            if kind == "avellanado":
                return CLEARANCE[screw], CSK_HEAD[screw]
            return CLEARANCE[screw], CLEARANCE[screw]
        if kind == "avellanado":
            return d, self.v(ev, "csk_d", d * 2)
        return d, d

    def display_name(self):
        if self.p.get("name"):
            return self.p["name"]
        screw = self.p.get("screw") if self.p.get("screw") != "—" else ""
        return f"{tr(self.LABEL)} {tr(self.p.get('kind', ''))} {screw}".strip()

    def local_prims(self, doc, ev):
        d, nom = self.diameters(ev)
        out = [("main", {"t": "circle", "c": (0.0, 0.0), "r": d / 2})]
        if abs(nom - d) > 1e-6:
            out.append(("ref", {"t": "circle", "c": (0.0, 0.0), "r": nom / 2}))
        return out


@register
class PocketEntity(Entity):
    TYPE, LABEL = "pocket", "Fresado / rebaje"
    DEFAULT_LAYER = "pocket"
    FIELDS = [Field("shape", "Forma", "choice", "rect", ["rect", "circle", "oval"]),
              Field("w", "Ancho / Ø", "num", 30.0), Field("h", "Alto", "num", 20.0),
              Field("r", "Radio esquina", "num", 2.0), Field("depth", "Profundidad", "num", 0.8)]

    def local_prims(self, doc, ev):
        sh = self.p.get("shape", "rect")
        w, h = self.v(ev, "w"), self.v(ev, "h")
        if sh == "circle":
            return [("main", {"t": "circle", "c": (0.0, 0.0), "r": w / 2})]
        if sh == "oval":
            return [("main", {"t": "poly", "pts": G.obround_poly(w, h), "closed": True})]
        return [("main", {"t": "poly", "pts": G.rect_poly(w, h, self.v(ev, "r")), "closed": True})]


WEIGHTS = {"fina": 300, "normal": 400, "media": 500, "seminegrita": 600, "negrita": 700, "gruesa": 900}


@register
class TextEntity(Entity):
    TYPE, LABEL = "text", "Texto"
    DEFAULT_LAYER = "print"
    FIELDS = [Field("text", "Texto", "str", "TEXTO"), Field("font", "Fuente", "font", "DejaVu Sans"),
              Field("size", "Altura (mm)", "num", 3.5),
              Field("weight", "Grosor", "choice", "normal", list(WEIGHTS)),
              Field("italic", "Cursiva", "bool", False), Field("underline", "Subrayado", "bool", False),
              Field("strike", "Tachado", "bool", False), Field("upper", "Mayúsculas", "bool", False),
              Field("color", "Color", "color", "", tip="Vacío = color de serigrafía del panel"),
              Field("align", "Alineación", "choice", "centro", ["izquierda", "centro", "derecha"]),
              Field("sx", "Escala X (%)", "num", 100.0), Field("spacing", "Espaciado entre letras (%)", "num", 100.0),
              Field("line", "Interlineado (%)", "num", 160.0)]

    def weight_value(self) -> int:
        w = self.p.get("weight") or "normal"
        if w == "normal" and self.p.get("bold"):  # proyectos antiguos
            w = "negrita"
        return WEIGHTS.get(w, 400)

    def local_prims(self, doc, ev):
        text = str(self.p.get("text", ""))
        if self.p.get("upper"):
            text = text.upper()
        return [("main", pr) for pr in text_prims(
            text, self.p.get("font", ""), self.v(ev, "size", 3.5), self.weight_value(), bool(self.p.get("italic")),
            self.p.get("align", "centro"), self.v(ev, "sx", 100.0) / 100.0,
            spacing=self.v(ev, "spacing", 100.0), line=self.v(ev, "line", 160.0),
            underline=bool(self.p.get("underline")), strike=bool(self.p.get("strike")),
            color=self.p.get("color") or None)]


def text_prims(text, font, size, bold, italic, align="centro", sx=1.0, dx=0.0, dy=0.0, *, spacing=100.0,
               line=160.0, underline=False, strike=False, color=None, valign="base"):
    """Primitivas de un texto (varias líneas). Línea base de la 1.ª línea en dy salvo valign='centro'."""
    out = []
    lines = str(text).split("\n")
    lh = size * max(0.5, line) / 100.0
    if valign == "centro":
        dy += -size / 2 + (len(lines) - 1) * lh / 2
    for li, txt in enumerate(lines):
        polys, width = textpath.outlines(txt, font, size, bold, italic, spacing)
        width *= sx
        ox = {"izquierda": 0.0, "derecha": -width}.get(align, -width / 2)
        oy = -li * lh
        for pts, closed in polys:
            pr = {"t": "poly", "pts": [(dx + ox + px * sx, dy + oy + py) for px, py in pts], "closed": closed}
            if color:
                pr["color"] = color
            out.append(pr)
        th = max(0.12, size * 0.075)
        for on, yy in ((underline, -size * 0.16), (strike, size * 0.36)):
            if on and width > 0:
                x0, y0 = dx + ox, dy + oy + yy
                pr = {"t": "poly", "pts": [(x0, y0 - th / 2), (x0 + width, y0 - th / 2), (x0 + width, y0 + th / 2),
                                           (x0, y0 + th / 2)], "closed": True}
                if color:
                    pr["color"] = color
                out.append(pr)
    return out


@register
class ImageEntity(Entity):
    TYPE, LABEL = "image", "Imagen / logotipo"
    DEFAULT_LAYER = "print"
    FIELDS = [Field("w", "Ancho", "num", 30.0), Field("h", "Alto", "num", 20.0),
              Field("data", "Datos", "readonly", ""), Field("source", "Origen", "readonly", "")]

    def local_prims(self, doc, ev):
        return [("ref", {"t": "poly", "pts": G.rect_poly(self.v(ev, "w"), self.v(ev, "h")), "closed": True})]


@register
class PathEntity(Entity):
    """Contornos importados (DXF/SVG) o generados. Coordenadas locales en mm."""
    TYPE, LABEL = "path", "Contorno importado"
    FIELDS = [Field("scale", "Escala (%)", "num", 100.0), Field("mirror", "Espejo X", "bool", False),
              Field("source", "Origen", "readonly", ""), Field("paths", "Trazos", "readonly", [])]

    def local_prims(self, doc, ev):
        s = self.v(ev, "scale", 100.0) / 100.0
        mx = -1.0 if self.p.get("mirror") else 1.0
        out = []
        for path in self.p.get("paths", []):
            pts = [(float(a) * s * mx, float(b) * s) for a, b in path.get("pts", [])]
            if len(pts) >= 2:
                out.append(("main", {"t": "poly", "pts": pts, "closed": bool(path.get("closed", True))}))
        return out


@register
class ComponentEntity(Entity):
    TYPE, LABEL = "component", "Componente"
    FIELDS = [Field("label", "Rótulo", "str", ""), Field("label_size", "Altura rótulo", "num", 3.0),
              Field("label_dy", "Posición rótulo (Y)", "num", 0.0, tip="0 = automática"),
              Field("show_ref", "Mostrar referencia", "bool", True),
              Field("comp", "Definición", "readonly", {})]

    def display_name(self):
        from .library import comp_name
        return self.p.get("name") or comp_name(self.p.get("comp", {}) or {"name": "Componente"})

    def local_prims(self, doc, ev):
        comp = self.p.get("comp", {}) or {}
        out = []
        for s in comp.get("cutouts", []):
            out += [("main", pr) for pr in shape_prims(s)]
        refb = None
        for s in comp.get("reference", []):
            for pr in shape_prims(s):
                out.append(("ref", pr))
                refb = G.bbox_union(refb, G.prim_bbox(pr))
        for s in comp.get("footprint", []):
            out += [("footprint", pr) for pr in shape_prims(s)]
        for s in comp.get("graphics", []):  # marcas de serigrafía propias del componente
            if s.get("shape") == "text":
                out += [("print", pr) for pr in text_prims(s.get("text", ""), "", float(s.get("size", 2.5)),
                                                         False, False, "centro", 1.0,
                                                         float(s.get("x", 0)), float(s.get("y", 0)))]
            else:
                out += [("print", pr) for pr in shape_prims(s)]
        label = self.p.get("label", "")
        if label:
            size = self.v(ev, "label_size", 3.0)
            dy = self.v(ev, "label_dy", 0.0)
            if abs(dy) < 1e-9:
                if refb is None:
                    for _r, pr in out:
                        refb = G.bbox_union(refb, G.prim_bbox(pr))
                dy = (refb[3] if refb else 5.0) + 2.0
            out += [("label", pr) for pr in text_prims(label, "", size, False, False, "centro", 1.0, 0.0, dy)]
        return out

    def geometry(self, doc, ev):
        # El rótulo nunca rota con el componente (se mantiene legible).
        x, y, rot = self.v(ev, "x"), self.v(ev, "y"), self.v(ev, "rot")
        res = []
        for role, pr in self.local_prims(doc, ev):
            if role == "label":
                res.append(("print", transform_prim(pr, x, y, 0.0)))
            else:
                res.append((role, transform_prim(pr, x, y, rot)))
        return res


@register
class DimensionEntity(Entity):
    TYPE, LABEL = "dimension", "Cota"
    HAS_POS = False
    DEFAULT_LAYER = "dim"
    FIELDS = [Field("orient", "Orientación", "choice", "h", ["h", "v", "a"],
                    tip="h=horizontal, v=vertical, a=alineada"),
              Field("offset", "Desplazamiento", "num", -8.0), Field("text", "Texto (vacío=auto)", "str", ""),
              Field("prec", "Decimales", "int", 1), Field("a", "Punto A", "readonly", {"xy": [0, 0]}),
              Field("b", "Punto B", "readonly", {"xy": [10, 0]})]

    def points(self, doc, ev):
        return doc.anchor_point(self.p.get("a"), ev), doc.anchor_point(self.p.get("b"), ev)

    def measure(self, doc, ev) -> float:
        a, b = self.points(doc, ev)
        o = self.p.get("orient", "h")
        if o == "h":
            return abs(b[0] - a[0])
        if o == "v":
            return abs(b[1] - a[1])
        return G.dist(a, b)

    def geometry(self, doc, ev):
        a, b = self.points(doc, ev)
        o = self.p.get("orient", "h")
        off = self.v(ev, "offset", -8.0)
        th = float(doc.settings.get("dim_text_h", 2.5))
        if o == "h":
            ly = a[1] + off
            p1, p2 = (a[0], ly), (b[0], ly)
            ext = [[a, (a[0], ly + math.copysign(1.5, off) if off else ly)],
                   [b, (b[0], ly + math.copysign(1.5, off) if off else ly)]]
        elif o == "v":
            lx = a[0] + off
            p1, p2 = (lx, a[1]), (lx, b[1])
            ext = [[a, (lx + math.copysign(1.5, off) if off else lx, a[1])],
                   [b, (lx + math.copysign(1.5, off) if off else lx, b[1])]]
        else:
            L = G.dist(a, b) or 1e-9
            nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
            p1 = (a[0] + nx * off, a[1] + ny * off)
            p2 = (b[0] + nx * off, b[1] + ny * off)
            s = math.copysign(1.5, off) if off else 0
            ext = [[a, (p1[0] + nx * s, p1[1] + ny * s)], [b, (p2[0] + nx * s, p2[1] + ny * s)]]
        out = [("main", {"t": "poly", "pts": e, "closed": False}) for e in ext]
        out.append(("main", {"t": "poly", "pts": [p1, p2], "closed": False}))
        L = G.dist(p1, p2)
        if L > 1e-6:
            ux, uy = (p2[0] - p1[0]) / L, (p2[1] - p1[1]) / L
            al, aw = min(2.5, L / 3), 0.6
            for (px, py), sgn in ((p1, 1), (p2, -1)):
                tip = (px, py)
                bx, by = px + ux * al * sgn, py + uy * al * sgn
                out.append(("main", {"t": "poly", "pts": [tip, (bx - uy * aw, by + ux * aw),
                                                          (bx + uy * aw, by - ux * aw)], "closed": True}))
        txt = self.p.get("text") or f"{self.measure(doc, ev):.{int(self.p.get('prec', 1))}f}"
        ang = math.degrees(math.atan2(p2[1] - p1[1], p2[0] - p1[0])) if L > 1e-6 else 0.0
        if ang > 90.0001 or ang < -89.999:
            ang -= 180 if ang > 0 else -180
        mid = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        na = math.radians(ang + 90)
        pos = (mid[0] + math.cos(na) * 0.8, mid[1] + math.sin(na) * 0.8)
        out.append(("main", {"t": "text", "pos": pos, "h": th, "text": txt, "angle": ang}))
        return out

    def move(self, dx, dy):
        for k in ("a", "b"):
            an = self.p.get(k) or {}
            if "xy" in an:
                an["xy"] = [an["xy"][0] + dx, an["xy"][1] + dy]
        if not any("xy" in (self.p.get(k) or {}) for k in ("a", "b")):
            o = self.p.get("orient", "h")
            self.p["offset"] = _shift_raw(self.p.get("offset", 0.0), dy if o == "h" else dx)

    def anchor(self, doc, ev, name):
        b = self.bbox(doc, ev)
        return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


from . import scale  # noqa: E402,F401  (registra ScaleEntity)
from . import stud  # noqa: E402,F401  (registra StudEntity)
