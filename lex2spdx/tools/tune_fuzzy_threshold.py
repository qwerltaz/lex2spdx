"""Tune MapFuzzyMatch threshold using validation data and report test performance."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from lex2spdx import cvar
from lex2spdx import logger
from lex2spdx import maps
from lex2spdx import preprocess
from lex2spdx import spdx_license_data

_log = logger.get()

REQUIRED_COLUMNS = ("idx", "license", "ground_truth")


@dataclass(frozen=True)
class Metrics:
    threshold: int
    total_count: int
    mapped_count: int
    correct_mapped: int
    correct_mapped_equiv: int
    coverage: float | None
    precision: float | None
    recall: float | None
    f1: float | None
    precision_equiv: float | None
    recall_equiv: float | None
    f1_equiv: float | None


def _load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    df = pd.read_csv(path)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")

    df = df[list(REQUIRED_COLUMNS)].copy()
    df["license"] = df["license"].fillna("")
    df["ground_truth"] = df["ground_truth"].fillna("")

    df = df.loc[df["ground_truth"].astype(str).str.len() > 0].reset_index(drop=True)
    return df


def _normalize_fields(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["license_normalized"] = df["license"].apply(
        lambda value: preprocess.normalize_license_field(value) or ""
    )
    df["ground_truth"] = df["ground_truth"].apply(
        lambda value: preprocess.normalize_license_field(value) or ""
    )
    return df


def _filter_pipeline_candidates(df: pd.DataFrame) -> pd.DataFrame:
    pre_maps = [
        maps.MapNA(),
        maps.MapExactID(),
        maps.MapExactMatch(),
        maps.MapLicenseFamily(),
    ]

    def is_unresolved(license_field: str) -> bool:
        for license_map in pre_maps:
            result = license_map.map(license_field)
            if result is not None:
                return False
        return True

    mask = df["license_normalized"].apply(is_unresolved)
    return df.loc[mask].reset_index(drop=True)


def _is_correct_prediction(predicted: str | None, ground_truth: str) -> bool:
    if not predicted:
        return False
    if predicted == ground_truth:
        return True
    if ground_truth in maps.LICENSE_FAMILIES:
        return maps.SPDX_ID_TO_FAMILY.get(predicted) == ground_truth
    return False


_GPL_VARIANT_PATTERN = re.compile(r"^(agpl|gpl|lgpl)\s+(\d+)(?:\s+0){1,2}(?:\s+(?:only|or\s+later))?$")

_NORMALIZED_SPDX_IDS = set(spdx_license_data.LicenseDataNormalized.license_ids)


def _build_variant_base_map(license_ids: set[str]) -> dict[str, str]:
    base_map: dict[str, str] = {}
    for license_id in license_ids:
        tokens = license_id.split()
        base = None
        for i in range(len(tokens) - 1, 0, -1):
            candidate = " ".join(tokens[:i])
            if candidate in license_ids:
                base = candidate
                break
        base_map[license_id] = base or license_id
    return base_map


_VARIANT_BASE_BY_ID = _build_variant_base_map(_NORMALIZED_SPDX_IDS)


def _gpl_variant_key(value: str | None) -> tuple[str, int] | None:
    if not value:
        return None
    match = _GPL_VARIANT_PATTERN.match(value)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def _variant_base_id(value: str | None) -> str | None:
    if not value:
        return None
    return _VARIANT_BASE_BY_ID.get(value)


def _is_equivalent_prediction(predicted: str | None, ground_truth: str) -> bool:
    if _is_correct_prediction(predicted, ground_truth):
        return True
    if not predicted:
        return False
    predicted_key = _gpl_variant_key(predicted)
    ground_truth_key = _gpl_variant_key(ground_truth)
    if predicted_key is not None and predicted_key == ground_truth_key:
        return True
    predicted_base = _variant_base_id(predicted)
    ground_truth_base = _variant_base_id(ground_truth)
    return predicted_base is not None and predicted_base == ground_truth_base


def _compute_metrics(df: pd.DataFrame, threshold: int) -> Metrics:
    fuzzy_map = maps.MapFuzzyMatch()
    fuzzy_map.fuzzy_match_threshold = threshold

    total_count = len(df)
    mapped_count = 0
    correct_mapped = 0
    correct_mapped_equiv = 0

    for _, row in df.iterrows():
        result = fuzzy_map.map(row["license_normalized"])
        predicted = result.identifier if isinstance(result, maps.MapResult) else None
        if predicted is not None:
            mapped_count += 1
        ground_truth = row["ground_truth"]
        if _is_correct_prediction(predicted, ground_truth):
            correct_mapped += 1
        if _is_equivalent_prediction(predicted, ground_truth):
            correct_mapped_equiv += 1

    coverage = (mapped_count / total_count) if total_count else None
    precision = (correct_mapped / mapped_count) if mapped_count else None
    recall = (correct_mapped / total_count) if total_count else None
    precision_equiv = (correct_mapped_equiv / mapped_count) if mapped_count else None
    recall_equiv = (correct_mapped_equiv / total_count) if total_count else None

    if precision and recall and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = None

    if precision_equiv and recall_equiv and (precision_equiv + recall_equiv) > 0:
        f1_equiv = 2 * precision_equiv * recall_equiv / (precision_equiv + recall_equiv)
    else:
        f1_equiv = None

    return Metrics(
        threshold=threshold,
        total_count=total_count,
        mapped_count=mapped_count,
        correct_mapped=correct_mapped,
        correct_mapped_equiv=correct_mapped_equiv,
        coverage=coverage,
        precision=precision,
        recall=recall,
        f1=f1,
        precision_equiv=precision_equiv,
        recall_equiv=recall_equiv,
        f1_equiv=f1_equiv,
    )


def _collect_wrong_predictions(df: pd.DataFrame, threshold: int) -> pd.DataFrame:
    fuzzy_map = maps.MapFuzzyMatch()
    fuzzy_map.fuzzy_match_threshold = threshold

    records: list[dict[str, object]] = []
    for _, row in df.iterrows():
        result = fuzzy_map.map(row["license_normalized"])
        predicted = result.identifier if isinstance(result, maps.MapResult) else None
        if predicted is None:
            continue
        ground_truth = row["ground_truth"]
        exact_correct = _is_correct_prediction(predicted, ground_truth)
        equiv_correct = _is_equivalent_prediction(predicted, ground_truth)
        if exact_correct:
            continue
        records.append({
            "idx": row["idx"],
            "license": row["license"],
            "license_normalized": row["license_normalized"],
            "ground_truth": ground_truth,
            "predicted": predicted,
            "exact_correct": exact_correct,
            "equiv_correct": equiv_correct,
        })

    return pd.DataFrame.from_records(records)


def _select_best(metrics: list[Metrics], objective: str) -> Metrics:
    if not metrics:
        raise ValueError("No metrics to select from.")

    def sort_key(item: Metrics) -> tuple:
        primary = getattr(item, objective)
        primary_value = primary if primary is not None else -1
        precision_value = item.precision if item.precision is not None else -1
        coverage_value = item.coverage if item.coverage is not None else -1
        return primary_value, precision_value, coverage_value

    return max(metrics, key=sort_key)


def _metrics_to_frame(metrics: list[Metrics]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "threshold": item.threshold,
            "total_count": item.total_count,
            "mapped_count": item.mapped_count,
            "correct_mapped": item.correct_mapped,
            "correct_mapped_equiv": item.correct_mapped_equiv,
            "coverage": item.coverage,
            "precision": item.precision,
            "recall": item.recall,
            "f1": item.f1,
            "precision_equiv": item.precision_equiv,
            "recall_equiv": item.recall_equiv,
            "f1_equiv": item.f1_equiv,
        }
        for item in metrics
    ])


def _write_outputs(
        output_dir: Path,
        timestamp: str,
        validation_metrics: list[Metrics],
        best_validation: Metrics,
        test_metrics: Metrics | None,
        wrong_predictions: pd.DataFrame | None,
        config: dict[str, object],
) -> dict[str, Path | None]:
    timestamped_dir = output_dir / timestamp
    timestamped_dir.mkdir(parents=True, exist_ok=True)

    validation_path = timestamped_dir / "fuzzy_threshold_validation.csv"
    best_path = timestamped_dir / "fuzzy_threshold_best.json"
    test_path = timestamped_dir / "fuzzy_threshold_test.json"
    wrong_predictions_path = timestamped_dir / "fuzzy_threshold_wrong_predictions.csv"

    _metrics_to_frame(validation_metrics).to_csv(validation_path, index=False)

    best_payload = {
        "best_threshold": best_validation.threshold,
        "validation": best_validation.__dict__,
        "config": config,
    }
    with open(best_path, "w", encoding="utf-8") as handle:
        json.dump(best_payload, handle, indent=2, sort_keys=True)

    if test_metrics is not None:
        with open(test_path, "w", encoding="utf-8") as handle:
            json.dump({"test": test_metrics.__dict__}, handle, indent=2, sort_keys=True)

    if wrong_predictions is not None:
        wrong_predictions.to_csv(wrong_predictions_path, index=False)

    return {
        "validation_path": validation_path,
        "best_path": best_path,
        "test_path": test_path if test_metrics is not None else None,
        "wrong_predictions_path": wrong_predictions_path if wrong_predictions is not None else None,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tune MapFuzzyMatch threshold using validation data and report test performance."
    )
    parser.add_argument(
        "--validation-path",
        type=Path,
        default=cvar.data_dir / "pypi" / "validation" / "validation.csv",
        help="Path to validation dataset CSV.",
    )
    parser.add_argument(
        "--test-path",
        type=Path,
        default=cvar.data_dir / "pypi" / "validation" / "test.csv",
        help="Path to test dataset CSV.",
    )
    parser.add_argument(
        "--min-threshold",
        type=int,
        default=60,
        help="Minimum fuzzy threshold to evaluate (inclusive).",
    )
    parser.add_argument(
        "--max-threshold",
        type=int,
        default=95,
        help="Maximum fuzzy threshold to evaluate (inclusive).",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=1,
        help="Step size for threshold grid.",
    )
    parser.add_argument(
        "--objective",
        choices=("f1", "precision", "coverage", "recall"),
        default="f1",
        help="Metric to optimize on validation data.",
    )
    parser.add_argument(
        "--no-pipeline-filter",
        action="store_true",
        help="Skip filtering examples that earlier maps already resolve.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=cvar.data_dir / "output" / "threshold_tuning",
        help="Directory to write tuning results.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    validation = _normalize_fields(_load_dataset(args.validation_path))
    test = _normalize_fields(_load_dataset(args.test_path))

    if not args.no_pipeline_filter:
        validation = _filter_pipeline_candidates(validation)
        test = _filter_pipeline_candidates(test)

    thresholds = list(range(args.min_threshold, args.max_threshold + 1, args.step))
    validation_metrics = [_compute_metrics(validation, threshold) for threshold in thresholds]
    best_validation = _select_best(validation_metrics, args.objective)

    test_metrics = None
    if not test.empty:
        test_metrics = _compute_metrics(test, best_validation.threshold)

    wrong_source = test if not test.empty else validation
    wrong_predictions = _collect_wrong_predictions(wrong_source, best_validation.threshold)
    if wrong_predictions.empty:
        wrong_predictions = None

    config = {
        "validation_path": str(args.validation_path),
        "test_path": str(args.test_path),
        "min_threshold": args.min_threshold,
        "max_threshold": args.max_threshold,
        "step": args.step,
        "objective": args.objective,
        "pipeline_filter": not args.no_pipeline_filter,
    }

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S__%f")
    outputs = _write_outputs(
        args.output_dir,
        timestamp,
        validation_metrics,
        best_validation,
        test_metrics,
        wrong_predictions,
        config,
    )

    _log.info("Best threshold on validation (%s): %s", args.objective, best_validation.threshold)
    _log.info("Validation precision: %s", best_validation.precision)
    _log.info("Validation recall: %s", best_validation.recall)
    _log.info("Validation f1: %s", best_validation.f1)
    _log.info("Validation precision (equiv): %s", best_validation.precision_equiv)
    _log.info("Validation recall (equiv): %s", best_validation.recall_equiv)
    _log.info("Validation f1 (equiv): %s", best_validation.f1_equiv)
    _log.info("Validation coverage: %s", best_validation.coverage)
    if test_metrics is not None:
        _log.info("Test precision: %s", test_metrics.precision)
        _log.info("Test recall: %s", test_metrics.recall)
        _log.info("Test f1: %s", test_metrics.f1)
        _log.info("Test precision (equiv): %s", test_metrics.precision_equiv)
        _log.info("Test recall (equiv): %s", test_metrics.recall_equiv)
        _log.info("Test f1 (equiv): %s", test_metrics.f1_equiv)
        _log.info("Test coverage: %s", test_metrics.coverage)

    _log.info("Wrote validation grid to %s", outputs["validation_path"])
    _log.info("Wrote best threshold to %s", outputs["best_path"])
    if outputs["test_path"] is not None:
        _log.info("Wrote test metrics to %s", outputs["test_path"])
    if outputs["wrong_predictions_path"] is not None:
        _log.info("Wrote wrong predictions to %s", outputs["wrong_predictions_path"])


if __name__ == "__main__":
    main()
