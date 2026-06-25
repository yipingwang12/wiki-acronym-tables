"""Production server entry point for Fly.io deployment.

Env vars:
  PORT       HTTP port (default 8080)
  DB_PATH    SQLite database path (default /data/quiz.db on Fly, logs/quiz.db locally)
  DECKS_DIR  Exported deck-artifact directory (default ./data/decks)
"""

from __future__ import annotations

import os
from pathlib import Path

from wiki_acronyms.desktop_app import create_full_app
from wiki_acronyms.logger import QuizLogger

_ROOT = Path(__file__).resolve().parent
_PORT = int(os.environ.get('PORT', '8080'))
_DB_PATH = Path(os.environ.get('DB_PATH', str(_ROOT / 'logs' / 'quiz.db')))
_DECKS_DIR = Path(os.environ.get('DECKS_DIR', str(_ROOT / 'data' / 'decks')))


def create_app():
    """WSGI app factory for gunicorn: gunicorn 'server:create_app()'."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = QuizLogger(db_path=_DB_PATH)
    return create_full_app(_DECKS_DIR, logger)


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=_PORT, debug=False, threaded=True)
