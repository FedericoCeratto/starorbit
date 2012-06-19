import math

class Vector(object):
    """2D vector, with no specific unit value"""

    def __init__(self, x, y=None):
        """Point or vector"""
        if isinstance(x, Vector):
            self.tup = x.tup

        elif isinstance(x, tuple):
            assert len(x) == 2
            assert y is None, 'y cannot be set when the first param is a tuple'
            self.tup = x

        else:
            assert y is not None, 'y must be set'
            self.tup = (x, y)

    @property
    def x(self):
        return self.tup[0]

    @property
    def y(self):
        return self.tup[1]

    # act as a tuple
    def __len__(self):
        return len(self.tup)

    def __getitem__(self, i):
        """The Vector behaves as a tuple, mostly for interacting with pygame.
        Return integers measured in pixels
        """
        return int(self.tup[i])

    def __add__(self, other):
        if type(self) == type(other):
            return type(self)(self.x + other.x, self.y + other.y)
        if isinstance(other, Rect):
            return self + type(self)(other.topleft)
        raise(TypeError("Incompatible Vector types"))

    def __sub__(self, other):
        return self + (other * -1)

    def __mul__(self, other):
        if type(self) == type(other):
            # vector dot product
            return self.x * other.x + self.y * other.y
        elif type(other) in (int, float):
            # scalar product
            return type(self)(self.x * other, self.y * other)
        raise(TypeError("Incompatible Vector types"))

    def __div__(self, scalar):
        assert isinstance(scalar, int) or isinstance(scalar, float), \
            "Integer or Float required."
        return type(self)(self.x / scalar, self.y / scalar)


    # modulo attribute getter and setter
    @property
    def modulo(self):
        return (self.x ** 2 + self.y ** 2) ** .5

    @modulo.setter
    def modulo(self, m):
        assert isinstance(m, int) or isinstance(m, float), "Integer or Float required."
        a = self.angle
        x = math.sin(a) * m
        y = math.cos(a) * m
        self.tup = (x, y)

    # angle attribute getter and setter
    @property
    def angle(self):
        if self.modulo == 0:
            return 0

        a = math.acos(self.y / self.modulo)
        if self.x >= 0:
            return a
        return math.pi * 2 - a

    @angle.setter
    def angle(self, a):
        assert isinstance(m, int) or isinstance(m, float), "Integer or Float required."
        m = self.modulo
        x = math.sin(a) * m
        y = math.cos(a) * m
        self.tup = (x, y)

    def angle_against(self, other):
        """Angle between two vectors"""
        assert type(self) == type(other), "Incompatible Vector types"
        m = self.modulo
        om = other.modulo
        assert m > 0 and om > 0, 'One of the vectors has zero length'
        cos_alpha = self * other / (m * om)
        return math.acos(cos_alpha)

    def distance(self, other):
        assert type(self) == type(other), "Incompatible Vector types"
        d = other - self
        return d.modulo

    def normalized(self, other=None):
        v = self
        if other is not None:
            v = other - self
        return v / v.modulo

    def orthogonal(self):
        """Create an orthogonal vector"""
        return type(self)(self.y, -1 * self.x)

    def orthonormal(self, other=None):
        """Create an orthogonal vector of length 1"""
        v = self if other is None else other - self
        return v.orthogonal().normalized()

    def round_to_int(self):
        self.tup = (int(self.x), int(self.y))

    @property
    def rounded(self):
        return type(self)(int(self.x), int(self.y))

    def __repr__(self):
        return "Vector {%.3f, %.3f}" % (self.x, self.y)

    def set_polar(self, angle=None, modulo=None):
        if modulo == None:
            modulo = self.modulo
        x = math.sin(angle) * modulo
        y = math.cos(angle) * modulo
        self.tup = (x, y)


class PVector(Vector):
    """2D vector, measured in pixels"""
    def __repr__(self):
        return "PVector {%.3f, %.3f}" % (self.x, self.y)
