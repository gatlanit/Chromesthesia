"""
algorithm.py
Orchestrates the Chromatic Synthesis algorithm:
  - melody mode:   pixel scan → monophonic note sequence
  - chords mode:   region average → chord progression
  - combined mode: both tracks simultaneously
"""

from PIL import Image

from src.image_reader import load_image, sample_image, get_regions, average_region
from src.color_mapper import (
    pixel_to_note, region_to_chord,
    NoteEvent, ChordEvent,
)
from src.midi_writer import write_melody, write_chords, write_combined


def generate_melody(
    image_path: str,
    output_path: str,
    root: str = "C",
    scale: str = "major",
    scan_mode: str = "horizontal",
    stride: int = 4,
    bpm: int = 120,
    rest_alpha_threshold: int = 30,
    max_notes: int = 512,
) -> list[NoteEvent]:
    """
    Scan an image and produce a monophonic MIDI melody.

    Parameters
    ----------
    image_path   : path to input image
    output_path  : path for output .mid file
    root         : key root note (e.g. 'C', 'F#', 'Bb')
    scale        : scale name ('major', 'minor', 'pentatonic', 'dorian', ...)
    scan_mode    : pixel traversal path ('horizontal', 'vertical', 'diagonal', 'spiral')
    stride       : sample every Nth pixel (higher = fewer notes)
    bpm          : tempo in beats per minute
    rest_alpha_threshold : alpha < this value becomes a rest
    max_notes    : cap on number of notes generated
    """
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

    # Collapse consecutive rests into one
    notes = _collapse_rests(notes)

    print(f"  Generated {len(notes)} note events")
    write_melody(notes, output_path, bpm=bpm)
    return notes


def generate_chords(
    image_path: str,
    output_path: str,
    n_chords: int = 8,
    axis: str = "vertical",
    chord_duration: float = 4.0,
    bpm: int = 90,
) -> list[ChordEvent]:
    """
    Divide image into N regions and produce a MIDI chord progression.

    Parameters
    ----------
    image_path     : path to input image
    output_path    : path for output .mid file
    n_chords       : number of chords in the progression
    axis           : 'vertical' (left→right strips) or 'horizontal' (top→bottom)
    chord_duration : duration of each chord in beats
    bpm            : tempo in beats per minute
    """
    img = load_image(image_path)
    print(f"  Image loaded: {img.size[0]}×{img.size[1]} px")

    regions = get_regions(img, n_chords, axis=axis)
    chords: list[ChordEvent] = []
    for region in regions:
        avg = average_region(region)
        chord = region_to_chord(*avg, duration=chord_duration)
        chords.append(chord)

    progression = " | ".join(f"{c.root_name}{c.quality.value}" for c in chords)
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
    n_chords: int = 8,
    axis: str = "vertical",
    chord_duration: float = 4.0,
    bpm: int = 100,
    max_notes: int = 512,
) -> tuple[list[ChordEvent], list[NoteEvent]]:
    """
    Generate both a chord progression and a melody from the same image,
    written to a two-track MIDI file.
    """
    img = load_image(image_path)
    print(f"  Image loaded: {img.size[0]}×{img.size[1]} px")

    # ── Chord track ───────────────────────────────────────────────────────────
    regions = get_regions(img, n_chords, axis=axis)
    chords: list[ChordEvent] = []
    for region in regions:
        avg = average_region(region)
        chord = region_to_chord(*avg, duration=chord_duration)
        chords.append(chord)

    progression = " | ".join(f"{c.root_name}{c.quality.value}" for c in chords)
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
