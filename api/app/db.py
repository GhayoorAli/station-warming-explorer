import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/climate"

_pool: ConnectionPool | None = None


def open_pool(dsn: str | None = None) -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            dsn or os.environ.get("DATABASE_URL", DEFAULT_DSN),
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def fetch_all(sql: str, params: dict | tuple = ()) -> list[dict]:
    with open_pool().connection() as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: dict | tuple = ()) -> dict | None:
    with open_pool().connection() as conn:
        return conn.execute(sql, params).fetchone()
