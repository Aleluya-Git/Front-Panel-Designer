"""Panel lateral de propiedades (entidad, selección múltiple o panel)."""
from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFontComboBox, QFormLayout, QGridLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
                               QToolButton, QVBoxLayout, QWidget)

from ..core.document import FINISHES, MATERIALS, PRESETS
from ..core.expr import ExprError, is_expr, parse_number
from ..i18n import N_, tr
from . import icons

PROP_GROUPS = [("posicion", N_("Posición")), ("tamano", N_("Tamaño")), ("caracteristicas", N_("Características")),
               ("opciones", N_("Opciones"))]
SIZE_FIELDS = {"w", "h", "d", "r", "l", "n", "radius", "length", "size", "sx", "depth", "scale", "flat", "csk_d",
               "label_size", "len_major", "len_minor", "mark_w", "dot_major", "dot_minor", "ref_w", "text_size",
               "spacing", "line", "csk_angle"}


def field_group(fld) -> str:
    if fld.group:
        return fld.group
    if fld.name in ("x", "y", "rot"):
        return "posicion"
    if fld.kind == "bool":
        return "opciones"
    if fld.name in SIZE_FIELDS:
        return "tamano"
    return "caracteristicas"


# Etiquetas visibles para opciones cuyo valor interno es un código
OPTION_LABELS = {"rect": N_("Rectangular"), "circle": N_("Circular"), "oval": N_("Ovalada"),
                 "h": N_("Horizontal"), "v": N_("Vertical"), "a": N_("Alineada"),
                 "0": "0°", "45": "45°", "90": "90°", "135": "135°", "180": "180°",
                 "tangente": N_("Tangente (sigue el arco)")}


def _fmt(raw):
    if raw is None:
        return ""
    if isinstance(raw, float):
        return f"{raw:.4f}".rstrip("0").rstrip(".")
    return str(raw)


def _polish(w):
    w.style().unpolish(w)
    w.style().polish(w)


class NumEdit(QLineEdit):
    """Campo numérico que admite expresiones ('=W/2')."""

    def __init__(self, raw, on_commit, evaluator_fn):
        super().__init__(_fmt(raw))
        self.on_commit = on_commit
        self.evaluator_fn = evaluator_fn
        self.editingFinished.connect(self._commit)
        self._last = self.text()
        self._tip(raw)

    def _tip(self, raw):
        if is_expr(raw):
            try:
                v = self.evaluator_fn().value(raw)
                self.setToolTip(f"{raw}  →  {v:.4f} mm")
            except (ExprError, ZeroDivisionError, ValueError) as e:
                self.setToolTip(str(e))
            self.setStyleSheet("font-style: italic;")
        else:
            self.setToolTip(tr("Número o expresión (p. ej. =W/2, =margen+5)"))
            self.setStyleSheet("")

    def _commit(self):
        if self.text() == self._last:
            return
        try:
            raw = parse_number(self.text())
            if is_expr(raw):
                self.evaluator_fn().value(raw)
        except (ExprError, ZeroDivisionError, ValueError) as e:
            self.setProperty("error", True)
            self.setToolTip(str(e))
            _polish(self)
            return
        self.setProperty("error", False)
        _polish(self)
        self._last = self.text()
        self._tip(raw)
        self.on_commit(raw)


class ColorButton(QPushButton):
    def __init__(self, color, on_change):
        super().__init__()
        self.on_change = on_change
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, c):
        self.color = c
        self.setText(c)
        self.setStyleSheet(f"QPushButton {{ background: {c}; color: {'#000' if QColor(c).lightness() > 128 else '#fff'}; }}")

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self, tr("Color"))
        if c.isValid():
            self.set_color(c.name())
            self.on_change(c.name())


class PropertiesPanel(QScrollArea):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        self.setWidgetResizable(True)
        self.setMinimumWidth(280)
        self._build()

    @property
    def doc(self):
        return self.mw.doc

    def _set(self, label, fn):
        self.mw.checkpoint(label)
        fn()
        self.mw.changed()

    def _build(self):
        w = QWidget()
        self.v = QVBoxLayout(w)
        self.v.setContentsMargins(8, 8, 8, 8)
        self.setWidget(w)

    def refresh(self):
        old = self.takeWidget()  # se libera después: puede estar emitiendo la señal que nos llama
        if old is not None:
            old.hide()
            old.deleteLater()
        self._build()
        sel = [self.doc.get(i) for i in self.mw.canvas.selected]
        sel = [e for e in sel if e is not None]
        if not sel:
            self._panel_form()
        elif len(sel) == 1:
            self._entity_form(sel[0])
        else:
            self._multi_form(sel)
        self.v.addStretch(1)

    def _title(self, text):
        t = QLabel(text)
        t.setProperty("role", "title")
        self.v.addWidget(t)

    def _hint(self, text):
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setProperty("role", "hint")
        self.v.addWidget(lab)

    # ------------------------------------------------------------ panel
    def _panel_form(self):
        p = self.doc.panel
        self._title(tr("Panel"))
        f = QFormLayout()
        title = QLineEdit(str(self.doc.meta.get("title", "")))
        title.editingFinished.connect(lambda: self._set(tr("Título"), lambda: self.doc.meta.__setitem__("title", title.text())))
        f.addRow(tr("Título"), title)
        preset = QComboBox()
        for name in PRESETS:
            preset.addItem(tr(name), name)
        preset.setCurrentIndex(max(0, preset.findData(p.preset)))
        btn = QPushButton(tr("Aplicar"))
        btn.setToolTip(tr("Ajusta el tamaño y añade los taladros de fijación estándar"))
        btn.clicked.connect(lambda: self.mw.apply_preset(preset.currentData()))
        row = QHBoxLayout()
        row.addWidget(preset, 1)
        row.addWidget(btn)
        f.addRow(tr("Plantilla"), row)
        for attr, label in (("w", tr("Ancho (W)")), ("h", tr("Alto (H)")), ("t", tr("Espesor (T)")),
                            ("r", tr("Radio esquinas"))):
            ed = NumEdit(getattr(p, attr), lambda raw, a=attr: self._set(tr("Panel: {a}").format(a=a),
                                                                         lambda: setattr(p, a, raw)),
                         self.doc.evaluator)
            f.addRow(label, ed)
        mat = QComboBox()
        for m in MATERIALS:
            mat.addItem(tr(m), m)
        mat.setCurrentIndex(max(0, mat.findData(p.material)))

        def set_mat(_i):
            m = mat.currentData()

            def fn():
                p.material = m
                p.color = MATERIALS[m]["color"]
                if m == "Metacrilato":
                    p.finish = "Transparente"
            self._set(tr("Material"), fn)
            self.refresh()
        mat.currentIndexChanged.connect(set_mat)
        f.addRow(tr("Material"), mat)
        if p.material == "Personalizado":
            mn = QLineEdit(p.material_name)
            mn.editingFinished.connect(lambda: self._set(tr("Material"), lambda: setattr(p, "material_name", mn.text())))
            f.addRow(tr("Nombre material"), mn)
        tsel = QComboBox()
        tsel.setEditable(True)
        tsel.addItems(["1.0", "1.5", "2.0", "2.5", "3.0", "4.0", "5.0", "6.0"])
        tsel.setCurrentText(_fmt(p.t))
        tsel.setToolTip(tr("Espesores habituales; también puede escribir una expresión en 'Espesor (T)'"))

        def set_t(_i):
            try:
                val = float(tsel.currentText().replace(",", "."))
            except ValueError:
                return
            self._set(tr("Espesor"), lambda: setattr(p, "t", val))
            self.refresh()
        tsel.activated.connect(set_t)
        f.addRow(tr("Espesor habitual"), tsel)
        fin = QComboBox()
        for x in FINISHES:
            fin.addItem(tr(x), x)
        fin.setCurrentIndex(max(0, fin.findData(p.finish)))
        fin.currentIndexChanged.connect(lambda _i: self._set(tr("Acabado"), lambda: setattr(p, "finish", fin.currentData())))
        f.addRow(tr("Acabado"), fin)
        f.addRow(tr("Color panel"), ColorButton(p.color, lambda c: self._set(tr("Color"), lambda: setattr(p, "color", c))))
        f.addRow(tr("Color serigrafía"), ColorButton(p.print_color,
                                                    lambda c: self._set(tr("Color"), lambda: setattr(p, "print_color", c))))
        self.v.addLayout(f)
        ev = self.doc.evaluator()
        W, H, T, _r = self.doc.panel_dims(ev)
        self._hint(tr("{w} × {h} × {t} mm · {n} entidades").format(w=f"{W:.2f}", h=f"{H:.2f}", t=f"{T:.2f}",
                                                                   n=len(self.doc.entities)))
        self._hint(tr("Consejo: los campos numéricos admiten expresiones con variables, p. ej. <b>=W/2</b>."))

    # ------------------------------------------------------------ entidad
    def _entity_form(self, e):
        self._title(tr(e.LABEL))
        boxes = {}
        for key, title in PROP_GROUPS:
            box = QGroupBox(tr(title))
            boxes[key] = (box, QFormLayout(box))
        car = boxes["caracteristicas"][1]
        lay = QComboBox()
        for L in self.doc.layers:
            lay.addItem(L.name, L.id)
        lay.setCurrentIndex(max(0, lay.findData(e.layer)))
        lay.currentIndexChanged.connect(lambda _i: self._set(tr("Cambiar capa"), lambda: setattr(e, "layer", lay.currentData())))
        car.addRow(tr("Capa"), lay)
        lk = QCheckBox(tr("Bloqueada"))
        lk.setChecked(e.locked)
        lk.toggled.connect(lambda v: self._set(tr("Bloquear"), lambda: setattr(e, "locked", v)))
        boxes["opciones"][1].addRow(lk)
        for fld in e.all_fields():
            wdg = self._field_widget(e, fld)
            if wdg is None:
                continue
            if fld.tip:
                wdg.setToolTip(tr(fld.tip))
            form = boxes[field_group(fld)][1]
            if fld.kind == "bool":
                wdg.setText(tr(fld.label))
                form.addRow(wdg)
            else:
                form.addRow(tr(fld.label), wdg)
        for key, _t in PROP_GROUPS:
            box, form = boxes[key]
            if form.rowCount():
                self.v.addWidget(box)
        ev = self.doc.evaluator()
        if e.TYPE == "component":
            comp = e.p.get("comp", {})
            from ..core.library import comp_name
            self._hint(f"<b>{comp_name(comp)}</b><br>{comp.get('description', '')}<br>"
                       f"<i>{tr('Verifique las medidas con la hoja de datos del fabricante.')}</i>")
            b = QPushButton(tr("Editar definición de este componente…"))
            b.clicked.connect(lambda: self.mw.edit_instance_component(e))
            self.v.addWidget(b)
            b2 = QPushButton(tr("Guardar en una biblioteca…"))
            b2.clicked.connect(lambda: self.mw.save_instance_to_library(e))
            self.v.addWidget(b2)
        if e.TYPE == "text":
            b = QPushButton(tr("Editar texto…"))
            b.clicked.connect(lambda: self.mw.edit_text(e))
            self.v.addWidget(b)
        if e.TYPE == "stud":
            b = QPushButton(tr("Editar perno / casquillo…"))
            b.clicked.connect(lambda: self.mw.edit_stud(e))
            self.v.addWidget(b)
            d = e.data()
            self._hint(tr("Agujero Ø{h} mm · cabeza Ø{c} mm · espesor mínimo de panel {m} mm").format(
                h=f"{d['hole']:.2f}", c=f"{d['head']:.2f}", m=d["min_t"]))
        if e.TYPE == "scale":
            b = QPushButton(tr("Abrir el generador de escalas…"))
            b.clicked.connect(lambda: self.mw.edit_scale(e))
            self.v.addWidget(b)
        if e.TYPE == "hole":
            d, nom = e.diameters(ev)
            txt = tr("Taladro Ø{d} mm").format(d=f"{d:.2f}")
            if abs(nom - d) > 1e-6:
                txt += " · " + tr("nominal/cabeza Ø{d}").format(d=f"{nom:.2f}")
            self._hint(txt)
        if e.TYPE == "dimension":
            self._hint(tr("Medida: {m} mm · A: {a} · B: {b}").format(
                m=f"{e.measure(self.doc, ev):.3f}", a=self._anchor_txt(e.p.get("a")), b=self._anchor_txt(e.p.get("b"))))
        if e.HAS_POS:
            b = e.bbox(self.doc, ev)
            self._hint(tr("Tamaño {w} × {h} mm").format(w=f"{b[2] - b[0]:.2f}", h=f"{b[3] - b[1]:.2f}"))

    def _anchor_txt(self, an):
        an = an or {}
        if "xy" in an:
            return f"({an['xy'][0]:.2f}, {an['xy'][1]:.2f})"
        if an.get("ref") == "panel":
            return f"{tr('panel')}/{an.get('anchor')}"
        e = self.doc.get(an.get("ref", ""))
        return f"«{e.display_name()}»" if e else "?"

    def _field_widget(self, e, fld):
        name, kind = fld.name, fld.kind
        raw = e.p.get(name, fld.default)

        def setter(v, n=name):
            self._set(tr("Cambiar {p}").format(p=tr(fld.label).lower()), lambda: e.p.__setitem__(n, v))
        if kind == "num":
            return NumEdit(raw, setter, self.doc.evaluator)
        if kind == "int":
            sp = QSpinBox()
            sp.setRange(0, 1000)
            sp.setValue(int(raw or 0))
            sp.editingFinished.connect(lambda: sp.value() != raw and setter(sp.value()))
            return sp
        if kind == "str":
            le = QLineEdit(str(raw).replace("\n", "\\n"))
            le.editingFinished.connect(lambda: str(raw) != le.text().replace("\\n", "\n")
                                       and setter(le.text().replace("\\n", "\n")))
            if name == "text":
                le.setToolTip(tr("Use \\n para saltos de línea"))
            return le
        if kind == "bool":
            cb = QCheckBox()
            cb.setChecked(bool(raw))
            cb.toggled.connect(setter)
            return cb
        if kind == "choice":
            co = QComboBox()
            for opt in fld.options:
                co.addItem(tr(OPTION_LABELS.get(opt, opt)), opt)
            co.setCurrentIndex(max(0, co.findData(raw)))
            co.currentIndexChanged.connect(lambda _i: (setter(co.currentData()), self.refresh()))
            return co
        if kind == "color":
            from .textscale import ColorField
            cf = ColorField(raw, tr("Por defecto"))
            cf.changed.connect(lambda: setter(cf.value))
            return cf
        if kind == "font":
            fc = QFontComboBox()
            fc.setCurrentText(str(raw))
            fc.currentTextChanged.connect(setter)
            return fc
        if kind == "pts":
            le = QLineEdit("; ".join(f"{a:g},{b:g}" for a, b in (raw or [])))

            def commit():
                try:
                    pts = [[float(c) for c in pair.split(",")] for pair in le.text().split(";") if pair.strip()]
                    if all(len(p) == 2 for p in pts):
                        setter(pts)
                except ValueError:
                    le.setProperty("error", True)
                    _polish(le)
            le.editingFinished.connect(commit)
            le.setToolTip(tr("Vértices locales respecto a X/Y: x1,y1; x2,y2; ..."))
            return le
        if kind == "readonly":
            if name in ("comp", "a", "b"):
                return None
            if name == "paths":
                return QLabel(tr("{n} trazos").format(n=len(raw or [])))
            if name == "data":
                return QLabel(f"{len(raw or '') * 3 // 4 // 1024} KB" if raw else "—")
            return QLabel(_fmt(raw) or "—")
        return None

    # ------------------------------------------------------------ múltiple
    def _multi_form(self, sel):
        self._title(tr("{n} entidades seleccionadas").format(n=len(sel)))
        f = QFormLayout()
        lay = QComboBox()
        lay.addItem(tr("— sin cambios —"), None)
        for L in self.doc.layers:
            lay.addItem(L.name, L.id)

        def set_layer(_i):
            lid = lay.currentData()
            if lid:
                self._set(tr("Cambiar capa"), lambda: [setattr(e, "layer", lid) for e in sel])
        lay.currentIndexChanged.connect(set_layer)
        f.addRow(tr("Capa"), lay)
        self.v.addLayout(f)
        grid = QGridLayout()
        acts = [("align_left", tr("Alinear a la izquierda")), ("align_hcenter", tr("Centrar horizontalmente")),
                ("align_right", tr("Alinear a la derecha")), ("align_top", tr("Alinear arriba")),
                ("align_vcenter", tr("Centrar verticalmente")), ("align_bottom", tr("Alinear abajo")),
                ("dist_h", tr("Distribuir horizontalmente")), ("dist_v", tr("Distribuir verticalmente")),
                ("dist_panel", tr("Distribución automática en el panel (vinculada)"))]
        from PySide6.QtCore import QSize
        for i, (key, tip) in enumerate(acts):
            b = QToolButton()
            b.setIcon(icons.icon(key, self.mw.colors["text"]))
            b.setIconSize(QSize(30, 30))
            b.setToolTip(tip)
            b.clicked.connect(lambda _c=False, k=key: self.mw.run_layout(k))
            grid.addWidget(b, i // 3, i % 3)
        self.v.addLayout(grid)
        b = QPushButton(tr("Medir entre las dos primeras"))
        b.setEnabled(len(sel) >= 2)
        b.clicked.connect(self.mw.measure_selection)
        self.v.addWidget(b)
        b2 = QPushButton(tr("Guardar como componente…"))
        b2.clicked.connect(self.mw.component_from_selection)
        self.v.addWidget(b2)
        self._hint(tr("Las propiedades individuales se editan seleccionando una sola entidad."))
