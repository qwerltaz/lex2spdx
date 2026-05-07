from lex2spdx.preprocess import normalize_license_field


def test_normalize_license_field():
    assert normalize_license_field(None) is None

    assert normalize_license_field("") == ""

    assert normalize_license_field("  MIT   License ") == "mit"
    assert normalize_license_field("MIT License") == "mit"

    assert normalize_license_field("License :: OSI Approved :: Apache Software License") == "apache"
    assert normalize_license_field("OSI Approved :: Apache Software License") == "apache"

    assert normalize_license_field("Apache License, Version 2.0") == "apache 2 0"
    assert normalize_license_field("Apache 2.0") == "apache 2 0"

    assert normalize_license_field("v1.0") == "1 0"
    assert normalize_license_field("Apache v2.0") == "apache 2 0"

    assert normalize_license_field("gpl3") == "gpl 3"
    assert normalize_license_field("GPLv3") == "gpl 3"

    assert normalize_license_field("MIT    license    or    Apache") == "mit or apache"

    long_text = "a" * 1500
    truncated = normalize_license_field(long_text)
    assert len(truncated) <= 1000


def test_normalize_license_field_remove_stop_words():
    assert normalize_license_field("MIT license Apache") == "mit apache"

    assert normalize_license_field("MIT license Apache", remove_stop_words=False) == "mit license apache"

    assert normalize_license_field("Apache 2 version 0", remove_stop_words=True) == "apache 2 0"
    assert normalize_license_field("Apache 2 version 0", remove_stop_words=False) == "apache 2 version 0"

    assert normalize_license_field("software Apache", remove_stop_words=True) == "apache"
    assert normalize_license_field("software Apache", remove_stop_words=False) == "software apache"

    assert normalize_license_field("the Apache software license", remove_stop_words=True) == "apache"
    assert normalize_license_field("the Apache software license",
                                   remove_stop_words=False) == "the apache software license"


def test_normalize_license_field_truncate_long_texts():
    long_text = "a" * 1500

    truncated = normalize_license_field(long_text, truncate_long_texts=True)
    assert len(truncated) <= 1000

    not_truncated = normalize_license_field(long_text, truncate_long_texts=False)
    assert len(not_truncated) > 1000


def test_normalize_license_field_custom_truncate_max_length():
    long_text = "a" * 1500

    truncated_500 = normalize_license_field(long_text, truncate_max_length=500)
    assert len(truncated_500) <= 500

    truncated_200 = normalize_license_field(long_text, truncate_max_length=200)
    assert len(truncated_200) <= 200

    not_truncated = normalize_license_field(long_text, truncate_long_texts=False, truncate_max_length=100)
    assert len(not_truncated) > 100


def test_normalize_license_field_arguments_combined():
    text = "The MIT license or Apache version 2 dot 0 " + "a" * 1000

    result = normalize_license_field(text, remove_stop_words=False, truncate_max_length=300)
    assert len(result) <= 300
    assert "license" in result
    assert "version" in result

    # Remove stop words and don't truncate
    result = normalize_license_field(text, remove_stop_words=True, truncate_long_texts=False)
    assert len(result) > 300
    assert "license" not in result
    assert "version" not in result
    assert "mit" in result
    assert "apache" in result
