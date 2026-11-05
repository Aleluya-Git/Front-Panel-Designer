"""Genera efpd/lang/en.json, de.json y fr.json a partir de tools/traducciones/*.py

Uso:  python tools/generar_idiomas.py        (avisa de los textos sin traducir)
"""
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from efpd import i18n  # noqa: E402

LANGS = [("en", "English"), ("de", "Deutsch"), ("fr", "Français")]


def load_tables():
    table, long_ = {}, {}
    folder = os.path.join(ROOT, "tools", "traducciones")
    for fn in sorted(os.listdir(folder)):
        if fn.endswith(".py"):
            spec = importlib.util.spec_from_file_location(fn[:-3], os.path.join(folder, fn))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            table.update(getattr(mod, "T", {}))
            long_.update(getattr(mod, "LONG", {}))
    return table, long_


def main():
    table, long_ = load_tables()
    keys = i18n.all_strings()
    for k in keys:
        if k not in table:
            for prefix, vals in long_.items():
                if k.startswith(prefix):
                    table[k] = vals
    missing = [k for k in keys if k not in table]
    unused = [k for k in table if k not in keys]
    os.makedirs(i18n.BUILTIN_DIR, exist_ok=True)
    for idx, (code, name) in enumerate(LANGS):
        strings = {k: table[k][idx] for k in keys if k in table}
        with open(os.path.join(i18n.BUILTIN_DIR, f"{code}.json"), "w", encoding="utf-8") as f:
            json.dump({"format": "efpd-lang", "code": code, "language": name, "strings": strings},
                      f, ensure_ascii=False, indent=1)
    print(f"{len(keys)} textos · {len(missing)} sin traducir · {len(unused)} traducciones sin uso")
    for k in missing:
        print("  FALTA:", repr(k))
    for k in unused:
        print("  SIN USO:", repr(k)[:90])
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
