import argparse

import pandas as pd

from lex2spdx import cvar
from lex2spdx import logger
from lex2spdx.map import load_dataset

_log = logger.get()


def save_top_distinct_licenses(num: int | None = None, truncate_licenses: bool = False,
                               text_only: bool = False) -> None:
    """
    Develop a csv file with distinct license fields and their counts in the dataset.

    :param num: Size of sample of the dataset to load. Loads full dataset if None.
    :param truncate_licenses: Whether to truncate license texts to 100 characters.
    :param text_only: Whether to save only the license texts instead of together with counts.
    """
    try:
        df = load_dataset(num, False, cvar.pypi_unique_licenses_dataset_path, drop_duplicate_licenses=False)
    except FileNotFoundError:
        df = load_dataset(num, False, drop_duplicate_licenses=False)

    distinct_licenses = df["license"].value_counts()

    num_distinct = len(distinct_licenses)
    save_file_name = cvar.data_dir / f"top_{num_distinct}_popular_licenses"

    if truncate_licenses:
        distinct_licenses = distinct_licenses.rename(lambda x: x[:100] + "..." if len(x) > 100 else x)
        save_file_name = save_file_name.with_name(save_file_name.stem + "_truncated")

    if text_only:
        distinct_licenses = distinct_licenses.index
        save_file_name = save_file_name.with_name(save_file_name.stem + "_text_only")

    save_file_name = save_file_name.with_suffix(".csv")

    distinct_licenses = pd.DataFrame(distinct_licenses)
    distinct_licenses.to_csv(save_file_name, index=False)
    _log.info("Saved top %s popular distinct licenses to %s", num_distinct, save_file_name)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-n",
        type=int,
        default=None,
        help="Sample size used by `s`.",
    )
    parser.add_argument(
        "-x",
        action="store_true",
        help="Truncate license texts.",
    )
    parser.add_argument(
        "-t",
        action="store_true",
        help="Text only, without counts.",
    )
    args = parser.parse_args(argv)

    save_top_distinct_licenses(args.n, args.x, args.t)


if __name__ == '__main__':
    main()
