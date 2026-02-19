from dataclasses import dataclass
from xml.etree import ElementTree

import cvar

NAMESPACE = "http://www.spdx.org/license"


@dataclass(frozen=True)
class License:
    isOsiApproved: bool
    licenseId: str
    name: str
    listVersionAdded: str | None
    deprecatedVersion: str | None
    crossRefs: tuple[str, ...]


def load_spdx_licenses() -> list["License"]:
    license_list = []
    for xml_file in cvar.spdx_license_list_dir.glob("*.xml"):
        root = ElementTree.parse(xml_file).getroot()

        license_element = root.find(f"{{{NAMESPACE}}}license")
        if license_element is None:
            continue

        cross_refs = tuple(
            element.text
            for element in license_element.findall(f"{{{NAMESPACE}}}crossRefs/{{{NAMESPACE}}}crossRef")
            if element.text
        )

        license_list.append(License(
            isOsiApproved=license_element.get("isOsiApproved", "false").lower() == "true",
            licenseId=license_element.get("licenseId", ""),
            name=license_element.get("name", ""),
            listVersionAdded=license_element.get("listVersionAdded"),
            deprecatedVersion=license_element.get("deprecatedVersion"),
            crossRefs=cross_refs,
        ))

    return license_list


if __name__ == "__main__":
    licenses = load_spdx_licenses()
    print(f"Loaded {len(licenses)} licenses")
