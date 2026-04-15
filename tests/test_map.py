import pandas as pd

from lex2spdx.maps import IMap
from lex2spdx.map import MapPipeline, load_dataset


def test_load_dataset():
    df = load_dataset(100, False)

    assert 0 <= len(df) <= 100  # It drops rows with empty license fields.
    assert list(df.columns) == ['idx', 'pkg_idx', 'name', 'version', 'license', 'description', 'homepage', 'repository',
                                'author', 'maintainer', 'author_email', 'maintainer_email', 'requires_dist']

    load_dataset(0, False)
    load_dataset(0, True)


class FirstPassMap(IMap):
    def map(self, license_field: str):
        if license_field == "Apache-2.0":
            return "Apache-2.0"
        return None


class SecondPassMap(IMap):
    def map(self, license_field: str):
        if license_field == "MIT License":
            return "MIT"
        if license_field == "Unknown":
            return ""
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

    assert pipeline.last_mapped_by_map["FirstPassMap"] == [(3, "Apache-2.0", "Apache-2.0")]
    assert pipeline.last_unresolved_by_map["FirstPassMap"] == [(1, "MIT License"), (2, "Unknown")]

    assert pipeline.last_mapped_by_map["SecondPassMap"] == [(1, "MIT License", "MIT"), (2, "Unknown", "")]
    assert pipeline.last_unresolved_by_map["SecondPassMap"] == []
