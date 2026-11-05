"""Diálogos de Texto y Generador de escalas (con vista previa en vivo)."""
from __future__ import annotations

import copy

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFontComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget)

from ..core import geometry as G
from ..core.expr import ExprError, is_expr, parse_number
from ..core.scale import GROUPS, PRESETS, ScaleEntity
from ..core.entities import TextEntity
from ..i18n import N_, tr
from . import render
from .properties import OPTION_LABELS
from .safepaint import safe_paint


# ======================================================================= campos
class ColorField(QWidget):
    changed = Signal()

    def __init__(self, value: str, default_label: str):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.btn = QPushButton()
        self.btn.clicked.connect(self._pick)
        self.reset = QPushButton(default_label)
        self.reset.setToolTip(tr("Usar el color de serigrafía del panel"))
        self.reset.clicked.connect(lambda: self.set_value(""))
        h.addWidget(self.btn, 1)
        h.addWidget(self.reset)
        self.set_value(value or "", emit=False)

    def set_value(self, v, emit=True):
        self.value = v or ""
        if self.value:
            c = QColor(self.value)
            fg = "#000" if c.lightness() > 128 else "#fff"
            self.btn.setText(self.value)
            self.btn.setStyleSheet(f"QPushButton {{ background: {self.value}; color: {fg}; }}")
        else:
            self.btn.setText(tr("Color del panel"))
            self.btn.setStyleSheet("")
        if emit:
            self.changed.emit()

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.value or "#111111"), self, tr("Color"))
        if c.isValid():
            self.set_value(c.name())


class ParamForm(QWidget):
    """Formulario genérico a partir de los Field de una entidad."""
    changed = Signal()

    def __init__(self, fields, values: dict, groups=None):
        super().__init__()
        self.fields = {f.name: f for f in fields}
        self.widgets = {}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        groups = groups or [("", [f.name for f in fields])]
        for title, names in groups:
            box = QGroupBox(tr(title)) if title else QWidget()
            form = QFormLayout(box)
            for n in names:
                f = self.fields.get(n)
                if f is None:
                    continue
                w = self._widget(f, values.get(n, f.default))
                self.widgets[n] = w
                lab = QLabel(tr(f.label))
                if f.tip:
                    lab.setToolTip(tr(f.tip))
                    w.setToolTip(tr(f.tip))
                form.addRow(lab, w)
            v.addWidget(box)
        v.addStretch(1)

    def _widget(self, f, raw):
        # Las señales de Qt pasan su valor (float, int, bool, str…); changed no lleva argumentos.
        emit = lambda *_args: self.changed.emit()  # noqa: E731
        if f.kind == "num":
            if is_expr(raw):
                w = QLineEdit(str(raw))
                w.textChanged.connect(emit)
                return w
            w = QDoubleSpinBox()
            w.setRange(-100000, 100000)
            w.setDecimals(2)
            w.setSingleStep(0.5 if "(°)" not in f.label else 5.0)
            try:
                w.setValue(float(raw or 0))
            except (TypeError, ValueError):
                w.setValue(0.0)
            w.valueChanged.connect(emit)
            return w
        if f.kind == "int":
            w = QSpinBox()
            w.setRange(0, 1000)
            w.setValue(int(raw or 0))
            w.valueChanged.connect(emit)
            return w
        if f.kind == "choice":
            w = QComboBox()
            for o in f.options:
                w.addItem(tr(OPTION_LABELS.get(o, o)), o)
            w.setCurrentIndex(max(0, w.findData(raw)))
            w.currentIndexChanged.connect(emit)
            return w
        if f.kind == "bool":
            w = QCheckBox()
            w.setChecked(bool(raw))
            w.toggled.connect(emit)
            return w
        if f.kind == "font":
            w = QFontComboBox()
            if raw:
                w.setCurrentFont(QFont(str(raw)))
            w.currentFontChanged.connect(emit)
            return w
        if f.kind == "color":
            w = ColorField(raw, tr("Por defecto"))
            w.changed.connect(emit)
            return w
        w = QLineEdit(str(raw))
        w.textChanged.connect(emit)
        return w

    def set_values(self, values: dict):
        for n, raw in values.items():
            w = self.widgets.get(n)
            if w is None:
                continue
            w.blockSignals(True)
            if isinstance(w, QDoubleSpinBox):
                try:
                    w.setValue(float(raw))
                except (TypeError, ValueError):
                    pass
            elif isinstance(w, QSpinBox):
                w.setValue(int(raw))
            elif isinstance(w, QComboBox) and not isinstance(w, QFontComboBox):
                w.setCurrentIndex(max(0, w.findData(raw)))
            elif isinstance(w, QCheckBox):
                w.setChecked(bool(raw))
            elif isinstance(w, QFontComboBox):
                w.setCurrentFont(QFont(str(raw)))
            elif isinstance(w, ColorField):
                w.set_value(raw, emit=False)
            elif isinstance(w, QLineEdit):
                w.setText(str(raw))
            w.blockSignals(False)
        self.changed.emit()

    def values(self) -> dict:
        out = {}
        for n, w in self.widgets.items():
            if isinstance(w, QDoubleSpinBox):
                out[n] = round(w.value(), 6)
            elif isinstance(w, QSpinBox):
                out[n] = w.value()
            elif isinstance(w, QFontComboBox):
                out[n] = w.currentFont().family()
            elif isinstance(w, QComboBox):
                out[n] = w.currentData()
            elif isinstance(w, QCheckBox):
                out[n] = w.isChecked()
            elif isinstance(w, ColorField):
                out[n] = w.value
            elif isinstance(w, QLineEdit):
                if self.fields[n].kind == "num":
                    try:
                        out[n] = parse_number(w.text())
                    except ExprError:
                        continue
                else:
                    out[n] = w.text()
        return out


# ======================================================================= vista previa
class EntityPreview(QWidget):
    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        self.entity = None
        self._view = None  # (x0, y0, x1, y1) en mm; fijo para que se aprecien los cambios de tamaño
        self.setMinimumSize(360, 300)
        self.setToolTip(tr("Doble clic: ajustar la vista"))

    def set_entity(self, e):
        self.entity = e
        self.update()

    def fit(self):
        self._view = None
        self.update()

    def mouseDoubleClickEvent(self, _e):
        self.fit()

    @safe_paint
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#2a2e35"))
        if self.entity is None:
            p.end()
            return
        ev = self.doc.evaluator()
        items = []
        try:
            e2 = self.entity.clone()
            e2.p["x"], e2.p["y"] = 0.0, 0.0
            for role, pr in e2.geometry(self.doc, ev):
                if pr["t"] == "text":
                    items += [(role, q) for q in render.text_prim_polys(pr)]
                else:
                    items.append((role, pr))
        except Exception as ex:  # noqa: BLE001 - valores intermedios inválidos mientras se escribe
            p.setPen(QColor("#ff6b6b"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(ex))
            p.end()
            return
        b = None
        for _r, pr in items:
            b = G.bbox_union(b, G.prim_bbox(pr))
        if b is None:
            p.end()
            return
        bw, bh = max(1.0, b[2] - b[0]), max(1.0, b[3] - b[1])
        v = self._view
        inside = v is not None and b[0] >= v[0] and b[1] >= v[1] and b[2] <= v[2] and b[3] <= v[3]
        tiny = v is not None and max(bw / (v[2] - v[0]), bh / (v[3] - v[1])) < 0.2
        if v is None or not inside or tiny:
            m = 0.3 * max(bw, bh) + 2.0
            v = self._view = (b[0] - m, b[1] - m, b[2] + m, b[3] + m)
        vw, vh = v[2] - v[0], v[3] - v[1]
        s = min((self.width() - 10) / vw, (self.height() - 24) / vh)
        p.save()
        p.translate(self.width() / 2 - (v[0] + v[2]) / 2 * s, (self.height() - 18) / 2 + (v[1] + v[3]) / 2 * s)
        p.scale(s, -s)
        plate = QRectF(v[0], v[1], vw, vh)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(self.doc.panel.color)))
        p.drawRect(plate)
        # cuadrícula en mm
        step = 1.0
        for cand in (1.0, 2.0, 5.0, 10.0, 20.0, 50.0):
            step = cand
            if cand * s >= 12:
                break
        import math as _m
        gp = QPen(QColor(0, 0, 0, 28), 1)
        gp.setCosmetic(True)
        gp5 = QPen(QColor(0, 0, 0, 60), 1)
        gp5.setCosmetic(True)
        i0, i1 = int(_m.floor(v[0] / step)), int(_m.ceil(v[2] / step))
        for i in range(i0, i1 + 1):
            p.setPen(gp5 if i % 5 == 0 else gp)
            p.drawLine(QPointF(i * step, v[1]), QPointF(i * step, v[3]))
        j0, j1 = int(_m.floor(v[1] / step)), int(_m.ceil(v[3] / step))
        for j in range(j0, j1 + 1):
            p.setPen(gp5 if j % 5 == 0 else gp)
            p.drawLine(QPointF(v[0], j * step), QPointF(v[2], j * step))
        self._grid_step = step
        default = QColor(self.doc.panel.print_color)
        cols = sorted({pr.get("color") or "" for r, pr in items if r == "main"})
        for col in cols:
            closed, opened = QPainterPath(), QPainterPath()
            closed.setFillRule(Qt.FillRule.OddEvenFill)
            for r, pr in items:
                if r != "main" or (pr.get("color") or "") != col:
                    continue
                is_closed = pr["t"] == "circle" or pr.get("closed", True)
                render.add_prim(closed if is_closed else opened, pr)
            c = QColor(col) if col else default
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(c))
            p.drawPath(closed)
            pn = QPen(c, 1.5)
            pn.setCosmetic(True)
            pn.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pn)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(opened)
        refp = QPainterPath()
        for r, pr in items:
            if r == "ref":
                render.add_prim(refp, pr)
        pn = QPen(QColor("#e5484d"), 1.2)
        pn.setCosmetic(True)
        p.setPen(pn)
        p.drawPath(refp)
        p.restore()
        f = QFont()
        f.setPointSize(8)
        p.setFont(f)
        p.setPen(QColor("#c0c6ce"))
        p.drawText(QPointF(8, self.height() - 6), f"{bw:.1f} × {bh:.1f} mm   ·   "
                   + tr("cuadrícula {g} mm").format(g=f"{getattr(self, '_grid_step', 1.0):g}")
                   + "   ·   " + tr("doble clic: ajustar"))
        p.end()


def _buttons(dlg):
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Aceptar"))
    bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


def _layer_combo(doc, current, processes=("print", "engrave")):
    co = QComboBox()
    for L in doc.layers:
        if L.process in processes:
            co.addItem(L.name, L.id)
    idx = co.findData(current)
    co.setCurrentIndex(idx if idx >= 0 else 0)
    return co


# ======================================================================= texto
class TextDialog(QDialog):
    TEXT_GROUPS = [(N_("Fuente"), ["font", "size", "weight", "italic", "underline", "strike", "upper", "color"]),
                   (N_("Disposición"), ["align", "sx", "spacing", "line", "rot"])]

    def __init__(self, parent, doc, entity: TextEntity | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Texto") if entity is None else tr("Editar texto"))
        self.resize(900, 560)
        self.doc = doc
        self.proto = entity.clone(keep_id=True) if entity is not None else TextEntity(text=tr("Texto"))
        v = QVBoxLayout(self)
        sp = QSplitter()
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel(tr("Texto (varias líneas permitidas):")))
        self.text = QPlainTextEdit(str(self.proto.p.get("text", "")))
        self.text.setMaximumHeight(90)
        self.text.textChanged.connect(self._update)
        lv.addWidget(self.text)
        row = QFormLayout()
        self.layer = _layer_combo(doc, self.proto.layer)
        row.addRow(tr("Capa"), self.layer)
        lv.addLayout(row)
        p = dict(self.proto.p)
        if p.get("weight", "normal") == "normal" and p.get("bold"):
            p["weight"] = "negrita"
        self.form = ParamForm(self.proto.all_fields(), p, self.TEXT_GROUPS)
        self.form.changed.connect(self._update)
        lv.addWidget(self.form, 1)
        sp.addWidget(left)
        self.preview = EntityPreview(doc)
        sp.addWidget(self.preview)
        sp.setSizes([420, 480])
        v.addWidget(sp, 1)
        v.addWidget(_buttons(self))
        self._update()

    def _update(self):
        self.proto.p.update(self.form.values())
        self.proto.p["text"] = self.text.toPlainText()
        self.proto.p.pop("bold", None)
        self.preview.set_entity(self.proto)

    def result_params(self):
        self._update()
        return copy.deepcopy(self.proto.p), self.layer.currentData()


# ======================================================================= escalas
class ScaleDialog(QDialog):
    def __init__(self, parent, doc, entity: ScaleEntity | None = None, hint: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Generador de escalas"))
        self.resize(1000, 700)
        self.doc = doc
        self.proto = entity.clone(keep_id=True) if entity is not None else ScaleEntity()
        if entity is None and hint:
            self.proto.p.update(hint)
        v = QVBoxLayout(self)
        sp = QSplitter()
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        top = QFormLayout()
        self.preset = QComboBox()
        self.preset.addItem(tr("— elegir plantilla —"), None)
        for name in PRESETS:
            self.preset.addItem(tr(name), name)
        self.preset.activated.connect(self._apply_preset)
        top.addRow(tr("Plantilla"), self.preset)
        self.layer = _layer_combo(doc, self.proto.layer)
        top.addRow(tr("Capa"), self.layer)
        lv.addLayout(top)
        hint_lab = QLabel(tr("Ángulos: 0° = izquierda (9 en punto), sentido horario; 90° = arriba. "
                             "Un potenciómetro de 300° va de -60° a 240°."))
        hint_lab.setWordWrap(True)
        hint_lab.setProperty("role", "hint")
        lv.addWidget(hint_lab)
        self.form = ParamForm(self.proto.all_fields(), self.proto.p, GROUPS)
        self.form.changed.connect(self._update)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        lv.addWidget(scroll, 1)
        sp.addWidget(left)
        self.preview = EntityPreview(doc)
        sp.addWidget(self.preview)
        sp.setSizes([430, 570])
        v.addWidget(sp, 1)
        v.addWidget(_buttons(self))
        self._update()

    def _apply_preset(self, _i):
        name = self.preset.currentData()
        if not name:
            return
        base = ScaleEntity().p
        keep = {k: self.proto.p.get(k) for k in ("x", "y", "name", "color", "font")}
        vals = {k: base[k] for k in base if k not in keep}
        vals.update(PRESETS[name])
        self.form.set_values(vals)
        self.preview.fit()

    def _update(self):
        self.proto.p.update(self.form.values())
        self.preview.set_entity(self.proto)

    def result_params(self):
        self._update()
        return copy.deepcopy(self.proto.p), self.layer.currentData()
