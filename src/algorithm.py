"""
algorithm.py
Orchestrates the Chromesthesia algorithm:
  - melody mode:   pixel scan → monophonic note sequence (capped to N bars)
  - chords mode:   region average → chord progression (functional harmony)
  - combined mode: both tracks simultaneously, melody matches chord length
"""

from PIL import Image

from src.image_reader import load_image, sample_image, get_regions, average_region
from src.color_mapper import (
    pixel_to_note, build_progression,
    NoteEvent, ChordEvent,
)
from src.midi_writer import write_melody, write_chords, write_combined

# Fixed BPM - DAWs can adjust tempo on their own
DEFAULT_BPM = 120


def _trim_melody_to_beats(notes: list[NoteEvent], max_beats: float) -> list[NoteEvent]:
    """
    Trim a melody so its total duration does not exceed max_beats.
    Truncates the last note if needed to fit exactly.
    """
    trimmed = []
    total = 0.0
    for note in notes:
        remaining = max_beats - total
        if remaining <= 0:
            break
        if note.duration > remaining:
            # Truncate last note to fill exactly
            trimmed.append(NoteEvent(
                midi_note=note.midi_note,
                duration=remaining,
                velocity=note.velocity,
                is_rest=note.is_rest,
            ))
            break
        trimmed.append(note)
        total += note.duration
    return trimmed


def generate_melody(
    image_path: str,
    output_path: str,
    root: str = "C",
    scale: str = "major",
    scan_mode: str = "horizontal",
    stride: int = 4,
    bpm: int = DEFAULT_BPM,
    n_bars: int = 4,
    beats_per_bar: float = 4.0,
    rest_alpha_threshold: int = 30,
) -> list[NoteEvent]:
    """
    Scan an image and produce a monophonic MIDI melody, capped to n_bars.
    """
    img = load_image(image_path)
    print(f"  Image loaded: {img.size[0]}×{img.size[1]} px")

    max_beats = n_bars * beats_per_bar

    # Generate more notes than needed, then trim to exact bar count
    notes: list[NoteEvent] = []
    total_beats = 0.0
    for r, g, b, a in sample_image(img, mode=scan_mode, stride=stride):
        note = pixel_to_note(r, g, b, a,
                             root=root,
                             scale=scale,
                             rest_alpha_threshold=rest_alpha_threshold)
        notes.append(note)
        total_beats += note.duration
        if total_beats >= max_beats:
            break

    notes = _collapse_rests(notes)
    notes = _trim_melody_to_beats(notes, max_beats)

    actual_beats = sum(n.duration for n in notes)
    print(f"  Generated {len(notes)} note events ({actual_beats:.1f} beats / {n_bars} bars)")
    write_melody(notes, output_path, bpm=bpm)
    return notes


def generate_chords(
    image_path: str,
    output_path: str,
    root: str = "C",
    scale: str = "major",
    n_chords: int = 4,
    axis: str = "vertical",
    chord_duration: float = 4.0,
    bpm: int = DEFAULT_BPM,
) -> list[ChordEvent]:
    """
    Divide image into N regions and produce a MIDI chord progression
    using functional harmony with tension/resolution.
    """
    img = load_image(image_path)
    print(f"  Image loaded: {img.size[0]}×{img.size[1]} px")

    regions = get_regions(img, n_chords, axis=axis)
    region_data = [average_region(r) for r in regions]

    chords = build_progression(
        region_data,
        root=root,
        scale=scale,
        chord_duration=chord_duration,
    )

    n_bars = int(n_chords * chord_duration / 4)
    progression = " | ".join(c.label() for c in chords)
    print(f"  Progression ({n_bars} bars): {progression}")
    write_chords(chords, output_path, bpm=bpm)
    return chords


def generate_combined(
    image_path: str,
    output_path: str,
    root: str = "C",
    scale: str = "major",
    scan_mode: str = "horizontal",
    stride: int = 4,
    n_chords: int = 4,
    axis: str = "vertical",
    chord_duration: float = 4.0,
    bpm: int = DEFAULT_BPM,
) -> tuple[list[ChordEvent], list[NoteEvent]]:
    """
    Generate both a chord progression and a melody from the same image,
    written to a two-track MIDI file. Melody is trimmed to match the
    total length of the chord progression.
    """
    img = load_image(image_path)
    print(f"  Image loaded: {img.size[0]}×{img.size[1]} px")

    # ── Chord track (functional harmony) ──────────────────────────────────────
    regions = get_regions(img, n_chords, axis=axis)
    region_data = [average_region(r) for r in regions]

    chords = build_progression(
        region_data,
        root=root,
        scale=scale,
        chord_duration=chord_duration,
    )

    total_chord_beats = sum(c.duration for c in chords)
    n_bars = int(total_chord_beats / 4)
    progression = " | ".join(c.label() for c in chords)
    print(f"  Progression ({n_bars} bars): {progression}")

    # ── Melody track (capped to chord length) ────────────────────────────────
    notes: list[NoteEvent] = []
    total_beats = 0.0
    for r, g, b, a in sample_image(img, mode=scan_mode, stride=stride):
        note = pixel_to_note(r, g, b, a, root=root, scale=scale)
        notes.append(note)
        total_beats += note.duration
        if total_beats >= total_chord_beats:
            break

    notes = _collapse_rests(notes)
    notes = _trim_melody_to_beats(notes, total_chord_beats)

    actual_beats = sum(n.duration for n in notes)
    print(f"  Melody: {len(notes)} events ({actual_beats:.1f} beats / {n_bars} bars)")

    write_combined(chords, notes, output_path, bpm=bpm)
    return chords, notes


# ── Helpers ────────────────────────────────────────────────────────────────────

def _collapse_rests(notes: list[NoteEvent]) -> list[NoteEvent]:
    """Merge consecutive rest events into a single longer rest."""
    collapsed = []
    for note in notes:
        if note.is_rest and collapsed and collapsed[-1].is_rest:
            collapsed[-1].duration += note.duration
        else:
            collapsed.append(note)
    return collapsed
