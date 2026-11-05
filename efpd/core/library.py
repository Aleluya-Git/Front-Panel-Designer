"""Biblioteca de componentes electrónicos.

Formato de un componente (JSON, coordenadas en mm relativas al centro):

{
  "id": "pot_16mm", "name": "Potenciómetro 16 mm", "category": "Potenciómetros",
  "description": "...",
  "cutouts":   [ {"shape": "circle", "d": 7.5}, ... ],   # mecanizado en el panel
  "reference": [ {"shape": "circle", "d": 25} ],          # silueta visible (mando, bisel...)
  "footprint": [ {"shape": "circle", "d": 17} ],          # cuerpo tras el panel
  "graphics":  [ {"shape": "text", "text": "+", "x": 0, "y": 8, "size": 3} ]  # serigrafía opcional
}

Formas: circle(d), rect(w,h,r), oval(l,w), dhole(d,flat), ellipse(w,h), poly(pts,closed);
todas con x, y, rot opcionales.

Las medidas integradas corresponden a modelos habituales del mercado y son
orientativas: verifique siempre con la hoja de datos del fabricante.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
from typing import Dict, List, Optional


def C(d, x=0.0, y=0.0):
    return {"shape": "circle", "d": d, "x": x, "y": y}


def R(w, h, r=0.0, x=0.0, y=0.0):
    return {"shape": "rect", "w": w, "h": h, "r": r, "x": x, "y": y}


def _corners(sx, sy, d=3.2):
    return [C(d, -sx / 2, -sy / 2), C(d, sx / 2, -sy / 2), C(d, -sx / 2, sy / 2), C(d, sx / 2, sy / 2)]


def _fan(size, hole_spacing, screw_d, grill=False):
    cut = [C(size - 2.0)] if not grill else _honeycomb(size - 3.0, 4.0, 1.2)
    return {"cutouts": cut + _corners(hole_spacing, hole_spacing, screw_d),
            "reference": [R(size, size, 3.0)], "footprint": [R(size, size, 3.0)]}


def _honeycomb(area_d, hole_d, web):
    pitch = hole_d + web
    out = []
    rows = int(area_d / (pitch * 0.866)) + 2
    for j in range(-rows, rows + 1):
        y = j * pitch * 0.866
        off = (pitch / 2) if j % 2 else 0.0
        cols = int(area_d / pitch) + 2
        for i in range(-cols, cols + 1):
            x = i * pitch + off
            if math.hypot(x, y) + hole_d / 2 <= area_d / 2:
                out.append(C(hole_d, round(x, 3), round(y, 3)))
    return out


def _slider(travel, slot_w, pitch, screw_d, body_w, cap_w, cap_h):
    """Potenciómetro deslizante vertical: ranura de recorrido + 2 tornillos en los extremos."""
    return {"cutouts": [{"shape": "oval", "l": travel + slot_w, "w": slot_w, "rot": 90},
                        C(screw_d, 0, -pitch / 2), C(screw_d, 0, pitch / 2)],
            "reference": [R(cap_w, cap_h, 1.5), R(0.6, travel, 0)],
            "footprint": [R(body_w, pitch + 8, 1)]}


def _c(id_, name, cat, desc, **kw):
    d = {"id": id_, "name": name, "category": cat, "description": desc,
         "cutouts": [], "reference": [], "footprint": [], "graphics": [], "builtin": True}
    d.update(kw)
    return d


BUILTIN: List[dict] = [
    # ---------------------------------------------------------------- potenciómetros
    _c("pot_16mm", "Potenciómetro 16 mm (M7)", "Potenciómetros", "Rosca M7, tetón antigiro a 7.8 mm",
       cutouts=[C(7.5), C(3.2, 0, 7.8)], reference=[C(25)], footprint=[C(17)]),
    _c("pot_24mm", "Potenciómetro 24 mm (M10)", "Potenciómetros", "Alpha/Bourns 24 mm, rosca 3/8\"",
       cutouts=[C(10.0)], reference=[C(30)], footprint=[C(25)]),
    _c("pot_9mm", "Potenciómetro 9 mm (M7)", "Potenciómetros", "Alpha 9 mm vertical, PCB",
       cutouts=[C(7.2)], reference=[C(15)], footprint=[R(10, 12)]),
    _c("encoder_ec11", "Encoder rotativo EC11", "Potenciómetros", "Rosca M7",
       cutouts=[C(7.2)], reference=[C(20)], footprint=[R(12.5, 13.5)]),
    _c("trimmer_hole", "Acceso a trimmer Ø4", "Potenciómetros", "Orificio de ajuste con destornillador",
       cutouts=[C(4.0)], reference=[C(6)]),
    # ---------------------------------------------------------------- deslizantes
    _c("slide_15", "Potenciómetro deslizante 15 mm", "Potenciómetros deslizantes",
       "Tipo PTA15: recorrido 15 mm, ranura 2.5 mm, M2 (orientativo)", **_slider(15, 2.5, 30.0, 2.2, 9, 8, 12)),
    _c("slide_20", "Potenciómetro deslizante 20 mm", "Potenciómetros deslizantes",
       "Tipo PTA20: recorrido 20 mm, ranura 2.5 mm, M2 (orientativo)", **_slider(20, 2.5, 35.0, 2.2, 9, 8, 12)),
    _c("slide_30", "Potenciómetro deslizante 30 mm", "Potenciómetros deslizantes",
       "Tipo PTA30: recorrido 30 mm, ranura 2.5 mm, M2 (orientativo)", **_slider(30, 2.5, 45.0, 2.2, 9, 8, 12)),
    _c("slide_45", "Potenciómetro deslizante 45 mm", "Potenciómetros deslizantes",
       "Tipo PTA45: recorrido 45 mm, ranura 2.5 mm, M2 (orientativo)", **_slider(45, 2.5, 60.0, 2.2, 9, 10, 14)),
    _c("slide_60", "Potenciómetro deslizante 60 mm", "Potenciómetros deslizantes",
       "Tipo PTA60: recorrido 60 mm, ranura 2.5 mm, M2 (orientativo)", **_slider(60, 2.5, 75.0, 2.2, 9, 10, 14)),
    _c("fader_60", "Fader de estudio 60 mm", "Potenciómetros deslizantes",
       "Recorrido 60 mm, ranura 3 mm, M3 (orientativo)", **_slider(60, 3.0, 88.0, 3.2, 11, 12, 22)),
    _c("fader_100", "Fader de estudio 100 mm", "Potenciómetros deslizantes",
       "Tipo ALPS RSA0N 100 mm: ranura 3 mm, M3 a 128 mm (orientativo)", **_slider(100, 3.0, 128.0, 3.2, 11, 12, 22)),
    # ---------------------------------------------------------------- interruptores
    _c("toggle_mini", "Interruptor palanca mini (M6)", "Interruptores", "Rosca 1/4\"-40",
       cutouts=[C(6.4)], reference=[R(13, 8, 1)], footprint=[R(13, 8, 1)]),
    _c("toggle_std", "Interruptor palanca estándar (M12)", "Interruptores", "",
       cutouts=[C(12.2)], reference=[C(18)], footprint=[R(22, 16)]),
    _c("rocker_kcd1", "Interruptor basculante KCD1", "Interruptores", "Encaje a presión 19×13",
       cutouts=[R(19.2, 13.0)], reference=[R(21, 15, 0.8)], footprint=[R(19, 13)]),
    _c("rocker_kcd3", "Interruptor basculante KCD3 (red)", "Interruptores", "Encaje a presión 30×22",
       cutouts=[R(30.2, 22.2)], reference=[R(32, 25, 1)], footprint=[R(30, 22)]),
    _c("slide_sw", "Interruptor deslizante", "Interruptores", "Ventana 9×4 con 2 tornillos M2",
       cutouts=[{"shape": "oval", "l": 9.5, "w": 4.0}, C(2.2, -9.5, 0), C(2.2, 9.5, 0)],
       reference=[R(23, 7, 1)], footprint=[R(23, 7)]),
    # ---------------------------------------------------------------- pulsadores
    _c("push_12mm", "Pulsador 12 mm", "Pulsadores", "Antivandálico / panel Ø12",
       cutouts=[C(12.2)], reference=[C(14)], footprint=[C(15)]),
    _c("push_16mm", "Pulsador 16 mm", "Pulsadores", "", cutouts=[C(16.2)], reference=[C(18)], footprint=[C(19)]),
    _c("push_19mm", "Pulsador 19 mm", "Pulsadores", "", cutouts=[C(19.2)], reference=[C(22)], footprint=[C(22)]),
    _c("push_22mm", "Pulsador industrial 22 mm", "Pulsadores", "Serie 22 mm con tetón antigiro",
       cutouts=[{"shape": "dhole", "d": 22.3, "flat": 10.4, "rot": 90}], reference=[C(30)], footprint=[C(30)]),
    _c("tact_cap", "Pulsador táctil (capuchón Ø7)", "Pulsadores", "Pulsador PCB con capuchón",
       cutouts=[C(7.5)], reference=[C(10)]),
    # ---------------------------------------------------------------- LEDs
    _c("led_3mm", "LED 3 mm", "LEDs", "", cutouts=[C(3.1)], reference=[C(4)]),
    _c("led_5mm", "LED 5 mm", "LEDs", "", cutouts=[C(5.1)], reference=[C(6)]),
    _c("led_5mm_bezel", "LED 5 mm con portaled", "LEDs", "Portaled metálico Ø8",
       cutouts=[C(8.0)], reference=[C(10)]),
    _c("led_10mm", "LED 10 mm", "LEDs", "", cutouts=[C(10.1)], reference=[C(12)]),
    # ---------------------------------------------------------------- displays
    _c("lcd_1602", "LCD 16×2 (HD44780)", "Displays", "Módulo 80×36, ventana 71×24, M3 a 75×31",
       cutouts=[R(71.0, 24.0, 0.5)] + _corners(75.0, 31.0, 3.2), reference=[R(64.5, 16.0)],
       footprint=[R(80, 36)]),
    _c("lcd_2004", "LCD 20×4 (HD44780)", "Displays", "Módulo 98×60, ventana 97×40, M3 a 93×55",
       cutouts=[R(77.0, 26.0, 0.5, 0, 0)] + _corners(93.0, 55.0, 3.2), reference=[R(76.0, 25.2)],
       footprint=[R(98, 60)]),
    _c("lcd_12864", "LCD gráfico 128×64", "Displays", "Módulo 93×70, ventana 72×40",
       cutouts=[R(72.0, 40.0, 0.5)] + _corners(88.0, 65.0, 3.2), reference=[R(70.7, 38.8)],
       footprint=[R(93, 70)]),
    _c("oled_096", "OLED 0.96\" 128×64", "Displays", "Módulo 27×27, área 22×11 (orientativo)",
       cutouts=[R(23.0, 12.5, 0.5, 0, 1.5)] + _corners(23.0, 23.0, 2.2), reference=[R(21.7, 10.9, 0, 0, 1.5)],
       footprint=[R(27.3, 27.8)]),
    _c("oled_130", "OLED 1.3\" 128×64", "Displays", "Módulo 35×33, área 30×15 (orientativo)",
       cutouts=[R(31.0, 17.0, 0.5, 0, 2)] + _corners(30.0, 28.0, 2.2), reference=[R(29.4, 14.7, 0, 0, 2)],
       footprint=[R(35.4, 33.5)]),
    _c("tft_28", "TFT 2.8\" ILI9341", "Displays", "Módulo 86×50, área activa 58×43, M3 a 80×44",
       cutouts=[R(60.0, 45.0, 0.5, -4.0, 0)] + _corners(80.0, 44.0, 3.2), reference=[R(57.6, 43.2, 0, -4.0, 0)],
       footprint=[R(86, 50)]),
    _c("tft_35", "TFT 3.5\" 480×320", "Displays", "Módulo 98×56, área 74×49",
       cutouts=[R(75.0, 50.0, 0.5, -5, 0)] + _corners(92.0, 50.0, 3.2), reference=[R(73.4, 49.0, 0, -5, 0)],
       footprint=[R(98, 56)]),
    _c("vm_056", "Voltímetro/amperímetro 0.56\"", "Displays", "Panel a presión 45.5×26.5",
       cutouts=[R(45.5, 26.5)], reference=[R(48, 29, 1)], footprint=[R(45, 26)]),
    _c("seg7_4dig", "Display 7 seg. 4 dígitos 0.56\"", "Displays", "Ventana 50×19",
       cutouts=[R(50.5, 19.5, 0.5)], reference=[R(50.3, 19.0)], footprint=[R(50, 19)]),
    # ---------------------------------------------------------------- conectores
    _c("banana_4mm", "Borne banana 4 mm", "Conectores", "Borne de unión, Ø8",
       cutouts=[C(8.2)], reference=[C(13)], footprint=[C(12)]),
    _c("banana_socket", "Hembra banana 4 mm (empotrar)", "Conectores", "Ø6.2",
       cutouts=[C(6.2)], reference=[C(10)], footprint=[C(10)]),
    _c("bnc", "BNC de panel", "Conectores", "Agujero en D 9.7 mm, plano a 4.45",
       cutouts=[{"shape": "dhole", "d": 9.7, "flat": 4.45}], reference=[C(14)], footprint=[C(13)]),
    _c("bnc_4h", "BNC brida 4 tornillos", "Conectores", "Brida 18×18, M2.5 a 12.7",
       cutouts=[C(12.7)] + _corners(12.7, 12.7, 2.7), reference=[R(18, 18, 1)], footprint=[R(18, 18)]),
    _c("rca", "RCA de panel", "Conectores", "Rosca M6", cutouts=[C(6.5)], reference=[C(10)], footprint=[C(10)]),
    _c("xlr_d", "XLR (formato D, Neutrik)", "Conectores", "Ø24 + 2×M3 en diagonal 19×24",
       cutouts=[C(24.0), C(3.2, -9.5, 12.0), C(3.2, 9.5, -12.0)], reference=[R(26, 31, 2)],
       footprint=[C(24)]),
    _c("jack_35", "Jack 3.5 mm (Thonkiconn)", "Conectores", "Rosca M6", cutouts=[C(6.0)], reference=[C(8)],
       footprint=[R(9, 10.5)]),
    _c("jack_635", "Jack 6.35 mm", "Conectores", "Rosca 3/8\"", cutouts=[C(9.5)], reference=[C(13)],
       footprint=[R(15, 20)]),
    _c("jack_dc", "Conector DC 5.5×2.1", "Conectores", "Rosca M8", cutouts=[C(8.1)], reference=[C(11)],
       footprint=[C(11)]),
    _c("usb_a", "USB-A de panel", "Conectores", "Ventana 13.5×6.5, M3 a 28 mm",
       cutouts=[R(13.5, 6.5, 0.5), C(3.2, -14, 0), C(3.2, 14, 0)], reference=[R(36, 10, 1.5)],
       footprint=[R(16, 8)]),
    _c("usb_b", "USB-B de panel", "Conectores", "Ventana 12.5×11.5, M3 a 30 mm",
       cutouts=[R(12.5, 11.5, 0.5), C(3.2, -15, 0), C(3.2, 15, 0)], reference=[R(38, 14, 1.5)],
       footprint=[R(15, 14)]),
    _c("usb_c", "USB-C de panel", "Conectores", "Ventana 9.5×3.7, M2 a 16 mm",
       cutouts=[R(9.5, 3.7, 1.5), C(2.2, -8, 0), C(2.2, 8, 0)], reference=[R(21, 7, 2)],
       footprint=[R(12, 6)]),
    _c("rj45", "RJ45 de panel", "Conectores", "Ventana 16×14, M3 a 28 mm",
       cutouts=[R(16.2, 14.2, 0.5), C(3.2, -14, 0), C(3.2, 14, 0)], reference=[R(36, 20, 2)],
       footprint=[R(16, 21)]),
    _c("iec_c14", "IEC C14 (atornillar)", "Conectores", "Ventana 27.5×20, M3 a 40 mm",
       cutouts=[R(27.5, 20.0, 1.0), C(3.2, -20, 0), C(3.2, 20, 0)], reference=[R(48, 22, 2)],
       footprint=[R(28, 20)]),
    _c("iec_c14_snap", "IEC C14 (a presión)", "Conectores", "Ventana 27.5×19.5",
       cutouts=[{"shape": "poly", "closed": True,
                 "pts": [[-13.75, -9.75], [13.75, -9.75], [13.75, 5.75], [9.75, 9.75], [-9.75, 9.75], [-13.75, 5.75]]}],
       reference=[R(31, 23, 1)], footprint=[R(28, 20)]),
    _c("iec_fused", "IEC C14 con fusible e interruptor", "Conectores", "Módulo 47×28",
       cutouts=[R(47.5, 28.0, 1.0)], reference=[R(50, 31, 2)], footprint=[R(47, 28)]),
    _c("fuse_holder", "Portafusibles de panel 5×20", "Conectores", "Rosca M12, plano a 5.6",
       cutouts=[{"shape": "dhole", "d": 12.5, "flat": 5.6}], reference=[C(17)], footprint=[C(13)]),
    _c("db9", "D-Sub DB9", "Conectores", "Tornillos a 25 mm",
       cutouts=[{"shape": "poly", "closed": True,
                 "pts": [[-9.3, 3.2], [9.3, 3.2], [8.1, -3.2], [-8.1, -3.2]]}, C(3.1, -12.5, 0), C(3.1, 12.5, 0)],
       reference=[R(31, 12.5, 1)], footprint=[R(31, 12.5)]),
    _c("sma", "SMA de panel", "Conectores", "Rosca 1/4\"", cutouts=[C(6.5)], reference=[C(8)]),
    _c("midi_din5", "DIN-5 (MIDI)", "Conectores", "Ø15 + 2×M3 a 22.5",
       cutouts=[C(15.5), C(3.2, -11.25, 0), C(3.2, 11.25, 0)], reference=[C(20)], footprint=[R(20, 20)]),
    _c("speakon", "Speakon NL4 (formato D)", "Conectores", "Ø24 + 2×M3",
       cutouts=[C(24.0), C(3.2, -9.5, 12.0), C(3.2, 9.5, -12.0)], reference=[R(26, 31, 2)], footprint=[C(24)]),
    # ---------------------------------------------------------------- bornes
    _c("term_2p", "Bornera de panel 2 polos", "Bornes", "Ventana 11×8, M3 a 22 mm",
       cutouts=[R(11, 8, 0.5), C(3.2, -11, 0), C(3.2, 11, 0)], reference=[R(28, 12, 1)], footprint=[R(14, 10)]),
    _c("term_4p", "Bornera de panel 4 polos", "Bornes", "Ventana 21×8, M3 a 32 mm",
       cutouts=[R(21, 8, 0.5), C(3.2, -16, 0), C(3.2, 16, 0)], reference=[R(38, 12, 1)], footprint=[R(24, 10)]),
    _c("binding_post_pair", "Par de bornes 19 mm (estándar)", "Bornes", "Separación normalizada 19.05 mm",
       cutouts=[C(8.2, -9.525, 0), C(8.2, 9.525, 0)], reference=[C(13, -9.525, 0), C(13, 9.525, 0)],
       graphics=[{"shape": "text", "text": "+", "x": -9.525, "y": 8.5, "size": 3},
                 {"shape": "text", "text": "-", "x": 9.525, "y": 8.5, "size": 3}]),
    # ---------------------------------------------------------------- ventiladores
    _c("fan_40", "Ventilador 40 mm", "Ventiladores", "Taladros a 32 mm", **_fan(40, 32.0, 3.4)),
    _c("fan_60", "Ventilador 60 mm", "Ventiladores", "Taladros a 50 mm", **_fan(60, 50.0, 4.3)),
    _c("fan_80", "Ventilador 80 mm", "Ventiladores", "Taladros a 71.5 mm", **_fan(80, 71.5, 4.3)),
    _c("fan_92", "Ventilador 92 mm", "Ventiladores", "Taladros a 82.5 mm", **_fan(92, 82.5, 4.3)),
    _c("fan_120", "Ventilador 120 mm", "Ventiladores", "Taladros a 105 mm", **_fan(120, 105.0, 4.3)),
    _c("fan_60_grill", "Ventilador 60 mm (rejilla)", "Ventiladores", "Rejilla hexagonal Ø4",
       **_fan(60, 50.0, 4.3, grill=True)),
    _c("fan_80_grill", "Ventilador 80 mm (rejilla)", "Ventiladores", "Rejilla hexagonal Ø4",
       **_fan(80, 71.5, 4.3, grill=True)),
    # ---------------------------------------------------------------- instrumentos
    _c("meter_85c1", "Galvanómetro 85C1", "Instrumentos", "Ø56 + 4×M3",
       cutouts=[C(56.0)] + _corners(46.0, 46.0, 3.5), reference=[R(64, 56, 2)], footprint=[C(56)]),
    _c("meter_91c4", "Galvanómetro 91C4", "Instrumentos", "Ø36 + 2×M3",
       cutouts=[C(36.5), C(3.2, -15.5, 15.5), C(3.2, 15.5, 15.5)], reference=[R(64, 56, 2)], footprint=[C(37)]),
]


# ---------------------------------------------------------------- rejillas de ventilador
# (tamaño, separación de taladros, Ø de recorte habituales)
FAN_SIZES = [(40, 32.0, (38,)), (50, 40.0, (48,)), (60, 50.0, (57, 60)), (70, 60.0, (67,)),
             (80, 71.5, (76, 77)), (92, 82.5, (89, 90)), (120, 105.0, (115, 118)), (140, 124.5, (136,))]
CSK = {"M3": (3.4, 6.7), "M4": (4.5, 9.0)}
FAN_NAME_TPL = {
    ("cut", "hole"): "Recorte para ventilador {s} × {s} Ø{d}; orificio Ø{h}",
    ("cut", "csk"): "Recorte para ventilador {s} × {s} Ø{d}; avellanado {m}",
    ("arc", "hole"): "Ranura curvada para ventilador {s} × {s} Ø{d}; orificio Ø{h}",
    ("arc", "csk"): "Ranura curvada para ventilador {s} × {s} Ø{d}; avellanado {m}",
    ("hex", "hole"): "Rejilla hexagonal para ventilador {s} × {s} Ø{d}; orificio Ø{h}",
    ("hex", "csk"): "Rejilla hexagonal para ventilador {s} × {s} Ø{d}; avellanado {m}",
}


def _arc_grille(D: float, size: float):
    """Anillos concéntricos de ranuras curvadas (4 por anillo, puentes en los ejes)."""
    w = 2.5 if size <= 40 else (3.0 if size <= 60 else 4.0)
    web = 2.0 if size <= 60 else 2.5
    hub = size * 0.22
    out = []
    r = D / 2 - w / 2
    while r - w / 2 >= hub:
        gap = math.degrees(((web + w) / 2) / r)
        for q in range(4):
            out.append({"shape": "arcslot", "r": round(r, 3), "w": w, "a0": round(q * 90 + gap, 3),
                        "a1": round((q + 1) * 90 - gap, 3)})
        r -= w + web
    return out


def _fan_family():
    comps = []
    for size, pitch, diams in FAN_SIZES:
        holes = [("hole", 3.2), ("hole", 3.7), ("csk", "M3")] if size <= 60 else [("hole", 4.3), ("csk", "M4")]
        for style in ("cut", "arc", "hex"):
            for D in diams:
                for hk, hv in holes:
                    if hk == "hole":
                        hd, ref_d, hname = hv, None, f"{hv:g}"
                        args = {"s": size, "d": f"{D:g}", "h": f"{hv:g}"}
                    else:
                        hd, ref_d = CSK[hv]
                        hname = "csk_" + hv.lower()
                        args = {"s": size, "d": f"{D:g}", "m": hv}
                    if style == "cut":
                        body = [C(D)]
                    elif style == "arc":
                        body = _arc_grille(D, size)
                    else:
                        body = _honeycomb(D, 4.0 if size <= 60 else 5.0, 1.2 if size <= 60 else 1.5)
                    holes_c = _corners(pitch, pitch, hd)
                    ref = [R(size, size, 3.0)] + ([C(ref_d, x=h["x"], y=h["y"]) for h in holes_c] if ref_d else [])
                    tpl = FAN_NAME_TPL[(style, hk)]
                    name = tpl.format(**args)
                    desc = f"{size}×{size} mm · taladros a {pitch:g} mm"
                    if ref_d:
                        desc += f" · avellanado 90° Ø{ref_d:g}"
                    c = _c(f"fang_{style}_{size}_{D:g}_{hname}".replace(".", "p"), name, "Rejillas de ventilador", desc,
                           cutouts=body + holes_c, reference=ref, footprint=[R(size, size, 3.0)])
                    c["name_fmt"] = {"tpl": tpl, "args": args}
                    comps.append(c)
    return comps


BUILTIN += _fan_family()


def comp_name(c: dict) -> str:
    """Nombre visible (traducido) de un componente, incluidos los generados por plantilla."""
    from ..i18n import tr
    nf = c.get("name_fmt") if isinstance(c, dict) else None
    if nf and nf.get("tpl"):
        try:
            return tr(nf["tpl"]).format(**nf.get("args", {}))
        except (KeyError, IndexError, ValueError):
            pass
    return tr(c.get("name", "")) if isinstance(c, dict) else ""


def user_library_dir() -> str:
    base = os.environ.get("EFPD_HOME")
    if not base:
        if os.name == "nt":
            base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "EFPD")
        else:
            base = os.path.join(os.path.expanduser("~"), ".local", "share", "efpd")
    path = os.path.join(base, "componentes")
    os.makedirs(path, exist_ok=True)
    return path


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s.lower()).strip("_")
    return s or "componente"


def validate(comp: dict) -> List[str]:
    """Devuelve lista de errores (vacía si es válido)."""
    from ..i18n import tr
    errs = []
    if not comp.get("name"):
        errs.append(tr("Falta el nombre"))
    shapes = ("circle", "rect", "oval", "dhole", "ellipse", "poly", "text", "arcslot")
    for key in ("cutouts", "reference", "footprint", "graphics"):
        lst = comp.get(key, [])
        if not isinstance(lst, list):
            errs.append(tr("'{k}' debe ser una lista").format(k=key))
            continue
        for i, s in enumerate(lst):
            if not isinstance(s, dict) or s.get("shape") not in shapes:
                errs.append(tr("{k}[{i}]: forma desconocida").format(k=key, i=i))
    if not comp.get("cutouts") and not comp.get("graphics"):
        errs.append(tr("El componente no tiene mecanizados ni gráficos"))
    return errs


BUILTIN_LIBRARY = "Biblioteca integrada"
DEFAULT_USER_LIBRARY = "Mis componentes"


class Library:
    """Biblioteca integrada (sólo lectura) + bibliotecas de usuario.

    Cada biblioteca de usuario es un fichero JSON en la carpeta de usuario::

        {"format": "efpd-library", "name": "Mi biblioteca", "components": [ {...}, ... ]}

    (Se siguen leyendo los ficheros antiguos de un solo componente.)
    """

    def __init__(self, user_dir: Optional[str] = None):
        self.user_dir = user_dir or user_library_dir()
        self.items: Dict[str, dict] = {}
        self.libraries: Dict[str, str] = {}  # nombre -> ruta del fichero
        self.reload()

    # ------------------------------------------------------------ lectura
    def reload(self):
        self.items = {}
        for c in BUILTIN:
            c2 = copy.deepcopy(c)
            c2["library"] = BUILTIN_LIBRARY
            self.items[c2["id"]] = c2
        self.libraries = {}
        for fn in sorted(os.listdir(self.user_dir)):
            if not fn.lower().endswith(".json"):
                continue
            path = os.path.join(self.user_dir, fn)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("format") == "efpd-library":
                name = str(data.get("name") or os.path.splitext(fn)[0])
                comps = data.get("components", [])
            else:  # formato antiguo: un componente (o lista) por fichero
                name = DEFAULT_USER_LIBRARY
                comps = data if isinstance(data, list) else [data]
            self.libraries.setdefault(name, path)
            for c in comps:
                if isinstance(c, dict) and not validate(c):
                    c["builtin"] = False
                    c["library"] = name
                    c.setdefault("id", "user_" + slugify(c["name"]))
                    c.setdefault("category", "Personalizados")
                    self.items[c["id"]] = c

    def library_names(self) -> List[str]:
        """Bibliotecas de usuario (editables)."""
        return sorted(self.libraries, key=str.lower)

    def tree(self) -> Dict[str, Dict[str, List[dict]]]:
        """{biblioteca: {categoría: [componentes]}} — la integrada primero."""
        out: Dict[str, Dict[str, List[dict]]] = {BUILTIN_LIBRARY: {}}
        for name in self.library_names():
            out[name] = {}
        for c in self.items.values():
            lib = out.setdefault(c.get("library", BUILTIN_LIBRARY), {})
            lib.setdefault(c.get("category", "Otros"), []).append(c)
        for cats in out.values():
            for v in cats.values():
                v.sort(key=lambda c: c["name"].lower())
        return {k: dict(sorted(v.items())) for k, v in out.items()}

    def categories(self) -> Dict[str, List[dict]]:
        cats: Dict[str, List[dict]] = {}
        for c in self.items.values():
            cats.setdefault(c.get("category", "Otros"), []).append(c)
        for v in cats.values():
            v.sort(key=lambda c: c["name"])
        return dict(sorted(cats.items()))

    def get(self, cid: str) -> Optional[dict]:
        c = self.items.get(cid)
        return copy.deepcopy(c) if c else None

    # ------------------------------------------------------------ escritura
    def _lib_path(self, name: str) -> str:
        if name in self.libraries:
            return self.libraries[name]
        base = slugify(name)
        path, n = os.path.join(self.user_dir, base + ".json"), 2
        used = set(self.libraries.values())
        while os.path.exists(path) or path in used:
            path, n = os.path.join(self.user_dir, f"{base}_{n}.json"), n + 1
        return path

    def _write_library(self, name: str) -> None:
        path = self._lib_path(name)
        comps = [{k: v for k, v in c.items() if k not in ("builtin", "library")}
                 for c in self.items.values() if c.get("library") == name and not c.get("builtin")]
        comps.sort(key=lambda c: c["name"].lower())
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"format": "efpd-library", "name": name, "components": comps}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        self.libraries[name] = path

    def create_library(self, name: str) -> str:
        from ..i18n import tr
        name = name.strip()
        if not name or name == BUILTIN_LIBRARY:
            raise ValueError(tr("Nombre de biblioteca no válido"))
        if name not in self.libraries:
            self._write_library(name)
        return name

    def save_user(self, comp: dict, library: Optional[str] = None) -> str:
        """Guarda (o mueve) un componente en una biblioteca de usuario, creándola si no existe."""
        errs = validate(comp)
        if errs:
            raise ValueError("; ".join(errs))
        comp = copy.deepcopy(comp)
        lib = (library or comp.get("library") or DEFAULT_USER_LIBRARY).strip()
        if lib == BUILTIN_LIBRARY:
            lib = DEFAULT_USER_LIBRARY
        cid = comp.get("id")
        prev = self.items.get(cid) if cid else None
        if not cid or (prev is not None and prev.get("builtin")):
            base = "user_" + slugify(comp["name"])
            cid, n = base, 2
            while cid in self.items:
                cid, n = f"{base}_{n}", n + 1
        old_lib = prev.get("library") if prev is not None and not prev.get("builtin") else None
        comp.update({"id": cid, "builtin": False, "library": lib})
        comp.setdefault("category", "Personalizados")
        self.items[cid] = comp
        self._write_library(lib)
        if old_lib and old_lib != lib and old_lib in self.libraries:
            self._write_library(old_lib)
        return cid

    def delete_user(self, cid: str) -> bool:
        c = self.items.get(cid)
        if not c or c.get("builtin"):
            return False
        del self.items[cid]
        if c.get("library") in self.libraries:
            self._write_library(c["library"])
        return True

    def delete_library(self, name: str) -> bool:
        path = self.libraries.pop(name, None)
        if not path:
            return False
        self.items = {k: v for k, v in self.items.items() if v.get("library") != name}
        if os.path.exists(path):
            os.remove(path)
        return True

    def export_library(self, name: str, dest: str) -> None:
        self._write_library(name)
        import shutil
        shutil.copyfile(self.libraries[name], dest)

    def import_library(self, path: str) -> str:
        """Importa un fichero de biblioteca (se fusiona si ya existe una con el mismo nombre)."""
        from ..i18n import tr
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("format") == "efpd-library":
            name, comps = str(data.get("name") or "Importada"), data.get("components", [])
        elif isinstance(data, (list, dict)):
            name = os.path.splitext(os.path.basename(path))[0]
            comps = data if isinstance(data, list) else [data]
        else:
            raise ValueError(tr("El fichero no es una biblioteca válida"))
        if name == BUILTIN_LIBRARY:
            name += " (2)"
        ok = 0
        for c in comps:
            if isinstance(c, dict) and not validate(c):
                c = dict(c)
                if c.get("id") in self.items and self.items[c["id"]].get("library") != name:
                    c.pop("id")
                c["builtin"] = False
                c["library"] = name
                c.setdefault("category", "Personalizados")
                if not c.get("id"):
                    base, n = "user_" + slugify(c["name"]), 2
                    c["id"] = base
                    while c["id"] in self.items:
                        c["id"], n = f"{base}_{n}", n + 1
                self.items[c["id"]] = c
                ok += 1
        if not ok:
            raise ValueError(tr("El fichero no contiene componentes válidos"))
        self._write_library(name)
        return name


TEMPLATE = {
    "name": "Mi componente", "category": "Personalizados", "description": "",
    "cutouts": [{"shape": "circle", "d": 10.0}, {"shape": "circle", "d": 3.2, "x": -12, "y": 0},
                {"shape": "circle", "d": 3.2, "x": 12, "y": 0}],
    "reference": [{"shape": "rect", "w": 30, "h": 14, "r": 2}],
    "footprint": [{"shape": "rect", "w": 20, "h": 14}],
    "graphics": [],
}


def component_from_entities(doc, entities, name: str, category: str = "Personalizados") -> dict:
    """Crea una definición de componente a partir de entidades seleccionadas.

    Las entidades en capas de proceso 'ref' van a 'reference'; el resto de
    formas simples, a 'cutouts'. Las coordenadas se centran en la caja común.
    """
    from . import geometry as G
    ev = doc.evaluator()
    b = None
    for e in entities:
        b = G.bbox_union(b, e.bbox(doc, ev))
    cx, cy = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) if b else (0.0, 0.0)
    from ..i18n import tr
    comp = {"name": name, "category": category, "description": tr("Creado desde selección"),
            "cutouts": [], "reference": [], "footprint": [], "graphics": []}
    for e in entities:
        proc = doc.process_of(e.layer)
        dest = {"ref": "reference", "print": "graphics", "engrave": "graphics"}.get(proc, "cutouts")
        for role, pr in e.geometry(doc, ev):
            d = dest if role == "main" else {"ref": "reference", "footprint": "footprint"}.get(role, "graphics")
            if pr["t"] == "circle":
                comp[d].append({"shape": "circle", "d": round(pr["r"] * 2, 4),
                                "x": round(pr["c"][0] - cx, 4), "y": round(pr["c"][1] - cy, 4)})
            elif pr["t"] == "poly":
                comp[d].append({"shape": "poly", "closed": pr.get("closed", True),
                                "pts": [[round(x - cx, 4), round(y - cy, 4)] for x, y in pr["pts"]]})
    return comp
