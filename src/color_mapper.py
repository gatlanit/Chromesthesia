"""
color_mapper.py
Maps HSV color values to musical parameters.

Core idea: The color wheel and the circle of fifths are both 12-step cyclic
systems. Hue maps directly to pitch class via circle-of-fifths ordering.
"""

import colorsys
from dataclasses import dataclass
from enum import Enum


# ── Scales ────────────────────────────────────────────────────────────────────

SCALES = {
    "major":      [0, 2, 4, 5, 7, 9, 11],
    "minor":      [0, 2, 3, 5, 7, 8, 10],
    "pentatonic": [0, 2, 4, 7, 9],
    "dorian":     [0, 2, 3, 5, 7, 9, 10],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "chromatic":  list(range(12)),
}

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Circle of fifths order: C G D A E B F# Db Ab Eb Bb F
# Maps 12 hue sectors (30° each) → pitch class (0–11)
HUE_TO_PITCH_CLASS = [
    0,   # 0°   Red          → C
    7,   # 30°  Red-Orange   → G
    2,   # 60°  Orange       → D
    9,   # 90°  Yellow-Org   → A
    4,   # 120° Yellow       → E
    11,  # 150° Yellow-Grn   → B
    6,   # 180° Green        → F#/Gb
    1,   # 210° Cyan-Green   → Db
    8,   # 240° Blue         → Ab
    3,   # 270° Blue-Violet  → Eb
    10,  # 300° Violet       → Bb
    5,   # 330° Red-Violet   → F
]

# Named root notes → semitone offset from C
ROOT_OFFSETS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


class ChordQuality(Enum):
    MAJOR = "maj"
    MINOR = "min"
    DIMINISHED = "dim"
    MAJOR_7TH = "maj7"
    DOMINANT_7TH = "7"
    SUSPENDED_2 = "sus2"


# Chord intervals in semitones above root
CHORD_INTERVALS = {
    ChordQuality.MAJOR:        [0, 4, 7],
    ChordQuality.MINOR:        [0, 3, 7],
    ChordQuality.DIMINISHED:   [0, 3, 6],
    ChordQuality.MAJOR_7TH:    [0, 4, 7, 11],
    ChordQuality.DOMINANT_7TH: [0, 4, 7, 10],
    ChordQuality.SUSPENDED_2:  [0, 2, 7],
}


@dataclass
class NoteEvent:
    midi_note: int
    duration: float   # in beats (1.0 = quarter note)
    velocity: int     # 0–127
    is_rest: bool = False

    def __repr__(self):
        if self.is_rest:
            return f"REST({self.duration:.2f}b)"
        name = NOTE_NAMES[self.midi_note % 12]
        octave = (self.midi_note // 12) - 1
        return f"{name}{octave}(dur={self.duration:.2f}, vel={self.velocity})"


@dataclass
class ChordEvent:
    midi_notes: list[int]
    duration: float
    velocity: int
    root_name: str = ""
    quality: ChordQuality = ChordQuality.MAJOR

    def __repr__(self):
        return f"{self.root_name}{self.quality.value}(dur={self.duration:.2f}, vel={self.velocity})"


# ── Core mapping functions ─────────────────────────────────────────────────────

def rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert 0–255 RGB to HSV (h: 0–360, s: 0–1, v: 0–1)."""
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return h * 360, s, v


def hue_to_pitch_class(hue: float) -> int:
    """Map hue (0–360°) to pitch class (0–11) via circle of fifths."""
    sector = int(hue / 30) % 12
    return HUE_TO_PITCH_CLASS[sector]


def snap_to_scale(pitch_class: int, root_offset: int, scale_intervals: list[int]) -> int:
    """
    Snap a pitch class to the nearest degree in the given scale.
    Returns a pitch class (0–11) within the scale.
    """
    # Normalize relative to root
    relative = (pitch_class - root_offset) % 12
    # Find nearest scale degree
    best = min(scale_intervals, key=lambda d: min(abs(relative - d), 12 - abs(relative - d)))
    return (best + root_offset) % 12


def saturation_to_quality(saturation: float) -> ChordQuality:
    """Map saturation (0–1) to chord quality."""
    if saturation > 0.70:
        return ChordQuality.MAJOR
    elif saturation > 0.45:
        return ChordQuality.MINOR
    elif saturation > 0.25:
        return ChordQuality.SUSPENDED_2
    else:
        return ChordQuality.MAJOR_7TH


def value_to_octave(value: float, base_octave: int = 3) -> int:
    """Map brightness (0–1) to MIDI octave."""
    return base_octave + int(value * 2.99)  # 0–1 → octave 3, 4, or 5


def alpha_to_velocity(alpha: int) -> int:
    """Map alpha (0–255) to MIDI velocity (40–120)."""
    return int((alpha / 255) * 80) + 40


def saturation_to_duration(saturation: float,
                            min_dur: float = 0.25,
                            max_dur: float = 2.0) -> float:
    """High saturation = short/staccato; low saturation = long/sustained."""
    return min_dur + (1 - saturation) * (max_dur - min_dur)


# ── Pixel → Note ───────────────────────────────────────────────────────────────

def pixel_to_note(
    r: int, g: int, b: int, a: int,
    root: str = "C",
    scale: str = "major",
    rest_alpha_threshold: int = 30,
) -> NoteEvent:
    """
    Convert a single RGBA pixel to a NoteEvent.
    """
    if a < rest_alpha_threshold:
        return NoteEvent(midi_note=0, duration=0.5, velocity=0, is_rest=True)

    h, s, v = rgb_to_hsv(r, g, b)

    root_offset = ROOT_OFFSETS[root]
    scale_intervals = SCALES[scale]

    raw_pitch_class = hue_to_pitch_class(h)
    pitch_class = snap_to_scale(raw_pitch_class, root_offset, scale_intervals)
    octave = value_to_octave(v)
    midi_note = pitch_class + (octave + 1) * 12

    duration = saturation_to_duration(s)
    velocity = alpha_to_velocity(a)

    return NoteEvent(midi_note=midi_note, duration=duration, velocity=velocity)


# ── Region → Chord ─────────────────────────────────────────────────────────────

def region_to_chord(
    avg_r: float, avg_g: float, avg_b: float, avg_a: float,
    duration: float = 4.0,
) -> ChordEvent:
    """
    Convert an averaged RGBA region to a ChordEvent.
    """
    h, s, v = rgb_to_hsv(int(avg_r), int(avg_g), int(avg_b))

    pitch_class = hue_to_pitch_class(h)
    quality = saturation_to_quality(s)
    octave = value_to_octave(v, base_octave=3)
    velocity = alpha_to_velocity(int(avg_a))

    root_midi = pitch_class + (octave + 1) * 12
    intervals = CHORD_INTERVALS[quality]
    midi_notes = [root_midi + interval for interval in intervals]

    return ChordEvent(
        midi_notes=midi_notes,
        duration=duration,
        velocity=velocity,
        root_name=NOTE_NAMES[pitch_class],
        quality=quality,
    )
