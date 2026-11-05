"""Modelo de documento: panel, material, capas, variables y entidades."""
from __future__ import annotations

import copy
import datetime as _dt
import itertools
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from . import geometry as G
from .entities import Entity, HoleEntity, OvalSlotEntity, entity_from_dict
from ..i18n import tr
from .expr import Evaluator

FORMAT_VERSION = 1

PROCESSES = {
    "cut": "Mecanizado pasante",
    "pocket": "Fresado / rebaje",
    "engrave": "Grabado",
    "print": "Serigrafía / impresión",
    "ref": "Referencia (no se fabrica)",
    "dim": "Cotas",
}

MATERIALS: Dict[str, dict] = {
    "Aluminio": {"color": "#c9cdd2", "t": 2.0, "alpha": 1.0, "metal": True},
    "Acero": {"color": "#8f969d", "t": 1.5, "alpha": 1.0, "metal": True},
    "Metacrilato": {"color": "#d8ecff", "t": 3.0, "alpha": 0.55, "metal": False},
    "PVC": {"color": "#f0f0f0", "t": 3.0, "alpha": 1.0, "metal": False},
    "Personalizado": {"color": "#b0a080", "t": 2.0, "alpha": 1.0, "metal": False},
}
FINISHES = ["Natural", "Anodizado", "Cepillado", "Pintado mate", "Pintado brillo", "Lacado", "Transparente"]


@dataclass
class Layer:
    id: str
    name: str
    process: str = "cut"
    color: str = "#ff5050"
    visible: bool = True
    locked: bool = False


def default_layers() -> List[Layer]:
    return [Layer("cut", "Mecanizado pasante", "cut", "#e5484d"),
            Layer("pocket", "Fresado / rebaje", "pocket", "#f5a524"),
            Layer("engrave", "Grabado", "engrave", "#3e9bff"),
            Layer("print", "Serigrafía", "print", "#1c1c1c"),
            Layer("dim", "Cotas", "dim", "#2fb67c"),
            Layer("ref", "Referencia", "ref", "#9a8cff")]


@dataclass
class Panel:
    w: object = 160.0
    h: object = 80.0
    t: object = 2.0
    r: object = 0.0
    material: str = "Aluminio"
    material_name: str = ""
    color: str = "#c9cdd2"
    print_color: str = "#111111"
    finish: str = "Anodizado"
    preset: str = "Personalizado"


DEFAULT_SETTINGS = {
    "grid": 2.5, "grid_major": 5, "snap_grid": True, "snap_objects": True,
    "min_edge": 2.0, "min_web": 1.5, "dim_text_h": 2.5, "min_text_gap": 0.5, "min_text_edge": 1.0,
}


_REVISIONS = itertools.count(1)


class Document:
    def __init__(self):
        self.panel = Panel()
        self.layers: List[Layer] = default_layers()
        for L in self.layers:
            L.name = tr(L.name)
        self.entities: List[Entity] = []
        self.variables: Dict[str, object] = {}
        self.settings: Dict[str, object] = dict(DEFAULT_SETTINGS)
        self.meta: Dict[str, object] = {"title": tr("Nuevo panel"), "author": "", "notes": "",
                                        "created": _now()}
        self.changelog: List[dict] = []
        # Contador global: dos documentos nunca comparten número de revisión, así las cachés de la GUI
        # (geometría, cotas automáticas) no reutilizan datos del documento abierto antes.
        self.revision = next(_REVISIONS)

    # ------------------------------------------------------------ evaluación
    def evaluator(self) -> Evaluator:
        base = Evaluator(self.variables)
        w = base.safe(self.panel.w, 100.0)
        h = base.safe(self.panel.h, 50.0)
        t = base.safe(self.panel.t, 2.0)
        return Evaluator(self.variables, {"W": w, "H": h, "T": t})

    def panel_dims(self, ev: Optional[Evaluator] = None) -> Tuple[float, float, float, float]:
        ev = ev or self.evaluator()
        return (ev.builtins["W"], ev.builtins["H"], ev.builtins["T"],
                max(0.0, ev.safe(self.panel.r, 0.0)))

    def panel_outline(self, ev: Optional[Evaluator] = None) -> G.Poly:
        w, h, _t, r = self.panel_dims(ev)
        return G.transform_pts(G.rect_poly(w, h, r), w / 2, h / 2)

    # ------------------------------------------------------------ capas
    def layer(self, lid: str) -> Optional[Layer]:
        for L in self.layers:
            if L.id == lid:
                return L
        return None

    def process_of(self, layer_id: str) -> str:
        L = self.layer(layer_id)
        return L.process if L else "cut"

    # ------------------------------------------------------------ entidades
    def get(self, eid: str) -> Optional[Entity]:
        for e in self.entities:
            if e.id == eid:
                return e
        return None

    def add(self, e: Entity) -> Entity:
        if self.layer(e.layer) is None:
            e.layer = self.layers[0].id
        self.entities.append(e)
        self.touch()
        return e

    def remove(self, ids: Iterable[str]) -> None:
        ids = set(ids)
        self.entities = [e for e in self.entities if e.id not in ids]
        # Las cotas vinculadas a entidades borradas se convierten en libres
        ev = self.evaluator()
        for e in self.entities:
            if e.TYPE == "dimension":
                for k in ("a", "b"):
                    an = e.p.get(k) or {}
                    if an.get("ref") in ids:
                        e.p[k] = {"xy": [0.0, 0.0]}
        del ev
        self.touch()

    def touch(self):
        self.revision = next(_REVISIONS)

    def anchor_point(self, an, ev: Evaluator) -> Tuple[float, float]:
        an = an or {}
        if "xy" in an:
            return (float(an["xy"][0]), float(an["xy"][1]))
        ref = an.get("ref")
        name = an.get("anchor", "c")
        if ref == "panel":
            w, h = ev.builtins["W"], ev.builtins["H"]
            return {"bl": (0, 0), "br": (w, 0), "tl": (0, h), "tr": (w, h), "c": (w / 2, h / 2),
                    "b": (w / 2, 0), "t": (w / 2, h), "l": (0, h / 2), "r": (w, h / 2)}.get(name, (0, 0))
        e = self.get(ref) if ref else None
        if e is None or e.TYPE == "dimension":
            return (0.0, 0.0)
        return e.anchor(self, ev, name)

    def geometry(self, ev: Optional[Evaluator] = None, visible_only: bool = False,
                 entities: Optional[Iterable[Entity]] = None):
        """Itera (entidad, rol_resuelto, prim) para todo el diseño."""
        ev = ev or self.evaluator()
        for e in (entities if entities is not None else self.entities):
            L = self.layer(e.layer)
            if visible_only and L is not None and not L.visible:
                continue
            proc = L.process if L else "cut"
            for role, pr in e.geometry(self, ev):
                yield e, (proc if role == "main" else role), pr

    # ------------------------------------------------------------ registro
    def log(self, label: str):
        self.changelog.append({"t": _now(), "what": label})
        if len(self.changelog) > 2000:
            del self.changelog[:-2000]

    # ------------------------------------------------------------ serialización
    def to_dict(self) -> dict:
        return {"format": "efpd", "version": FORMAT_VERSION,
                "meta": copy.deepcopy(self.meta), "panel": asdict(self.panel),
                "layers": [asdict(L) for L in self.layers],
                "variables": copy.deepcopy(self.variables),
                "settings": copy.deepcopy(self.settings),
                "entities": [e.to_dict() for e in self.entities],
                "changelog": copy.deepcopy(self.changelog)}

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        doc = cls()
        doc.load_dict(d)
        return doc

    def load_dict(self, d: dict) -> None:
        if d.get("format") not in (None, "efpd"):
            raise ValueError("No es un proyecto EFPD")
        self.meta = dict(self.meta, **d.get("meta", {}))
        pd = dict(asdict(Panel()), **d.get("panel", {}))
        self.panel = Panel(**{k: pd[k] for k in asdict(Panel()).keys()})
        if d.get("layers"):
            self.layers = [Layer(**{k: v for k, v in L.items() if k in Layer.__dataclass_fields__})
                           for L in d["layers"]]
        else:
            self.layers = default_layers()
        self.variables = dict(d.get("variables", {}))
        self.settings = dict(DEFAULT_SETTINGS, **d.get("settings", {}))
        self.entities = [entity_from_dict(e) for e in d.get("entities", [])]
        self.changelog = list(d.get("changelog", []))
        self.touch()


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# ================================================================ plantillas
PRESETS = ["Personalizado", "Rack 19\" 1U", "Rack 19\" 2U", "Rack 19\" 3U", "Rack 19\" 4U",
           "Eurorack 3U 4HP", "Eurorack 3U 8HP", "Eurorack 3U 10HP", "Eurorack 3U 12HP",
           "Eurorack 3U 20HP", "Eurorack 3U 42HP", "Hammond 1590B (tapa)", "Hammond 1590BB (tapa)",
           "Hammond 1590XX (tapa)", "Caja instrumento 200×100", "Fuente lab. 250×120"]


def apply_preset(doc: Document, name: str, add_holes: bool = True) -> None:
    """Ajusta el tamaño del panel y añade los taladros de fijación estándar."""
    p = doc.panel
    p.preset = name
    holes: List[Entity] = []
    if name.startswith("Rack 19"):
        n = int(name.split()[-1][0])
        p.w, p.h, p.t, p.r = 482.6, round(44.45 * n - 0.8, 2), 3.0, 0.0
        x0 = (482.6 - 465.1) / 2
        ys = [5.925, p.h - 5.925] if n > 1 else [p.h / 2]
        for x in (x0, 482.6 - x0):
            for y in ys:
                holes.append(OvalSlotEntity(x=round(x, 3), y=round(y, 3), l=10.0, w=6.5, name=tr("Fijación rack")))
    elif name.startswith("Eurorack"):
        hp = int(name.split()[-1].replace("HP", ""))
        p.w, p.h, p.t, p.r = round(hp * 5.08 - 0.3, 2), 128.5, 2.0, 0.0
        xs = [7.5] if hp < 10 else [7.5, 7.5 + 5.08 * (hp - 3)]
        for x in xs:
            for y in (3.0, 125.5):
                holes.append(OvalSlotEntity(x=x, y=y, l=5.2, w=3.2, name=tr("Fijación eurorack")))
    elif name.startswith("Hammond"):
        sizes = {"1590B": (112.4, 60.5), "1590BB": (119.5, 94.0), "1590XX": (145.0, 121.0)}
        key = name.split()[1]
        p.w, p.h = sizes.get(key, (112.4, 60.5))
        p.t, p.r = 2.5, 4.0
        if add_holes:
            m = 4.0
            for x in (m, p.w - m):
                for y in (m, p.h - m):
                    holes.append(HoleEntity(x=x, y=y, kind="avellanado", screw="M3", name=tr("Tornillo tapa")))
    elif name.startswith("Caja instrumento"):
        p.w, p.h, p.t, p.r = 200.0, 100.0, 2.0, 1.0
        for x in (6.0, 194.0):
            for y in (6.0, 94.0):
                holes.append(HoleEntity(x=x, y=y, kind="avellanado", screw="M3", name=tr("Fijación")))
    elif name.startswith("Fuente lab"):
        p.w, p.h, p.t, p.r = 250.0, 120.0, 2.0, 2.0
        for x in (8.0, 242.0):
            for y in (8.0, 112.0):
                holes.append(HoleEntity(x=x, y=y, kind="avellanado", screw="M4", name=tr("Fijación")))
    if add_holes:
        for h in holes:
            doc.add(h)
    doc.touch()
