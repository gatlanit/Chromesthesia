"""
tests/test_mappings.py
Verifies the core color→music mappings and functional harmony produce
musically correct output.
"""

import pytest
from src.color_mapper import (
    hue_to_pitch_class, snap_to_scale, saturation_to_quality,
    value_to_octave, alpha_to_velocity, pixel_to_duration,
    pitch_class_to_scale_degree, build_progression,
    pixel_to_note, region_to_chord,
    ChordQuality, SCALES, NOTE_NAMES, NOTE_DURATIONS, ROOT_OFFSETS,
    _base_quality_for_degree, _modify_quality,
)


# ── Hue → Pitch Class ─────────────────────────────────────────────────────────

class TestHueToPitchClass:
    def test_red_maps_to_c(self):
        assert hue_to_pitch_class(0) == 0    # C

    def test_orange_maps_to_d(self):
        assert hue_to_pitch_class(60) == 2   # D

    def test_yellow_maps_to_e(self):
        assert hue_to_pitch_class(120) == 4  # E

    def test_green_maps_to_fsharp(self):
        assert hue_to_pitch_class(180) == 6  # F#

    def test_blue_maps_to_ab(self):
        assert hue_to_pitch_class(240) == 8  # Ab

    def test_violet_maps_to_bb(self):
        assert hue_to_pitch_class(300) == 10 # Bb

    def test_wraparound_360_sector(self):
        assert hue_to_pitch_class(359) == 5   # F (330°–360° sector)
        assert hue_to_pitch_class(0)   == 0   # C

    def test_returns_valid_pitch_class(self):
        for hue in range(0, 360, 5):
            pc = hue_to_pitch_class(hue)
            assert 0 <= pc <= 11, f"hue {hue}° produced invalid pitch class {pc}"


# ── Scale Quantization ────────────────────────────────────────────────────────

class TestSnapToScale:
    def test_c_in_c_major_is_unchanged(self):
        result = snap_to_scale(0, root_offset=0, scale_intervals=SCALES["major"])
        assert result == 0

    def test_fsharp_snaps_to_f_in_c_major(self):
        result = snap_to_scale(6, root_offset=0, scale_intervals=SCALES["major"])
        assert result in [5, 7]

    def test_all_scale_notes_are_unchanged(self):
        c_major_pcs = [0, 2, 4, 5, 7, 9, 11]
        for pc in c_major_pcs:
            result = snap_to_scale(pc, root_offset=0, scale_intervals=SCALES["major"])
            assert result == pc

    def test_result_is_always_in_scale(self):
        c_major_pcs = set([0, 2, 4, 5, 7, 9, 11])
        for pc in range(12):
            result = snap_to_scale(pc, root_offset=0, scale_intervals=SCALES["major"])
            assert result in c_major_pcs


# ── Scale Degree Lookup ───────────────────────────────────────────────────────

class TestPitchClassToScaleDegree:
    def test_tonic_is_degree_0(self):
        assert pitch_class_to_scale_degree(0, 0, SCALES["major"]) == 0

    def test_fifth_is_degree_4(self):
        # G (7) in C major: C=0 D=1 E=2 F=3 G=4
        assert pitch_class_to_scale_degree(7, 0, SCALES["major"]) == 4

    def test_non_scale_tone_returns_negative(self):
        # C# (1) is not in C major
        assert pitch_class_to_scale_degree(1, 0, SCALES["major"]) == -1

    def test_works_with_transposed_root(self):
        # In D major (root=2): D=0, E=1, F#=2, G=3, A=4
        assert pitch_class_to_scale_degree(9, 2, SCALES["major"]) == 4  # A is the 5th


# ── Saturation → Chord Quality (legacy) ──────────────────────────────────────

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
            assert 3 <= octave <= 5


# ── Alpha → Velocity ──────────────────────────────────────────────────────────

class TestAlphaToVelocity:
    def test_fully_opaque_produces_loud_velocity(self):
        assert alpha_to_velocity(255) == 120

    def test_fully_transparent_produces_soft_velocity(self):
        assert alpha_to_velocity(0) == 40

    def test_velocity_monotonically_increases_with_alpha(self):
        velocities = [alpha_to_velocity(a) for a in range(0, 256, 16)]
        assert velocities == sorted(velocities)

    def test_velocity_in_valid_midi_range(self):
        for a in [0, 64, 128, 192, 255]:
            vel = alpha_to_velocity(a)
            assert 0 <= vel <= 127


# ── Saturation → Duration ─────────────────────────────────────────────────────

class TestPixelToDuration:
    def test_always_returns_standard_note_length(self):
        """Every pixel should produce a real rhythmic value."""
        for r in range(0, 256, 64):
            for g in range(0, 256, 64):
                for b in range(0, 256, 64):
                    dur = pixel_to_duration(r, g, b, 45.0, 0.1, 0.5)
                    assert dur in NOTE_DURATIONS, f"rgb=({r},{g},{b}) → {dur}, not standard"

    def test_greyscale_pixels_produce_varied_durations(self):
        """Even greyscale pixels with subtle differences should vary rhythmically."""
        durations = set()
        # Simulate near-grey pixels like the beach image (R≈G≈B with slight drift)
        for offset in range(20):
            r, g, b = 100 + offset, 100 + offset // 2, 95 + offset
            dur = pixel_to_duration(r, g, b, 40.0, 0.05, 0.4)
            durations.add(dur)
        assert len(durations) >= 3, f"Expected rhythmic variety from greyscale, got: {durations}"

    def test_identical_pixels_produce_same_duration(self):
        """Deterministic: same input = same output."""
        d1 = pixel_to_duration(120, 130, 125, 40.0, 0.05, 0.5)
        d2 = pixel_to_duration(120, 130, 125, 40.0, 0.05, 0.5)
        assert d1 == d2

    def test_varied_colors_produce_variety(self):
        """Distinctly different colors should produce many different durations."""
        from src.color_mapper import rgb_to_hsv
        pixels = [(255,0,0), (0,255,0), (0,0,255), (255,255,0),
                  (0,255,255), (128,0,128), (50,50,50), (200,200,200)]
        durations = set()
        for r, g, b in pixels:
            h, s, v = rgb_to_hsv(r, g, b)
            durations.add(pixel_to_duration(r, g, b, h, s, v))
        assert len(durations) >= 3, f"Expected varied durations from different colors, got: {durations}"


# ── Functional Harmony: Base Quality ──────────────────────────────────────────

class TestBaseQualityForDegree:
    def test_tonic_is_major_in_major_key(self):
        assert _base_quality_for_degree(0, "major") == ChordQuality.MAJOR

    def test_supertonic_is_minor_in_major_key(self):
        assert _base_quality_for_degree(1, "major") == ChordQuality.MINOR

    def test_dominant_is_major_in_major_key(self):
        assert _base_quality_for_degree(4, "major") == ChordQuality.MAJOR

    def test_leading_tone_is_diminished_in_major(self):
        assert _base_quality_for_degree(6, "major") == ChordQuality.DIMINISHED

    def test_tonic_is_minor_in_minor_key(self):
        assert _base_quality_for_degree(0, "minor") == ChordQuality.MINOR

    def test_third_is_major_in_minor_key(self):
        # III in natural minor is major
        assert _base_quality_for_degree(2, "minor") == ChordQuality.MAJOR


# ── Quality Modifier ──────────────────────────────────────────────────────────

class TestModifyQuality:
    def test_high_brightness_contrast_creates_suspension(self):
        """Regions with sharp brightness change → sus4 or sus2."""
        result = _modify_quality(ChordQuality.MAJOR, saturation=0.6, brightness=0.5,
                                  brightness_delta=0.25, position=0, n_chords=4)
        assert result in (ChordQuality.SUSPENDED_4, ChordQuality.SUSPENDED_2)

    def test_alternating_sus_types_on_high_contrast(self):
        """Even position → sus4, odd position → sus2."""
        even = _modify_quality(ChordQuality.MAJOR, saturation=0.6, brightness=0.5,
                                brightness_delta=0.25, position=0, n_chords=4)
        odd = _modify_quality(ChordQuality.MAJOR, saturation=0.6, brightness=0.5,
                               brightness_delta=0.25, position=1, n_chords=4)
        assert even == ChordQuality.SUSPENDED_4
        assert odd == ChordQuality.SUSPENDED_2

    def test_very_dark_desaturated_creates_diminished(self):
        """Very dark + washed out → dim chord."""
        result = _modify_quality(ChordQuality.MINOR, saturation=0.1, brightness=0.15,
                                  brightness_delta=0.05, position=0, n_chords=4)
        assert result == ChordQuality.DIMINISHED

    def test_saturated_chord_mostly_plain_triad(self):
        """Highly saturated + early position → keeps base triad."""
        result = _modify_quality(ChordQuality.MAJOR, saturation=0.8, brightness=0.3,
                                  brightness_delta=0.05, position=0, n_chords=4)
        assert result == ChordQuality.MAJOR

    def test_low_sat_produces_variety_across_positions(self):
        """Different positions with low saturation should produce varied voicings."""
        qualities = set()
        for pos in range(8):
            q = _modify_quality(ChordQuality.MAJOR, saturation=0.10,
                                 brightness=0.3 + pos * 0.05,
                                 brightness_delta=0.05,
                                 position=pos, n_chords=8)
            qualities.add(q)
        assert len(qualities) >= 3, (
            f"Expected at least 3 different voicings across 8 positions, got: {qualities}"
        )

    def test_output_is_always_valid_chord_quality(self):
        """Every combination of inputs produces a valid ChordQuality."""
        for sat in [0.0, 0.1, 0.3, 0.5, 0.8]:
            for bri in [0.1, 0.3, 0.5, 0.7, 0.9]:
                for pos in range(4):
                    result = _modify_quality(ChordQuality.MAJOR, sat, bri, 0.05, pos, 4)
                    assert isinstance(result, ChordQuality)
                    result = _modify_quality(ChordQuality.MINOR, sat, bri, 0.05, pos, 4)
                    assert isinstance(result, ChordQuality)


# ── build_progression (integration) ───────────────────────────────────────────

class TestBuildProgression:
    def test_produces_correct_number_of_chords(self):
        regions = [(200, 100, 50, 255)] * 4  # 4 warm regions
        chords = build_progression(regions, root="C", scale="major")
        assert len(chords) == 4

    def test_final_chord_is_never_suspended_or_diminished(self):
        """Progression should resolve - last chord must be stable."""
        # Feed regions that would produce tension (dark, desaturated, high contrast)
        regions = [
            (50, 50, 50, 255),    # dark grey
            (200, 200, 200, 255), # bright grey (high contrast → sus)
            (30, 30, 30, 255),    # very dark
            (100, 100, 100, 255), # mid grey
        ]
        chords = build_progression(regions, root="C", scale="major")
        last = chords[-1]
        unstable = {ChordQuality.SUSPENDED_4, ChordQuality.SUSPENDED_2, ChordQuality.DIMINISHED}
        assert last.quality not in unstable, f"Final chord is {last.label()}, should resolve"

    def test_sus4_is_followed_by_resolution(self):
        """If a sus4 appears, the next chord should resolve to the same root."""
        # Create high contrast to force sus4
        regions = [
            (180, 50, 50, 255),   # dark
            (180, 220, 220, 255), # bright (big delta → sus4)
            (180, 180, 180, 255), # mid (should resolve)
            (200, 100, 50, 255),  # warm ending
        ]
        chords = build_progression(regions, root="C", scale="major")

        for i, chord in enumerate(chords[:-1]):
            if chord.quality == ChordQuality.SUSPENDED_4:
                nxt = chords[i + 1]
                # Resolution: same root, stable quality
                assert nxt.root_pitch_class == chord.root_pitch_class, \
                    f"sus4 on {chord.root_name} resolved to different root {nxt.root_name}"
                assert nxt.quality not in (ChordQuality.SUSPENDED_4, ChordQuality.SUSPENDED_2), \
                    f"sus4 resolved to another suspension: {nxt.label()}"

    def test_progression_has_variety(self):
        """With varied colors, progression shouldn't be all the same quality."""
        regions = [
            (255, 0, 0, 255),     # saturated red
            (100, 100, 100, 255), # grey
            (0, 0, 200, 255),     # saturated blue
            (200, 200, 50, 255),  # saturated yellow
        ]
        chords = build_progression(regions, root="C", scale="major")
        qualities = set(c.quality for c in chords)
        assert len(qualities) >= 2, f"All chords have same quality: {chords[0].quality}"

    def test_all_chord_notes_valid_midi(self):
        regions = [(r, 128, 128, 255) for r in range(0, 256, 64)]
        chords = build_progression(regions, root="C", scale="major")
        for chord in chords:
            for note in chord.midi_notes:
                assert 0 <= note <= 127, f"Invalid MIDI note {note} in {chord.label()}"


# ── pixel_to_note integration ─────────────────────────────────────────────────

class TestPixelToNote:
    def test_transparent_pixel_is_rest(self):
        note = pixel_to_note(255, 0, 0, 0)
        assert note.is_rest

    def test_opaque_red_produces_note_near_c(self):
        note = pixel_to_note(255, 0, 0, 255, root="C", scale="major")
        assert not note.is_rest
        pitch_class = note.midi_note % 12
        c_major = {0, 2, 4, 5, 7, 9, 11}
        assert pitch_class in c_major

    def test_bright_pixel_produces_higher_octave_than_dark(self):
        bright_note = pixel_to_note(255, 255, 255, 255)
        dark_note   = pixel_to_note(30, 30, 30, 255)
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


# ── region_to_chord integration (legacy simple mode) ──────────────────────────

class TestRegionToChord:
    def test_saturated_warm_region_produces_major_chord(self):
        chord = region_to_chord(230, 80, 20, 255)
        assert chord.quality == ChordQuality.MAJOR

    def test_desaturated_region_produces_7th_or_sus(self):
        chord = region_to_chord(180, 175, 170, 255)
        assert chord.quality in [ChordQuality.MAJOR_7TH, ChordQuality.SUSPENDED_2]

    def test_chord_contains_multiple_notes(self):
        chord = region_to_chord(100, 150, 200, 255)
        assert len(chord.midi_notes) >= 3

    def test_all_chord_notes_in_valid_midi_range(self):
        chord = region_to_chord(100, 150, 200, 255)
        for note in chord.midi_notes:
            assert 0 <= note <= 127

    def test_root_name_is_valid_note_name(self):
        chord = region_to_chord(255, 128, 0, 255)
        assert chord.root_name in NOTE_NAMES
