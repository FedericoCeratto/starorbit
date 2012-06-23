#!/usr/bin/env python

# Star Orbit game
# Copyright (C) 2012 Federico Ceratto
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

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

from units import degrees, radians, seconds, degrees_per_sec
from vectors import Vector, PVector
from sound import SoundPlayer

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
    def __init__(self, fname, raw_scale):
        self._angle = 0
        gloss.Sprite.__init__(self, gloss.Texture(fname))
        self._raw_scale = raw_scale
        self._raw_rotation = 0.0

    def _recenter(self):
        """Update sprite rect based on screen offset and image size"""
        self.move_to(*self.gcenter.on_screen)

    def update(self):
        self._recenter()

    def draw(self):
        """Draw on screen"""
        angle = getattr(self, '_angle', 0.0)
        gloss.Sprite.draw(self, scale=self._raw_scale * game.zoom,
            rotation=angle, origin=None)


class Orbit(object):
    """Starship orbit"""
    def __init__(self):
        self.gcenter = GVector(0, 0)
        self._alpha = 0
        self._fading = 'in' # 'in', 'out', None
        self._orbit = ()
        self._color = gloss.Color(1, 1, 1, .2)

    def fade_in(self, orbit):
        """Start fading in a new orbit"""
        self._orbit = [o[0] for o in orbit]
        self._fading = 'in'

    def fade_out(self):
        """Start fading out the orbit"""
        self._fading = 'out'

    def update(self):

        if self._fading == 'in':
            self._alpha += .01
            if self._alpha > .2:
                self._alpha = .2
                self._fading = None
            self._color = gloss.Color(1, 1, 1, self._alpha)

        elif self._fading == 'out':
            self._alpha -= .01
            if self._alpha < 0:
                self._alpha = 0
                self._fading = None
            self._color = gloss.Color(1, 1, 1, self._alpha)

    def draw(self):
        """Draw orbit"""
        if not self._orbit:
            return

        p_orbit = [o.on_screen for o in self._orbit]
        gloss.Gloss.draw_lines(
            p_orbit,
            color=self._color,
            width=game.zoom * 1,
            join=False
        )

class BlackBackground(object):
    """Black background, below the star backdrop"""

    def update(self):
        pass

    def draw(self):
        """Draw on screen"""
        gloss.Gloss.draw_box(
            position = (0, 0),
            width = game.resolution[0],
            height = game.resolution[1],
            color = gloss.Color(0, 0, 0, 1),
        )

class Background(Sprite):
    def __init__(self):
        Sprite.__init__(self, 'space_dim.jpg', 1)
        self.gcenter = GVector(0, 0)

class BlackOverlay(object):
    """Black overlay used to fade to black"""
    def __init__(self):
        self._alpha = 0
        self._fading = 0

    def update(self):
        #FIXME: deltat
        if self._fading:
            self._alpha += self._fading
            if self._alpha < 0:
                self._alpha = 0
                self._fading = 0
            elif self._alpha > 1:
                self._angle = 1
                self._fading = 0

    def fade_to_black(self, speed=.01):
        self._fading = speed

    def set_to_black(self):
        self._alpha = 1
        self._fading = 0

    def fade_in(self, speed=.01):
        self._fading = -speed

    def draw(self):
        """Draw on screen"""
        if self._alpha:
            gloss.Gloss.draw_box(
                position = (0, 0),
                width = game.resolution[0],
                height = game.resolution[1],
                color = gloss.Color(0, 0, 0, self._alpha),
            )

class Circle(Sprite):
    def __init__(self):
        Sprite.__init__(self, 'art/circle_cyan.png', 1)
        self.gcenter = GVector(0, 0)

    def update(self):
        self.gcenter = game._ship.gcenter - GVector(10, 10)
        self._recenter()


class Satellite(Sprite):
    def __init__(self):
        Sprite.__init__(self, 'art/blue_sun.png', .01)
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

    def _predict_orbit_chunk(self):
        """Predict object orbit"""
        if len(self.orbit) == 0:
            self.orbit = [(self.gcenter, self.gspeed)]

        initial_gcenter = self.orbit[0][0]
        gcenter, gspeed = self.orbit[-1]

        for x in xrange(100):
            gspeed += self._calculate_acceleration(gcenter, self.mass)
            gcenter += gspeed

            if len(self.orbit) > 10:
                if gcenter.distance(initial_gcenter) < 6:
                    self.orbit.append((gcenter, gspeed))
                    self._orbit_prediction_running = False
                    game.orbit.fade_in(self.orbit)
                    return

            if gcenter.distance(self.orbit[-1][0]) > 5:
                self.orbit.append((gcenter, gspeed))
                if len(self.orbit) > 500:
                    self._orbit_prediction_running = False
                    game.orbit.fade_in(self.orbit)
                    return


class Sun(Sprite):
    def __init__(self, gcenter=None):
        Sprite.__init__(self, 'art/space_planet.png', .02)
        if gcenter:
            self.gcenter = gcenter
        else:
            self.gcenter = GVector(400, 300)
        self.gspeed = GVector(0, 0)
        self.mass = 4

class Starship(Satellite):
    def __init__(self, gcenter):
        gloss.Sprite.__init__(self, gloss.Texture('art/shuttle.png'))
        self._angle = degrees(0)
        self._target_angle = degrees(0)
        self._angular_velocity = degrees_per_sec(0)
        self._orbit_prediction_thread = None
        self._orbit_prediction_running = False
        self._raw_scale = .0025
        self._tp = None
        self.gcenter = gcenter
        self.gspeed = GVector(0, -0.3)
        self.mass = 4
        self.orbit = ()
        self.propellent = 1500
        self.hull_temperature = 0
        self._start_orbit_prediction()

    def _update_temperature(self):
        """Calculate temperature increase/decrease"""
        dt = -1
        for sun in game._suns:
            distance = self.gcenter.distance(sun.gcenter)
            dt += 10000 / distance ** 2

        if dt < 0 and self.hull_temperature < 0:
            return

        self.hull_temperature += dt

    def update(self):
        """Plot orbit, move ship"""
        if self._orbit_prediction_running:
            self._predict_orbit_chunk()

        self.gspeed += self._calculate_acceleration(self.gcenter, self.mass)
        self.gcenter += self.gspeed * game.speed
        self._rotate()
        self._update_temperature()
        self._recenter()

    def fire_thruster(self):
        """Fire thruster"""
        self.propellent -= 10
        thrust = GVector(.5, 0)
        thrust.angle_cw_degs = self._angle
        print self._angle, repr(thrust), thrust.angle, thrust.angle_cw_degs
        self.gspeed += thrust
        self._start_orbit_prediction()
        self._tp = Thruster(self.gcenter, thrust)
        game._particles.append(self._tp)

    def _start_orbit_prediction(self):
        game.orbit.fade_out()
        self._orbit_prediction_running = True
        self.orbit = []

    def set_target_angle(self, vector):
        """Set ship target angle. Side thrusters will be engaged to
        rotate it
        """
        self._target_angle = vector.angle_cw_degs.opposite

    def _rotate(self):
        """Control yaw Reaction control system
        based on angle, angular velocity and target angle
        """
        #TODO deltat
        self._angle += self._angular_velocity * seconds(1)
        self.yaw_rcs_status = ''

        signed_delta = float(self._target_angle - self._angle)
        # signed_delta is defined between -180 and 180
        if signed_delta > 180:
            signed_delta -= 360

        if abs(signed_delta) < 1:
            # rotation completed
            self._angular_velocity = degrees_per_sec(0)
            self._angle = self._target_angle
            return

        av = self._angular_velocity
        # momentum should be degrees per (sec ** 2)
        momentum = degrees_per_sec(math.copysign(.1, signed_delta))

        if av != 0 and math.sqrt(2 * abs(signed_delta) / .1) > abs(signed_delta / av):
            # closing too fast - better slow down
            self._angular_velocity -= momentum
            self.yaw_rcs_status = 'YAW CCW' if av > 0 else 'YAW CW'
        else:
            # increase speed
            self._angular_velocity += momentum
            self.yaw_rcs_status = 'YAW CW' if av > 0 else 'YAW CCW'


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


class Debris(PSystem):
    def __init__(self, gcenter):
        texture = pygame.Surface(size=(1,1))
        texture = gloss.Texture("art/red_dot.png")
        wind = gcenter - game._suns[0].gcenter
        wind.modulo = 100
        self._ps = gloss.ParticleSystem(
            texture,
            onfinish = self._finished,
            position = gcenter.on_screen.tup,
            name = "fire",
            initialparticles = 1,
            particlelifespan = 275,
            wind = map(int, wind.tup),
            minspeed = 10,
            maxspeed = 20,
            minscale = game.zoom * .1,
            maxscale = game.zoom * .1,
            startcolor = Color(1, 0, 0, 1),
            endcolor = Color(1, 1, 0, 0),
        )


class Thruster(PSystem):
    def __init__(self, gcenter, thrust):
        self.gcenter = gcenter
        tex = gloss.Texture("smoke.tga")

        wind = PVector(game.zoom * 38, 0)
        wind.angle_cw_degs = 360 - thrust.angle
        wind = wind.round_tup

        self._ps = gloss.ParticleSystem(
            tex,
            onfinish = self._finished,
            position = gcenter.on_screen.tup,
            name = "smoke",
            initialparticles = 10,
            particlelifespan = 90,
            growth = .8,
            wind = wind,
            minspeed = 1,
            maxspeed = 5,
            minscale = game.zoom * .05,
            maxscale = game.zoom * .1,
            startcolor = Color(1, 1, 1, 1),
            endcolor = Color(1, 1, 1, 0),
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
        self._color = color

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
        self._display_fps = display_fps
        self.speed = 1
        self.zoom = 1
        self._zoom_level = 3.9
        self.changed_scale = True
        self.gcamera = GVector(0, 0)

        # load sounds
        self.soundplayer = SoundPlayer()

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
        self._presolution = PVector(self.resolution)

    def _change_resolution(self, resolution):
        """Change screen resolution"""
        self.resolution = resolution
        Gloss.screen_resolution = resolution.tup
        self._display_s = pygame.display.set_mode(resolution,
            pygame.RESIZABLE | pygame.DOUBLEBUF | pygame.OPENGL)
        self._background = pygame.image.load('space_dim.jpg')
        self._background = pygame.transform.smoothscale(self._background,
            resolution)
        self.changed_scale = True #FIXME: remove changed_scale everywhere
        self._presolution = PVector(self.resolution)

    def _zoom_in(self):
        self._zoom_level -= .2
        if pygame.KMOD_CTRL & pygame.key.get_mods():
            self._zoom_level -= .8
        if self._zoom_level < .01:
            self._zoom_level = .01

    def _zoom_out(self):
        self._zoom_level += .2
        if pygame.KMOD_CTRL & pygame.key.get_mods():
            self._zoom_level += .8

    def _update_zoom(self):
        # I have no idea what i'm doing
        zoom = 32 * math.atan(1/self._zoom_level)
        if self.zoom != zoom:
            self.zoom += (zoom - self.zoom) / 10
            self.changed_scale = True

    def _impulse(self):
        """Fire thrusters for one impulse"""
        if self._ship.propellent:
            self._ship.fire_thruster()
        else:
            pass #TODO: add error sound

    def _rotate_ship(self):
        """Fire side thrusters to rotate ship"""
        if self._ship.propellent:
            mpos = pygame.mouse.get_pos()
            thrust = self._ship.gcenter.on_screen - PVector(mpos)
            self._ship.set_target_angle(thrust.normalized())
        else:
            pass #TODO: add error sound

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
        elif event.button == 3: # right click
            self._rotate_ship()

    def _keypress(self, event):
        if event.key == 27:
            # quit on Esc key or window closing
            pygame.quit()
            sys.exit()
        elif event.unicode == u' ':
            self.soundplayer.play('thruster')
            self._impulse()

        #FIXME: remove test sounds
        elif event.unicode == u'g':
            self.soundplayer.play('gear')
        elif event.unicode == u'b':
            self.soundplayer.play('beep')

    def load_content(self):
        """Load images, create game objects"""
        self._font = gloss.SpriteFont(
            '/usr/share/fonts/truetype/freefont/FreeSans.ttf', 10)

        self._below_background = BlackBackground()
        self._background = Background()
        self.orbit = Orbit()
        self._suns = [Sun(gcenter=GVector(100, -100)), ]
        self._satellites = [Satellite() for x in xrange(10)]
        for s in self._satellites:
            s.place_in_orbit(self._suns[0])
        self._circles = [Circle(), ]
        self._circles = []
        self._particles = []
        self._ship = Starship(GVector(-100, 100))
        self._ship.place_in_orbit(self._suns[0])

        self._bars = [
            HBar(self._ship, 'propellent', .05, gloss.Color(0, 1, 0, .6), vmax=1500),
            HBar(self._ship, 'hull_temperature', .40, gloss.Color(1, 0, 0, .6), vmax=1500),
        ]
        self._black_overlay = BlackOverlay()
        self._black_overlay.set_to_black()
        self._black_overlay.fade_in()

    def _add_solar_debris(self):
        """Add debris caused by sun"""
        if Gloss.tick_count % 10 != 0:
            return
        gc = self._ship.gcenter + self._ship.gspeed * (random.random() - 1) * 3 
        self._particles.append(Debris(gc))

    def draw(self):
        """Main game loop: update game objects, handle zoom and pan, finally
        draw to screen
        """
        self._update_zoom()

        k = min(1, self.zoom / 10)
        self.gcamera = self._ship.gcenter * k + self._suns[0].gcenter * (1 - k)

        self._add_solar_debris()
        self.changed_scale = True
        layers = (
            '_below_background',
            '_background',
            '_suns',
            '_satellites',
            '_particles',
            'orbit',
            '_circles',
            '_ship',
            '_black_overlay',
            '_bars'
        )

        for l in layers:
            items = getattr(self, l)
            if isinstance(items, list):
                [i.update() for i in items]
            else:
                items.update()

        for l in layers:
            items = getattr(self, l)
            if isinstance(items, list):
                [i.draw() for i in items]
            else:
                items.draw()

        self._draw_bottom_right_text("%06.2f" % self._ship._angle, 50)
        self._draw_bottom_right_text("%06.2f" % self._ship.gspeed.angle_cw_degs, 100)
        self._draw_bottom_right_text("%06.2f" % self._ship.gspeed.modulo, 150)
        self._draw_bottom_right_text(self._ship.yaw_rcs_status, 220)

        if self._display_fps:
            fps = 1/gloss.Gloss.elapsed_seconds
            self._font.draw("%.2f" % fps, scale = 1,
                color = gloss.Color.BLUE, letterspacing = 0, linespacing = -25)

    def _draw_bottom_right_text(self, text, y):
        """Draw gray metrics"""
        self._font.draw(text, scale = 1,
            position = self._presolution - PVector(y, 15),
            color = gloss.Color(1, 1, 1, .5),
            letterspacing = 0,
            linespacing = -25
        )


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
