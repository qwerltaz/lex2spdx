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


with open(cvar.resources_dir / "license-families.json", "r", encoding="utf-8") as f:
    LICENSE_FAMILIES = json.load(f)

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
            candidates = [text, name]

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
        # For full texts/title texts, prefer a stricter scorer to penalize extra tokens.
        self.scorer_text = rapidfuzz.fuzz.token_sort_ratio

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

        id_name_scores = sorted([score_id, score_name], key=lambda x: x[1], reverse=True)
        best_id_name_text, best_id_name_score, best_id_name_index = id_name_scores[0]
        best_id_name_spdx_id = licenses[best_id_name_index]["licenseId"]

        if best_id_name_score >= self.fuzzy_match_threshold:
            _log.debug(
                "Best id/name fuzzy match '%s' (SPDX ID '%s') for input %s\nid/name fuzzy scores: %r",
                shorten_field(best_id_name_text),
                best_id_name_spdx_id,
                shorten_field(license_field),
                id_name_scores,
            )
            return MapResult(best_id_name_spdx_id, "spdx_id")

        license_texts = tuple(license_info["text"] for license_info in licenses)
        score_text = self.fuzzy_extract_one(
            license_field, license_texts, scorer=self.scorer_text
        )

        # Sorting in case of adding more fields. For now only one element.
        text_scores2 = sorted([score_text], key=lambda x: x[1], reverse=True)
        best_text_match, best_text_score, best_text_index = text_scores2[0]
        best_text_spdx_id = licenses[best_text_index]["licenseId"]

        _log.debug(
            "Priority fuzzy below threshold for input %s\npriority scores: %r\n"
            "text fallback best match '%s' (SPDX ID '%s') with score %.2f",
            shorten_field(license_field),
            id_name_scores,
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
        for name, inputs in (("license_ids", license_ids), ("license_names", license_names),
                             ("license_title_texts", license_title_texts), ("license_texts", license_texts)):
            scorer = self.scorer_text
            if inputs in (license_ids, license_names):
                scorer = self.scorer_id_name

            scores = self.fuzzy_extract(license_field, inputs, scorer=scorer)
            _log.info(
                "Fuzzy match scores for input '%s'\nagainst %s:\n%r",
                shorten_field(license_field),
                name,
                list(map(lambda x: (shorten_field(x[0]), x[1], x[2]), scores)),
            )


def _():
    logger.set_stdout_log_level("DEBUG")
    test_field = "BSD-3"#"Copyright 2024 Université Paris-Saclay  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    test_field = preprocess.normalize_license_field(test_field)
    MapFuzzyMatch().debug_map(test_field)
    # print(MapFuzzyMatch().map(test_field))

def _token_set_ratio_test():
    input_license = "Copyright 2024 Université Paris-Saclay  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    mit_text = "MIT License Copyright (c) <year> <copyright holders> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice (including the next paragraph) shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    fsl_1_1_mit = "# Functional Source License, Version 1.1, MIT Future License ## Abbreviation FSL-1.1-MIT ## Notice Copyright ${year} ${licensor name} ## Terms and Conditions ### Licensor (\"We\") The party offering the Software under these Terms and Conditions. ### The Software The \"Software\" is each version of the software that we make available under these Terms and Conditions, as indicated by our inclusion of these Terms and Conditions with the Software. ### License Grant Subject to your compliance with this License Grant and the Patents, Redistribution and Trademark clauses below, we hereby grant you the right to use, copy, modify, create derivative works, publicly perform, publicly display and redistribute the Software for any Permitted Purpose identified below. ### Permitted Purpose A Permitted Purpose is any purpose other than a Competing Use. A Competing Use means making the Software available to others in a commercial product or service that: 1. substitutes for the Software; 2. substitutes for any other product or service we offer using the Software that exists as of the date we make the Software available; or 3. offers the same or substantially similar functionality as the Software. Permitted Purposes specifically include using the Software: 1. for your internal use and access; 2. for non-commercial education; 3. for non-commercial research; and 4. in connection with professional services that you provide to a licensee using the Software in accordance with these Terms and Conditions. ### Patents To the extent your use for a Permitted Purpose would necessarily infringe our patents, the license grant above includes a license under our patents. If you make a claim against any party that the Software infringes or contributes to the infringement of any patent, then your patent license to the Software ends immediately. ### Redistribution The Terms and Conditions apply to all copies, modifications and derivatives of the Software. If you redistribute any copies, modifications or derivatives of the Software, you must include a copy of or a link to these Terms and Conditions and not remove any copyright notices provided in or with the Software. ### Disclaimer THE SOFTWARE IS PROVIDED \"AS IS\" AND WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING WITHOUT LIMITATION WARRANTIES OF FITNESS FOR A PARTICULAR PURPOSE, MERCHANTABILITY, TITLE OR NON-INFRINGEMENT. IN NO EVENT WILL WE HAVE ANY LIABILITY TO YOU ARISING OUT OF OR RELATED TO THE SOFTWARE, INCLUDING INDIRECT, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES, EVEN IF WE HAVE BEEN INFORMED OF THEIR POSSIBILITY IN ADVANCE. ### Trademarks Except for displaying the License Details and identifying us as the origin of the Software, you have no right under these Terms and Conditions to use our trademarks, trade names, service marks or product names. ## Grant of Future License We hereby irrevocably grant you an additional license to use the Software under the MIT license that is effective on the second anniversary of the date we make the Software available. On or after that date, you may use the Software under the MIT license, in which case the following will apply: Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    json_license = "JSON License Copyright (c) 2002 JSON.org Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. The Software shall be used for Good, not Evil. THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."
    input_license = preprocess.normalize_license_field(input_license)
    mit_text = preprocess.normalize_license_field(mit_text)
    fsl_1_1_mit = preprocess.normalize_license_field(fsl_1_1_mit)
    json_license = preprocess.normalize_license_field(json_license)
    print(f"{rapidfuzz.fuzz.token_sort_ratio(input_license, mit_text)= }")
    print(f"{rapidfuzz.fuzz.token_sort_ratio(input_license, fsl_1_1_mit)= }")
    print(f"{rapidfuzz.fuzz.token_sort_ratio(input_license, json_license)= }")



if __name__ == '__main__':
    _()
    # _token_set_ratio_test()
