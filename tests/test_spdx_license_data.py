from __future__ import annotations

from pathlib import Path

import pytest

from lex2spdx import cvar
from lex2spdx.spdx_license_data import get_licenses


_XML_NS = "http://www.spdx.org/license"


def _write_spdx_xml(path: Path, *, license_xml: str) -> None:
    path.write_text(
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        f"<licenseList xmlns=\"{_XML_NS}\">\n"
        f"{license_xml}\n"
        "</licenseList>\n",
        encoding="utf-8",
    )


def test_get_licenses_parses_xml_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    xml_dir = tmp_path / "spdx-licenses"
    xml_dir.mkdir()

    _write_spdx_xml(
        xml_dir / "Test-1.0.xml",
        license_xml=(
            "  <license licenseId=\"Test-1.0\" name=\"Test License\" isOsiApproved=\"true\" "
            "listVersionAdded=\"3.0\">\n"
            "    <crossRefs>\n"
            "      <crossRef>https://example.com/license</crossRef>\n"
            "    </crossRefs>\n"
            "    <text>\n"
            "      <titleText>Test License Title</titleText>\n"
            "      <copyrightText>Copyright 2026</copyrightText>\n"
            "      <p> Paragraph 1 </p>\n"
            "      <p>Paragraph\n2</p>\n"
            "    </text>\n"
            "  </license>"
        ),
    )

    # This file should be ignored by get_licenses (no <license> element)
    _write_spdx_xml(xml_dir / "NoLicense.xml", license_xml="  <notALicense />")

    monkeypatch.setattr(cvar, "spdx_license_list_dir", xml_dir)

    licenses = get_licenses()
    assert len(licenses) == 1

    lic = licenses[0]
    assert lic["licenseId"] == "Test-1.0"
    assert lic["name"] == "Test License"
    assert lic["isOsiApproved"] is True
    assert lic["listVersionAdded"] == "3.0"
    assert lic["deprecatedVersion"] is None

    assert lic["crossRefs"] == ["https://example.com/license"]

    assert lic["titleText"] == "Test License Title"
    assert lic["copyrightText"] == "Copyright 2026"
    assert lic["text"] == "Test License Title Copyright 2026 Paragraph 1 Paragraph 2"


def test_get_licenses_skips_generic_title_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    xml_dir = tmp_path / "spdx-licenses"
    xml_dir.mkdir()

    _write_spdx_xml(
        xml_dir / "GenericTitle.xml",
        license_xml=(
            "  <license licenseId=\"Generic\" name=\"Generic\">\n"
            "    <text>\n"
            "      <titleText>LICENSE</titleText>\n"
            "      <p>Some body</p>\n"
            "    </text>\n"
            "  </license>"
        ),
    )

    monkeypatch.setattr(cvar, "spdx_license_list_dir", xml_dir)

    licenses = get_licenses()
    assert len(licenses) == 1
    assert licenses[0]["titleText"] == ""


def test_get_licenses_normalize_normalizes_string_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    xml_dir = tmp_path / "spdx-licenses"
    xml_dir.mkdir()

    _write_spdx_xml(
        xml_dir / "MIT.xml",
        license_xml=(
            "  <license licenseId=\"MIT\" name=\"MIT License\" listVersionAdded=\"v1.0\">\n"
            "    <crossRefs>\n"
            "      <crossRef>https://opensource.org/licenses/MIT</crossRef>\n"
            "    </crossRefs>\n"
            "    <text>\n"
            "      <titleText>MIT License</titleText>\n"
            "      <p> Permission is hereby granted... </p>\n"
            "    </text>\n"
            "  </license>"
        ),
    )

    monkeypatch.setattr(cvar, "spdx_license_list_dir", xml_dir)

    licenses = get_licenses(normalize=True)
    assert len(licenses) == 1

    lic = licenses[0]
    assert lic["licenseId"] == "mit"
    assert lic["name"] == "mit license"
    assert lic["listVersionAdded"] == " 1 0"

    # Lists are not normalized by get_licenses(normalize=True)
    assert lic["crossRefs"] == ["https://opensource.org/licenses/MIT"]

    assert "permission is hereby granted" in lic["text"]

