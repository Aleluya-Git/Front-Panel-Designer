"""Escalas para potenciómetros rotatorios (redondas) y deslizantes (lineales).

Convención de ángulos (como en los diales): 0° = izquierda (9 en punto) y los
ángulos crecen en sentido horario; 90° = arriba. Un potenciómetro típico de
300° va de -60° a 240°.

Las marcas principales se generan a partir de la numeración (valor inicial,
final e incremento) o de una lista de textos. Entre cada dos marcas
principales se pueden añadir submarcas. Todas las piezas se generan como
contornos rellenos (serigrafía/grabado láser) o, opcionalmente, como trazo
simple para grabado CNC con fresa en V.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from . import geometry as G
from .entities import Entity, Field, register, text_prims, WEIGHTS

SHAPES = ["redonda", "lineal"]
MARK_STYLES = ["rayas", "puntos", "carácter", "ninguna"]
LABEL_MODES = ["números", "texto", "ninguna"]
MARK_POS = ["exterior", "interior", "centradas"]
TEXT_POS = ["exterior", "interior"]
TEXT_ROT = ["0", "45", "90", "135", "180", "tangente"]

# Grupos de campos para el diálogo
GROUPS = [
    ("Forma de la escala", ["shape", "radius", "length", "a0", "a1", "rot"]),
    ("Marcas", ["mark_style", "mark_char", "minor_div", "len_major", "len_minor", "mark_w", "dot_major", "dot_minor",
                "mark_pos", "mark_gap", "ref_line", "ref_w"]),
    ("Numeración y texto", ["label_mode", "v0", "v1", "step", "label_every", "decimals", "prefix", "suffix", "plus_sign", "texts",
                            "text_size", "text_gap", "text_pos", "text_rot", "font", "weight"]),
    ("Colores y acabado", ["color", "color_major", "color_minor", "single_line"]),
]


def dial_dir(a_deg: float) -> Tuple[float, float]:
    """Vector unitario para un ángulo de dial (0 = izquierda, horario)."""
    t = math.radians(180.0 - a_deg)
    return math.cos(t), math.sin(t)


@register
class ScaleEntity(Entity):
    TYPE, LABEL = "scale", "Escala"
    DEFAULT_LAYER = "print"
    FIELDS = [
        Field("shape", "Forma", "choice", "redonda", SHAPES),
        Field("radius", "Radio (redonda)", "num", 14.0),
        Field("length", "Longitud (lineal)", "num", 45.0),
        Field("a0", "Ángulo inicial (°)", "num", -60.0, tip="0° = izquierda, sentido horario; 90° = arriba"),
        Field("a1", "Ángulo final (°)", "num", 240.0),
        Field("mark_style", "Tipo de marca", "choice", "rayas", MARK_STYLES),
        Field("mark_char", "Carácter de marca", "str", "•"),
        Field("minor_div", "Submarcas entre marcas", "int", 1),
        Field("len_major", "Longitud marca", "num", 3.0),
        Field("len_minor", "Longitud submarca", "num", 1.5),
        Field("mark_w", "Grosor de raya", "num", 0.3),
        Field("dot_major", "Ø punto de marca", "num", 1.2),
        Field("dot_minor", "Ø punto de submarca", "num", 0.6),
        Field("mark_pos", "Posición de las marcas", "choice", "exterior", MARK_POS),
        Field("mark_gap", "Separación de las marcas", "num", 0.0, tip="Distancia desde el radio / la línea base"),
        Field("ref_line", "Línea de referencia", "bool", False),
        Field("ref_w", "Grosor línea de referencia", "num", 0.3),
        Field("label_mode", "Etiquetas", "choice", "números", LABEL_MODES),
        Field("v0", "Valor inicial", "num", 0.0),
        Field("v1", "Valor final", "num", 10.0),
        Field("step", "Incremento", "num", 1.0, tip="Salto entre marcas principales (p. ej. 5, 10)"),
        Field("label_every", "Etiquetar cada N marcas", "int", 1),
        Field("decimals", "Decimales", "int", 0),
        Field("prefix", "Prefijo", "str", ""),
        Field("suffix", "Sufijo", "str", ""),
        Field("plus_sign", "Signo + en positivos", "bool", False),
        Field("texts", "Textos (separados por ;)", "str", "MIN;MAX"),
        Field("text_size", "Tamaño del texto", "num", 2.5),
        Field("text_gap", "Separación del texto", "num", 1.0),
        Field("text_pos", "Posición del texto", "choice", "exterior", TEXT_POS),
        Field("text_rot", "Rotar texto", "choice", "0", TEXT_ROT,
              tip="Ángulo del texto respecto al panel; «tangente» sigue el arco de la escala"),
        Field("font", "Fuente", "font", ""),
        Field("weight", "Grosor", "choice", "normal", list(WEIGHTS)),
        Field("color", "Color", "color", "", tip="Vacío = color de serigrafía del panel"),
        Field("color_major", "Color de las marcas", "color", "", tip="Vacío = el color general"),
        Field("color_minor", "Color de las submarcas", "color", "", tip="Vacío = el color de las marcas"),
        Field("single_line", "Trazo simple (grabado CNC)", "bool", False),
    ]

    # ------------------------------------------------------------ marcas
    def ticks(self, ev) -> Tuple[List[Tuple[float, bool, int]], List[str]]:
        """[(fracción 0..1, es_principal, índice_principal)], etiquetas de las principales."""
        mode = self.p.get("label_mode", "números")
        labels: List[str] = []
        if mode == "texto":
            labels = [t.strip() for t in str(self.p.get("texts", "")).split(";")]
            labels = [t for t in labels if t != ""] or ["", ""]
            n = len(labels)
        else:
            v0, v1 = self.v(ev, "v0", 0.0), self.v(ev, "v1", 10.0)
            step = abs(self.v(ev, "step", 1.0)) or abs(v1 - v0) or 1.0
            n = int(math.floor(abs(v1 - v0) / step + 1e-6)) + 1
            n = max(2, min(n, 1000))
            sgn = 1.0 if v1 >= v0 else -1.0
            dec = max(0, min(6, int(self.v(ev, "decimals", 0))))
            pre, suf = str(self.p.get("prefix", "")), str(self.p.get("suffix", ""))
            for i in range(n):
                val = v0 + sgn * step * i
                txt = f"{val:.{dec}f}"
                if txt.startswith("-") and float(txt) == 0:
                    txt = txt[1:]
                if self.p.get("plus_sign") and float(txt) > 0:
                    txt = "+" + txt
                labels.append(pre + txt + suf)
            if mode == "ninguna":
                labels = [""] * n
        minor = max(0, min(50, int(self.v(ev, "minor_div", 0))))
        out = []
        for i in range(n):
            out.append((i / (n - 1) if n > 1 else 0.0, True, i))
            if i < n - 1:
                for k in range(1, minor + 1):
                    out.append(((i + k / (minor + 1)) / (n - 1), False, i))
        return out, labels

    def _span(self, ev):
        if self.p.get("shape") == "lineal":
            return self.v(ev, "length", 45.0)
        a0, a1 = self.v(ev, "a0", -60.0), self.v(ev, "a1", 240.0)
        return a0, a1

    # ------------------------------------------------------------ geometría
    def local_prims(self, doc, ev):
        color = self.p.get("color") or None
        single = bool(self.p.get("single_line"))
        style = self.p.get("mark_style", "rayas")
        pos = self.p.get("mark_pos", "exterior")
        gap = self.v(ev, "mark_gap", 0.0)
        lmaj, lmin = max(0.0, self.v(ev, "len_major", 3.0)), max(0.0, self.v(ev, "len_minor", 1.5))
        mw = max(0.02, self.v(ev, "mark_w", 0.3))
        dmaj, dmin = max(0.05, self.v(ev, "dot_major", 1.2)), max(0.05, self.v(ev, "dot_minor", 0.6))
        ts = max(0.3, self.v(ev, "text_size", 2.5))
        tgap = self.v(ev, "text_gap", 1.0)
        font = self.p.get("font", "")
        weight = WEIGHTS.get(self.p.get("weight", "normal"), 400)
        trot = str(self.p.get("text_rot", "0"))
        if self.p.get("rotate_text") and trot == "0":  # proyectos anteriores
            trot = "tangente"
        rot_text = trot == "tangente"
        fixed = 0.0 if rot_text else float(trot) if trot.replace(".", "", 1).lstrip("-").isdigit() else 0.0
        col_maj = self.p.get("color_major") or None
        col_min = self.p.get("color_minor") or col_maj
        every = max(1, int(self.v(ev, "label_every", 1)))
        round_ = self.p.get("shape", "redonda") != "lineal"
        rot = self.v(ev, "rot", 0.0)
        ticks, labels = self.ticks(ev)
        out: List[Tuple[str, dict]] = []

        def add(pr, col=None):
            c = col or color
            if c:
                pr["color"] = c
            out.append(("main", pr))

        def adder(major):
            c = col_maj if major else col_min
            return lambda pr: add(pr, c)

        def tick_range(major):
            """(inicio, fin) de la marca, medidos hacia fuera desde el radio/la línea base."""
            L = lmaj if major else lmin
            if style == "puntos":
                L = dmaj if major else dmin
            if style == "carácter":
                L = (lmaj if major else lmin)
            if pos == "exterior":
                return gap, gap + L
            if pos == "interior":
                return -gap - L, -gap
            return -L / 2, L / 2

        # extensión de las marcas principales (para colocar el texto)
        r_lo, r_hi = tick_range(True) if style != "ninguna" else (0.0, 0.0)

        if round_:
            R = max(0.1, self.v(ev, "radius", 14.0))
            a0, a1 = self._span(ev)
            # línea de referencia (arco)
            if self.p.get("ref_line"):
                rw = max(0.02, self.v(ev, "ref_w", 0.3))
                t0, t1 = math.radians(180 - a0), math.radians(180 - a1)
                if single:
                    add({"t": "poly", "pts": G.arc_pts(0, 0, R, t0, t1), "closed": False})
                else:
                    outer = G.arc_pts(0, 0, R + rw / 2, t0, t1)
                    inner = G.arc_pts(0, 0, max(0.01, R - rw / 2), t1, t0)
                    add({"t": "poly", "pts": outer + inner, "closed": True})
            for frac, major, _idx in ticks:
                a = a0 + (a1 - a0) * frac
                ux, uy = dial_dir(a)
                lo, hi = tick_range(major)
                self._mark(adder(major), style, major, ux, uy, R + lo, R + hi, mw, dmaj, dmin, single, font, weight,
                           rot_text, -rot + fixed)
            # etiquetas
            for frac, major, idx in ticks:
                if not major or idx % every or not labels[idx]:
                    continue
                a = a0 + (a1 - a0) * frac
                ux, uy = dial_dir(a)
                ang = (math.degrees(math.atan2(uy, ux)) - 90.0) if rot_text else -rot + fixed
                prs, w, h = self._label(labels[idx], font, ts, weight, ang)
                if not prs:
                    continue
                half = abs(ux) * w / 2 + abs(uy) * h / 2
                if self.p.get("text_pos", "exterior") == "exterior":
                    rt = R + max(r_hi, 0.0) + tgap + half
                else:
                    rt = R + min(r_lo, 0.0) - tgap - half
                for q in prs:
                    q["pts"] = [(x + ux * rt, y + uy * rt) for x, y in q["pts"]]
                    add(q)
            # cruz de centro (referencia, no se fabrica)
            out.append(("ref", {"t": "poly", "pts": [(-1.5, 0), (1.5, 0)], "closed": False}))
            out.append(("ref", {"t": "poly", "pts": [(0, -1.5), (0, 1.5)], "closed": False}))
        else:
            L = max(0.1, self.v(ev, "length", 45.0))
            if self.p.get("ref_line"):
                rw = max(0.02, self.v(ev, "ref_w", 0.3))
                if single:
                    add({"t": "poly", "pts": [(-L / 2, 0), (L / 2, 0)], "closed": False})
                else:
                    add({"t": "poly", "pts": [(-L / 2, -rw / 2), (L / 2, -rw / 2), (L / 2, rw / 2), (-L / 2, rw / 2)],
                         "closed": True})
            for frac, major, _idx in ticks:
                x = -L / 2 + L * frac
                lo, hi = tick_range(major)
                self._mark_lin(adder(major), style, major, x, lo, hi, mw, dmaj, dmin, single, font, weight, rot_text,
                               -rot + fixed)
            for frac, major, idx in ticks:
                if not major or idx % every or not labels[idx]:
                    continue
                x = -L / 2 + L * frac
                prs, w, h = self._label(labels[idx], font, ts, weight, 90.0 if rot_text else -rot + fixed)
                if not prs:
                    continue
                half = h / 2
                if self.p.get("text_pos", "exterior") == "exterior":
                    y = max(r_hi, 0.0) + tgap + half
                else:
                    y = min(r_lo, 0.0) - tgap - half
                for q in prs:
                    q["pts"] = [(px + x, py + y) for px, py in q["pts"]]
                    add(q)
            out.append(("ref", {"t": "poly", "pts": [(-L / 2, -1.5), (-L / 2, 1.5)], "closed": False}))
            out.append(("ref", {"t": "poly", "pts": [(L / 2, -1.5), (L / 2, 1.5)], "closed": False}))
            out.append(("ref", {"t": "poly", "pts": [(0, -1.5), (0, 1.5)], "closed": False}))
        return out

    @staticmethod
    def _label(txt, font, ts, weight, ang):
        """Texto centrado en el origen y girado 'ang' grados: (prims, ancho, alto) en el marco local."""
        prs = text_prims(txt, font, ts, weight, False, "centro", 1.0, 0.0, 0.0, valign="centro")
        b = None
        for q in prs:
            b = G.bbox_union(b, G.prim_bbox(q))
        if b is None:
            return [], 0.0, 0.0
        cx0, cy0 = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        for q in prs:
            q["pts"] = G.transform_pts([(x - cx0, y - cy0) for x, y in q["pts"]], 0.0, 0.0, ang)
        b = None
        for q in prs:
            b = G.bbox_union(b, G.prim_bbox(q))
        return prs, b[2] - b[0], b[3] - b[1]

    @staticmethod
    def _bar(add, x0, y0, x1, y1, w, single):
        if single:
            add({"t": "poly", "pts": [(x0, y0), (x1, y1)], "closed": False})
            return
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 1e-9:
            return
        nx, ny = -(y1 - y0) / L * w / 2, (x1 - x0) / L * w / 2
        add({"t": "poly", "pts": [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)],
             "closed": True})

    def _mark(self, add, style, major, ux, uy, r0, r1, mw, dmaj, dmin, single, font, weight, rot_text, upright):
        if style == "ninguna":
            return
        if style == "rayas":
            self._bar(add, ux * r0, uy * r0, ux * r1, uy * r1, mw if major else mw * 0.8, single)
        elif style == "puntos":
            d = dmaj if major else dmin
            rm = (r0 + r1) / 2
            add({"t": "circle", "c": (ux * rm, uy * rm), "r": d / 2})
        else:
            self._char(add, ux * (r0 + r1) / 2, uy * (r0 + r1) / 2, abs(r1 - r0), font, weight,
                       math.degrees(math.atan2(uy, ux)) - 90.0 if rot_text else upright)

    def _mark_lin(self, add, style, major, x, y0, y1, mw, dmaj, dmin, single, font, weight, rot_text, upright=0.0):
        if style == "ninguna":
            return
        if style == "rayas":
            self._bar(add, x, y0, x, y1, mw if major else mw * 0.8, single)
        elif style == "puntos":
            d = dmaj if major else dmin
            add({"t": "circle", "c": (x, (y0 + y1) / 2), "r": d / 2})
        else:
            self._char(add, x, (y0 + y1) / 2, abs(y1 - y0), font, weight, 90.0 if rot_text else upright)

    def _char(self, add, x, y, size, font, weight, ang):
        ch = str(self.p.get("mark_char", "•")) or "•"
        prs = text_prims(ch, font, max(0.3, size), weight, False, "centro", 1.0, 0.0, 0.0)
        b = None
        for q in prs:
            b = G.bbox_union(b, G.prim_bbox(q))
        if b is None:
            return
        cx0, cy0 = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        for q in prs:
            q["pts"] = G.transform_pts([(px - cx0, py - cy0) for px, py in q["pts"]], x, y, ang)
            add(q)


# Plantillas rápidas para el diálogo: nombre -> parámetros
PRESETS = {
    "Rotatorio 300° · 0–10": {"shape": "redonda", "a0": -60.0, "a1": 240.0, "v0": 0.0, "v1": 10.0, "step": 1.0,
                              "minor_div": 1, "mark_style": "rayas", "label_mode": "números"},
    "Rotatorio 270° · 0–10": {"shape": "redonda", "a0": -45.0, "a1": 225.0, "v0": 0.0, "v1": 10.0, "step": 1.0,
                              "minor_div": 4, "mark_style": "rayas", "label_mode": "números"},
    "Rotatorio 300° · 1–11 (puntos)": {"shape": "redonda", "a0": -60.0, "a1": 240.0, "v0": 1.0, "v1": 11.0,
                                       "step": 1.0, "minor_div": 0, "mark_style": "puntos", "label_mode": "números"},
    "Rotatorio 270° · 0–100 de 10 en 10": {"shape": "redonda", "a0": -45.0, "a1": 225.0, "v0": 0.0, "v1": 100.0,
                                           "step": 10.0, "minor_div": 1, "label_every": 2, "mark_style": "rayas",
                                           "label_mode": "números"},
    "Rotatorio ganancia −12…+12 dB": {"shape": "redonda", "a0": -45.0, "a1": 225.0, "v0": -12.0, "v1": 12.0,
                                      "step": 6.0, "minor_div": 2, "mark_style": "rayas", "label_mode": "números",
                                      "plus_sign": True},
    "Rotatorio MIN / MAX": {"shape": "redonda", "a0": -60.0, "a1": 240.0, "label_mode": "texto", "texts": "MIN;MAX",
                            "v0": 0.0, "v1": 10.0, "step": 1.0, "minor_div": 0, "mark_style": "rayas"},
    "Selector 6 posiciones": {"shape": "redonda", "a0": 15.0, "a1": 165.0, "label_mode": "texto",
                              "texts": "1;2;3;4;5;6", "minor_div": 0, "mark_style": "puntos"},
    "Semicírculo (referencia FPD) 1–10": {"shape": "redonda", "radius": 30.0, "a0": -10.0, "a1": 190.0, "v0": 1.0,
                                          "v1": 10.0, "step": 1.0, "minor_div": 4, "len_major": 5.0, "len_minor": 3.0,
                                          "ref_line": True, "text_size": 4.0, "text_gap": 3.0,
                                          "mark_pos": "exterior", "mark_style": "rayas"},
    "Deslizante 45 mm · 0–10": {"shape": "lineal", "length": 45.0, "rot": 90.0, "v0": 0.0, "v1": 10.0, "step": 1.0,
                                "minor_div": 1, "mark_style": "rayas", "label_mode": "números"},
    "Deslizante 60 mm · dB": {"shape": "lineal", "length": 60.0, "rot": 90.0, "label_mode": "texto",
                              "texts": "-∞;-40;-30;-20;-10;-5;0;+5;+10", "minor_div": 1, "mark_style": "rayas"},
    "Deslizante 100 mm · 0–100 de 5 en 5": {"shape": "lineal", "length": 100.0, "rot": 90.0, "v0": 0.0, "v1": 100.0,
                                            "step": 5.0, "minor_div": 4, "label_every": 2, "mark_style": "rayas",
                                            "label_mode": "números"},
}
