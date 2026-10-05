"""Each adapter parses the original polluted input through its own loader."""
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def split_rows(rows, parameters):
    # Only one header row is supported here. Additional header rows remain
    # in data: do not silently synthesize a successful multirow-header load.
    if parameters['header_lines'] and rows:
        return rows[0], rows[1:]
    return [], rows


def options(p):
    # A quote used as its own escape means doubled quotes, not a separate
    # escape prefix. Translate Pollock metadata to csv/Pandas arguments.
    quote = p['quotechar'] or None
    return dict(delimiter=p['delimiter'], quotechar=quote,
                escapechar=None if p['escapechar'] == quote else (p['escapechar'] or None),
                doublequote=p['escapechar'] == quote,
                quoting=csv.QUOTE_MINIMAL if quote else csv.QUOTE_NONE)


def python_csv(path, p):
    with path.open(encoding=p['encoding'], newline='') as file:
        reader = csv.reader(file, **options(p))
        for _ in range(p['preamble_lines']):
            next(reader, None)
        rows = list(reader)
    return split_rows(rows, p)


def clevercsv(path, p):
    import clevercsv as library
    with path.open(encoding=p['encoding'], newline='') as file:
        reader = library.reader(file, delimiter=p['delimiter'],
                                quotechar=p['quotechar'],
                                escapechar='' if p['escapechar'] == p['quotechar'] else p['escapechar'])
        for _ in range(p['preamble_lines']):
            next(reader, None)
        rows = list(reader)
    return split_rows(rows, p)


def pandas(path, p):
    import pandas as pd
    header = list(range(p['header_lines'])) if p['header_lines'] > 1 else (0 if p['header_lines'] else None)
    table = pd.read_csv(path, encoding=p['encoding'], skiprows=p['preamble_lines'],
                        header=header, dtype=str, keep_default_na=False,
                        index_col=None if p['header_lines'] > 1 else False,
                        on_bad_lines='error', **options(p))
    # Serialize Pandas' native MultiIndex column labels into Pollock's
    # space-joined header representation. No input rows are repaired.
    labels = [' '.join(map(str, col)) for col in table.columns] if p['header_lines'] > 1 else list(table.columns)
    return (labels if p['header_lines'] else []), table.values.tolist()


def sqlite(path, p):
    executable = os.getenv('SQLITE_EXE') or str(ROOT / 'tools/sqlite/sqlite3.exe')
    if not Path(executable).is_file():
        executable = shutil.which('sqlite3') or executable
    # SQLite's shell exposes field/record separators, but its CSV quote
    # and escape conventions are fixed. Keep those limitations observable.
    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / 'import.db'
        definitions = ', '.join(f'c{i} TEXT' for i in range(p['n_columns']))
        commands = (
            '.bail on\n'
            f'CREATE TABLE loaded_data ({definitions});\n'
            '.mode csv\n'
            f'.separator {json.dumps(p["delimiter"])} {json.dumps(p["row_delimiter"])}\n'
            f'.import --skip {p["preamble_lines"]} {json.dumps(path.resolve().as_posix())} loaded_data\n'
        )
        result = subprocess.run([executable, '-batch', str(database)], input=commands,
                                text=True, encoding='utf-8', capture_output=True, timeout=60)
        if result.stderr.strip():
            print(result.stderr.strip())
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or 'SQLite import failed')
        connection = sqlite3.connect(database)
        try:
            rows = [list(row) for row in connection.execute('SELECT * FROM loaded_data ORDER BY rowid')]
        finally:
            connection.close()
    return split_rows(rows, p)


def mysql(path, p):
    import mysql.connector
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    connection = mysql.connector.connect(
        host=os.getenv('MYSQL_HOST', 'localhost'), port=int(os.getenv('MYSQL_PORT', '3306')),
        user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'],
        database='pollock_benchmark', charset='utf8mb4', allow_local_infile=True,
        connection_timeout=15)
    try:
        cursor = connection.cursor()
        try:
            columns = [f'c{i}' for i in range(p['n_columns'])]
            # Text columns avoid conflating CSV parsing with SQL type conversion.
            # Column count comes from metadata, never expected cell contents.
            definitions = ', '.join(f'{name} LONGTEXT' for name in columns)
            cursor.execute('CREATE TEMPORARY TABLE loaded_data ('
                           f'load_order BIGINT AUTO_INCREMENT PRIMARY KEY, {definitions})')
            cursor.execute(
                'LOAD DATA LOCAL INFILE %s INTO TABLE loaded_data CHARACTER SET utf8mb4 '
                'FIELDS TERMINATED BY %s OPTIONALLY ENCLOSED BY %s ESCAPED BY %s '
                'LINES TERMINATED BY %s IGNORE %s LINES '
                f'({", ".join(columns)})',
                (path.resolve().as_posix(), p['delimiter'], p['quotechar'],
                 p['escapechar'], p['row_delimiter'], p['preamble_lines']))
            # Capture warnings before the SELECT replaces the statement diagnostics.
            cursor.execute('SHOW WARNINGS')
            for level, code, message in cursor.fetchall():
                print(f'{level} {code}: {message}')
            cursor.execute(f'SELECT {", ".join(columns)} FROM loaded_data ORDER BY load_order')
            rows = [list(row) for row in cursor.fetchall()]
        finally:
            cursor.close()
    finally:
        connection.close()
    return split_rows(rows, p)


LOADERS = dict(python_csv=python_csv, pandas=pandas, clevercsv=clevercsv, sqlite=sqlite, mysql=mysql)
