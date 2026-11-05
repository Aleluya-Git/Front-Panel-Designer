"""Internacionalización.

Los textos fuente del programa están en español. Cada idioma es un fichero
JSON con la forma::

    {"format": "efpd-lang", "code": "en", "language": "English",
     "strings": {"Texto en español": "Translated text", ...}}

Idiomas integrados en ``efpd/lang/``; los idiomas añadidos por el usuario se
copian a la carpeta de datos del usuario (``…/EFPD/idiomas``). Un texto que
falte en la traducción se muestra en español.

Uso en el código:  ``tr("Guardar")``  ·  ``tr("{n} entidades").format(n=3)``
``N_("texto")`` marca un literal para la plantilla sin traducirlo en ese punto.
"""
from __future__ import annotations

import ast
import json
import os
import shutil
from typing import Dict, List, Optional

SOURCE_CODE = "es"
SOURCE_NAME = "Español"
BUILTIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")
PKG_DIR = os.path.dirname(os.path.abspath(__file__))

_code = SOURCE_CODE
_table: Dict[str, str] = {}


def tr(s: str) -> str:
    if not _table:
        return s
    return _table.get(s) or s


def N_(s: str) -> str:  # noqa: N802 - convención gettext
    return s


def current() -> str:
    return _code


def user_dir() -> str:
    from .core.library import user_library_dir
    p = os.path.join(os.path.dirname(user_library_dir()), "idiomas")
    os.makedirs(p, exist_ok=True)
    return p


def read_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("strings"), dict):
        raise ValueError(tr("El fichero no es un idioma válido (falta 'strings')"))
    code = str(data.get("code", "")).strip()
    if not code or not code.replace("_", "").replace("-", "").isalnum():
        raise ValueError(tr("El fichero de idioma necesita un 'code' válido (p. ej. 'it')"))
    data["code"] = code
    data.setdefault("language", code)
    return data


def available() -> Dict[str, dict]:
    """{código: {"language": nombre, "path": ruta | None, "user": bool}}"""
    out = {SOURCE_CODE: {"language": SOURCE_NAME, "path": None, "user": False}}
    for folder, is_user in ((BUILTIN_DIR, False), (user_dir(), True)):
        if not os.path.isdir(folder):
            continue
        for fn in sorted(os.listdir(folder)):
            if fn.lower().endswith(".json"):
                p = os.path.join(folder, fn)
                try:
                    d = read_file(p)
                except (OSError, ValueError):
                    continue
                out[d["code"]] = {"language": d["language"], "path": p, "user": is_user}
    return out


def set_language(code: Optional[str]) -> str:
    global _code, _table
    langs = available()
    if not code or code not in langs or code == SOURCE_CODE:
        _code, _table = SOURCE_CODE, {}
        return _code
    try:
        d = read_file(langs[code]["path"])
        _table = {k: v for k, v in d["strings"].items() if isinstance(v, str) and v}
        _code = code
    except (OSError, ValueError):
        _code, _table = SOURCE_CODE, {}
    return _code


def install_file(path: str) -> str:
    """Copia un fichero de idioma a la carpeta de usuario. Devuelve su código."""
    d = read_file(path)
    dest = os.path.join(user_dir(), f"{d['code']}.json")
    if os.path.abspath(path) != os.path.abspath(dest):
        shutil.copyfile(path, dest)
    return d["code"]


# ------------------------------------------------------------ plantilla
def _ast_strings() -> List[str]:
    found: List[str] = []
    for root, _dirs, files in os.walk(PKG_DIR):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            try:
                with open(os.path.join(root, fn), encoding="utf-8") as f:
                    tree = ast.parse(f.read())
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                fname = node.func.id if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) else (
                    node.func.attr if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) else None)
                if (fname in ("tr", "N_")
                        and node.args and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    found.append(node.args[0].value)
    return found


_CODE_OPTS = {"—", "M2", "M2.5", "M3", "M4", "M5", "M6", "M8", "rect", "circle", "oval", "h", "v", "a"}


def _data_strings() -> List[str]:
    from .core import document, entities, library, scale
    out: List[str] = []
    for cls in entities.TYPES.values():
        out.append(cls.LABEL)
        for f in cls.all_fields():
            out.append(f.label)
            if f.tip:
                out.append(f.tip)
            out += [o for o in f.options if o not in _CODE_OPTS]
    out += list(document.PROCESSES.values()) + list(document.MATERIALS) + document.FINISHES + document.PRESETS
    out += [L.name for L in document.default_layers()]
    for c in library.BUILTIN:
        out += [c["name_fmt"]["tpl"] if c.get("name_fmt") else c["name"], c["category"]]
    out += [g[0] for g in scale.GROUPS] + list(scale.PRESETS)
    out += [library.BUILTIN_LIBRARY, library.DEFAULT_USER_LIBRARY, library.TEMPLATE["name"], "Personalizados", "Otros"]
    return out


def all_strings() -> List[str]:
    seen, out = set(), []
    for s in _ast_strings() + _data_strings():
        if s and s not in seen and any(ch.isalpha() for ch in s):
            seen.add(s)
            out.append(s)
    return out


def make_template(path: str, base_code: str = "en") -> int:
    """Escribe una plantilla con todos los textos; los valores se rellenan con
    el idioma base (inglés por defecto) para facilitar la traducción."""
    base = {}
    langs = available()
    if base_code in langs and langs[base_code]["path"]:
        try:
            base = read_file(langs[base_code]["path"])["strings"]
        except (OSError, ValueError):
            base = {}
    keys = all_strings()
    data = {"format": "efpd-lang", "code": "xx", "language": "Nuevo idioma / New language",
            "_instructions": "Change 'code' (e.g. 'it') and 'language' (e.g. 'Italiano'), translate every value "
                             "(keys are the Spanish originals and must not be changed), keep {placeholders} "
                             "unchanged, then use View > Language > Install language from file.",
            "strings": {k: base.get(k, k) for k in keys}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return len(keys)
