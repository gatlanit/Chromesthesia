"""
image_reader.py
Handles image loading and pixel sampling along configurable paths.
"""

from PIL import Image
import numpy as np
from typing import Generator


def load_image(path: str, max_dimension: int = 512) -> Image.Image:
    """
    Load an image and resize it so no dimension exceeds max_dimension.
    Converts to RGBA to ensure consistent 4-channel access.
    """
    img = Image.open(path).convert("RGBA")
    img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    return img


def get_pixels(img: Image.Image) -> np.ndarray:
    """Return image as (H, W, 4) RGBA numpy array."""
    return np.array(img, dtype=np.uint8)


def sample_horizontal(pixels: np.ndarray, stride: int = 1) -> Generator:
    """
    Scan left→right, top→bottom. Yields (r, g, b, a) tuples.
    stride: take every Nth pixel to control note density.
    """
    h, w, _ = pixels.shape
    for row in range(0, h, max(stride, 1)):
        for col in range(0, w, max(stride, 1)):
            yield tuple(pixels[row, col])


def sample_vertical(pixels: np.ndarray, stride: int = 1) -> Generator:
    """Scan top→bottom, left→right."""
    h, w, _ = pixels.shape
    for col in range(0, w, max(stride, 1)):
        for row in range(0, h, max(stride, 1)):
            yield tuple(pixels[row, col])


def sample_diagonal(pixels: np.ndarray, stride: int = 1) -> Generator:
    """
    Scan along diagonals (top-left to bottom-right).
    Creates interesting cross-cutting melodic movement.
    """
    h, w, _ = pixels.shape
    for d in range(0, h + w - 1, max(stride, 1)):
        for row in range(max(0, d - w + 1), min(h, d + 1)):
            col = d - row
            if 0 <= col < w:
                yield tuple(pixels[row, col])


def sample_spiral(pixels: np.ndarray, stride: int = 1) -> Generator:
    """
    Spiral inward from edges to center.
    Creates a sense of journey toward the image's core.
    """
    arr = pixels.copy()
    top, bottom, left, right = 0, arr.shape[0] - 1, 0, arr.shape[1] - 1
    count = 0

    while top <= bottom and left <= right:
        for col in range(left, right + 1):
            if count % max(stride, 1) == 0:
                yield tuple(arr[top, col])
            count += 1
        top += 1
        for row in range(top, bottom + 1):
            if count % max(stride, 1) == 0:
                yield tuple(arr[row, right])
            count += 1
        right -= 1
        if top <= bottom:
            for col in range(right, left - 1, -1):
                if count % max(stride, 1) == 0:
                    yield tuple(arr[bottom, col])
                count += 1
            bottom -= 1
        if left <= right:
            for row in range(bottom, top - 1, -1):
                if count % max(stride, 1) == 0:
                    yield tuple(arr[row, left])
                count += 1
            left += 1


SCAN_MODES = {
    "horizontal": sample_horizontal,
    "vertical": sample_vertical,
    "diagonal": sample_diagonal,
    "spiral": sample_spiral,
}


def sample_image(img: Image.Image, mode: str = "horizontal", stride: int = 1) -> Generator:
    """
    Sample pixels from image using the named scan mode.
    mode: one of 'horizontal', 'vertical', 'diagonal', 'spiral'
    stride: take every Nth pixel
    """
    if mode not in SCAN_MODES:
        raise ValueError(f"Unknown scan mode '{mode}'. Choose from: {list(SCAN_MODES)}")
    pixels = get_pixels(img)
    return SCAN_MODES[mode](pixels, stride)


def get_regions(img: Image.Image, n: int, axis: str = "vertical") -> list[np.ndarray]:
    """
    Divide image into N equal strips along the given axis.
    Returns list of pixel arrays, one per strip.
    axis: 'vertical' (left→right strips) or 'horizontal' (top→bottom strips)
    """
    pixels = get_pixels(img)
    h, w, _ = pixels.shape

    if axis == "vertical":
        strip_width = max(w // n, 1)
        return [pixels[:, i * strip_width:(i + 1) * strip_width, :] for i in range(n)]
    elif axis == "horizontal":
        strip_height = max(h // n, 1)
        return [pixels[i * strip_height:(i + 1) * strip_height, :, :] for i in range(n)]
    else:
        raise ValueError(f"Unknown axis '{axis}'. Use 'vertical' or 'horizontal'.")


def average_region(region: np.ndarray) -> tuple[float, float, float, float]:
    """Return mean (R, G, B, A) of a pixel region."""
    return tuple(region.mean(axis=(0, 1)).tolist())
