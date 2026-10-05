# Baseline adapter for the supplied clean CSV; not the configured pollution adapter.
import csv
from pathlib import Path


def load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    """Read the first row as the header and the remaining rows as data."""
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader, [])
        records = list(reader)

    return header, records