"""Check generated artifacts and representative pollution properties."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def read_rows(path):
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))

def main():
    cases = json.loads((ROOT / "data/pollock_manifest.json").read_text())
    polluted = ROOT / "data/polluted/pollock"
    expected = ROOT / "data/expected/pollock"
    parameters = ROOT / "data/parameters/pollock"
    names = [case["filename"] for case in cases]
    assert len(names) == len(set(names)), "Duplicate cases"
    for name in names:
        assert (polluted / name).is_file(), name
        assert (expected / name).is_file(), name
        metadata = json.loads((parameters / (name + "_parameters.json")).read_text())
        assert "header_lines" in metadata, name
        read_rows(expected / name)
    # These fixture checks intentionally assume the supplied 84-by-9 source.
    # Changing datasets requires updating these checks and generation assumptions.
    source_rows = read_rows(ROOT / "data/clean/source.csv")
    assert read_rows(expected / "source.csv") == source_rows
    assert len(source_rows) == 84 and all(len(row) == 9 for row in source_rows)
    assert (polluted / "file_no_payload.csv").read_bytes() == b""
    assert (expected / "file_no_payload.csv").read_bytes() == b""
    assert not (polluted / "file_no_trailing_newline.csv").read_bytes().endswith(b"\n")
    assert (polluted / "file_double_trailing_newline.csv").read_bytes().endswith(b"\r\n\r\n")
    assert read_rows(expected / "file_no_header.csv") == source_rows[1:]
    assert read_rows(expected / "file_header_only.csv") == source_rows[:1]
    assert read_rows(expected / "file_one_data_row.csv") == source_rows[:2]
    print(f"Verified {len(cases)} complete artifact sets and representative content/newline checks.")

if __name__ == "__main__":
    main()
