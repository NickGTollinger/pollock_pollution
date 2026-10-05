# Baseline adapter for the supplied clean CSV; preserve strings and empty cells.
from pathlib import Path

import pandas as pd


def load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    # Keep values as strings and preserve empty cells.
    table = pd.read_csv(
        path,
        header=0,
        dtype=str,
        keep_default_na=False,
    )

    return table.columns.tolist(), table.values.tolist()