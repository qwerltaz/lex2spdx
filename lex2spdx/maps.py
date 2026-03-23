"""Individual maps to SPDX licenses. Each map will always return an SPDX ID or None."""

from abc import ABC, abstractmethod

try:
    from . import load_spdx_licenses
except ImportError:
    import load_spdx_licenses

LICENSES = load_spdx_licenses.get_licenses()


class IMap(ABC):
    def __init__(self):
        self.licenses = LICENSES

    @abstractmethod
    def map(self, license_field: str) -> str | None:
        """
        Map a license string to an SPDX license identifier.

        :param license_field: The license string to map.
        :return: The mapped SPDX license or None if no match is found.
        """


class MapExactID(IMap):
    """Map to SPDX ID only if the license exactly matches an SPDX identifier."""

    def map(self, license_field: str) -> str | None:
        for license_spdx in LICENSES:
            if license_field == license_spdx["licenseId"]:
                return license_spdx["licenseId"]

        return None


class MapExactMatch(IMap):
    """
    Map to SPDX ID only if the license exactly matches a license name, full text,
    title text, or copyright text, according to the SPDX specification.
    """

    def map(self, license_field: str) -> str | None:
        for license_spdx in self.licenses:
            if any((
                    license_field == license_spdx["text"],
                    license_field == license_spdx["name"],
                    license_field == license_spdx["titleText"],
                    license_field == license_spdx["copyrightText"],
            )):
                return license_spdx["licenseId"]

        return None


class MapSubstring(IMap):
    """
    Map to SPDX ID only if the license contains exactly a license name, text,
    title text, or copyright text, according to the SPDX specification.
    """

    def map(self, license_field: str) -> str | None:
        for license_spdx in self.licenses:
            text = license_spdx["text"]
            name = license_spdx["name"]
            title_text = license_spdx["titleText"]
            copyright_text = license_spdx["copyrightText"]

            if any((
                    bool(text) and text in license_field,
                    bool(name) and name in license_field,
                    bool(title_text) and title_text in license_field,
                    bool(copyright_text) and copyright_text in license_field,
            )):
                return license_spdx["licenseId"]

        return None
