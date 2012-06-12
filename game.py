import pygame
from pygame import gfxdraw
from pygame.locals import *
import random, math, sys

class Point(object):

    def __init__(self, x, y=None):
        """Point or vector"""
        if isinstance(x, Point):
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
        """The Point/Vector behaves as a tuple, mostly for interacting with pygame.
        Return integers measured in pixels
        """
        return int(self.tup[i])

    def __add__(self, other):
        if type(self) == type(other):
            return type(self)(self.x + other.x, self.y + other.y)
        if isinstance(other, Rect):
            return self + type(self)(other.topleft)
        raise(TypeError("Incompatible Vector/Point types"))

    def __sub__(self, other):
        return self + (other * -1)

    def __mul__(self, other):
        if type(self) == type(other):
            # vector dot product
            return self.x * other.x + self.y * other.y
        elif type(other) in (int, float):
            # scalar product
            return type(self)(self.x * other, self.y * other)
        raise(TypeError("Incompatible Vector/Point types"))

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
        assert type(self) == type(other), "Incompatible Vector/Point types"
        m = self.modulo
        om = other.modulo
        assert m > 0 and om > 0, 'One of the vectors has zero length'
        cos_alpha = self * other / (m * om)
        return math.acos(cos_alpha)

    def distance(self, other):
        assert type(self) == type(other), "Incompatible Vector/Point types"
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

    def orthonormal(self):
        """Create an orthogonal vector of length 1"""
        return self.orthogonal().normalized()

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


class PVector(Point):
    """2D vector, measured in pixels"""
    pass


class GVector(Point):
    """2D vector, measured in game units"""
    @property
    def pvector(self):
        """Equivalent vector measured in pixes"""
        return self.in_pixels

    def __getitem__(self, i):
        """The Point/Vector behaves as a tuple, mostly for interacting with pygame.
        Return integers measured in pixels
        """
        return int(self.tup[i] * 1) # FIXME: Grid size

    @property
    def in_pixels(self):
        """Equivalent vector measured in pixes"""
        return PVector(Grid_To_Scr(self.tup))



def distance(a, b):
    """Calculate distance between two points (tuples)"""
    d = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
    return d ** (.5)


pygame.init()
game = None

class Sprite(pygame.sprite.DirtySprite):
    def __init__(self, into):
        self.add([into])

class Orbits(Sprite):
    def __init__(self, into):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 1
        self.dirty = 1 
        self.image = pygame.Surface(RES, pygame.SRCALPHA)
        self.rect = pygame.Rect((0, 0), (10, 10))
        self.add([into])

    def update(self):
        self.dirty = 1

class Satellite(Sprite):
    def __init__(self, into):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 1
        self.dirty = 1 
        self.image = pygame.image.load('/usr/share/games/uqm/content/ipanims/ip_sun.2.png')
        x = random.randint(10, 790)
        y = random.randint(10, 590)
        self.gcenter = GVector(x, y)
        self.gspeed = GVector(.5, 0)
        self.rect = pygame.Rect(self.gcenter.tup, (10, 10))
        self.mass = .001
        self.radius = math.sqrt(self.mass)
        self.add([into])

    def update(self):
        """Move satellite"""
        self.gspeed += self._calculate_acceleration(self.gcenter, self.mass)
        self.gcenter += self.gspeed * game.speed
        self.rect.topleft = self.gcenter.tup
        #self._predict_orbit()
        self.dirty = 1

    def _get_suns(self):
        return [sun for sun in game.stack.get_sprites_from_layer(SAT_L)
            if isinstance(sun, Sun)]

    def _calculate_acceleration(self, center, mass, step=1):
        """Calculate gravitational acceleration relative to suns"""
        acceleration_v = GVector(0, 0)
        for sun in self._get_suns():
            distance = center.distance(sun.gcenter)
            dist_normal = center.normalized(sun.gcenter)
            force = 10.125 * (mass * sun.mass)/(distance ** 2) * step
            acceleration_v += dist_normal * force / mass

        return acceleration_v

    def _predict_orbit(self, steps=500):
        """Predict object orbit"""
        step = 3
        center = self.gcenter
        gspeed = self.gspeed * game.speed
        positions = []
        for x in xrange(steps):
            gspeed += self._calculate_acceleration(center, self.mass, step=step)
            center += gspeed * step
            positions.append((center, gspeed))
        return positions

    def _plot_orbit(self, orbit):
        """Plot orbit on orbits sprite"""
        surf = game._orbit.image
        surf.fill((0, 0, 0, 0))
        color = (0, 0, 255, 200)

        for p, v in orbit:
            w = min(254, int(v.modulo * 155))
            surf.set_at((int(p.x), int(p.y)), (w, w, 255, 70))

        #gfxdraw.aapolygon(surf, orbit, color)
        #pygame.draw.aalines(surf, color, False, orbit, True)

        game._orbit.dirty = 1


class Sun(pygame.sprite.DirtySprite):
    def __init__(self, into=None, gcenter=None):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 2
        self.dirty = 1
        self.image = pygame.image.load('/usr/share/games/uqm/content/ipanims/ip_sun.4.png')
        self.rect = self.image.get_rect()
        if gcenter:
            self.gcenter = gcenter
        else:
            self.gcenter = GVector(400, 300)
        self.gspeed = GVector(0, 0)
        self.rect.center = self.gcenter.tup
        self.mass = 4
        self.radius = math.sqrt(self.mass)
        if into is not None:
            self.add([into])

    def update(self):
        self.dirty = 1

class Starship(Satellite):
    def __init__(self, into=None):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 2
        self.dirty = 1
        self._raw_image = pygame.image.load('art/ship.png')
        self.gcenter = GVector(200, 300)
        self.gspeed = GVector(0, -0.3)
        self.thrust = None
        self.rect = pygame.Rect(self.gcenter.tup, (10, 10))
        self.mass = 4
        self.radius = math.sqrt(self.mass)
        self.add([into])
        self.thrust = GVector(0, 0)

    def update(self):
        """Plot orbit, move ship"""
        if self.thrust:
            self.gspeed += self.thrust
            self._cached_orbit = self._predict_orbit()
            self.thrust = None
            self._plot_orbit(self._cached_orbit)

        self.gspeed += self._calculate_acceleration(self.gcenter, self.mass)
        self.gcenter += self.gspeed * game.speed
        angle = self.gspeed.angle / math.pi * 180 + 180
        self.image = pygame.transform.rotozoom(self._raw_image, angle, .7)
        self.rect = self.image.get_rect()
        self.rect.center = self.gcenter.tup
        self.dirty = 1


SAT_L=0
RES=(800, 600)
RES=(1024, 768)

class Game(object):
    def __init__(self):
        self._clock = pygame.time.Clock()
        self._display_s = pygame.display.set_mode(RES)
        self.stack = pygame.sprite.LayeredDirty()
        self._background = pygame.image.load('space_dim.jpg')
        self._background = pygame.transform.smoothscale(self._background, RES)
        self.speed = 1
        self.propellent = 1500

        self._orbit = Orbits(self.stack)
        sun = Sun(into=self.stack)
        Sun(gcenter=GVector(500, 400), into=self.stack)
        for x in xrange(8):
            sat = Satellite(self.stack)
            sp = sun.gcenter - sat.gcenter
            sat.gspeed = sp.orthonormal() * .3
        self._ship = Starship(into=self.stack)


    def update(self):

        # clear out existing sprites
        self.stack.clear(self._display_s, self._background)

        # run update on every stack element
        self.stack.update()

        #satellites = self.stack.get_sprites_from_layer(SAT_L)

        for P in []:
            if P.x > 800-P.radius:   P.x = 800-P.radius;  P.speedx *= -1
            if P.x < 0+P.radius:     P.x = 0+P.radius;    P.speedx *= -1
            if P.y > 600-P.radius:   P.y = 600-P.radius;  P.speedy *= -1
            if P.y < 0+P.radius:     P.y = 0+P.radius;    P.speedy *= -1
            for P2 in satellites:
                if P != P2:
                    Distance = math.sqrt(  ((P.x-P2.x)**2)  +  ((P.y-P2.y)**2)  )
                    if Distance < (P.radius+P2.radius):
                        # collision
                        P.speedx = ((P.mass*P.speedx)+(P2.mass*P2.speedx))/(P.mass+P2.mass)
                        P.speedy = ((P.mass*P.speedy)+(P2.mass*P2.speedy))/(P.mass+P2.mass)
                        P.x = ((P.mass*P.x)+(P2.mass*P2.x))/(P.mass+P2.mass)
                        P.y = ((P.mass*P.y)+(P2.mass*P2.y))/(P.mass+P2.mass)
                        P.mass += P2.mass
                        P.radius = math.sqrt(P.mass)
                        #Particles.remove(P2)

        self.stack.draw(self._display_s)
        pygame.display.flip()

    def get_input(self):
        keystate = pygame.key.get_pressed()
        for event in pygame.event.get():
            if event.type == QUIT or keystate[K_ESCAPE]:
                pygame.quit()
                sys.exit()

        if pygame.mouse.get_pressed()[2]:
            if self.propellent:
                # fire thrusters
                mpos = pygame.mouse.get_pos()
                thrust = self._ship.gcenter - GVector(mpos)
                self._ship.thrust = thrust.normalized() * .001
                self.propellent -= 1

    def run(self):
        """Game loop"""
        while True:
            speed = self._clock.tick(60) / 16.0
            self.get_input()
            self.update()


def main():
    global game
    game = Game()
    game.run()

if __name__ == '__main__':
    main()
