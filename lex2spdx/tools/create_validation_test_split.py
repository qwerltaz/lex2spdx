"""Create random validation/test splits from the PyPI dataset."""

from __future__ import annotations

import argparse
import os.path
from pathlib import Path

import pandas as pd

from .. import cvar
from .. import logger

_log = logger.get()


def _load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if "license" not in df.columns:
        raise ValueError("Dataset is missing required 'license' column.")

    if "idx" not in df.columns:
        df = df.reset_index().rename(columns={"index": "idx"})

    df = df[["idx", "license"]].copy()
    df.dropna(subset=["license"], inplace=True)
    return df


def _validate_args(sample_size: int, validation_ratio: float) -> None:
    if sample_size <= 0:
        raise ValueError("sample_size must be a positive integer.")
    if not (0.0 < validation_ratio < 1.0):
        raise ValueError("validation_ratio must be between 0 and 1 (exclusive).")


def _split_sample(df: pd.DataFrame, sample_size: int, validation_ratio: float, seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    sample_size = min(sample_size, len(df))
    if sample_size == 0:
        raise ValueError("No rows available after filtering license values.")

    sample = df.sample(n=sample_size, random_state=seed)
    sample = sample.sample(frac=1, random_state=seed).reset_index(drop=True)

    validation_size = int(round(sample_size * validation_ratio))
    validation_size = max(1, min(validation_size, sample_size - 1))

    validation_df = sample.iloc[:validation_size].copy()
    test_df = sample.iloc[validation_size:].copy()

    validation_df["ground_truth"] = ""
    test_df["ground_truth"] = ""

    return validation_df, test_df


def _write_outputs(validation_df: pd.DataFrame, test_df: pd.DataFrame, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    validation_path = output_dir / f"validation.csv"
    test_path = output_dir / f"test.csv"

    if os.path.exists(validation_path) or os.path.exists(test_path):
        raise FileExistsError(f"Output files already exist: {validation_path}, {test_path}.")

    columns = ["idx", "license", "ground_truth"]
    validation_df.to_csv(validation_path, index=False, columns=columns)
    test_df.to_csv(test_path, index=False, columns=columns)

    return validation_path, test_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Create random validation/test splits for manual labeling.")
    parser.add_argument(
        "-s",
        "--sample-size",
        type=int,
        default=1000,
        help="Number of samples to include across validation and test.",
    )
    parser.add_argument(
        "-v",
        "--validation-ratio",
        type=float,
        default=0.6,
        help="Fraction of samples assigned to validation (0 < ratio < 1).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=cvar.data_dir / "pypi" / "validation",
        help="Directory to write split CSVs.",
    )
    args = parser.parse_args(argv)

    _validate_args(args.sample_size, args.validation_ratio)

    dataset_path = cvar.pypi_versions_dataset_path
    _log.info("Loading dataset from %s", dataset_path)

    df = _load_dataset(dataset_path)
    validation_df, test_df = _split_sample(df, args.sample_size, args.validation_ratio, args.seed)
    validation_path, test_path = _write_outputs(validation_df, test_df, args.output_dir)

    _log.info("Wrote %d validation rows to %s", len(validation_df), validation_path)
    _log.info("Wrote %d test rows to %s", len(test_df), test_path)


if __name__ == "__main__":
    main()

