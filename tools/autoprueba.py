"""Autoprueba completa: núcleo + interfaz gráfica (sin intervención del usuario).

Genera:
  autoprueba_resultado.txt   resumen y errores detallados
  autoprueba_salida/         archivos exportados y capturas de pantalla

Uso:  python tools/autoprueba.py [--visible]
"""
from __future__ import annotations

import io
import os
import platform
import sys
import tempfile
import time
import traceback
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "autoprueba_salida")
os.makedirs(OUT, exist_ok=True)
os.environ["EFPD_HOME"] = tempfile.mkdtemp(prefix="efpd_autoprueba_")
os.environ["EFPD_NO_DIALOGS"] = "1"
if "--visible" not in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # El modo sin pantalla de Qt no encuentra las fuentes del sistema en Windows: se le indican
    # para que las capturas muestren los textos reales en lugar de cuadraditos.
    _fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    if sys.platform == "win32" and os.path.isdir(_fonts):
        os.environ.setdefault("QT_QPA_FONTDIR", _fonts)

results = []
RESULT = os.path.join(ROOT, "autoprueba_resultado.txt")
HEADER = []
_HANG = open(os.path.join(ROOT, "autoprueba_bloqueo.txt"), "w", encoding="utf-8")  # pila si algo se queda colgado
import faulthandler  # noqa: E402
faulthandler.enable(file=_HANG, all_threads=True)  # cierre brusco (fallo de Qt): deja aquí la traza de Python


def mark(txt):
    """Anota la operación en curso: si el proceso se cierra de golpe, queda la última."""
    _HANG.write(f"  · {txt}\n")
    _HANG.flush()


def write_report(final=False):
    """Escribe el informe (también parcial, tras cada paso, por si el programa se cuelga o se cierra)."""
    lines = list(HEADER)
    ok = sum(1 for st, *_ in results if st == "OK")
    lines.append(f"\nRESULTADO: {ok}/{len(results)} pasos correctos" + ("" if final else "  (EN CURSO / INTERRUMPIDA)") + "\n")
    for st, name, info, dt in results:
        lines.append(f"[{st:5}] {name}  ({dt:.2f} s)" + (f"  → {info}" if st == "OK" and info else ""))
    fails = [(n, i) for st, n, i, _ in results if st != "OK"]
    if fails:
        lines.append("\n================ DETALLE DE ERRORES ================")
        for n, i in fails:
            lines.append(f"\n### {n}\n{i}")
    lines.append(f"\nArchivos generados en: {OUT}")
    text = "\n".join(lines)
    with open(RESULT, "w", encoding="utf-8") as f:
        f.write(text)
    return text, fails


def step(name):
    def deco(fn):
        import faulthandler
        faulthandler.cancel_dump_traceback_later()
        _HANG.seek(0)
        _HANG.truncate()
        _HANG.write(f"Paso en curso: {name}\n")
        _HANG.flush()
        faulthandler.dump_traceback_later(90, exit=True, file=_HANG)  # >90 s en un paso = bloqueo
        t0 = time.time()
        try:
            info = fn()
            results.append(("OK", name, info or "", time.time() - t0))
        except Exception:  # noqa: BLE001
            results.append(("FALLO", name, traceback.format_exc(), time.time() - t0))
        faulthandler.cancel_dump_traceback_later()
        write_report()
        return fn
    return deco


def main():
    HEADER[:] = ["AUTOPRUEBA — Electronic Front Panel Designer",
                 f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                 f"Python {sys.version.split()[0]} · {platform.platform()}"]
    lines = HEADER
    # ------------------------------------------------------------ 1. núcleo
    buf = io.StringIO()
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "tests"))
    r = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
    results.append(("OK" if r.wasSuccessful() else "FALLO", f"Pruebas del núcleo ({r.testsRun} pruebas)",
                    "" if r.wasSuccessful() else buf.getvalue(), 0.0))
    write_report()
    # ------------------------------------------------------------ 2. GUI
    try:
        import PySide6
        from PySide6 import QtCore
        lines.append(f"PySide6 {PySide6.__version__} · Qt {QtCore.qVersion()} · plataforma Qt: "
                     f"{os.environ.get('QT_QPA_PLATFORM', 'nativa')}")
        gui_tests()
    except ImportError as e:
        results.append(("FALLO", "Importar PySide6", str(e) + "\n¿Ejecutó install.bat?", 0.0))
    except Exception:  # noqa: BLE001 - un fallo fuera de los pasos no debe perder el informe
        results.append(("FALLO", "Autoprueba de interfaz (fuera de un paso)", traceback.format_exc(), 0.0))
    text, fails = write_report(final=True)
    print(text)
    import faulthandler
    faulthandler.cancel_dump_traceback_later()
    _HANG.close()
    try:
        os.remove(os.path.join(ROOT, "autoprueba_bloqueo.txt"))
    except OSError:
        pass
    return 0 if not fails else 1


def gui_tests():
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QMouseEvent
    from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

    app = QApplication.instance() or QApplication(sys.argv)
    # Diálogos modales: respuestas automáticas
    QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    QMessageBox.critical = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
    QInputDialog.getText = staticmethod(lambda *a, **k: ("PRUEBA", True))
    QInputDialog.getItem = staticmethod(lambda *a, **k: (a[3][0] if len(a) > 3 else "", True))
    QInputDialog.getDouble = staticmethod(lambda *a, **k: (12.0, True))

    from efpd.gui import qt_text
    from efpd.core import textpath
    from efpd.core import geometry as G
    from efpd.core.document import Document
    from efpd.core.entities import (CircleEntity, ComponentEntity, HoleEntity, ImageEntity, PocketEntity,
                                    TextEntity, TYPES)
    from efpd.io import dxf_import, project, svg_import
    from efpd.gui import render
    from efpd.gui.main_window import MainWindow
    from efpd.gui.view3d import View3D

    def _auto_ask(self, title, text, buttons=None, default=None):
        keys = [b[0] for b in (buttons or [])]
        return "discard" if "discard" in keys else "yes"
    MainWindow._ask = _auto_ask
    from efpd.gui import textscale
    textscale.TextDialog.exec = lambda self: 1      # aceptar sin mostrar
    textscale.ScaleDialog.exec = lambda self: 1
    from efpd.gui import studdlg
    studdlg.StudDialog.exec = lambda self: 1

    st = {}

    @step("Contornos de texto con fuentes del sistema")
    def _():
        qt_text.install()
        polys, w = textpath.outlines("Ag 0-30V", "", 5.0, False, False)
        assert len(polys) >= 6 and w > 10, (len(polys), w)
        return f"{len(polys)} contornos, ancho {w:.1f} mm"

    @step("Crear ventana principal")
    def _():
        st["w"] = MainWindow()
        st["w"].resize(1500, 950)
        st["w"].show()
        app.processEvents()

    w = st.get("w")
    if w is None:
        return
    cv = w.canvas

    def mouse(kind, x, y, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier):
        p = cv.w2s(x, y)
        t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
             "release": QEvent.Type.MouseButtonRelease, "dbl": QEvent.Type.MouseButtonDblClick}[kind]
        buttons = Qt.MouseButton.NoButton if kind == "release" else button
        ev = QMouseEvent(t, QPointF(p), QPointF(cv.mapToGlobal(p.toPoint())), button, buttons, mods)
        {"press": cv.mousePressEvent, "move": cv.mouseMoveEvent, "release": cv.mouseReleaseEvent,
         "dbl": cv.mouseDoubleClickEvent}[kind](ev)

    def drag(x0, y0, x1, y1):
        mouse("press", x0, y0)
        for k in range(1, 6):
            mouse("move", x0 + (x1 - x0) * k / 5, y0 + (y1 - y0) * k / 5)
        mouse("release", x1, y1)

    @step("Plantillas de panel")
    def _():
        w.apply_preset("Eurorack 3U 12HP")
        assert len(w.doc.entities) == 4
        w.apply_preset("Fuente lab. 250×120")
        w.file_new()
        return "Eurorack y fuente de laboratorio"

    @step("Herramientas de dibujo con el ratón")
    def _():
        cv.fit_view()
        n0 = len(w.doc.entities)
        for tool, a, b in (("rect", (20, 20), (50, 40)), ("roundrect", (60, 20), (90, 40)),
                           ("slot", (100, 20), (130, 25)), ("ellipse", (20, 60), (40, 75)),
                           ("circle", (60, 70), (66, 70)), ("polygon", (90, 70), (96, 70)),
                           ("oval", (110, 60), (130, 60)), ("pocket", (140, 15), (155, 45))):
            cv.set_tool(tool)
            drag(*a, *b)
        for tool, pt in (("hole", (10, 10)), ("hole_csk", (150, 10)), ("hole_thread", (10, 70)),
                         ("dhole", (145, 70)), ("text", (80, 52))):
            cv.set_tool(tool)
            mouse("press", *pt)
            mouse("release", *pt)
        cv.set_tool("polyline")
        for pt in ((30, 45), (40, 50), (35, 55)):
            mouse("press", *pt)
            mouse("release", *pt)
        mouse("dbl", 35, 55)
        cv.set_tool("dimension")
        for pt in ((20, 20), (50, 20)):
            mouse("press", *pt)
            mouse("release", *pt)
        cv.set_tool("measure")
        for pt in ((0, 0), (30, 40)):
            mouse("press", *pt)
            mouse("release", *pt)
        assert cv._measure is not None
        made = len(w.doc.entities) - n0
        assert made >= 15, made
        types = sorted({e.TYPE for e in w.doc.entities})
        return f"{made} entidades: {', '.join(types)}"

    @step("Seleccionar, mover, ventana de selección, deshacer/rehacer")
    def _():
        cv.set_tool("select")
        e = w.doc.entities[0]
        ev = w.doc.evaluator()
        x0 = e.v(ev, "x")
        b = e.bbox(w.doc, ev)
        cx, cy = b[0] + 1.5, b[3] - 1.5     # dentro del relleno, lejos de cotas y textos
        mouse("press", cx, cy)
        assert e.id in cv.selected, "no se seleccionó"
        for k in range(1, 6):
            mouse("move", cx + k * 2, cy)
        mouse("release", cx + 10, cy)
        x1 = e.v(w.doc.evaluator(), "x")
        assert abs(x1 - x0 - 10) < 2.6, (x0, x1)
        w.undo()
        assert abs(w.doc.get(e.id).v(w.doc.evaluator(), "x") - x0) < 1e-6
        w.redo()
        drag(-5, -5, 200, 130)
        n = len(cv.selected)
        assert n >= 10, n
        return f"ventana: {n} seleccionadas"

    @step("Copiar, pegar, duplicar, girar, simetría, matriz, bloquear, eliminar")
    def _():
        e = CircleEntity(x=70, y=95, d=6)
        w.doc.add(e)
        w.changed()
        cv.set_selection([e.id])
        w.copy()
        w.paste()
        w.duplicate()
        w.rotate_selected(90)
        w.mirror_selected()
        w.toggle_lock()
        w.toggle_lock()
        from efpd.core import layout
        w.checkpoint("matriz")
        layout.make_array(w.doc, [e], 3, 2, 8, 8)
        w.changed()
        n = len(w.doc.entities)
        cv.set_selection([e.id])
        w.delete_selected()
        assert len(w.doc.entities) == n - 1
        return f"{len(w.doc.entities)} entidades"

    @step("Panel de propiedades para cada tipo de entidad")
    def _():
        for _t, cls in TYPES.items():
            e = cls()
            w.doc.add(e)
            cv.set_selection([e.id])
            app.processEvents()
        cv.set_selection([])
        cv.set_selection([x.id for x in w.doc.entities[:3]])
        app.processEvents()
        return f"{len(TYPES)} tipos"

    @step("Documento de ejemplo con biblioteca, variables y parámetros")
    def _():
        doc = Document()
        doc.panel.w, doc.panel.h, doc.panel.t = "=ancho", 100.0, 2.0
        doc.variables.update({"ancho": 220.0, "margen": 25.0})
        doc.meta["title"] = "Fuente de laboratorio"
        w.set_document(doc)
        lib = w.lib
        ids = []
        for cid in ("pot_16mm", "pot_16mm", "pot_24mm", "toggle_mini"):
            c = ComponentEntity(x=50, y=60, comp=lib.get(cid), label="AJUSTE")
            w.doc.add(c)
            ids.append(c)
        cv.set_selection([c.id for c in ids])
        w.run_layout("dist_panel")
        w.doc.add(ComponentEntity(x=60, y=25, comp=lib.get("lcd_1602")))
        for i, cid in enumerate(("banana_4mm", "banana_4mm", "banana_4mm")):
            w.doc.add(ComponentEntity(x=f"=W - 60 + {i}*19.05", y=25, comp=lib.get(cid), label=["+", "COM", "-"][i]))
        w.doc.add(ComponentEntity(x=150, y=78, comp=lib.get("led_5mm_bezel")))
        for x, y in ((6, 6), ("=W-6", 6), (6, 94), ("=W-6", 94)):
            w.doc.add(HoleEntity(x=x, y=y, kind="avellanado", screw="M3"))
        w.doc.add(PocketEntity(x=60, y=25, w=90, h=40, depth=0.6, r=3, layer="pocket"))
        w.doc.add(TextEntity(x="=W/2", y=92, text="FUENTE DE LABORATORIO 0-30 V / 5 A", size=4, bold=True))
        img = QImage(64, 64, QImage.Format.Format_ARGB32)
        img.fill(QColor("#e5484d"))
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        import base64
        ba = QByteArray()
        b = QBuffer(ba)
        b.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(b, "PNG")
        b.close()
        w.doc.add(ImageEntity(x=20, y=92, w=8, h=8, data=base64.b64encode(bytes(ba.data())).decode()))
        w.changed()
        W1 = ids[-1].v(w.doc.evaluator(), "x")
        w.doc.variables["ancho"] = 260.0
        W2 = ids[-1].v(w.doc.evaluator(), "x")
        assert abs((W2 - W1) - 40.0) < 1e-6, (W1, W2)
        w.doc.variables["ancho"] = 220.0
        w.changed()
        cv.set_selection([])
        w.auto_dimension()
        w.panel_dimensions()
        w.full_refresh()
        cv.fit_view()
        return f"{len(w.doc.entities)} entidades; distribución vinculada a W comprobada"

    @step("Verificación de interferencias")
    def _():
        issues = w.run_checks()
        return f"{len(issues)} resultados: " + "; ".join(i.message for i in issues[:3])

    @step("Capturas del lienzo (tema oscuro y claro)")
    def _():
        from efpd.gui import render as _render
        mark(f"{len(w.doc.entities)} entidades; tipos: {sorted({e.TYPE for e in w.doc.entities})}")
        mark("render.collect_items")
        _render.collect_items(w.doc)
        for m in ("visual", "fab"):
            mark(f"render.render_image {m}")
            _render.render_image(w.doc, 50, m)
        mark("cotas automáticas: _dim_targets")
        cv._dim_cache = (-1, [])
        cv._dim_targets()
        for mode in ("off", "size_all"):
            w._set_auto_dims(mode)
            mark(f"lienzo grab (cotas={mode})")
            cv.grab().save(os.path.join(OUT, f"lienzo_oscuro_{mode}.png"))
        for name, wd in (("biblioteca", w.library_panel), ("propiedades", w.props), ("capas", w.layers_panel),
                         ("variables", w.vars_panel), ("historial", w.history_panel), ("verificacion", w.checks_panel)):
            mark(f"grab panel {name}")
            wd.grab()
        for name, tb in w.toolbars.items():
            mark(f"grab barra {name}")
            tb.grab()
        mark("app.processEvents")
        app.processEvents()
        mark("grab ventana (oscuro)")
        w.grab().save(os.path.join(OUT, "ventana_oscuro.png"))
        mark("cambiar a tema claro")
        w.toggle_theme()
        mark("processEvents tras el tema")
        app.processEvents()
        mark("grab ventana (claro)")
        w.grab().save(os.path.join(OUT, "ventana_claro.png"))
        mark("volver a tema oscuro")
        w.toggle_theme()
        comps = [e for e in w.doc.entities if e.TYPE == "component"]
        mark("seleccionar componente")
        if comps:
            cv.set_selection([comps[0].id])
        w.actions["show_dims"].setChecked(True)
        for mode in ("size_all", "all"):
            mark(f"cotas {mode}")
            w._set_auto_dims(mode)
            app.processEvents()
            cv.grab().save(os.path.join(OUT, f"cotas_{mode}.png"))
        w._set_auto_dims("size_all")
        assert "_grid" in w.toolbars and w.grid_spin is not None
        assert w.actions["snap_grid"] in w.toolbars["_grid"].actions()
        assert w.actions["snap_obj"] in w.toolbars["_grid"].actions()
        return "lienzo/ventana oscuro y claro, cotas_size_all.png, cotas_all.png"

    @step("Texto con estilos (diálogo, color, subrayado, tachado, grosor)")
    def _():
        from efpd.gui.textscale import TextDialog
        n0 = len(w.doc.entities)
        w.place_text(40, 40)
        assert len(w.doc.entities) == n0 + 1
        t = w.doc.entities[-1]
        dlg = TextDialog(w, w.doc, t)
        dlg.text.setPlainText("AJUSTE FINO\nGain")
        dlg.form.set_values({"weight": "negrita", "underline": True, "strike": False, "color": "#d03030",
                             "size": 5.0, "spacing": 120.0, "italic": True})
        params, layer = dlg.result_params()
        assert params["underline"] and params["color"] == "#d03030" and params["weight"] == "negrita"
        dlg.preview.resize(420, 260)
        dlg.preview.grab().save(os.path.join(OUT, "texto_dialogo_vista_previa.png"))
        w.edit_text(t)  # exec aceptado automáticamente
        t.p.update(params)
        w.changed()
        geo = t.geometry(w.doc, w.doc.evaluator())
        assert all(pr.get("color") == "#d03030" for _r, pr in geo)
        return f"{len(geo)} contornos de texto con color"

    @step("Generador de escalas (redonda, lineal sobre deslizante, plantillas)")
    def _():
        from efpd.gui.textscale import ScaleDialog
        from efpd.core.scale import ScaleEntity
        # 1) sobre potenciómetro rotatorio seleccionado
        pot = ComponentEntity(x=60, y=80, comp=w.lib.get("pot_24mm"))
        sl = ComponentEntity(x=150, y=60, comp=w.lib.get("slide_45"))
        w.doc.add(pot)
        w.doc.add(sl)
        w.changed()
        cv.set_selection([pot.id])
        hint, at = w._scale_hint()
        assert hint["shape"] == "redonda" and abs(at[0] - 60) < 1e-6, (hint, at)
        n0 = len(w.doc.entities)
        w.insert_scale()
        sc = w.doc.entities[-1]
        assert len(w.doc.entities) == n0 + 1 and sc.TYPE == "scale"
        # 2) sobre deslizante: lineal, longitud = recorrido, girada 90°
        cv.set_selection([sl.id])
        hint, at = w._scale_hint()
        assert hint["shape"] == "lineal" and abs(hint["length"] - 45) < 1e-6 and abs(hint["rot"] - 90) < 1e-6, hint
        w.insert_scale()
        lin = w.doc.entities[-1]
        assert lin.p["shape"] == "lineal"
        # 3) diálogo con cada plantilla
        dlg = ScaleDialog(w, w.doc, sc)
        for i in range(1, dlg.preset.count()):
            dlg.preset.setCurrentIndex(i)
            dlg._apply_preset(i)
            params, _layer = dlg.result_params()
            e = ScaleEntity()
            e.p.update(params)
            assert e.geometry(w.doc, w.doc.evaluator())
        dlg.preset.setCurrentIndex(dlg.preset.findData("Semicírculo (referencia FPD) 1–10"))
        dlg._apply_preset(0)
        dlg.preview.resize(520, 420)
        dlg.preview.grab().save(os.path.join(OUT, "escala_dialogo_vista_previa.png"))
        dlg.resize(1000, 700)
        dlg.grab().save(os.path.join(OUT, "escala_dialogo.png"))
        # 4) colocar con clic cuando no hay selección
        cv.set_selection([])
        w.insert_scale()
        assert cv.tool == "place"
        assert cv._preview_prims(), "la escala no aparece junto al cursor tras aceptar"
        mouse("press", 120, 100)
        mouse("release", 120, 100)
        assert w.doc.entities[-1].TYPE == "scale" and cv.tool == "select"
        w.edit_scale(w.doc.entities[-1])
        cv.fit_view()
        app.processEvents()
        cv.grab().save(os.path.join(OUT, "lienzo_escalas.png"))
        return f"{dlg.preset.count() - 1} plantillas OK · escalas en lienzo_escalas.png"

    @step("Dibujo con vista previa: arrastrar y modo de dos clics")
    def _():
        snap_obj = w.doc.settings.get("snap_objects", True)
        w.doc.settings["snap_objects"] = False
        cv.set_tool("rect")
        n0 = len(w.doc.entities)
        # modo dos clics: primer clic + soltar sin mover -> pendiente; la forma sigue al cursor
        mouse("press", 30, 30)
        mouse("release", 30, 30)
        assert cv._drag and cv._drag.get("pending"), "no quedó pendiente tras el primer clic"
        mouse("move", 50, 40)
        prims = cv._preview_prims()
        assert prims, "sin vista previa durante la creación"
        txt = cv._preview_size_text()
        assert txt and "20" in txt and "10" in txt, txt
        app.processEvents()
        cv.grab().save(os.path.join(OUT, "dibujo_vista_previa.png"))
        mouse("press", 50, 40)
        mouse("release", 50, 40)
        e = w.doc.entities[-1]
        ev = w.doc.evaluator()
        assert len(w.doc.entities) == n0 + 1 and abs(e.v(ev, "w") - 20) < 1e-6 and abs(e.v(ev, "h") - 10) < 1e-6
        # Esc cancela una creación pendiente
        mouse("press", 10, 10)
        mouse("release", 10, 10)
        from PySide6.QtGui import QKeyEvent
        cv.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        assert cv._drag is None
        cv.set_tool("select")
        w.doc.settings["snap_objects"] = snap_obj
        return f"{txt}; dibujo_vista_previa.png"

    @step("Propiedades agrupadas (posición, tamaño, características, opciones)")
    def _():
        from PySide6.QtWidgets import QGroupBox
        e = w.doc.entities[-1]
        cv.set_selection([e.id])
        app.processEvents()
        titles = [b.title() for b in w.props.widget().findChildren(QGroupBox)]
        from efpd.i18n import tr as _tr
        for t in ("Posición", "Tamaño", "Características", "Opciones"):
            assert _tr(t) in titles, titles
        w.props.resize(320, 700)
        w.props.grab().save(os.path.join(OUT, "propiedades_agrupadas.png"))
        return ", ".join(titles)

    @step("Pernos y casquillos roscados (diálogo, colocación, agujero ciego)")
    def _():
        from efpd.gui.studdlg import StudDialog
        dlg = StudDialog(w, w.doc)
        dlg.kind.setCurrentIndex(dlg.kind.findData("casquillo"))
        dlg.thread.setCurrentText("M3")
        dlg.resize(780, 520)
        dlg.grab().save(os.path.join(OUT, "perno_dialogo.png"))
        dlg.offset.setValue(0.6)
        dlg.section.resize(340, 440)
        dlg.section.grab().save(os.path.join(OUT, "perno_seccion_ciego.png"))
        assert dlg.result_params()["depth_offset"] == 0.6
        w.insert_stud()  # exec aceptado automáticamente -> herramienta colocar junto al cursor
        assert cv.tool == "place" and cv.place_entity is not None and cv.place_entity.TYPE == "stud"
        assert cv._preview_prims(), "el perno no se muestra junto al cursor"
        mouse("press", 12, 12)
        mouse("release", 12, 12)
        st_e = w.doc.entities[-1]
        assert st_e.TYPE == "stud"
        w.edit_stud(st_e)
        st_e.p["depth_offset"] = 0.5
        w.changed()
        roles = {r for _e, r, _p in w.doc.geometry(w.doc.evaluator(), entities=[st_e])}
        assert "pocket_back" in roles, roles
        return "perno_dialogo.png, perno_seccion_ciego.png"

    @step("Biblioteca: rejillas de ventilador")
    def _():
        lp = w.library_panel
        lp.search.setText("60 × 60")
        app.processEvents()
        found = []
        stack = [lp.tree.topLevelItem(i) for i in range(lp.tree.topLevelItemCount())]
        while stack:
            x = stack.pop()
            if lp._cid(x):
                found.append(lp._cid(x))
            stack += [x.child(i) for i in range(x.childCount())]
        lp.search.setText("")
        assert any(f.startswith("fang_arc_60") for f in found), found[:5]
        lp.preview.set_comp(w.lib.items["fang_arc_80_77_4p3"])
        lp.preview.resize(300, 300)
        lp.preview.grab().save(os.path.join(OUT, "rejilla_ventilador.png"))
        return f"{len(found)} coincidencias; rejilla_ventilador.png"

    @step("Vista previa de escala y texto se actualiza al cambiar opciones")
    def _():
        from efpd.gui.textscale import ScaleDialog, TextDialog
        dlg = ScaleDialog(w, w.doc)
        before = len(dlg.preview.entity.geometry(w.doc, w.doc.evaluator()))
        dlg.form.widgets["radius"].setValue(31.0)                      # QDoubleSpinBox.valueChanged(float)
        assert dlg.proto.p["radius"] == 31.0, "el radio no llegó a la vista previa"
        i = dlg.form.widgets["mark_style"].findData("puntos")
        dlg.form.widgets["mark_style"].setCurrentIndex(i)               # QComboBox.currentIndexChanged(int)
        assert dlg.proto.p["mark_style"] == "puntos"
        dlg.form.widgets["ref_line"].setChecked(True)                   # QCheckBox.toggled(bool)
        assert dlg.proto.p["ref_line"] is True
        dlg.form.widgets["minor_div"].setValue(4)                       # QSpinBox.valueChanged(int)
        dlg.form.widgets["suffix"].setText("dB")                        # QLineEdit.textChanged(str)
        assert dlg.proto.p["suffix"] == "dB" and dlg.proto.p["minor_div"] == 4
        i = dlg.form.widgets["text_rot"].findData("45")
        dlg.form.widgets["text_rot"].setCurrentIndex(i)
        dlg.form.widgets["color_major"].set_value("#ff0000")
        assert dlg.proto.p["text_rot"] == "45" and dlg.proto.p["color_major"] == "#ff0000"
        after = len(dlg.preview.entity.geometry(w.doc, w.doc.evaluator()))
        assert after != before, "la geometría de la vista previa no cambió"
        dlg.preview.resize(500, 400)
        dlg.preview.grab().save(os.path.join(OUT, "escala_vista_previa_actualizada.png"))
        td = TextDialog(w, w.doc)
        td.form.widgets["size"].setValue(9.0)
        td.form.widgets["underline"].setChecked(True)
        td.text.setPlainText("CAMBIADO")
        assert td.proto.p["size"] == 9.0 and td.proto.p["underline"] and td.proto.p["text"] == "CAMBIADO"
        return f"{before} → {after} primitivas; escala_vista_previa_actualizada.png"

    @step("Varias formas seguidas con vista previa (arrastrar)")
    def _():
        snap_obj = w.doc.settings.get("snap_objects", True)
        w.doc.settings["snap_objects"] = False
        res = []
        for k, tool in enumerate(("rect", "circle", "roundrect", "ellipse", "rect", "pocket")):
            cv.set_tool(tool)
            x0, y0 = 20 + k * 25, 20
            mouse("press", x0, y0)
            for j in range(1, 6):
                mouse("move", x0 + j * 2, y0 + j * 2)
                assert cv._preview_prims(), f"sin vista previa en la forma {k + 1} ({tool})"
            n = len(w.doc.entities)
            mouse("release", x0 + 10, y0 + 10)
            assert len(w.doc.entities) == n + 1, f"la forma {k + 1} ({tool}) no se creó"
            assert cv._drag is None
            res.append(tool)
        cv.set_tool("select")
        w.doc.settings["snap_objects"] = snap_obj
        return " → ".join(res)

    @step("Iconos (hoja de muestra)")
    def _():
        from PySide6.QtGui import QPainter, QPixmap
        keys = [a.data() for a in w.actions.values() if not a.icon().isNull()]
        cols, size = 12, 48
        rows = (len(keys) + cols - 1) // cols
        sheet = QPixmap(cols * (size + 12) + 12, rows * (size + 12) + 12)
        for bg, name in ((QColor("#1f2227"), "iconos_oscuro.png"), (QColor("#f3f4f6"), "iconos_claro.png")):
            sheet.fill(bg)
            p = QPainter(sheet)
            for i, k in enumerate(keys):
                pm = w.actions[k].icon().pixmap(size, size)
                p.drawPixmap(12 + (i % cols) * (size + 12), 12 + (i // cols) * (size + 12), pm)
            p.end()
            sheet.save(os.path.join(OUT, name))
        names = [a.toolTip() for a in (w.actions["export_dxf"], w.actions["import_svg"])]
        return f"{len(keys)} iconos · {names}"

    @step("Bibliotecas: componente nuevo en biblioteca nueva y existente")
    def _():
        from efpd.gui.dialogs import ComponentEditor
        from efpd.core.library import component_from_entities
        shapes = [CircleEntity(x=10, y=10, d=6), HoleEntity(x=20, y=10)]
        comp = component_from_entities(w.doc, shapes, "Prueba A")
        dlg = ComponentEditor(w, comp, "x", library=w.lib)
        dlg.lib_combo.addItem("Biblioteca de prueba")
        dlg.lib_combo.setCurrentText("Biblioteca de prueba")
        cid_a = w._save_from_editor(dlg)
        assert cid_a and w.lib.items[cid_a]["library"] == "Biblioteca de prueba"
        dlg2 = ComponentEditor(w, dict(comp, name="Prueba B"), "x", library=w.lib)
        assert dlg2.lib_combo.findText("Biblioteca de prueba") >= 0, "la biblioteca existente no aparece"
        dlg2.lib_combo.setCurrentText("Biblioteca de prueba")
        cid_b = w._save_from_editor(dlg2)
        tree = w.lib.tree()
        n = sum(len(v) for v in tree["Biblioteca de prueba"].values())
        assert n == 2, n
        w.library_panel.refresh()
        tops = [w.library_panel.tree.topLevelItem(i).text(0) for i in range(w.library_panel.tree.topLevelItemCount())]
        assert "Biblioteca de prueba" in tops, tops
        w.lib.delete_user(cid_a)
        w.lib.delete_user(cid_b)
        w.lib.delete_library("Biblioteca de prueba")
        w.library_panel.refresh()
        return f"bibliotecas en el árbol: {tops}"

    @step("Biblioteca: miniatura al seleccionar y tooltip con imagen")
    def _():
        from PySide6.QtCore import QPoint
        from efpd.gui.comppreview import thumbnail
        lp = w.library_panel
        found = None
        it = lp.tree.topLevelItem(0)
        stack = [it]
        while stack:
            x = stack.pop()
            if lp._cid(x) == "xlr_d":
                found = x
                break
            stack += [x.child(i) for i in range(x.childCount())]
        assert found is not None
        lp.tree.setCurrentItem(found)
        app.processEvents()
        assert lp.preview.comp is not None and lp.preview.comp["id"] == "xlr_d"
        lp.preview.resize(300, 220)
        lp.preview.grab().save(os.path.join(OUT, "biblioteca_vista_previa.png"))
        c = w.lib.items["xlr_d"]
        lp.tip.show_for("xlr_d", c, "<b>XLR</b>", QPoint(200, 200))
        app.processEvents()
        assert lp.tip.isVisible()
        lp.tip.grab().save(os.path.join(OUT, "biblioteca_tooltip.png"))
        lp.tip.hide_tip()
        assert not thumbnail(c, 120, 90).isNull()
        return "biblioteca_vista_previa.png, biblioteca_tooltip.png"

    @step("Acerca de (con icono)")
    def _():
        from efpd.gui.dialogs import AboutDialog
        from efpd.gui import icons
        assert not icons.app_icon().isNull(), "no se encontró efpd/resources/icon.png"
        assert not w.windowIcon().isNull()
        d = AboutDialog(w)
        d.adjustSize()
        d.grab().save(os.path.join(OUT, "acerca_de.png"))
        return "acerca_de.png"

    @step("Vista 3D (varias orientaciones)")
    def _():
        v = View3D(w.doc)
        v.resize(1000, 700)
        for name, yaw, pitch in (("iso", -18, -58), ("frontal", 0, 0), ("trasera", 180, 45)):
            v.set_view(yaw, pitch)
            v.grab().save(os.path.join(OUT, f"vista3d_{name}.png"))
        return "vista3d_iso/frontal/trasera.png"

    @step("Exportaciones (DXF, SVG, PDF, PNG, STL, G-code, HPGL)")
    def _():
        from efpd.io import dxf_export, gcode, mesh, svg_export
        files = {}
        dxf_export.export_dxf(w.doc, os.path.join(OUT, "panel.dxf"))
        svg_export.export_svg(w.doc, os.path.join(OUT, "panel_fabricacion.svg"))
        svg_export.export_svg(w.doc, os.path.join(OUT, "panel_visual.svg"), style="visual")
        render.export_pdf(w.doc, os.path.join(OUT, "panel_realista.pdf"), "visual")
        render.export_pdf(w.doc, os.path.join(OUT, "panel_tecnico.pdf"), "fab")
        img = render.render_image(w.doc, 200, "visual")
        assert img.save(os.path.join(OUT, "panel.png"))
        mesh.export_stl(w.doc, os.path.join(OUT, "panel.stl"))
        gcode.export_gcode(w.doc, os.path.join(OUT, "panel.nc"), gcode.GcodeSettings())
        gcode.export_hpgl(w.doc, os.path.join(OUT, "panel.plt"))
        for fn in ("panel.dxf", "panel_fabricacion.svg", "panel_visual.svg", "panel_realista.pdf", "panel_tecnico.pdf",
                   "panel.png", "panel.stl", "panel.nc", "panel.plt"):
            sz = os.path.getsize(os.path.join(OUT, fn))
            assert sz > 200, (fn, sz)
            files[fn] = sz
        return ", ".join(f"{k} {v // 1024} KB" for k, v in files.items())

    @step("Importar DXF y SVG exportados")
    def _():
        a = dxf_import.import_dxf(os.path.join(OUT, "panel.dxf"))
        b = svg_import.import_svg(os.path.join(OUT, "panel_fabricacion.svg"))
        return f"DXF {len(a.p['paths'])} trazos · SVG {len(b.p['paths'])} trazos"

    @step("Guardar y abrir proyecto .efpd")
    def _():
        p = os.path.join(OUT, "fuente_laboratorio.efpd")
        w.path = p
        assert w.file_save()
        n = len(w.doc.entities)
        assert w.load_path(p)
        assert len(w.doc.entities) == n
        project.autosave(w.doc, p)
        project.clear_autosave()
        return p

    @step("Diálogos (G-code, componente, preferencias, barras, matriz, PNG)")
    def _():
        from efpd.gui.dialogs import (ArrayDialog, ComponentEditor, GcodeDialog, ImageExportDialog,
                                      PreferencesDialog, ToolbarConfigDialog)
        from efpd.gui.main_window import TOOLBARS
        g = GcodeDialog(w, w.gsettings, 2.0)
        assert g.settings().tool_d > 0
        ce = ComponentEditor(w, w.lib.get("xlr_d"))
        c, errs = ce.result_comp()
        assert not errs, errs
        ce.preview.resize(300, 240)
        ce.preview.grab().save(os.path.join(OUT, "editor_componente.png"))
        PreferencesDialog(w, w.doc, w.prefs).prefs()
        ToolbarConfigDialog(w, TOOLBARS, w.actions, w._toolbar_config()).result()
        ArrayDialog(w).values()
        ImageExportDialog(w)
        cid = w.lib.save_user(dict(c, name="Prueba usuario"))
        w.library_panel.refresh()
        assert w.lib.delete_user(cid)
        return "OK"

    @step("Paneles: capas, variables, historial")
    def _():
        w.layers_panel.refresh()
        w.layers_panel._add()
        w.vars_panel._add()
        w.history_panel.refresh()
        n = len(w.history.undo_stack)
        w.history_goto(max(0, n - 2))
        w.history_goto(n)
        return f"{n} pasos en historial"

    @step("Rendimiento de dibujo del lienzo")
    def _():
        t0 = time.time()
        for _ in range(10):
            cv.invalidate()
            cv.repaint()
        dt = (time.time() - t0) / 10
        return f"{dt * 1000:.0f} ms por fotograma"

    @step("Idiomas: inglés, alemán, francés y uno nuevo desde fichero")
    def _():
        from efpd import i18n
        from efpd.gui.app import switch_language
        win = w
        titles = {}
        for code in ("en", "de", "fr"):
            win = switch_language(win, code)
            app.processEvents()
            titles[code] = win.menuBar().actions()[0].text()
            win.grab().save(os.path.join(OUT, f"ventana_{code}.png"))
            assert len(win.doc.entities) == len(w.doc.entities), "se perdió el documento al cambiar de idioma"
        assert titles["en"] == "&File" and titles["de"] == "&Datei" and titles["fr"] == "&Fichier", titles
        p = os.path.join(OUT, "idioma_plantilla.json")
        n = i18n.make_template(p)
        import json
        d = json.load(open(p, encoding="utf-8"))
        d["code"], d["language"] = "it", "Italiano"
        d["strings"]["&Archivo"] = "&File (IT)"
        json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        assert i18n.install_file(p) == "it"
        win = switch_language(win, "it")
        assert win.menuBar().actions()[0].text() == "&File (IT)"
        win = switch_language(win, "es")
        st["w"] = win
        return f"{titles} · plantilla con {n} textos · idioma 'it' instalado"

    @step("Desplegables: la opción resaltada es visible (tema oscuro y claro)")
    def _():
        from PySide6.QtWidgets import QComboBox
        out = []
        for theme in ("oscuro", "claro"):
            if w.prefs["theme"] != theme:
                w.toggle_theme()
            app.processEvents()
            co = QComboBox(w)
            co.addItems(["M2", "M2.5", "M3", "M4", "M5", "M6"])
            co.setCurrentIndex(1)
            co.resize(200, 28)
            co.show()
            co.showPopup()
            app.processEvents()
            view = co.view()
            view.setCurrentIndex(view.model().index(1, 0))
            app.processEvents()
            img = view.grab().toImage()
            rect = view.visualRect(view.model().index(1, 0))
            px = img.pixelColor(rect.center().x(), rect.center().y())
            acc = QColor(w.colors["accent"])
            diff = abs(px.red() - acc.red()) + abs(px.green() - acc.green()) + abs(px.blue() - acc.blue())
            view.grab().save(os.path.join(OUT, f"desplegable_{theme}.png"))
            co.hidePopup()
            co.deleteLater()
            assert diff < 60, f"tema {theme}: la opción resaltada no usa el color de acento ({px.name()} vs {acc.name()})"
            out.append(f"{theme} {px.name()}")
        if w.prefs["theme"] != "oscuro":
            w.toggle_theme()
        return " · ".join(out) + " · desplegable_oscuro.png, desplegable_claro.png"

    @step("Verificación: interferencias de textos, escalas y rótulos")
    def _():
        from efpd.core.checks import check as _check
        from efpd.core.document import Document as _Doc
        from efpd.core.entities import HoleEntity as _Hole, TextEntity as _Text
        from efpd.core.scale import ScaleEntity as _Scale
        d = _Doc()
        d.add(_Hole(x=30, y=30))
        d.add(_Scale(x=30, y=30, radius=2))
        d.add(_Text(x=30, y=30.5, text="VOL", size=4))
        d.add(_Text(x=90, y=40, text="AAA", size=4))
        d.add(_Text(x=91, y=40, text="BBB", size=4))
        d.add(_Text(x=1, y=60, text="BORDE", size=4))
        iss = _check(d)
        msgs = [i.message for i in iss]
        assert any("VOL" in m for m in msgs), msgs
        assert any("AAA" in m and "BBB" in m for m in msgs), msgs
        assert any("BORDE" in m for m in msgs), msgs
        assert any("Escala" in m or "Scale" in m for m in msgs), msgs
        w.checks_panel.show_issues(iss)
        app.processEvents()
        w.run_checks()
        return f"{len(iss)} resultados: " + "; ".join(msgs[:4])

    @step("PNG con cotas de usuario y cotas automáticas")
    def _():
        from efpd.core.document import Document as _Doc
        from efpd.core.entities import DimensionEntity as _Dim, HoleEntity as _Hole, RectEntity as _Rect
        from efpd.gui import render as _render
        from efpd.gui.dialogs import ImageExportDialog as _IED
        d = _Doc()
        h = d.add(_Hole(x=30, y=30))
        d.add(_Rect(x=90, y=40, w=30, h=15))
        d.add(_Dim(a={"xy": [10, 60]}, b={"xy": [70, 60]}, orient="h", offset=5))
        dim_col = QColor([L.color for L in d.layers if L.process == "dim"][0])
        pos_col = QColor(_render.AUTOPOS_COLOR)

        def count(img, col):
            n = 0
            for y in range(0, img.height(), 2):
                for x in range(0, img.width(), 2):
                    c = img.pixelColor(x, y)
                    if abs(c.red() - col.red()) + abs(c.green() - col.green()) + abs(c.blue() - col.blue()) < 90:
                        n += 1
            return n
        res = {}
        for name, kw in (("nada", dict(show_dims=False)),
                         ("usuario", dict(show_dims=True)),
                         ("auto", dict(show_dims=False, auto_dims="all", selected={h.id})),
                         ("ambas", dict(show_dims=True, auto_dims="size_all", selected={h.id}))):
            img = _render.render_image(d, 150, "visual", **kw)
            img.save(os.path.join(OUT, f"png_cotas_{name}.png"))
            res[name] = (count(img, dim_col), count(img, pos_col))
        assert res["usuario"][0] > res["nada"][0] + 20, f"las cotas de usuario no se dibujan en el PNG: {res}"
        assert res["auto"][0] > res["nada"][0] + 20, f"las cotas automáticas (tamaños) no se dibujan: {res}"
        assert res["auto"][1] > res["nada"][1] + 20, f"las cotas automáticas (posición) no se dibujan: {res}"
        assert res["ambas"][0] > res["usuario"][0], f"no se suman cotas de usuario y automáticas: {res}"
        dlg = _IED(w, user_dims=True, auto_mode="size_all", has_selection=False)
        assert dlg.auto.currentData() == "size_all" and dlg.dims.isChecked()
        dlg.grab().save(os.path.join(OUT, "png_dialogo_cotas.png"))
        dlg.deleteLater()
        return f"píxeles de cota {res} · png_cotas_*.png, png_dialogo_cotas.png"

    @step("Ejemplos: abrir, seleccionar y arrastrar cada componente")
    def _():
        from efpd.core.checks import check as _check
        folder = os.path.join(ROOT, "ejemplos")
        out = []
        for name in ("fuente_laboratorio.efpd", "eurorack_vco_12hp.efpd", "rack_2u_amplificador_trasero.efpd",
                     "fuente_laboratorio.efpd"):  # se repite para comprobar que no quedan datos del anterior
            assert w.load_path(os.path.join(folder, name), as_path=""), name
            app.processEvents()
            cv.set_tool("select")
            ev = w.doc.evaluator()
            assert not any(e.locked for e in w.doc.entities), f"{name}: hay elementos bloqueados"
            assert not any(L.locked for L in w.doc.layers), f"{name}: hay capas bloqueadas"
            # lo que se dibuja corresponde al documento abierto
            ids_drawn = {i for i, _r, _p in cv.items()}
            assert ids_drawn <= {e.id for e in w.doc.entities}, f"{name}: el lienzo muestra otro documento"
            moved = 0
            for e in [x for x in w.doc.entities if x.TYPE == "component"]:
                ev = w.doc.evaluator()
                cut = next((pr for _e, r, pr in w.doc.geometry(ev, entities=[e]) if r == "cut"), None)
                if cut is None:
                    continue
                if cut["t"] == "circle":
                    px, py = cut["c"]
                else:   # sobre el contorno del hueco (el centro de una ranura curva puede estar vacío)
                    px, py = cut["pts"][0]
                x0, y0 = e.v(ev, "x"), e.v(ev, "y")
                cv.set_selection([])
                drag(px, py, px + 5.0, py)
                assert cv.selected == {e.id}, f"{name}: al hacer clic en «{e.display_name()}» se seleccionó " \
                    f"{[w.doc.get(i).display_name() for i in cv.selected]}"
                x1 = w.doc.get(e.id).v(w.doc.evaluator(), "x")
                assert abs(x1 - x0 - 5.0) < 2.6, f"{name}: «{e.display_name()}» no se movió ({x0} → {x1})"
                w.undo()
                assert abs(w.doc.get(e.id).v(w.doc.evaluator(), "x") - x0) < 1e-6
                moved += 1
            errs = [i.message for i in _check(w.doc) if i.level in ("error", "aviso")]
            assert not errs, f"{name}: la verificación encuentra problemas: {errs}"
            cv.grab().save(os.path.join(OUT, "ejemplo_" + name.replace(".efpd", ".png")))
            out.append(f"{name.split('.')[0]}: {moved} componentes movidos")
        return " · ".join(out[:3])

    @step("Sin errores de dibujado durante toda la prueba")
    def _():
        from efpd.gui import safepaint
        if safepaint.ERRORS:
            raise AssertionError("\n\n".join(f"[{wd}]\n{t}" for wd, t in safepaint.ERRORS[:5]))
        return "0 errores"

    w = st["w"]
    w.history.mark_clean()
    w.close()


if __name__ == "__main__":
    sys.exit(main())
