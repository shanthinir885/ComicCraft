"""Generic helpers: filename sanitisation, safe paths, JSON extraction, logging."""

from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from app.config import settings

logger = logging.getLogger("comiccraft")

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9-]+")


def configure_logging() -> None:
    """Configure root logging once, at application start-up."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


def sanitize_filename(value: str, max_length: int = 48) -> str:
    """Return a filesystem-safe slug derived from arbitrary user/AI text."""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _UNSAFE_CHARS.sub("_", ascii_only).strip("._-").lower()
    slug = re.sub(r"_{2,}", "_", slug)
    if not slug:
        slug = "comiccraft"
    return slug[:max_length]


def unique_filename(prefix: str, extension: str) -> str:
    """Build a timestamped, collision-resistant filename."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:6]
    ext = extension.lstrip(".")
    return f"{sanitize_filename(prefix)}_{stamp}_{suffix}.{ext}"


def ensure_within(base: Path, candidate: Path) -> Path:
    """Guarantee *candidate* resolves inside *base*; raise otherwise."""
    base_resolved = base.resolve()
    candidate_resolved = candidate.resolve()
    if base_resolved not in candidate_resolved.parents and base_resolved != candidate_resolved:
        raise ValueError("Resolved path escapes its allowed directory.")
    return candidate_resolved


def static_url(path: Path) -> str:
    """Convert an absolute path inside /static into a browser-usable URL."""
    try:
        relative = path.resolve().relative_to(settings.STATIC_DIR.resolve())
    except ValueError:
        return ""
    return "/static/" + relative.as_posix()


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences that LLMs frequently wrap JSON in."""
    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        if cleaned.endswith("```"):
            cleaned = cleaned[: -3]
    return cleaned.strip()


def extract_json(text: str) -> Optional[Any]:
    """Defensively extract the first valid JSON object/array from model output.

    Strategy: strip fences -> direct parse -> bracket-balanced substring scan.
    Returns ``None`` when no valid JSON can be recovered.
    """
    if not text:
        return None

    cleaned = strip_code_fences(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(cleaned)):
            char = cleaned[index]
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    snippet = cleaned[start : index + 1]
                    try:
                        return json.loads(snippet)
                    except json.JSONDecodeError:
                        break
    return None


def truncate(text: str, limit: int) -> str:
    """Trim text to *limit* characters without cutting mid-word when avoidable."""
    value = " ".join(str(text).split())
    if len(value) <= limit:
        return value
    clipped = value[:limit].rsplit(" ", 1)[0]
    return (clipped or value[:limit]).rstrip() + "…"
