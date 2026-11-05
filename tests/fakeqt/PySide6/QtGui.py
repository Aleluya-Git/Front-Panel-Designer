import sys
from ._base import mod
sys.modules[__name__] = mod("PySide6.QtGui", {})
