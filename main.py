#!/usr/bin/env python3
"""
Chromatic Synthesis — Image → MIDI
Usage:
  python main.py --image photo.jpg --mode chords --key C --scale major --output out.mid
"""

import argparse
import sys
from pathlib import Path

from src.algorithm import generate_melody, generate_chords, generate_combined, DEFAULT_BPM
from src.color_mapper import SCALES, ROOT_OFFSETS


MODES = ["melody", "chords", "combined"]
SCAN_MODES = ["horizontal", "vertical", "diagonal", "spiral"]


def parse_args():
    parser = argparse.ArgumentParser(
        prog="chromatic-synthesis",
        description="Convert an image's RGBA values into a MIDI melody or chord progression.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --image sunset.jpg --mode chords --key D --output sunset.mid
  python main.py --image ocean.png  --mode melody --key Ab --scale minor --bars 8
  python main.py --image forest.jpg --mode combined --chords 8
        """,
    )

    parser.add_argument("--image", "-i", required=True, help="Path to input image file")
    parser.add_argument("--output", "-o", default=None, help="Path for output .mid file (default: <image>.mid)")
    parser.add_argument("--mode", "-m", choices=MODES, default="combined",
                        help="Generation mode: melody | chords | combined (default: combined)")

    # Musical parameters
    parser.add_argument("--key", "-k", default="C", choices=list(ROOT_OFFSETS.keys()),
                        help="Root key (default: C)")
    parser.add_argument("--scale", "-s", default="major", choices=list(SCALES.keys()),
                        help="Scale type (default: major)")
    parser.add_argument("--bpm", "-b", type=int, default=DEFAULT_BPM,
                        help=f"Tempo in BPM (default: {DEFAULT_BPM}). DAWs can change this on import.")

    # Melody parameters
    parser.add_argument("--scan", default="horizontal", choices=SCAN_MODES,
                        help="Pixel scan path for melody mode (default: horizontal)")
    parser.add_argument("--stride", type=int, default=4,
                        help="Sample every Nth pixel for melody (default: 4)")
    parser.add_argument("--bars", type=int, default=4,
                        help="Length of melody in bars (default: 4). In combined mode, melody matches chord length.")

    # Chord parameters
    parser.add_argument("--chords", "-n", type=int, default=4,
                        help="Number of chords in progression (default: 4)")
    parser.add_argument("--axis", default="vertical", choices=["vertical", "horizontal"],
                        help="Region split axis for chord mode (default: vertical)")
    parser.add_argument("--chord-duration", type=float, default=4.0,
                        help="Duration of each chord in beats (default: 4.0 = one bar)")

    return parser.parse_args()


def main():
    args = parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: image file not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or image_path.stem + ".mid"

    print(f"\n🎨 Chromatic Synthesis")
    print(f"   Image : {image_path}")
    print(f"   Mode  : {args.mode}")
    print(f"   Key   : {args.key} {args.scale}")
    print(f"   Output: {output_path}\n")

    if args.mode == "melody":
        generate_melody(
            str(image_path), output_path,
            root=args.key, scale=args.scale,
            scan_mode=args.scan, stride=args.stride,
            bpm=args.bpm, n_bars=args.bars,
        )

    elif args.mode == "chords":
        generate_chords(
            str(image_path), output_path,
            root=args.key, scale=args.scale,
            n_chords=args.chords, axis=args.axis,
            chord_duration=args.chord_duration, bpm=args.bpm,
        )

    elif args.mode == "combined":
        generate_combined(
            str(image_path), output_path,
            root=args.key, scale=args.scale,
            scan_mode=args.scan, stride=args.stride,
            n_chords=args.chords, axis=args.axis,
            chord_duration=args.chord_duration,
            bpm=args.bpm,
        )

    print(f"\n✅ Done. Open {output_path} in any DAW.")


if __name__ == "__main__":
    main()
