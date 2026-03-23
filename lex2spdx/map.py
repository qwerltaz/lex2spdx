"""Pipeline runner for mapping PyPI packages to SPDX licenses."""

import pandas as pd

try:
    from . import cvar
    from . import maps
except ImportError:
    import cvar
    import maps


def load_dataset(sample_size: int | None = None) -> pd.DataFrame:
    """
    :param sample_size: The number of rows to load instead of full dataset. If None, load the full dataset.
    :return: The loaded dataset.
    """
    df = pd.read_csv(cvar.pypi_versions_dataset_path, low_memory=False, nrows=sample_size)
    df.drop(["Unnamed: 0", "idx"], axis=1, inplace=True)
    df.dropna(subset=["license"], inplace=True)
    return df


class MapPipeline:

    def __init__(self, maps: tuple[maps.IMap]):
        self.maps = maps

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        for map in self.maps:
            for license_field in df["license"]:
                print(f"true: {license_field}, mapped: {map.map(license_field)}")


if __name__ == "__main__":
    df = load_dataset(100)
    mp = MapPipeline((maps.MapSubstring(),))
    mp.run(df)
