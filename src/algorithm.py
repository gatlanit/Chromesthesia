"""
algorithm.py
Orchestrates the Chromatic Synthesis algorithm:
  - melody mode:   pixel scan → monophonic note sequence
  - chords mode:   region average → chord progression (functional harmony)
  - combined mode: both tracks simultaneously
"""

from PIL import Image

from src.image_reader import load_image, sample_image, get_regions, average_region
from src.color_mapper import (
    pixel_to_note, build_progression,
    NoteEvent, ChordEvent,
)
from src.midi_writer import write_melody, write_chords, write_combined

# Fixed BPM — DAWs can adjust tempo on their own
DEFAULT_BPM = 120


def generate_melody(
    image_path: str,
    output_path: str,
    root: str = "C",
    scale: str = "major",
    scan_mode: str = "horizontal",
    stride: int = 4,
    bpm: int = DEFAULT_BPM,
    rest_alpha_threshold: int = 30,
    max_notes: int = 512,
) -> list[NoteEvent]:
    """Scan an image and produce a monophonic MIDI melody."""
    img = load_image(image_path)
    print(f"  Image loaded: {img.size[0]}×{img.size[1]} px")

    notes: list[NoteEvent] = []
    for r, g, b, a in sample_image(img, mode=scan_mode, stride=stride):
        note = pixel_to_note(r, g, b, a,
                             root=root,
                             scale=scale,
                             rest_alpha_threshold=rest_alpha_threshold)
        notes.append(note)
        if len(notes) >= max_notes:
            break

    notes = _collapse_rests(notes)

    print(f"  Generated {len(notes)} note events")
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

    progression = " | ".join(c.label() for c in chords)
    print(f"  Progression: {progression}")
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
    max_notes: int = 512,
) -> tuple[list[ChordEvent], list[NoteEvent]]:
    """
    Generate both a chord progression and a melody from the same image,
    written to a two-track MIDI file.
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

    progression = " | ".join(c.label() for c in chords)
    print(f"  Progression: {progression}")

    # ── Melody track ──────────────────────────────────────────────────────────
    notes: list[NoteEvent] = []
    for r, g, b, a in sample_image(img, mode=scan_mode, stride=stride):
        note = pixel_to_note(r, g, b, a, root=root, scale=scale)
        notes.append(note)
        if len(notes) >= max_notes:
            break

    notes = _collapse_rests(notes)
    print(f"  Generated {len(notes)} melody events")

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
