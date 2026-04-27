"""Configuration variables."""

from pathlib import Path

project_dir = Path(__file__).parent.parent

data_dir = project_dir / "data"
logs_dir = project_dir / "logs"
pypi_data_dir = data_dir / "pypi" / "raw"
pypi_versions_dataset_path = pypi_data_dir / "pypi_versions_05-19-2025.csv"
spdx_license_list_dir = data_dir / "spdx-licenses"

resources_dir = project_dir / "resources"
