#
# Physical units of measure
# AssertionError(s) are raised when incompatible operations are executed
#

from math import pi

class meters(float):
    def __add__(self, *args):
        assert isinstance(args[0], meters), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return super(meters, self).__add__(*args)

    def __sub__(self, *args):
        assert isinstance(args[0], meters), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return super(meters, self).__sub__(*args)


class radians(float):
    def __add__(self, *args):
        assert isinstance(args[0], radians), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return super(radians, self).__add__(*args)

    def __sub__(self, *args):
        assert isinstance(args[0], radians), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return super(radians, self).__sub__(*args)

    @property
    def degrees(self):
        return degrees(self * 180 / pi)


class degrees(float):
    def __add__(self, *args):
        assert isinstance(args[0], degrees), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return degrees(super(degrees, self).__add__(*args) % 360)

    def __sub__(self, *args):
        assert isinstance(args[0], degrees), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return degrees(super(degrees, self).__sub__(*args) % 360)

    @property
    def radians(self):
        return radians(self * pi / 180)

    @property
    def opposite(self):
        return self + degrees(180)


class degrees_per_sec(float):
    """Angular velocity"""

    def __add__(self, *args):
        assert isinstance(args[0], type(self)), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return type(self)(super(degrees_per_sec, self).__add__(*args))

    def __sub__(self, *args):
        assert isinstance(args[0], type(self)), \
            "Incorrect units: %s %s" % (type(self), type(args[0]))
        return type(self)(super(degrees_per_sec, self).__sub__(*args))

    def __mul__(self, other):
        if isinstance(other, seconds): # [degrees/s] * [s] = [degrees]
            return degrees(super(degrees_per_sec, self).__mul__(other))
        elif isinstance(other, (int, float)): # usual multiplication
            return type(self)(super(degrees_per_sec, self).__mul__(other))
        raise AssertionError, "Incorrect units: %s %s" % (type(self), type(other))

class seconds(float):
    pass
