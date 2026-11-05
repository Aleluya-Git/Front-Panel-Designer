"""Pruebas del núcleo (sin GUI). Ejecutar: python -m unittest discover -s tests -v"""
import json
import math
import os
import struct
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("EFPD_HOME", tempfile.mkdtemp(prefix="efpd_test_"))

from efpd.core import geometry as G  # noqa: E402
from efpd.core import layout  # noqa: E402
from efpd.core.checks import check, measure_between  # noqa: E402
from efpd.core.document import Document, apply_preset, PRESETS  # noqa: E402
from efpd.core.entities import TYPES, entity_from_dict, ComponentEntity, HoleEntity, CircleEntity, \
    RectEntity, TextEntity, PocketEntity, DimensionEntity  # noqa: E402
from efpd.core.expr import Evaluator, ExprError, parse_number  # noqa: E402
from efpd.core.history import History  # noqa: E402
from efpd.core.library import Library, BUILTIN, validate, component_from_entities  # noqa: E402
from efpd.io import dxf_export, dxf_import, svg_export, svg_import, mesh, gcode, project  # noqa: E402

TMP = tempfile.mkdtemp(prefix="efpd_out_")


def sample_doc():
    doc = Document()
    doc.panel.w, doc.panel.h, doc.panel.t = 200.0, 100.0, 2.0
    doc.variables["paso"] = 40.0
    lib = Library()
    for i, cid in enumerate(["pot_16mm", "pot_16mm", "jack_35", "led_5mm"]):
        doc.add(ComponentEntity(x=f"=30 + {i}*paso", y=55, comp=lib.get(cid), label=f"C{i}"))
    doc.add(ComponentEntity(x=100, y=22, comp=lib.get("lcd_1602")))
    doc.add(HoleEntity(x=5, y=5, kind="avellanado", screw="M3"))
    doc.add(HoleEntity(x=195, y=5, kind="roscado", screw="M4"))
    doc.add(PocketEntity(x=170, y=22, w=30, h=20, depth=0.8, layer="pocket"))
    doc.add(TextEntity(x="=W/2", y=90, text="FUENTE LAB 0-30V", size=4))
    doc.add(DimensionEntity(a={"ref": "panel", "anchor": "bl"}, b={"ref": doc.entities[0].id, "anchor": "c"}))
    return doc


class T(unittest.TestCase):
    def test_geometry(self):
        self.assertAlmostEqual(G.area(G.rect_poly(10, 5)), 50.0)
        self.assertAlmostEqual(abs(G.area(G.circle_poly(0, 0, 10))), math.pi * 100, delta=1.0)
        self.assertTrue(G.point_in_poly((0, 0), G.rect_poly(2, 2)))
        self.assertAlmostEqual(G.poly_distance(G.rect_poly(2, 2), G.transform_pts(G.rect_poly(2, 2), 5, 0)), 3.0)
        off = G.offset_poly(G.rect_poly(10, 10), -1)
        self.assertAlmostEqual(G.area(off), 64.0, places=6)
        tz = G.trapezoids([G.rect_poly(10, 10), G.rect_poly(4, 4)])
        a = sum((y1 - y0) * ((xr0 - xl0) + (xr1 - xl1)) / 2 for y0, y1, xl0, xl1, xr0, xr1 in tz)
        self.assertAlmostEqual(a, 84.0, places=6)

    def test_expr(self):
        ev = Evaluator({"a": "=b*2", "b": 3}, {"W": 100})
        self.assertEqual(ev.value("=a + W/4"), 31.0)
        self.assertEqual(ev.value("=max(1, sqrt(16))"), 4.0)
        with self.assertRaises(ExprError):
            Evaluator({"x": "=y", "y": "=x"}).value("=x")
        with self.assertRaises(ExprError):
            ev.value("=__import__('os')")
        self.assertEqual(parse_number("2,5"), 2.5)
        self.assertEqual(parse_number("W/2"), "=W/2")

    def test_entities_roundtrip(self):
        doc = Document()
        for t, cls in TYPES.items():
            e = cls()
            doc.add(e)
            e2 = entity_from_dict(json.loads(json.dumps(e.to_dict())))
            self.assertEqual(e2.TYPE, t)
            list(e.geometry(doc, doc.evaluator()))

    def test_param_link(self):
        doc = sample_doc()
        e = doc.entities[1]
        ev = doc.evaluator()
        self.assertAlmostEqual(e.v(ev, "x"), 70.0)
        doc.variables["paso"] = 50
        self.assertAlmostEqual(e.v(doc.evaluator(), "x"), 80.0)
        e.move(5, 0)
        self.assertTrue(str(e.p["x"]).startswith("="))
        self.assertAlmostEqual(e.v(doc.evaluator(), "x"), 85.0)

    def test_history(self):
        doc = sample_doc()
        h = History(doc)
        n = len(doc.entities)
        h.checkpoint("Añadir")
        doc.add(CircleEntity(x=10, y=10))
        self.assertEqual(len(doc.entities), n + 1)
        h.undo()
        self.assertEqual(len(doc.entities), n)
        h.redo()
        self.assertEqual(len(doc.entities), n + 1)

    def test_layout(self):
        doc = Document()
        es = [doc.add(CircleEntity(x=x, y=y, d=10)) for x, y in ((10, 10), (30, 20), (90, 30))]
        layout.align(doc, es, "bottom")
        ev = doc.evaluator()
        self.assertTrue(all(abs(e.v(ev, "y") - 10) < 1e-6 for e in es))
        layout.distribute(doc, es, "h")
        self.assertAlmostEqual(es[1].v(doc.evaluator(), "x"), 50.0)
        layout.distribute_on_panel(doc, es, "h", 20)
        doc.panel.w = 300
        self.assertAlmostEqual(es[2].v(doc.evaluator(), "x"), 280.0)
        new = layout.make_array(doc, es[:1], 3, 2, 10, 10)
        self.assertEqual(len(new), 5)
        dims = layout.auto_dimension(doc, es)
        self.assertTrue(dims)

    def test_presets(self):
        for p in PRESETS:
            d = Document()
            apply_preset(d, p)
            self.assertGreater(d.panel_dims()[0], 10)

    def test_library(self):
        lib = Library()
        self.assertGreaterEqual(len(BUILTIN), 50)
        for c in BUILTIN:
            self.assertEqual(validate(c), [], c["id"])
        doc = Document()
        es = [doc.add(CircleEntity(x=10, y=10, d=6)), doc.add(RectEntity(x=30, y=10, w=10, h=4))]
        comp = component_from_entities(doc, es, "Prueba")
        cid = lib.save_user(comp, "Biblioteca A")
        cid2 = lib.save_user(dict(comp, name="Otro"), "Biblioteca B")
        lib2 = Library()
        self.assertIn(cid, lib2.items)
        self.assertEqual(set(lib2.library_names()) >= {"Biblioteca A", "Biblioteca B"}, True)
        self.assertEqual(lib2.items[cid]["library"], "Biblioteca A")
        moved = lib2.save_user(lib2.get(cid), "Biblioteca B")  # mover de biblioteca
        lib3 = Library()
        self.assertEqual(lib3.items[moved]["library"], "Biblioteca B")
        self.assertEqual(len(lib3.tree()["Biblioteca B"]["Personalizados"]), 2)
        out = os.path.join(TMP, "lib.json")
        lib3.export_library("Biblioteca B", out)
        lib3.delete_library("Biblioteca B")
        self.assertNotIn("Biblioteca B", Library().library_names())
        self.assertEqual(Library().import_library(out), "Biblioteca B")
        self.assertTrue(Library().delete_user(cid2))

    def test_checks(self):
        doc = sample_doc()
        issues = check(doc)
        self.assertTrue(issues)
        a = doc.add(CircleEntity(x=100, y=80, d=10))
        b = doc.add(CircleEntity(x=105, y=80, d=10))
        msgs = [i.message for i in check(doc)]
        self.assertTrue(any("solapan" in m for m in msgs))
        c, gap, *_ = measure_between(doc, a, b)
        self.assertAlmostEqual(c, 5.0)
        doc.add(CircleEntity(x=-5, y=50, d=4))
        self.assertTrue(any("sale del panel" in i.message for i in check(doc)))

    def test_exports(self):
        doc = sample_doc()
        p = os.path.join(TMP, "t.dxf")
        n = dxf_export.export_dxf(doc, p)
        self.assertGreater(n, 10)
        ent = dxf_import.import_dxf(p)
        self.assertGreater(len(ent.p["paths"]), 5)
        s = os.path.join(TMP, "t.svg")
        svg_export.export_svg(doc, s)
        svg_export.export_svg(doc, os.path.join(TMP, "v.svg"), style="visual")
        ent2 = svg_import.import_svg(s)
        self.assertGreater(len(ent2.p["paths"]), 5)
        st = os.path.join(TMP, "t.stl")
        nt = mesh.export_stl(doc, st)
        with open(st, "rb") as f:
            f.seek(80)
            self.assertEqual(struct.unpack("<I", f.read(4))[0], nt)
        self.assertEqual(os.path.getsize(st), 84 + 50 * nt)
        code, warns = gcode.generate(doc, gcode.GcodeSettings())
        self.assertIn("G2", code)
        self.assertIn("M30", code)
        gcode.export_hpgl(doc, os.path.join(TMP, "t.plt"))

    def test_mesh_volume(self):
        doc = Document()
        doc.panel.w, doc.panel.h, doc.panel.t = 100.0, 50.0, 2.0
        doc.add(RectEntity(x=50, y=25, w=20, h=10))
        m = mesh.build_mesh(doc)
        vol = 0.0
        for a, b, c in m["panel"]:
            vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        self.assertAlmostEqual(vol, (5000 - 200) * 2.0, delta=1.0)

    def test_svg_path_parser(self):
        p = os.path.join(TMP, "logo.svg")
        with open(p, "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 200 100">'
                    '<g transform="translate(10,10)"><path d="M0 0h50v30H0z m60 0 a15 15 0 1 0 30 0 '
                    'a15 15 0 1 0 -30 0z M100,0 C120,0 130,20 150,20 S180,0 190,0 Q195,40 180,60 T150,80"/>'
                    '<circle cx="20" cy="70" r="10"/></g></svg>')
        ent = svg_import.import_svg(p)
        allp = [pt for q in ent.p["paths"] for pt in q["pts"]]
        b = G.bbox(allp)
        self.assertLess(b[2] - b[0], 20.01)
        self.assertEqual(sum(1 for q in ent.p["paths"] if q["closed"]), 3)

    def test_project_io(self):
        doc = sample_doc()
        p = os.path.join(TMP, "p.efpd")
        project.save_project(doc, p)
        d2 = project.load_project(p)
        self.assertEqual(len(d2.entities), len(doc.entities))
        self.assertEqual(d2.variables, doc.variables)
        project.autosave(doc, p)
        self.assertIsNotNone(project.pending_autosave())
        project.clear_autosave()
        self.assertIsNone(project.pending_autosave())


class TScale(unittest.TestCase):
    def test_round_and_linear(self):
        from efpd.core.scale import ScaleEntity, PRESETS, dial_dir
        doc = Document()
        ux, uy = dial_dir(90)
        self.assertAlmostEqual(ux, 0, places=9)
        self.assertAlmostEqual(uy, 1, places=9)
        ev = doc.evaluator()
        e = ScaleEntity(x=50, y=50, v0=0, v1=100, step=10, minor_div=1)
        ticks, labels = e.ticks(ev)
        self.assertEqual(labels[0], "0")
        self.assertEqual(labels[-1], "100")
        self.assertEqual(sum(1 for t in ticks if t[1]), 11)
        self.assertEqual(len(ticks), 21)
        e2 = ScaleEntity(label_mode="texto", texts="OFF;LOW;HIGH")
        self.assertEqual(e2.ticks(ev)[1], ["OFF", "LOW", "HIGH"])
        e3 = ScaleEntity(v0=-12, v1=12, step=6, plus_sign=True)
        self.assertEqual(e3.ticks(ev)[1], ["-12", "-6", "0", "+6", "+12"])
        for name, par in PRESETS.items():
            for style in ("rayas", "puntos", "carácter", "ninguna"):
                for single in (False, True):
                    s_ = ScaleEntity(x=50, y=50, **par)
                    s_.p.update(mark_style=style, single_line=single)
                    geo = s_.geometry(doc, ev)
                    self.assertTrue(geo, (name, style))
        # radio de las rayas: exterior, comienzan en R
        r = ScaleEntity(x=0, y=0, radius=20, len_major=3, label_mode="ninguna", minor_div=0, mark_w=0.2)
        pts = [p for role, pr in r.geometry(doc, ev) if role == "main" for p in pr["pts"]]
        d = [math.hypot(*p) for p in pts]
        self.assertAlmostEqual(min(d), 20.0, delta=0.02)
        self.assertAlmostEqual(max(d), 23.0, delta=0.02)
        # lineal girada 90°: longitud a lo largo de Y
        lin = ScaleEntity(x=0, y=0, shape="lineal", length=60, rot=90, label_mode="ninguna", minor_div=0)
        b = lin.bbox(doc, ev)
        self.assertAlmostEqual(b[3] - b[1], 60.0, delta=1.0)
        # serializa y se exporta
        doc.add(r)
        doc.add(lin)
        from efpd.io import dxf_export
        self.assertGreater(dxf_export.export_dxf(doc, os.path.join(TMP, "scale.dxf")), 20)

    def test_text_styles(self):
        from efpd.core.entities import TextEntity
        doc = Document()
        ev = doc.evaluator()
        plain = TextEntity(text="ABC", size=4)
        und = TextEntity(text="ABC", size=4, underline=True, strike=True, color="#ff0000")
        n0, n1 = len(plain.geometry(doc, ev)), len(und.geometry(doc, ev))
        self.assertEqual(n1, n0 + 2)
        self.assertTrue(all(pr.get("color") == "#ff0000" for _r, pr in und.geometry(doc, ev)))
        old = TextEntity(text="X", bold=True)
        self.assertEqual(old.weight_value(), 700)
        up = TextEntity(text="abc", upper=True)
        self.assertEqual(len(up.geometry(doc, ev)), len(TextEntity(text="ABC").geometry(doc, ev)))
        wide = TextEntity(text="ABC", spacing=200).bbox(doc, ev)
        narrow = TextEntity(text="ABC").bbox(doc, ev)
        self.assertGreater(wide[2] - wide[0], narrow[2] - narrow[0])

    def test_sliders_in_library(self):
        lib = Library()
        ids = [c["id"] for c in BUILTIN if c["category"] == "Potenciómetros deslizantes"]
        self.assertGreaterEqual(len(ids), 7)
        c = lib.get("fader_100")
        self.assertTrue(any(s["shape"] == "oval" for s in c["cutouts"]))


class TTextChecks(unittest.TestCase):
    """La verificación detecta interferencias de textos, escalas y rótulos."""

    def _msgs(self, d):
        return [(i.level, i.message) for i in check(d)]

    def test_text_and_scale_interferences(self):
        from efpd.core.scale import ScaleEntity
        d = Document()
        d.add(HoleEntity(x=30, y=30))
        d.add(ScaleEntity(x=30, y=30, radius=12))                     # correcta
        d.add(TextEntity(x=30, y=30.5, text="VOL", size=4))            # sobre el agujero
        d.add(TextEntity(x=90, y=40, text="AAA", size=4))
        d.add(TextEntity(x=91, y=40, text="BBB", size=4))              # solapa con AAA
        d.add(TextEntity(x=1, y=60, text="BORDE", size=4))             # se sale
        m = self._msgs(d)
        self.assertTrue(any(l == "error" and "VOL" in t and "invade" in t for l, t in m), m)
        self.assertTrue(any("AAA" in t and "BBB" in t and "solapan" in t for _l, t in m), m)
        self.assertTrue(any(l == "error" and "BORDE" in t for l, t in m), m)

    def test_clean_layout_and_hidden_under_knob(self):
        from efpd.core.scale import ScaleEntity
        pot = next(c for c in BUILTIN if c.get("id") == "pot_16mm")
        d = Document()
        d.add(ComponentEntity(x=40, y=40, comp=pot, label="GAIN", label_dy=-22))
        d.add(ScaleEntity(x=40, y=40, radius=14))
        self.assertEqual([i.level for i in check(d)], ["info"], self._msgs(d))
        d.add(ScaleEntity(x=110, y=40, radius=8))
        d.add(ComponentEntity(x=110, y=40, comp=pot))
        self.assertTrue(any("no se verá" in t for _l, t in self._msgs(d)))


class TAutoDims(unittest.TestCase):
    def test_modes(self):
        from efpd.core import autodims
        d = Document()
        h = d.add(HoleEntity(x=30, y=30))
        d.add(RectEntity(x=90, y=40, w=30, h=15))
        self.assertEqual(autodims.build(d, None, "off"), [])
        sa = autodims.build(d, None, "size_all")
        self.assertTrue(sa and all(k == "autodim" for k, _p in sa))
        al = autodims.build(d, None, "all")
        self.assertIn("autopos", {k for k, _p in al})
        self.assertEqual(autodims.build(d, None, "selection"), [])
        sel = autodims.build(d, None, "selection", [h.id])
        self.assertTrue(sel and len(sel) < len(al))
        # las cotas quedan fuera del elemento (debajo / a la derecha)
        ys = [y for _k, p in sa for _x, y in p["pts"]]
        self.assertLess(min(ys), 30 - 1.6)


class TExamples(unittest.TestCase):
    """Los proyectos de ejemplo se abren limpios y cada componente se puede seleccionar."""

    def test_examples(self):
        from efpd.core.hittest import hit_test
        folder = os.path.join(ROOT, "ejemplos")
        revs = set()
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".efpd"):
                continue
            d = project.load_project(os.path.join(folder, name))
            self.assertNotIn(d.revision, revs, "dos documentos con la misma revisión (cachés de la GUI)")
            revs.add(d.revision)
            ev = d.evaluator()
            self.assertFalse(any(e.locked for e in d.entities) or any(L.locked for L in d.layers), name)
            for e in d.entities:
                if e.HAS_POS:
                    self.assertFalse(isinstance(e.p.get("x"), str) or isinstance(e.p.get("y"), str),
                                     f"{name}: «{e.display_name()}» con posición por fórmula")
            self.assertEqual([i.level for i in check(d)], ["info"], [i.message for i in check(d)])
            items = [(e.id, r, pr) for e, r, pr in d.geometry(ev)]
            for e in d.entities:
                if e.TYPE != "component":
                    continue
                cut = next(pr for _e, r, pr in d.geometry(ev, entities=[e]) if r == "cut")
                px, py = cut["c"] if cut["t"] == "circle" else cut["pts"][0]
                self.assertEqual(hit_test(d, items, px, py, 0.4), e.id, f"{name}: {e.display_name()}")


class TStudsGrilles(unittest.TestCase):
    def test_stud_through_and_blind(self):
        from efpd.core.stud import StudEntity
        doc = Document()
        doc.panel.w, doc.panel.h, doc.panel.t = 100.0, 50.0, 2.0
        through = doc.add(StudEntity(x=20, y=25, kind="casquillo", thread="M3"))
        blind = doc.add(StudEntity(x=60, y=25, kind="perno", thread="M4", depth_offset=0.5))
        ev = doc.evaluator()
        roles_t = {r for _e, r, _p in doc.geometry(ev, entities=[through])}
        roles_b = {r for _e, r, _p in doc.geometry(ev, entities=[blind])}
        self.assertIn("cut", roles_t)
        self.assertIn("pocket_back", roles_b)
        self.assertNotIn("cut", roles_b)
        # volumen: agujero pasante Ø5.1 y ciego Ø4.1 de 1.5 mm de profundidad
        m = mesh.build_mesh(doc)
        vol = 0.0
        for a, b, c in m["panel"] + m["pocket"]:
            vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
        exp = 100 * 50 * 2 - math.pi * 2.55 ** 2 * 2 - math.pi * 2.05 ** 2 * 1.5
        self.assertAlmostEqual(vol, exp, delta=1.5)  # círculos aproximados por polígonos
        doc.panel.material = "Metacrilato"
        doc.panel.t = 0.8
        msgs = " ".join(i.message for i in check(doc))
        self.assertIn("panel metálico", msgs)
        self.assertIn("menor que el mínimo", msgs)
        from efpd.io import dxf_export
        dxf_export.export_dxf(doc, os.path.join(TMP, "stud.dxf"))
        self.assertIn("FRESADO_TRASERO", open(os.path.join(TMP, "stud.dxf"), encoding="cp1252").read())
        code, warns = gcode.generate(doc, gcode.GcodeSettings())
        self.assertTrue(any("trasera" in w for w in warns))

    def test_fan_grilles(self):
        from efpd.core.library import comp_name
        lib = Library()
        fam = [c for c in lib.items.values() if c.get("category") == "Rejillas de ventilador"]
        self.assertGreaterEqual(len(fam), 60)
        arc = lib.get("fang_arc_60_60_3p7")
        self.assertTrue(any(s["shape"] == "arcslot" for s in arc["cutouts"]))
        self.assertIn("60 × 60", comp_name(arc))
        doc = Document()
        doc.panel.w, doc.panel.h = 120.0, 120.0
        doc.add(ComponentEntity(x=60, y=60, comp=arc))
        errs = [i for i in check(doc) if i.level == "error"]
        self.assertEqual(errs, [], [i.message for i in errs])
        self.assertAlmostEqual(abs(G.area(G.arc_slot_poly(20, 4, 10, 80))),
                               math.radians(70) * 20 * 4 + math.pi * 4, delta=0.5)

    def test_scale_colors_and_text_rotation(self):
        from efpd.core.scale import ScaleEntity
        doc = Document()
        ev = doc.evaluator()
        e = ScaleEntity(minor_div=1, color="#000001", color_major="#ff0000", color_minor="#00ff00", v1=2, step=1)
        cols = [pr.get("color") for r, pr in e.geometry(doc, ev) if r == "main"]
        self.assertIn("#ff0000", cols)
        self.assertIn("#00ff00", cols)
        self.assertIn("#000001", cols)  # números con el color general
        boxes = []
        for rot in ("0", "90"):
            s_ = ScaleEntity(label_mode="texto", texts="ABCDEFG;X", mark_style="ninguna", text_rot=rot)
            pts = [p for r, pr in s_.geometry(doc, ev) if r == "main" for p in pr["pts"]]
            b = G.bbox(pts)
            boxes.append((b[2] - b[0], b[3] - b[1]))
        self.assertNotAlmostEqual(boxes[0][0], boxes[1][0], delta=0.5)
        old = ScaleEntity(rotate_text=True)  # proyectos antiguos
        self.assertTrue(old.geometry(doc, ev))


class THitTest(unittest.TestCase):
    def test_click_selection(self):
        from efpd.core.hittest import hit_test
        from efpd.core import textpath
        doc = Document()
        r = doc.add(RectEntity(x=35, y=30, w=30, h=20))
        d = doc.add(DimensionEntity(orient="h", offset=8.0, a={"xy": [20, 20]}, b={"xy": [50, 20]}))
        h = doc.add(CircleEntity(x=45, y=36, d=4))
        ev = doc.evaluator()
        items = []
        for e, role, pr in doc.geometry(ev):
            if pr["t"] == "text":
                polys, w = textpath.outlines(pr["text"], "", pr["h"], False, False)
                for pts, closed in polys:
                    items.append((e.id, role, {"t": "poly", "closed": closed,
                                               "pts": [(x - w / 2 + pr["pos"][0], y + pr["pos"][1]) for x, y in pts]}))
            else:
                items.append((e.id, role, pr))
        self.assertEqual(hit_test(doc, items, 24, 36, 0.5), r.id)      # relleno del rectángulo
        self.assertEqual(hit_test(doc, items, 25, 28, 0.5), d.id)      # sobre la línea de cota
        self.assertEqual(hit_test(doc, items, 45, 36, 0.5), h.id)      # agujero dentro del rectángulo
        self.assertEqual(hit_test(doc, items, 20, 34, 0.5), r.id)      # sobre el borde
        self.assertIsNone(hit_test(doc, items, 80, 80, 0.5))

    def test_distribute_ties_follow_drawing_order(self):
        doc = Document()
        es = [doc.add(CircleEntity(x=50, y=10, d=5, name=str(i))) for i in range(4)]
        layout.distribute_on_panel(doc, list(reversed(es)), "h", 10.0)
        ev = doc.evaluator()
        xs = [e.v(ev, "x") for e in es]
        self.assertEqual(xs, sorted(xs))


class TPaintSimulation(unittest.TestCase):
    def test_all_paint_paths_with_fake_qt(self):
        """Ejecuta todos los paintEvent con un Qt simulado (en un proceso aparte, sin PySide6 real)."""
        import subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fake = os.path.join(root, "tests", "fakeqt")
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([fake, root]))
        r = subprocess.run([sys.executable, os.path.join(fake, "simular_dibujado.py")], env=env,
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout[-3000:] + r.stderr[-3000:])
        self.assertIn("lienzo: casos OK", r.stdout)


class TGuiStatic(unittest.TestCase):
    def test_no_signal_connected_to_bare_emit(self):
        """Conectar valueChanged(float) a otra_senal.emit (sin argumentos) falla en silencio en PySide6."""
        import ast
        import glob
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "efpd", "gui")
        bad = []
        for fn in glob.glob(os.path.join(root, "*.py")):
            tree = ast.parse(open(fn, encoding="utf-8").read())
            emit_aliases = set()
            for node in ast.walk(tree):
                if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute)
                        and node.value.attr == "emit"):
                    emit_aliases |= {t.id for t in node.targets if isinstance(t, ast.Name)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "connect":
                    for a in node.args:
                        if (isinstance(a, ast.Attribute) and a.attr == "emit") or \
                                (isinstance(a, ast.Name) and a.id in emit_aliases):
                            bad.append(f"{os.path.basename(fn)}:{node.lineno}")
        self.assertEqual(bad, [])


class TI18n(unittest.TestCase):
    def test_translations_complete(self):
        from efpd import i18n
        keys = i18n.all_strings()
        self.assertGreater(len(keys), 200)
        langs = i18n.available()
        for code in ("en", "de", "fr"):
            self.assertIn(code, langs)
            table = i18n.read_file(langs[code]["path"])["strings"]
            missing = [k for k in keys if not table.get(k)]
            self.assertEqual(missing, [], f"{code}: faltan {len(missing)}")
            for k, v in table.items():  # mismos marcadores {x}
                import re
                self.assertEqual(sorted(re.findall(r"\{\w*\}", k)), sorted(re.findall(r"\{\w*\}", v)), (code, k))
        i18n.set_language("de")
        self.assertNotEqual(i18n.tr("Guardar"), "Guardar")
        p = os.path.join(TMP, "xx.json")
        i18n.make_template(p)
        import json as _j
        d = _j.load(open(p, encoding="utf-8"))
        d["code"], d["language"] = "it", "Italiano"
        d["strings"]["Guardar"] = "Salva"
        _j.dump(d, open(p, "w", encoding="utf-8"))
        self.assertEqual(i18n.install_file(p), "it")
        i18n.set_language("it")
        self.assertEqual(i18n.tr("Guardar"), "Salva")
        i18n.set_language("es")


if __name__ == "__main__":
    unittest.main(verbosity=2)
