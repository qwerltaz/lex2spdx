"""Individual maps to SPDX licenses."""

from abc import ABC, abstractmethod

import load_spdx_licenses

LICENSES = load_spdx_licenses.get_licenses()


class IMap(ABC):
    @abstractmethod
    def map(self, license_field: str) -> str | None:
        """
        Map a license string to an SPDX license identifier.

        :param license_field: The license string to map.
        :return: The mapped SPDX license or None if no match is found.
        """


class MapExactMatch(IMap):
    """
    Map to SPDX ID only if the license exactly matches a license text,
    title text, or copyright text.
    """

    def map(self, license_field: str) -> str | None:
        for license_spdx in LICENSES:
            if any((
                    license_field == license_spdx["text"],
                    license_field == license_spdx["titleText"],
                    license_field == license_spdx["copyrightText"],
            )):
                return license_spdx["licenseId"]

        return None


class MapSubstring(IMap):
    """
    Map to SPDX ID only if the license contains exactly a license text,
    title text, or copyright text.
    """

    def map(self, license_field: str) -> str | None:
        for license_spdx in LICENSES:
            text = license_spdx["text"]
            title_text = license_spdx["titleText"]
            copyright_text = license_spdx["copyrightText"]

            if any((
                    bool(text) and text in license_field,
                    bool(title_text) and title_text in license_field,
                    bool(copyright_text) and copyright_text in license_field,
            )):
                return license_spdx["licenseId"]

        return None
