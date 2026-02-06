"""Pipeline runner for mapping PyPI packages to SPDX licenses."""

import pandas as pd

import cvar


def load_dataset() -> pd.DataFrame:
    df = pd.read_csv(cvar.pypi_versions_dataset_path)
    return df
