# Baseline native SQLite shell import; Python retrieves the already parsed rows.
import sqlite3
import subprocess
import tempfile
from pathlib import Path


def load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    project_dir = Path(__file__).resolve().parents[1]
    sqlite_exe = project_dir / "tools" / "sqlite" / "sqlite3.exe"
    source_path = path.resolve()

    if not sqlite_exe.is_file():
        raise FileNotFoundError(f"SQLite executable missing: {sqlite_exe}")

    if not source_path.is_file():
        raise FileNotFoundError(f"Input file missing: {source_path}")

    # Forward slashes work on Windows and avoid backslash escaping
    # in SQLite's command-line commands.
    import_path = source_path.as_posix()

    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "baseline.db"

        commands = (
            ".bail on\n"
            f'.import --csv "{import_path}" loaded_data\n'
        )

        # SQLite itself parses and imports the CSV.
        result = subprocess.run(
            [str(sqlite_exe), "-batch", str(database_path)],
            input=commands,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or "SQLite import failed."
            )

        # Keep warnings visible even if SQLite returns success.
        if result.stderr.strip():
            print(f"SQLite import messages:\n{result.stderr.strip()}")

        # Python only retrieves rows already parsed by SQLite.
        connection = sqlite3.connect(database_path)

        try:
            cursor = connection.execute(
                "SELECT * FROM loaded_data ORDER BY rowid"
            )
            header = [column[0] for column in cursor.description]
            records = [list(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    return header, records