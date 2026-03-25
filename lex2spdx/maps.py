"""Individual maps to SPDX licenses. Each map will always return an SPDX ID or None."""

from abc import ABC, abstractmethod

try:
    from .spdx_license_data import LicenseData
except ImportError:
    from spdx_license_data import LicenseData


class IMap(ABC):
    def __init__(self):
        self.licenses = LicenseData.licenses

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
        for license_spdx in LicenseData.licenses:
            if license_field == license_spdx["licenseId"]:
                return license_spdx["licenseId"]

        return None


class MapExactMatch(IMap):
    """
    Map to SPDX ID only if the license exactly matches a license name, full text,
    or title text, according to the SPDX specification.
    """

    def map(self, license_field: str) -> str | None:
        for license_spdx in self.licenses:
            if any((
                    license_field == license_spdx["text"],
                    license_field == license_spdx["name"],
                    license_field == license_spdx["titleText"],
            )):
                return license_spdx["licenseId"]

        return None


class MapSubstring(IMap):
    """
    Map to SPDX ID only if the license contains exactly a license name, text,
    or title text, according to the SPDX specification.
    """

    def map(self, license_field: str) -> str | None:
        for license_spdx in self.licenses:
            text = license_spdx["text"]
            name = license_spdx["name"]
            title_text = license_spdx["titleText"]

            if any((
                    bool(text) and text in license_field,
                    bool(name) and name in license_field,
                    bool(title_text) and title_text in license_field,
            )):
                return license_spdx["licenseId"]

        return None


print()
