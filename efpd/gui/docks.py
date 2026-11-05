"""Paneles acoplables: capas, biblioteca, variables, historial y verificación."""
from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog, QComboBox, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPushButton, QSplitter,
                               QTableWidget, QTableWidgetItem, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from ..core.document import PROCESSES, Layer
from ..core.entities import new_id
from ..core.expr import ExprError, parse_number
from ..core.library import BUILTIN_LIBRARY, comp_name
from ..i18n import tr
from .comppreview import ComponentPreview, ThumbTip


# ======================================================================= capas
class LayersPanel(QWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([tr("Vis."), tr("Bloq."), tr("Color"), tr("Nombre"), tr("Proceso")])
        hh = self.table.horizontalHeader()
        for i in range(3):
            hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemChanged.connect(self._renamed)
        self.table.currentCellChanged.connect(self._current)
        v.addWidget(self.table)
        row = QHBoxLayout()
        for text, fn, tip in (("+", self._add, tr("Nueva capa")), ("−", self._del, tr("Eliminar capa vacía")),
                              ("↑", lambda: self._move(-1), tr("Subir")), ("↓", lambda: self._move(1), tr("Bajar")),
                              (tr("Seleccionar"), self._select_all, tr("Seleccionar todo lo de esta capa"))):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.active = QLabel()
        self.active.setProperty("role", "hint")
        v.addWidget(self.active)
        self._loading = False

    @property
    def doc(self):
        return self.mw.doc

    def refresh(self):
        self._loading = True
        self.table.setRowCount(len(self.doc.layers))
        for r, L in enumerate(self.doc.layers):
            for c, val in ((0, L.visible), (1, L.locked)):
                cb = QCheckBox()
                cb.setChecked(val)
                cb.toggled.connect(lambda v, lay=L, col=c: self._toggle(lay, col, v))
                w = QWidget()
                h = QHBoxLayout(w)
                h.setContentsMargins(6, 0, 0, 0)
                h.addWidget(cb)
                self.table.setCellWidget(r, c, w)
            b = QToolButton()
            b.setStyleSheet(f"background: {L.color}; border-radius: 4px; min-width: 18px;")
            b.clicked.connect(lambda _c=False, lay=L: self._color(lay))
            self.table.setCellWidget(r, 2, b)
            it = QTableWidgetItem(L.name)
            it.setData(Qt.ItemDataRole.UserRole, L.id)
            self.table.setItem(r, 3, it)
            co = QComboBox()
            for k, name in PROCESSES.items():
                co.addItem(tr(name), k)
            co.setCurrentIndex(max(0, co.findData(L.process)))
            co.currentIndexChanged.connect(lambda _i, lay=L, cmb=co: self._process(lay, cmb.currentData()))
            self.table.setCellWidget(r, 4, co)
        self._loading = False
        self._show_active()

    def _show_active(self):
        L = self.doc.layer(self.mw.active_layer)
        self.active.setText(tr("Capa activa para nuevas formas: <b>{n}</b>").format(n=L.name if L else "?"))

    def _current(self, row, _c, _pr, _pc):
        if 0 <= row < len(self.doc.layers):
            self.mw.active_layer = self.doc.layers[row].id
            self._show_active()

    def _toggle(self, L, col, v):
        self.mw.checkpoint(tr("Capa: visibilidad") if col == 0 else tr("Capa: bloqueo"))
        if col == 0:
            L.visible = v
        else:
            L.locked = v
        self.mw.changed()

    def _color(self, L):
        c = QColorDialog.getColor(QColor(L.color), self, tr("Color de capa"))
        if c.isValid():
            self.mw.checkpoint(tr("Capa: color"))
            L.color = c.name()
            self.mw.changed()
            self.refresh()

    def _process(self, L, proc):
        if self._loading or proc == L.process:
            return
        self.mw.checkpoint(tr("Capa: proceso"))
        L.process = proc
        self.mw.changed()

    def _renamed(self, it):
        if self._loading or it.column() != 3:
            return
        L = self.doc.layer(it.data(Qt.ItemDataRole.UserRole))
        if L and it.text() and it.text() != L.name:
            self.mw.checkpoint(tr("Capa: renombrar"))
            L.name = it.text()
            self.mw.changed()

    def _add(self):
        self.mw.checkpoint(tr("Nueva capa"))
        L = Layer(new_id(), tr("Capa {n}").format(n=len(self.doc.layers) + 1), "engrave", "#c678dd")
        self.doc.layers.append(L)
        self.mw.changed()
        self.refresh()

    def _del(self):
        r = self.table.currentRow()
        if not (0 <= r < len(self.doc.layers)) or len(self.doc.layers) <= 1:
            return
        L = self.doc.layers[r]
        if any(e.layer == L.id for e in self.doc.entities):
            self.mw.status(tr("La capa no está vacía"))
            return
        self.mw.checkpoint(tr("Eliminar capa"))
        self.doc.layers.pop(r)
        if self.mw.active_layer == L.id:
            self.mw.active_layer = self.doc.layers[0].id
        self.mw.changed()
        self.refresh()

    def _move(self, d):
        r = self.table.currentRow()
        n = r + d
        if 0 <= r < len(self.doc.layers) and 0 <= n < len(self.doc.layers):
            self.mw.checkpoint(tr("Ordenar capas"))
            L = self.doc.layers
            L[r], L[n] = L[n], L[r]
            self.mw.changed()
            self.refresh()
            self.table.selectRow(n)

    def _select_all(self):
        r = self.table.currentRow()
        if 0 <= r < len(self.doc.layers):
            lid = self.doc.layers[r].id
            self.mw.canvas.set_selection([e.id for e in self.doc.entities if e.layer == lid])


# ======================================================================= biblioteca
def comp_tooltip_html(c: dict) -> str:
    desc = c.get("description", "")
    lib = c.get("library", BUILTIN_LIBRARY)
    return (f"<b>{comp_name(c)}</b><br><span style='color:#9aa3ad'>{tr(lib)} · {tr(c.get('category', ''))}</span>"
            + (f"<br>{desc}" if desc else ""))


class LibraryPanel(QWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Buscar componente…"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        v.addWidget(self.search)
        split = QSplitter(Qt.Orientation.Vertical)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMouseTracking(True)
        self.tree.itemDoubleClicked.connect(lambda it, _c: self._place(it))
        self.tree.currentItemChanged.connect(self._selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.viewport().installEventFilter(self)
        split.addWidget(self.tree)
        box = QWidget()
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 4, 0, 0)
        self.preview = ComponentPreview(170)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setProperty("role", "hint")
        bv.addWidget(self.preview, 1)
        bv.addWidget(self.info)
        split.addWidget(box)
        split.setSizes([420, 220])
        v.addWidget(split, 1)
        row = QHBoxLayout()
        b1 = QPushButton(tr("Nuevo…"))
        b1.clicked.connect(lambda: self.mw.edit_component(None))
        b2 = QPushButton(tr("Desde selección"))
        b2.clicked.connect(self.mw.component_from_selection)
        b3 = QPushButton(tr("Colocar"))
        b3.clicked.connect(lambda: self._place(self.tree.currentItem()))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addWidget(b3)
        v.addLayout(row)
        hint = QLabel(tr("Doble clic para colocar. Clic derecho para editar, duplicar o gestionar bibliotecas."))
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        v.addWidget(hint)
        self.tip = ThumbTip()

    def refresh(self):
        q = self.search.text().strip().lower()
        self.tree.clear()
        for lib_name, cats in self.mw.lib.tree().items():
            lib_item = QTreeWidgetItem([tr(lib_name)])
            lib_item.setData(0, Qt.ItemDataRole.UserRole + 1, lib_name)
            f = lib_item.font(0)
            f.setBold(True)
            lib_item.setFont(0, f)
            any_child = False
            for cat, comps in cats.items():
                cat_item = None
                for c in comps:
                    name = comp_name(c)
                    if q and q not in name.lower() and q not in c["name"].lower() and q not in tr(cat).lower() \
                            and q not in c.get("description", "").lower():
                        continue
                    if cat_item is None:
                        cat_item = QTreeWidgetItem([tr(cat)])
                        lib_item.addChild(cat_item)
                    it = QTreeWidgetItem([name])
                    it.setData(0, Qt.ItemDataRole.UserRole, c["id"])
                    cat_item.addChild(it)
                    any_child = True
                if cat_item is not None and q:
                    cat_item.setExpanded(True)
            if any_child or (not q and lib_name != BUILTIN_LIBRARY):
                self.tree.addTopLevelItem(lib_item)
                lib_item.setExpanded(True)

    def _cid(self, it):
        return it.data(0, Qt.ItemDataRole.UserRole) if it else None

    def _selected(self, cur, _prev):
        cid = self._cid(cur)
        c = self.mw.lib.items.get(cid) if cid else None
        self.preview.set_comp(c)
        self.info.setText(comp_tooltip_html(c) if c else "")

    def eventFilter(self, obj, ev):
        if obj is self.tree.viewport():
            t = ev.type()
            if t == QEvent.Type.ToolTip:
                it = self.tree.itemAt(ev.pos())
                cid = self._cid(it)
                c = self.mw.lib.items.get(cid) if cid else None
                if c:
                    self.tip.show_for(cid, c, comp_tooltip_html(c), ev.globalPos())
                else:
                    self.tip.hide_tip()
                return True
            if t == QEvent.Type.MouseMove and self.tip.isVisible():
                it = self.tree.itemAt(ev.position().toPoint())
                if self._cid(it) != self.tip.key:
                    self.tip.hide_tip()
            elif t in (QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
                self.tip.hide_tip()
        return super().eventFilter(obj, ev)

    def _place(self, it):
        cid = self._cid(it)
        if cid:
            self.tip.hide_tip()
            self.mw.start_place_component(cid)

    def _menu(self, pos):
        it = self.tree.itemAt(pos)
        cid = self._cid(it)
        lib_name = it.data(0, Qt.ItemDataRole.UserRole + 1) if it else None
        m = QMenu(self)
        if cid:
            c = self.mw.lib.items.get(cid, {})
            m.addAction(tr("Colocar"), lambda: self.mw.start_place_component(cid))
            if c.get("builtin", True):
                m.addAction(tr("Duplicar en una biblioteca propia…"), lambda: self.mw.edit_component(cid, duplicate=True))
            else:
                m.addAction(tr("Editar…"), lambda: self.mw.edit_component(cid))
                m.addAction(tr("Duplicar…"), lambda: self.mw.edit_component(cid, duplicate=True))
                m.addAction(tr("Eliminar"), lambda: self.mw.delete_component(cid))
            m.addSeparator()
        if lib_name and lib_name != BUILTIN_LIBRARY:
            m.addAction(tr("Exportar biblioteca…"), lambda: self.mw.export_library(lib_name))
            m.addAction(tr("Eliminar biblioteca"), lambda: self.mw.delete_library(lib_name))
            m.addSeparator()
        m.addAction(tr("Nuevo componente…"), lambda: self.mw.edit_component(None))
        m.addAction(tr("Nueva biblioteca…"), self.mw.new_library)
        m.addAction(tr("Importar biblioteca…"), self.mw.import_library)
        m.addAction(tr("Recargar biblioteca"), lambda: (self.mw.lib.reload(), self.refresh()))
        m.exec(self.tree.viewport().mapToGlobal(pos))


# ======================================================================= variables
class VariablesPanel(QWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([tr("Nombre"), tr("Valor / expresión"), "= mm"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._edited)
        v.addWidget(self.table)
        row = QHBoxLayout()
        b1 = QPushButton(tr("Añadir"))
        b1.clicked.connect(self._add)
        b2 = QPushButton(tr("Eliminar"))
        b2.clicked.connect(self._del)
        row.addWidget(b1)
        row.addWidget(b2)
        v.addLayout(row)
        hint = QLabel(tr("Integradas: <b>W</b>, <b>H</b>, <b>T</b> (panel), <b>HP</b>=5.08, <b>U</b>=44.45, <b>inch</b>. "
                         "Use =nombre en cualquier medida para vincularla."))
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        v.addWidget(hint)
        self._loading = False

    def refresh(self):
        self._loading = True
        doc = self.mw.doc
        ev = doc.evaluator()
        names = sorted(doc.variables)
        self.table.setRowCount(len(names))
        for r, n in enumerate(names):
            a = QTableWidgetItem(n)
            a.setData(Qt.ItemDataRole.UserRole, n)
            self.table.setItem(r, 0, a)
            raw = doc.variables[n]
            self.table.setItem(r, 1, QTableWidgetItem(str(raw)))
            try:
                val = f"{ev.value(raw):.4f}".rstrip("0").rstrip(".")
                col = None
            except (ExprError, ZeroDivisionError, ValueError) as e:
                val, col = str(e), QColor("#ff4d4f")
            it = QTableWidgetItem(val)
            it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if col:
                it.setForeground(QBrush(col))
            self.table.setItem(r, 2, it)
        self._loading = False

    def _edited(self, it):
        if self._loading:
            return
        doc = self.mw.doc
        r = it.row()
        old = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        name = self.table.item(r, 0).text().strip()
        raw_txt = self.table.item(r, 1).text() if self.table.item(r, 1) else "0"
        if not name.isidentifier() or name in ("W", "H", "T"):
            self.mw.status(tr("Nombre de variable no válido"))
            self.refresh()
            return
        try:
            raw = parse_number(raw_txt)
        except ExprError as e:
            self.mw.status(str(e))
            self.refresh()
            return
        self.mw.checkpoint(tr("Variable {n}").format(n=name))
        if old != name:
            doc.variables.pop(old, None)
        doc.variables[name] = raw
        self.mw.changed(refresh_props=True)
        self.refresh()

    def _add(self):
        doc = self.mw.doc
        n = 1
        while f"var{n}" in doc.variables:
            n += 1
        self.mw.checkpoint(tr("Nueva variable"))
        doc.variables[f"var{n}"] = 10.0
        self.mw.changed()
        self.refresh()

    def _del(self):
        r = self.table.currentRow()
        if r < 0:
            return
        name = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        self.mw.checkpoint(tr("Eliminar variable {n}").format(n=name))
        self.mw.doc.variables.pop(name, None)
        self.mw.changed(refresh_props=True)
        self.refresh()


# ======================================================================= historial
class HistoryPanel(QTabWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        self.steps = QListWidget()
        self.steps.itemClicked.connect(self._jump)
        self.log = QListWidget()
        self.addTab(self.steps, tr("Deshacer"))
        self.addTab(self.log, tr("Registro"))

    def refresh(self):
        h = self.mw.history
        self.steps.clear()
        self.steps.addItem(QListWidgetItem("● " + tr("Estado inicial")))
        for i, lab in enumerate(h.labels()):
            it = QListWidgetItem(lab)
            if i >= len(h.undo_stack):
                it.setForeground(QBrush(QColor("#888888")))
            self.steps.addItem(it)
        self.steps.setCurrentRow(len(h.undo_stack))
        self.log.clear()
        for entry in reversed(self.mw.doc.changelog[-300:]):
            self.log.addItem(f"{entry.get('t', '')[11:19]}  {entry.get('what', '')}")

    def _jump(self, it):
        self.mw.history_goto(self.steps.row(it))


# ======================================================================= verificación
class ChecksPanel(QWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 6, 6, 6)
        self.list = QListWidget()
        self.list.itemClicked.connect(self._go)
        v.addWidget(self.list)
        b = QPushButton(tr("Verificar interferencias"))
        b.clicked.connect(self.mw.run_checks)
        v.addWidget(b)

    def show_issues(self, issues):
        self.list.clear()
        icon = {"error": "⛔", "aviso": "⚠", "info": "ℹ"}
        for iss in issues:
            it = QListWidgetItem(f"{icon.get(iss.level, '')}  {iss.message}")
            it.setData(Qt.ItemDataRole.UserRole, (list(iss.ids), iss.where))
            if iss.level == "error":
                it.setForeground(QBrush(QColor("#ff4d4f")))
            elif iss.level == "aviso":
                it.setForeground(QBrush(QColor("#f5a524")))
            self.list.addItem(it)

    def _go(self, it):
        ids, where = it.data(Qt.ItemDataRole.UserRole)
        if ids:
            self.mw.canvas.set_selection(ids)
            if where:
                self.mw.canvas.center_on(*where)
