import glob
import os
import random

import pygame

from cruel.core import paths
from cruel.audio.clausthy_loop import LoopingMusic
from cruel.audio.clausthy_sfx import SoundVariations

"""
Music and sound effects. The music was made in Clausthy's Loop Studio and is played by cruel/audio/clausthy_loop.py; the
sound effects come from Clausthy's SFX Lab and are played by cruel/audio/clausthy_sfx.py (a random variation
each time, so repeats don't sound robotic).

  - The title screen plays the menu theme: its intro once, then the loop forever with no gap.
  - In a run, the game music plays quietly underneath (GAME_THEME_VOLUME). Every track in music/gameMusic/ (each in
    its own folder with its .json) is in the playlist: one is picked at random as the run starts and fades in as
    the menu theme fades out. After TRACK_MINUTES it fades out and a different one fades in. Going back to the
    title fades it out. A new track only needs its folder dropped into music/gameMusic/.
  - In a Metropolis the city's own music plays instead: the tracks in music/metropolis/ (set by setCity). Walking
    into a city fades the game track out and a city track in; leaving fades back to the game music.
  - A Bomb going off plays the explosion, and every swing at a wall plays a hit.
  - Now and then in a run (every AMBIENCE_GAP seconds, picked at random each time), one of the sounds in
    music/ambience/ plays quietly: a drip somewhere in the dark. Each sound has its own folder with its _sfx.json;
    a new one only needs its folder dropped in.

The volumes come from the Sound settings: Master x Music for the music, Master x Effects for sound effects, or
nothing when muted. If the computer has no audio device, or the files are missing, the game just runs silently.
"""

MENU_THEME = "music/mainMenuTheme/dungeon_depths.json"
GAME_MUSIC = "music/gameMusic"  # one folder per track, each with its .json
CITY_MUSIC = "music/metropolis"  # the Metropolis's theme: one folder per track, each with its .json
EXPLOSION = "music/soundEffects/explosion/explosion_sfx.json"
HIT = "music/soundEffects/hit/hit_sfx.json"
AMBIENCE = "music/ambience"  # one folder per sound, each with its _sfx.json
AMBIENCE_GAP = (45, 100)     # seconds between two ambient sounds: a random time in this range each time
AMBIENCE_VOLUME = 0.6        # ambient sounds play at this much of the effects volume
MENU_CHANNEL = 0    # these two are reserved for music, so a sound effect can never take one over
GAME_CHANNEL = 1
FADE_MS = 800       # the menu theme fades out over this long
GAME_FADE_IN_MS = 2500  # a game track comes in slowly
GAME_FADE_OUT_MS = 2500  # and goes out slowly when it's time for the next one
TRACK_MINUTES = 4   # how long one game track plays (looping) before the next one
GAME_THEME_VOLUME = 0.35  # the game music plays at this much of the music volume, so it stays in the background


class Sound():
    def __init__(self, settings):
        self.settings = settings
        self.menuTheme = self.explosion = self.hit = None
        self.ambience = []      # the ambient sounds (SoundVariations), one per folder in music/ambience/
        self.nextAmbience = None  # when the next ambient sound plays (pygame ticks), while in a run
        self.gameTracks = []    # every game track that loaded (LoopingMusic)
        self.cityTracks = []    # every Metropolis track that loaded: they play instead while you're in a city
        self.inCity = False     # you're in a Metropolis (setCity)
        self.gameTheme = None   # the one playing now
        self.inRun = False      # game music is wanted (between playGameTheme and stopGameTheme)
        self.trackStart = 0     # when the current game track started (pygame ticks)
        self.switching = False  # the current track is fading out to make way for the next
        self.gameFadeStart = None  # when the game track started fading in (pygame ticks), while it is
        self.sampleChannel = None  # the last Effects Volume sample, so holding the key doesn't stack them up
        self.problem = ""  # why there's no sound, if there isn't any (shown on the Sound settings page)
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100)
            pygame.mixer.set_reserved(GAME_CHANNEL + 1)
        except pygame.error:
            self.problem = "No audio device found"
            return
        self.silence = self.makeSilence()
        self.menuTheme = self.loadMusic(MENU_THEME, MENU_CHANNEL)
        self.gameTracks = self.loadTracks(GAME_MUSIC)
        self.cityTracks = self.loadTracks(CITY_MUSIC)
        self.explosion = self.loadEffect(paths.resourcePath(EXPLOSION))
        self.hit = self.loadEffect(paths.resourcePath(HIT))
        for manifest in sorted(glob.glob(os.path.join(paths.resourcePath(AMBIENCE), "*", "*.json"))):
            sound = self.loadEffect(manifest, AMBIENCE_VOLUME)
            if sound is not None:
                self.ambience.append(sound)

    def loadEffect(self, manifest, share=1.0):
        """A sound effect (SoundVariations), or None if its files are missing. share: how much of the effects volume
        it plays at (kept on it, so applyVolume can set it again)."""
        try:
            sound = SoundVariations(manifest, volume=self.effectsVolume() * share)
        except (OSError, KeyError, ValueError, pygame.error):
            self.problem = "Sound files not found"
            return None
        sound.share = share
        return sound

    def makeSilence(self):
        """A hundredth of a second of nothing. pygame plays a channel's queued sound when the channel stops, even after
        a fade-out or stop(), and the looping music always has the next loop queued. So before stopping, the queue
        gets this instead: the fade ends, the silence plays, and then the channel really is quiet."""
        frequency, sampleFormat, channels = pygame.mixer.get_init()
        return pygame.mixer.Sound(buffer=bytes((frequency // 100) * channels * (abs(sampleFormat) // 8)))

    def loadTracks(self, folder):
        """Every track in folder (one folder per track, each with its .json) that loads, on the game music channel."""
        tracks = []
        for manifest in sorted(glob.glob(os.path.join(paths.resourcePath(folder), "*", "*.json"))):
            track = self.loadMusic(manifest, GAME_CHANNEL)
            if track is not None:
                tracks.append(track)
        return tracks

    def loadMusic(self, manifest, channel):
        try:
            return LoopingMusic(paths.resourcePath(manifest), channel=pygame.mixer.Channel(channel), volume=0.0)
        except (OSError, KeyError, ValueError, pygame.error):
            self.problem = "Music files not found"
            return None

    def musicVolume(self):
        """0.0 to 1.0: what the menu theme plays at with the current settings."""
        if self.settings.muted:
            return 0.0
        return (self.settings.masterVolume / 100) * (self.settings.musicVolume / 100)

    def gameThemeVolume(self):
        """The game theme's volume right now: quieter than the menu theme, and lower still while it fades in."""
        volume = self.musicVolume() * GAME_THEME_VOLUME
        if self.gameFadeStart is not None:
            progress = (pygame.time.get_ticks() - self.gameFadeStart) / GAME_FADE_IN_MS
            if progress >= 1:
                self.gameFadeStart = None
            else:
                volume *= max(0.0, progress)
        return volume

    def effectsVolume(self):
        if self.settings.muted:
            return 0.0
        return (self.settings.masterVolume / 100) * (self.settings.effectsVolume / 100)

    def applyVolume(self):
        """Call after changing a volume setting: everything changes right away."""
        if self.menuTheme is not None:
            self.menuTheme.set_volume(self.musicVolume())
        if self.gameTheme is not None:
            self.gameTheme.set_volume(self.gameThemeVolume())
        for sound in [self.explosion, self.hit] + self.ambience:
            if sound is not None:
                sound.set_volume(self.effectsVolume() * sound.share)

    def stopTheme(self, theme):
        if theme is not None and theme.is_playing:
            theme.channel.queue(self.silence)  # replaces the queued loop (see makeSilence)
            theme.stop(fade_ms=FADE_MS)

    def playMenuTheme(self):
        if self.menuTheme is not None and not self.menuTheme.is_playing:
            self.menuTheme.set_volume(self.musicVolume())
            self.menuTheme.play()

    def stopMenuTheme(self):
        self.stopTheme(self.menuTheme)

    def playGameTheme(self):
        """A run started: a random game track fades in (unless one is already playing), and the ambient sounds
        start their timer."""
        self.inRun = True
        self.scheduleAmbience()
        if self.gameTheme is None or not self.gameTheme.is_playing:
            self.startNextTrack()

    def playlist(self):
        """The tracks to pick from now: the city's in a Metropolis (if it has any), the game music anywhere else."""
        return self.cityTracks if self.inCity and self.cityTracks else self.gameTracks

    def setCity(self, inCity):
        """Call every frame with whether you're in a Metropolis. When that changes, the track playing fades out and
        one from the other playlist fades in."""
        if inCity == self.inCity:
            return
        self.inCity = inCity
        if self.inRun and not self.switching and self.gameTheme is not None and self.gameTheme.is_playing                 and self.gameTheme not in self.playlist():
            self.fadeOutForNext()

    def fadeOutForNext(self):
        """The track playing fades out; update starts the next one once it's quiet."""
        self.switching = True
        self.gameFadeStart = None
        self.gameTheme.channel.queue(self.silence)  # (see makeSilence)
        self.gameTheme.stop(fade_ms=GAME_FADE_OUT_MS)

    def startNextTrack(self):
        """Fades in a track from the playlist picked at random, not the one that just played (unless it's the only
        one)."""
        tracks = self.playlist()
        choices = [t for t in tracks if t is not self.gameTheme] or tracks
        if not choices:
            return
        self.gameTheme = random.choice(choices)
        self.switching = False
        self.trackStart = self.gameFadeStart = pygame.time.get_ticks()
        self.gameTheme.set_volume(0.0)
        self.gameTheme.play()

    def stopGameTheme(self):
        self.inRun = self.switching = False
        self.gameFadeStart = None
        self.stopTheme(self.gameTheme)

    def scheduleAmbience(self):
        self.nextAmbience = pygame.time.get_ticks() + int(random.uniform(*AMBIENCE_GAP) * 1000)

    def playHit(self):
        """A swing at a wall."""
        if self.hit is not None:
            self.hit.play()

    def playExplosion(self, sample=False):
        """A Bomb went off. sample: just letting you hear the Effects Volume, skipped while the last sample still plays."""
        if self.explosion is None:
            return
        if sample and self.sampleChannel is not None and self.sampleChannel.get_busy():
            return
        channel = self.explosion.play()
        if sample:
            self.sampleChannel = channel

    def update(self):
        """Once per frame: keeps the loops queued so they repeat without a gap, and fades the game theme in."""
        if self.menuTheme is not None:
            self.menuTheme.update()
        if not self.inRun:
            return
        if self.ambience and self.nextAmbience is not None and pygame.time.get_ticks() >= self.nextAmbience:
            random.choice(self.ambience).play()
            self.scheduleAmbience()
        if self.gameTheme is None:
            return
        self.gameTheme.update()
        if self.switching:
            if not self.gameTheme.channel.get_busy():  # the old track has faded out: in comes the next
                self.startNextTrack()
        elif pygame.time.get_ticks() - self.trackStart >= TRACK_MINUTES * 60000 and len(self.playlist()) > 1:
            self.fadeOutForNext()
        elif self.gameFadeStart is not None and self.gameTheme.is_playing:
            self.gameTheme.set_volume(self.gameThemeVolume())
