import sqlite3
from contextlib import contextmanager

class SQLiteDatabase:
    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        # check_same_thread=False 是為了讓不同層級的調用能共用連線
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    @contextmanager
    def transaction(self):
        """這是遺失的關鍵：提供資料庫事務管理"""
        try:
            yield self._conn
            self._conn.commit()
        except Exception as e:
            self._conn.rollback()
            raise e

    def initialize_schema(self):
        """核心建表 SQL - 確保測試環境有表可用"""
        schema = """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            tenant_id TEXT,
            queue_id TEXT,
            state TEXT,
            payload_json TEXT,
            priority INTEGER,
            available_at TEXT,
            attempt_count INTEGER,
            max_attempts INTEGER,
            current_lease_id TEXT,
            current_worker_id TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS leases (
            lease_id TEXT PRIMARY KEY,
            lease_token TEXT,
            tenant_id TEXT,
            queue_id TEXT,
            job_id TEXT,
            worker_id TEXT,
            state TEXT,
            leased_at TEXT,
            lease_until TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            tenant_id TEXT,
            state TEXT,
            last_heartbeat_at TEXT,
            updated_at TEXT
        );
        """
        self._conn.executescript(schema)
        print("✅ Database tables created successfully!")
