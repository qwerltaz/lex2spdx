import json
from typing import TypedDict
from xml.etree import ElementTree

import cvar

XML_NAMESPACE = "http://www.spdx.org/license"
OUTPUT_PATH = cvar.spdx_license_list_dir.parent / "spdx-licenses.json"


class License(TypedDict):
    isOsiApproved: bool
    licenseId: str
    name: str
    listVersionAdded: str | None
    deprecatedVersion: str | None
    crossRefs: list[str]
    text: str
    titleText: str
    copyrightText: str


def _extract_text(element: ElementTree.Element | None) -> str:
    """Extract XML text element with paragraphs into a space-separated string."""
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _save_spdx_licenses() -> None:
    license_list = []
    for xml_file in cvar.spdx_license_list_dir.glob("*.xml"):
        root = ElementTree.parse(xml_file).getroot()

        license_element = root.find(f"{{{XML_NAMESPACE}}}license")
        if license_element is None:
            continue

        cross_refs = [
            element.text
            for element in license_element.findall(f"{{{XML_NAMESPACE}}}crossRefs/{{{XML_NAMESPACE}}}crossRef")
            if element.text
        ]

        text_element = license_element.find(f"{{{XML_NAMESPACE}}}text")
        title_element = license_element.find(f"{{{XML_NAMESPACE}}}text/{{{XML_NAMESPACE}}}titleText")
        copyright_element = license_element.find(f"{{{XML_NAMESPACE}}}text/{{{XML_NAMESPACE}}}copyrightText")

        license_list.append(License(
            isOsiApproved=license_element.get("isOsiApproved", "false").lower() == "true",
            licenseId=license_element.get("licenseId", ""),
            name=license_element.get("name", ""),
            listVersionAdded=license_element.get("listVersionAdded"),
            deprecatedVersion=license_element.get("deprecatedVersion"),
            crossRefs=cross_refs,
            text=_extract_text(text_element),
            titleText=_extract_text(title_element),
            copyrightText=_extract_text(copyright_element),
        ))

    OUTPUT_PATH.write_text(json.dumps(license_list, indent=4), encoding="utf-8")
    print(f"Saved {len(license_list)} licenses to {OUTPUT_PATH}")


def load_spdx_licenses() -> list[License]:
    """Load and return a list of SPDX license as dictionaries with their information."""
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        licenses = json.load(f)

    return licenses


if __name__ == "__main__":
    _save_spdx_licenses()
