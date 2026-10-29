import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

_pool = None


def init_pool(app):
    global _pool
    _pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        host=os.environ.get("PG_HOST", "postgres"),
        port=int(os.environ.get("PG_PORT", 5432)),
        dbname=os.environ.get("PG_DB", "rh_target"),
        user=os.environ.get("PG_USER", "api_reader"),
        password=os.environ.get("PG_PASSWORD", "api_reader_pwd"),
        options="-c default_transaction_read_only=on",
    )
    app.logger.info("Pool PostgreSQL initialise")


def close_pool():
    if _pool:
        _pool.closeall()


@contextmanager
def get_cursor():
    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
