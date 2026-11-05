"""Ventana principal: acciones, menús, barras, paneles y orquestación."""
from __future__ import annotations

import base64
import json
import os
import traceback

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QImage, QKeySequence
from PySide6.QtWidgets import (QApplication, QDockWidget, QDoubleSpinBox, QFileDialog, QInputDialog, QLabel,
                               QMainWindow, QMenu, QMessageBox, QSizePolicy, QToolBar)

from .. import APP_NAME, i18n
from ..core import layout
from ..core.checks import check, measure_between
from ..core.document import Document, apply_preset
from ..core.entities import ComponentEntity, ImageEntity, TextEntity, entity_from_dict
from ..core.history import History
from ..core.library import BUILTIN_LIBRARY, Library, comp_name, component_from_entities
from ..i18n import N_, tr
from ..io import dxf_export, dxf_import, gcode, mesh, project, svg_export, svg_import
from . import icons, render
from .canvas import Canvas
from .dialogs import (AboutDialog, ArrayDialog, ComponentEditor, GcodeDialog, ImageExportDialog, PreferencesDialog,
                      ToolbarConfigDialog)
from .docks import ChecksPanel, HistoryPanel, LayersPanel, LibraryPanel, VariablesPanel
from .properties import PropertiesPanel
from .theme import apply_theme
from .view3d import View3DDialog

# Barras configurables (los nombres son claves internas; se muestran traducidos)
TOOLBARS = {
    N_("Archivo"): ["new", "open", "save", "|", "undo", "redo"],
    N_("Importar / Exportar"): ["import_dxf", "import_svg", "import_image", "|", "export_dxf", "export_svg",
                                "export_pdf", "export_png", "export_stl", "export_gcode", "export_hpgl"],
    N_("Dibujo"): ["tool_select", "tool_pan", "|", "tool_rect", "tool_roundrect", "tool_circle", "tool_ellipse",
                   "tool_polygon", "tool_polyline", "|", "tool_slot", "tool_oval", "tool_hole", "tool_hole_csk",
                   "tool_hole_thread", "tool_dhole", "tool_pocket", "|", "tool_text", "insert_scale", "insert_stud", "import_image", "|",
                   "tool_dimension", "tool_measure"],
    N_("Organizar"): ["align_left", "align_hcenter", "align_right", "align_top", "align_vcenter", "align_bottom", "|",
                      "dist_h", "dist_v", "dist_panel", "array", "mirror", "rotate90", "|", "duplicate", "delete"],
    N_("Vista"): ["zoom_fit", "view3d", "check", "autodim"],
}

TOOLS = [("select", N_("Seleccionar"), "V"), ("pan", N_("Desplazar vista"), "H"), ("rect", N_("Rectángulo"), "R"),
         ("roundrect", N_("Rectángulo redondeado"), "Shift+R"), ("circle", N_("Círculo"), "C"),
         ("ellipse", N_("Elipse"), "E"), ("polygon", N_("Polígono regular"), "G"),
         ("polyline", N_("Polígono libre"), "P"), ("slot", N_("Ranura rectangular"), "S"),
         ("oval", N_("Ranura ovalada"), "O"), ("hole", N_("Agujero de montaje"), "M"),
         ("hole_csk", N_("Agujero avellanado"), "Shift+M"), ("hole_thread", N_("Agujero roscado"), "Ctrl+Shift+M"),
         ("dhole", N_("Agujero en D"), "Shift+D"), ("pocket", N_("Fresado / rebaje"), "F"), ("text", N_("Texto"), "T"),
         ("dimension", N_("Cota"), "D"), ("measure", N_("Medir"), "Shift+Q")]

AUTO_DIM_MODES = [("size_all", N_("Tamaño de todos · posición de la selección")),
                  ("all", N_("Tamaño y posición de todos")),
                  ("selection", N_("Sólo de la selección")),
                  ("off", N_("Sin cotas automáticas"))]


class MainWindow(QMainWindow):
    def __init__(self, carry: dict | None = None):
        super().__init__()
        self.settings = QSettings("EFPD", "ElectronicFrontPanelDesigner")
        self.prefs = {"theme": self.settings.value("theme", "oscuro"),
                      "autosave_min": int(self.settings.value("autosave_min", 2)),
                      "undo_limit": int(self.settings.value("undo_limit", 0)),
                      "icon_size": int(self.settings.value("icon_size", 32))}
        self.colors = apply_theme(QApplication.instance(), self.prefs["theme"])
        self.setWindowIcon(icons.app_icon())
        self.lib = Library()
        self._switching = False
        if carry:
            self.doc, self.history, self.path = carry["doc"], carry["history"], carry["path"]
            self.active_layer, self.clipboard = carry["active_layer"], carry["clipboard"]
        else:
            self.doc = Document()
            self.history = History(self.doc, self.prefs["undo_limit"])
            self.path = ""
            self.active_layer = "cut"
            self.clipboard = []
        self._autosaved_at = -1
        try:
            self.gsettings = gcode.GcodeSettings.from_dict(json.loads(self.settings.value("gcode", "{}") or "{}"))
        except (ValueError, TypeError):
            self.gsettings = gcode.GcodeSettings()

        self.canvas = Canvas(self)
        self.canvas.auto_dims = self.settings.value("auto_dims", "size_all")
        self.setCentralWidget(self.canvas)
        self._build_docks()
        self._build_actions()
        self._build_menus()
        self._build_status()
        self._build_toolbars()
        self.canvas.selectionChanged.connect(self._on_selection)
        self.canvas.cursorMoved.connect(lambda x, y: self.pos_label.setText(f"X {x:9.3f}   Y {y:9.3f} mm"))
        self.canvas.message.connect(self.status)
        self.canvas.zoomChanged.connect(lambda s: self.zoom_label.setText(f"{s / 3.78 * 100:.0f} %"))
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self._autosave)
        self._restart_autosave()
        self.resize(1500, 900)
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        st = self.settings.value("state")
        if st is not None:
            self.restoreState(st)
        self.full_refresh()
        self.canvas.set_tool("select")

    def carry_state(self) -> dict:
        return {"doc": self.doc, "history": self.history, "path": self.path, "active_layer": self.active_layer,
                "clipboard": self.clipboard}

    # ================================================================ construcción
    def _dock(self, title, widget, area, name):
        d = QDockWidget(title, self)
        d.setObjectName(name)
        d.setWidget(widget)
        d.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                      | QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self.addDockWidget(area, d)
        return d

    def _build_docks(self):
        R, L = Qt.DockWidgetArea.RightDockWidgetArea, Qt.DockWidgetArea.LeftDockWidgetArea
        self.library_panel = LibraryPanel(self)
        self.props = PropertiesPanel(self)
        self.layers_panel = LayersPanel(self)
        self.vars_panel = VariablesPanel(self)
        self.history_panel = HistoryPanel(self)
        self.checks_panel = ChecksPanel(self)
        self.d_lib = self._dock(tr("Biblioteca de componentes"), self.library_panel, L, "dock_lib")
        self.d_props = self._dock(tr("Propiedades"), self.props, R, "dock_props")
        self.d_layers = self._dock(tr("Capas"), self.layers_panel, R, "dock_layers")
        self.d_vars = self._dock(tr("Variables"), self.vars_panel, R, "dock_vars")
        self.d_hist = self._dock(tr("Historial"), self.history_panel, L, "dock_hist")
        self.d_checks = self._dock(tr("Verificación"), self.checks_panel, L, "dock_checks")
        self.tabifyDockWidget(self.d_layers, self.d_vars)
        self.tabifyDockWidget(self.d_hist, self.d_checks)
        self.d_layers.raise_()
        self.d_hist.raise_()

    def _act(self, key, text, slot=None, shortcut=None, icon_key=None, checkable=False, tip=None):
        a = QAction(text, self)
        if icon_key:
            a.setIcon(icons.icon(icon_key, self.colors["text"]))
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if slot:
            a.triggered.connect(slot)
        a.setCheckable(checkable)
        sc = QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText) if shortcut else ""
        a.setToolTip((tip or text.replace("&", "")) + (f"  ({sc})" if sc else ""))
        a.setData(key)
        self.actions[key] = a
        return a

    def _build_actions(self):
        self.actions = {}
        A = self._act
        SK = QKeySequence.StandardKey
        A("new", tr("&Nuevo"), self.file_new, SK.New, "new")
        A("open", tr("&Abrir…"), self.file_open, SK.Open, "open")
        A("save", tr("&Guardar"), self.file_save, SK.Save, "save")
        A("save_as", tr("Guardar &como…"), self.file_save_as, SK.SaveAs)
        A("import_dxf", tr("Importar DXF…"), lambda: self.import_vector("dxf"), None, "imp_DXF")
        A("import_svg", tr("Importar SVG…"), lambda: self.import_vector("svg"), None, "imp_SVG")
        A("import_image", tr("Importar imagen / logotipo…"), self.import_image, None, "imp_IMG")
        A("export_dxf", tr("Exportar DXF (fabricación)…"), self.export_dxf, "Ctrl+Shift+E", "exp_DXF")
        A("export_svg", tr("Exportar SVG (fabricación)…"), lambda: self.export_svg("fabricacion"), None, "exp_SVG")
        A("export_svg_vis", tr("Exportar SVG (aspecto realista)…"), lambda: self.export_svg("visual"), None, "exp_SVG")
        A("export_pdf", tr("Exportar PDF vectorial (realista)…"), lambda: self.export_pdf("visual"), None, "exp_PDF")
        A("export_pdf_fab", tr("Exportar PDF vectorial (plano técnico 1:1)…"), lambda: self.export_pdf("fab"), None,
          "exp_PDF")
        A("export_png", tr("Exportar PNG…"), self.export_png, None, "exp_PNG")
        A("export_stl", tr("Exportar STL (impresión 3D)…"), self.export_stl, None, "exp_STL")
        A("export_gcode", tr("Exportar G-code CNC…"), self.export_gcode, None, "exp_NC")
        A("export_hpgl", tr("Exportar HPGL (plotter / grabadora)…"), self.export_hpgl, None, "exp_PLT")
        A("quit", tr("&Salir"), self.close, SK.Quit)
        A("undo", tr("&Deshacer"), self.undo, SK.Undo, "undo")
        A("redo", tr("&Rehacer"), self.redo, SK.Redo, "redo")
        A("cut", tr("Cor&tar"), self.cut, SK.Cut)
        A("copy", tr("&Copiar"), self.copy, SK.Copy)
        A("paste", tr("&Pegar"), self.paste, SK.Paste)
        A("duplicate", tr("Duplicar"), self.duplicate, "Ctrl+D", "duplicate")
        A("delete", tr("Eliminar"), self.delete_selected, None, "delete")
        A("select_all", tr("Seleccionar todo"), lambda: self.canvas.set_selection([e.id for e in self.doc.entities]),
          SK.SelectAll)
        A("rotate90", tr("Girar 90°"), lambda: self.rotate_selected(90), "Ctrl+R", "rotate")
        A("mirror", tr("Simetría horizontal (eje del panel)"), self.mirror_selected, None, "mirror")
        A("array", tr("Matriz de copias…"), self.array_selected, None, "array")
        A("lock", tr("Bloquear / desbloquear"), self.toggle_lock, "Ctrl+L")
        names = {"left": tr("Alinear a la izquierda"), "hcenter": tr("Centrar horizontalmente"),
                 "right": tr("Alinear a la derecha"), "top": tr("Alinear arriba"),
                 "vcenter": tr("Centrar verticalmente"), "bottom": tr("Alinear abajo")}
        for k, label in names.items():
            A(f"align_{k}", label, lambda _c=False, m=k: self.run_layout(f"align_{m}"), None, f"align_{k}")
        A("dist_h", tr("Distribuir horizontalmente"), lambda: self.run_layout("dist_h"), None, "dist_h")
        A("dist_v", tr("Distribuir verticalmente"), lambda: self.run_layout("dist_v"), None, "dist_v")
        A("dist_panel", tr("Distribución automática en el panel (vinculada)"), lambda: self.run_layout("dist_panel"),
          None, "dist_panel")
        A("zoom_in", tr("Acercar"), lambda: self.canvas.zoom(1.25), SK.ZoomIn)
        A("zoom_out", tr("Alejar"), lambda: self.canvas.zoom(0.8), SK.ZoomOut)
        A("zoom_fit", tr("Ajustar a la ventana"), self.canvas.fit_view, "Ctrl+0", "zoom_fit")
        A("view3d", tr("Vista previa 3D…"), self.show_3d, "F3", "view3d")
        A("check", tr("Verificar interferencias"), self.run_checks, "F7", "check")
        A("autodim", tr("Crear cotas vinculadas (acotación automática)"), self.auto_dimension, None, "autodim")
        A("panel_dims", tr("Acotar tamaño del panel"), self.panel_dimensions)
        A("measure_sel", tr("Medir entre selección"), self.measure_selection)
        A("prefs", tr("Preferencias…"), self.preferences, "Ctrl+,", "settings")
        A("toolbars", tr("Configurar barras de herramientas…"), self.configure_toolbars)
        A("theme", tr("Alternar tema claro / oscuro"), self.toggle_theme, "Ctrl+Shift+T")
        A("new_comp", tr("Nuevo componente…"), lambda: self.edit_component(None), None, "component")
        A("insert_stud", tr("Perno / casquillo roscado…"), self.insert_stud, "Shift+B", "stud",
          tip=tr("Perno o casquillo roscado a presión (delante o en el reverso del panel)"))
        A("insert_scale", tr("Generador de escalas…"), self.insert_scale, "Shift+E", "scale",
          tip=tr("Escala para potenciómetro rotatorio o deslizante (si hay un potenciómetro seleccionado se "
                 "centra en él)"))
        A("comp_from_sel", tr("Crear componente desde selección…"), self.component_from_selection)
        A("new_lib", tr("Nueva biblioteca…"), self.new_library, None, "library")
        A("import_lib", tr("Importar biblioteca…"), self.import_library)
        A("lang_template", tr("Generar plantilla de idioma…"), self.make_language_template)
        A("lang_install", tr("Instalar idioma desde fichero…"), self.install_language)
        A("help_keys", tr("Atajos y uso"), self.help_keys, "F1")
        A("about", tr("Acerca de…"), self.about)
        A("show_ref", tr("Mostrar referencias de componentes"), None, None, None, True)
        A("show_fp", tr("Mostrar cuerpos traseros"), None, None, None, True)
        A("show_dims", tr("Mostrar cotas"), None, "Ctrl+Shift+D", "show_dims", True)
        A("snap_grid", tr("Ajustar a rejilla"), None, "F9", "snap_grid", True)
        A("snap_obj", tr("Ajustar a objetos"), None, "F10", "snap_obj", True)
        self.actions["show_ref"].setChecked(True)
        self.actions["show_dims"].setChecked(bool(self.settings.value("show_dims", True, type=bool)))
        self.canvas.show_dims = self.actions["show_dims"].isChecked()
        self.actions["show_ref"].toggled.connect(lambda v: self._canvas_flag("show_ref", v))
        self.actions["show_fp"].toggled.connect(lambda v: self._canvas_flag("show_footprint", v))
        self.actions["show_dims"].toggled.connect(self._toggle_dims)
        self.actions["snap_grid"].toggled.connect(lambda v: self.doc.settings.__setitem__("snap_grid", v))
        self.actions["snap_obj"].toggled.connect(lambda v: self.doc.settings.__setitem__("snap_objects", v))
        self.tool_group = QActionGroup(self)
        self.tool_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        for key, label, sc in TOOLS:
            a = A(f"tool_{key}", tr(label), lambda _c=False, t=key: self.canvas.set_tool(t), sc, key, True)
            self.tool_group.addAction(a)
        self.actions["tool_select"].setChecked(True)
        self.dim_group = QActionGroup(self)
        for key, label in AUTO_DIM_MODES:
            a = QAction(tr(label), self)
            a.setCheckable(True)
            a.setData(key)
            a.setChecked(self.canvas.auto_dims == key)
            a.triggered.connect(lambda _c=False, k=key: self._set_auto_dims(k))
            self.dim_group.addAction(a)

    def _canvas_flag(self, attr, v):
        setattr(self.canvas, attr, v)
        self.canvas._dim_cache = (-1, [])
        self.canvas.update()

    def _toggle_dims(self, v):
        self.settings.setValue("show_dims", v)
        self._canvas_flag("show_dims", v)

    def _set_auto_dims(self, mode):
        self.canvas.auto_dims = mode
        self.settings.setValue("auto_dims", mode)
        if mode != "off" and not self.actions["show_dims"].isChecked():
            self.actions["show_dims"].setChecked(True)
        self.canvas.update()

    def _build_menus(self):
        mb = self.menuBar()
        a = self.actions

        def fill(menu, keys):
            for k in keys:
                if k is None:
                    menu.addSeparator()
                else:
                    menu.addAction(a[k])
        m = mb.addMenu(tr("&Archivo"))
        fill(m, ["new", "open"])
        self.recent_menu = m.addMenu(tr("Recientes"))
        self._fill_recent()
        m.addSeparator()
        fill(m, ["save", "save_as", None])
        mi = m.addMenu(tr("Importar"))
        fill(mi, ["import_dxf", "import_svg", "import_image"])
        me = m.addMenu(tr("Exportar"))
        fill(me, ["export_dxf", "export_svg", "export_svg_vis", "export_pdf", "export_pdf_fab", "export_png",
                  "export_stl", "export_gcode", "export_hpgl"])
        m.addSeparator()
        m.addAction(a["quit"])
        m = mb.addMenu(tr("&Editar"))
        fill(m, ["undo", "redo", None, "cut", "copy", "paste", "duplicate", "delete", None, "select_all", "lock",
                 None, "prefs"])
        m = mb.addMenu(tr("&Ver"))
        fill(m, ["zoom_in", "zoom_out", "zoom_fit", None, "view3d", None, "show_dims"])
        md = m.addMenu(tr("Cotas automáticas"))
        for act in self.dim_group.actions():
            md.addAction(act)
        fill(m, ["show_ref", "show_fp", None, "snap_grid", "snap_obj", None, "theme", "toolbars"])
        self.panels_menu = m.addMenu(tr("Paneles"))
        self.lang_menu = m.addMenu(icons.icon("language"), tr("Idioma / Language"))
        self._fill_languages()
        m = mb.addMenu(tr("&Dibujo"))
        for key, _l, _s in TOOLS:
            m.addAction(a[f"tool_{key}"])
            if key == "text":
                m.addAction(a["insert_scale"])
            if key == "dhole":
                m.addAction(a["insert_stud"])
            if key in ("pan", "polyline", "pocket", "text"):
                m.addSeparator()
        m = mb.addMenu(tr("&Organizar"))
        fill(m, ["align_left", "align_hcenter", "align_right", "align_top", "align_vcenter", "align_bottom", None,
                 "dist_h", "dist_v", "dist_panel", None, "array", "mirror", "rotate90"])
        m = mb.addMenu(tr("&Componentes"))
        fill(m, ["new_comp", "comp_from_sel", None, "new_lib", "import_lib"])
        m = mb.addMenu(tr("&Herramientas"))
        fill(m, ["check", "measure_sel", None, "autodim", "panel_dims", None, "tool_measure"])
        m = mb.addMenu(tr("A&yuda"))
        fill(m, ["help_keys", "about"])
        for d in (self.d_lib, self.d_props, self.d_layers, self.d_vars, self.d_hist, self.d_checks):
            self.panels_menu.addAction(d.toggleViewAction())

    def _fill_languages(self):
        self.lang_menu.clear()
        grp = QActionGroup(self.lang_menu)
        cur = i18n.current()
        for code, info in sorted(i18n.available().items(), key=lambda kv: (kv[0] != "es", kv[1]["language"])):
            act = QAction(f"{info['language']}  ({code})", self.lang_menu)
            act.setCheckable(True)
            act.setChecked(code == cur)
            act.triggered.connect(lambda _c=False, c=code: self.set_language(c))
            grp.addAction(act)
            self.lang_menu.addAction(act)
        self.lang_menu.addSeparator()
        self.lang_menu.addAction(self.actions["lang_template"])
        self.lang_menu.addAction(self.actions["lang_install"])

    def _toolbar_config(self):
        try:
            cur = json.loads(self.settings.value("toolbars", "") or "{}")
        except ValueError:
            cur = {}
        return {name: cur.get(name, [k for k in keys if k != "|"]) for name, keys in TOOLBARS.items()}

    def _build_toolbars(self):
        for tb in getattr(self, "toolbars", {}).values():
            self.removeToolBar(tb)
            tb.deleteLater()
        self.toolbars = {}
        size = QSize(self.prefs["icon_size"], self.prefs["icon_size"])
        cfg = self._toolbar_config()
        for name, keys in TOOLBARS.items():
            tb = QToolBar(tr(name), self)
            tb.setObjectName(f"tb_{name}")
            tb.setMovable(True)
            tb.setIconSize(size)
            vis = cfg.get(name, keys)
            last_sep = True
            for k in keys:
                if k == "|":
                    if not last_sep:
                        tb.addSeparator()
                        last_sep = True
                    continue
                if k in vis and k in self.actions:
                    tb.addAction(self.actions[k])
                    last_sep = False
            area = Qt.ToolBarArea.LeftToolBarArea if name == "Dibujo" else Qt.ToolBarArea.TopToolBarArea
            self.addToolBar(area, tb)
            self.toolbars[name] = tb
        # Barra de rejilla y ajuste (fija, arriba)
        tb = QToolBar(tr("Rejilla y ajuste"), self)
        tb.setObjectName("tb_grid")
        tb.setIconSize(size)
        tb.addAction(self.actions["snap_grid"])
        tb.addAction(self.actions["snap_obj"])
        lab = QLabel("  " + tr("Rejilla") + " ")
        tb.addWidget(lab)
        self.grid_spin = QDoubleSpinBox()
        self.grid_spin.setRange(0.01, 100)
        self.grid_spin.setDecimals(2)
        self.grid_spin.setSingleStep(0.5)
        self.grid_spin.setSuffix(" mm")
        self.grid_spin.setToolTip(tr("Paso de rejilla"))
        self.grid_spin.setMinimumWidth(95)
        self.grid_spin.setValue(float(self.doc.settings.get("grid", 2.5)))
        self.grid_spin.valueChanged.connect(self._grid_changed)
        tb.addWidget(self.grid_spin)
        tb.addSeparator()
        tb.addAction(self.actions["show_dims"])
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.toolbars["_grid"] = tb

    def _build_status(self):
        sb = self.statusBar()
        self.msg_label = QLabel()
        self.msg_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sb.addWidget(self.msg_label, 1)
        self.pos_label = QLabel("X 0.000  Y 0.000 mm")
        self.pos_label.setMinimumWidth(220)
        sb.addPermanentWidget(self.pos_label)
        self.zoom_label = QLabel("100 %")
        sb.addPermanentWidget(self.zoom_label)

    def _grid_changed(self, v):
        if abs(float(self.doc.settings.get("grid", 2.5)) - v) > 1e-9:
            self.doc.settings["grid"] = v
            self.canvas.update()

    # ================================================================ estado
    def status(self, msg):
        self.msg_label.setText(msg)

    def checkpoint(self, label):
        self.history.checkpoint(label)

    def changed(self, refresh_props=False):
        self.doc.touch()
        self.canvas.invalidate()
        self.history_panel.refresh()
        self.vars_panel.refresh()
        self._update_title()
        if refresh_props:
            self.props.refresh()
        self.actions["undo"].setEnabled(self.history.can_undo())
        self.actions["redo"].setEnabled(self.history.can_redo())

    def full_refresh(self):
        self.canvas.selected = {i for i in self.canvas.selected if self.doc.get(i)}
        if self.doc.layer(self.active_layer) is None:
            self.active_layer = self.doc.layers[0].id
        self.layers_panel.refresh()
        self.library_panel.refresh()
        self.actions["snap_grid"].setChecked(bool(self.doc.settings.get("snap_grid", True)))
        self.actions["snap_obj"].setChecked(bool(self.doc.settings.get("snap_objects", True)))
        self.grid_spin.blockSignals(True)
        self.grid_spin.setValue(float(self.doc.settings.get("grid", 2.5)))
        self.grid_spin.blockSignals(False)
        self.changed(refresh_props=True)

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else tr("sin guardar")
        dirty = " *" if self.history.is_dirty() else ""
        self.setWindowTitle(f"{self.doc.meta.get('title', '')} — {name}{dirty} — {APP_NAME}")

    def _on_selection(self):
        self.props.refresh()
        n = len(self.canvas.selected)
        if n:
            self.status(tr("{n} entidad(es) seleccionada(s)").format(n=n))

    def on_tool_changed(self, tool):
        if not hasattr(self, "tool_group"):
            return
        a = self.actions.get(f"tool_{tool}")
        if a is not None:
            a.setChecked(True)
        else:
            cur = self.tool_group.checkedAction()
            if cur is not None:
                cur.setChecked(False)

    def selection(self):
        return [e for e in (self.doc.get(i) for i in self.canvas.selected) if e is not None]

    def _ask(self, title, text, buttons=None, default=None):
        mb = QMessageBox(QMessageBox.Icon.Question, title, text, parent=self)
        btns = buttons or [("yes", tr("Sí"), QMessageBox.ButtonRole.YesRole),
                           ("no", tr("No"), QMessageBox.ButtonRole.NoRole)]
        made = {}
        for key, label, role in btns:
            made[mb.addButton(label, role)] = key
        if default:
            for b, k in made.items():
                if k == default:
                    mb.setDefaultButton(b)
        mb.exec()
        return made.get(mb.clickedButton(), "cancel")

    # ================================================================ archivo
    def maybe_save(self) -> bool:
        if not self.history.is_dirty():
            return True
        r = self._ask(APP_NAME, tr("El diseño tiene cambios sin guardar. ¿Guardarlos?"),
                      [("save", tr("Guardar"), QMessageBox.ButtonRole.AcceptRole),
                       ("discard", tr("Descartar"), QMessageBox.ButtonRole.DestructiveRole),
                       ("cancel", tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)], "save")
        if r == "save":
            return self.file_save()
        return r == "discard"

    def set_document(self, doc, path=""):
        self.doc = doc
        self.history = History(doc, self.prefs["undo_limit"])
        self.path = path
        self.canvas.selected = set()
        self.canvas.flagged = set()
        self.full_refresh()
        self.canvas.fit_view()

    def file_new(self):
        if self.maybe_save():
            self.set_document(Document())

    def file_open(self, path=None):
        if not self.maybe_save():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, tr("Abrir proyecto"), self._last_dir(),
                                                  tr("Proyectos EFPD (*.efpd);;Todos (*)"))
        if path:
            self.load_path(path)

    def load_path(self, path, as_path=None):
        try:
            doc = project.load_project(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, tr("No se pudo abrir el proyecto:\n{e}").format(e=e))
            return False
        self.set_document(doc, path if as_path is None else as_path)
        if as_path is None:
            self._add_recent(path)
        self.status(tr("Abierto: {p}").format(p=path))
        return True

    def file_save(self):
        if not self.path:
            return self.file_save_as()
        try:
            project.save_project(self.doc, self.path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, tr("No se pudo guardar:\n{e}").format(e=e))
            return False
        self.history.mark_clean()
        self._update_title()
        self._add_recent(self.path)
        self.status(tr("Guardado: {p}").format(p=self.path))
        return True

    def file_save_as(self):
        name = (self.doc.meta.get("title") or "panel").replace(" ", "_") + ".efpd"
        path, _ = QFileDialog.getSaveFileName(self, tr("Guardar proyecto"), os.path.join(self._last_dir(), name),
                                              tr("Proyectos EFPD (*.efpd)"))
        if not path:
            return False
        if not path.lower().endswith(".efpd"):
            path += ".efpd"
        self.path = path
        return self.file_save()

    def _last_dir(self):
        return self.settings.value("last_dir", os.path.expanduser("~"))

    def _recent(self):
        rec = self.settings.value("recent", []) or []
        return [rec] if isinstance(rec, str) else list(rec)

    def _add_recent(self, path):
        self.settings.setValue("last_dir", os.path.dirname(path))
        rec = [p for p in self._recent() if p != path]
        rec.insert(0, path)
        self.settings.setValue("recent", rec[:10])
        self._fill_recent()

    def _fill_recent(self):
        self.recent_menu.clear()
        rec = self._recent()
        for p in rec:
            self.recent_menu.addAction(p, lambda _c=False, path=p: self.file_open(path))
        if not rec:
            self.recent_menu.addAction(tr("(vacío)")).setEnabled(False)

    def _restart_autosave(self):
        mins = int(self.prefs.get("autosave_min", 2))
        self.autosave_timer.stop()
        if mins > 0:
            self.autosave_timer.start(mins * 60 * 1000)

    def _autosave(self):
        stamp = len(self.history.undo_stack) + 100000 * len(self.history.redo_stack)
        if self.history.is_dirty() and stamp != self._autosaved_at:
            try:
                project.autosave(self.doc, self.path)
                self._autosaved_at = stamp
                self.status(tr("Autoguardado"))
            except OSError as e:
                self.status(tr("Autoguardado fallido: {e}").format(e=e))

    def save_layout(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("state", self.saveState())

    def closeEvent(self, ev):
        if self._switching:
            self.autosave_timer.stop()
            ev.accept()
            return
        if not self.maybe_save():
            ev.ignore()
            return
        self.save_layout()
        project.clear_autosave()
        ev.accept()

    # ================================================================ idioma
    def set_language(self, code):
        if code == i18n.current():
            return
        self.settings.setValue("language", code)
        from .app import switch_language
        switch_language(self, code)

    def make_language_template(self):
        path, _ = QFileDialog.getSaveFileName(self, tr("Generar plantilla de idioma"),
                                              os.path.join(self._last_dir(), "idioma_nuevo.json"), "JSON (*.json)")
        if not path:
            return
        try:
            n = i18n.make_template(path)
        except OSError as e:
            QMessageBox.critical(self, APP_NAME, str(e))
            return
        QMessageBox.information(self, tr("Plantilla de idioma"), tr(
            "Plantilla creada con {n} textos:\n{p}\n\n1. Cambie \"code\" (p. ej. \"it\") y \"language\" (p. ej. "
            "\"Italiano\").\n2. Traduzca los valores de \"strings\" (no cambie las claves ni los marcadores entre llaves).\n"
            "3. Use Ver → Idioma → Instalar idioma desde fichero.").format(n=n, p=path))

    def install_language(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Instalar idioma"), self._last_dir(), "JSON (*.json)")
        if not path:
            return
        try:
            code = i18n.install_file(path)
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, APP_NAME, tr("No se pudo instalar el idioma:\n{e}").format(e=e))
            return
        self._fill_languages()
        if self._ask(tr("Idioma instalado"), tr("Idioma «{c}» instalado. ¿Cambiar a él ahora?").format(c=code)) == "yes":
            self.set_language(code)

    # ================================================================ edición
    def undo(self):
        if self.history.can_undo():
            lab = self.history.undo()
            self.full_refresh()
            self.status(tr("Deshecho: {l}").format(l=lab))

    def redo(self):
        if self.history.can_redo():
            lab = self.history.redo()
            self.full_refresh()
            self.status(tr("Rehecho: {l}").format(l=lab))

    def history_goto(self, row):
        self.history.goto(row)
        self.full_refresh()

    def delete_selected(self):
        sel = self.selection()
        if not sel:
            return
        self.checkpoint(tr("Eliminar {n}").format(n=len(sel)))
        self.doc.remove([e.id for e in sel])
        self.canvas.set_selection([])
        self.changed()

    def copy(self):
        sel = self.selection()
        self.clipboard = [e.to_dict() for e in sel]
        if sel:
            QApplication.clipboard().setText(json.dumps({"efpd_entities": self.clipboard}))
            self.status(tr("{n} copiada(s)").format(n=len(sel)))

    def cut(self):
        self.copy()
        self.delete_selected()

    def paste(self):
        data = self.clipboard
        try:
            txt = QApplication.clipboard().text()
            if txt.startswith('{"efpd_entities"'):
                data = json.loads(txt)["efpd_entities"]
        except (ValueError, KeyError):
            pass
        if not data:
            return
        self.checkpoint(tr("Pegar"))
        new = []
        for d in data:
            e = entity_from_dict(d).clone()
            e.move(5.0, -5.0)
            self.doc.add(e)
            new.append(e.id)
        self.changed()
        self.canvas.set_selection(new)

    def duplicate(self):
        sel = self.selection()
        if not sel:
            return
        self.checkpoint(tr("Duplicar"))
        new = []
        for e in sel:
            n = e.clone()
            n.move(5.0, -5.0)
            self.doc.add(n)
            new.append(n.id)
        self.changed()
        self.canvas.set_selection(new)

    def nudge(self, dx, dy):
        sel = [e for e in self.selection() if not e.locked]
        if not sel:
            return
        self.checkpoint(tr("Desplazar"))
        for e in sel:
            e.move(dx, dy)
        self.changed(refresh_props=True)

    def rotate_selected(self, deg):
        sel = [e for e in self.selection() if not e.locked and e.HAS_POS]
        if sel:
            self.checkpoint(tr("Girar"))
            for e in sel:
                e.rotate_by(deg)
            self.changed(refresh_props=True)

    def mirror_selected(self):
        sel = self.selection()
        if sel:
            self.checkpoint(tr("Simetría"))
            layout.mirror_h(self.doc, sel)
            self.changed(refresh_props=True)

    def toggle_lock(self):
        sel = self.selection()
        if sel:
            self.checkpoint(tr("Bloqueo"))
            v = not all(e.locked for e in sel)
            for e in sel:
                e.locked = v
            self.changed(refresh_props=True)

    def array_selected(self):
        sel = self.selection()
        if not sel:
            self.status(tr("Seleccione primero las entidades a repetir"))
            return
        dlg = ArrayDialog(self)
        if dlg.exec():
            cols, rows, dx, dy = dlg.values()
            self.checkpoint(tr("Matriz"))
            new = layout.make_array(self.doc, sel, cols, rows, dx, dy)
            self.changed()
            self.canvas.set_selection([e.id for e in sel] + [e.id for e in new])

    def run_layout(self, key):
        sel = self.selection()
        if not sel:
            self.status(tr("Seleccione entidades para alinear o distribuir"))
            return
        if key == "dist_panel":
            axes = [tr("Horizontal (a lo ancho)"), tr("Vertical (a lo alto)")]
            axis, ok = QInputDialog.getItem(self, tr("Distribución automática"), tr("Eje:"), axes, 0, False)
            if not ok:
                return
            margin, ok = QInputDialog.getDouble(self, tr("Distribución automática"), tr("Margen lateral (mm):"),
                                                15.0, 0, 500, 2)
            if not ok:
                return
            self.checkpoint(tr("Distribución automática"))
            layout.distribute_on_panel(self.doc, sel, "h" if axis == axes[0] else "v", margin, linked=True)
            self.status(tr("Posiciones vinculadas a W/H y a la variable de margen: cambie el panel y se redistribuyen"))
        else:
            self.checkpoint(tr("Distribuir") if key.startswith("dist_") else tr("Alinear"))
            if key.startswith("align_"):
                layout.align(self.doc, sel, key[6:])
            elif key == "dist_h":
                layout.distribute(self.doc, sel, "h")
            elif key == "dist_v":
                layout.distribute(self.doc, sel, "v")
        self.changed(refresh_props=True)

    # ================================================================ panel / componentes
    def apply_preset(self, name):
        add = True
        if name != "Personalizado":
            r = self._ask(tr("Plantilla"), tr("Aplicar «{n}».\n¿Añadir también los taladros de fijación?").format(n=tr(name)),
                          [("yes", tr("Sí"), QMessageBox.ButtonRole.YesRole),
                           ("no", tr("No"), QMessageBox.ButtonRole.NoRole),
                           ("cancel", tr("Cancelar"), QMessageBox.ButtonRole.RejectRole)], "yes")
            if r == "cancel":
                return
            add = r == "yes"
        self.checkpoint(tr("Plantilla {n}").format(n=tr(name)))
        apply_preset(self.doc, name, add_holes=add)
        self.changed(refresh_props=True)
        self.canvas.fit_view()

    def start_place_component(self, cid):
        comp = self.lib.get(cid)
        if not comp:
            return
        comp.pop("builtin", None)
        comp.pop("library", None)
        proto = ComponentEntity(comp=comp, name="")
        proto.layer = self.active_layer if self.doc.process_of(self.active_layer) == "cut" else "cut"
        self.canvas.set_tool("component", proto)
        self.status(tr("Colocando «{n}» — clic en el panel, Esc para terminar").format(n=comp_name(comp)))
        self.canvas.setFocus()

    def _save_from_editor(self, dlg):
        c, errs = dlg.result_comp()
        if not c or errs:
            return None
        lib = dlg.selected_library()
        try:
            cid = self.lib.save_user(c, lib)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return None
        self.library_panel.refresh()
        self.status(tr("Componente «{n}» guardado en la biblioteca «{l}»").format(n=c["name"], l=lib))
        return cid

    def edit_component(self, cid, duplicate=False):
        comp = self.lib.get(cid) if cid else None
        if comp and duplicate:
            comp.pop("id", None)
            comp["name"] = comp_name(comp) + " " + tr("(copia)")
            comp.pop("name_fmt", None)
            if comp.get("builtin", True):
                comp["category"] = tr(comp.get("category", "Personalizados"))
                comp.pop("library", None)
        title = tr("Editar componente") if cid and not duplicate else tr("Nuevo componente")
        dlg = ComponentEditor(self, comp, title, library=self.lib)
        if dlg.exec():
            self._save_from_editor(dlg)

    # ---------------------------------------------------------------- texto y escalas
    def place_text(self, x, y):
        from .textscale import TextDialog
        dlg = TextDialog(self, self.doc)
        if dlg.exec():
            params, layer = dlg.result_params()
            if not str(params.get("text", "")).strip():
                return
            e = TextEntity()
            e.p.update(params)
            e.p["x"], e.p["y"] = round(x, 4), round(y, 4)
            e.layer = layer or "print"
            self.checkpoint(tr("Añadir texto"))
            self.doc.add(e)
            self.changed()
            self.canvas.set_selection([e.id])

    def edit_text(self, e):
        from .textscale import TextDialog
        dlg = TextDialog(self, self.doc, e)
        if dlg.exec():
            params, layer = dlg.result_params()
            self.checkpoint(tr("Editar texto"))
            params["x"], params["y"] = e.p.get("x"), e.p.get("y")
            e.p.clear()
            e.p.update(params)
            if layer:
                e.layer = layer
            self.changed(refresh_props=True)

    def _scale_hint(self):
        """Si hay un potenciómetro seleccionado, adapta y coloca la escala sobre él."""
        sel = [e for e in self.selection() if e.TYPE == "component"]
        if len(sel) != 1:
            return None, None
        c = sel[0]
        ev = self.doc.evaluator()
        comp = c.p.get("comp", {})
        cx, cy, crot = c.v(ev, "x"), c.v(ev, "y"), c.v(ev, "rot")
        travel = None
        cap_w = 10.0
        knob_r = None
        for s_ in comp.get("reference", []):
            if s_.get("shape") == "rect" and float(s_.get("w", 1)) < 1.0:
                travel = float(s_.get("h", 0))
            elif s_.get("shape") == "rect":
                cap_w = float(s_.get("w", cap_w))
            elif s_.get("shape") == "circle":
                knob_r = max(knob_r or 0.0, float(s_.get("d", 0)) / 2)
        if travel:
            import math
            off = cap_w / 2 + 2.0
            a = math.radians(crot)
            x, y = cx - off * math.cos(a), cy - off * math.sin(a)
            return {"shape": "lineal", "length": round(travel, 3), "rot": round(crot + 90.0, 3)}, (x, y)
        hint = {"shape": "redonda", "rot": round(crot, 3)}
        if knob_r:
            hint["radius"] = round(knob_r + 1.5, 2)
        return hint, (cx, cy)

    def insert_scale(self):
        from .textscale import ScaleDialog
        from ..core.scale import ScaleEntity
        hint, at = self._scale_hint()
        dlg = ScaleDialog(self, self.doc, None, hint)
        if not dlg.exec():
            return
        params, layer = dlg.result_params()
        e = ScaleEntity()
        e.p.update(params)
        e.layer = layer or "print"
        if at is not None:
            e.p["x"], e.p["y"] = round(at[0], 4), round(at[1], 4)
            self.checkpoint(tr("Añadir escala"))
            self.doc.add(e)
            self.changed()
            self.canvas.set_selection([e.id])
            self.status(tr("Escala colocada sobre el potenciómetro seleccionado"))
        else:
            self.canvas.set_tool("place", e)
            self.status(tr("Haga clic en el panel para colocar la escala"))
            self.canvas.setFocus()

    def insert_stud(self):
        from .studdlg import StudDialog
        from ..core.stud import StudEntity
        dlg = StudDialog(self, self.doc)
        if not dlg.exec():
            return
        e = StudEntity()
        e.p.update(dlg.result_params())
        e.layer = next((L.id for L in self.doc.layers if L.process == "cut"), self.active_layer)
        self.canvas.set_tool("place", e)
        self.status(tr("Haga clic en el panel para colocar el perno / casquillo · Esc para cancelar"))
        self.canvas.setFocus()

    def edit_stud(self, e):
        from .studdlg import StudDialog
        dlg = StudDialog(self, self.doc, e)
        if dlg.exec():
            params = dlg.result_params()
            self.checkpoint(tr("Editar perno / casquillo"))
            params["x"], params["y"] = e.p.get("x"), e.p.get("y")
            e.p.clear()
            e.p.update(params)
            self.changed(refresh_props=True)

    def edit_scale(self, e):
        from .textscale import ScaleDialog
        dlg = ScaleDialog(self, self.doc, e)
        if dlg.exec():
            params, layer = dlg.result_params()
            self.checkpoint(tr("Editar escala"))
            params["x"], params["y"] = e.p.get("x"), e.p.get("y")
            e.p.clear()
            e.p.update(params)
            if layer:
                e.layer = layer
            self.changed(refresh_props=True)

    def edit_instance_component(self, e):
        dlg = ComponentEditor(self, e.p.get("comp", {}), tr("Definición de esta instancia"), show_library=False)
        if dlg.exec():
            c, errs = dlg.result_comp()
            if c and not errs:
                self.checkpoint(tr("Editar componente"))
                e.p["comp"] = c
                self.changed(refresh_props=True)

    def save_instance_to_library(self, e):
        comp = dict(e.p.get("comp", {}))
        comp.pop("id", None)
        comp["name"] = tr(comp.get("name", "Componente"))
        dlg = ComponentEditor(self, comp, tr("Guardar en una biblioteca"), library=self.lib)
        if dlg.exec():
            self._save_from_editor(dlg)

    def delete_component(self, cid):
        if self._ask(APP_NAME, tr("¿Eliminar este componente de la biblioteca de usuario?")) == "yes":
            self.lib.delete_user(cid)
            self.library_panel.refresh()

    def component_from_selection(self):
        sel = [e for e in self.selection() if e.TYPE not in ("dimension", "image")]
        if not sel:
            self.status(tr("Seleccione las formas que formarán el componente"))
            return
        comp = component_from_entities(self.doc, sel, tr("Nuevo componente"))
        dlg = ComponentEditor(self, comp, tr("Nuevo componente desde selección"), library=self.lib)
        dlg.name.selectAll()
        dlg.name.setFocus()
        if dlg.exec():
            self._save_from_editor(dlg)

    def new_library(self):
        name, ok = QInputDialog.getText(self, tr("Nueva biblioteca"), tr("Nombre de la nueva biblioteca:"))
        if ok and name.strip():
            try:
                self.lib.create_library(name)
            except (OSError, ValueError) as e:
                QMessageBox.warning(self, APP_NAME, str(e))
                return
            self.library_panel.refresh()

    def import_library(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Importar biblioteca"), self._last_dir(), "JSON (*.json)")
        if path:
            try:
                name = self.lib.import_library(path)
            except (OSError, ValueError) as e:
                QMessageBox.warning(self, APP_NAME, tr("No se pudo importar:\n{e}").format(e=e))
                return
            self.library_panel.refresh()
            self.status(tr("Biblioteca «{n}» importada").format(n=name))

    def export_library(self, name):
        from ..core.library import slugify
        path, _ = QFileDialog.getSaveFileName(self, tr("Exportar biblioteca"),
                                              os.path.join(self._last_dir(), slugify(name) + ".json"), "JSON (*.json)")
        if path:
            self.lib.export_library(name, path)
            self.status(tr("Biblioteca exportada: {p}").format(p=path))

    def delete_library(self, name):
        if name == BUILTIN_LIBRARY:
            return
        if self._ask(APP_NAME, tr("¿Eliminar la biblioteca «{n}» y todos sus componentes?").format(n=name)) == "yes":
            self.lib.delete_library(name)
            self.library_panel.refresh()

    # ================================================================ herramientas
    def run_checks(self):
        issues = check(self.doc)
        self.checks_panel.show_issues(issues)
        self.canvas.flagged = {i for iss in issues if iss.level in ("error", "aviso") for i in iss.ids}
        self.canvas.update()
        self.d_checks.show()
        self.d_checks.raise_()
        n_err = sum(1 for i in issues if i.level == "error")
        n_warn = sum(1 for i in issues if i.level == "aviso")
        self.status(tr("Verificación: {e} errores, {w} avisos").format(e=n_err, w=n_warn))
        return issues

    def measure_selection(self):
        sel = self.selection()
        if len(sel) < 2:
            self.status(tr("Seleccione dos entidades"))
            return
        c, gap, ca, cb = measure_between(self.doc, sel[0], sel[1])
        self.canvas._measure = (ca, cb)
        self.canvas.update()
        msg = tr("Entre centros: {c} mm (ΔX {dx}, ΔY {dy})\nHolgura mínima entre contornos: {g} mm").format(
            c=f"{c:.3f}", dx=f"{cb[0] - ca[0]:.3f}", dy=f"{cb[1] - ca[1]:.3f}", g=f"{gap:.3f}")
        self.status(msg.replace("\n", " · "))
        QMessageBox.information(self, tr("Medición"), msg)

    def auto_dimension(self):
        sel = self.selection() or [e for e in self.doc.entities if e.TYPE != "dimension"]
        self.checkpoint(tr("Acotación automática"))
        new = layout.auto_dimension(self.doc, sel)
        if not self.actions["show_dims"].isChecked():
            self.actions["show_dims"].setChecked(True)
        self.changed()
        self.status(tr("{n} cotas vinculadas creadas").format(n=len(new)))

    def panel_dimensions(self):
        self.checkpoint(tr("Acotar panel"))
        layout.panel_dimensions(self.doc)
        if not self.actions["show_dims"].isChecked():
            self.actions["show_dims"].setChecked(True)
        self.changed()

    def show_3d(self):
        View3DDialog(self, self.doc, self.export_stl).exec()

    def preferences(self):
        dlg = PreferencesDialog(self, self.doc, self.prefs)
        if dlg.exec():
            self.checkpoint(tr("Preferencias del documento"))
            self.doc.settings.update(dlg.doc_settings())
            old = dict(self.prefs)
            self.prefs.update(dlg.prefs())
            for k, v in self.prefs.items():
                self.settings.setValue(k, v)
            self.history.limit = self.prefs["undo_limit"]
            self._restart_autosave()
            if self.prefs["theme"] != old["theme"]:
                self._apply_theme()
            if self.prefs["icon_size"] != old["icon_size"]:
                self._build_toolbars()
            self.full_refresh()

    def toggle_theme(self):
        self.prefs["theme"] = "claro" if self.prefs["theme"] == "oscuro" else "oscuro"
        self.settings.setValue("theme", self.prefs["theme"])
        self._apply_theme()

    def _apply_theme(self):
        self.colors = apply_theme(QApplication.instance(), self.prefs["theme"])
        self.props.refresh()
        self.canvas.update()

    def configure_toolbars(self):
        dlg = ToolbarConfigDialog(self, TOOLBARS, self.actions, self._toolbar_config())
        if dlg.exec():
            self.settings.setValue("toolbars", json.dumps(dlg.result()))
            self._build_toolbars()

    def canvas_context_menu(self, gpos):
        m = QMenu(self)
        a = self.actions
        if self.canvas.selected:
            for k in ("cut", "copy", "duplicate", "delete", None, "rotate90", "mirror", "array", "lock", None,
                      "measure_sel", "comp_from_sel", "autodim"):
                m.addSeparator() if k is None else m.addAction(a[k])
            sub = m.addMenu(tr("Alinear"))
            for k in ("align_left", "align_hcenter", "align_right", "align_top", "align_vcenter", "align_bottom",
                      "dist_h", "dist_v", "dist_panel"):
                sub.addAction(a[k])
            sub2 = m.addMenu(tr("Mover a capa"))
            for L in self.doc.layers:
                sub2.addAction(L.name, lambda _c=False, lid=L.id: self._move_to_layer(lid))
        else:
            for k in ("paste", "select_all", None, "zoom_fit", "view3d", "check", "panel_dims", "show_dims"):
                m.addSeparator() if k is None else m.addAction(a[k])
        m.exec(gpos)

    def _move_to_layer(self, lid):
        self.checkpoint(tr("Cambiar capa"))
        for e in self.selection():
            e.layer = lid
        self.changed(refresh_props=True)

    # ================================================================ importación
    def _center(self):
        W, H, _T, _r = self.doc.panel_dims()
        return (W / 2, H / 2)

    def import_vector(self, kind):
        flt = "DXF (*.dxf)" if kind == "dxf" else "SVG (*.svg)"
        path, _ = QFileDialog.getOpenFileName(self, tr("Importar {k}").format(k=kind.upper()), self._last_dir(), flt)
        if not path:
            return
        try:
            e = (dxf_import.import_dxf if kind == "dxf" else svg_import.import_svg)(path, center=self._center())
        except Exception as ex:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, tr("No se pudo importar:\n{e}").format(e=ex))
            return
        opts = [("cut", tr("Mecanizado pasante")), ("engrave", tr("Grabado")), ("print", tr("Serigrafía")),
                ("pocket", tr("Fresado / rebaje")), ("ref", tr("Referencia"))]
        choice, ok = QInputDialog.getItem(self, tr("Importar"), tr("¿Cómo se fabricará este contorno?"),
                                          [o[1] for o in opts], 0, False)
        if not ok:
            return
        proc = next((k for k, lab in opts if lab == choice), "cut")
        e.layer = next((L.id for L in self.doc.layers if L.process == proc), self.active_layer)
        self.checkpoint(tr("Importar {f}").format(f=os.path.basename(path)))
        self.doc.add(e)
        self.changed()
        self.canvas.set_selection([e.id])
        self.status(tr("Importados {n} trazos de {f}").format(n=len(e.p["paths"]), f=os.path.basename(path)))

    def import_image(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Importar imagen"), self._last_dir(),
                                              tr("Imágenes (*.png *.jpg *.jpeg *.bmp);;SVG como contorno (*.svg)"))
        if not path:
            return
        if path.lower().endswith(".svg"):
            self.import_vector("svg")
            return
        img = QImage(path)
        if img.isNull():
            QMessageBox.warning(self, APP_NAME, tr("No se pudo leer la imagen"))
            return
        if max(img.width(), img.height()) > 2000:
            img = img.scaled(2000, 2000, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        buf.close()
        data = base64.b64encode(bytes(ba.data())).decode("ascii")
        w = 40.0
        h = round(w * img.height() / max(1, img.width()), 3)
        cx, cy = self._center()
        e = ImageEntity(x=cx, y=cy, w=w, h=h, data=data, source=os.path.basename(path), layer="print")
        self.checkpoint(tr("Importar imagen"))
        self.doc.add(e)
        self.changed()
        self.canvas.set_selection([e.id])

    # ================================================================ exportación
    def _save_name(self, title, ext, flt):
        base = (self.doc.meta.get("title") or "panel").replace(" ", "_")
        if self.path:
            base = os.path.splitext(os.path.basename(self.path))[0]
        path, _ = QFileDialog.getSaveFileName(self, title, os.path.join(self._last_dir(), base + ext), flt)
        if path and not path.lower().endswith(ext):
            path += ext
        return path

    def _run_export(self, fn, path, label):
        try:
            res = fn()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, APP_NAME, tr("Error al exportar {f}:\n{e}").format(f=label, e=e)
                                 + "\n\n" + traceback.format_exc(limit=3))
            return None
        self.status(tr("{f} exportado: {p}").format(f=label, p=path))
        return res if res is not None else True

    def _pre_export_check(self):
        errs = [i for i in check(self.doc) if i.level == "error"]
        if errs:
            r = self._ask(tr("Verificación"), tr("Se han detectado {n} errores de fabricación (p. ej.: {m}).\n"
                                                 "¿Exportar de todos modos?").format(n=len(errs), m=errs[0].message))
            return r == "yes"
        return True

    def _roles(self):
        return ("outline", "cut", "pocket", "pocket_back", "engrave", "print") + (("dim",) if self.canvas.show_dims else ())

    def export_dxf(self):
        if not self._pre_export_check():
            return
        p = self._save_name(tr("Exportar DXF"), ".dxf", "DXF (*.dxf)")
        if p:
            self._run_export(lambda: dxf_export.export_dxf(self.doc, p, self._roles()), p, "DXF")

    def export_svg(self, style):
        p = self._save_name(tr("Exportar SVG"), ".svg", "SVG (*.svg)")
        if p:
            self._run_export(lambda: svg_export.export_svg(self.doc, p, self._roles(), style), p, "SVG")

    def export_pdf(self, mode):
        p = self._save_name(tr("Exportar PDF"), ".pdf", "PDF (*.pdf)")
        if p:
            self._run_export(lambda: render.export_pdf(self.doc, p, mode, show_dims=self.canvas.show_dims), p, "PDF")

    def export_png(self):
        cv = self.canvas
        auto = cv.auto_dims if cv.show_dims else "off"
        dlg = ImageExportDialog(self, user_dims=cv.show_dims, auto_mode=auto, has_selection=bool(cv.selected))
        if not dlg.exec():
            return
        p = self._save_name(tr("Exportar PNG"), ".png", "PNG (*.png)")
        if p:
            sel = set(cv.selected)

            def go():
                img = render.render_image(self.doc, dlg.dpi.value(), dlg.mode.currentData(), dlg.dims.isChecked(),
                                          dlg.transp.isChecked(), auto_dims=dlg.auto.currentData(), selected=sel)
                if not img.save(p):
                    raise OSError(tr("No se pudo escribir el archivo"))
            self._run_export(go, p, "PNG")

    def export_stl(self):
        p = self._save_name(tr("Exportar STL"), ".stl", "STL (*.stl)")
        if p:
            n = self._run_export(lambda: mesh.export_stl(self.doc, p), p, "STL")
            if n:
                self.status(tr("STL exportado: {n} triángulos → {p}").format(n=n, p=p))

    def export_gcode(self):
        if not self._pre_export_check():
            return
        _W, _H, T, _r = self.doc.panel_dims()
        dlg = GcodeDialog(self, self.gsettings, T)
        if not dlg.exec():
            return
        self.gsettings = dlg.settings()
        self.settings.setValue("gcode", json.dumps(self.gsettings.to_dict()))
        p = self._save_name(tr("Exportar G-code"), ".nc", "G-code (*.nc *.gcode *.ngc *.tap)")
        if p:
            warns = self._run_export(lambda: gcode.export_gcode(self.doc, p, self.gsettings), p, "G-code")
            if isinstance(warns, list) and warns:
                QMessageBox.information(self, "G-code", tr("Exportado con observaciones:") + "\n\n• "
                                        + "\n• ".join(dict.fromkeys(warns)))

    def export_hpgl(self):
        p = self._save_name(tr("Exportar HPGL"), ".plt", "HPGL (*.plt *.hpgl)")
        if p:
            self._run_export(lambda: gcode.export_hpgl(self.doc, p), p, "HPGL")

    # ================================================================ ayuda
    def help_keys(self):
        QMessageBox.information(self, tr("Atajos y uso"), tr(HELP_HTML))

    def about(self):
        AboutDialog(self).exec()


HELP_HTML = N_("""<h3>Navegación</h3>
<p>Rueda: zoom · Botón central o Espacio+arrastrar: desplazar · Ctrl+0: ajustar</p>
<h3>Herramientas</h3>
<p>V seleccionar · R rectángulo · Mayús+R redondeado · C círculo · E elipse · G polígono · P polígono libre ·
S ranura · O ranura ovalada · M agujero · Mayús+M avellanado · Ctrl+Mayús+M roscado · Mayús+D agujero en D ·
F rebaje · T texto · D cota · Mayús+Q medir</p>
<h3>Edición</h3>
<p>Flechas: mover un paso de rejilla (Mayús ×10, Ctrl 0.1 mm) · Ctrl+D duplicar · Ctrl+R girar 90° ·
Supr eliminar · Ctrl+L bloquear · F7 verificar · F3 vista 3D · F9/F10 ajuste a rejilla/objetos ·
Ctrl+Mayús+D mostrar cotas</p>
<h3>Cotas</h3>
<p>Con «Mostrar cotas» activo se ven el tamaño de cada elemento a sus lados y la posición (X/Y desde la esquina
inferior izquierda) de los seleccionados. Elija el modo en Ver → Cotas automáticas.</p>
<h3>Parámetros</h3>
<p>Cualquier medida admite expresiones: <b>=W/2</b>, <b>=margen + 2*paso</b>. Defina variables en el panel
<i>Variables</i>. W, H y T son el ancho, alto y espesor del panel.</p>
<h3>Ventana de selección</h3>
<p>De izquierda a derecha: sólo lo que queda dentro · de derecha a izquierda: todo lo que toca.</p>""")
