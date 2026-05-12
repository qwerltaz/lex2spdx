import pandas as pd

from lex2spdx.map import MapPipeline, load_dataset
from lex2spdx.maps import IMap, MapResult


def test_load_dataset():
    df = load_dataset(100, False)

    assert 0 <= len(df) <= 100  # It drops rows with empty license fields.
    assert list(df.columns) == ['idx', 'pkg_idx', 'name', 'version', 'license', 'description', 'homepage', 'repository',
                                'author', 'maintainer', 'author_email', 'maintainer_email', 'requires_dist']

    load_dataset(0, False)
    load_dataset(0, True)


class FirstPassMap(IMap):
    def map(self, license_field: str):
        if license_field == "apache 2 0":
            return MapResult("apache 2 0", "spdx_id")
        return None


class SecondPassMap(IMap):
    def map(self, license_field: str):
        if license_field == "mit license":
            return MapResult("mit", "spdx_id")
        if license_field == "unknown":
            return ""
        return None


class NormalizedApacheMap(IMap):
    def map(self, license_field: str):
        if license_field == "apache 2 0":
            return MapResult("apache 2 0", "spdx_id")
        return None


def test_map_pipeline_keeps_none_results_for_later_maps_and_tracks_map_outputs():
    df = pd.DataFrame(
        [
            {"idx": 1, "license": "MIT License"},
            {"idx": 2, "license": "Unknown"},
            {"idx": 3, "license": "Apache-2.0"},
        ]
    )

    pipeline = MapPipeline([FirstPassMap(), SecondPassMap()])
    mapped, failed = pipeline.run(df)

    assert mapped == {1, 2, 3}
    assert failed == set()

    assert pipeline.last_mapped_by_map["FirstPassMap"] == [(3, "Apache-2.0", "apache 2 0", "spdx_id")]
    assert pipeline.last_unresolved_by_map["FirstPassMap"] == [(1, "MIT License"), (2, "Unknown")]

    assert pipeline.last_mapped_by_map["SecondPassMap"] == [(1, "MIT License", "mit", "spdx_id"), (2, "Unknown", "", "unknown")]
    assert pipeline.last_unresolved_by_map["SecondPassMap"] == []


def test_map_pipeline_normalizes_license_field_before_map_invocation():
    df = pd.DataFrame(
        [
            {"idx": 10, "license": "  Apache 2.0  "},
        ]
    )

    pipeline = MapPipeline([NormalizedApacheMap()])
    mapped, failed = pipeline.run(df)

    assert mapped == {10}
    assert failed == set()
    assert pipeline.last_mapped_by_map["NormalizedApacheMap"] == [(10, "  Apache 2.0  ", "apache 2 0", "spdx_id")]
    assert pipeline.last_unresolved_by_map["NormalizedApacheMap"] == []
