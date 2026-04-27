

import os
from django.core.exceptions import ValidationError
from django.conf import settings

# Magic bytes

FILE_SIGNATURES = {
    b"\x25\x50\x44\x46": "application/pdf",       # %PDF
    b"\xff\xd8\xff":     "image/jpeg",              # JPEG/JPG
    b"\x89\x50\x4e\x47": "image/png",              # PNG
}

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_SIZE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 5 MB


def _sniff_mimetype(file_obj) -> str | None:
    """Sniff file type by magic bytes."""
    file_obj.seek(0)
    header = file_obj.read(8)
    file_obj.seek(0)

    for signature, mimetype in FILE_SIGNATURES.items():
        if header.startswith(signature):
            return mimetype
    return None


def validate_upload(file_obj) -> None:
    """Validate uploaded file size, extension, and content."""
    # Size check
    if file_obj.size > MAX_SIZE_BYTES:
        raise ValidationError(
            f"File '{file_obj.name}' is {file_obj.size / (1024*1024):.1f} MB. "
            f"Maximum allowed size is {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    # Extension check
    _, ext = os.path.splitext(file_obj.name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"File extension '{ext}' is not allowed. "
            f"Accepted formats: PDF, JPG, PNG."
        )

    # Magic-byte check
    detected = _sniff_mimetype(file_obj)
    if detected is None:
        raise ValidationError(
            f"File '{file_obj.name}' does not appear to be a valid PDF, JPG, or PNG. "
            f"Upload was rejected."
        )

    # Cross-check
    ext_to_expected_mime = {
        ".pdf":  "application/pdf",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png":  "image/png",
    }
    expected = ext_to_expected_mime.get(ext)
    if detected != expected:
        raise ValidationError(
            f"File content does not match its extension. "
            f"Extension says '{ext}' but file is actually '{detected}'. Upload rejected."
        )
