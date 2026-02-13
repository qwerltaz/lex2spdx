"""Pipeline runner for mapping PyPI packages to SPDX licenses."""

import pandas as pd

import cvar
from maps import map_spdx


def load_dataset(sample_size: int | None) -> pd.DataFrame:
    """
    :param sample_size: The number of rows to load instead of full dataset. If None, load the full dataset.
    :return: The loaded dataset.
    """
    df = pd.read_csv(cvar.pypi_versions_dataset_path, low_memory=False, nrows=sample_size)
    df.drop(["Unnamed: 0", "idx"], axis=1, inplace=True)
    return df


if __name__ == "__main__":
    map_spdx.MapExactMatch().map("MIT License")