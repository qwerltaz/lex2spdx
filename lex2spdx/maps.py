"""Individual maps from free-text license fields to SPDX licenses."""
import json
from abc import ABC, abstractmethod
from typing import Literal

import rapidfuzz

from . import cvar
from . import logger
from .spdx_license_data import LicenseData, LicenseDataNormalized

_log = logger.get()


def shorten_field(text_field: str | None) -> str | None:
    """Shorten a text field for text representation if it's too long."""
    if text_field is None:
        return None

    return text_field[:50] + "..." if len(text_field) > 50 else text_field


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
        for license_spdx in LicenseDataNormalized.licenses:
            if license_field == license_spdx["licenseId"]:
                return license_spdx["licenseId"]

        return None


class MapExactMatch(IMap):
    """
    Map to SPDX ID only if the license exactly matches a license name, or full text,
    according to the SPDX specification.
    """

    def map(self, license_field: str):
        for license_spdx in LicenseDataNormalized.licenses:
            text = license_spdx["text"]
            name = license_spdx["name"]
            id = license_spdx["licenseId"]
            candidates = [text, name, id]

            for candidate in candidates:
                if candidate and license_field == candidate:
                    return license_spdx["licenseId"]

        return None


class MapSubstring(IMap):
    """
    Map to SPDX ID only if the license contains exactly a license name or text,
     according to the SPDX specification.
    """

    def map(self, license_field: str):
        for license_spdx in LicenseDataNormalized.licenses:
            text = license_spdx["text"]
            name = license_spdx["name"]

            candidates = [text, name]
            for candidate in candidates:
                if candidate and candidate in license_field:
                    return license_spdx["licenseId"]

        return None


class MapFuzzyMatch(IMap):
    """
    Use fuzzy text matching to find approximately most fitting SPDX ID.
    Finds best match for the given license field from all SPDX license
    IDs, names, and full texts, then picks the one with the highest
    similarity, if it's above our certainty threshold, otherwise None.

    Prioritizes matching SPDX license ID and name, then text.
    """

    def __init__(self):
        super().__init__()
        self.fuzzy_match_threshold = 90

    def map(self, license_field: str):
        score_id = rapidfuzz.process.extractOne(
            license_field,
            LicenseDataNormalized.license_ids,
        )
        score_name = rapidfuzz.process.extractOne(
            license_field,
            LicenseDataNormalized.license_names,
        )

        priority_scores = sorted([score_id, score_name], key=lambda x: x[1], reverse=True)
        best_priority_text, best_priority_score, best_priority_index = priority_scores[0]
        best_priority_spdx_id = LicenseDataNormalized.license_ids[best_priority_index]

        if best_priority_score >= self.fuzzy_match_threshold:
            _log.debug(
                "Best priority fuzzy match '%s' (SPDX ID '%s') for input %s\npriority fuzzy scores: %r",
                shorten_field(best_priority_text),
                best_priority_spdx_id,
                shorten_field(license_field),
                priority_scores,
            )
            return best_priority_spdx_id

        score_text = rapidfuzz.process.extractOne(
            license_field,
            LicenseDataNormalized.license_texts,
        )
        best_text_match, best_text_score, best_text_index = score_text
        best_text_spdx_id = LicenseData.license_ids[best_text_index]

        _log.debug(
            "Priority fuzzy below threshold for input %s\npriority scores: %r\n"
            "text fallback best match '%s' (SPDX ID '%s') with score %.2f",
            shorten_field(license_field),
            priority_scores,
            shorten_field(best_text_match),
            best_text_spdx_id,
            best_text_score,
        )

        return best_text_spdx_id if best_text_score > self.fuzzy_match_threshold else None
