#!/usr/bin/env python3
"""Idempotent PostgreSQL migration runner.

Applies ``migrations/V*.sql`` in filename order, each in its own transaction,
recording applied files in ``public.schema_migrations``. Re-running is safe:
already-applied files are skipped. Pure-Python (pg8000) so it needs no libpq.

Usage:
    python Database/PostgreSQL/apply_migrations.py

Connection is read from PG_HOST / PG_PORT / PG_USER / PG_PASSWORD / PG_DATABASE
(defaults match .env.example).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pg8000.dbapi

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _connect() -> "pg8000.dbapi.Connection":
    return pg8000.dbapi.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")),
        user=os.getenv("PG_USER", "epi_os"),
        password=os.getenv("PG_PASSWORD", "epi_os"),
        database=os.getenv("PG_DATABASE", "epi_os"),
    )


def _ensure_ledger(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS public.schema_migrations ("
        "  filename TEXT PRIMARY KEY,"
        "  applied_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    conn.commit()


def _applied(conn) -> set[str]:
    cur = conn.cursor()
    cur.execute("SELECT filename FROM public.schema_migrations")
    return {row[0] for row in cur.fetchall()}


def main() -> int:
    files = sorted(MIGRATIONS_DIR.glob("V*.sql"))
    if not files:
        print("no migrations found")
        return 0

    conn = _connect()
    try:
        _ensure_ledger(conn)
        done = _applied(conn)
        for path in files:
            if path.name in done:
                print(f"skip   {path.name}")
                continue
            sql = path.read_text()
            cur = conn.cursor()
            try:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO public.schema_migrations (filename) VALUES (%s)",
                    (path.name,),
                )
                conn.commit()
                print(f"apply  {path.name}")
            except Exception:
                conn.rollback()
                raise
    finally:
        conn.close()
    print("migrations up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
