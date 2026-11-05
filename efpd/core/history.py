"""Deshacer / rehacer ilimitado basado en instantáneas del documento.

Cada operación de edición llama a ``checkpoint(etiqueta)`` ANTES de modificar
el documento. Las instantáneas son JSON compacto, así que el coste es bajo y la
restauración siempre es exacta (incluidas expresiones y variables).
"""
from __future__ import annotations

import json
from typing import List, Tuple

from .document import Document


class History:
    def __init__(self, doc: Document, limit: int = 0):
        self.doc = doc
        self.limit = limit  # 0 = ilimitado
        self.undo_stack: List[Tuple[str, str]] = []
        self.redo_stack: List[Tuple[str, str]] = []
        self.clean_index = 0

    def _snap(self) -> str:
        d = self.doc.to_dict()
        d.pop("changelog", None)
        return json.dumps(d, separators=(",", ":"))

    def _restore(self, s: str) -> None:
        log = self.doc.changelog
        self.doc.load_dict(json.loads(s))
        self.doc.changelog = log

    def checkpoint(self, label: str) -> None:
        self.undo_stack.append((label, self._snap()))
        self.redo_stack.clear()
        if self.limit and len(self.undo_stack) > self.limit:
            drop = len(self.undo_stack) - self.limit
            del self.undo_stack[:drop]
            self.clean_index -= drop
        self.doc.log(label)

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo(self) -> str:
        if not self.undo_stack:
            return ""
        label, state = self.undo_stack.pop()
        self.redo_stack.append((label, self._snap()))
        self._restore(state)
        self.doc.log(f"Deshacer: {label}")
        return label

    def redo(self) -> str:
        if not self.redo_stack:
            return ""
        label, state = self.redo_stack.pop()
        self.undo_stack.append((label, self._snap()))
        self._restore(state)
        self.doc.log(f"Rehacer: {label}")
        return label

    def goto(self, index: int) -> None:
        """Salta a la posición 'index' (número de pasos aplicados)."""
        while len(self.undo_stack) > index and self.undo_stack:
            self.undo()
        while len(self.undo_stack) < index and self.redo_stack:
            self.redo()

    def labels(self) -> List[str]:
        return [l for l, _ in self.undo_stack] + [l for l, _ in reversed(self.redo_stack)]

    def mark_clean(self) -> None:
        self.clean_index = len(self.undo_stack)

    def is_dirty(self) -> bool:
        return self.clean_index != len(self.undo_stack)

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.clean_index = 0
