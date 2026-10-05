# Checks Python dependencies and a MySQL connection; does not check the SQLite CLI.
import csv
import sqlite3

import clevercsv
import mysql.connector
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

print("Python csv: available")
print(f"Pandas: {pd.__version__}")
print(f"CleverCSV: {clevercsv.__version__}")
print(f"SQLite: {sqlite3.sqlite_version}")

# Verify that the local MySQL server accepts our connection.
connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PASSWORD"],
)

try:
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT VERSION()")
        print(f"MySQL: {cursor.fetchone()[0]}")
    finally:
        cursor.close()
finally:
    connection.close()

print("Setup checks passed.")