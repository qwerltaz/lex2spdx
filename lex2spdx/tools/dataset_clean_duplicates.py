import pandas as pd

from lex2spdx import cvar


def main():
    df = pd.read_csv(cvar.pypi_versions_dataset_path)

    # Also drop names (it's a versions dataset with multiple entries for the same package, one for each version).
    # Not important for this project.
    df_no_duplicates = df.drop_duplicates(subset=["name"])
    df_no_duplicates = df_no_duplicates.drop_duplicates(subset=["license"])
    df_no_duplicates.dropna(subset=["license"], inplace=True)
    print(f"Original dataset size: {len(df)}")  # 7693395
    print(f"Dataset size after removing duplicates: {len(df_no_duplicates)}")  # 17689

    df_no_duplicates.to_csv(cvar.pypi_unique_licenses_dataset_path, index=False)


if __name__ == '__main__':
    main()
