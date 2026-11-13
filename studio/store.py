"""User-scoped workspace records; short transactions and optimistic revisions."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect():
    path = Path(os.environ.get("STUDIO_DB", ".runtime/studio.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""CREATE TABLE IF NOT EXISTS records (
       id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
       body TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
       updated TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))""")
    db.execute("""CREATE TABLE IF NOT EXISTS imports (
       key TEXT PRIMARY KEY, owner TEXT NOT NULL, state TEXT NOT NULL, payload TEXT NOT NULL)""")
    db.execute("""CREATE TABLE IF NOT EXISTS revisions (
       record_id TEXT NOT NULL, owner TEXT NOT NULL, revision INTEGER NOT NULL,
       body TEXT NOT NULL, created TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
       PRIMARY KEY(record_id,revision))""")
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def save(owner, kind, title, body, record_id=None, revision=None):
    with connect() as db:
        encoded = json.dumps(body, ensure_ascii=False)
        if record_id:
            previous = db.execute(
                "SELECT * FROM records WHERE id=? AND owner=?", (record_id, owner)
            ).fetchone()
            if previous:
                db.execute(
                    "INSERT OR IGNORE INTO revisions(record_id,owner,revision,body) VALUES(?,?,?,?)",
                    (record_id, owner, previous["revision"], previous["body"]),
                )
            changed = db.execute(
                """UPDATE records SET title=?, body=?, revision=revision+1,
                updated=strftime('%Y-%m-%dT%H:%M:%fZ','now')
                WHERE id=? AND owner=? AND kind=? AND revision=?""",
                (title, encoded, record_id, owner, kind, revision),
            ).rowcount
            if not changed:
                raise ValueError("记录已改变或不可访问，请重新打开后保存")
        else:
            record_id = uuid.uuid4().hex
            db.execute(
                "INSERT INTO records(id,owner,kind,title,body) VALUES(?,?,?,?,?)",
                (record_id, owner, kind, title, encoded),
            )
        latest = db.execute(
            "SELECT revision,body FROM records WHERE id=? AND owner=?", (record_id, owner)
        ).fetchone()
        db.execute(
            "INSERT OR IGNORE INTO revisions(record_id,owner,revision,body) VALUES(?,?,?,?)",
            (record_id, owner, latest["revision"], latest["body"]),
        )
    return get(owner, record_id)


def get(owner, record_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM records WHERE owner=? AND id=?", (owner, record_id)
        ).fetchone()
    if row is None:
        raise KeyError("记录不存在或不可访问")
    value = dict(row)
    value["body"] = json.loads(value["body"])
    return value


def listing(owner, kind):
    with connect() as db:
        rows = db.execute(
            "SELECT id,title,revision,updated FROM records WHERE owner=? AND kind=? ORDER BY updated DESC LIMIT 100",
            (owner, kind),
        ).fetchall()
    return [dict(row) for row in rows]
