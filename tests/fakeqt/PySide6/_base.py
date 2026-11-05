from unittest.mock import MagicMock
class _Meta(type):
    def __getattr__(cls, name):
        m = MagicMock(name=f"{cls.__name__}.{name}")
        setattr(cls, name, m)
        return m
class Stub(metaclass=_Meta):
    def __init__(self, *a, **k): pass
    def __getattr__(self, name):
        m = MagicMock(name=name)
        object.__setattr__(self, name, m)
        return m
class QPointF:
    def __init__(self, x=0.0, y=0.0):
        if isinstance(x, QPointF): x, y = x._x, x._y
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise TypeError(f"QPointF({type(x).__name__}, {type(y).__name__})")
        self._x, self._y = float(x), float(y)
    def x(self): return self._x
    def y(self): return self._y
    def __add__(self, o): return QPointF(self._x + o._x, self._y + o._y)
    def __sub__(self, o): return QPointF(self._x - o._x, self._y - o._y)
    def manhattanLength(self): return abs(self._x) + abs(self._y)
    def toPoint(self): return self
class QRectF:
    def __init__(self, *a):
        if len(a) == 2: a = (a[0].x(), a[0].y(), a[1].x()-a[0].x(), a[1].y()-a[0].y())
        for v in a:
            if not isinstance(v, (int, float)): raise TypeError(f"QRectF arg {type(v).__name__}")
        self.a = a
    def normalized(self): return self
class Signal:
    def __init__(self, *a): pass
    def __get__(self, obj, t=None): return MagicMock()
def mod(name, extra):
    import types
    m = types.ModuleType(name)
    def ga(attr):
        if attr in extra: return extra[attr]
        c = _Meta(attr, (Stub,), {})
        setattr(m, attr, c)
        return c
    m.__getattr__ = ga
    for k, v in extra.items(): setattr(m, k, v)
    return m
