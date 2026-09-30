import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager


class Store:
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL, reason TEXT, details TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_state(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
            return json.loads(row["value"]) if row else default

    def set_state(self, key, value):
        with self.connect() as db:
            db.execute("INSERT INTO state VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value, separators=(",", ":"))))

    def operation(self, kind, status="pending", reason=None, details=None):
        now, op_id = time.time(), uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?,?)", (op_id, kind, status, now, now, reason,
                       json.dumps(details or {}, separators=(",", ":"))))
            db.execute("DELETE FROM operations WHERE status IN ('succeeded','failed','interrupted') AND id IN "
                       "(SELECT id FROM operations WHERE status IN ('succeeded','failed','interrupted') "
                       "ORDER BY updated DESC LIMIT -1 OFFSET 10000)")
        return op_id

    def update_operation(self, op_id, status, reason=None, details=None):
        with self.connect() as db:
            row = db.execute("SELECT details FROM operations WHERE id=?", (op_id,)).fetchone()
            merged = json.loads(row["details"]) if row else {}
            merged.update(details or {})
            db.execute("UPDATE operations SET status=?, updated=?, reason=COALESCE(?,reason), details=? WHERE id=?",
                       (status, time.time(), reason, json.dumps(merged, separators=(",", ":")), op_id))

    def operations(self):
        with self.connect() as db:
            return [dict(row) | {"details": json.loads(row["details"])} for row in
                    db.execute("SELECT * FROM operations ORDER BY created DESC LIMIT 100")]

    def interrupt_running(self, reason):
        with self.connect() as db:
            db.execute("UPDATE operations SET status='interrupted', updated=?, reason=? WHERE status IN ('pending','running')",
                       (time.time(), reason))

    def save_session(self, token_hash, csrf, expires):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO sessions VALUES(?,?,?)", (token_hash, csrf, expires))

    def session(self, token_hash, now=None):
        with self.connect() as db:
            row = db.execute("SELECT csrf, expires FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
            if not row or row["expires"] <= (now or time.time()):
                return None
            return dict(row)

    def delete_session(self, token_hash):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
