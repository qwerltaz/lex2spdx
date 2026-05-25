from pathlib import Path

import pandas as pd
import pytest

from lex2spdx import maps
from lex2spdx.tools import tune_fuzzy_threshold as tft


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_load_dataset_filters_empty_ground_truth(tmp_path: Path) -> None:
    data_path = tmp_path / "validation.csv"
    _write_csv(
        data_path,
        [
            {"idx": 1, "license": "MIT", "ground_truth": "MIT"},
            {"idx": 2, "license": "Apache", "ground_truth": ""},
            {"idx": 3, "license": None, "ground_truth": None},
        ],
    )

    df = tft._load_dataset(data_path)

    assert list(df.columns) == list(tft.REQUIRED_COLUMNS)
    assert len(df) == 1
    assert df.loc[0, "license"] == "MIT"
    assert df.loc[0, "ground_truth"] == "MIT"


def test_filter_pipeline_candidates_removes_pre_mapped_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeMapNA:
        def map(self, license_field: str):
            return "" if license_field == "unknown" else None

    class FakeMapExactID:
        def map(self, license_field: str):
            if license_field == "mit":
                return maps.MapResult("MIT", "spdx_id")
            return None

    class FakeMapExactMatch:
        def map(self, license_field: str):
            if license_field == "apache":
                return maps.MapResult("Apache-2.0", "spdx_id")
            return None

    class FakeMapLicenseFamily:
        def map(self, license_field: str):
            if license_field == "bsd":
                return maps.MapResult("BSD", "license_family")
            return None

    monkeypatch.setattr(tft.maps, "MapNA", FakeMapNA)
    monkeypatch.setattr(tft.maps, "MapExactID", FakeMapExactID)
    monkeypatch.setattr(tft.maps, "MapExactMatch", FakeMapExactMatch)
    monkeypatch.setattr(tft.maps, "MapLicenseFamily", FakeMapLicenseFamily)

    df = pd.DataFrame(
        {
            "license_normalized": ["unknown", "mit", "apache", "bsd", "custom"],
        }
    )

    filtered = tft._filter_pipeline_candidates(df)

    assert filtered["license_normalized"].tolist() == ["custom"]


def test_compute_metrics_and_select_best(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeMapFuzzyMatch:
        def __init__(self) -> None:
            self.fuzzy_match_threshold = 0

        def map(self, license_field: str):
            if self.fuzzy_match_threshold >= 80:
                if license_field == "alpha":
                    return maps.MapResult("MIT", "spdx_id")
                return None
            if license_field == "alpha":
                return maps.MapResult("Apache-2.0", "spdx_id")
            if license_field == "beta":
                return maps.MapResult("Apache-2.0", "spdx_id")
            return None

    monkeypatch.setattr(tft.maps, "MapFuzzyMatch", FakeMapFuzzyMatch)

    df = pd.DataFrame(
        {
            "license_normalized": ["alpha", "beta", "gamma"],
            "ground_truth": ["MIT", "Apache-2.0", "BSD"],
        }
    )

    metrics_70 = tft._compute_metrics(df, 70)
    metrics_85 = tft._compute_metrics(df, 85)

    assert metrics_70.mapped_count == 2
    assert metrics_70.correct_mapped == 1
    assert metrics_70.precision == pytest.approx(0.5)
    assert metrics_70.recall == pytest.approx(1 / 3)
    assert metrics_70.f1 == pytest.approx(0.4)

    assert metrics_85.mapped_count == 1
    assert metrics_85.correct_mapped == 1
    assert metrics_85.precision == pytest.approx(1.0)
    assert metrics_85.recall == pytest.approx(1 / 3)
    assert metrics_85.f1 == pytest.approx(0.5)

    best = tft._select_best([metrics_70, metrics_85], "f1")
    assert best.threshold == 85


def test_normalize_fields_normalizes_ground_truth() -> None:
    """Verify that _normalize_fields normalizes both license and ground_truth."""
    df = pd.DataFrame(
        {
            "license": ["  MIT License  ", "Apache 2.0"],
            "ground_truth": ["  MIT  ", "APACHE-2.0"],
        }
    )

    normalized = tft._normalize_fields(df)

    assert normalized.loc[0, "license_normalized"] == "mit license"
    assert normalized.loc[0, "ground_truth"] == "mit"
    assert normalized.loc[1, "license_normalized"] == "apache 2 0"
    assert normalized.loc[1, "ground_truth"] == "apache 2 0"


def test_is_correct_prediction_with_normalized_values() -> None:
    """Verify that _is_correct_prediction works after normalization."""
    assert tft._is_correct_prediction("mit", "mit") is True
    assert tft._is_correct_prediction("mit", "apache") is False
    assert tft._is_correct_prediction(None, "mit") is False
    assert tft._is_correct_prediction("", "mit") is False
