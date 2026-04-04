"""
color_mapper.py
Maps HSV color values to musical parameters.

Core idea: The color wheel and the circle of fifths are both 12-step cyclic
systems. Hue maps directly to pitch class via circle-of-fifths ordering.

Chord quality is driven by functional harmony (scale degree determines base
quality), with saturation and brightness acting as modifiers that introduce
suspensions, 7ths, diminished, and other color tones. A post-processing step
ensures suspended chords resolve and diminished chords move properly.
"""

import colorsys
from dataclasses import dataclass, field
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
    MINOR_7TH = "m7"
    DOMINANT_7TH = "7"
    SUSPENDED_2 = "sus2"
    SUSPENDED_4 = "sus4"
    ADD9 = "add9"
    MINOR_ADD9 = "madd9"


# Chord intervals in semitones above root
CHORD_INTERVALS = {
    ChordQuality.MAJOR:        [0, 4, 7],
    ChordQuality.MINOR:        [0, 3, 7],
    ChordQuality.DIMINISHED:   [0, 3, 6],
    ChordQuality.MAJOR_7TH:    [0, 4, 7, 11],
    ChordQuality.MINOR_7TH:    [0, 3, 7, 10],
    ChordQuality.DOMINANT_7TH: [0, 4, 7, 10],
    ChordQuality.SUSPENDED_2:  [0, 2, 7],
    ChordQuality.SUSPENDED_4:  [0, 5, 7],
    ChordQuality.ADD9:         [0, 4, 7, 14],
    ChordQuality.MINOR_ADD9:   [0, 3, 7, 14],
}

# ── Functional harmony: scale degree → base chord quality ────────────────────
# In major: I=maj, ii=min, iii=min, IV=maj, V=maj, vi=min, vii°=dim
# These are the *base* qualities; saturation/brightness modify them.

MAJOR_DEGREE_QUALITIES = {
    0: ChordQuality.MAJOR,       # I
    1: ChordQuality.MINOR,       # ii
    2: ChordQuality.MINOR,       # iii
    3: ChordQuality.MAJOR,       # IV
    4: ChordQuality.MAJOR,       # V
    5: ChordQuality.MINOR,       # vi
    6: ChordQuality.DIMINISHED,  # vii°
}

MINOR_DEGREE_QUALITIES = {
    0: ChordQuality.MINOR,       # i
    1: ChordQuality.DIMINISHED,  # ii°
    2: ChordQuality.MAJOR,       # III
    3: ChordQuality.MINOR,       # iv
    4: ChordQuality.MINOR,       # v  (or major V with raised 7th)
    5: ChordQuality.MAJOR,       # VI
    6: ChordQuality.MAJOR,       # VII
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
    midi_notes: list[int] = field(default_factory=list)
    duration: float = 4.0
    velocity: int = 80
    root_name: str = ""
    root_pitch_class: int = 0
    quality: ChordQuality = ChordQuality.MAJOR

    def label(self) -> str:
        return f"{self.root_name}{self.quality.value}"

    def __repr__(self):
        return f"{self.label()}(dur={self.duration:.2f}, vel={self.velocity})"


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
    relative = (pitch_class - root_offset) % 12
    best = min(scale_intervals, key=lambda d: min(abs(relative - d), 12 - abs(relative - d)))
    return (best + root_offset) % 12


def pitch_class_to_scale_degree(pitch_class: int, root_offset: int, scale_intervals: list[int]) -> int:
    """Return the index (0-based) of a pitch class within the scale. -1 if not found."""
    relative = (pitch_class - root_offset) % 12
    if relative in scale_intervals:
        return scale_intervals.index(relative)
    return -1


def saturation_to_quality(saturation: float) -> ChordQuality:
    """Map saturation (0–1) to chord quality. Legacy simple mapper."""
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
    """Convert a single RGBA pixel to a NoteEvent."""
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


# ── Region → Chord (simple, legacy) ──────────────────────────────────────────

def region_to_chord(
    avg_r: float, avg_g: float, avg_b: float, avg_a: float,
    duration: float = 4.0,
) -> ChordEvent:
    """Convert an averaged RGBA region to a ChordEvent (simple mode)."""
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
        root_pitch_class=pitch_class,
        quality=quality,
    )


# ── Functional Chord Builder ─────────────────────────────────────────────────
# This is the "smart" chord builder that uses scale degree function + image
# properties as modifiers for more musical progressions.

def _base_quality_for_degree(degree: int, scale_name: str) -> ChordQuality:
    """Get the diatonic chord quality for a given scale degree index."""
    if scale_name in ("minor", "dorian"):
        table = MINOR_DEGREE_QUALITIES
    else:
        table = MAJOR_DEGREE_QUALITIES
    return table.get(degree % 7, ChordQuality.MAJOR)


def _modify_quality(base: ChordQuality, saturation: float, brightness: float,
                     brightness_delta: float, position: int = 0,
                     n_chords: int = 4) -> ChordQuality:
    """
    Determine chord voicing by combining multiple image signals with
    the chord's position in the progression.

    Distributes output across the full voicing palette:
      - Plain triads  (major, minor)
      - 7ths          (maj7, m7, dom7)
      - 9ths          (add9, madd9)
      - Suspensions   (sus2, sus4)
      - Diminished

    Uses a "voicing score" derived from brightness, saturation, delta,
    and position — this avoids the old problem of every low-sat region
    hitting the same branch and producing identical chord types.
    """
    # ── High contrast → suspension (tension point) ────────────────────────────
    if brightness_delta > 0.15:
        # Alternate between sus4 and sus2 based on position
        if base in (ChordQuality.MAJOR, ChordQuality.MINOR):
            return ChordQuality.SUSPENDED_4 if position % 2 == 0 else ChordQuality.SUSPENDED_2

    # ── Very dark + desaturated → diminished (rare, moody) ────────────────────
    if brightness < 0.25 and saturation < 0.15:
        return ChordQuality.DIMINISHED

    # ── Compute a voicing score from combined signals ─────────────────────────
    # This distributes chord types across the progression instead of mapping
    # every low-sat region to the same voicing.
    #
    # score components:
    #   - brightness (0–1):  dark = low, bright = high
    #   - position phase:    cycles through voicing options
    #   - saturation:        minor influence on color
    phase = (position / max(n_chords, 1))  # 0.0 – ~1.0 across progression
    score = (brightness * 0.4 + phase * 0.4 + saturation * 0.2) % 1.0

    if saturation >= 0.40:
        # Saturated: mostly plain triads, occasionally add color
        if score < 0.7:
            return base  # plain triad
        elif base == ChordQuality.MAJOR:
            return ChordQuality.ADD9
        elif base == ChordQuality.MINOR:
            return ChordQuality.MINOR_ADD9
        return base

    # ── Low / moderate saturation: full voicing palette ───────────────────────
    # Distribute across 5 zones so each chord in the progression can land
    # on a different voicing type.

    if base in (ChordQuality.MAJOR, ChordQuality.DIMINISHED):
        # Major-family voicings
        if score < 0.20:
            return ChordQuality.MAJOR          # plain triad
        elif score < 0.40:
            return ChordQuality.MAJOR_7TH      # dreamy 7th
        elif score < 0.55:
            return ChordQuality.ADD9            # open 9th
        elif score < 0.70:
            return ChordQuality.SUSPENDED_2     # airy sus2
        elif score < 0.85:
            return ChordQuality.SUSPENDED_4     # tense sus4
        else:
            return ChordQuality.MAJOR           # bookend with triad
    else:
        # Minor-family voicings
        if score < 0.20:
            return ChordQuality.MINOR           # plain triad
        elif score < 0.40:
            return ChordQuality.MINOR_7TH       # m7
        elif score < 0.55:
            return ChordQuality.MINOR_ADD9       # madd9
        elif score < 0.70:
            return ChordQuality.SUSPENDED_2      # sus2
        elif score < 0.85:
            return ChordQuality.SUSPENDED_4      # sus4
        else:
            return ChordQuality.MINOR            # bookend with triad


def _is_low_variance(regions: list[dict], key: str, threshold: float) -> bool:
    """Check if a property has very little variation across regions."""
    values = [r[key] for r in regions]
    return (max(values) - min(values)) < threshold


def _brightness_to_degree(brightness: float, min_v: float, max_v: float,
                            n_degrees: int) -> int:
    """
    Map brightness to a scale degree index, normalized to the image's
    own brightness range. This spreads chord roots across the scale
    even when hue is uniform.
    """
    span = max_v - min_v
    if span < 0.01:
        return 0
    normalized = (brightness - min_v) / span  # 0–1 within image range
    return int(normalized * (n_degrees - 0.01))  # 0 to n_degrees-1


def build_progression(
    region_hsv_data: list[tuple[float, float, float, float]],
    root: str = "C",
    scale: str = "major",
    chord_duration: float = 4.0,
) -> list[ChordEvent]:
    """
    Build a musically coherent chord progression from a list of region averages.

    Each region's hue → root note (snapped to scale). The chord's scale degree
    determines its base quality (functional harmony). Saturation and brightness
    act as modifiers to introduce 7ths, suspensions, and diminished chords.

    For low-saturation / monochrome images (where hue is meaningless), the
    algorithm switches to brightness-driven mode: brightness differences across
    regions are mapped to different scale degrees, ensuring variety even from
    greyscale input.

    A resolution pass ensures:
    - sus4 chords resolve to major/minor on the next chord
    - dim chords resolve up by half step or to the tonic
    - The last chord resolves home (tonic or V→I)
    """
    root_offset = ROOT_OFFSETS[root]
    scale_intervals = SCALES[scale]
    n = len(region_hsv_data)
    n_degrees = len(scale_intervals)

    # ── Step 1: Extract raw HSV per region ────────────────────────────────────
    regions = []
    for avg_r, avg_g, avg_b, avg_a in region_hsv_data:
        h, s, v = rgb_to_hsv(int(avg_r), int(avg_g), int(avg_b))
        velocity = alpha_to_velocity(int(avg_a))
        regions.append({"h": h, "s": s, "v": v, "vel": velocity})

    # ── Step 2: Detect if image is monochrome / low-variance ──────────────────
    low_hue_variance = _is_low_variance(regions, "h", threshold=40.0)
    low_sat = all(r["s"] < 0.20 for r in regions)
    use_brightness_mode = low_hue_variance and low_sat

    # ── Step 3: Compute brightness deltas (contrast with neighbors) ───────────
    brightness_values = [r["v"] for r in regions]
    min_v, max_v = min(brightness_values), max(brightness_values)

    for i, reg in enumerate(regions):
        prev_v = regions[i - 1]["v"] if i > 0 else reg["v"]
        next_v = regions[i + 1]["v"] if i < n - 1 else reg["v"]
        reg["v_delta"] = abs(reg["v"] - prev_v) * 0.5 + abs(reg["v"] - next_v) * 0.5

    # ── Step 4: Build chords ──────────────────────────────────────────────────
    chords: list[ChordEvent] = []
    for i, reg in enumerate(regions):

        if use_brightness_mode:
            # Monochrome mode: use brightness to pick scale degree
            degree = _brightness_to_degree(reg["v"], min_v, max_v, n_degrees)
            pc = (scale_intervals[degree] + root_offset) % 12
        else:
            # Normal mode: hue → pitch class → snap to scale
            raw_pc = hue_to_pitch_class(reg["h"])
            pc = snap_to_scale(raw_pc, root_offset, scale_intervals)
            degree = pitch_class_to_scale_degree(pc, root_offset, scale_intervals)
            if degree < 0:
                degree = 0

        base_quality = _base_quality_for_degree(degree, scale)

        # In monochrome mode, amplify subtle contrast
        effective_delta = reg["v_delta"]
        if use_brightness_mode:
            effective_delta *= 2.0

        quality = _modify_quality(
            base_quality, reg["s"], reg["v"], effective_delta,
            position=i, n_chords=n,
        )

        # Dominant function: V degree gets dom7 to create pull toward tonic
        if degree == 4 and quality in (ChordQuality.MAJOR, ChordQuality.MINOR):
            quality = ChordQuality.DOMINANT_7TH

        octave = value_to_octave(reg["v"], base_octave=3)
        root_midi = pc + (octave + 1) * 12
        intervals = CHORD_INTERVALS[quality]
        midi_notes = [root_midi + iv for iv in intervals]

        chords.append(ChordEvent(
            midi_notes=midi_notes,
            duration=chord_duration,
            velocity=reg["vel"],
            root_name=NOTE_NAMES[pc],
            root_pitch_class=pc,
            quality=quality,
        ))

    # ── Step 5: Resolution pass ───────────────────────────────────────────────
    chords = _apply_resolutions(chords, root_offset, scale_intervals, scale)

    return chords


def _apply_resolutions(
    chords: list[ChordEvent],
    root_offset: int,
    scale_intervals: list[int],
    scale_name: str,
) -> list[ChordEvent]:
    """
    Post-process the progression for good voice leading:
    - After a sus4, the next chord resolves to the same root as major or minor
    - After a dim, the next chord moves up (resolution)
    - The final chord settles on tonic or a stable quality
    """
    n = len(chords)

    for i in range(n - 1):
        curr = chords[i]
        nxt = chords[i + 1]

        # sus4 → resolve: next chord keeps same root, becomes major or minor
        if curr.quality == ChordQuality.SUSPENDED_4:
            degree = pitch_class_to_scale_degree(curr.root_pitch_class, root_offset, scale_intervals)
            resolved_quality = _base_quality_for_degree(degree, scale_name) if degree >= 0 else ChordQuality.MAJOR
            nxt_chord = _rebuild_chord(curr.root_pitch_class, resolved_quality,
                                       nxt.velocity, nxt.duration)
            chords[i + 1] = nxt_chord

        # dim → resolve: next chord moves up to the nearest stable chord
        # (don't force it if the next chord is already sus — that creates double tension)
        if curr.quality == ChordQuality.DIMINISHED and nxt.quality not in (
            ChordQuality.SUSPENDED_4, ChordQuality.SUSPENDED_2, ChordQuality.DIMINISHED
        ):
            # Resolve dim → one semitone up as minor, or keep existing if it's already good
            resolve_pc = (curr.root_pitch_class + 1) % 12
            resolve_pc = snap_to_scale(resolve_pc, root_offset, scale_intervals)
            degree = pitch_class_to_scale_degree(resolve_pc, root_offset, scale_intervals)
            resolved_quality = _base_quality_for_degree(degree, scale_name) if degree >= 0 else ChordQuality.MINOR
            chords[i + 1] = _rebuild_chord(resolve_pc, resolved_quality,
                                           nxt.velocity, nxt.duration)

    # Final chord: settle on tonic (stable ending)
    if n >= 2:
        last = chords[-1]
        # If last chord is tense (sus/dim), resolve to tonic
        if last.quality in (ChordQuality.SUSPENDED_4, ChordQuality.SUSPENDED_2,
                            ChordQuality.DIMINISHED):
            tonic_quality = _base_quality_for_degree(0, scale_name)
            chords[-1] = _rebuild_chord(root_offset, tonic_quality,
                                        last.velocity, last.duration)

    return chords


def _rebuild_chord(
    pitch_class: int,
    quality: ChordQuality,
    velocity: int,
    duration: float,
    base_octave: int = 4,
) -> ChordEvent:
    """Construct a ChordEvent from a pitch class and quality."""
    root_midi = pitch_class + (base_octave + 1) * 12
    intervals = CHORD_INTERVALS[quality]
    midi_notes = [root_midi + iv for iv in intervals]
    return ChordEvent(
        midi_notes=midi_notes,
        duration=duration,
        velocity=velocity,
        root_name=NOTE_NAMES[pitch_class],
        root_pitch_class=pitch_class,
        quality=quality,
    )
