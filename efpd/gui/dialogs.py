"""Diálogos: matriz, G-code, editor de componentes, preferencias, barras, PNG, acerca de."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QVBoxLayout)

from .. import APP_NAME, __version__
from ..core.library import BUILTIN_LIBRARY, DEFAULT_USER_LIBRARY, TEMPLATE, validate
from ..i18n import N_, tr
from ..io.gcode import GcodeSettings
from . import icons
from .comppreview import ComponentPreview


def _dspin(v, lo=-10000.0, hi=10000.0, dec=3, step=0.5, suffix=" mm"):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setValue(v)
    if suffix:
        s.setSuffix(suffix)
    return s


def _buttons(dlg):
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Aceptar"))
    bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


# ======================================================================= matriz
class ArrayDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("Matriz de copias"))
        f = QFormLayout(self)
        self.cols = QSpinBox()
        self.cols.setRange(1, 200)
        self.cols.setValue(4)
        self.rows = QSpinBox()
        self.rows.setRange(1, 200)
        self.rows.setValue(1)
        self.dx = _dspin(20.0)
        self.dy = _dspin(20.0)
        f.addRow(tr("Columnas"), self.cols)
        f.addRow(tr("Filas"), self.rows)
        f.addRow(tr("Paso X"), self.dx)
        f.addRow(tr("Paso Y"), self.dy)
        f.addRow(_buttons(self))

    def values(self):
        return self.cols.value(), self.rows.value(), self.dx.value(), self.dy.value()


# ======================================================================= G-code
class GcodeDialog(QDialog):
    def __init__(self, parent, s: GcodeSettings, thickness: float):
        super().__init__(parent)
        self.setWindowTitle(tr("Exportar G-code"))
        v = QVBoxLayout(self)
        g1 = QGroupBox(tr("Herramienta"))
        f = QFormLayout(g1)
        self.tool_d = _dspin(s.tool_d, 0.1, 20, 3, 0.1)
        self.rpm = _dspin(s.rpm, 0, 60000, 0, 500, " rpm")
        self.feed = _dspin(s.feed, 1, 20000, 0, 50, " mm/min")
        self.plunge = _dspin(s.plunge, 1, 5000, 0, 10, " mm/min")
        self.step = _dspin(s.step_down, 0.01, 10, 3, 0.05)
        self.safe = _dspin(s.safe_z, 0.5, 50, 2, 0.5)
        for lab, w in ((tr("Diámetro fresa"), self.tool_d), (tr("Husillo"), self.rpm), (tr("Avance XY"), self.feed),
                       (tr("Avance Z"), self.plunge), (tr("Paso en Z"), self.step), (tr("Z seguridad"), self.safe)):
            f.addRow(lab, w)
        v.addWidget(g1)
        g2 = QGroupBox(tr("Operaciones"))
        f2 = QFormLayout(g2)
        self.brk = _dspin(s.breakthrough, 0, 5, 2, 0.05)
        self.eng = _dspin(s.engrave_depth, 0.01, 5, 3, 0.05)
        self.stepover = _dspin(s.stepover, 0.1, 0.9, 2, 0.05, "")
        f2.addRow(QLabel(tr("Espesor del panel: {t} mm").format(t=f"{thickness:.2f}")))
        f2.addRow(tr("Sobrepasada inferior"), self.brk)
        f2.addRow(tr("Profundidad de grabado"), self.eng)
        f2.addRow(tr("Solape vaciado (× Ø)"), self.stepover)
        self.chk = {}
        for key, lab in (("compensate", tr("Compensar radio de herramienta")),
                         ("climb", tr("Fresado en concordancia (trepado)")),
                         ("include_engrave", tr("Grabado")), ("include_print_as_engrave", tr("Serigrafía como grabado")),
                         ("include_pockets", tr("Rebajes")), ("include_cuts", tr("Mecanizados pasantes")),
                         ("include_outline", tr("Contorno exterior"))):
            cb = QCheckBox(lab)
            cb.setChecked(getattr(s, key))
            self.chk[key] = cb
            f2.addRow(cb)
        v.addWidget(g2)
        note = QLabel(tr("G-code básico (G0/G1/G2/G3, mm, absoluto). Revíselo siempre en un simulador antes de mecanizar."))
        note.setWordWrap(True)
        note.setProperty("role", "hint")
        v.addWidget(note)
        v.addWidget(_buttons(self))

    def settings(self) -> GcodeSettings:
        s = GcodeSettings(tool_d=self.tool_d.value(), rpm=self.rpm.value(), feed=self.feed.value(),
                          plunge=self.plunge.value(), step_down=self.step.value(), safe_z=self.safe.value(),
                          breakthrough=self.brk.value(), engrave_depth=self.eng.value(),
                          stepover=self.stepover.value())
        for k, cb in self.chk.items():
            setattr(s, k, cb.isChecked())
        return s


# ======================================================================= componentes
class ComponentEditor(QDialog):
    """Editor de componentes en JSON con vista previa en vivo y elección de biblioteca."""

    def __init__(self, parent, comp=None, title=None, library=None, show_library=True):
        super().__init__(parent)
        self.setWindowTitle(title or tr("Componente"))
        self.resize(960, 600)
        self.library = library
        v = QVBoxLayout(self)
        top = QFormLayout()
        comp = dict(comp or TEMPLATE)
        if comp is TEMPLATE or comp.get("name") == TEMPLATE["name"]:
            comp["name"] = tr(TEMPLATE["name"])
        self.name = QLineEdit(comp.get("name", ""))
        self.cat = QLineEdit(comp.get("category", "Personalizados"))
        self.desc = QLineEdit(comp.get("description", ""))
        top.addRow(tr("Nombre"), self.name)
        self.lib_combo = None
        if show_library and library is not None:
            row = QHBoxLayout()
            self.lib_combo = QComboBox()
            names = library.library_names() or [tr(DEFAULT_USER_LIBRARY)]
            self.lib_combo.addItems(names)
            cur = comp.get("library")
            if cur and cur != BUILTIN_LIBRARY:
                if self.lib_combo.findText(cur) < 0:
                    self.lib_combo.addItem(cur)
                self.lib_combo.setCurrentText(cur)
            row.addWidget(self.lib_combo, 1)
            b = QPushButton(tr("Nueva biblioteca…"))
            b.clicked.connect(self._new_library)
            row.addWidget(b)
            top.addRow(tr("Biblioteca"), row)
        top.addRow(tr("Categoría"), self.cat)
        top.addRow(tr("Descripción"), self.desc)
        v.addLayout(top)
        sp = QSplitter()
        self.text = QPlainTextEdit()
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(mono)
        body = {k: comp.get(k, []) for k in ("cutouts", "reference", "footprint", "graphics")}
        self.text.setPlainText(json.dumps(body, indent=2, ensure_ascii=False))
        self.text.textChanged.connect(self._update)
        self.preview = ComponentPreview(260)
        sp.addWidget(self.text)
        sp.addWidget(self.preview)
        sp.setSizes([520, 420])
        v.addWidget(sp, 1)
        self.err = QLabel()
        self.err.setWordWrap(True)
        v.addWidget(self.err)
        help_ = QLabel(tr("Formas: circle(d) · rect(w,h,r) · oval(l,w) · dhole(d,flat) · ellipse(w,h) · "
                          "poly(pts,closed) · text(text,size, sólo en graphics). Todas con x, y, rot opcionales (mm). "
                          "cutouts = mecanizado · reference = silueta visible · footprint = cuerpo trasero."))
        help_.setWordWrap(True)
        help_.setProperty("role", "hint")
        v.addWidget(help_)
        self.bb = _buttons(self)
        v.addWidget(self.bb)
        self.extra = {k: comp[k] for k in ("id",) if k in comp}
        self._update()

    def _new_library(self):
        name, ok = QInputDialog.getText(self, tr("Nueva biblioteca"), tr("Nombre de la nueva biblioteca:"))
        name = (name or "").strip()
        if ok and name and name != BUILTIN_LIBRARY:
            if self.lib_combo.findText(name) < 0:
                self.lib_combo.addItem(name)
            self.lib_combo.setCurrentText(name)

    def selected_library(self):
        return self.lib_combo.currentText().strip() if self.lib_combo is not None else None

    def result_comp(self):
        try:
            body = json.loads(self.text.toPlainText())
        except ValueError as e:
            return None, [tr("JSON no válido: {e}").format(e=e)]
        if not isinstance(body, dict):
            return None, [tr("El JSON debe ser un objeto con cutouts/reference/footprint/graphics")]
        comp = {"name": self.name.text().strip(), "category": self.cat.text().strip() or "Personalizados",
                "description": self.desc.text().strip(), **self.extra}
        for k in ("cutouts", "reference", "footprint", "graphics"):
            comp[k] = body.get(k, [])
        return comp, validate(comp)

    def _update(self):
        comp, errs = self.result_comp()
        ok_btn = self.bb.button(QDialogButtonBox.StandardButton.Ok)
        if comp is not None:
            self.preview.set_comp(comp)
        self.err.setText("<span style='color:#ff4d4f'>" + " · ".join(errs) + "</span>" if errs
                         else "✔ " + tr("Definición válida"))
        ok_btn.setEnabled(not errs)


# ======================================================================= preferencias
class PreferencesDialog(QDialog):
    def __init__(self, parent, doc, prefs: dict):
        super().__init__(parent)
        self.setWindowTitle(tr("Preferencias"))
        f = QFormLayout(self)
        st = doc.settings
        self.grid = _dspin(float(st.get("grid", 2.5)), 0.01, 100, 3, 0.5)
        self.major = QSpinBox()
        self.major.setRange(2, 20)
        self.major.setValue(int(st.get("grid_major", 5)))
        self.min_edge = _dspin(float(st.get("min_edge", 2.0)), 0, 50, 2, 0.5)
        self.min_web = _dspin(float(st.get("min_web", 1.5)), 0, 50, 2, 0.5)
        self.text_gap = _dspin(float(st.get("min_text_gap", 0.5)), 0, 50, 2, 0.1)
        self.text_edge = _dspin(float(st.get("min_text_edge", 1.0)), 0, 50, 2, 0.5)
        self.dim_h = _dspin(float(st.get("dim_text_h", 2.5)), 0.5, 20, 2, 0.5)
        self.theme = QComboBox()
        self.theme.addItem(tr("Oscuro"), "oscuro")
        self.theme.addItem(tr("Claro"), "claro")
        self.theme.setCurrentIndex(max(0, self.theme.findData(prefs.get("theme", "oscuro"))))
        self.icon_size = QSpinBox()
        self.icon_size.setRange(20, 64)
        self.icon_size.setSuffix(" px")
        self.icon_size.setValue(int(prefs.get("icon_size", 32)))
        self.autosave = QSpinBox()
        self.autosave.setRange(0, 120)
        self.autosave.setSuffix(" min")
        self.autosave.setValue(int(prefs.get("autosave_min", 2)))
        self.autosave.setSpecialValueText(tr("desactivado"))
        self.undo_limit = QSpinBox()
        self.undo_limit.setRange(0, 100000)
        self.undo_limit.setSpecialValueText(tr("ilimitado"))
        self.undo_limit.setValue(int(prefs.get("undo_limit", 0)))
        f.addRow(QLabel("<b>" + tr("Documento") + "</b>"))
        f.addRow(tr("Rejilla"), self.grid)
        f.addRow(tr("Línea mayor cada"), self.major)
        f.addRow(tr("Distancia mínima al borde"), self.min_edge)
        f.addRow(tr("Puente mínimo entre huecos"), self.min_web)
        f.addRow(tr("Separación mínima texto–hueco"), self.text_gap)
        f.addRow(tr("Distancia mínima texto–borde"), self.text_edge)
        f.addRow(tr("Altura texto de cotas"), self.dim_h)
        f.addRow(QLabel("<b>" + tr("Aplicación") + "</b>"))
        f.addRow(tr("Tema"), self.theme)
        f.addRow(tr("Tamaño de iconos"), self.icon_size)
        f.addRow(tr("Autoguardado cada"), self.autosave)
        f.addRow(tr("Pasos de deshacer"), self.undo_limit)
        f.addRow(_buttons(self))

    def doc_settings(self):
        return {"grid": self.grid.value(), "grid_major": self.major.value(), "min_edge": self.min_edge.value(),
                "min_web": self.min_web.value(), "dim_text_h": self.dim_h.value(),
                "min_text_gap": self.text_gap.value(), "min_text_edge": self.text_edge.value()}

    def prefs(self):
        return {"theme": self.theme.currentData(), "autosave_min": self.autosave.value(),
                "undo_limit": self.undo_limit.value(), "icon_size": self.icon_size.value()}


# ======================================================================= barras de herramientas
class ToolbarConfigDialog(QDialog):
    def __init__(self, parent, toolbars: dict, actions: dict, current: dict):
        """toolbars: {nombre: [claves posibles]}, actions: {clave: QAction}, current: {nombre: [claves visibles]}"""
        super().__init__(parent)
        self.setWindowTitle(tr("Configurar barras de herramientas"))
        self.resize(760, 560)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        self.lists = {}
        for name, keys in toolbars.items():
            box = QGroupBox(tr(name))
            bl = QVBoxLayout(box)
            lw = QListWidget()
            for k in keys:
                if k == "|":
                    continue
                a = actions.get(k)
                it = QListWidgetItem(a.icon() if a else QIcon(), a.text().replace("&", "") if a else k)
                it.setData(Qt.ItemDataRole.UserRole, k)
                it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                it.setCheckState(Qt.CheckState.Checked if k in current.get(name, keys) else Qt.CheckState.Unchecked)
                lw.addItem(it)
            bl.addWidget(lw)
            self.lists[name] = lw
            h.addWidget(box)
        v.addLayout(h)
        v.addWidget(_buttons(self))

    def result(self):
        out = {}
        for name, lw in self.lists.items():
            out[name] = [lw.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lw.count())
                         if lw.item(i).checkState() == Qt.CheckState.Checked]
        return out


# ======================================================================= PNG
AUTO_DIM_CHOICES = [("off", N_("Sin cotas automáticas")), ("size_all", N_("Tamaño de todos · posición de la selección")),
                    ("all", N_("Tamaño y posición de todos")), ("selection", N_("Sólo de la selección"))]


class ImageExportDialog(QDialog):
    def __init__(self, parent, user_dims: bool = True, auto_mode: str = "off", has_selection: bool = False):
        super().__init__(parent)
        self.setWindowTitle(tr("Exportar PNG"))
        f = QFormLayout(self)
        self.dpi = QSpinBox()
        self.dpi.setRange(50, 2400)
        self.dpi.setValue(300)
        self.dpi.setSuffix(" ppp")
        self.mode = QComboBox()
        self.mode.addItem(tr("Aspecto realista"), "visual")
        self.mode.addItem(tr("Plano de fabricación"), "fab")
        self.dims = QCheckBox(tr("Incluir cotas de usuario"))
        self.dims.setChecked(user_dims)
        self.auto = QComboBox()
        for key, label in AUTO_DIM_CHOICES:
            self.auto.addItem(tr(label), key)
        self.auto.setCurrentIndex(max(0, self.auto.findData(auto_mode)))
        self.auto.setToolTip(tr("Las mismas cotas automáticas que se ven en el lienzo junto a cada elemento"))
        self.transp = QCheckBox(tr("Fondo transparente"))
        f.addRow(tr("Resolución"), self.dpi)
        f.addRow(tr("Estilo"), self.mode)
        f.addRow(self.dims)
        f.addRow(tr("Cotas automáticas"), self.auto)
        if not has_selection:
            hint = QLabel(tr("No hay nada seleccionado: las cotas «de la selección» no aparecerán."))
            hint.setProperty("role", "hint")
            hint.setWordWrap(True)
            f.addRow(hint)
        f.addRow(self.transp)
        f.addRow(_buttons(self))


# ======================================================================= acerca de
class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(tr("Acerca de {app}").format(app=APP_NAME))
        h = QHBoxLayout(self)
        logo = QLabel()
        logo.setPixmap(icons.app_pixmap(160))
        logo.setAlignment(Qt.AlignmentFlag.AlignTop)
        h.addWidget(logo)
        v = QVBoxLayout()
        t = QLabel(f"<h2 style='margin:0'>{APP_NAME}</h2><p>{tr('Versión')} {__version__}</p>"
                   f"<p>{tr('Diseño de paneles frontales y traseros para equipos electrónicos.')}</p>"
                   f"<p>Python · PySide6 (Qt 6)</p>"
                   f"<p><i>{tr('Las medidas de la biblioteca son orientativas: verifique siempre con las hojas de datos de los fabricantes antes de mecanizar.')}</i></p>")
        t.setWordWrap(True)
        t.setMinimumWidth(360)
        v.addWidget(t)
        v.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText(tr("Cerrar"))
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        v.addWidget(bb)
        h.addLayout(v)
