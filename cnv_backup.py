"""
Backups of the CNV register SQLite database.

Uses SQLite's online backup API (consistent copy even while the DB is open),
checks every backup with PRAGMA integrity_check and prunes old backups:
the newest KEEP_LATEST backups are kept, plus the oldest backup of every month.

Run directly for a manual backup:  python cnv_backup.py
"""

import os
import re
import sqlite3
import sys
from datetime import datetime

import cnv_register_db as db

BACKUP_DIR = r"U:\cnv_register_backups"
KEEP_LATEST = 30
BACKUP_NAME_RE = re.compile(r"^cnv_register_(\d{4}-\d{2}-\d{2})_(\d{6})(?:_[\w-]+)?\.db$")


def list_backups(backup_dir=BACKUP_DIR):
    """Returns backup file names in backup_dir, oldest first."""
    if not os.path.isdir(backup_dir):
        return []
    names = [n for n in os.listdir(backup_dir) if BACKUP_NAME_RE.match(n)]
    return sorted(names, key=lambda n: BACKUP_NAME_RE.match(n).groups())


def check_integrity(db_path):
    """Returns True if PRAGMA integrity_check reports 'ok'."""
    conn = sqlite3.connect(db_path)
    try:
        result = conn.execute("PRAGMA integrity_check;").fetchone()
        return result is not None and result[0] == "ok"
    finally:
        conn.close()


def prune_backups(backup_dir=BACKUP_DIR, keep_latest=KEEP_LATEST):
    """Deletes backups that are neither among the newest keep_latest nor the first of their month."""
    names = list_backups(backup_dir)
    keep = set(names[-keep_latest:]) if keep_latest > 0 else set()
    seen_months = set()
    for name in names:
        month = BACKUP_NAME_RE.match(name).group(1)[:7]
        if month not in seen_months:
            seen_months.add(month)
            keep.add(name)
    removed = []
    for name in names:
        if name not in keep:
            os.remove(os.path.join(backup_dir, name))
            removed.append(name)
    if removed:
        print(f"  - Removed {len(removed)} old backup(s).")
    return removed


def backup_database(db_path=db.DB_FILE, backup_dir=BACKUP_DIR, reason=None):
    """Creates a checked backup of db_path in backup_dir. Returns the backup path or None on failure."""
    if not os.path.exists(db_path):
        print(f"Backup skipped: database '{db_path}' does not exist.")
        return None
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except OSError as e:
        print(f"ERROR: Cannot create backup folder '{backup_dir}': {e}")
        return None

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    suffix = f"_{re.sub(r'[^A-Za-z0-9-]', '-', reason)}" if reason else ""
    backup_path = os.path.join(backup_dir, f"cnv_register_{stamp}{suffix}.db")

    source = target = None
    try:
        source = sqlite3.connect(db_path)
        target = sqlite3.connect(backup_path)
        source.backup(target)
    except sqlite3.Error as e:
        print(f"ERROR during backup to '{backup_path}': {e}")
        return None
    finally:
        if target: target.close()
        if source: source.close()

    if not check_integrity(backup_path):
        print(f"ERROR: Integrity check FAILED for backup '{backup_path}'.")
        return None

    print(f"Backup created and verified: {backup_path}")
    prune_backups(backup_dir)
    return backup_path


def backup_if_due(db_path=db.DB_FILE, backup_dir=BACKUP_DIR):
    """Creates a daily backup unless one exists for today. Returns a backup path, or None on failure."""
    today = datetime.now().strftime("%Y-%m-%d")
    todays = [n for n in list_backups(backup_dir) if BACKUP_NAME_RE.match(n).group(1) == today]
    if todays:
        print("Daily backup already exists for today.")
        return os.path.join(backup_dir, todays[-1])
    return backup_database(db_path, backup_dir, reason="daily")


if __name__ == "__main__":
    result = backup_database(reason="manual")
    sys.exit(0 if result else 1)
