from lex2spdx.preprocess import normalize_license_field


def test_normalize_license_field():
    assert normalize_license_field(None) is None

    assert normalize_license_field("") == ""

    assert normalize_license_field("  MIT   License ") == "mit license"
    assert normalize_license_field("MIT License") == "mit license"

    assert normalize_license_field("License :: OSI Approved :: Apache Software License") == "apache software license"

    assert normalize_license_field("Apache License, Version 2.0") == "apache license version 2 0"
    assert normalize_license_field("Apache 2.0") == "apache 2 0"

    assert normalize_license_field("v1.0") == "1 0"
    assert normalize_license_field("Apache v2.0") == "apache 2 0"

    assert normalize_license_field("gpl3") == "gpl 3"
    assert normalize_license_field("GPLv3") == "gpl 3"

    assert normalize_license_field("MIT    license    or    Apache") == "mit license or apache"

    long_text = "a" * 1500
    truncated = normalize_license_field(long_text)
    assert len(truncated) <= 1000
