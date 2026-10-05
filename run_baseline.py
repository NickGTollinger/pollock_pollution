# Clean-file comparison only. Configured pollution runs use benchmark/adapters.py.
import csv
from pathlib import Path

from loaders.python_csv import load_csv as load_python
from loaders.pandas_csv import load_csv as load_pandas
from loaders.clevercsv_csv import load_csv as load_clevercsv
from loaders.sqlite_csv import load_csv as load_sqlite
from loaders.mysql_csv import load_csv as load_mysql

project_dir = Path(__file__).resolve().parent
source_path = project_dir / "data" / "clean" / "source.csv"

loaders = {
    "python_csv": load_python,
    "pandas": load_pandas,
    "clevercsv": load_clevercsv,
    "sqlite": load_sqlite,
    "mysql": load_mysql,
}

def main():
    # Temporary comparison reference for the clean-file baseline.
    expected_header, expected_records = load_python(source_path)

    for name, loader in loaders.items():
        print(f"\n{name}")

        try:
            header, records = loader(source_path)

            output_path = project_dir / "results" / name / "source.csv"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Use a common CSV format to export each loader's result.
            with output_path.open(
                "w", encoding="utf-8", newline=""
            ) as file:
                writer = csv.writer(file)
                writer.writerow(header)
                writer.writerows(records)

            print(f"Header columns: {len(header)}")
            print(f"Data records: {len(records)}")
            print(f"Record widths: {sorted({len(row) for row in records})}")
            print(f"Header matches reference: {header == expected_header}")
            print(f"Records match reference: {records == expected_records}")

        except Exception as error:
            # Let the remaining loaders run if one fails.
            print(f"FAILED: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()