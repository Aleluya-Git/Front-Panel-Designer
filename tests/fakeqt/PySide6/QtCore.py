from ._base import QPointF, QRectF, Signal, Stub, _Meta
import sys
from ._base import mod
_m = mod("PySide6.QtCore", {"QPointF": QPointF, "QRectF": QRectF, "Signal": Signal})
sys.modules[__name__] = _m
