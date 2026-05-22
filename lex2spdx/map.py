"""Pipeline runner for mapping PyPI packages to SPDX licenses."""

import argparse
import os
import random
from datetime import datetime
from typing import TypedDict, Literal
import json

import pandas as pd
from tqdm import tqdm

from . import cvar
from . import logger
from . import maps
from . import preprocess
from . import spdx_license_data

_log = logger.get()


def _load_row_count_cache(cache_path: os.PathLike | str) -> dict[str, dict[str, int]]:
    if not os.path.exists(cache_path):
        return {}
    with open(cache_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_row_count_cache(cache_path: os.PathLike | str, cache: dict[str, dict[str, int]]) -> None:
    os.makedirs(os.path.dirname(os.fspath(cache_path)), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2, sort_keys=True)


def _get_dataset_row_count(path: str | os.PathLike) -> int:
    """Return the number of data rows (excluding header) in a CSV file."""
    cache_path = cvar.data_dir / "output" / "dataset_row_counts.json"
    path_str = os.fspath(path)
    stat = os.stat(path_str)

    cache = _load_row_count_cache(cache_path)
    cached = cache.get(path_str)
    if cached and cached.get("mtime") == int(stat.st_mtime) and cached.get("size") == stat.st_size:
        return cached.get("rows", 0)

    df = pd.read_csv(path_str)
    row_count = max(0, len(df) - 1)

    cache[path_str] = {"mtime": int(stat.st_mtime), "size": stat.st_size, "rows": row_count}
    _save_row_count_cache(cache_path, cache)

    return row_count


def load_already_mapped_indices() -> set[int]:
    """Load previously mapped row indices from CSVs in the output/mapped directory."""
    mapped_dir = cvar.data_dir / "output" / "mapped"
    if not mapped_dir.exists():
        return set()

    mapped_files = mapped_dir.glob("*.csv")
    if not mapped_files:
        return set()

    mapped_indices: set[int] = set()
    for mapped_file in mapped_files:
        # No try-except. Let it fail on unexpected columns or other error.
        df = pd.read_csv(mapped_file, usecols=["idx"])

        idx_values = pd.to_numeric(df["idx"]).dropna().astype(int)
        mapped_indices.update(idx_values.tolist())

    return mapped_indices


def load_dataset(sample_size: int | None = None, random_start: bool = False,
                 path: str | None = None, drop_duplicate_licenses: bool = True) -> pd.DataFrame:
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
        total_rows = _get_dataset_row_count(path)
        if total_rows == 0 or sample_size == 0:
            return pd.read_csv(path, low_memory=False, nrows=0)

        if sample_size > total_rows:
            sample_size = total_rows

        max_start = max(0, total_rows - sample_size)
        start_row = random.randint(0, max_start)

        df = pd.read_csv(
            path,
            low_memory=False,
            skiprows=range(1, start_row + 1),
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
        self.normalized_to_original_id = spdx_license_data.get_normalized_to_original_id_mapping()

        self.save_results_threshold = 10000

    def run(self, df: pd.DataFrame) -> tuple[list, list, set[int]]:
        mapped_rows_indices: list[MapOutputEntry] = list()
        failed_rows_indices: list[MapOutputEntry] = list()

        existing_mapped_indices = load_already_mapped_indices()
        existing_mapped_in_df = set(df["idx"]).intersection(existing_mapped_indices)
        if existing_mapped_in_df:
            _log.info("Skipping %d rows that are already mapped.", len(existing_mapped_in_df))

        unresolved_rows_indices = set(df["idx"]) - existing_mapped_in_df

        self.last_mapped_by_map = {m.__class__.__name__: [] for m in self.maps}
        self.last_unresolved_by_map = {m.__class__.__name__: [] for m in self.maps}

        rows_by_idx = df.set_index("idx")
        failed_to_map = set()

        for count, idx in tqdm(enumerate(unresolved_rows_indices, start=1), total=len(unresolved_rows_indices), desc="Mapping rows"):
            row = rows_by_idx.loc[idx]
            row_license = str(row["license"])

            row_license_normalized = preprocess.normalize_license_field(row_license) or ""
            _log.debug("normalization changed '%s' to '%s'", maps.shorten_field(row_license),
                       maps.shorten_field(row_license_normalized))

            is_mapped = False
            for license_map in self.maps:
                map_name = license_map.__class__.__name__

                _log.debug("Mapping idx %s with license '%s' using map %s", idx,
                           maps.shorten_field(row_license), map_name)

                result = license_map.map(row_license_normalized)
                output_entry = MapOutputEntry(idx=idx, map_name=map_name)

                if result is None:
                    self.last_unresolved_by_map[map_name].append((idx, row_license))
                    output_entry["license"] = None
                    output_entry["mapping_type"] = "undetermined"
                    failed_rows_indices.append(output_entry)
                    _log.debug("❌Map %s did not map input '%s' (%s)",
                               map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license))
                elif result == "":
                    self.last_mapped_by_map[map_name].append((idx, row_license, "", "unknown"))
                    output_entry["license"] = ""
                    output_entry["mapping_type"] = "unknown"
                    mapped_rows_indices.append(output_entry)
                    _log.info("✅Map %s confirmed input '%s' (%s) as unknown",
                              map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license))
                    is_mapped = True
                    break
                else:
                    identifier = result.identifier
                    mapping_type = result.mapping_type

                    if mapping_type == "spdx_id" and identifier in self.normalized_to_original_id:
                        identifier = self.normalized_to_original_id[identifier]

                    self.last_mapped_by_map[map_name].append((idx, row_license, identifier, mapping_type))
                    output_entry["license"] = identifier
                    output_entry["mapping_type"] = mapping_type
                    mapped_rows_indices.append(output_entry)

                    _log.info("✅Map %s mapped input '%s' (%s) to %s '%s'",
                              map_name, maps.shorten_field(row_license_normalized), maps.shorten_field(row_license),
                              mapping_type, identifier)

                    is_mapped = True
                    break

            if not is_mapped:
                failed_to_map.add(row_license)

            if len(mapped_rows_indices) >= self.save_results_threshold:
                save_results(mapped_rows_indices, "mapped")
                save_results(failed_rows_indices, "failed")
                mapped_rows_indices.clear()
                failed_rows_indices.clear()

        return mapped_rows_indices, failed_rows_indices, failed_to_map


def run_map_pipeline(on_test_dataset: bool = False, sample_size: int | None = None,
                     unique_entries_dataset: bool = True) -> None:
    """
    Run the mapping pipeline on the PyPI dataset and save the mapped results to a CSV file.

    :param on_test_dataset: Whether to run the mapping pipeline on the test dataset.
    :param sample_size: The number of rows to load from the dataset. If None,
    :param unique_entries_dataset: Run on dataset with only unique entries.
    load the full dataset. Ignored if on_test_dataset is True.
    """
    if sample_size == -1:
        sample_size = None

    if on_test_dataset:
        df = load_dataset(9999, False, cvar.data_dir / "pypi/test/test.csv")
    else:
        random_start = isinstance(sample_size, int) and sample_size >= 0
        df_path = cvar.pypi_unique_licenses_dataset_path if unique_entries_dataset else None
        df = load_dataset(sample_size, random_start, df_path)

    mp = MapPipeline([
        maps.MapNA(),
        maps.MapExactID(),
        maps.MapExactMatch(),
        maps.MapLicenseFamily(),
        maps.MapFuzzyMatch()
    ])

    mapped, map_fails, never_mapped = mp.run(df)

    _log.info("failed to map: %s", never_mapped)

    if mapped:
        save_results(mapped, "mapped")
    if map_fails:
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
        help="Sample size if running on the default dataset. -1 to run on the full dataset."
    )
    parser.add_argument(
        "-r",
        action="store_true",
        help="Run on dataset with only unique license entries."
    )
    args = parser.parse_args(argv)

    run_map_pipeline(args.t, args.s, args.r)


if __name__ == "__main__":
    main()
