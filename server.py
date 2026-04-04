"""
server.py - Flask backend for Chromesthesia web app.

Routes:
  GET  /           to serves the frontend (static HTML/CSS/JS)
  POST /generate   to accepts image + options, returns .mid file download
"""

import os
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, jsonify, send_from_directory

from src.algorithm import generate_melody, generate_chords, generate_combined, DEFAULT_BPM

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "tiff"}

VALID_MODES = {"melody", "chords", "combined"}
VALID_SCALES = {"major", "minor", "pentatonic", "dorian", "mixolydian", "chromatic"}
VALID_KEYS = {
    "C", "C#", "Db", "D", "D#", "Eb", "E", "F",
    "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B",
}
VALID_SCANS = {"horizontal", "vertical", "diagonal", "spiral"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/generate", methods=["POST"])
def generate():
    # ── Validate image upload ─────────────────────────────────────────────────
    if "image" not in request.files:
        return jsonify({"error": "No image file uploaded"}), 400

    file = request.files["image"]
    if file.filename == "" or not _allowed_file(file.filename):
        return jsonify({"error": f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"}), 400

    # ── Parse options ─────────────────────────────────────────────────────────
    mode = request.form.get("mode", "combined")
    key = request.form.get("key", "C")
    scale = request.form.get("scale", "major")
    scan = request.form.get("scan", "horizontal")
    n_chords = int(request.form.get("chords", "4"))
    stride = int(request.form.get("stride", "4"))

    if mode not in VALID_MODES:
        return jsonify({"error": f"Invalid mode. Choose from: {VALID_MODES}"}), 400
    if key not in VALID_KEYS:
        return jsonify({"error": f"Invalid key. Choose from: {sorted(VALID_KEYS)}"}), 400
    if scale not in VALID_SCALES:
        return jsonify({"error": f"Invalid scale. Choose from: {VALID_SCALES}"}), 400
    if scan not in VALID_SCANS:
        return jsonify({"error": f"Invalid scan mode. Choose from: {VALID_SCANS}"}), 400
    if n_chords not in (4, 8):
        return jsonify({"error": "Chords must be 4 or 8"}), 400

    # ── Save uploaded image to temp file ──────────────────────────────────────
    tmp_dir = tempfile.mkdtemp()
    ext = file.filename.rsplit(".", 1)[1].lower()
    image_path = os.path.join(tmp_dir, f"upload.{ext}")
    output_path = os.path.join(tmp_dir, "output.mid")

    try:
        file.save(image_path)

        # ── Run the algorithm ─────────────────────────────────────────────────
        if mode == "melody":
            generate_melody(
                image_path, output_path,
                root=key, scale=scale,
                scan_mode=scan, stride=stride,
                bpm=DEFAULT_BPM, n_bars=n_chords,
            )
        elif mode == "chords":
            generate_chords(
                image_path, output_path,
                root=key, scale=scale,
                n_chords=n_chords, bpm=DEFAULT_BPM,
                scan_mode=scan, stride=stride,
            )
        elif mode == "combined":
            generate_combined(
                image_path, output_path,
                root=key, scale=scale,
                scan_mode=scan, stride=stride,
                n_chords=n_chords, bpm=DEFAULT_BPM,
            )

        # ── Return MIDI file as download ──────────────────────────────────────
        return send_file(
            output_path,
            mimetype="audio/midi",
            as_attachment=True,
            download_name=f"chromatic-synthesis-{mode}-{key}-{scale}.mid",
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        # Clean up temp files
        for f in Path(tmp_dir).glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass


if __name__ == "__main__":
    print("\nChromesthesia - Web App")
    print("   http://localhost:5000\n")
    app.run(debug=True, port=5000)
