import json
import re
from typing import overload

import rapidfuzz

from lex2spdx import cvar

_REMOVE_STOP_WORDS = False
_TRUNCATE_LONG_TEXTS = True
_TRUNCATE_MAX_LENGTH = 1000

with open(cvar.resources_dir / "stop-words.json", "r", encoding="utf-8") as f:
    _stop_words = set(json.load(f))


@overload
def normalize_license_field(text: None) -> None: ...


@overload
def normalize_license_field(text: str) -> str: ...


def normalize_license_field(text: str | None) -> str | None:
    """Normalize whitespace, spacing, and common wording variants in free-text license fields."""
    if text is None:
        return None
    if text == "":
        return ""

    if text.lower().startswith("license ::"):
        text = text.split("::")[-1].strip()

    if _TRUNCATE_LONG_TEXTS and len(text) > _TRUNCATE_MAX_LENGTH:
        text = text[:_TRUNCATE_MAX_LENGTH]

    text_normalized = rapidfuzz.utils.default_process(text)

    # v1.0 -> ␣1.0.
    text_normalized = re.sub(r"v(\d)", r" \1", text_normalized)

    text_normalized = re.sub(r"\s+", " ", text_normalized.strip())

    # gpl3 -> gpl 3 0.
    text_normalized = re.sub(r"gpl(\d)", r"gpl \1", text_normalized)

    if _REMOVE_STOP_WORDS:
        words = text_normalized.split()
        words = [word for word in words if word not in _stop_words]
        text_normalized = " ".join(words)

    return text_normalized
