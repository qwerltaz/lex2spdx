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
    mapped, map_fails, never_mapped = pipeline.run(df)

    assert len(mapped) == 3
    assert never_mapped == set()

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
    mapped, map_fails, neverm_mapped = pipeline.run(df)

    assert mapped == [{'idx': 10, 'license': 'apache 2 0', 'map_name': 'NormalizedApacheMap', 'mapping_type': 'spdx_id'}]
    assert neverm_mapped == set()
    assert pipeline.last_mapped_by_map["NormalizedApacheMap"] == [(10, "  Apache 2.0  ", "apache 2 0", "spdx_id")]
    assert pipeline.last_unresolved_by_map["NormalizedApacheMap"] == []
