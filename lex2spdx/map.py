"""Pipeline runner for mapping PyPI packages to SPDX licenses."""

import argparse
import os
import random
from datetime import datetime
from typing import TypedDict, Literal

import pandas as pd

from . import cvar
from . import logger
from . import maps
from . import preprocess

_log = logger.get()


def load_dataset(sample_size: int | None = None, random_start: bool = False,
                 path: str | None = None, drop_duplicate_licenses: bool = False) -> pd.DataFrame:
    """
    Loads the PyPI metadata dataset and drops empty license fields.

    :param path: The path to the dataset CSV file.
    :param sample_size: The number of rows to load instead of full dataset. If None, load the full dataset.
    :param random_start: If True, start sampling at random position in dataset. Only used if sample_size is not None.
    :param drop_duplicate_licenses: Whether to drop duplicate licenses and keep only entires with unique licenses (
    arbitrary drop order).
    """
    path = path or cvar.pypi_versions_dataset_path

    if sample_size is not None and random_start:
        # About 10% of the true dataset size, for faster random sampling.
        alleged_dataset_size = 15000

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

    if drop_duplicate_licenses:
        df.drop_duplicates(subset=["license"], inplace=True)
        _log.warning("Dropping duplicate licenses from dataset.")

    return df


class MapOutputEntry(TypedDict):
    idx: int
    license: str | None
    mapping_type: str
    map_name: str


class MapPipeline:

    def __init__(self, maps_list: list[maps.IMap]):
        self.maps = maps_list
        self.last_mapped_by_map: dict[
            str, list[tuple[int, str, str, str]]] = {}  # (idx, original_license, identifier, mapping_type)
        self.last_unresolved_by_map: dict[str, list[tuple[int, str]]] = {}

    def run(self, df: pd.DataFrame) -> tuple[list, list, set[int]]:
        mapped_rows_indices: list[MapOutputEntry] = list()
        # Contains each fail to map a field, meaning there can be multiple entries for the same row if it failed to
        # map in multiple maps.
        failed_rows_indices: list[MapOutputEntry] = list()

        # Contains only rows not yet mapped by any map.
        unresolved_rows_indices = set(df["idx"])

        self.last_mapped_by_map = {}
        self.last_unresolved_by_map = {}

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
                _log.debug("normalization changed '%s' to '%s'", maps.shorten_field(row_license),
                           maps.shorten_field(row_license_normalized))

                result = license_map.map(row_license_normalized)

                output_entry = MapOutputEntry(idx=idx, map_name=map_name)

                if result is None:
                    next_unresolved_rows_indices.add(idx)
                    unresolved_by_this_map.append((idx, row_license))
                    output_entry["license"] = None
                    output_entry["mapping_type"] = "undetermined"
                    failed_rows_indices.append(output_entry)
                    _log.info("❌Map %s did not map input '%s' (%s)",
                              map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license))
                elif result == "":
                    mapped_by_this_map.append((idx, row_license, "", "unknown"))
                    output_entry["license"] = ""
                    output_entry["mapping_type"] = "unknown"
                    mapped_rows_indices.append(output_entry)
                    _log.info("✅Map %s confirmed input '%s' (%s) as unknown",
                              map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license))
                else:
                    identifier = result.identifier
                    mapping_type = result.mapping_type
                    mapped_by_this_map.append((idx, row_license, identifier, mapping_type))
                    output_entry["license"] = identifier
                    output_entry["mapping_type"] = mapping_type
                    mapped_rows_indices.append(output_entry)
                    _log.info("✅Map %s mapped input '%s' (%s) to %s '%s'",
                              map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license),
                              mapping_type, identifier)

            self.last_mapped_by_map[map_name] = mapped_by_this_map
            self.last_unresolved_by_map[map_name] = unresolved_by_this_map
            unresolved_rows_indices = next_unresolved_rows_indices

        # String values of licenses that failed to map.
        failed_to_map = set(df[df["idx"].isin(unresolved_rows_indices)]["license"])

        return mapped_rows_indices, failed_rows_indices, failed_to_map


def run_map_pipeline(on_test_dataset: bool = False, sample_size: int | None = None, test_mode: bool = True) -> None:
    """
    Run the mapping pipeline on the PyPI dataset and save the mapped results to a CSV file.

    :param on_test_dataset: Whether to run the mapping pipeline on the test dataset.
    :param sample_size: The number of rows to load from the dataset. If None,
    :param test_mode: Enable test mode to run on smaller dataset with unique entries.
    load the full dataset. Ignored if on_test_dataset is True.
    """
    drop_duplicate_licenses = sample_size is not None

    if on_test_dataset:
        df = load_dataset(9999, False, cvar.data_dir / "pypi/test/test.csv")
    else:
        df_path = cvar.pypi_unique_licenses_dataset_path if test_mode else None
        df = load_dataset(sample_size, True, df_path, drop_duplicate_licenses)

    mp = MapPipeline([
        maps.MapNA(),
        maps.MapExactID(),
        maps.MapExactMatch(),
        maps.MapLicenseFamily(),
        maps.MapFuzzyMatch()
    ])

    mapped, map_fails, never_mapped = mp.run(df)

    _log.info("failed to map: %s", never_mapped)

    save_results(mapped, "mapped")
    save_results(map_fails, "failed")


def save_results(mapped: list[MapOutputEntry], result_type: Literal["mapped", "failed"]) -> None:
    """Save the mapped results to a CSV file in the output directory, with a timestamp in the filename."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S__%f")
    output_dir = cvar.data_dir / "output"
    dir_path = output_dir / result_type
    os.makedirs(dir_path, exist_ok=True)
    path = dir_path / f"{result_type}_{timestamp}.csv"
    df = pd.DataFrame(mapped, columns=["idx", "license", "mapping_type", "map_name"])
    df.to_csv(path, index=False)
    _log.info("Saved %d %s results to %s", len(mapped), result_type, path)


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
        default=100,
        help="Sample size if running on the default dataset.",
    )
    parser.add_argument(
        "-r",
        action="store_true",
        help="Enable test run for debugging the map pipeline."
    )
    args = parser.parse_args(argv)

    run_map_pipeline(args.t, args.s, args.r)


if __name__ == "__main__":
    main()
