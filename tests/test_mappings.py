"""
tests/test_mappings.py
Verifies the core color→music mappings produce musically correct output.
Each test answers: "What musical behavior would break if this test fails?"
"""

import pytest
from src.color_mapper import (
    hue_to_pitch_class, snap_to_scale, saturation_to_quality,
    value_to_octave, alpha_to_velocity, saturation_to_duration,
    pixel_to_note, region_to_chord,
    ChordQuality, SCALES, NOTE_NAMES,
)


# ── Hue → Pitch Class ─────────────────────────────────────────────────────────

class TestHueToPitchClass:
    def test_red_maps_to_c(self):
        assert hue_to_pitch_class(0) == 0    # C

    def test_orange_maps_to_d(self):
        assert hue_to_pitch_class(60) == 2   # D (circle of fifths: C→G→D)

    def test_yellow_maps_to_e(self):
        assert hue_to_pitch_class(120) == 4  # E

    def test_green_maps_to_fsharp(self):
        assert hue_to_pitch_class(180) == 6  # F#

    def test_blue_maps_to_ab(self):
        assert hue_to_pitch_class(240) == 8  # Ab

    def test_violet_maps_to_bb(self):
        assert hue_to_pitch_class(300) == 10 # Bb

    def test_wraparound_360_sector(self):
        # 359° is in the 330°–360° sector (red-violet → F, pitch class 5)
        # It is NOT the same sector as 0° (red → C, pitch class 0)
        assert hue_to_pitch_class(359) == 5   # F
        assert hue_to_pitch_class(0)   == 0   # C

    def test_returns_valid_pitch_class(self):
        """Every hue should produce a pitch class 0–11."""
        for hue in range(0, 360, 5):
            pc = hue_to_pitch_class(hue)
            assert 0 <= pc <= 11, f"hue {hue}° produced invalid pitch class {pc}"


# ── Scale Quantization ────────────────────────────────────────────────────────

class TestSnapToScale:
    def test_c_in_c_major_is_unchanged(self):
        # C (0) is in C major → should stay C
        result = snap_to_scale(0, root_offset=0, scale_intervals=SCALES["major"])
        assert result == 0

    def test_fsharp_snaps_to_f_in_c_major(self):
        # F# (6) is not in C major; nearest scale note is F (5) or G (7)
        result = snap_to_scale(6, root_offset=0, scale_intervals=SCALES["major"])
        assert result in [5, 7], f"F# should snap to F or G in C major, got {NOTE_NAMES[result]}"

    def test_all_scale_notes_are_unchanged(self):
        """Notes already in the scale should not be moved."""
        c_major_pcs = [0, 2, 4, 5, 7, 9, 11]
        for pc in c_major_pcs:
            result = snap_to_scale(pc, root_offset=0, scale_intervals=SCALES["major"])
            assert result == pc, f"Note {NOTE_NAMES[pc]} changed from {pc} to {result}"

    def test_result_is_always_in_scale(self):
        """Any pitch class, after snapping to C major, must be a C major note."""
        c_major_pcs = set([0, 2, 4, 5, 7, 9, 11])
        for pc in range(12):
            result = snap_to_scale(pc, root_offset=0, scale_intervals=SCALES["major"])
            assert result in c_major_pcs, f"Snapped {pc} → {result}, not in C major"


# ── Saturation → Chord Quality ────────────────────────────────────────────────

class TestSaturationToQuality:
    def test_high_saturation_is_major(self):
        assert saturation_to_quality(0.9) == ChordQuality.MAJOR

    def test_medium_saturation_is_minor(self):
        assert saturation_to_quality(0.55) == ChordQuality.MINOR

    def test_low_saturation_is_sus2(self):
        assert saturation_to_quality(0.35) == ChordQuality.SUSPENDED_2

    def test_very_low_saturation_is_major7(self):
        assert saturation_to_quality(0.1) == ChordQuality.MAJOR_7TH

    def test_greyscale_produces_jazz_quality(self):
        """A greyscale pixel (s=0) should produce a dreamy 7th chord."""
        assert saturation_to_quality(0.0) == ChordQuality.MAJOR_7TH


# ── Value → Octave ────────────────────────────────────────────────────────────

class TestValueToOctave:
    def test_dark_produces_low_octave(self):
        assert value_to_octave(0.0) == 3

    def test_bright_produces_high_octave(self):
        assert value_to_octave(1.0) == 5

    def test_midrange_produces_middle_octave(self):
        result = value_to_octave(0.5)
        assert result in [3, 4]

    def test_octave_always_in_valid_range(self):
        for v in [i / 10 for i in range(11)]:
            octave = value_to_octave(v)
            assert 3 <= octave <= 5, f"v={v} produced octave {octave}"


# ── Alpha → Velocity ──────────────────────────────────────────────────────────

class TestAlphaToVelocity:
    def test_fully_opaque_produces_loud_velocity(self):
        vel = alpha_to_velocity(255)
        assert vel == 120

    def test_fully_transparent_produces_soft_velocity(self):
        vel = alpha_to_velocity(0)
        assert vel == 40

    def test_velocity_monotonically_increases_with_alpha(self):
        velocities = [alpha_to_velocity(a) for a in range(0, 256, 16)]
        assert velocities == sorted(velocities), "Velocity should increase with alpha"

    def test_velocity_in_valid_midi_range(self):
        for a in [0, 64, 128, 192, 255]:
            vel = alpha_to_velocity(a)
            assert 0 <= vel <= 127, f"alpha={a} produced out-of-range velocity {vel}"


# ── Saturation → Duration ─────────────────────────────────────────────────────

class TestSaturationToDuration:
    def test_high_saturation_is_short(self):
        short = saturation_to_duration(1.0)
        long_ = saturation_to_duration(0.0)
        assert short < long_, "High saturation should produce shorter notes"

    def test_duration_respects_bounds(self):
        assert saturation_to_duration(1.0) >= 0.25
        assert saturation_to_duration(0.0) <= 2.0


# ── pixel_to_note integration ─────────────────────────────────────────────────

class TestPixelToNote:
    def test_transparent_pixel_is_rest(self):
        note = pixel_to_note(255, 0, 0, 0)  # red, fully transparent
        assert note.is_rest

    def test_opaque_red_produces_note_near_c(self):
        """Pure red → hue=0 → C → note should be in C major."""
        note = pixel_to_note(255, 0, 0, 255, root="C", scale="major")
        assert not note.is_rest
        pitch_class = note.midi_note % 12
        c_major = {0, 2, 4, 5, 7, 9, 11}
        assert pitch_class in c_major, f"Red pixel produced {NOTE_NAMES[pitch_class]}, not in C major"

    def test_bright_pixel_produces_higher_octave_than_dark(self):
        """Bright pixel (high V) should produce higher MIDI note than dark pixel."""
        bright_note = pixel_to_note(255, 255, 255, 255)  # white
        dark_note   = pixel_to_note(30, 30, 30, 255)     # near-black
        assert bright_note.midi_note >= dark_note.midi_note

    def test_opaque_pixel_has_higher_velocity_than_semi_transparent(self):
        note_loud = pixel_to_note(200, 100, 50, 255)
        note_soft = pixel_to_note(200, 100, 50, 80)
        assert note_loud.velocity > note_soft.velocity

    def test_midi_note_in_valid_range(self):
        for r, g, b, a in [(0,0,0,255), (255,255,255,255), (128,0,200,200)]:
            note = pixel_to_note(r, g, b, a)
            if not note.is_rest:
                assert 0 <= note.midi_note <= 127


# ── region_to_chord integration ───────────────────────────────────────────────

class TestRegionToChord:
    def test_saturated_warm_region_produces_major_chord(self):
        """High-saturation red/orange region → major chord."""
        chord = region_to_chord(230, 80, 20, 255)  # warm orange, saturated
        assert chord.quality == ChordQuality.MAJOR

    def test_desaturated_region_produces_7th_or_sus(self):
        """Near-grey region → dreamy quality (maj7 or sus2)."""
        chord = region_to_chord(180, 175, 170, 255)  # near-grey
        assert chord.quality in [ChordQuality.MAJOR_7TH, ChordQuality.SUSPENDED_2]

    def test_chord_contains_multiple_notes(self):
        chord = region_to_chord(100, 150, 200, 255)
        assert len(chord.midi_notes) >= 3

    def test_all_chord_notes_in_valid_midi_range(self):
        chord = region_to_chord(100, 150, 200, 255)
        for note in chord.midi_notes:
            assert 0 <= note <= 127, f"Chord note {note} out of MIDI range"

    def test_root_name_is_valid_note_name(self):
        chord = region_to_chord(255, 128, 0, 255)
        assert chord.root_name in NOTE_NAMES
