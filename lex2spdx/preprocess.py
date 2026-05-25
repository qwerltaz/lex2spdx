import json
import re
from typing import overload

from lex2spdx import cvar

with open(cvar.resources_dir / "stop-words.json", "r", encoding="utf-8") as f:
    _stop_words = set(json.load(f))

# Leave alphanumeric characters and also those important to license classification, such as '+'.
_allowed_non_alphanumeric_chars = "+"
_allowed_non_alphanumeric_pattern = re.escape(_allowed_non_alphanumeric_chars)
_alphanumeric_plus_regex = re.compile(rf"(?ui)[^\w{_allowed_non_alphanumeric_pattern}]")


@overload
def normalize_license_field(text: None, *args, **kwargs) -> None: ...


@overload
def normalize_license_field(text: str, *args, **kwargs) -> str: ...


def normalize_license_field(text: str | None, remove_stop_words: bool = False, truncate_long_texts: bool = False,
                            truncate_max_length: int = 1000) -> str | None:
    """
    Normalize whitespace, spacing, and common wording variants in free-text license fields.

    :param text: The input text to normalize
    :param remove_stop_words: Whether to erase some unrelated words that do not alter classification.
    :param truncate_long_texts: Whether to truncate text if too long.
    :param truncate_max_length: Length to which truncate the text, if truncation is enabled.
    """
    if text is None:
        return None
    if text == "":
        return ""

    if text.lower().startswith("license ::") or text.lower().startswith("osi approved ::"):
        text = text.split("::")[-1]

    text = text.strip()

    if truncate_long_texts and len(text) > truncate_max_length:
        text = text[:truncate_max_length]

    text_normalized = _alphanumeric_plus_regex.sub(" ", text)
    text_normalized = text_normalized.strip().lower()

    text_normalized = re.sub(r"\s+", " ", text_normalized)

    # gpl3 -> gpl 3.
    text_normalized = re.sub(r"gpl(\d)", r"gpl \1", text_normalized)
    # gplv3 -> gpl 3.
    text_normalized = re.sub(r"gplv(\d)", r"gpl \1", text_normalized)

    if remove_stop_words:
        words = text_normalized.split()
        words = [word for word in words if word not in _stop_words]
        text_normalized = " ".join(words)

    return text_normalized
