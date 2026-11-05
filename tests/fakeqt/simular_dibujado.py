"""Simula todo el dibujado de la interfaz con un Qt falso (tests/fakeqt/PySide6).

No sustituye a la autoprueba con Qt real, pero detecta errores de Python en
los paintEvent (variables pisadas, tipos incorrectos…) sin necesidad de PySide6.
"""
import traceback, sys
from unittest.mock import MagicMock
from PySide6._base import _Meta
class FM:
    def horizontalAdvance(self, t): return 7 * len(t)
    def height(self): return 12
    def boundingRect(self, t):
        m = MagicMock(); m.width.return_value = 7 * len(t); m.height.return_value = 12; return m
def make_p():
    p = MagicMock(); p.fontMetrics.return_value = FM(); p.isActive.return_value = True; return p
class FakePainter(metaclass=_Meta):
    def __new__(cls, *a): return make_p()
from efpd.gui import safepaint, render
import efpd.gui.canvas as C, efpd.gui.comppreview as CP, efpd.gui.view3d as V, efpd.gui.textscale as TS, efpd.gui.studdlg as SD
for mod in (C, CP, V, TS, SD, safepaint):
    mod.QPainter = FakePainter
from efpd.core.document import Document
from efpd.core.entities import ComponentEntity, HoleEntity, PocketEntity, TextEntity, ImageEntity, DimensionEntity, RectEntity
from efpd.core.scale import ScaleEntity, PRESETS
from efpd.core.stud import StudEntity
from efpd.core.library import Library
from efpd.gui.theme import THEMES
lib = Library()
doc = Document(); doc.panel.w, doc.panel.h = 220.0, 100.0
ids=[doc.add(ComponentEntity(x=50+i*30, y=60, comp=lib.get(c), label="AJUSTE")) for i,c in enumerate(("pot_16mm","pot_24mm","fang_arc_60_60_3p7","slide_45"))]
doc.add(HoleEntity(x=6, y=6, kind="avellanado", screw="M3"))
doc.add(PocketEntity(x=60, y=25, w=90, h=40, layer="pocket"))
doc.add(TextEntity(x=100, y=92, text="FUENTE", color="#ff0000", underline=True))
doc.add(ImageEntity(x=20, y=92, w=8, h=8, data=""))
doc.add(DimensionEntity(orient="h", offset=-8, a={"ref":"panel","anchor":"bl"}, b={"ref":ids[0].id,"anchor":"c"}))
doc.add(ScaleEntity(x=50, y=60, **PRESETS["Rotatorio 300° · 0–10"], color_major="#f00"))
doc.add(StudEntity(x=200, y=10, depth_offset=0.5)); doc.add(StudEntity(x=200, y=30))
r = doc.add(RectEntity(x=150, y=20, w=20, h=10))
mw = MagicMock(); mw.doc = doc; mw.colors = THEMES["oscuro"]
cv = C.Canvas(mw)
cv.s, cv.ox, cv.oy = 4.0, 30.0, 500.0
cv.width = lambda: 1200; cv.height = lambda: 700; cv.rect = MagicMock()
cases = 0
for sel in (set(), {r.id}, {ids[0].id, ids[3].id}):
    for flagged in (set(), {r.id}):
        for mode in ("off", "size_all", "all", "selection"):
            for tool, drag in (("select", None), ("rect", {"kind": "create", "p0": (10.0, 10.0), "pending": True}), ("place", None)):
                cv.selected, cv.flagged, cv.auto_dims = sel, flagged, mode
                cv.tool = tool; cv._drag = drag
                cv.place_entity = ScaleEntity() if tool == "place" else None
                cv._cursor_w = (40.0, 30.0); cv._dim_cache = (-1, []); cv._items_rev = -1
                n0 = len(safepaint.ERRORS)
                cv.paintEvent(None); cases += 1
                if len(safepaint.ERRORS) > n0:
                    print("FALLO", bool(sel), bool(flagged), mode, tool); print(safepaint.ERRORS[-1][1][-1200:]); sys.exit(1)
print("lienzo: casos OK", cases)
for m in ("visual", "fab"):
    render.paint_document(make_p(), doc, None, mode=m)
    for am in ("size_all", "all", "selection"):
        its = render.with_auto_dims(doc, render.collect_items(doc), am, [doc.entities[0].id])
        assert any(r in ("autodim", "autopos") for _e, r, _p in its), am
        render.paint_document(make_p(), doc, its, mode=m, show_dims=True)
print("render visual/fab OK (con cotas automáticas)")
for cid in ("xlr_d", "fang_arc_80_77_4p3", "slide_45"):
    CP.paint_component(make_p(), lib.get(cid), 260, 190)
print("miniaturas OK")
v = V.View3D(doc); v.width=lambda:800; v.height=lambda:600; v.rect=MagicMock(); v.paintEvent(None)
ep = TS.EntityPreview(doc); ep.width=lambda:400; ep.height=lambda:300; ep.rect=MagicMock()
for e in (ScaleEntity(**PRESETS["Deslizante 60 mm · dB"]), TextEntity(text="AB\nC", underline=True, strike=True)):
    ep.set_entity(e); ep.paintEvent(None)
sec = SD.StudSection(); sec.width=lambda:340; sec.height=lambda:440; sec.rect=MagicMock()
for kw in (dict(), dict(kind="perno", reverse=False), dict(depth_offset=0.6)):
    sec.set_state(StudEntity(**kw), 2.0); sec.paintEvent(None)
print("3D / vista previa / sección: errores =", len(safepaint.ERRORS))
for w_, t in safepaint.ERRORS: print("ERROR en", w_, t[-1200:])
sys.exit(1 if safepaint.ERRORS else 0)
