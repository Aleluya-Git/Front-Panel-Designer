# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: genera la aplicación empaquetada (carpeta en Windows, .app en macOS).

Uso:  pyinstaller --noconfirm packaging/efpd.spec
"""
import os
import sys

from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH lo define PyInstaller)
sys.path.insert(0, ROOT)
from efpd import APP_NAME, __version__  # noqa: E402

datas = [(os.path.join(ROOT, "efpd", "resources"), os.path.join("efpd", "resources")),
         (os.path.join(ROOT, "efpd", "lang"), os.path.join("efpd", "lang"))]
# Las fuentes .py también van incluidas: «Generar plantilla de idioma» lee de ellas los textos traducibles.
for folder, _dirs, files in os.walk(os.path.join(ROOT, "efpd")):
    if "__pycache__" in folder:
        continue
    for fn in files:
        if fn.endswith(".py"):
            datas.append((os.path.join(folder, fn), os.path.relpath(folder, ROOT)))

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=collect_submodules("efpd"),
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="FrontPanelDesigner",
    console=False,
    icon=os.path.join(ROOT, "efpd", "resources", "icon.ico" if sys.platform == "win32" else "icon.icns"),
    version=os.path.join(SPECPATH, "windows", "version_info.txt") if sys.platform == "win32" else None,  # noqa: F821
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="FrontPanelDesigner", strip=False, upx=False)  # noqa: F821

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name=f"{APP_NAME}.app",
        icon=os.path.join(ROOT, "efpd", "resources", "icon.icns"),
        bundle_identifier="io.github.aleluya-git.frontpaneldesigner",
        version=__version__,
        info_plist={
            "CFBundleName": "Front Panel Designer",
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": __version__,
            "CFBundleVersion": __version__,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "© 2026 Aleluya-Git · GPL-3.0",
            "LSMinimumSystemVersion": "11.0",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "Electronic Front Panel Designer Project",
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
                "CFBundleTypeExtensions": ["efpd"],
                "CFBundleTypeIconFile": "icon.icns",
                "LSItemContentTypes": ["io.github.aleluya-git.efpd"],
            }],
            "UTExportedTypeDeclarations": [{
                "UTTypeIdentifier": "io.github.aleluya-git.efpd",
                "UTTypeDescription": "Electronic Front Panel Designer Project",
                "UTTypeConformsTo": ["public.data", "public.zip-archive"],
                "UTTypeTagSpecification": {"public.filename-extension": ["efpd"]},
            }],
        },
    )
