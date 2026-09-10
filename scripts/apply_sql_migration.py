"""Apply one checked-in SQL migration using the configured DATABASE_URL."""
import argparse
from pathlib import Path

from sqlalchemy import text

from backend.src.db.database import engine


MIGRATIONS = (Path(__file__).resolve().parents[1] / "backend" / "src" / "db" / "migrations").resolve()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("migration", help="Migration filename, for example 003_add_auth.sql")
    args = parser.parse_args()
    path = (MIGRATIONS / args.migration).resolve()
    if path.parent != MIGRATIONS or not path.is_file() or path.suffix.lower() != ".sql":
        raise SystemExit("Migration must be an existing .sql file in the migrations directory.")

    statements = [statement.strip() for statement in path.read_text(encoding="utf-8").split(";") if statement.strip()]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    print(f"Applied {path.name} ({len(statements)} statements).")


if __name__ == "__main__":
    main()
