"""Pipeline runner for mapping PyPI packages to SPDX licenses."""
import json
import random
import pandas as pd

try:
    from . import cvar
    from . import maps
except ImportError:
    import cvar
    import maps


def load_dataset(sample_size: int | None = None, random_start: bool = False) -> pd.DataFrame:
    """
    :param sample_size: The number of rows to load instead of full dataset. If None, load the full dataset.
    :param random_start: If True, start sampling at random position in dataset. Only used if sample_size is not None.
    :return: The loaded dataset.
    """
    # About 10% of the true dataset size, for faster random sampling.
    alleged_dataset_size = 200000

    if sample_size > alleged_dataset_size:
        sample_size = alleged_dataset_size

    if sample_size is not None and random_start:
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

    def run(self, df: pd.DataFrame) -> tuple[set, set]:
        mapped_rows_indices = set()
        failed_rows_indices = set()

        for license_map in self.maps:
            for _, row in df.iterrows():
                if row["idx"] in mapped_rows_indices:
                    continue

                row_license = row["license"]
                result = license_map.map(row_license)
                if result is None:
                    failed_rows_indices.add(row["idx"])
                else:
                    mapped_rows_indices.add(row["idx"])

        return mapped_rows_indices, failed_rows_indices


def main():
    df = load_dataset(3000, True)
    mp = MapPipeline([maps.MapExactID(), maps.MapSubstring()])
    mapped, failed = mp.run(df)

    failed_df = df[[x in failed for x in df["idx"]]]
    mapped_df = df[[x in mapped for x in df["idx"]]]
    failed_set = set(failed_df["license"])
    print("failed to map: ", failed_set)
    with open("failed_to_map.json", "w", encoding="utf-8") as f:
        json.dump(list(failed_set), f, indent=4)


if __name__ == "__main__":
    main()
