import lex2spdx.maps


def test_map_na():
    """Should not have uppercase letters."""
    map_na = lex2spdx.maps.MapNA()
    for value in map_na.bad_values:
        assert value == value.lower(), "All values should be lowercase."

    assert map_na.map("Free for non-commercial use") == ""


def test_map_exact_id():
    map_exact_id = lex2spdx.maps.MapExactID()

    assert map_exact_id.map("MIT") == "MIT"
    assert map_exact_id.map("MIT License") is None
    assert map_exact_id.map("") is None
    assert map_exact_id.map("GNU LIBRARY GENERAL PUBLIC LICENSE Version 2, June 1991") is None


def test_map_exact_match():
    map_exact_match = lex2spdx.maps.MapExactMatch()

    # Title text
    assert map_exact_match.map("MIT License") == "MIT"
    assert map_exact_match.map("MIT License ") is None
    assert map_exact_match.map("MIT  License") is None
    assert map_exact_match.map("mit  License") is None
    # Both IDs have the same title text, for now accept either, will think if this is ok or not.
    assert map_exact_match.map("GNU LIBRARY GENERAL PUBLIC LICENSE Version 2, June 1991") in ("LGPL-2.0", "LGPL-2.0+")
    # Name
    assert map_exact_match.map("The Unlicense") == "Unlicense"
    # Text
    assert map_exact_match.map(
        "Copyright (c) 1992, 1991, 1990 MIPS Computer Systems, Inc. MIPS Computer Systems, Inc. grants "
        "reproduction and use rights to all parties, PROVIDED that this comment is maintained in the copy.") == "MIPS"


def test_map_substring():
    map_substring = lex2spdx.maps.MapSubstring()

    # Title text
    assert map_substring.map("MIT License") == "MIT"
    assert map_substring.map(" MIT License ") == "MIT"
    # Name
    assert map_substring.map("The Unlicense") == "Unlicense"
    # Text
    assert map_substring.map(
        "Copyright (c) 1992, 1991, 1990 MIPS Computer Systems, Inc. MIPS Computer Systems, Inc. grants "
        "reproduction and use rights to all parties, PROVIDED that this comment is maintained in the copy.") == "MIPS"
    assert (map_substring.map(
        "lipsum Copyright (c) 1992, 1991, 1990 MIPS Computer Systems, Inc. MIPS Computer Systems, Inc. grants "
        "reproduction and use rights to all parties, PROVIDED that this comment is maintained in the copy. lipsum")
            == "MIPS")

    assert map_substring.map("MIT  License") is None
