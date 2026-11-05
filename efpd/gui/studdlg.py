"""Diálogo «Propiedades del perno / casquillo roscado» con corte en sección acotado."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from ..core.stud import KINDS, LENGTHS, THREADS, StudEntity
from ..i18n import tr
from .safepaint import safe_paint


class StudSection(QWidget):
    """Corte en sección: panel, agujero y elemento, con las medidas principales."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 420)
        self.e = None
        self.T = 2.0

    def set_state(self, e: StudEntity, T: float):
        self.e, self.T = e, T
        self.update()

    @safe_paint
    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        if self.e is None:
            p.end()
            return
        d = self.e.data()
        L = float(self.e.p.get("length", 6) or 6)
        T = self.T
        rev = bool(self.e.p.get("reverse", True))
        off = float(self.e.p.get("depth_offset", 0) or 0)
        blind = rev and off > 1e-6
        casq = self.e.p.get("kind") == "casquillo"
        total_h = T + L + d["head_h"] + 6
        total_w = max(d["head"], d["body"]) * 3.2
        s = min((self.width() - 40) / total_w, (self.height() - 90) / total_h)
        cx = self.width() / 2
        # el frente del panel está arriba; si el elemento va delante se dibuja invertido
        top = 40 + (d["head_h"] + 2) * s if rev else 40 + (L + 2) * s
        y_front, y_back = top, top + T * s
        ink = QPen(QColor("#111111"), 1.6)
        thin = QPen(QColor("#444444"), 1)
        dash = QPen(QColor("#444444"), 1, Qt.PenStyle.DashLine)
        p.setFont(QFont(p.font().family(), 9))
        # panel con agujero
        hole_r = d["hole"] / 2 * s
        panel_col = QColor("#c9cdd2")
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(panel_col))
        p.drawRect(QRectF(10, y_front, self.width() - 20, T * s))
        p.setBrush(QBrush(QColor("#ffffff")))
        if blind:
            depth = max(0.05, T - off) * s
            p.drawRect(QRectF(cx - hole_r, y_back - depth, 2 * hole_r, depth))
        else:
            p.drawRect(QRectF(cx - hole_r, y_front, 2 * hole_r, T * s))
        p.setPen(ink)
        p.drawLine(QPointF(10, y_front), QPointF(self.width() - 10, y_front))
        p.drawLine(QPointF(10, y_back), QPointF(self.width() - 10, y_back))
        p.setPen(QColor("#666666"))
        p.drawText(QPointF(14, y_front - 4), tr("Frente"))
        p.drawText(QPointF(14, y_back + 14), tr("Reverso"))
        # elemento
        body_r = d["body"] / 2 * s
        head_r = d["head"] / 2 * s
        hh = d["head_h"] * s
        sign = 1 if rev else -1
        base = y_back if rev else y_front           # cara por la que sobresale
        far = y_front if rev else y_back            # cara opuesta (cabeza)
        p.setPen(ink)
        p.setBrush(QBrush(QColor("#e8eaed")))
        if blind:
            # el cuello entra en el agujero ciego desde el reverso
            depth_px = max(0.05, T - off) * s
            p.drawRect(QRectF(cx - min(body_r, hole_r), base - depth_px, 2 * min(body_r, hole_r), depth_px))
            p.drawRect(QRectF(cx - body_r, base, 2 * body_r, L * s))
        else:
            p.drawRect(QRectF(cx - head_r, far - sign * hh, 2 * head_r, sign * hh))
            p.drawRect(QRectF(cx - body_r, far, 2 * body_r, (base - far) + sign * L * s))
        # rosca
        p.setPen(dash)
        p.setBrush(Qt.BrushStyle.NoBrush)
        tr_r = float(self.e.p.get("thread", "M3")[1:]) / 2 * s
        end = base + sign * L * s
        if casq:
            p.drawLine(QPointF(cx - tr_r, base), QPointF(cx - tr_r, end))
            p.drawLine(QPointF(cx + tr_r, base), QPointF(cx + tr_r, end))
        else:
            p.drawLine(QPointF(cx - tr_r * 0.8, base), QPointF(cx - tr_r * 0.8, end))
            p.drawLine(QPointF(cx + tr_r * 0.8, base), QPointF(cx + tr_r * 0.8, end))
        # cotas
        p.setPen(thin)

        def hdim(x0, x1, y, txt):
            p.drawLine(QPointF(x0, y), QPointF(x1, y))
            for x in (x0, x1):
                p.drawLine(QPointF(x, y - 4), QPointF(x, y + 4))
            p.drawText(QRectF(x0, y - 18, x1 - x0, 14), Qt.AlignmentFlag.AlignCenter, txt)

        def vdim(x, y0, y1, txt):
            p.drawLine(QPointF(x, y0), QPointF(x, y1))
            for y in (y0, y1):
                p.drawLine(QPointF(x - 4, y), QPointF(x + 4, y))
            p.drawText(QRectF(x - 60, (y0 + y1) / 2 - 7, 54, 14), Qt.AlignmentFlag.AlignRight, txt)

        if not blind:
            yh = far - sign * hh - sign * 14
            hdim(cx - head_r, cx + head_r, yh if rev else yh + 14, f"Ø{d['head']:.2f} mm")
            vdim(cx - head_r - 12, far - sign * hh, far, f"{d['head_h']:.2f}")
        hdim(cx - body_r, cx + body_r, end + sign * 22 if rev else end - 8, f"Ø{d['body']:.2f} mm")
        vdim(cx - body_r - 16, base, end, f"{L:g}")
        vdim(self.width() - 30, y_front, y_back, f"T {T:g}")
        p.setPen(QColor("#333333"))
        info = tr("Agujero Ø{h} mm").format(h=f"{d['hole']:.2f}")
        if blind:
            info += " · " + tr("ciego, profundidad {p} mm").format(p=f"{max(0.0, T - off):.2f}")
        p.drawText(QPointF(12, self.height() - 10), info)
        p.end()


class StudDialog(QDialog):
    def __init__(self, parent, doc, entity: StudEntity | None = None):
        super().__init__(parent)
        self.setWindowTitle(tr("Propiedades del perno / casquillo roscado"))
        self.resize(760, 520)
        self.doc = doc
        self.proto = entity.clone(keep_id=True) if entity is not None else StudEntity()
        h = QHBoxLayout(self)
        left = QWidget()
        f = QFormLayout(left)
        self.kind = QComboBox()
        for k in KINDS:
            self.kind.addItem(tr(k).capitalize(), k)
        self.kind.setCurrentIndex(max(0, self.kind.findData(self.proto.p.get("kind"))))
        self.thread = QComboBox()
        self.thread.addItems(THREADS)
        self.thread.setCurrentText(self.proto.p.get("thread", "M3"))
        self.length = QComboBox()
        self.length.setEditable(True)
        self.offset = QDoubleSpinBox()
        self.offset.setRange(0, 20)
        self.offset.setDecimals(2)
        self.offset.setSingleStep(0.1)
        self.offset.setSuffix(" mm")
        self.offset.setValue(float(self.proto.p.get("depth_offset", 0) or 0))
        self.offset.setToolTip(tr("0 = agujero pasante. >0 (en el reverso) = agujero ciego que deja ese espesor delante"))
        self.reverse = QCheckBox(tr("Colocar en el reverso"))
        self.reverse.setChecked(bool(self.proto.p.get("reverse", True)))
        f.addRow(tr("Tipo"), self.kind)
        f.addRow(tr("Rosca"), self.thread)
        f.addRow(tr("Longitud"), self.length)
        f.addRow(tr("Offset de profundidad"), self.offset)
        f.addRow("", self.reverse)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setProperty("role", "hint")
        f.addRow(self.info)
        note = QLabel(tr("Medidas orientativas de elementos a presión tipo PEM: verifique con la hoja de datos."))
        note.setWordWrap(True)
        note.setProperty("role", "hint")
        f.addRow(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Aceptar"))
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancelar"))
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lv = QVBoxLayout()
        lv.addWidget(left)
        lv.addStretch(1)
        lv.addWidget(bb)
        h.addLayout(lv, 1)
        rv = QVBoxLayout()
        rv.addWidget(QLabel(tr("Vista previa:")))
        self.section = StudSection()
        rv.addWidget(self.section, 1)
        h.addLayout(rv, 1)
        self._fill_lengths(float(self.proto.p.get("length", 6) or 6))
        self.kind.currentIndexChanged.connect(lambda _i: (self._fill_lengths(None), self._update()))
        self.thread.currentTextChanged.connect(lambda _t: self._update())
        self.length.currentTextChanged.connect(lambda _t: self._update())
        self.offset.valueChanged.connect(lambda _v: self._update())
        self.reverse.toggled.connect(lambda _v: self._update())
        self._update()

    def _fill_lengths(self, keep):
        cur = keep if keep is not None else self._length()
        self.length.blockSignals(True)
        self.length.clear()
        for L in LENGTHS[self.kind.currentData()]:
            self.length.addItem(f"{L:g} mm ({L / 25.4:.4f}\")", float(L))
        idx = self.length.findData(float(cur)) if cur else -1
        if idx >= 0:
            self.length.setCurrentIndex(idx)
        elif cur:
            self.length.setEditText(f"{cur:g}")
        self.length.blockSignals(False)

    def _length(self):
        txt = self.length.currentText().split("mm")[0].strip().replace(",", ".")
        try:
            return float(txt)
        except ValueError:
            return float(self.length.currentData() or 6)

    def _update(self):
        self.proto.p.update(kind=self.kind.currentData(), thread=self.thread.currentText(), length=self._length(),
                            depth_offset=round(self.offset.value(), 3), reverse=self.reverse.isChecked())
        _W, _H, T, _r = self.doc.panel_dims()
        d = self.proto.data()
        txt = tr("Agujero Ø{h} mm · cabeza Ø{c} mm · espesor mínimo de panel {m} mm").format(
            h=f"{d['hole']:.2f}", c=f"{d['head']:.2f}", m=d["min_t"])
        if T < d["min_t"]:
            txt += "<br><span style='color:#e5484d'>" + tr("El panel ({t} mm) es más fino que el mínimo").format(t=f"{T:g}") + "</span>"
        if self.offset.value() > 0 and not self.reverse.isChecked():
            txt += "<br>" + tr("El agujero ciego sólo se aplica al colocar en el reverso")
        self.info.setText(txt)
        self.section.set_state(self.proto, T)

    def result_params(self):
        self._update()
        return dict(self.proto.p)
