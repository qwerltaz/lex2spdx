"""Configuration variables."""

from pathlib import Path

data_dir = Path("../data")
pypi_data_dir = data_dir / "raw" / "pypi"
pypi_versions_dataset_path = pypi_data_dir / "pypi_versions_05-19-2025.csv"
