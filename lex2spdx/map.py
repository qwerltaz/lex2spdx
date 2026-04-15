"""Pipeline runner for mapping PyPI packages to SPDX licenses."""
import argparse
import random
import pandas as pd

try:
    from . import cvar
    from . import maps
    from . import logger
except ImportError:
    import cvar
    import maps
    import logger

log = logger.get()


def load_dataset(sample_size: int | None = None, random_start: bool = False) -> pd.DataFrame:
    """
    Loads the PyPI metadata dataset and drops empty license fields.

    :param sample_size: The number of rows to load instead of full dataset. If None, load the full dataset.
    :param random_start: If True, start sampling at random position in dataset. Only used if sample_size is not None.
    :return: The loaded dataset.
    """
    if sample_size is not None and random_start:
        # About 10% of the true dataset size, for faster random sampling.
        alleged_dataset_size = 200000

        if sample_size > alleged_dataset_size:
            sample_size = alleged_dataset_size

        start_row = random.randint(0, alleged_dataset_size)

        df = pd.read_csv(
            cvar.pypi_versions_dataset_path,
            low_memory=False,
            skiprows=range(1, start_row),
            nrows=sample_size,
        )
    else:
        df = pd.read_csv(cvar.pypi_versions_dataset_path, low_memory=False, nrows=sample_size)

    df.drop(["Unnamed: 0"], axis=1, inplace=True)
    df.dropna(subset=["license"], inplace=True)
    return df


class MapPipeline:

    def __init__(self, maps: list[maps.IMap]):
        self.maps = maps
        self.last_mapped_by_map: dict[str, list[tuple[int, str, str]]] = {}
        self.last_unresolved_by_map: dict[str, list[tuple[int, str]]] = {}

    def run(self, df: pd.DataFrame) -> tuple[set, set]:
        mapped_rows_indices = set()
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
                row_license = row["license"]
                result = license_map.map(row_license)

                if result is None:
                    next_unresolved_rows_indices.add(idx)
                    unresolved_by_this_map.append((idx, row_license))
                    log.info("Map %s did not map input '%s'", map_name, row_license)
                else:
                    mapped_rows_indices.add(idx)
                    mapped_by_this_map.append((idx, row_license, result))
                    log.info("Map %s mapped input '%s' to SPDX ID '%s'", map_name, row_license, result)

            self.last_mapped_by_map[map_name] = mapped_by_this_map
            self.last_unresolved_by_map[map_name] = unresolved_by_this_map
            unresolved_rows_indices = next_unresolved_rows_indices

        failed_rows_indices = unresolved_rows_indices

        return mapped_rows_indices, failed_rows_indices


def run_map_pipeline():
    df = load_dataset(100, True)
    mp = MapPipeline([maps.MapNA(), maps.MapExactID(), maps.MapExactMatch(), maps.MapFuzzyMatch()])
    mapped, failed = mp.run(df)

    failed_df = df[[x in failed for x in df["idx"]]]
    mapped_df = df[[x in mapped for x in df["idx"]]]
    failed_set = set(failed_df["license"])
    log.info("failed to map: %s", failed_set)


def save_top_distinct_licenses(num: int | None = None) -> None:
    """
    Develop a csv file with distinct license fields and their counts in the dataset.

    :param num: Size of sample of the dataset to load. Loads full dataset if None.
    """
    df = load_dataset(num, False)
    distinct_licenses = df["license"].value_counts()

    num_distinct = len(distinct_licenses)
    save_file_name = cvar.data_dir / f"top_{num_distinct}_popular_licenses.csv"
    distinct_licenses.to_csv(save_file_name)
    log.info("Saved top %s popular distinct licenses to %s", num_distinct, save_file_name)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run SPDX mapping pipeline utilities.")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["p", "s"],
        default="p",
        help="p: run mapping pipeline\ns: save a number of distinct license fields to file."
    )
    parser.add_argument(
        "-n",
        type=int,
        default=None,
        help="Sample size used by `s`.",
    )
    args = parser.parse_args(argv)

    match args.command:
        case "s":
            save_top_distinct_licenses(args.n)
        case "p":
            run_map_pipeline()


if __name__ == "__main__":
    main()
