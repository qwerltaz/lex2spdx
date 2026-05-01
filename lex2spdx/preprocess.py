import re

import rapidfuzz


def normalize_license_field(text: str | None) -> str | None:
    """Normalize whitespace, spacing, and common wording variants in free-text license fields."""
    if text is None:
        return None
    if text == "":
        return ""

    if text.lower().startswith("license ::"):
        text = text.split("::")[-1].strip()

    text_normalized = rapidfuzz.utils.default_process(text)

    text_normalized = re.sub(r"\s+", " ", text_normalized.strip())

    # gplv3 -> gpl 3 0
    text_normalized = re.sub(r"gplv(\d)", r"gpl \1 0", text_normalized)

    return text_normalized
