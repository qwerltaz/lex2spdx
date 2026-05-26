"""Plot threshold tuning results from tune_fuzzy_threshold output."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def plot_threshold_tuning(
        validation_csv: Path,
        best_json: Path | None = None,
        output_path: Path | None = None,
) -> None:
    """
    Plot threshold tuning results.

    :param validation_csv: Path to validation metrics CSV file.
    :param best_json: Optional path to best threshold JSON file.
    :param output_path: Path to save the plot. If None, display interactively.
    """
    validation_df = pd.read_csv(validation_csv)

    best_threshold = None
    test_metrics = None
    if best_json and best_json.exists():
        with open(best_json, "r", encoding="utf-8") as f:
            best_data = json.load(f)
            best_threshold = best_data.get("best_threshold")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Fuzzy Threshold Tuning Results", fontsize=16, fontweight="bold")

    # 1. Precision vs Recall.
    ax = axes[0, 0]
    ax.plot(validation_df["recall"], validation_df["precision"], marker="o", linewidth=2, markersize=5)
    if best_threshold is not None:
        best_row = validation_df[validation_df["threshold"] == best_threshold]
        if not best_row.empty:
            best_recall = best_row["recall"].values[0]
            best_precision = best_row["precision"].values[0]
            ax.scatter([best_recall], [best_precision], color="red", s=200, marker="*", zorder=5,
                       label=f"Best ({best_threshold})")
            ax.legend()
    ax.set_xlabel("Recall", fontsize=11)
    ax.set_ylabel("Precision", fontsize=11)
    ax.set_title("Precision vs Recall", fontweight="bold")
    ax.grid(True, alpha=0.3)

    # 2. F1 Score vs Threshold.
    ax = axes[0, 1]
    ax.plot(validation_df["threshold"], validation_df["f1"], marker="o", linewidth=2, markersize=5, color="green")
    if best_threshold is not None:
        best_f1 = validation_df[validation_df["threshold"] == best_threshold]["f1"].values[0]
        ax.scatter([best_threshold], [best_f1], color="red", s=200, marker="*", zorder=5,
                   label=f"Best F1: {best_f1:.4f}")
        ax.legend()
    ax.set_xlabel("Threshold", fontsize=11)
    ax.set_ylabel("F1 Score", fontsize=11)
    ax.set_title("F1 Score vs Threshold", fontweight="bold")
    ax.grid(True, alpha=0.3)

    # 3. Precision, Recall, Coverage vs Threshold.
    ax = axes[1, 0]
    ax.plot(validation_df["threshold"], validation_df["precision"], marker="o", label="Precision", linewidth=2,
            markersize=4)
    ax.plot(validation_df["threshold"], validation_df["recall"], marker="s", label="Recall", linewidth=2, markersize=4)
    ax.plot(validation_df["threshold"], validation_df["coverage"], marker="^", label="Coverage", linewidth=2,
            markersize=4)
    if best_threshold is not None:
        ax.axvline(x=best_threshold, color="red", linestyle="--", linewidth=2, alpha=0.7,
                   label=f"Best Threshold: {best_threshold}")
    ax.set_xlabel("Threshold", fontsize=11)
    ax.set_ylabel("Score", fontsize=11)
    ax.set_title("Metrics vs Threshold", fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # 4. Mapped Count vs Threshold.
    ax = axes[1, 1]
    ax.plot(validation_df["threshold"], validation_df["mapped_count"], marker="o", linewidth=2, markersize=5,
            color="purple", label="Mapped")
    ax.plot(validation_df["threshold"], validation_df["correct_mapped"], marker="s", linewidth=2, markersize=5,
            color="orange", label="Correct")
    if best_threshold is not None:
        best_mapped = validation_df[validation_df["threshold"] == best_threshold]["mapped_count"].values[0]
        ax.scatter([best_threshold], [best_mapped], color="red", s=200, marker="*", zorder=5)
    ax.set_xlabel("Threshold", fontsize=11)
    ax.set_ylabel("Count", fontsize=11)
    ax.set_title("Mapped vs Correct Predictions", fontweight="bold")
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    output_path = validation_csv.parent / "threshold_tuning_results.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.show()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot threshold tuning results from tune_fuzzy_threshold.py output."
    )
    parser.add_argument(
        "--validation-csv",
        type=Path,
        help="Path to fuzzy_threshold_validation.csv file.",
    )
    parser.add_argument(
        "--best-json",
        type=Path,
        help="Path to fuzzy_threshold_best.json file (optional).",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="Path to the timestamped run directory. Auto-detects CSV and JSON files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.run_dir:
        if not args.run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {args.run_dir}")
        validation_csv = args.run_dir / "fuzzy_threshold_validation.csv"
        best_json = args.run_dir / "fuzzy_threshold_best.json"
        if not validation_csv.exists():
            raise FileNotFoundError(f"Validation CSV not found: {validation_csv}")
    else:
        if not args.validation_csv:
            raise ValueError("Either --run-dir or --validation-csv must be provided.")
        validation_csv = args.validation_csv
        best_json = args.best_json

    plot_threshold_tuning(validation_csv, best_json)


if __name__ == "__main__":
    main()
