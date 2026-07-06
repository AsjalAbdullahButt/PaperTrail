"""Standalone schema bootstrap.

Run from the backend/ directory with the venv active:

    python create_tables.py

Creates the `papertrail` database (if missing) and all tables (if missing),
then prints the tables it can see.
"""
from sqlalchemy import inspect

from app.database import engine, init_db


def main() -> None:
    init_db()
    tables = inspect(engine).get_table_names()
    print("Database ready. Tables:", ", ".join(sorted(tables)) or "(none)")


if __name__ == "__main__":
    main()
