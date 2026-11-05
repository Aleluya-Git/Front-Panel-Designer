"""Expresiones paramétricas seguras.

Un valor numérico de cualquier entidad puede ser un número o una cadena que
empiece por '=' (p. ej. ``"=W/2"``, ``"=margen + 2*paso"``). Las variables
globales del documento son a su vez expresiones y se resuelven de forma
recursiva con detección de ciclos. Variables integradas: W, H, T (ancho, alto
y espesor del panel).
"""
from __future__ import annotations

import ast
import math
import operator
from typing import Dict, Optional

from ..i18n import tr

_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
           ast.FloorDiv: operator.floordiv}
_UNOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"min": min, "max": max, "abs": abs, "round": round, "sqrt": math.sqrt,
          "sin": lambda d: math.sin(math.radians(d)), "cos": lambda d: math.cos(math.radians(d)),
          "tan": lambda d: math.tan(math.radians(d)), "floor": math.floor, "ceil": math.ceil,
          "hypot": math.hypot}
_CONSTS = {"pi": math.pi, "inch": 25.4, "HP": 5.08, "U": 44.45}


class ExprError(ValueError):
    pass


def is_expr(raw) -> bool:
    return isinstance(raw, str) and raw.strip().startswith("=")


def parse_number(text: str):
    """Convierte la entrada de un campo de texto en valor bruto (float o '=expr')."""
    t = text.strip().replace(",", ".") if not text.strip().startswith("=") else text.strip()
    if t.startswith("="):
        compile_expr(t)  # valida sintaxis
        return t
    try:
        return float(t)
    except ValueError:
        # Permitir escribir una expresión sin '='
        compile_expr("=" + t)
        return "=" + t


_cache: Dict[str, ast.AST] = {}


def compile_expr(src: str) -> ast.AST:
    s = src.strip()
    if s.startswith("="):
        s = s[1:]
    s = s.replace(",", ".") if s.count("(") == 0 else s
    node = _cache.get(s)
    if node is None:
        try:
            node = ast.parse(s, mode="eval").body
        except SyntaxError as e:
            raise ExprError(tr("Sintaxis inválida: {s}").format(s=src)) from e
        _check(node)
        _cache[s] = node
    return node


def _check(node):
    for n in ast.walk(node):
        if isinstance(n, (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name,
                          ast.Load, ast.Call)) or type(n) in _BINOPS or type(n) in _UNOPS:
            if isinstance(n, ast.Call) and not (isinstance(n.func, ast.Name) and n.func.id in _FUNCS):
                raise ExprError(tr("Función no permitida"))
            if isinstance(n, ast.Constant) and not isinstance(n.value, (int, float)):
                raise ExprError(tr("Sólo se admiten números"))
            continue
        raise ExprError(tr("Elemento no permitido en expresión: {s}").format(s=type(n).__name__))


class Evaluator:
    """Resuelve valores brutos con las variables del documento."""

    def __init__(self, variables: Dict[str, object], builtins: Optional[Dict[str, float]] = None):
        self.variables = variables
        self.builtins = dict(builtins or {})
        self._resolved: Dict[str, float] = {}
        self._stack = []

    def var(self, name: str) -> float:
        if name in self.builtins:
            return self.builtins[name]
        if name in self._resolved:
            return self._resolved[name]
        if name in _CONSTS:
            return _CONSTS[name]
        if name not in self.variables:
            raise ExprError(tr("Variable desconocida: {s}").format(s=name))
        if name in self._stack:
            raise ExprError(tr("Referencia circular: {s}").format(s=" → ".join(self._stack + [name])))
        self._stack.append(name)
        try:
            v = self.value(self.variables[name])
        finally:
            self._stack.pop()
        self._resolved[name] = v
        return v

    def value(self, raw, default: float = 0.0) -> float:
        if raw is None or raw == "":
            return default
        if isinstance(raw, bool):
            return float(raw)
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            s = raw.strip()
            if not s.startswith("="):
                try:
                    return float(s.replace(",", "."))
                except ValueError:
                    pass
            return float(self._eval(compile_expr(s)))
        raise ExprError(tr("Valor no numérico: {s}").format(s=repr(raw)))

    def safe(self, raw, default: float = 0.0) -> float:
        try:
            return self.value(raw, default)
        except (ExprError, ZeroDivisionError, OverflowError, ValueError, TypeError):
            return default

    def _eval(self, n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            return self.var(n.id)
        if isinstance(n, ast.BinOp):
            return _BINOPS[type(n.op)](self._eval(n.left), self._eval(n.right))
        if isinstance(n, ast.UnaryOp):
            return _UNOPS[type(n.op)](self._eval(n.operand))
        if isinstance(n, ast.Call):
            return _FUNCS[n.func.id](*[self._eval(a) for a in n.args])
        raise ExprError(tr("Expresión no soportada"))
