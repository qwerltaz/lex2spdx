"""Individual maps from free-text license fields to SPDX licenses."""
import json
from abc import ABC, abstractmethod
from typing import Literal

import rapidfuzz

try:
    from .spdx_license_data import LicenseData
    from . import logger
    from . import cvar
except ImportError:
    from spdx_license_data import LicenseData
    import logger
    import cvar

log = logger.get()


class IMap(ABC):
    @abstractmethod
    def map(self, license_field: str) -> str | None | Literal[""]:
        """
        Map a free-text license string to an SPDX license identifier.

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
        with open(cvar.resources_dir / "unknown_license_fields.json", "r", encoding="utf-8") as f:
            self.bad_values: list = json.load(f)

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
    """
    Use fuzzy text matching to find approximately most fitting SPDX ID.
    Finds best match for the given license field from all SPDX license
    IDs, names, title texts, and full texts, then picks the one with the highest
    similarity, if it's above our certainty threshold, otherwise None.
    """

    def __init__(self):
        super().__init__()
        self.fuzzy_match_threshold = 90

    def map(self, license_field: str):
        score_id = rapidfuzz.process.extractOne(license_field, LicenseData.license_ids,
                                                processor=rapidfuzz.utils.default_process)
        score_name = rapidfuzz.process.extractOne(license_field, LicenseData.license_names,
                                                  processor=rapidfuzz.utils.default_process)
        score_title_text = rapidfuzz.process.extractOne(license_field, LicenseData.license_title_texts,
                                                        processor=rapidfuzz.utils.default_process)
        score_text = rapidfuzz.process.extractOne(license_field, LicenseData.license_texts,
                                                  processor=rapidfuzz.utils.default_process)

        scores = sorted([score_id, score_name, score_title_text, score_text], key=lambda x: x[1], reverse=True)
        best_match = scores[0]
        best_match_text, best_match_score, best_match_index = best_match
        best_match_spdx_id = LicenseData.license_ids[best_match_index]
        log.debug("Best match '%s' (SPDX ID '%s') for input %s\nfuzzy matching scores: %r", best_match_text,
                  best_match_spdx_id, license_field, scores)

        return best_match_spdx_id if best_match_score > self.fuzzy_match_threshold else None
