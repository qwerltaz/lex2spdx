from typing import TypedDict
from xml.etree import ElementTree

try:
    from . import cvar
except ImportError:
    import cvar

_XML_NAMESPACE = "http://www.spdx.org/license"


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


def get_licenses() -> list[License]:
    """Parse SPDX license XML files and return a list of License dictionaries with their information."""
    license_list = []
    for xml_file in cvar.spdx_license_list_dir.glob("*.xml"):
        root = ElementTree.parse(xml_file).getroot()

        license_element = root.find(f"{{{_XML_NAMESPACE}}}license")
        if license_element is None:
            continue

        cross_refs = [
            element.text
            for element in license_element.findall(f"{{{_XML_NAMESPACE}}}crossRefs/{{{_XML_NAMESPACE}}}crossRef")
            if element.text
        ]

        text_element = license_element.find(f"{{{_XML_NAMESPACE}}}text")
        title_element = license_element.find(f"{{{_XML_NAMESPACE}}}text/{{{_XML_NAMESPACE}}}titleText")
        copyright_element = license_element.find(f"{{{_XML_NAMESPACE}}}text/{{{_XML_NAMESPACE}}}copyrightText")

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

    return license_list


class LicenseData:
    licenses = get_licenses()
    license_ids = set(map(lambda x: x["licenseId"], licenses))
    license_names = set(map(lambda x: x["name"], licenses))
    license_title_texts = set(map(lambda x: x["titleText"], licenses))
    license_texts = set(map(lambda x: x["text"], licenses))
