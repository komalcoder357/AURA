"""Tiny additive migration for SQLite/PostgreSQL: adds columns that newer models have but an existing
database lacks, so users keep their accounts, chats and memory when they upgrade.
For SQLite a timestamped copy of the database file is made BEFORE any change (instance/backups/)."""
import os
import shutil
import time

from sqlalchemy import inspect, text

from extensions import db


def _default_sql(col):
    d = col.default
    if d is None or not getattr(d, "is_scalar", False):
        return ""
    v = d.arg
    if isinstance(v, bool):
        return f" DEFAULT {1 if v else 0}"
    if isinstance(v, (int, float)):
        return f" DEFAULT {v}"
    return " DEFAULT '" + str(v).replace("'", "''") + "'"


def _missing_columns(insp):
    out = []
    for table in db.metadata.sorted_tables:
        if insp.has_table(table.name):
            have = {c["name"] for c in insp.get_columns(table.name)}
            out += [(table, col) for col in table.columns if col.name not in have]
    return out


def backup_sqlite(app):
    """Copy the SQLite file (if any) next to itself in a 'backups' folder. Returns the path or None."""
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    path = url.database if os.path.isabs(url.database) else os.path.join(app.instance_path, url.database)
    if not os.path.exists(path):
        return None
    folder = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, time.strftime("aura-%Y%m%d-%H%M%S.db"))
    shutil.copy2(path, dest)
    return dest


def run(app):
    """Returns the list of added 'table.column' names (empty when the schema was already current)."""
    insp = inspect(db.engine)
    missing = _missing_columns(insp)
    if missing:
        app.logger.info("Schema upgrade needed; backup: %s", backup_sqlite(app))  # exactly once, before any ALTER
    added = []
    for table, col in missing:
        default = _default_sql(col)
        not_null = " NOT NULL" if (not col.nullable and default) else ""
        ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col.type.compile(db.engine.dialect)}{not_null}{default}'
        db.session.execute(text(ddl))
        added.append(f"{table.name}.{col.name}")
    if insp.has_table("user_preferences"):
        db.session.execute(text("UPDATE user_preferences SET theme='neutral' WHERE theme='classic'"))
    db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_conversation_user_updated ON conversation (user_id, updated_at)"))
    db.session.commit()
    return added
