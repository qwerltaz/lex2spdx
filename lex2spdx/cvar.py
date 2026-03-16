"""Configuration variables."""

from pathlib import Path

data_dir = Path(__file__).parent.parent / "data"
pypi_data_dir = data_dir / "pypi" / "raw"
pypi_versions_dataset_path = pypi_data_dir / "pypi_versions_05-19-2025.csv"
spdx_license_list_dir = data_dir / "spdx-licenses"
