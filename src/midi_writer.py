"""
midi_writer.py
Converts NoteEvent / ChordEvent sequences into MIDI files using mido.
"""

import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from src.color_mapper import NoteEvent, ChordEvent


def beats_to_ticks(beats: float, ticks_per_beat: int) -> int:
    return max(1, int(beats * ticks_per_beat))


def write_melody(
    notes: list[NoteEvent],
    output_path: str,
    bpm: int = 120,
    ticks_per_beat: int = 480,
    channel: int = 0,
    program: int = 0,  # 0 = Acoustic Grand Piano
) -> None:
    """
    Write a monophonic melody (list of NoteEvents) to a MIDI file.
    """
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)

    track.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(Message("program_change", channel=channel, program=program, time=0))

    for note in notes:
        duration_ticks = beats_to_ticks(note.duration, ticks_per_beat)
        if note.is_rest or note.velocity == 0:
            track.append(Message("note_on", channel=channel, note=60, velocity=0, time=duration_ticks))
        else:
            midi_note = max(0, min(127, note.midi_note))
            velocity = max(1, min(127, note.velocity))
            track.append(Message("note_on", channel=channel, note=midi_note, velocity=velocity, time=0))
            track.append(Message("note_off", channel=channel, note=midi_note, velocity=0, time=duration_ticks))

    mid.save(output_path)
    print(f"✓ Melody saved → {output_path}  ({len(notes)} notes, {bpm} BPM)")


def write_chords(
    chords: list[ChordEvent],
    output_path: str,
    bpm: int = 90,
    ticks_per_beat: int = 480,
    channel: int = 0,
    program: int = 0,
) -> None:
    """
    Write a chord progression (list of ChordEvents) to a MIDI file.
    Each chord's notes are triggered simultaneously.
    """
    mid = MidiFile(ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    mid.tracks.append(track)

    track.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(Message("program_change", channel=channel, program=program, time=0))

    for chord in chords:
        duration_ticks = beats_to_ticks(chord.duration, ticks_per_beat)
        velocity = max(1, min(127, chord.velocity))
        valid_notes = [max(0, min(127, n)) for n in chord.midi_notes]

        # Note-on all chord tones simultaneously (time=0 for all after first)
        for i, note in enumerate(valid_notes):
            track.append(Message("note_on", channel=channel, note=note, velocity=velocity, time=0))

        # Note-off all chord tones after duration
        for i, note in enumerate(valid_notes):
            t = duration_ticks if i == 0 else 0
            track.append(Message("note_off", channel=channel, note=note, velocity=0, time=t))

    mid.save(output_path)
    print(f"✓ Chords saved → {output_path}  ({len(chords)} chords, {bpm} BPM)")


def write_combined(
    chords: list[ChordEvent],
    notes: list[NoteEvent],
    output_path: str,
    bpm: int = 100,
    ticks_per_beat: int = 480,
    chord_program: int = 48,  # 48 = Strings
    melody_program: int = 0,  # 0  = Piano
) -> None:
    """
    Write a two-track MIDI file (type 1): chord progression on track 0,
    melody on track 1. Both tracks are in a single .mid file.
    """
    mid = MidiFile(type=1, ticks_per_beat=ticks_per_beat)

    # ── Track 0: Chords ───────────────────────────────────────────────────────
    chord_track = MidiTrack()
    mid.tracks.append(chord_track)
    chord_track.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    chord_track.append(Message("program_change", channel=0, program=chord_program, time=0))

    for chord in chords:
        duration_ticks = beats_to_ticks(chord.duration, ticks_per_beat)
        velocity = max(1, min(127, chord.velocity))
        valid_notes = [max(0, min(127, n)) for n in chord.midi_notes]
        for note in valid_notes:
            chord_track.append(Message("note_on", channel=0, note=note, velocity=velocity, time=0))
        for i, note in enumerate(valid_notes):
            chord_track.append(Message("note_off", channel=0, note=note, velocity=0,
                                       time=duration_ticks if i == 0 else 0))

    # ── Track 1: Melody ───────────────────────────────────────────────────────
    melody_track = MidiTrack()
    mid.tracks.append(melody_track)
    melody_track.append(Message("program_change", channel=1, program=melody_program, time=0))

    for note in notes:
        duration_ticks = beats_to_ticks(note.duration, ticks_per_beat)
        if note.is_rest or note.velocity == 0:
            melody_track.append(Message("note_on", channel=1, note=60, velocity=0, time=duration_ticks))
        else:
            midi_note = max(0, min(127, note.midi_note))
            velocity = max(1, min(127, note.velocity))
            melody_track.append(Message("note_on", channel=1, note=midi_note, velocity=velocity, time=0))
            melody_track.append(Message("note_off", channel=1, note=midi_note, velocity=0, time=duration_ticks))

    mid.save(output_path)
    print(f"✓ Combined saved → {output_path}  ({len(chords)} chords + {len(notes)} melody notes, {bpm} BPM)")
