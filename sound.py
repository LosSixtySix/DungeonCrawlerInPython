import glob
import os
import random

import pygame

import paths
from music.clausthy_loop import LoopingMusic
from music.clausthy_sfx import SoundVariations

"""
Music and sound effects. The music was made in Clausthy's Loop Studio and is played by music/clausthy_loop.py; the
sound effects come from Clausthy's SFX Lab and are played by music/clausthy_sfx.py (a random variation
each time, so repeats don't sound robotic).

  - The title screen plays the menu theme: its intro once, then the loop forever with no gap.
  - In a run, the game music plays quietly underneath (GAME_THEME_VOLUME). Every track in music/gameMusic/ (each in
    its own folder with its .json) is in the playlist: one is picked at random as the run starts and fades in as
    the menu theme fades out. After TRACK_MINUTES it fades out and a different one fades in. Going back to the
    title fades it out. A new track only needs its folder dropped into music/gameMusic/.
  - A Bomb going off plays the explosion.

The volumes come from the Sound settings: Master x Music for the music, Master x Effects for sound effects, or
nothing when muted. If the computer has no audio device, or the files are missing, the game just runs silently.
"""

MENU_THEME = "music/mainMenuTheme/dungeon_depths.json"
GAME_MUSIC = "music/gameMusic"  # one folder per track, each with its .json
EXPLOSION = "music/soundEffects/explosion/explosion_sfx.json"
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
        self.menuTheme = self.explosion = None
        self.gameTracks = []    # every game track that loaded (LoopingMusic)
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
        folder = paths.resourcePath(GAME_MUSIC)
        for manifest in sorted(glob.glob(os.path.join(folder, "*", "*.json"))):
            track = self.loadMusic(manifest, GAME_CHANNEL)
            if track is not None:
                self.gameTracks.append(track)
        try:
            self.explosion = SoundVariations(paths.resourcePath(EXPLOSION), volume=self.effectsVolume())
        except (OSError, KeyError, ValueError, pygame.error):
            self.problem = "Sound files not found"

    def makeSilence(self):
        """A hundredth of a second of nothing. pygame plays a channel's queued sound when the channel stops, even after
        a fade-out or stop(), and the looping music always has the next loop queued. So before stopping, the queue
        gets this instead: the fade ends, the silence plays, and then the channel really is quiet."""
        frequency, sampleFormat, channels = pygame.mixer.get_init()
        return pygame.mixer.Sound(buffer=bytes((frequency // 100) * channels * (abs(sampleFormat) // 8)))

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
        if self.explosion is not None:
            self.explosion.set_volume(self.effectsVolume())

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
        """A run started: a random game track fades in (unless one is already playing)."""
        self.inRun = True
        if self.gameTheme is None or not self.gameTheme.is_playing:
            self.startNextTrack()

    def startNextTrack(self):
        """Fades in a game track picked at random, not the one that just played (unless it's the only one)."""
        choices = [t for t in self.gameTracks if t is not self.gameTheme] or self.gameTracks
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
        if self.gameTheme is None or not self.inRun:
            return
        self.gameTheme.update()
        if self.switching:
            if not self.gameTheme.channel.get_busy():  # the old track has faded out: in comes the next
                self.startNextTrack()
        elif pygame.time.get_ticks() - self.trackStart >= TRACK_MINUTES * 60000 and len(self.gameTracks) > 1:
            self.switching = True
            self.gameFadeStart = None
            self.gameTheme.channel.queue(self.silence)  # (see makeSilence)
            self.gameTheme.stop(fade_ms=GAME_FADE_OUT_MS)
        elif self.gameFadeStart is not None and self.gameTheme.is_playing:
            self.gameTheme.set_volume(self.gameThemeVolume())
