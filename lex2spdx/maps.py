"""Individual maps from free-text license fields to SPDX licenses."""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

import rapidfuzz

from . import cvar, preprocess
from . import logger
from .spdx_license_data import LicenseDataNormalized

_log = logger.get()


@dataclass
class MapResult:
    """Result of a license mapping operation with one of several possible result types."""
    identifier: str
    mapping_type: Literal["spdx_id", "license_family"]


LICENSE_FAMILIES = {
    "BSD": ["0BSD", "BSD-1-Clause", "BSD-2-Clause", "BSD-2-Clause-Darwin", "BSD-2-Clause-FreeBSD",
            "BSD-2-Clause-NetBSD", "BSD-2-Clause-Patent", "BSD-2-Clause-Views", "BSD-3-Clause",
            "BSD-3-Clause-Attribution", "BSD-3-Clause-Clear", "BSD-3-Clause-LBNL", "BSD-3-Clause-Modification-Variant",
            "BSD-3-Clause-No-Nuclear-License", "BSD-3-Clause-No-Nuclear-License-2014",
            "BSD-3-Clause-No-Nuclear-Warranty",
            "BSD-Source-Code", "FreeBSD-DOC"],
    "GPL": ["GPL-1.0-only", "GPL-1.0-or-later", "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later"],
    "LGPL": ["LGPL-2.0-only", "LGPL-2.0-or-later", "LGPL-2.1-only", "LGPL-2.1-or-later", "LGPL-3.0-only",
             "LGPL-3.0-or-later"],
    "AGPL": ["AGPL-1.0-only", "AGPL-1.0-or-later", "AGPL-3.0-only", "AGPL-3.0-or-later"],
    "Apache": ["Apache-1.0", "Apache-1.1", "Apache-2.0"],
    "MPL": ["MPL-1.0", "MPL-1.1", "MPL-2.0", "MPL-2.0-no-copyleft-exception"],
    "ISC": ["ISC"],
    "Artistic": ["Artistic-1.0", "Artistic-1.0-cl8", "Artistic-1.0-Perl", "Artistic-2.0"],
}

SPDX_ID_TO_FAMILY = {}
for family, spdx_ids in LICENSE_FAMILIES.items():
    for spdx_id in spdx_ids:
        SPDX_ID_TO_FAMILY[spdx_id] = family


def shorten_field(text_field: str | None) -> str | None:
    """Shorten a text field for text representation if it's too long."""
    if text_field is None:
        return None

    return text_field[:50] + "..." if len(text_field) > 50 else text_field


class IMap(ABC):
    @abstractmethod
    def map(self, license_field: str) -> MapResult | None | Literal[""]:
        """
        Map a free-text license string to an SPDX license identifier or license family.

        Return an empty string if the license is confirmed to be unknown, and
        it cannot be mapped.

        Return None if the mapping failed to find a fitting identifier,
        but there's a chance it's identifiable in general.

        :param license_field: The license string to map.
        :return: MapResult with identifier and mapping_type, empty string, or None.
        """


class MapNA(IMap):
    """Discard fields like 'Unknown'. Nothing we can do here."""

    def __init__(self):
        super().__init__()
        with open(cvar.resources_dir / "unknown-license-fields.json", "r", encoding="utf-8") as f:
            self.bad_values: set[str] = set(json.load(f))
        self.bad_values = set(map(preprocess.normalize_license_field, self.bad_values))
        _log.debug("MapNA final bad values: %s", self.bad_values)

    def map(self, license_field: str):
        if license_field in self.bad_values:
            return ""
        else:
            return None


class MapExactID(IMap):
    """Map to SPDX ID only if the license exactly matches an SPDX identifier."""

    def map(self, license_field: str):
        for license_spdx in LicenseDataNormalized.licenses:
            if license_field == license_spdx["licenseId"]:
                return MapResult(license_spdx["licenseId"], "spdx_id")

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
                    return MapResult(license_spdx["licenseId"], "spdx_id")

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
                    return MapResult(license_spdx["licenseId"], "spdx_id")

        return None


class MapLicenseFamily(IMap):
    """
    Map to a license family (e.g., 'BSD', 'GPL', 'Apache') based on exact match
    of the normalized license field to common family identifiers.
    """

    def __init__(self):
        super().__init__()
        self.family_names_normalized = {preprocess.normalize_license_field(family): family
                                        for family in LICENSE_FAMILIES.keys()}

    def map(self, license_field: str):
        if license_field in self.family_names_normalized:
            return MapResult(self.family_names_normalized[license_field], "license_family")

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
        self.fuzzy_match_threshold = 85
        # Partial_ratio is very permissive for short strings.
        # Example: "doc" will score 100 against any long text containing
        # "documentation" and can cause false positives.
        #
        # For SPDX ids/names we prefer token-based similarity to require whole-token matches.
        # This still matches, e.g., "mit license ..." -> "mit", but avoids "doc" -> "documentation".
        self.scorer_id_name = rapidfuzz.fuzz.token_set_ratio
        # For full texts/title texts, token-based similarity is also safer than substring matching.
        self.scorer_text = rapidfuzz.fuzz.token_set_ratio

    @staticmethod
    def fuzzy_extract_one(license_field: str, choices: tuple[str, ...], *, scorer):
        ret = rapidfuzz.process.extractOne(
            license_field,
            choices,
            scorer=scorer,
        )

        return ret

    @staticmethod
    def fuzzy_extract(license_field: str, choices: tuple[str, ...], *, scorer):
        ret = rapidfuzz.process.extract(
            license_field,
            choices,
            scorer=scorer,
        )

        return ret

    def map(self, license_field: str):
        licenses = LicenseDataNormalized.licenses
        license_ids = tuple(license_info["licenseId"] for license_info in licenses)
        license_names = tuple(license_info["name"] for license_info in licenses)

        score_id = self.fuzzy_extract_one(
            license_field, license_ids, scorer=self.scorer_id_name
        )
        score_name = self.fuzzy_extract_one(
            license_field, license_names, scorer=self.scorer_id_name
        )

        priority_scores = sorted([score_id, score_name], key=lambda x: x[1], reverse=True)
        best_priority_text, best_priority_score, best_priority_index = priority_scores[0]
        best_priority_spdx_id = licenses[best_priority_index]["licenseId"]

        if best_priority_score >= self.fuzzy_match_threshold:
            _log.debug(
                "Best priority fuzzy match '%s' (SPDX ID '%s') for input %s\npriority fuzzy scores: %r",
                shorten_field(best_priority_text),
                best_priority_spdx_id,
                shorten_field(license_field),
                priority_scores,
            )
            return MapResult(best_priority_spdx_id, "spdx_id")

        license_texts = tuple(license_info["text"] for license_info in licenses)
        license_title_texts = tuple(license_info["titleText"] for license_info in licenses)
        score_text = self.fuzzy_extract_one(
            license_field, license_texts, scorer=self.scorer_text
        )
        score_title_text = self.fuzzy_extract_one(
            license_field, license_title_texts, scorer=self.scorer_text
        )

        priority_scores2 = sorted([score_text, score_title_text], key=lambda x: x[1], reverse=True)
        best_text_match, best_text_score, best_text_index = priority_scores2[0]
        best_text_spdx_id = licenses[best_text_index]["licenseId"]

        _log.debug(
            "Priority fuzzy below threshold for input %s\npriority scores: %r\n"
            "text fallback best match '%s' (SPDX ID '%s') with score %.2f",
            shorten_field(license_field),
            priority_scores,
            shorten_field(best_text_match),
            best_text_spdx_id,
            best_text_score,
        )

        if best_text_score > self.fuzzy_match_threshold:
            return MapResult(best_text_spdx_id, "spdx_id")
        return None

    def debug_map(self, license_field: str):
        licenses = LicenseDataNormalized.licenses
        license_ids = tuple(license_info["licenseId"] for license_info in licenses)
        license_names = tuple(license_info["name"] for license_info in licenses)
        license_title_texts = tuple(license_info["titleText"] for license_info in licenses)
        license_texts = tuple(license_info["text"] for license_info in licenses)
        for inputs in (license_ids, license_names, license_title_texts, license_texts):
            scorer = self.scorer_text
            if inputs in (license_ids, license_names):
                scorer = self.scorer_id_name

            scores = self.fuzzy_extract(license_field, inputs, scorer=scorer)
            _log.debug(
                "Fuzzy match scores for input '%s'\nagainst %s:\n%r",
                shorten_field(license_field),
                list(map(shorten_field, inputs)),
                list(map(lambda x: (shorten_field(x[0]), x[1], x[2]), scores)),
            )


def _():
    test_field = "gnu general public 3 gpl 3"
    test_field = preprocess.normalize_license_field(test_field)
    MapFuzzyMatch().debug_map(test_field)
    # print(MapFuzzyMatch().map(test_field))


if __name__ == '__main__':
    _()
