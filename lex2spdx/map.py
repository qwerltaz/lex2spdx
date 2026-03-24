"""Pipeline runner for mapping PyPI packages to SPDX licenses."""

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

    df.drop(["Unnamed: 0", "idx"], axis=1, inplace=True, errors="ignore")
    df.dropna(subset=["license"], inplace=True)
    return df


class MapPipeline:

    def __init__(self, maps: list[maps.IMap]):
        self.maps = maps

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        fail_maps = pd.DataFrame()
        success_maps = pd.DataFrame()

        for map in self.maps:
            for row in df:
                license = row["licenses"]
                # TODO release successfully mapped fields so next maps don't even see them.
                result = map.map(license)


def main():
    df = load_dataset(1000, True)
    mp = MapPipeline([maps.MapExactID()])
    mp.run(df)


if __name__ == "__main__":
    main()
