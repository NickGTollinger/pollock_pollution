# Baseline native MySQL import with nine text columns for this specific fixture.
import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv


def load_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    project_dir = Path(__file__).resolve().parents[1]
    load_dotenv(project_dir / ".env")

    source_path = path.resolve()

    if not source_path.is_file():
        raise FileNotFoundError(f"Input file missing: {source_path}")

    # Baseline only: identify the clean file's newline sequence.
    # This reads bytes but does not parse its CSV fields.
    file_bytes = source_path.read_bytes()
    newline = "\r\n" if b"\r\n" in file_bytes else "\n"

    connection = mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database="pollock_benchmark",
        charset="utf8mb4",
        allow_local_infile=True,
    )

    try:
        cursor = connection.cursor()

        try:
            # Generic column names let MySQL import the header itself.
            column_names = [f"c{i}" for i in range(1, 10)]
            definitions = ", ".join(
                f"{name} LONGTEXT" for name in column_names
            )

            # A temporary table disappears when the connection closes.
            cursor.execute(
                "CREATE TEMPORARY TABLE loaded_data ("
                "load_order BIGINT AUTO_INCREMENT PRIMARY KEY, "
                f"{definitions})"
            )

            # MySQL parses every row, including the header.
            # Double quotes handle enclosure and doubled quote escapes.
            cursor.execute(
                """
                LOAD DATA LOCAL INFILE %s
                INTO TABLE loaded_data
                CHARACTER SET utf8mb4
                FIELDS TERMINATED BY ','
                OPTIONALLY ENCLOSED BY '"'
                ESCAPED BY '"'
                LINES TERMINATED BY %s
                (c1, c2, c3, c4, c5, c6, c7, c8, c9)
                """,
                (source_path.as_posix(), newline),
            )

            # Display import warnings before issuing another query.
            cursor.execute("SHOW WARNINGS")
            for level, code, message in cursor.fetchall():
                print(f"MySQL {level} {code}: {message}")

            cursor.execute(
                f"SELECT {', '.join(column_names)} "
                "FROM loaded_data ORDER BY load_order"
            )
            rows = [list(row) for row in cursor.fetchall()]

        finally:
            cursor.close()

    finally:
        connection.close()

    if not rows:
        return [], []

    return rows[0], rows[1:]