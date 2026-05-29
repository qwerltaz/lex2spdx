"""Evaluate mapping outputs from data/output for pipeline and map performance."""

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .. import cvar
from .. import logger

_log = logger.get()

EXPECTED_COLUMNS = ("idx", "license", "mapping_type", "map_name")


@dataclass(frozen=True)
class OutputFiles:
    mapped: list[Path]
    failed: list[Path]


@dataclass(frozen=True)
class EvaluationOutputs:
    summary_path: Path
    map_performance_path: Path
    mapping_type_counts_path: Path
    map_success_counts_path: Path
    top_identifiers_path: Path
    conflicts_path: Path | None
    unresolved_inputs_path: Path
    predicted_inputs_path: Path


def _list_csv_files(dir_path: Path) -> list[Path]:
    if not dir_path.exists():
        return []
    return sorted(path for path in dir_path.glob("*.csv") if path.is_file())


def _load_output_df(files: Iterable[Path], label: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in files:
        df = pd.read_csv(path)
        missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Missing columns in {path}: {missing}")

        df = df[list(EXPECTED_COLUMNS)].copy()
        df["source_path"] = os.fspath(path)
        df["source_mtime"] = int(path.stat().st_mtime)
        df["source_label"] = label
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=list(EXPECTED_COLUMNS) + ["source_path", "source_mtime", "source_label"])

    return pd.concat(frames, ignore_index=True)


def _normalize_idx(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["idx"] = pd.to_numeric(df["idx"], errors="coerce")
    df = df.dropna(subset=["idx"])
    df["idx"] = df["idx"].astype(int)
    return df


def _dedupe_mapped(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return df, df.copy()

    signature_source = df[["license", "mapping_type", "map_name"]].fillna("")
    signature = signature_source.astype(str).agg("|".join, axis=1)
    df = df.assign(mapping_signature=signature)

    conflict_mask = df.groupby("idx")["mapping_signature"].transform("nunique") > 1
    conflicts = df.loc[conflict_mask].copy()

    df_sorted = df.sort_values(["idx", "source_mtime"]).copy()
    deduped = df_sorted.groupby("idx", as_index=False).tail(1)
    deduped = deduped.drop(columns=["mapping_signature"])
    conflicts = conflicts.drop(columns=["mapping_signature"])
    return deduped.reset_index(drop=True), conflicts.reset_index(drop=True)


def _dedupe_failed(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    return df.drop_duplicates(subset=["idx", "map_name"]).reset_index(drop=True)


def _evaluate_pipeline(mapped_df: pd.DataFrame, failed_df: pd.DataFrame) -> dict[str, object]:
    mapped_indices = set(mapped_df["idx"].tolist()) if not mapped_df.empty else set()
    failed_indices = set(failed_df["idx"].tolist()) if not failed_df.empty else set()

    unresolved_indices = failed_indices - mapped_indices
    total_indices = mapped_indices | failed_indices

    summary: dict[str, object] = {
        "mapped_unique": len(mapped_indices),
        "failed_unique": len(failed_indices),
        "unresolved_unique": len(unresolved_indices),
        "total_unique_seen": len(total_indices),
        "coverage_rate": (len(mapped_indices) / len(total_indices)) if total_indices else None,
    }

    type_counts = mapped_df["mapping_type"].value_counts(dropna=False)
    for mapping_type, count in type_counts.items():
        summary[f"mapping_type_{mapping_type}"] = int(count)

    return summary


def _evaluate_maps(mapped_df: pd.DataFrame, failed_df: pd.DataFrame) -> pd.DataFrame:
    success_counts = mapped_df.groupby("map_name")["idx"].nunique().rename("successes")

    # Count attempts as unique indices where each map was tried (succeeded or failed)
    combined_attempts = pd.concat([
        mapped_df[["idx", "map_name"]],
        failed_df[["idx", "map_name"]]
    ], ignore_index=True)
    attempt_counts = combined_attempts.groupby("map_name")["idx"].nunique().rename("attempts")

    map_perf = pd.concat([attempt_counts, success_counts], axis=1).fillna(0)
    map_perf["attempts"] = map_perf["attempts"].astype(int)
    map_perf["successes"] = map_perf["successes"].astype(int)
    map_perf["success_rate"] = map_perf.apply(
        lambda row: (row["successes"] / row["attempts"]) if row["attempts"] else None, axis=1
    )

    unknown_by_map = (
        mapped_df.loc[mapped_df["mapping_type"] == "unknown"]
        .groupby("map_name")["idx"].nunique()
        .rename("unknowns")
    )
    map_perf = pd.concat([map_perf, unknown_by_map], axis=1).fillna(0)
    map_perf["unknowns"] = map_perf["unknowns"].astype(int)

    map_perf = map_perf.reset_index().sort_values(["success_rate", "successes"], ascending=[False, False])
    return map_perf


def _top_identifiers(mapped_df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    spdx_only = mapped_df.loc[mapped_df["mapping_type"] == "spdx_id"]
    if spdx_only.empty:
        return pd.DataFrame(columns=["license", "count"])

    counts = spdx_only["license"].value_counts().head(top_n).rename_axis("license").reset_index(name="count")
    return counts


def _load_ground_truth(path: Path) -> pd.DataFrame:
    if not path.exists():
        _log.warning("Ground truth file not found: %s", path)
        return pd.DataFrame(columns=["idx", "ground_truth"])

    df = pd.read_csv(path)
    required = {"idx", "ground_truth"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {sorted(missing)}")

    df = df[["idx", "ground_truth"]].copy()
    df["idx"] = pd.to_numeric(df["idx"], errors="coerce")
    df = df.dropna(subset=["idx"])
    df["idx"] = df["idx"].astype(int)
    df["ground_truth"] = df["ground_truth"].fillna("")
    return df


def _load_input_licenses(indices: Iterable[int], dataset_path: Path) -> pd.DataFrame:
    idx_set = {int(idx) for idx in indices}
    if not idx_set:
        return pd.DataFrame(columns=["idx", "input_license"])
    if not dataset_path.exists():
        _log.warning("Dataset file not found: %s", dataset_path)
        return pd.DataFrame(columns=["idx", "input_license"])

    frames: list[pd.DataFrame] = []
    usecols = ["idx", "license"]
    for chunk in pd.read_csv(dataset_path, usecols=usecols, chunksize=100_000, low_memory=False):
        chunk["idx"] = pd.to_numeric(chunk["idx"], errors="coerce")
        chunk = chunk.dropna(subset=["idx"])
        chunk["idx"] = chunk["idx"].astype(int)
        matched = chunk[chunk["idx"].isin(idx_set)]
        if not matched.empty:
            matched = matched[["idx", "license"]].rename(columns={"license": "input_license"})
            frames.append(matched)
        if matched.shape[0] >= len(idx_set):
            break

    if not frames:
        return pd.DataFrame(columns=["idx", "input_license"])

    merged = pd.concat(frames, ignore_index=True)
    return merged.drop_duplicates(subset=["idx"]).reset_index(drop=True)


def _write_outputs(
        output_dir: Path,
        timestamp: str,
        summary: dict[str, object],
        map_perf: pd.DataFrame,
        mapping_type_counts: pd.DataFrame,
        map_success_counts: pd.DataFrame,
        top_identifiers: pd.DataFrame,
        conflicts: pd.DataFrame,
        unresolved_inputs: pd.DataFrame,
        predicted_inputs: pd.DataFrame,
) -> EvaluationOutputs:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / f"evaluation_summary_{timestamp}.json"
    map_perf_path = output_dir / f"map_performance_{timestamp}.csv"
    mapping_type_counts_path = output_dir / f"mapping_type_counts_{timestamp}.csv"
    map_success_counts_path = output_dir / f"map_success_counts_{timestamp}.csv"
    top_identifiers_path = output_dir / f"top_identifiers_{timestamp}.csv"
    unresolved_inputs_path = output_dir / f"unresolved_input_licenses_{timestamp}.csv"
    predicted_inputs_path = output_dir / f"predicted_input_licenses_{timestamp}.csv"
    conflicts_path: Path | None = None

    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)

    map_perf.to_csv(map_perf_path, index=False)
    mapping_type_counts.to_csv(mapping_type_counts_path, index=False)
    map_success_counts.to_csv(map_success_counts_path, index=False)
    top_identifiers.to_csv(top_identifiers_path, index=False)
    unresolved_inputs.to_csv(unresolved_inputs_path, index=False)
    predicted_inputs.to_csv(predicted_inputs_path, index=False)

    if not conflicts.empty:
        conflicts_path = output_dir / f"mapping_conflicts_{timestamp}.csv"
        conflicts.to_csv(conflicts_path, index=False)

    return EvaluationOutputs(
        summary_path=summary_path,
        map_performance_path=map_perf_path,
        mapping_type_counts_path=mapping_type_counts_path,
        map_success_counts_path=map_success_counts_path,
        top_identifiers_path=top_identifiers_path,
        conflicts_path=conflicts_path,
        unresolved_inputs_path=unresolved_inputs_path,
        predicted_inputs_path=predicted_inputs_path,
    )


def _log_summary(summary: dict[str, object]) -> None:
    _log.info("Pipeline coverage: %s", summary.get("coverage_rate"))
    _log.info("Mapped unique: %s", summary.get("mapped_unique"))
    _log.info("Unresolved unique: %s", summary.get("unresolved_unique"))
    for key, value in summary.items():
        if key.startswith("mapping_type_"):
            _log.info("%s: %s", key, value)


def evaluate_outputs(
        mapped_dir: Path,
        failed_dir: Path,
        output_dir: Path,
        top_n: int,
        dataset_path: Path,
) -> EvaluationOutputs:
    mapped_files = _list_csv_files(mapped_dir)
    failed_files = _list_csv_files(failed_dir)

    if not mapped_files:
        _log.warning("No mapped outputs found in %s", mapped_dir)
    if not failed_files:
        _log.warning("No failed outputs found in %s", failed_dir)

    mapped_df = _load_output_df(mapped_files, "mapped")
    failed_df = _load_output_df(failed_files, "failed")

    mapped_df = _normalize_idx(mapped_df)
    failed_df = _normalize_idx(failed_df)

    mapped_df, conflicts = _dedupe_mapped(mapped_df)
    failed_df = _dedupe_failed(failed_df)

    summary = _evaluate_pipeline(mapped_df, failed_df)
    map_perf = _evaluate_maps(mapped_df, failed_df)
    mapping_type_counts = (
        mapped_df["mapping_type"].value_counts(dropna=False).rename_axis("mapping_type").reset_index(name="count")
    )
    map_success_counts = mapped_df["map_name"].value_counts().rename_axis("map_name").reset_index(name="count")
    top_identifiers = _top_identifiers(mapped_df, top_n)

    mapped_indices = set(mapped_df["idx"].tolist()) if not mapped_df.empty else set()
    failed_indices = set(failed_df["idx"].tolist()) if not failed_df.empty else set()
    unresolved_indices = failed_indices - mapped_indices

    unresolved_inputs = _load_input_licenses(unresolved_indices, dataset_path)

    predicted_inputs = _load_input_licenses(mapped_indices, dataset_path)
    if not predicted_inputs.empty:
        predicted_inputs = predicted_inputs.merge(
            mapped_df[["idx", "license", "mapping_type", "map_name"]],
            on="idx",
            how="left",
        ).rename(columns={"license": "predicted_license"})

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S__%f")
    outputs = _write_outputs(
        output_dir,
        timestamp,
        summary,
        map_perf,
        mapping_type_counts,
        map_success_counts,
        top_identifiers,
        conflicts,
        unresolved_inputs,
        predicted_inputs,
    )

    _log_summary(summary)
    if not conflicts.empty:
        _log.warning("Found %d mapping conflicts across outputs.", len(conflicts))

    return outputs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate mapped outputs for pipeline and map performance.")
    parser.add_argument(
        "--mapped-dir",
        type=Path,
        default=cvar.data_dir / "output" / "mapped",
        help="Directory with mapped CSV outputs.",
    )
    parser.add_argument(
        "--failed-dir",
        type=Path,
        default=cvar.data_dir / "output" / "failed",
        help="Directory with failed CSV outputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=cvar.data_dir / "output" / "evaluation",
        help="Directory to write evaluation results.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Number of top SPDX identifiers to include.",
    )
    parser.add_argument(
        "--dataset-path",
        type=Path,
        default=cvar.pypi_unique_licenses_dataset_path,
        help="Dataset CSV containing idx and license columns.",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    evaluate_outputs(
        args.mapped_dir,
        args.failed_dir,
        args.output_dir,
        args.top_n,
        args.dataset_path,
    )


if __name__ == "__main__":
    main()
