"""Generación de G-code básico (fresadora / router CNC) y HPGL.

Estrategia:
  1. Grabado (trazado a profundidad fija, sin compensación).
  2. Rebajes: vaciado por contornos concéntricos.
  3. Mecanizados interiores: taladrado si el agujero ≤ fresa, interpolación
     circular para círculos, contorno compensado para el resto.
  4. Contorno exterior del panel (opcional), compensado hacia fuera.
Z=0 es la superficie superior del panel. Unidades mm, coordenadas absolutas.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import List, Tuple

from ..core import geometry as G
from ..core.document import Document
from ..i18n import tr
from .common import collect


@dataclass
class GcodeSettings:
    tool_d: float = 3.0
    feed: float = 600.0
    plunge: float = 150.0
    rpm: float = 12000.0
    safe_z: float = 5.0
    step_down: float = 0.5
    breakthrough: float = 0.2
    engrave_depth: float = 0.2
    stepover: float = 0.4          # fracción del diámetro para vaciados
    compensate: bool = True
    climb: bool = False
    include_engrave: bool = True
    include_pockets: bool = True
    include_cuts: bool = True
    include_outline: bool = True
    include_print_as_engrave: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        s = cls()
        for k, v in (d or {}).items():
            if hasattr(s, k):
                setattr(s, k, type(getattr(s, k))(v))
        return s


def _n(v: float) -> str:
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class _G:
    def __init__(self, s: GcodeSettings):
        self.s = s
        self.lines: List[str] = []
        self.z = s.safe_z

    def add(self, line):
        self.lines.append(line)

    def up(self):
        self.add(f"G0 Z{_n(self.s.safe_z)}")

    def rapid(self, x, y):
        self.add(f"G0 X{_n(x)} Y{_n(y)}")

    def plunge(self, z):
        self.add(f"G1 Z{_n(z)} F{_n(self.s.plunge)}")

    def path(self, pts, closed, z):
        self.rapid(*pts[0])
        self.plunge(z)
        first = True
        for x, y in pts[1:] + ([pts[0]] if closed else []):
            self.add(f"G1 X{_n(x)} Y{_n(y)}" + (f" F{_n(self.s.feed)}" if first else ""))
            first = False
        self.up()

    def circle(self, cx, cy, r, z, cw):
        self.rapid(cx + r, cy)
        self.plunge(z)
        self.add(f"{'G2' if cw else 'G3'} X{_n(cx + r)} Y{_n(cy)} I{_n(-r)} J0 F{_n(self.s.feed)}")
        self.up()


def _passes(depth: float, step: float) -> List[float]:
    n = max(1, int(math.ceil(depth / max(step, 0.01) - 1e-9)))
    return [-depth * (i + 1) / n for i in range(n)]


def _nearest_order(items: List[Tuple[Tuple[float, float], object]]):
    pos = (0.0, 0.0)
    rest = list(items)
    out = []
    while rest:
        k = min(range(len(rest)), key=lambda i: G.dist(pos, rest[i][0]))
        it = rest.pop(k)
        out.append(it)
        pos = it[0]
    return out


def generate(doc: Document, s: GcodeSettings) -> Tuple[str, List[str]]:
    """Devuelve (gcode, avisos)."""
    ev = doc.evaluator()
    W, H, T, _r = doc.panel_dims(ev)
    tool_r = s.tool_d / 2.0
    full = T + s.breakthrough
    warns: List[str] = []
    g = _G(s)
    g.add(f"( Electronic Front Panel Designer - {doc.meta.get('title', '')} )")
    g.add(f"( Panel {W:.2f} x {H:.2f} x {T:.2f} mm  {doc.panel.material} )")
    g.add(f"( Fresa D{s.tool_d}  avance {s.feed}  bajada {s.plunge}  paso Z {s.step_down} )")
    g.add("( Z0 = superficie superior del panel, origen = esquina inferior izquierda )")
    g.add("G21 G90 G17 G94")
    g.up()
    g.add(f"M3 S{int(s.rpm)}")
    g.add("G4 P2")

    items = collect(doc, ("cut", "pocket", "engrave", "print"))
    # ---- 1. grabado
    if s.include_engrave:
        roles = ("engrave", "print") if s.include_print_as_engrave else ("engrave",)
        eng = [pr for ro, pr, _e in items if ro in roles and pr["t"] in ("poly", "circle")]
        if eng:
            g.add("( --- Grabado --- )")
            for _c, pr in _nearest_order([(G.prim_bbox(p)[:2], p) for p in eng]):
                for pts, closed in G.prim_polys(pr, 0.02):
                    if len(pts) >= 2:
                        g.path(pts, closed, -s.engrave_depth)
    # ---- 2. rebajes
    if s.include_pockets:
        pk = [(pr, e) for ro, pr, e in items if ro == "pocket"]
        if pk:
            g.add("( --- Rebajes --- )")
        for pr, e in pk:
            depth = e.v(ev, "depth", 0.5) if e is not None and "depth" in e.p else 0.5
            for z in _passes(depth, s.step_down):
                for pts in _pocket_rings(pr, tool_r, s.stepover * s.tool_d):
                    g.path(_dir(pts, inside=True, climb=s.climb), True, z)
            if not _pocket_rings(pr, tool_r, s.stepover * s.tool_d):
                warns.append(tr("Rebaje «{n}» más pequeño que la fresa").format(n=e.display_name() if e else ""))
    # ---- 3. mecanizados interiores
    if s.include_cuts:
        cuts = [pr for ro, pr, _e in items if ro == "cut"]
        if cuts:
            g.add("( --- Mecanizados pasantes --- )")
        order = _nearest_order([(pr["c"] if pr["t"] == "circle" else G.bbox(pr["pts"])[:2], pr) for pr in cuts])
        for _c, pr in order:
            if pr["t"] == "circle":
                cx, cy = pr["c"]
                r = pr["r"] - (tool_r if s.compensate else 0.0)
                if r <= 0.05:
                    if pr["r"] * 2 < s.tool_d * 0.95:
                        warns.append(tr("Agujero Ø{d} menor que la fresa Ø{t}: taladrar aparte").format(
                            d=f"{pr['r'] * 2:.2f}", t=s.tool_d))
                    g.add(f"( Taladro Ø{pr['r'] * 2:.2f} )")
                    g.rapid(cx, cy)
                    for z in _passes(full, s.step_down * 2):
                        g.plunge(z)
                        g.add(f"G0 Z{_n(0.5)}")
                    g.up()
                    continue
                for z in _passes(full, s.step_down):
                    g.circle(cx, cy, r, z, cw=not s.climb)
            elif pr["t"] == "poly" and pr.get("closed", True):
                pts = G.offset_poly(pr["pts"], -tool_r) if s.compensate else G.orient(pr["pts"], True)
                if not pts:
                    warns.append(tr("Contorno interior más pequeño que la fresa (omitido)"))
                    continue
                for z in _passes(full, s.step_down):
                    g.path(_dir(pts, inside=True, climb=s.climb), True, z)
    if any(ro == "pocket_back" for ro, _p, _e in collect(doc, ("pocket_back",))):
        warns.append(tr("Los fresados por la cara trasera (agujeros ciegos) no se incluyen: mecanice el reverso aparte"))
    # ---- 4. contorno
    if s.include_outline:
        g.add("( --- Contorno exterior --- )")
        out = doc.panel_outline(ev)
        pts = G.offset_poly(out, tool_r) if s.compensate else G.orient(out, True)
        for z in _passes(full, s.step_down):
            g.path(_dir(pts, inside=False, climb=s.climb), True, z)
        warns.append(tr("Recuerde dejar puentes de sujeción o fijar bien la pieza antes del contorno"))
    g.up()
    g.add("M5")
    g.add("G0 X0 Y0")
    g.add("M30")
    return "\n".join(g.lines) + "\n", warns


def _dir(pts, inside, climb):
    """Convencional: exterior CCW, interior CW (husillo M3). Trepado: al revés."""
    ccw = G.orient(pts, True)
    want_ccw = (not inside) != climb
    return ccw if want_ccw else list(reversed(ccw))


def _pocket_rings(pr, tool_r, step):
    rings = []
    if pr["t"] == "circle":
        cx, cy = pr["c"]
        r = pr["r"] - tool_r
        while r > 0.01:
            rings.append(G.circle_poly(cx, cy, r, 0.02))
            r -= step
        if rings:
            rings.append([(cx, cy), (cx + 0.01, cy)])
        return rings
    base = G.orient(pr["pts"], True)
    d = tool_r
    for _ in range(500):
        ring = G.offset_poly(base, -d)
        if not ring:
            break
        rings.append(ring)
        d += step
    return rings


def export_gcode(doc: Document, path: str, s: GcodeSettings):
    code, warns = generate(doc, s)
    with open(path, "w", encoding="ascii", errors="replace", newline="\n") as f:
        f.write(code)
    return warns


def export_hpgl(doc: Document, path: str) -> int:
    """HPGL para plotters / cortadoras de vinilo / grabadoras. 40 unidades = 1 mm.

    Plumas: 1 mecanizado, 2 rebaje, 3 grabado, 4 serigrafía, 5 contorno.
    """
    pens = {"cut": 1, "pocket": 2, "engrave": 3, "print": 4, "outline": 5}
    items = collect(doc, tuple(pens))
    out = ["IN;", "PA;"]
    cur_pen = None
    n = 0
    for role, pr, _e in sorted(items, key=lambda t: pens[t[0]]):
        if pens[role] != cur_pen:
            cur_pen = pens[role]
            out.append(f"SP{cur_pen};")
        for pts, closed in G.prim_polys(pr, 0.05):
            if len(pts) < 2:
                continue
            seq = pts + ([pts[0]] if closed else [])
            out.append(f"PU{int(round(seq[0][0] * 40))},{int(round(seq[0][1] * 40))};")
            out.append("PD" + ",".join(f"{int(round(x * 40))},{int(round(y * 40))}" for x, y in seq[1:]) + ";")
            n += 1
    out += ["PU;", "SP0;"]
    with open(path, "w", encoding="ascii") as f:
        f.write("\n".join(out) + "\n")
    return n
