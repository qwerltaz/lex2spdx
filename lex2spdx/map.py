"""Pipeline runner for mapping PyPI packages to SPDX licenses."""

import argparse
import os
import random
from datetime import datetime

import pandas as pd

from . import cvar
from . import logger
from . import maps
from . import preprocess

_log = logger.get()


def load_dataset(sample_size: int | None = None, random_start: bool = False,
                 path: str | None = None) -> pd.DataFrame:
    """
    Loads the PyPI metadata dataset and drops empty license fields.

    :param path: The path to the dataset CSV file.
    :param sample_size: The number of rows to load instead of full dataset. If None, load the full dataset.
    :param random_start: If True, start sampling at random position in dataset. Only used if sample_size is not None.
    :return: The loaded dataset.
    """
    path = path or cvar.pypi_versions_dataset_path

    if sample_size is not None and random_start:
        # About 10% of the true dataset size, for faster random sampling.
        alleged_dataset_size = 200000

        if sample_size > alleged_dataset_size:
            sample_size = alleged_dataset_size

        start_row = random.randint(0, alleged_dataset_size)

        df = pd.read_csv(
            path,
            low_memory=False,
            skiprows=range(1, start_row),
            nrows=sample_size,
        )
    else:
        df = pd.read_csv(path, low_memory=False, nrows=sample_size)

    df.drop(["Unnamed: 0"], axis=1, inplace=True)
    df.dropna(subset=["license"], inplace=True)
    return df


class MapPipeline:

    def __init__(self, maps: list[maps.IMap]):
        self.maps = maps
        self.last_mapped_by_map: dict[str, list[tuple[int, str, str]]] = {}
        self.last_unresolved_by_map: dict[str, list[tuple[int, str]]] = {}
        self.mapped_idx_to_spdx_id: dict[int, str] = {}

    def run(self, df: pd.DataFrame) -> tuple[set, set]:
        mapped_rows_indices = set()
        unresolved_rows_indices = set(df["idx"])

        self.last_mapped_by_map = {}
        self.last_unresolved_by_map = {}
        self.mapped_idx_to_spdx_id = {}

        rows_by_idx = df.set_index("idx")

        for license_map in self.maps:
            map_name = license_map.__class__.__name__
            mapped_by_this_map = []
            unresolved_by_this_map = []
            next_unresolved_rows_indices = set()

            for idx in unresolved_rows_indices:
                row = rows_by_idx.loc[idx]
                row_license = str(row["license"])

                row_license_normalized = preprocess.normalize_license_field(row_license) or ""
                _log.debug("normalization changed %s to %s", maps.shorten_field(row_license),
                           maps.shorten_field(row_license_normalized))

                result = license_map.map(row_license_normalized)

                if result is None:
                    next_unresolved_rows_indices.add(idx)
                    unresolved_by_this_map.append((idx, row_license))
                    _log.info("❌Map %s did not map input '%s' (%s)",
                              map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license))
                else:
                    mapped_rows_indices.add(idx)
                    mapped_by_this_map.append((idx, row_license, result))
                    self.mapped_idx_to_spdx_id[idx] = result
                    _log.info("✅Map %s mapped input '%s' (%s) to SPDX ID '%s'",
                              map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license),
                              result)

            self.last_mapped_by_map[map_name] = mapped_by_this_map
            self.last_unresolved_by_map[map_name] = unresolved_by_this_map
            unresolved_rows_indices = next_unresolved_rows_indices

        failed_rows_indices = unresolved_rows_indices

        return mapped_rows_indices, failed_rows_indices


def run_map_pipeline(on_test_dataset: bool = False, sample_size: int | None = None):
    if on_test_dataset:
        df = load_dataset(9999, False, cvar.data_dir / "pypi/test/test.csv")
    else:
        df = load_dataset(sample_size, True)

    mp = MapPipeline([maps.MapNA(), maps.MapExactID(), maps.MapExactMatch(), maps.MapSubstring(), maps.MapFuzzyMatch()])
    mapped, failed = mp.run(df)

    failed_df = df[[x in failed for x in df["idx"]]]
    mapped_df = df[[x in mapped for x in df["idx"]]]
    failed_set = set(failed_df["license"])
    _log.info("failed to map: %s", failed_set)

    mapped_results = []
    for i, (idx, spdx_id) in enumerate(sorted(mp.mapped_idx_to_spdx_id.items())):
        mapped_results.append({
            "dataset_index": idx,
            "spdx_id": spdx_id,
        })

    mapped_results_df = pd.DataFrame(mapped_results)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = cvar.data_dir / "output"
    output_path = output_dir / f"mapped-{timestamp}.csv"
    os.makedirs(output_dir, exist_ok=True)
    mapped_results_df.to_csv(output_path, index=True)
    _log.info("Saved %d mapped results to %s", len(mapped_results_df), output_path)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run SPDX mapping pipeline utilities.")

    parser.add_argument(
        "-t",
        action="store_true",
        help="Whether to run mapping pipeline on the test dataset.",
    )
    parser.add_argument(
        "-s",
        type=int,
        default=500,
        help="Sample size if running on the default dataset.",
    )
    args = parser.parse_args(argv)

    run_map_pipeline(args.t, args.s)


if __name__ == "__main__":
    main()
