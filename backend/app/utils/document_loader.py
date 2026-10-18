"""
document_loader.py — Upload validation, type detection, and temporary file management.

Receives an UploadFile from the /api/analyze-document endpoint, validates it,
and writes the bytes to an OS temp file so extraction libraries can open it by path.
Callers must call cleanup_temp(doc.tmp_path) when done.
"""
from __future__ import annotations

import logging
import os
import tempfile
import io
import zipfile
from dataclasses import dataclass

from fastapi import UploadFile

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

# MIME type → internal file_type token
_MIME_MAP: dict[str, str] = {
    "text/plain": "txt",
    "application/pdf":                                                          "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":  "docx",
    "image/png":  "image",
    "image/jpeg": "image",
    "image/jpg":  "image",
}

# Extension → internal file_type token (fallback when MIME is generic/missing)
_EXT_MAP: dict[str, str] = {
    ".txt": "txt",
    ".pdf":  "pdf",
    ".docx": "docx",
    ".png":  "image",
    ".jpg":  "image",
    ".jpeg": "image",
}

# Internal file_type → temp-file suffix used when saving
# Images keep their original extension so Pillow can detect format correctly.
_DEFAULT_SUFFIX: dict[str, str] = {
    "txt": ".txt",
    "pdf":  ".pdf",
    "docx": ".docx",
    "image": ".png",  # overridden per actual extension below
}

# Magic byte signatures — defence-in-depth against filename spoofing.
# Key is file_type; values are accepted leading byte sequences.
_MAGIC_SIGS: dict[str, list[bytes]] = {
    "pdf":   [b"%PDF"],
    "docx":  [b"PK\x03\x04"],      # DOCX/XLSX/ZIP all share the PK header
    "image": [b"\x89PNG", b"\xff\xd8\xff"],  # PNG, JPEG
}


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class TempDocument:
    """A validated upload saved to a temporary file on disk."""
    tmp_path:     str   # Absolute path — delete after use
    file_type:    str   # "pdf" | "docx" | "image"
    filename:     str   # Original filename (sanitised for logging only)
    size_bytes:   int
    content_type: str   # MIME as reported by the browser


# ── Helpers ───────────────────────────────────────────────────────────────────

def detect_type(filename: str, content_type: str) -> str | None:
    """
    Resolve file_type from MIME first, then extension.
    Returns "pdf", "docx", "image", or None if unsupported.
    """
    mime = (content_type or "").lower().split(";")[0].strip()
    if mime in _MIME_MAP:
        return _MIME_MAP[mime]

    ext = os.path.splitext((filename or "").lower())[1]
    return _EXT_MAP.get(ext)


def _check_magic_bytes(data: bytes, file_type: str, filename: str) -> None:
    """
    Compare the file's leading bytes against expected magic signatures.
    Logs a warning on mismatch — does NOT raise, because the extractor
    libraries (pypdf, python-docx, Pillow) are the authoritative fail-safe.
    This is a defence-in-depth signal only.
    """
    if len(data) < 4:
        logger.warning("File too short for magic-byte check: %s (%d bytes)", filename, len(data))
        return

    sigs = _MAGIC_SIGS.get(file_type, [])
    if not sigs:
        return

    for sig in sigs:
        if data[:len(sig)] == sig:
            return  # signature matched — all good

    raise ValueError("The file contents do not match the selected file type. Please upload an uncorrupted document.")


# ── Public API ────────────────────────────────────────────────────────────────

async def load_upload(upload: UploadFile) -> TempDocument:
    """
    Read the UploadFile, validate it, and write it to an OS temp file.
    Raises ValueError on unsupported type, empty file, or file too large.
    The caller is responsible for cleanup via cleanup_temp(doc.tmp_path).
    """
    filename     = upload.filename or "upload"
    content_type = upload.content_type or ""

    # ── Type detection ────────────────────────────────────────────────────────
    file_type = detect_type(filename, content_type)
    if file_type is None:
        ext = os.path.splitext(filename)[1] or content_type
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            "Please upload a PDF, DOCX, TXT, PNG, or JPG file."
        )

    # ── Read bytes ────────────────────────────────────────────────────────────
    data = await upload.read(MAX_FILE_BYTES + 1)
    size_bytes = len(data)

    if size_bytes == 0:
        raise ValueError("The uploaded file is empty.")

    if size_bytes > MAX_FILE_BYTES:
        mb = size_bytes / (1024 * 1024)
        raise ValueError(
            f"File size ({mb:.1f} MB) exceeds the 10 MB limit."
        )

    # ── Magic bytes validation ─────────────────────────────────────────────────
    _check_magic_bytes(data, file_type, filename)
    if file_type == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(item.file_size for item in entries) > 100 * 1024 * 1024:
                    raise ValueError("This DOCX expands beyond the document processing limit.")
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("The uploaded archive is not a Word document.")
        except zipfile.BadZipFile as exc:
            raise ValueError("The DOCX file is damaged.") from exc

    # ── Write to temp file ────────────────────────────────────────────────────
    # Use the original extension for images so Pillow can detect format.
    if file_type == "image":
        ext = os.path.splitext(filename.lower())[1]
        suffix = ext if ext in (".png", ".jpg", ".jpeg") else ".png"
    else:
        suffix = _DEFAULT_SUFFIX[file_type]

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    logger.info(
        "Loaded upload: filename=%s  type=%s  size=%d B  tmp=%s",
        filename, file_type, size_bytes, tmp_path,
    )
    return TempDocument(
        tmp_path=tmp_path,
        file_type=file_type,
        filename=filename,
        size_bytes=size_bytes,
        content_type=content_type,
    )


def cleanup_temp(path: str) -> None:
    """Delete a temporary file. Logs a warning on failure instead of raising."""
    try:
        if path and os.path.exists(path):
            os.unlink(path)
            logger.debug("Deleted temp file: %s", path)
    except OSError as exc:
        logger.warning("Could not delete temp file %s: %s", path, exc)
