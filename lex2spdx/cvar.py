"""Configuration variables."""

from pathlib import Path

project_dir = Path(__file__).parent.parent

data_dir = project_dir / "data"
pypi_data_dir = data_dir / "pypi"
pypi_data_raw_dir = pypi_data_dir / "raw"
pypi_versions_dataset_path = pypi_data_raw_dir / "pypi_versions_05-19-2025.csv"
pypi_unique_licenses_dataset_dir = pypi_data_dir / "unique-licenses"
pypi_unique_licenses_dataset_path = pypi_unique_licenses_dataset_dir / "versions.csv"
spdx_license_list_dir = data_dir / "spdx-licenses"

resources_dir = project_dir / "resources"
logs_dir = project_dir / "logs"
