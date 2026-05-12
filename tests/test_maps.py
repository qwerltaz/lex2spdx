from _pytest.monkeypatch import MonkeyPatch

import lex2spdx.maps
from lex2spdx.maps import MapFuzzyMatch, MapResult
from lex2spdx.spdx_license_data import LicenseDataNormalized
from lex2spdx.preprocess import normalize_license_field


def test_map_na():
    """Should not have uppercase letters."""
    map_na = lex2spdx.maps.MapNA()
    for value in map_na.bad_values:
        assert value == value.lower(), "All values should be lowercase."

    unmappable_values = [
        "license.txt",
        "free for non commercial use",
        "inline license",
    ]
    unmappable_values = [normalize_license_field(x) for x in unmappable_values]

    for value in unmappable_values:
        assert value is not None
        value_str: str = value
        assert map_na.map(value_str) == "", f"Value '{value_str}' should be mapped to empty string."


def test_map_exact_id():
    map_exact_id = lex2spdx.maps.MapExactID()

    result = map_exact_id.map("mit")
    assert result == MapResult("mit", "spdx_id")
    assert map_exact_id.map("mit license") is None
    assert map_exact_id.map("") is None
    assert map_exact_id.map("gnu library general public license version 2 june 1991") is None


def test_map_exact_match():
    map_exact_match = lex2spdx.maps.MapExactMatch()

    # Name
    assert map_exact_match.map("mit license version") is None
    assert map_exact_match.map("mit licence") is None
    assert map_exact_match.map("mit licensee") is None
    # Text
    result = map_exact_match.map(normalize_license_field(
        "copyright c 1992 1991 1990 mips computer systems inc mips computer systems inc grants "
        "reproduction and use rights to all parties provided that this comment is maintained in the copy"))
    assert result == MapResult("mips", "spdx_id")


def test_map_substring():
    map_substring = lex2spdx.maps.MapSubstring()

    # Name
    result = map_substring.map("the unlicense")
    assert result == MapResult("unlicense", "spdx_id")
    # Text
    result = map_substring.map(
        "copyright c 1992 1991 1990 mips computer systems inc mips computer systems inc grants "
        "reproduction and use rights to all parties provided that this comment is maintained in the copy")
    assert result == MapResult("mips", "spdx_id")
    result = map_substring.map(
        "lipsum copyright c 1992 1991 1990 mips computer systems inc mips computer systems inc grants "
        "reproduction and use rights to all parties provided that this comment is maintained in the copy lipsum")
    assert result == MapResult("mips", "spdx_id")


def test_map_license_family():
    map_family = lex2spdx.maps.MapLicenseFamily()

    result = map_family.map("bsd")
    assert result == MapResult("BSD", "license_family")

    result = map_family.map("gpl")
    assert result == MapResult("GPL", "license_family")

    assert map_family.map("mit") is None
    assert map_family.map("unknown") is None


def create_and_patch_fuzzy_map(monkeypatch: MonkeyPatch) -> MapFuzzyMatch:
    map_fuzzy_match = lex2spdx.maps.MapFuzzyMatch()

    monkeypatch.setattr(LicenseDataNormalized, "license_ids", ["spdx 0", "spdx 1"])
    monkeypatch.setattr(LicenseDataNormalized, "license_names", ["name 0", "name 1"])
    monkeypatch.setattr(LicenseDataNormalized, "license_texts", ["text 0", "text 1"])
    return map_fuzzy_match


def test_map_fuzzy_match_prioritizes_id_name_title_over_full_text(monkeypatch: MonkeyPatch):
    map_fuzzy_match = create_and_patch_fuzzy_map(monkeypatch)

    def fake_extract_one(query, choices, processor=None, scorer=None):
        if choices is LicenseDataNormalized.license_ids:
            return "spdx 0", 91.0, 0
        if choices is LicenseDataNormalized.license_names:
            return "name 0", 92.0, 0
        return "text 1", 99.0, 1

    monkeypatch.setattr(lex2spdx.maps.rapidfuzz.process, "extractOne", fake_extract_one)

    result = map_fuzzy_match.map("sample")
    assert result == MapResult("spdx 0", "spdx_id")


def test_map_fuzzy_match_uses_text_fallback_only_when_priority_below_threshold(monkeypatch: MonkeyPatch):
    map_fuzzy_match = create_and_patch_fuzzy_map(monkeypatch)

    def fake_extract_one(query, choices, processor=None, scorer=None):
        if choices is LicenseDataNormalized.license_ids:
            return "spdx 0", 70.0, 0
        if choices is LicenseDataNormalized.license_names:
            return "name 0", 80.0, 0
        return "text 1", 95.0, 1

    monkeypatch.setattr(lex2spdx.maps.rapidfuzz.process, "extractOne", fake_extract_one)

    result = map_fuzzy_match.map("sample")
    assert result == MapResult("spdx 1", "spdx_id")


def test_map_fuzzy_match_does_not_match_short_spdx_id_as_substring(monkeypatch: MonkeyPatch):
    """Regression: avoid mapping to SPDX id 'doc' just because input contains 'documentation'."""
    map_fuzzy_match = lex2spdx.maps.MapFuzzyMatch()

    # Minimal synthetic SPDX data: make sure we have a short id ('doc')
    # and the correct one ('mit'). Token-based scoring should pick MIT.
    monkeypatch.setattr(LicenseDataNormalized, "license_ids", ["doc", "mit"])
    monkeypatch.setattr(LicenseDataNormalized, "license_names", ["doc", "mit"])
    monkeypatch.setattr(LicenseDataNormalized, "license_texts", ["doc license text", "mit license text"])
    monkeypatch.setattr(LicenseDataNormalized, "license_title_texts", ["doc title", "mit title"])

    license_field = normalize_license_field(
        "MIT License Copyright (c) 2023 ... associated documentation files"
    )

    assert map_fuzzy_match.map(license_field) == MapResult("mit", "spdx_id")
