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

from gloss import Gloss, GlossGame
from optparse import OptionParser
from pygame.locals import *
from time import time
from threading import Thread
import gloss
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


class SVector(Vector):
    """2D vector, as it appears on the screen
    e.g. SVector(0, 0) is always the topleft corner of the screen
    """
    @property
    def gvector(self):
        """Equivalent GVector"""
        pv = PVector(*self.tup) - game._screen_center + game.gcamera.pvector
        gv = pv / game.zoom
        return GVector(*gv.tup)


def distance(a, b):
    """Calculate distance between two points (tuples)"""
    d = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
    return d ** (.5)


class VectorDisplay(object):
    """Display vectors for debugging"""
    def __init__(self):
        self._items = []

    def show(self, start, end=None):
        """Display a cross or a vector between two points"""
        self._items.append((start, end, time()))

    def draw(self):
        """Draw items"""
        if not self._items:
            return

        newitems = []
        for start, end, tstamp in self._items:
            if tstamp + 1 > time():
                newitems.append((start, end, tstamp))
                if end:
                    self._plot_vector(start, end)
                else:
                    self._plot_cross(start)

        self._items = newitems

    def _plot_vector(self, start, end):
        """Plot a vector on the screen, applied to a starting position"""
        arrow = end - start
        tip_r = arrow.orthonormal() - arrow.normalized()
        tip_l = arrow.orthonormal() * -1  - arrow.normalized()
        tip_r *= 10
        tip_r += start
        gloss.Gloss.draw_lines(
            [start.on_screen, end.on_screen, tip_r.on_screen],
            color=gloss.Color(0, 1, 1, .5),
            width=1,
            join=False
        )

    def _plot_cross(self, start):
        """Plot a cross on the screen"""
        nodes = (
            start,
            start + GVector(size, 0),
            start + GVector(-size, 0),
            start,
            start + GVector(0, size),
            start + GVector(0, -size),
        )
        gloss.Gloss.draw_lines(
            [n.on_screen for n in nodes],
            color=gloss.Color(1, 1, 0, .1),
            width=1,
            join=False
        )


class MutePlayer(object):
    """Silent Sound Player, used to mute sound"""
    def __init__(self, *args, **kwargs):
        pass

    def play(self, *args, **kwargs):
        pass


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
        self._orbit = ()
        self._color = gloss.Color(1, 1, 1, .2)
        self._alpha_animator = animator_directional(maxv=.2, step=.01)
        self._alpha_animator.next()

    def fade_in(self, orbit):
        """Start fading in a new orbit"""
        self._orbit = [o[0] for o in orbit]
        self._fading = 'in'
        self._alpha_animator.send('up')

    def fade_out(self):
        """Start fading out the orbit"""
        self._alpha_animator.send('down')

    def update(self):

        alpha = self._alpha_animator.next()
        self._color = gloss.Color(1, 1, 1, alpha)

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
        Sprite.__init__(self, 'space_tileable.png', 1)

    def update(self):
        raise RuntimeError, "This must be used by Tiles"

    def draw(self, gc):
        """Draw on screen"""
        self.move_to(*gc.on_screen.tup)
        gloss.Sprite.draw(self, scale=self._raw_scale * game.zoom,
            origin=None)


class Tiles(object):
    """Manage tiled sprites
    """
    # each title is located by a (x, y) tuple in self._tiles
    # The central tile is at (0, 0)
    def __init__(self):
        self._tiles = {}
        self._basetile = Background()

    def _locate_tile(self, sv):
        """Given a point (in pixels on screen), locate the tile that contains
        it
        """
        gv = sv.gvector
        tile_width = self._basetile.texture.width
        tile_height = self._basetile.texture.height
        x = int(gv.x / tile_width)
        y = int(gv.y / tile_height)
        return (x, y)

    def _get_tile_center(self, x, y):
        """Given tile x, y coords, find the tile center
        """
        tile_width = self._basetile.texture.width
        tile_height = self._basetile.texture.height
        return GVector(tile_width * x, tile_height * y)

    def _find_displayed_tiles(self):
        """Find tiles that are currently visible
        """
        s_topleft = SVector(0, 0)
        s_bottomright = SVector(*game.resolution)
        ti_topleft = self._locate_tile(s_topleft)
        ti_bottomright = self._locate_tile(s_bottomright)

        for x in xrange(ti_topleft[0], ti_bottomright[0] + 1):
            for y in xrange(ti_topleft[1], ti_bottomright[1] + 1):
                if (x, y) not in self._tiles:
                    self._tiles[(x, y)] = self._get_tile_center(x, y)
                    #print ti_topleft, ti_bottomright, x,y, self._tiles[(x,y)]

    def update(self):
        self._find_displayed_tiles()

    def draw(self):
        """Draw displayed tiles"""
        for gc in self._tiles.itervalues():
            self._basetile.draw(gc)


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
        self._raw_scale = .025
        self._raw_scale = .015 # fixme
        self._tp = None
        self.gcenter = gcenter
        self.gspeed = GVector(0, -0.3)
        self.mass = 4
        self.orbit = ()
        self.propellent = 1500
        self.hull_temperature = 0
        self.landing_gears_deployed = False
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
        #print self._angle, repr(thrust), thrust.angle, thrust.angle_cw_degs
        self.gspeed += thrust
        self._start_orbit_prediction()
        t = Thruster(self.gcenter, thrust)
        game._particles.append(t)
        #game.vdebugger.show(self.gcenter, self.gspeed)


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

        if abs(signed_delta) < .1:
            # rotation completed
            self._angular_velocity = degrees_per_sec(0)
            self._angle = self._target_angle
            return

        av = self._angular_velocity
        # momentum should be degrees per (sec ** 2)
        momentum = degrees_per_sec(math.copysign(.1, signed_delta))

        if av != 0 and math.sqrt(2 * abs(signed_delta) / .1) > \
            1.05 * abs(signed_delta / av):
            # closing too fast - better slow down
            self._angular_velocity -= momentum
            cw = momentum < 0
        elif av == 0 or math.sqrt(2 * abs(signed_delta) / .1) < \
            0.95 * abs(signed_delta / av):
            # increase speed
            self._angular_velocity += momentum
            cw = momentum > 0
        else:
            return

        self.yaw_rcs_status = 'YAW CW' if cw else 'YAW CCW'
        t = RCSThruster(self, cw=cw)
        game._particles.append(t)

    def toggle_landing_gears(self):
        """Deploy/retract landing gear"""
        self.landing_gears_deployed ^= True
        game.soundplayer.play('gear')


class ShipReflex(Satellite):
    def __init__(self, ship, n, light_angle):
        gloss.Sprite.__init__(self, gloss.Texture('art/shuttle_light_%s.png' % n))
        self._ship = ship
        self.gspeed = ship.gspeed
        self.gcenter = ship.gcenter
        self.mass = 4
        self._raw_scale = .015 # fixme
        self._alpha = 0
        self._light_angle = degrees(light_angle)

    def update(self):
        self.gcenter = self._ship.gcenter
        self._angle = self._ship._angle
        self.gspeed = self._ship.gspeed
        self._recenter()

        mydir = GVector(1, 0)
        mydir.angle = (self._light_angle - self._angle).radians

        for sun in game._suns:
            light = self.gcenter - sun.gcenter
            dist = light.modulo
            if dist > 0:
                # scalar product
                alpha = (mydir * light.normalized())
                #alpha = (mydir * light.normalized()) / dist * 200
                alpha = max(0, min(1, alpha))
            else:
                alpha = 1

        self._alpha = alpha


    def draw(self):
        """Draw on screen"""
        angle = getattr(self, '_angle', 0.0)
        gloss.Sprite.draw(self, scale=self._raw_scale * game.zoom,
            rotation=angle, origin=None, color=gloss.Color(1,1,1,self._alpha))

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
        wind.modulo = 200
        self._ps = gloss.ParticleSystem(
            texture,
            onfinish = self._finished,
            position = gcenter.on_screen.tup,
            name = "fire",
            initialparticles = 1,
            particlelifespan = 275,
            wind = map(int, wind.tup),
            minspeed = 100,
            maxspeed = 300,
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
        wind.angle_cw_degs = thrust.angle_cw_degs
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


class RCSThruster(PSystem):
    """Propellent particles from the RCS nozzles"""
    def __init__(self, ship, cw=True):
        self.gcenter = ship.gcenter
        self._tex = gloss.Texture("smoke.tga")
        self._ps = [] # Running particle systems

        # Distance of the RCS thrusters from the ship center
        gdelta_front = GVector(3.5, 0)
        gdelta_front.angle_cw_degs = degrees(180) - ship._angle
        gdelta_rear = GVector(4, 0)
        gdelta_rear.angle_cw_degs = degrees(0) - ship._angle

        wind_front = PVector(100, 0)
        wind_rear = PVector(200, 0)

        if cw:
            wind_front.angle_cw_degs = degrees(270) - ship._angle
            wind_rear.angle_cw_degs = degrees(90) - ship._angle
        else:
            wind_front.angle_cw_degs = degrees(90) - ship._angle
            wind_rear.angle_cw_degs = degrees(270) - ship._angle

        self._create_particles(ship.gcenter + gdelta_front, wind_front)
        self._create_particles(ship.gcenter + gdelta_rear, wind_rear)

    def _create_particles(self, gpos, wind):
        ps = gloss.ParticleSystem(
            self._tex,
            onfinish = self._finished,
            position = gpos.on_screen.tup,
            name = "smoke",
            initialparticles = 5,
            particlelifespan = 90,
            growth = .8,
            wind = wind,
            minspeed = 1,
            maxspeed = 5,
            minscale = game.zoom * .005,
            maxscale = game.zoom * .007,
            startcolor = Color(1, 1, 1, 1),
            endcolor = Color(1, 1, 1, 0),
        )
        self._ps.append(ps)

    def draw(self):
        for ps in self._ps:
            ps.draw()

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

def animator(maximum, step=1):
    """Increase a counter on each call and reset it every time it reaches a
    maximum"""
    cnt = 0
    while True:
        yield cnt
        cnt = (cnt + step) % maximum

def animator_directional(minv=0, maxv=1, startv=0, step=.1, direction='up'):
    """Increase or decrease a counter on each call between a min and max
    value"""
    val = startv
    while True:
        if direction == 'up':
            val += step
            if val > maxv:
                val = maxv
                direction = 'stop'
        elif direction == 'down':
            val -= step
            if val < minv:
                val = minv
                direction = 'stop'
        newdir = (yield val)
        if newdir in ('up', 'down', 'stop'):
            direction = newdir


class Menu(object):
    """Hovering menu"""
    def __init__(self, game):
        self._game = game
        self._starting_position = PVector(game.resolution.x / 2,
        game.resolution.y / 4)
        # Line spacing: a vertical vector, based on the resolution
        self._line_spacing = PVector(0, game.resolution.y) / 20
        # Font size based on resolution
        self._fontsize = int(game.resolution.modulo / 40)
        self._animate_glow = animator(math.pi * 2, .05)
        self._options = {
            'main menu': (
                ('play game', '_play'),
                ('help', '_help'),
                ('exit', '_exit_game'),
            ),
            'in-game menu': (
                ('back to game', '_back_to_game'),
                ('exit', '_exit_game'),
            ),
            'help': (
                ("Space - fire thruster\nRight click - Yaw control\n" +
                "g - Toggle landing gears\nb - Beep\nMouse wheel - zoom\n" +
                "Ctrl-mouse-wheel - faster zoom", None),
                ('back', '_back_to_main_menu'),
            ),
        }
        self._selected_option = 0
        self._text = """StarOrbit Menu\n\n\n"""
        self.mode = 'main menu'

    def _setup_font(self):
        """Setup font. It must be done after Gloss has been initialized.."""
        self._font = gloss.SpriteFont(
            '/usr/share/fonts/truetype/freefont/FreeSans.ttf',
            self._fontsize
        )
        #pygame.font.SysFont try this

    def up(self):
        """Move up one item"""
        self._selected_option -= 1
        self._selected_option %= len(self._options[self.mode])

    def down(self):
        """Move down one item"""
        self._selected_option += 1
        self._selected_option %= len(self._options[self.mode])

    def enter(self):
        """Handle Enter keypress"""
        action = self._options[self.mode][self._selected_option][1]
        if action is None:
            return
        method = getattr(self, action)
        method()

    def _play(self):
        """Start game"""
        self.mode = 'play'
        #TODO: setup new level

    def _back_to_game(self):
        """Go back to game"""
        self.mode = 'play'

    def _back_to_main_menu(self):
        """Go back to main menu"""
        self.mode = 'main menu'

    def _help(self):
        """Show help menu"""
        self.mode = 'help'

    def _center(self, line):
        """ """
        w = self._font.font.size(line)[0]
        return PVector(w/2, 0)

    @property
    def active(self):
        """Return True if the Menu should be displayed"""
        return not self.mode == 'play'

    def draw(self):
        """Draw on screen"""
        try:
            self._font
        except:
            self._setup_font()

        # Build menu text
        text = self._text
        for n, item in enumerate(self._options[self.mode]):
            t = item[0] # Text
            if n == self._selected_option and item[1]:
                text += " [%s]\n" % t
            else:
                text += "  %s\n" % t

        # Draw lines
        anim = self._animate_glow.next()
        for n, line in enumerate(text.split('\n')):
            alpha_sin = math.sin(anim + .4 * n)
            alpha = .6 + .2 * alpha_sin
            p = self._starting_position + self._line_spacing * n
            p -= self._center(line)
            #print p
            self._draw_line(line, p, alpha)


    def _draw_line(self, text, p, alpha):
        """Draw a menu line"""
        self._font.draw(
            text,
            position = p,
            color = gloss.Color(1, 1, 1, alpha),
            letterspacing = 0,
            linespacing = 0
        )

    def keypress(self, event):
        """Handle keys pressed in Menu mode"""
        if event.key == K_ESCAPE:
            self._exit_game()
        elif event.key == K_UP:
            self.up()
        elif event.key == K_DOWN:
            self.down()
        elif event.key == K_RETURN:
            self.enter()

    def _exit_game(self):
            pygame.quit()
            sys.exit()



class Game(gloss.GlossGame):
    def __init__(self, fullscreen=False, resolution=None, display_fps=False,
        sound=True):
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
        if sound:
            self.soundplayer = SoundPlayer()
        else:
            self.soundplayer = MutePlayer()

        # event handlers
        self.on_mouse_down = self._mouse_click
        self.on_mouse_motion = lambda x: x
        self.on_key_down = self._keypress

        self._menu = Menu(self)
        self.vdebugger = VectorDisplay()

    def draw_loading_screen(self):
        """Display an intro image while loading sprites"""
        s = gloss.Sprite(gloss.Texture('art/loading.png'))
        gloss.Sprite.draw(s, scale=self.resolution.x / 800.0)

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
        """Zoom in"""
        if pygame.KMOD_CTRL & pygame.key.get_mods():
            self._zoom_level -= 2
        else:
            self._zoom_level -= .4

        if self._zoom_level < .1:
            self._zoom_level = .1

    def _zoom_out(self):
        """Zoom out"""
        if self._zoom_level > 40:
            return

        if pygame.KMOD_CTRL & pygame.key.get_mods():
            self._zoom_level += 2
        else:
            self._zoom_level += .4

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

        #FIXME raise RuntimeError, "Unable to kill %s" % repr(victim)

    def _mouse_click(self, event):
        """Handle mouse clicks and wheel movement during game"""
        if not self._menu.mode == 'play':
            return

        self.changed_scale = False
        if event.button == 4: # wheel up
            self._zoom_in()
        elif event.button == 5: # wheen down
            self._zoom_out()
        elif event.button == 3: # right click
            self._rotate_ship()

    def _keypress(self, event):
        """Handle keys pressed"""
        if self._menu.mode == 'play':
            self._in_game_keypress(event)
        else:
            self._menu.keypress(event)

    def _in_game_keypress(self, event):
        """Handle keys pressed during game"""
        if event.key == K_ESCAPE:
            # Go to in-game menu
            self._menu.mode = 'in-game menu'

        elif event.key == K_SPACE:
            self.soundplayer.play('thruster')
            self._impulse()

        #FIXME: remove test sounds
        elif event.unicode == u'g':
            self._ship.toggle_landing_gears()
        elif event.unicode == u'b':
            self.soundplayer.play('beep')


    def load_content(self):
        """Load images, create game objects"""
        self._font = gloss.SpriteFont(
            '/usr/share/fonts/truetype/freefont/FreeSans.ttf', 10)

        self._background_tiles = Tiles()
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
        self._ship_reflexes = [ShipReflex(self._ship, n, angle)
            for n, angle in (
                ('l', 90),
                ('t', 0),
                ('b', 180),
                ('r', -90),
            )
        ]

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
        self._background_tiles.update()

        self._add_solar_debris()
        self.changed_scale = True
        layers = (
            '_background_tiles',
            '_suns',
            '_satellites',
            '_particles',
            'orbit',
            '_circles',
            '_ship',
            '_ship_reflexes',
            '_black_overlay',
            '_bars'
        )

        # update all layers
        for l in layers:
            items = getattr(self, l)
            if isinstance(items, list):
                [i.update() for i in items]
            else:
                items.update()

        # draw all layers
        for l in layers:
            items = getattr(self, l)
            if isinstance(items, list):
                [i.draw() for i in items]
            else:
                items.draw()

        # draw dashboard text
        self._draw_bottom_right_text("%06.2f" % self._ship._angle, 50)
        self._draw_bottom_right_text("%06.2f" % self._ship.gspeed.angle_cw_degs, 100)
        self._draw_bottom_right_text("%06.2f" % self._ship.gspeed.modulo, 150)
        self._draw_bottom_right_text(self._ship.yaw_rcs_status, 220)
        landing_gear = 'LG' if self._ship.landing_gears_deployed else ''
        self._draw_bottom_right_text(landing_gear, 240)

        if self._display_fps:
            fps = 1/gloss.Gloss.elapsed_seconds
            self._font.draw("%.2f" % fps, scale = 1,
                color = gloss.Color.BLUE, letterspacing = 0, linespacing = -25)

        # draw debug items
        self.vdebugger.draw()

        # draw menu
        if self._menu.active:
            self._menu.draw()

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
    parser.add_option("--no-sound", dest="sound",
        action="store_false", help="Disable sound", default=True)
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
        display_fps=opts.framerate, sound=opts.sound)
    game.run()

if __name__ == '__main__':
    main()
