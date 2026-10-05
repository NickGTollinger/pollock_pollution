# Creates the local benchmark database and enables native local file imports.
import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

connection = mysql.connector.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.environ["MYSQL_USER"],
    password=os.environ["MYSQL_PASSWORD"],
)

try:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "CREATE DATABASE IF NOT EXISTS pollock_benchmark "
            "CHARACTER SET utf8mb4"
        )
        # One-time local server setup: requires administrative privileges and
        # changes the server setting until restart unless persisted separately.
        cursor.execute("SET GLOBAL local_infile = ON")
        print("MySQL benchmark database and local imports are ready.")
    finally:
        cursor.close()
finally:
    connection.close()