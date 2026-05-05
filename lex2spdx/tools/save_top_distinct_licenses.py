import argparse

from lex2spdx import cvar
from lex2spdx import logger
from lex2spdx.map import load_dataset

_log = logger.get()


def save_top_distinct_licenses(num: int | None = None) -> None:
    """
    Develop a csv file with distinct license fields and their counts in the dataset.

    :param num: Size of sample of the dataset to load. Loads full dataset if None.
    """
    df = load_dataset(num, False)
    distinct_licenses = df["license"].value_counts()

    num_distinct = len(distinct_licenses)
    save_file_name = cvar.data_dir / f"top_{num_distinct}_popular_licenses.csv"
    distinct_licenses.to_csv(save_file_name)
    _log.info("Saved top %s popular distinct licenses to %s", num_distinct, save_file_name)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Run SPDX mapping pipeline utilities.")

    parser.add_argument(
        "-n",
        type=int,
        default=None,
        help="Sample size used by `s`.",
    )
    args = parser.parse_args(argv)

    save_top_distinct_licenses(args.n)
