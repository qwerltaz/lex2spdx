"""Individual maps to SPDX licenses. Each map will always return an SPDX ID or None."""

from abc import ABC, abstractmethod
from typing import Literal

import rapidfuzz

try:
    from .spdx_license_data import LicenseData
except ImportError:
    from spdx_license_data import LicenseData
import logger

log = logger.get()


class IMap(ABC):
    @abstractmethod
    def map(self, license_field: str) -> str | None | Literal[""]:
        """
        Map a license string to an SPDX license identifier.

        Return an empty string if the license is confirmed to be unknown, and
        it cannot be mapped.

        Return None if the mapping failed to find a fitting identifier,
        but there's a chance it's identifiable in general.

        :param license_field: The license string to map.
        :return: The detected SPDX license ID.
        """


class MapNA(IMap):
    """Discard fields like 'Unknown'. Nothing we can do here."""

    def __init__(self):
        super().__init__()
        self.bad_values = ("unknown", "license.txt")

    def map(self, license_field: str):
        if license_field.lower() in self.bad_values:
            return ""
        else:
            return None


class MapExactID(IMap):
    """Map to SPDX ID only if the license exactly matches an SPDX identifier."""

    def map(self, license_field: str):
        for license_spdx in LicenseData.licenses:
            if license_field == license_spdx["licenseId"]:
                return license_spdx["licenseId"]

        return None


class MapExactMatch(IMap):
    """
    Map to SPDX ID only if the license exactly matches a license name, full text,
    or title text, according to the SPDX specification.
    """

    def map(self, license_field: str):
        for license_spdx in LicenseData.licenses:
            text = license_spdx["text"]
            name = license_spdx["name"]
            title_text = license_spdx["titleText"]
            candidates = [text, name, title_text]

            for candidate in candidates:
                if candidate and license_field == candidate:
                    return license_spdx["licenseId"]

        return None


class MapSubstring(IMap):
    """
    Map to SPDX ID only if the license contains exactly a license name, text,
    or title text, according to the SPDX specification.
    """

    def map(self, license_field: str):
        for license_spdx in LicenseData.licenses:
            text = license_spdx["text"]
            name = license_spdx["name"]
            title_text = license_spdx["titleText"]

            candidates = [text, name, title_text]
            for candidate in candidates:
                if candidate and candidate in license_field:
                    return license_spdx["licenseId"]

        return None


class MapFuzzyMatch(IMap):
    def __init__(self, threshold: int = 80):
        super().__init__()
        self.threshold = threshold

    def map(self, license_field: str):
        scores_id = rapidfuzz.process.extract(license_field, LicenseData.license_ids,
                                              processor=rapidfuzz.utils.default_process)
        scores_name = rapidfuzz.process.extract(license_field, LicenseData.license_names,
                                                processor=rapidfuzz.utils.default_process)
        scores_title_text = rapidfuzz.process.extract(license_field, LicenseData.license_title_texts,
                                                      processor=rapidfuzz.utils.default_process)
        scores_text = rapidfuzz.process.extract(license_field, LicenseData.license_texts,
                                                processor=rapidfuzz.utils.default_process)

        scores = scores_id + scores_name + scores_title_text + scores_text

        best_match_id = scores[0][0]
        log.debug("Best match '%s' for input %s\nfuzzy matching scores: %r", best_match_id, license_field, scores)

        return best_match_id
