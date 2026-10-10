"""Copy every Hermod table from one database to another, keeping ids (so Telegram links and
references survive). Used to move the local SQLite data into Supabase.

    python -m hermod.db.copy --to "postgresql://postgres.<ref>:<password>@<host>:5432/postgres"
    python -m hermod.db.copy --from sqlite:///./hermod.db --to ... --replace

The target must be empty unless --replace is given (which deletes its Hermod rows first).
"""
import argparse
import sys

from sqlalchemy import func, select, text
from sqlmodel import SQLModel

from hermod.db import models  # noqa: F401  (register tables)
from hermod.db.session import _make_engine, add_missing_columns, lock_down_supabase_tables


def copy_all(src_url: str, dst_url: str, replace: bool = False) -> dict[str, int]:
    src, dst = _make_engine(src_url), _make_engine(dst_url)
    add_missing_columns(src)  # an older source DB may lack newer columns
    SQLModel.metadata.create_all(dst)
    add_missing_columns(dst)
    tables = SQLModel.metadata.sorted_tables  # parents before children

    with dst.begin() as conn:
        rows = {t.name: conn.execute(select(func.count()).select_from(t)).scalar() for t in tables}
        if any(rows.values()):
            if not replace:
                raise SystemExit(f"Target isn't empty ({rows}); pass --replace to overwrite it")
            for t in reversed(tables):
                conn.execute(t.delete())

    copied = {}
    with src.connect() as s, dst.begin() as d:
        for t in tables:
            data = [dict(r._mapping) for r in s.execute(select(t).order_by(*t.primary_key))]
            if data:
                d.execute(t.insert(), data)
            copied[t.name] = len(data)
        if dst.dialect.name == "postgresql":
            # Inserting explicit ids doesn't advance the id sequences; move them past the max.
            for t in tables:
                d.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('\"{t.name}\"', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM \"{t.name}\"), 0) + 1, false)"))
    if dst.dialect.name == "postgresql":
        lock_down_supabase_tables(dst)
    return copied


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="src", default="sqlite:///./hermod.db")
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--replace", action="store_true", help="Delete existing rows in the target")
    a = ap.parse_args()
    copied = copy_all(a.src, a.dst, a.replace)
    print("Copied:", ", ".join(f"{k} {v}" for k, v in copied.items()))


if __name__ == "__main__":
    sys.exit(main())
