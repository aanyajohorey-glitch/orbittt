# Saves ORBIT's data in a small SQLite database.
# On my laptop everything goes into data/orbit.db.
# On Streamlit Cloud every visitor gets their own temporary database,
# so nobody can see anyone else's journal.

import json
import os
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path

LOCAL_DB = Path(__file__).parent / "data" / "orbit.db"
SESSION_FOLDER = Path(tempfile.gettempdir()) / "orbit_sessions"

TABLES = """
CREATE TABLE IF NOT EXISTS entries (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, source TEXT,
    text TEXT, primary_emotion TEXT, primary_score REAL, emotions TEXT, world TEXT, demo INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS collection (id TEXT PRIMARY KEY, world TEXT, source TEXT, intent TEXT,
    prompt TEXT, constraint_text TEXT, note TEXT, saved_at TEXT);
CREATE TABLE IF NOT EXISTS wellbeing (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, tool TEXT,
    before INTEGER, after INTEGER, demo INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, rating INTEGER,
    comment TEXT);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS ratings (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, kind TEXT,
    target TEXT, value INTEGER);
CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, kind TEXT,
    title TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS corrections (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, text TEXT,
    predicted TEXT, corrected TEXT, raw_scores TEXT, source TEXT);
"""
ALL_TABLES = ["entries", "collection", "wellbeing", "feedback", "ratings", "corrections", "notes", "settings"]


def on_cloud():
    # Streamlit Cloud runs apps from /mount/src/
    if os.environ.get("ORBIT_STORAGE") == "session":
        return True
    return str(Path(__file__).resolve()).replace("\\", "/").startswith("/mount/src/")


def session_id():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx().session_id
    except Exception:
        return "no-session"


def db_path():
    if on_cloud():
        return SESSION_FOLDER / f"{session_id()}.db"
    return LOCAL_DB


def personal_model_path():
    if on_cloud():
        return SESSION_FOLDER / f"{session_id()}_personal.npz"
    return Path(__file__).parent / "data" / "model" / "orbit_head_personal.npz"


def now():
    return datetime.now().isoformat(timespec="seconds")


def run(sql, values=()):
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute(sql, values).fetchall()]
    conn.commit()
    conn.close()
    return rows


def setup():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if on_cloud():
        # delete other visitors' databases that are older than a day
        for old in SESSION_FOLDER.glob("*.db"):
            try:
                if time.time() - old.stat().st_mtime > 24 * 3600:
                    old.unlink()
            except OSError:
                pass
    conn = sqlite3.connect(path)
    conn.executescript(TABLES)
    conn.commit()
    conn.close()


# settings
def get_setting(key, default=None):
    rows = run("SELECT value FROM settings WHERE key = ?", (key,))
    if rows:
        return rows[0]["value"]
    return default


def set_setting(key, value):
    run("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))


def journal_on():
    return get_setting("journal_on", "1") == "1"


# journal entries
def add_entry(source, text, emotions, world, primary, created_at=None, demo=False):
    score = dict(emotions).get(primary, emotions[0][1])
    run("INSERT INTO entries (created_at, source, text, primary_emotion, primary_score, emotions, world, demo) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (created_at or now(), source, text, primary, score, json.dumps(emotions), world, int(demo)))


def get_entries():
    rows = run("SELECT * FROM entries ORDER BY created_at")
    for row in rows:
        row["emotions"] = [tuple(pair) for pair in json.loads(row["emotions"])]
    return rows


def delete_entry(entry_id):
    run("DELETE FROM entries WHERE id = ?", (entry_id,))


# saved worlds
def add_world(item):
    run("INSERT OR REPLACE INTO collection VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (item["id"], item["world"], item["source"], item["intent"], item["prompt"], item["constraint"],
         item["note"], item["saved_at"]))


def get_worlds():
    rows = run("SELECT * FROM collection ORDER BY rowid")
    for row in rows:
        row["constraint"] = row.pop("constraint_text")
    return rows


def remove_world(item_id):
    run("DELETE FROM collection WHERE id = ?", (item_id,))


# mood before / after a tool
def add_wellbeing(tool, before, after, created_at=None, demo=False):
    run("INSERT INTO wellbeing (created_at, tool, before, after, demo) VALUES (?, ?, ?, ?, ?)",
        (created_at or now(), tool, before, after, int(demo)))


def get_wellbeing():
    return run("SELECT * FROM wellbeing ORDER BY created_at")


def add_feedback(rating, comment):
    run("INSERT INTO feedback (created_at, rating, comment) VALUES (?, ?, ?)", (now(), rating, comment))


def get_feedback():
    return run("SELECT * FROM feedback ORDER BY created_at")


# thumbs and star ratings
def add_rating(kind, target, value):
    rows = run("INSERT INTO ratings (created_at, kind, target, value) VALUES (?, ?, ?, ?) RETURNING id",
               (now(), kind, target, value))
    return rows[0]["id"]


def delete_rating(rating_id):
    run("DELETE FROM ratings WHERE id = ?", (rating_id,))


def get_ratings():
    return run("SELECT * FROM ratings ORDER BY created_at")


# notes: reach out drafts, letters
def add_note(kind, title, text, created_at=None):
    run("INSERT INTO notes (created_at, kind, title, text) VALUES (?, ?, ?, ?)", (created_at or now(), kind, title, text))


def get_notes(kind):
    return run("SELECT * FROM notes WHERE kind = ? ORDER BY created_at DESC", (kind,))


def delete_note(note_id):
    run("DELETE FROM notes WHERE id = ?", (note_id,))


# teach orbit corrections
def add_correction(text, predicted, corrected, scores, source):
    run("INSERT INTO corrections (created_at, text, predicted, corrected, raw_scores, source) VALUES (?, ?, ?, ?, ?, ?)",
        (now(), text, predicted, corrected, json.dumps(scores), source))


def get_corrections():
    rows = run("SELECT * FROM corrections ORDER BY created_at")
    for row in rows:
        row["raw_scores"] = json.loads(row["raw_scores"])
    return rows


def delete_corrections():
    run("DELETE FROM corrections")
    if personal_model_path().exists():
        personal_model_path().unlink()


# export, import and delete
def export_data():
    data = {"orbit_export": 1, "exported_at": now()}
    for table in ALL_TABLES:
        data[table] = run(f"SELECT * FROM {table}")
    return json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")


def import_data(raw):
    data = json.loads(raw.decode("utf-8"))
    if data.get("orbit_export") != 1:
        raise ValueError("This is not an ORBIT export file.")
    count = 0
    for table in ALL_TABLES:
        columns = [row["name"] for row in run(f"PRAGMA table_info({table})")]
        run(f"DELETE FROM {table}")
        for row in data.get(table, []):
            row = {k: v for k, v in row.items() if k in columns}
            if not row:
                continue
            marks = ", ".join("?" * len(row))
            run(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({marks})", tuple(row.values()))
            count += 1
    return count


def delete_everything():
    for table in ALL_TABLES:
        run(f"DELETE FROM {table}")
    if personal_model_path().exists():
        personal_model_path().unlink()
