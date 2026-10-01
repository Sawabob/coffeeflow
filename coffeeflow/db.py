"""SQLite: окреме з'єднання на контекст, параметри й атомарні зміни."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from flask import current_app, g


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=5,
                               isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@contextmanager
def transaction():
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise


def init_db():
    db = get_db()
    version = db.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0, 1):
        raise RuntimeError('Непідтримувана версія схеми; потрібна міграція.')
    db.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))
