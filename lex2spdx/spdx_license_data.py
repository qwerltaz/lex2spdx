from typing import TypedDict
from xml.etree import ElementTree

from . import cvar
from . import preprocess

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


def get_licenses(normalize: bool = False) -> list[License]:
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

        current_license = License(
            isOsiApproved=license_element.get("isOsiApproved", "false").lower() == "true",
            licenseId=license_element.get("licenseId", ""),
            name=license_element.get("name", ""),
            listVersionAdded=license_element.get("listVersionAdded"),
            deprecatedVersion=license_element.get("deprecatedVersion"),
            crossRefs=cross_refs,
            text=_extract_text(text_element),
            titleText=_extract_text(title_element),
            copyrightText=_extract_text(copyright_element),
        )

        if normalize:
            for key, value in current_license.items():
                if isinstance(value, str):
                    current_license[key] = preprocess.normalize_license_field(value)
        license_list.append(current_license)

    return license_list


class LicenseData:
    """Grouped data of SPDX licenses."""
    licenses = get_licenses()
    license_ids = tuple(map(lambda x: x["licenseId"], licenses))
    license_names = tuple(map(lambda x: x["name"], licenses))
    license_title_texts = tuple(map(lambda x: x["titleText"], licenses))
    license_texts = tuple(map(lambda x: x["text"], licenses))


class LicenseDataNormalized:
    """Grouped data of SPDX licenses with all fields normalized."""
    licenses = get_licenses(normalize=True)
    license_ids = tuple(map(lambda x: x["licenseId"], licenses))
    license_names = tuple(map(lambda x: x["name"], licenses))
    license_title_texts = tuple(map(lambda x: x["titleText"], licenses))
    license_texts = tuple(map(lambda x: x["text"], licenses))
