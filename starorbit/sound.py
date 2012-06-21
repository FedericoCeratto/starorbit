import pygame

class SoundPlayer(object):
    """Sound player: generate sounds and music"""
    def __init__(self):
        self._sounds = {}
        self._sounds_max_vol = {}
        pygame.mixer.init()
        sounds = (
            # mission sounds
            ('discovery_meco', 'NASA_discovery_meco', .5),
            ('discovery_vector_transfer', 'NASA_discovery_vector_transfer', .5),
            ('wheelstop', 'NASA_discovery_wheelstop', .5),
            ('gear', 'NASA_shuttle_gear', .5),
            ('planet', 'NASA_cassini_saturn', .5),
            ('thruster', 'NASA_thruster', .7),
            # background sounds
            ('beep', 'NASA_beep', .2),
        )
        for name, fname, max_vol in sounds:
            self._sounds[name] = pygame.mixer.Sound("sound/%s.ogg" % fname)
            self._sounds_max_vol[name] = max_vol

    def play(self, name):
        """Play a sound"""
        self._sounds[name].set_volume(self._sounds_max_vol[name])
        self._sounds[name].play()

    def fadeout(ms=100):
        for s in self._sounds:
            s.fadeout(ms)
