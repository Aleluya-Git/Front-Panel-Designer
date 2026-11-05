"""Genera los proyectos de ejemplo de la carpeta 'ejemplos'."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from efpd.core import layout  # noqa: E402
from efpd.core.document import Document, apply_preset  # noqa: E402
from efpd.core.entities import ComponentEntity, HoleEntity, PocketEntity, RectEntity, TextEntity  # noqa: E402
from efpd.core.library import Library  # noqa: E402
from efpd.core.scale import PRESETS, ScaleEntity  # noqa: E402
from efpd.core.stud import StudEntity  # noqa: E402
from efpd.io.project import save_project  # noqa: E402

lib = Library()
OUT = os.path.join(ROOT, "ejemplos")
os.makedirs(OUT, exist_ok=True)


def comp(cid, x, y, label="", **kw):
    return ComponentEntity(x=x, y=y, comp=lib.get(cid), label=label, **kw)


def fuente():
    d = Document()
    d.meta["title"] = "Fuente de laboratorio 0-30 V"
    d.variables.update({"ancho": 240.0, "fila_mandos": 60.0, "fila_bornes": 24.0})
    d.panel.w, d.panel.h, d.panel.t, d.panel.r = "=ancho", 100.0, 2.0, 1.5
    d.panel.color, d.panel.finish = "#2b2f36", "Anodizado"
    d.panel.print_color = "#f2f2f2"
    pots = [d.add(comp("pot_16mm", 0, "=fila_mandos", lab)) for lab in ("TENSIÓN", "AJUSTE FINO", "CORRIENTE")]
    layout.distribute_on_panel(d, pots, "h", 125.0)
    for i, p in enumerate(pots):  # sólo en la mitad derecha
        p.p["x"] = f"=W/2 + 15 + {i}*40"
        p.p["label_dy"] = 22.0
        sc = ScaleEntity(x=p.p["x"], y="=fila_mandos", **PRESETS["Rotatorio 300° · 0–10"])
        sc.p.update(radius=13.5, text_size=2.2, len_major=2.0, len_minor=1.0, label_every=2)
        d.add(sc)
    d.add(comp("lcd_2004", 62, 57))
    d.add(PocketEntity(x=62, y=57, w=104, h=62, r=3, depth=0.5, layer="pocket", name="Rebaje bisel LCD"))
    for i, lab in enumerate(("+", "COM", "−")):
        d.add(comp("banana_4mm", f"=W - 70 + {i}*19.05", "=fila_bornes", lab))
    d.add(comp("rocker_kcd1", 25, 11, "RED"))
    d.add(comp("led_5mm_bezel", 55, 11, "CV"))
    d.add(comp("led_5mm_bezel", 75, 11, "CC"))
    for x, y in ((6, 6), ("=W-6", 6), (6, 94), ("=W-6", 94)):
        d.add(HoleEntity(x=x, y=y, kind="avellanado", screw="M3"))
    d.add(TextEntity(x="=W/2", y=93, text="FUENTE DE LABORATORIO  0-30 V / 0-5 A", size=3.5, weight="negrita",
                     spacing=110))
    for x in ("=W/2 + 5", "=W - 15"):  # casquillos ciegos M3 detrás para sujetar la placa de mandos
        d.add(StudEntity(x=x, y=30, kind="casquillo", thread="M3", length=8, depth_offset=0.8))
    d.add(TextEntity(x="=W - 51", y=11, text="SALIDA", size=2.5, weight="seminegrita", underline=True,
                     color="#ff5a4f"))
    return d


def eurorack():
    d = Document()
    d.meta["title"] = "Módulo Eurorack VCO 12HP"
    apply_preset(d, "Eurorack 3U 12HP")
    d.settings["min_edge"] = 1.0  # los agujeros de fijación Eurorack van normalizados cerca del borde
    d.panel.color, d.panel.print_color = "#e9e9e6", "#111111"
    d.add(TextEntity(x="=W/2", y=118, text="VCO", size=6, bold=True))
    d.add(comp("pot_16mm", "=W/2", 92, "FREQ", label_dy=19.0))
    sc = ScaleEntity(x="=W/2", y=92, **PRESETS["Rotatorio 300° · 0–10"])
    sc.p.update(radius=13.0, text_size=2.0, len_major=2.0, len_minor=1.0, label_every=2, minor_div=1)
    d.add(sc)
    d.add(comp("pot_9mm", "=W/4", 61, "FINE"))
    d.add(comp("pot_9mm", "=3*W/4", 61, "PW"))
    jacks = [d.add(comp("jack_35", 0, 30, lab)) for lab in ("V/OCT", "FM", "PWM")]
    layout.distribute_on_panel(d, jacks, "h", 10.0)
    outs = [d.add(comp("jack_35", 0, 12, lab)) for lab in ("SIN", "TRI", "SAW", "SQR")]
    d.variables["margen_out"] = 8.0
    for i, o in enumerate(outs):
        o.p["x"] = f"=margen_out + {i}*(W - 2*margen_out)/3"
    d.add(comp("led_3mm", "=W/2", 48))
    return d


def rack_trasero():
    d = Document()
    d.meta["title"] = "Amplificador 2U — panel trasero"
    apply_preset(d, "Rack 19\" 2U")
    d.panel.color = "#8f969d"
    d.panel.material = "Acero"
    d.panel.finish = "Pintado mate"
    d.add(comp("iec_fused", 50, "=H/2", "230 V~"))
    d.add(comp("fang_arc_80_77_4p3", 130, "=H/2"))
    for i, lab in enumerate(("IN L", "IN R")):
        d.add(comp("xlr_d", 230 + i * 36, "=H/2", lab))
    for i, lab in enumerate(("OUT L", "OUT R")):
        d.add(comp("speakon", 330 + i * 36, "=H/2", lab))
    d.add(comp("binding_post_pair", 420, "=H/2 - 8", "GND"))
    d.add(RectEntity(x=445, y="=H/2", w=14, h=30, r=1.5, layer="engrave", name="Marco serie"))
    return d


def freeze(d):
    """Posiciones numéricas: los elementos se arrastran y editan como cualquier otro."""
    ev = d.evaluator()
    for e in d.entities:
        if e.HAS_POS:
            for k in ("x", "y", "rot"):
                if isinstance(e.p.get(k), str):
                    e.p[k] = round(e.v(ev, k), 3)
        e.locked = False
    for L in d.layers:
        L.locked, L.visible = False, True
    return d


if __name__ == "__main__":
    for name, fn in (("fuente_laboratorio.efpd", fuente), ("eurorack_vco_12hp.efpd", eurorack),
                     ("rack_2u_amplificador_trasero.efpd", rack_trasero)):
        save_project(freeze(fn()), os.path.join(OUT, name))
        print("generado", name)
