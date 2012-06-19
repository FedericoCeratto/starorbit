import gloss
from gloss import Gloss, GlossGame
from optparse import OptionParser
from pygame import gfxdraw
from pygame.locals import *
from threading import Thread
import math
import pygame
import random
import sys

from vectors import Vector, PVector

game = None
SAT_L = 0
G = 10.125

class GVector(Vector):
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

    @property
    def on_screen(self):
        """Equivalent vector measured in pixels, shifted based on the camera
        offset and the screen center
        """
        return self.pvector - game.gcamera.pvector + game._screen_center

    def __repr__(self):
        return "GVector {%.3f, %.3f}" % (self.x, self.y)


def distance(a, b):
    """Calculate distance between two points (tuples)"""
    d = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
    return d ** (.5)



class Sprite(gloss.Sprite):
    def __init__(self, fname):
        gloss.Sprite.__init__(self, gloss.Texture(fname))
        self._raw_scale = 1
        self._raw_rotation = 0.0

    def _recenter(self):
        """Update sprite rect based on screen offset"""
        self.pcenter = self.gcenter.on_screen
        self.move_to(int(self.pcenter.x), int(self.pcenter.y))

    def update(self):
        pass

    def draw(self):
        """Draw on screen"""
        self._recenter()
        angle = getattr(self, '_angle', 0.0)
        gloss.Sprite.draw(self, scale=self._raw_scale * game.zoom, rotation=angle)


class Orbit(object):
    """Starship orbit"""
    def __init__(self):
        self.gcenter = GVector(0, 0)
        self._alpha = 0
        self._fading = 'in' # 'in', 'out', None
        self._orbit = ()
        self._color = gloss.Color.smooth_step(
            gloss.Color.WHITE,
            gloss.Color.TRANSPARENT_WHITE,
            0.9
        )

    def fade_in(self, orbit):
        """Start fading in a new orbit"""
        self._orbit = orbit
        self._fading = 'in'

    def fade_out(self):
        """Start fading out the orbit"""
        self._fading = 'out'

    def update(self):

        if self._fading == 'in':
            self._alpha += .01
            if self._alpha > 1:
                self._alpha = 1
                self._fading = None
            self._color = gloss.Color.smooth_step(
                gloss.Color.TRANSPARENT_WHITE,
                gloss.Color.WHITE,
                self._alpha * .2
            )

        elif self._fading == 'out':
            self._alpha -= .01
            if self._alpha < 0:
                self._alpha = 0
                self._fading = None
            self._color = gloss.Color.smooth_step(
                gloss.Color.TRANSPARENT_WHITE,
                gloss.Color.WHITE,
                self._alpha * .2
            )

    def draw(self):
        if not self._orbit:
            return

        orbit_centers = [o.on_screen for o in self._orbit]

        gloss.Gloss.draw_lines(
            orbit_centers,
            color=self._color,
            width=game.zoom * 1,
            join=False
        )


class Background(Sprite):
    def __init__(self):
        Sprite.__init__(self, 'space_dim.jpg')
        t = self.texture
        self._raw_scale = 1
        self.gcenter = GVector(t.half_height, t.half_width) * -1 * self._raw_scale
        self.gcenter = GVector(-1000, -1000)

class Circle(Sprite):
    def __init__(self):
        Sprite.__init__(self, 'art/circle_cyan.png')
        self.gcenter = GVector(0, 0)

    def draw(self):
        """Draw on screen"""
        gloss.Sprite.draw(self, scale=.05)

    def update(self):
        self.gcenter = game._ship.gcenter - GVector(10, 10)
        self._recenter()


class Satellite(Sprite):
    def __init__(self):
        Sprite.__init__(self, 'art/blue_sun.png')
        self._raw_scale = .01
        x = random.randint(-300, 300)
        y = random.randint(-300, 300)
        self.gcenter = GVector(x, y)
        self.gspeed = GVector(.5, 0)
        self.rect = pygame.Rect(self.gcenter.tup, (10, 10))
        self.mass = .001
        self.orbit = ()

    def place_in_orbit(self, planet):
        """Place object in orbit against a planet"""
        d = self.gcenter.distance(planet.gcenter)
        v = math.sqrt((G * planet.mass ** 2) / ((self.mass + planet.mass) * d))
        self.gspeed = self.gspeed.orthonormal(planet.gcenter)
        self.gspeed.modulo = v

    def update(self):
        """Move satellite"""
        self.gspeed += self._calculate_acceleration(self.gcenter, self.mass)
        self.gcenter += self.gspeed * game.speed
        if self._collision_with_suns(self.gcenter):
            game.create_explosion(self.gcenter, self)
        self._recenter()

    def _collision_with_suns(self, center, thresh=15):
        for sun in game._suns:
            if center.distance(sun.gcenter) < thresh:
                return True
        return False

    def _calculate_acceleration(self, center, mass, step=1):
        """Calculate gravitational acceleration relative to suns"""
        acceleration_v = GVector(0, 0)
        for sun in game._suns:
            distance = center.distance(sun.gcenter)
            dist_normal = center.normalized(sun.gcenter)
            force = G * (mass * sun.mass)/(distance ** 2) * step
            acceleration_v += dist_normal * force / mass

        return acceleration_v


    def _predict_orbit(self, center):
        """Predict object orbit"""
        #gspeed = self.gspeed * game.speed
        gspeed = self.gspeed * 1
        positions = []
        far = False
        start = center
        for x in xrange(10000):
            gspeed += self._calculate_acceleration(center, self.mass)
            if gspeed.modulo > 12.5: # unreliable prediction
                self.orbit = positions
                return
            center += gspeed
            if x > 1000:
                if center.distance(start) < .1:
                    positions.append(center)
                    self.orbit = positions
                    return

            if x % 10 == 0:
                positions.append(center)
        self.orbit = positions



class Sun(Sprite):
    def __init__(self, gcenter=None):
        Sprite.__init__(self, 'art/sun.png')
        self._raw_scale = 1
        if gcenter:
            self.gcenter = gcenter
        else:
            self.gcenter = GVector(400, 300)
        self.gspeed = GVector(0, 0)
        self.mass = 4

class Starship(Satellite):
    def __init__(self, gcenter):
        gloss.Sprite.__init__(self, gloss.Texture('art/ship.png'))
        gloss.Sprite.__init__(self, gloss.Texture('art/ship.png'))
        self._angle = 0.0
        self._orbit_prediction_thread = None
        self._raw_scale = .025
        self._tp = None
        self.gcenter = gcenter
        self.gspeed = GVector(0, -0.3)
        self.mass = 4
        self.orbit = ()
        self.propellent = 1500
        self.temperature = 0
        self.thrust = GVector(0, 0)

    def _update_temperature(self):
        """Calculate temperature increase/decrease"""
        dt = -1
        for sun in game._suns:
            distance = self.gcenter.distance(sun.gcenter)
            dt += 10000 / distance ** 2

        if dt < 0 and self.temperature < 0:
            return

        self.temperature += dt

    def update(self):
        """Plot orbit, move ship"""
        if self.thrust:
            self.gspeed += self.thrust
            self.thrust = None

            # fire off a thread to perform prediction
            self._orbit_prediction_thread = Thread(
                target=self._predict_orbit,
                args=(self.gcenter, )
            )
            self._orbit_prediction_thread.start()
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
        self._angle = - self.gspeed.angle / math.pi * 180 + 180
        self._update_temperature()
        self._recenter()

    def fire_thruster(self, thrust):
        self.thrust = thrust * .01
        self.propellent -= 100

        forw_n = self.gspeed.normalized()
        side_n = forw_n.orthonormal()
        forw_component = forw_n * (thrust * forw_n)
        side_component = side_n * (thrust * side_n)
        self._tp = Thruster(self.gcenter, forw_component * 500)
        game._particles.append(self._tp)
        self._tp = Thruster(self.gcenter, side_component * 500)
        game._particles.append(self._tp)


class PSystem(object):
    """Wrapper for ParticleSystem"""
    def _finished(self, ps):
        """Remove self from the particle list"""
        game.kill_sprite(self)

    def draw(self):
        self._ps.draw()

    def update(self):
        pass


class Explosion(PSystem):
    def __init__(self, pcenter):
        self._texture= gloss.Texture("fire.png")
        self._ps = gloss.ParticleSystem(
            self._texture,
            onfinish = self._finished,
            position = pcenter.tup,
            name = "fire",
            initialparticles = 25,
            particlelifespan = 750,
            drag = 4,
            minspeed = 50,
            maxspeed = 100,
            minscale = game.zoom,
            maxscale = game.zoom,
        )


class Thruster(PSystem):
    def __init__(self, gcenter, gdir):
        self.gcenter = gcenter
        tex = gloss.Texture("smoke.tga")
        self._ps = gloss.ParticleSystem(
            tex,
            onfinish = self._finished,
            position = gcenter.pvector.tup,
            name = "smoke",
            initialparticles = 10,
            particlelifespan = 300,
            growth = 2.0,
            wind = map(int, gdir.pvector.tup),
            minspeed = 1,
            maxspeed = 5
        )

class Bar(object):
    """Basic display Bar class"""
    def update(self):
        self._value = getattr(self._obj, self._attr, 0) / self._value_max

    def draw(self):
        raise NotImplementedError


class VBar(object):
    """Vertical bar"""
    def __init__(self, pos_perc=10, len_perc=30, color=None):
        pass

class HBar(Bar):
    """Horizontal bar"""
    def __init__(self, obj, attr, pos_f, color, len_f=.3, vmax=1):
        res = game.resolution
        self._attr = attr
        self._maxlen = len_f * res.y
        self._obj = obj
        self._stopleft = PVector(res.x * pos_f, res.y - 10)
        self._value_max = float(vmax)
        self._value = 1
        self._color = gloss.Color.smooth_step(
            color,
            gloss.Color.TRANSPARENT_WHITE,
            0.4
        )

    def draw(self):
        gloss.Gloss.draw_box(
            position = self._stopleft.tup,
            width = self._value * self._maxlen,
            height = 5,
            color=self._color,
        )
        gloss.Gloss.draw_box(
            position = self._stopleft,
            width = 1, height = 5, color=self._color,
        )
        gloss.Gloss.draw_box(
            position = self._stopleft + PVector(self._maxlen, 0),
            width = 1, height = 5, color=self._color,
        )


class Game(gloss.GlossGame):
    def __init__(self, fullscreen=False, resolution=None, display_fps=False):
        """Initialize Game"""
        gloss.GlossGame.__init__(self, 'Satellife')
        pygame.init()
        pygame.display.set_caption('Game')
        if fullscreen:
            self._set_fullscreen()
        else:
            self._change_resolution(resolution)
        self._screen_center = self.resolution / 2
        self._clock = pygame.time.Clock()
        self._display_fps = display_fps
        self.stack = pygame.sprite.LayeredDirty()
        self.speed = 1
        self.zoom = 1
        self._zoom_level = 3.9
        self.changed_scale = True
        self.gcamera = GVector(0, 0)

        # event handlers
        self.on_mouse_down = self._mouse_click
        self.on_mouse_motion = lambda x: x
        self.on_key_down = self._keypress


    def _set_fullscreen(self):
        """Set fullscreen mode"""
        surf = self._display_s = pygame.display.set_mode((0, 0),
            pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF |
            pygame.OPENGL)
        Gloss.full_screen = True
        self.resolution = PVector(surf.get_size())
        self._background = pygame.image.load('space_dim.jpg')
        self._background = pygame.transform.smoothscale(self._background,
            self.resolution)
        self.changed_scale = True

    def _change_resolution(self, resolution):
        """Change screen resolution"""
        self.resolution = resolution
        Gloss.screen_resolution = resolution.tup
        self._display_s = pygame.display.set_mode(resolution,
            pygame.RESIZABLE | pygame.DOUBLEBUF | pygame.OPENGL)
        self._background = pygame.image.load('space_dim.jpg')
        self._background = pygame.transform.smoothscale(self._background,
            resolution)
        self.changed_scale = True

    def _zoom_in(self):
        if self._zoom_level >= .2:
            self._zoom_level -= .2

    def _zoom_out(self):
        self._zoom_level += .2

    def _update_zoom(self):
        # I have no idea what i'm doing
        zoom = 32 * math.atan(1/self._zoom_level)
        if self.zoom != zoom:
            self.zoom += (zoom - self.zoom) / 10
            self.changed_scale = True

    def _impulse(self):
        """Fire thrusters for one impulse"""
        if self._ship.propellent:
            mpos = pygame.mouse.get_pos()
            thrust = self._ship.gcenter - GVector(mpos)
            self._ship.fire_thruster(thrust.normalized())

    def create_explosion(self, gcenter, victim):
        self.kill_sprite(victim)
        self._particles.append(Explosion(gcenter.on_screen))

    def kill_sprite(self, victim):
        for li in self._suns, self._satellites, self._particles, self._circles, [self._ship]:
            for i in li:
                if i == victim:
                    li.remove(victim)
                    return

        raise RuntimeError, "Unable to kill %s" % repr(victim)

    def _mouse_click(self, event):
        self.changed_scale = False
        if event.button == 4: # wheel up
            self._zoom_in()
        elif event.button == 5: # wheen down
            self._zoom_out()
        #elif event.button == 3: # right click
        #mouse.get_pressed() allows continuous firing

    def _keypress(self, event):
        if event.key == 27:
            # quit on Esc key or window closing
            pygame.quit()
            sys.exit()
        elif event.unicode == u'i':
            self._impulse()

    def load_content(self):
        """Load images, create game objects"""
        self._font = gloss.SpriteFont(
            '/usr/share/fonts/truetype/freefont/FreeSans.ttf', 10)

        self._background = Background()
        self.orbit = Orbit()
        self._suns = [Sun(gcenter=GVector(100 * x, -100))
            for x in xrange(1)]
        self._satellites = [Satellite() for x in xrange(10)]
        for s in self._satellites:
            s.place_in_orbit(self._suns[0])
        self._circles = [Circle(), ]
        self._circles = []
        self._particles = []
        self._ship = Starship(GVector(-100, 100))
        self._ship.place_in_orbit(self._suns[0])

        self._bars = [
            HBar(self._ship, 'propellent', .05, gloss.Color.GREEN, vmax=1500),
            HBar(self._ship, 'temperature', .40, gloss.Color.RED, vmax=1500),
        ]


    def draw(self):
        """Main game loop: update game objects, handle zoom and pan, finally
        draw to screen
        """
        self._update_zoom()

        k = min(1, self.zoom / 10)
        self.gcamera = self._ship.gcenter * k + self._suns[0].gcenter * (1 - k)

        self.changed_scale = True
        stack = self._suns + self._satellites + self._particles + \
            [self.orbit] + self._circles + [self._ship] + self._bars
        for s in stack:
            s.update()

        self._background.draw()
        for s in stack:
            s.draw()

        if self._display_fps:
            fps = 1/gloss.Gloss.elapsed_seconds
            self._font.draw("%.2f" % fps, scale = 1,
                color = gloss.Color.BLUE, letterspacing = 0, linespacing = -25)

def parse_args():
    """Parse CLI args"""
    parser = OptionParser()
    parser.add_option("-f", "--fullscreen", dest="fullscreen",
        action="store_true", help="fullscreen", default=False)
    parser.add_option("-r", "--framerate", dest="framerate",
        action="store_true", help="display FPS", default=False)
    parser.add_option("-x", "--x-resolution", dest="resolution",
        help="resolution", default=800)

    (options, args) = parser.parse_args()
    rx = options.resolution
    if rx:
        options.resolution = PVector(int(rx), int(int(rx)/4.0*3))
    return options, args

def main():
    global game
    opts, args = parse_args()
    game = Game(fullscreen=opts.fullscreen, resolution=opts.resolution,
        display_fps=opts.framerate)
    game.run()

if __name__ == '__main__':
    main()
