"""
image_preprocessor.py — OpenCV-based image preprocessing for OCR.

Improves OCR accuracy on scanned legal notices and low-quality photographs by
applying a standard preprocessing pipeline before Tesseract sees the image.

Pipeline (applied in order):
  1. Grayscale conversion
  2. Upscaling  — if shortest dimension < 1000 px (Tesseract needs ≥ 300 dpi)
  3. Deskew     — correct document rotation up to ±45°
  4. Denoise    — fast NL-means denoising
  5. Binarize   — Otsu's thresholding (uniform light) or adaptive Gaussian
                   (non-uniform / shadow-heavy scans)

Graceful fallback:
  If opencv-python-headless is not installed the original path is returned
  unchanged and an empty steps list is returned.  The caller must not fail.

Usage:
    from app.utils.image_preprocessor import preprocess_image
    out_path, steps = preprocess_image("/tmp/upload.jpg")
    # out_path is a NEW temp file when preprocessing ran; caller must delete it.
    # out_path == src_path when OpenCV is unavailable (no new file created).
"""
from __future__ import annotations

import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# Minimum image dimension in pixels; smaller images are upscaled for Tesseract.
_MIN_DIM = 1200

# Images whose grayscale pixel std-dev exceeds this threshold are considered
# to have non-uniform illumination and receive adaptive instead of Otsu binarization.
_ADAPTIVE_STD_THRESHOLD = 55.0


def preprocess_image(src_path: str) -> tuple[str, list[str]]:
    """
    Apply OpenCV preprocessing to an image to improve OCR accuracy.

    Returns:
        (output_path, steps_applied)
        output_path — path to the preprocessed image (new temp file), OR
                      src_path unchanged when OpenCV is unavailable.
        steps_applied — list of human-readable step names that were executed.

    The caller is responsible for deleting output_path if it differs from
    src_path (i.e. a new temp file was created by this function).
    """
    steps: list[str] = []

    # ── Dependency check ───────────────────────────────────────────────────────
    try:
        import cv2            # type: ignore  # opencv-python-headless
        import numpy as np    # type: ignore  # installed as cv2 dependency
    except ImportError:
        logger.warning(
            "opencv-python-headless not installed — image preprocessing skipped. "
            "Run: pip install opencv-python-headless"
        )
        return src_path, steps

    # ── Load image ─────────────────────────────────────────────────────────────
    img_bgr = cv2.imread(src_path)

    if img_bgr is None:
        # cv2.imread can fail on some PNG/JPEG variants; fall back to Pillow → numpy
        try:
            from PIL import Image as _PILImage
            pil = _PILImage.open(src_path).convert("RGB")
            img_bgr = np.array(pil)[:, :, ::-1].copy()   # RGB → BGR
        except Exception as load_err:
            logger.warning("Could not load image for preprocessing: %s", load_err)
            return src_path, steps

    h, w = img_bgr.shape[:2]

    # ── Step 1: Grayscale ──────────────────────────────────────────────────────
    if len(img_bgr.shape) == 3:
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = img_bgr
    steps.append("grayscale")

    # ── Step 2: Upscale ────────────────────────────────────────────────────────
    min_dim = min(h, w)
    if min_dim < _MIN_DIM:
        scale = _MIN_DIM / min_dim
        gray = cv2.resize(
            gray, None,
            fx=scale, fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )
        steps.append(f"upscale_{scale:.2f}x")

    # ── Step 3: Deskew ─────────────────────────────────────────────────────────
    gray, deskew_step = _deskew(gray, cv2, np)
    if deskew_step:
        steps.append(deskew_step)

    # ── Step 4: Denoise ────────────────────────────────────────────────────────
    gray = cv2.fastNlMeansDenoising(
        gray, h=10,
        templateWindowSize=7,
        searchWindowSize=21,
    )
    steps.append("denoise")

    # ── Step 5: Binarize ───────────────────────────────────────────────────────
    std_dev = float(np.std(gray))
    if std_dev > _ADAPTIVE_STD_THRESHOLD:
        # Non-uniform illumination (shadows, curved pages) — adaptive Gaussian
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=11,
        )
        steps.append("adaptive_threshold")
    else:
        # Uniform illumination — Otsu's global threshold
        _, binary = cv2.threshold(
            gray, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU,
        )
        steps.append("otsu_threshold")

    # ── Write preprocessed image to temp file ──────────────────────────────────
    suffix = os.path.splitext(src_path)[1] or ".png"
    fd, out_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    if not cv2.imwrite(out_path, binary):
        logger.warning("cv2.imwrite failed for %s — returning original", out_path)
        try:
            os.unlink(out_path)
        except OSError:
            pass
        return src_path, []

    logger.info(
        "Image preprocessed: steps=%s  src_size=%dx%d  out=%s",
        steps, w, h, out_path,
    )
    return out_path, steps


# ── Internal helpers ───────────────────────────────────────────────────────────

def _deskew(
    gray,          # numpy.ndarray
    cv2,           # already-imported cv2 module
    np,            # already-imported numpy module
) -> tuple:        # (numpy.ndarray, str)
    """
    Detect and correct document skew using minAreaRect on dark pixels.
    Returns (corrected_image, step_label) where step_label is "" when no
    correction was needed (|angle| < 0.5°) or OpenCV had insufficient data.
    """
    # Find dark pixels (text on white background)
    dark_mask = gray < 128
    coords = np.column_stack(np.where(dark_mask))

    if len(coords) < 200:
        return gray, ""

    try:
        rect = cv2.minAreaRect(coords.astype(np.float32))
        angle = rect[-1]
    except Exception:
        return gray, ""

    # minAreaRect returns angle in [-90, 0).
    # Convert to intuitive rotation direction.
    if angle < -45.0:
        angle = -(90.0 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return gray, ""

    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, f"deskew_{angle:+.1f}deg"
