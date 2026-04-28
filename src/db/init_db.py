"""
DB 초기화 스크립트.

사용법:
    python -m src.db.init_db
"""

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str = None) -> sqlite3.Connection:
    """SQLite 연결 반환. WAL 모드 + foreign key 활성화."""
    db_path = db_path or os.getenv("DB_PATH", "data/lol_coach.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row   # dict처럼 컬럼명으로 접근 가능
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = None):
    """schema.sql을 읽어 테이블 생성."""
    db_path = db_path or os.getenv("DB_PATH", "data/lol_coach.db")
    logger.info(f"DB 초기화: {db_path}")

    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)

    with conn:
        conn.executescript(schema)

    logger.info("테이블 생성 완료")
    conn.close()


if __name__ == "__main__":
    init_db()
