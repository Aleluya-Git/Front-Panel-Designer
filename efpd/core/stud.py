"""Casquillos y pernos roscados a presión (tipo PEM / autoclinchantes).

* Perno (espárrago de cabeza plana): la cabeza queda enrasada en una cara y la
  rosca sobresale por la otra.
* Casquillo (separador roscado): el cuello entra en el panel y el cuerpo con
  rosca interior sobresale.

"Colocar en el reverso" = el elemento sobresale por la cara trasera (lo
habitual). Con "Offset de profundidad" > 0 (sólo en el reverso) el agujero es
ciego: se fresa desde detrás dejando ese espesor de material delante, de modo
que no se ve nada en la cara frontal.

Las medidas son orientativas (series habituales del mercado); verifique con la
hoja de datos del fabricante.
"""
from __future__ import annotations

from .entities import Entity, Field, register

THREADS = ["M2", "M2.5", "M3", "M4", "M5", "M6"]
KINDS = ["casquillo", "perno"]

# casquillo: Ø agujero, Ø cuerpo, Ø cabeza, alto cabeza, espesor mínimo de chapa
BUSH = {"M2": (4.1, 4.0, 6.0, 1.1, 1.0), "M2.5": (4.6, 4.5, 6.5, 1.1, 1.0), "M3": (5.1, 5.0, 7.0, 1.1, 1.0),
        "M4": (6.1, 6.0, 8.0, 1.3, 1.3), "M5": (7.1, 7.0, 9.5, 1.5, 1.5), "M6": (8.1, 8.0, 11.0, 1.5, 2.0)}
# perno: Ø agujero, Ø rosca, Ø cabeza, alto cabeza, espesor mínimo
STUD = {"M2": (2.1, 2.0, 3.6, 0.7, 1.0), "M2.5": (2.6, 2.5, 4.1, 0.7, 1.0), "M3": (3.1, 3.0, 4.6, 0.8, 1.0),
        "M4": (4.1, 4.0, 5.9, 1.0, 1.3), "M5": (5.1, 5.0, 6.6, 1.1, 1.5), "M6": (6.1, 6.0, 8.2, 1.5, 2.0)}
LENGTHS = {"casquillo": [3, 4, 5, 6, 8, 10, 12, 15, 20, 25], "perno": [6, 8, 10, 12, 15, 18, 20, 25, 30]}


@register
class StudEntity(Entity):
    TYPE, LABEL = "stud", "Perno / casquillo roscado"
    FIELDS = [Field("kind", "Tipo", "choice", "casquillo", KINDS, group="caracteristicas"),
              Field("thread", "Rosca", "choice", "M3", THREADS, group="caracteristicas"),
              Field("length", "Longitud", "num", 6.0, group="tamano"),
              Field("depth_offset", "Offset de profundidad", "num", 0.0, group="caracteristicas",
                    tip="0 = agujero pasante. >0 (en el reverso) = agujero ciego que deja ese espesor delante"),
              Field("reverse", "Colocar en el reverso", "bool", True, group="opciones")]

    def data(self):
        table = BUSH if self.p.get("kind") == "casquillo" else STUD
        hole, body, head, head_h, min_t = table.get(self.p.get("thread", "M3"), table["M3"])
        return {"hole": hole, "body": body, "head": head, "head_h": head_h, "min_t": min_t}

    def is_blind(self, ev) -> bool:
        return bool(self.p.get("reverse", True)) and self.v(ev, "depth_offset", 0.0) > 1e-6

    def blind_depth(self, ev, T: float) -> float:
        return max(0.05, T - self.v(ev, "depth_offset", 0.0))

    def display_name(self):
        if self.p.get("name"):
            return self.p["name"]
        from ..i18n import tr
        return f"{tr(self.p.get('kind', 'casquillo')).capitalize()} {self.p.get('thread', 'M3')} × " \
               f"{float(self.p.get('length', 6) or 0):g}"

    def local_prims(self, doc, ev):
        d = self.data()
        out = []
        if self.is_blind(ev):
            out.append(("pocket_back", {"t": "circle", "c": (0.0, 0.0), "r": d["hole"] / 2}))
        else:
            out.append(("main", {"t": "circle", "c": (0.0, 0.0), "r": d["hole"] / 2}))
            out.append(("ref", {"t": "circle", "c": (0.0, 0.0), "r": d["head"] / 2}))
        if self.p.get("reverse", True):
            out.append(("footprint", {"t": "circle", "c": (0.0, 0.0), "r": d["body"] / 2}))
            if self.is_blind(ev):
                out.append(("ref", {"t": "circle", "c": (0.0, 0.0), "r": d["head"] / 2}))
        else:
            out.append(("ref", {"t": "circle", "c": (0.0, 0.0), "r": d["body"] / 2}))
        return out
