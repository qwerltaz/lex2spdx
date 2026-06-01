"""Print map pipeline metrics on the validation test dataset."""

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from lex2spdx import cvar
from lex2spdx import maps
from lex2spdx import preprocess
from lex2spdx import spdx_license_data

REQUIRED_COLUMNS = ("idx", "license", "ground_truth")
LABEL_UNKNOWN = "<unknown>"
LABEL_UNDETERMINED = "<undetermined>"


@dataclass(frozen=True)
class PipelineMetrics:
    total_count: int
    mapped_count: int
    unknown_count: int
    undetermined_count: int
    coverage: float | None
    accuracy: float | None
    precision_weighted: float | None
    recall_weighted: float | None
    f1_weighted: float | None
    f1_macro: float | None


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
    df["ground_truth"] = df["ground_truth"].astype(str).str.strip()

    df = df.loc[df["ground_truth"].str.len() > 0].reset_index(drop=True)
    return df


def _normalize_eval_label(label: str, normalize_labels: bool) -> str:
    if label in (LABEL_UNKNOWN, LABEL_UNDETERMINED):
        return label
    cleaned = label.strip()
    if not normalize_labels:
        return cleaned
    normalized = preprocess.normalize_license_field(cleaned)
    return normalized if normalized is not None else cleaned


def _predict_label(
    license_field: str,
    maps_list: list[maps.IMap],
    normalized_to_original_id: dict[str, str],
) -> tuple[str, str]:
    license_normalized = preprocess.normalize_license_field(license_field) or ""
    for license_map in maps_list:
        result = license_map.map(license_normalized)
        if result is None:
            continue
        if result == "":
            return LABEL_UNKNOWN, "unknown"
        identifier = result.identifier
        if result.mapping_type == "spdx_id" and identifier in normalized_to_original_id:
            identifier = normalized_to_original_id[identifier]
        return identifier, result.mapping_type
    return LABEL_UNDETERMINED, "undetermined"


def _compute_metrics(df: pd.DataFrame, normalize_labels: bool) -> PipelineMetrics:
    maps_list: list[maps.IMap] = [
        maps.MapNA(),
        maps.MapExactID(),
        maps.MapExactMatch(),
        maps.MapLicenseFamily(),
        maps.MapFuzzyMatch(),
    ]
    normalized_to_original_id = spdx_license_data.get_normalized_to_original_id_mapping()

    y_true: list[str] = []
    y_pred: list[str] = []
    unknown_count = 0
    undetermined_count = 0

    for _, row in df.iterrows():
        license_field = str(row["license"])
        ground_truth = str(row["ground_truth"]).strip()

        predicted_label, mapping_type = _predict_label(license_field, maps_list, normalized_to_original_id)
        if mapping_type == "unknown":
            unknown_count += 1
        elif mapping_type == "undetermined":
            undetermined_count += 1

        y_true.append(_normalize_eval_label(ground_truth, normalize_labels))
        y_pred.append(_normalize_eval_label(predicted_label, normalize_labels))

    total_count = len(y_true)
    mapped_count = total_count - undetermined_count
    coverage = (mapped_count / total_count) if total_count else None

    if total_count:
        accuracy = accuracy_score(y_true, y_pred)
        precision_weighted = precision_score(y_true, y_pred, average="weighted", zero_division=0)
        recall_weighted = recall_score(y_true, y_pred, average="weighted", zero_division=0)
        f1_weighted = f1_score(y_true, y_pred, average="weighted", zero_division=0)
        f1_macro = f1_score(y_true, y_pred, average="macro", zero_division=0)
    else:
        accuracy = None
        precision_weighted = None
        recall_weighted = None
        f1_weighted = None
        f1_macro = None

    return PipelineMetrics(
        total_count=total_count,
        mapped_count=mapped_count,
        unknown_count=unknown_count,
        undetermined_count=undetermined_count,
        coverage=coverage,
        accuracy=accuracy,
        precision_weighted=precision_weighted,
        recall_weighted=recall_weighted,
        f1_weighted=f1_weighted,
        f1_macro=f1_macro,
    )


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _print_metrics(metrics: PipelineMetrics, normalize_labels: bool) -> None:
    label_mode = "normalized" if normalize_labels else "raw"
    print("Map pipeline metrics (test set)")
    print(f"Label comparison: {label_mode}")
    print(f"Total rows: {metrics.total_count}")
    print(f"Mapped rows: {metrics.mapped_count}")
    print(f"Unknown rows: {metrics.unknown_count}")
    print(f"Undetermined rows: {metrics.undetermined_count}")
    print(f"Coverage: {_format_metric(metrics.coverage)}")
    print(f"Accuracy: {_format_metric(metrics.accuracy)}")
    print(f"Precision (weighted): {_format_metric(metrics.precision_weighted)}")
    print(f"Recall (weighted): {_format_metric(metrics.recall_weighted)}")
    print(f"F1 (weighted): {_format_metric(metrics.f1_weighted)}")
    print(f"F1 (macro): {_format_metric(metrics.f1_macro)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print map pipeline metrics on the validation test dataset."
    )
    parser.add_argument(
        "--test-path",
        type=Path,
        default=cvar.data_dir / "pypi" / "validation" / "test.csv",
        help="Path to the test dataset CSV.",
    )
    parser.add_argument(
        "--raw-labels",
        action="store_true",
        help="Compare labels without normalization.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    df = _load_dataset(args.test_path)
    metrics = _compute_metrics(df, normalize_labels=not args.raw_labels)
    _print_metrics(metrics, normalize_labels=not args.raw_labels)


if __name__ == "__main__":
    main()

