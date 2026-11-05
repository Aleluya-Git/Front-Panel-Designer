"""Formato de proyecto .efpd (ZIP con project.json) y autoguardado."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile

from ..core.document import Document, FORMAT_VERSION
from ..core.library import user_library_dir

APP_NAME = "Electronic Front Panel Designer"


def save_project(doc: Document, path: str) -> None:
    data = doc.to_dict()
    meta = {"app": APP_NAME, "format_version": FORMAT_VERSION}
    d = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(suffix=".efpd.tmp", dir=d)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("meta.json", json.dumps(meta, indent=2))
            z.writestr("project.json", json.dumps(data, ensure_ascii=False, indent=1))
        os.replace(tmp, path)  # escritura atómica
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load_project(path: str) -> Document:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            data = json.loads(z.read("project.json").decode("utf-8"))
    else:  # JSON plano (compatibilidad / edición manual)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    if data.get("version", 1) > FORMAT_VERSION:
        raise ValueError("El proyecto se creó con una versión más reciente del programa")
    return Document.from_dict(data)


def autosave_dir() -> str:
    p = os.path.join(os.path.dirname(user_library_dir()), "autoguardado")
    os.makedirs(p, exist_ok=True)
    return p


def autosave_path() -> str:
    return os.path.join(autosave_dir(), "autoguardado.efpd")


def autosave(doc: Document, source_path: str = "") -> str:
    p = autosave_path()
    save_project(doc, p)
    with open(p + ".info", "w", encoding="utf-8") as f:
        json.dump({"source": source_path}, f)
    return p


def pending_autosave():
    """Devuelve (ruta, ruta_original) si quedó un autoguardado de una sesión anterior."""
    p = autosave_path()
    if os.path.exists(p):
        src = ""
        try:
            with open(p + ".info", encoding="utf-8") as f:
                src = json.load(f).get("source", "")
        except (OSError, ValueError):
            pass
        return p, src
    return None


def clear_autosave() -> None:
    for p in (autosave_path(), autosave_path() + ".info"):
        if os.path.exists(p):
            os.remove(p)
