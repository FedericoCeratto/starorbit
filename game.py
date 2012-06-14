from optparse import OptionParser
from pygame import gfxdraw
from pygame.locals import *
import pygame
import random, math, sys
from threading import Thread

game = None
SAT_L=0

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
        return int(self.tup[i] * game.zoom)

    @property
    def in_pixels(self):
        """Equivalent vector measured in pixes"""
        scaled = self * game.zoom
        return PVector(scaled.tup)


def distance(a, b):
    """Calculate distance between two points (tuples)"""
    d = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
    return d ** (.5)



class Sprite(pygame.sprite.DirtySprite):
    def __init__(self, into):
        self.add([into])

    def _load_raw_image(self, fname, scale):
        """Load raw sprite image"""
        img = pygame.image.load(fname)
        self._raw_image = img.convert_alpha()
        self._raw_size = GVector(img.get_size()) * scale

    def _scale(self):
        """Scale raw image into .image attribute, based on game zoom"""
        self.image = pygame.transform.smoothscale(self._raw_image, self._raw_size)
        self.rect = pygame.Rect((0, 0), (0, 0))

    def _recenter(self):
        """Update sprite rect based on screen offset"""
        rgcenter = self.gcenter - game.goffset
        pcenter = rgcenter.pvector + game.pscreen_center
        self.rect.center = pcenter.tup

    def update(self):
        if game.changed_scale:
            self._scale()
        self._recenter()
        self.dirty = 1

class Orbits(Sprite):
    def __init__(self, into):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 1
        self.dirty = 1 
        self._raw_image = pygame.Surface(game.resolution, pygame.SRCALPHA)
        self._raw_size = GVector(game.resolution)
        self.gcenter = GVector(0, 0)
        self.rect = pygame.Rect((0, 0), (0, 0))
        self.add([into])
        self._alpha = 0
        self._fading = 'in' # 'in', 'out', None
        self._orbit = ()

    def _plot_orbit(self):
        """Plot an orbit"""
        self._raw_image.fill((0, 0, 0, 0))
        color = (0, 0, 255, 200)
        self.dirty = 1

        #white = (255, ) * 4
        #sx, sy = self._raw_image.get_size()
        #pygame.draw.line(self._raw_image, white, (0,0), (0, sy))
        #pygame.draw.line(self._raw_image, white, (0,0), (sx, 0))

        for p, v in self._orbit:
            w = min(254, int(v.modulo * 128))
            self._raw_image.set_at((int(p.x), int(p.y)), (w, w, 255, self._alpha))

        self._scale()
        self._recenter()
        self.dirty = 1

    def fade_in(self, orbit):
        """Start fading in a new orbit"""
        self._orbit = orbit
        self._fading = 'in'

    def fade_out(self):
        """Start fading out the orbit"""
        self._fading = 'out'

    def update(self):
        if self._fading == 'in':
            self._alpha += 30
            if self._alpha > 255:
                self._alpha = 255
                self._fading = None
            self._plot_orbit()

        elif self._fading == 'out':
            self._alpha -= 30
            if self._alpha < 0:
                self._alpha = 0
                self._fading = None
            self._plot_orbit()

        if game.changed_scale:
            self._plot_orbit()
            self._scale()
        self._recenter()
        self.dirty = 1

class Satellite(Sprite):
    def __init__(self, into):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 1
        self.dirty = 1 
        x = random.randint(10, 790)
        y = random.randint(10, 590)
        self.gcenter = GVector(x, y)
        self.gspeed = GVector(.5, 0)
        self.rect = pygame.Rect(self.gcenter.tup, (10, 10))
        self.mass = .001
        self.add([into])
        self._load_raw_image('art/sun.png', .2)
        self.orbit = ()

    def update(self):
        """Move satellite"""
        if game.changed_scale:
            self._scale()
        self.gspeed += self._calculate_acceleration(self.gcenter, self.mass)
        self.gcenter += self.gspeed * game.speed
        self._recenter()
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

    def _predict_orbit(self, center):
        """Predict object orbit"""
        #gspeed = self.gspeed * game.speed
        gspeed = self.gspeed * 1
        positions = []
        for x in xrange(5000):
            gspeed += self._calculate_acceleration(center, self.mass)
            if gspeed.modulo > 2.5: # unreliable prediction
                self.orbit = positions
                return
            center += gspeed
            positions.append((center, gspeed))
        self.orbit = positions



class Sun(Sprite):
    def __init__(self, into=None, gcenter=None):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 2
        self.dirty = 1
        self._load_raw_image('art/sun.png', .5)
        if gcenter:
            self.gcenter = gcenter
        else:
            self.gcenter = GVector(400, 300)
        self.gspeed = GVector(0, 0)
        self.mass = 4
        if into is not None:
            self.add([into])


class Starship(Satellite):
    def __init__(self, into=None):
        pygame.sprite.DirtySprite.__init__(self)
        self.layer = 2
        self.dirty = 1
        self._load_raw_image('art/ship.png', .25)
        self.gcenter = GVector(200, 300)
        self.gspeed = GVector(0, -0.3)
        self.thrust = None
        self.mass = 4
        self.add([into])
        self.thrust = GVector(0, 0)
        self._orbit_prediction_thread = None
        self.orbit = ()

    def update(self):
        """Plot orbit, move ship"""
        if game.changed_scale:
            self._scale()

        if self.thrust:
            self.gspeed += self.thrust

        if self.thrust or game.changed_scale:
            # fire off a thread to perform prediction
            self._orbit_prediction_thread = Thread(
                target=self._predict_orbit,
                args=(self.gcenter, )
            )
            self._orbit_prediction_thread.start()
            self.thrust = None
            # blank out old orbit
            game.orbit.fade_out()

        if self._orbit_prediction_thread:
            if not self._orbit_prediction_thread.is_alive():
                # thread just terminated
                self._orbit_prediction_thread = None
                # plot new orbit
                game.orbit.fade_in(self.orbit)

        self.gspeed += self._calculate_acceleration(self.gcenter, self.mass)
        self.gcenter += self.gspeed * game.speed
        angle = self.gspeed.angle / math.pi * 180 + 180

        tmp = pygame.transform.smoothscale(self._raw_image, self._raw_size)
        self.image = pygame.transform.rotozoom(tmp, angle, .7)
        self.rect = self.image.get_rect()
        self._recenter()
        self.dirty = 1



class Game(object):
    def __init__(self, fullscreen=False, resolution=None):
        """Initialize Game"""
        pygame.init()
        pygame.display.set_caption('Game')
        if fullscreen:
            self._set_fullscreen()
        else:
            self._change_resolution(resolution)
        self._clock = pygame.time.Clock()
        self.stack = pygame.sprite.LayeredDirty()
        self.speed = 1
        self.propellent = 1500
        self.zoom = 1
        self._zoom_level = 3.9
        self.changed_scale = True
        self.goffset = GVector(0, 0)

    def _set_fullscreen(self):
        """Set fullscreen mode"""
        surf = self._display_s = pygame.display.set_mode((0, 0),
            pygame.FULLSCREEN | pygame.HWSURFACE)
        self.resolution = PVector(surf.get_size())
        self.pscreen_center = self.resolution / 2
        self._background = pygame.image.load('space_dim.jpg')
        self._background = pygame.transform.smoothscale(self._background,
            self.resolution)
        self.changed_scale = True

    def _change_resolution(self, resolution):
        """Change screen resolution"""
        self.resolution = resolution
        self.pscreen_center = resolution / 2
        self._display_s = pygame.display.set_mode(resolution,
            pygame.RESIZABLE)
        self._background = pygame.image.load('space_dim.jpg')
        self._background = pygame.transform.smoothscale(self._background,
            resolution)
        self.changed_scale = True

    def _create_space_objects(self):
        self.orbit = Orbits(self.stack)
        sun = Sun(into=self.stack)
        Sun(gcenter=GVector(700, 600), into=self.stack)
        Sun(gcenter=GVector(500, 100), into=self.stack)
        for x in xrange(8):
            sat = Satellite(self.stack)
            sp = sun.gcenter - sat.gcenter
            sat.gspeed = sp.orthonormal() * .3
        self._ship = Starship(into=self.stack)

    def _zoom_in(self):
        if self._zoom_level < .5:
            return
        self._zoom_level -= .5
        self.changed_scale = True
        # I have no idea what i'm doing
        self.zoom = 4 * math.atan(1/self._zoom_level)

    def _zoom_out(self):
        self._zoom_level += .5
        self.changed_scale = True
        self.zoom = 4 * math.atan(1/self._zoom_level)

    def _impulse(self):
        """Fire thrusters for one impulse"""
        if not self.propellent:
            return
        mpos = pygame.mouse.get_pos()
        thrust = self._ship.gcenter - GVector(mpos)
        self._ship.thrust = thrust.normalized() * .001
        self.propellent -= 1

    def update(self):

        # clear out existing sprites
        self.stack.clear(self._display_s, self._background)

        # run update on every stack element
        self.stack.update()

        self.stack.draw(self._display_s)
        pygame.display.flip()

    def get_input(self):
        """Process user input"""
        self.changed_scale = False
        for event in pygame.event.get():
            if event.type == QUIT or event.type == KEYDOWN and event.key == 27:
                # quit on Esc key or window closing
                pygame.quit()
                sys.exit()
            elif event.type == KEYDOWN: # key pressed
                if event.unicode == u'i':
                    self._impulse()
            elif event.type == MOUSEBUTTONDOWN: # mouse click
                if event.button == 4: # wheel up
                    self._zoom_in()
                elif event.button == 5: # wheen down
                    self._zoom_out()
                #elif event.button == 3: # right click
                #mouse.get_pressed() allows continuous firing
            elif event.type == VIDEORESIZE:
                self._change_resolution(PVector(event.size))

        if pygame.mouse.get_pressed()[2]:
            self._impulse()

    def run(self):
        """Game loop"""
        self._create_space_objects()
        self.update()
        while True:
            speed = self._clock.tick(60) / 16.0
            self.get_input()
            k = min(5, self._zoom_level) / 5
            self.goffset = self._ship.gcenter * (1-k) + GVector(400, 300) * k
            self.update()


def parse_args():
    """Parse CLI args"""
    parser = OptionParser()
    parser.add_option("-f", "--fullscreen", dest="fullscreen",
        action="store_true", help="fullscreen", default=False)
    parser.add_option("-x", "--x-resolution", dest="resolution",
        help="resolution", default=None)

    (options, args) = parser.parse_args()
    rx = options.resolution
    if rx:
        options.resolution = PVector(int(rx), int(int(rx)/4.0*3))
    return options, args

def main():
    global game
    opts, args = parse_args()
    game = Game(fullscreen=opts.fullscreen, resolution=opts.resolution)
    game.run()

if __name__ == '__main__':
    main()
