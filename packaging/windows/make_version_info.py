"""Escribe packaging/windows/version_info.txt (recurso de versión del .exe) a partir de efpd.__version__."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from efpd import APP_NAME, __version__  # noqa: E402

nums = [int(x) for x in (__version__.split(".") + ["0", "0", "0"])[:4] if x.isdigit()]
nums = (nums + [0, 0, 0, 0])[:4]
t = tuple(nums)
text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Aleluya-Git'),
      StringStruct('FileDescription', '{APP_NAME}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'FrontPanelDesigner'),
      StringStruct('LegalCopyright', '(C) 2026 Aleluya-Git - GPL-3.0'),
      StringStruct('OriginalFilename', 'FrontPanelDesigner.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
with open(os.path.join(HERE, "version_info.txt"), "w", encoding="utf-8") as f:
    f.write(text)
print("version_info.txt", __version__)
