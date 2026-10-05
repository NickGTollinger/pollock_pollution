# Baseline adapter for the supplied clean CSV using CleverCSV.
from pathlib import Path

import clevercsv


def load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = clevercsv.reader(
            file,
            delimiter=",",
            quotechar='"',
            escapechar="",
        )
        header = next(reader, [])
        records = list(reader)

    return header, records