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
    def map(self, license_field: str) -> str | None:
        for license_spdx in LICENSES:
            if any((
                    license_field == license_spdx["text"],
                    license_field == license_spdx["titleText"],
                    license_field == license_spdx["copyrightText"],
            )):
                return license_spdx["licenseId"]

        return None
