"""Flask Blueprint: JSON API for PWA deck listing, content loading, and SRS sync."""

from __future__ import annotations

import hashlib
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from .deck_loader import discover_decks, load_monarchs_deck, load_poetry_deck

_PWA_DIR = Path(__file__).resolve().parent.parent.parent / 'pwa'

api_bp = Blueprint('api', __name__)


def _deck_id(config_path: str, poem_title: str | None) -> str:
    return hashlib.sha256(f"{config_path}|{poem_title or ''}".encode()).hexdigest()[:12]


def _deck_to_dict(d, *, include_id: bool = True) -> dict:
    out = {
        'name': d.name,
        'type': d.deck_type,
        'mode': d.mode,
        'group': d.group,
        'last_studied': d.last_studied,
    }
    if include_id:
        out['id'] = _deck_id(d.config_path, d.poem_title)
    return out


@api_bp.route('/pwa/')
@api_bp.route('/pwa/<path:filename>')
def pwa_static(filename='index.html'):
    """Serve PWA static files so iPhone can install from http://<host>:5001/pwa/."""
    return send_from_directory(str(_PWA_DIR), filename)


@api_bp.after_request
def _cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response


@api_bp.route('/api/decks')
def list_decks():
    logger = current_app.config['LOGGER']
    config_dir = current_app.config['CONFIG_DIR']
    decks = discover_decks(config_dir, logger)
    return jsonify([_deck_to_dict(d) for d in decks])


@api_bp.route('/api/deck/<deck_id>/content')
def deck_content(deck_id: str):
    logger = current_app.config['LOGGER']
    config_dir = current_app.config['CONFIG_DIR']
    decks = discover_decks(config_dir, logger)
    deck = next((d for d in decks if _deck_id(d.config_path, d.poem_title) == deck_id), None)
    if deck is None:
        return jsonify({'error': 'deck not found'}), 404

    try:
        if deck.deck_type == 'poetry':
            items, title = load_poetry_deck(Path(deck.config_path), deck.poem_title)
            return jsonify({'items': items, 'mode': 'words', 'title': title, 'labels': None})
        else:
            items, title, labels = load_monarchs_deck(Path(deck.config_path))
            return jsonify({'items': items, 'mode': 'digits', 'title': title, 'labels': labels})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


@api_bp.route('/api/sync', methods=['OPTIONS'])
def sync_preflight():
    return '', 204


@api_bp.route('/api/sync', methods=['POST'])
def sync():
    """Last-write-wins merge of client SRS state with server.

    Request body:  { "changes": [{item_key, card_json, updated_at}, ...] }
    Response body: { "cards":   [{item_key, card_json, updated_at}, ...] }
    """
    logger = current_app.config['LOGGER']
    body = request.get_json(force=True, silent=True) or {}
    changes = body.get('changes', [])

    for change in changes:
        key = change.get('item_key')
        card_json = change.get('card_json')
        updated_at = change.get('updated_at')
        if not (key and card_json and updated_at):
            continue
        row = logger._conn.execute(
            'SELECT updated_at FROM srs_state WHERE item_key=?', (key,)
        ).fetchone()
        if row is None or updated_at > row[0]:
            logger._conn.execute(
                'INSERT INTO srs_state (item_key, card_json, updated_at) VALUES (?,?,?) '
                'ON CONFLICT(item_key) DO UPDATE SET '
                'card_json=excluded.card_json, updated_at=excluded.updated_at',
                (key, card_json, updated_at),
            )

    logger._conn.commit()

    rows = logger._conn.execute(
        'SELECT item_key, card_json, updated_at FROM srs_state'
    ).fetchall()
    return jsonify({'cards': [
        {'item_key': r[0], 'card_json': r[1], 'updated_at': r[2]} for r in rows
    ]})
