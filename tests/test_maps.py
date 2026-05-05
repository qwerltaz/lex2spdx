from _pytest.monkeypatch import MonkeyPatch

import lex2spdx.maps
from lex2spdx.maps import MapFuzzyMatch
from lex2spdx.spdx_license_data import LicenseDataNormalized


def test_map_na():
    """Should not have uppercase letters."""
    map_na = lex2spdx.maps.MapNA()
    for value in map_na.bad_values:
        assert value == value.lower(), "All values should be lowercase."

    assert map_na.map("free for non commercial use") == ""
    assert map_na.map("license txt") == ""
    assert map_na.map("inline license") == ""


def test_map_exact_id():
    map_exact_id = lex2spdx.maps.MapExactID()

    assert map_exact_id.map("mit") == "mit"
    assert map_exact_id.map("mit license") is None
    assert map_exact_id.map("") is None
    assert map_exact_id.map("gnu library general public license version 2 june 1991") is None


def test_map_exact_match():
    map_exact_match = lex2spdx.maps.MapExactMatch()

    # Name
    assert map_exact_match.map("mit license") == "mit"
    assert map_exact_match.map("mit license version") is None
    assert map_exact_match.map("mit licence") is None
    assert map_exact_match.map("mit licensee") is None
    assert map_exact_match.map("the unlicense") == "unlicense"
    # Text
    assert map_exact_match.map(
        "copyright c 1992 1991 1990 mips computer systems inc mips computer systems inc grants "
        "reproduction and use rights to all parties provided that this comment is maintained in the copy") == "mips"


def test_map_substring():
    map_substring = lex2spdx.maps.MapSubstring()

    # Name
    assert map_substring.map("the unlicense") == "unlicense"
    # Text
    assert map_substring.map(
        "copyright c 1992 1991 1990 mips computer systems inc mips computer systems inc grants "
        "reproduction and use rights to all parties provided that this comment is maintained in the copy") == "mips"
    assert (map_substring.map(
        "lipsum copyright c 1992 1991 1990 mips computer systems inc mips computer systems inc grants "
        "reproduction and use rights to all parties provided that this comment is maintained in the copy lipsum")
            == "mips")

    assert map_substring.map("mit licence") is None


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

    assert map_fuzzy_match.map("sample") == "spdx 0"


def test_map_fuzzy_match_uses_text_fallback_only_when_priority_below_threshold(monkeypatch: MonkeyPatch):
    map_fuzzy_match = create_and_patch_fuzzy_map(monkeypatch)

    def fake_extract_one(query, choices, processor=None, scorer=None):
        if choices is LicenseDataNormalized.license_ids:
            return "spdx 0", 70.0, 0
        if choices is LicenseDataNormalized.license_names:
            return "name 0", 80.0, 0
        return "text 1", 95.0, 1

    monkeypatch.setattr(lex2spdx.maps.rapidfuzz.process, "extractOne", fake_extract_one)

    assert map_fuzzy_match.map("sample") == "spdx 1"
