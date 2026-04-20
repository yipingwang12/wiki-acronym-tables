"""Desktop app: PyWebView + Flask with Anki-style deck picker."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path

from datetime import datetime, timezone

from flask import Flask, flash, redirect, render_template, request, session, url_for

from .deck_loader import discover_decks, load_monarchs_deck, load_poetry_deck
from .logger import QuizLogger, config_hash
from .quiz import (
    AcronymDisplay, DigitDisplay, LineDisplay,
    make_acronym_display, make_digit_display, make_line_display,
    score_acronym_response, score_digit_response, score_response,
)
from .srs import SRSScheduler

_MISS_COST = 3
_FALSE_ALARM_COST = 1
_MAX_HEALTH = 10
_PORT = 5001
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _ROOT / 'configs'


def _make_srs(logger: QuizLogger) -> SRSScheduler:
    return SRSScheduler(
        logger,
        max_interval_days=365,
        learning_steps=[1, 10, 60, 360],
        graduated_steps=[1, 2, 3, 4, 5, 6, 7],
        new_cards_per_day=20,
        relearn_steps=[1, 2, 3],
        difficulty_forgiveness=1.0,
        stability_forgiveness=1.0,
    )


def create_full_app(config_dir: Path, logger: QuizLogger) -> Flask:
    app = Flask(__name__, template_folder=_TEMPLATE_DIR)
    app.secret_key = secrets.token_hex(16)
    app.config['CONFIG_DIR'] = config_dir
    app.config['DECK'] = None
    app.config['LOAD_STATE'] = 'idle'
    app.config['LOAD_ERROR'] = None
    _load_lock = threading.Lock()

    @app.template_filter('relative_time')
    def _relative_time(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso.replace('Z', '+00:00'))
            delta = datetime.now(timezone.utc) - dt
            days = delta.days
            if days == 0:
                return 'today'
            if days == 1:
                return 'yesterday'
            return f'{days} days ago'
        except Exception:
            return iso

    def _empty_stats() -> dict:
        return {'easy': 0, 'good': 0, 'hard': 0, 'again': 0, 'total_time': 0.0, 'completed': 0}

    def _init_session(deck: dict) -> None:
        if 'line_idx' not in session:
            srs = deck['srs']
            lines = deck['lines']
            session['line_idx'] = 0
            session['health'] = _MAX_HEALTH
            session['display'] = None
            session['attempt_id'] = None
            session['log_sid'] = logger.start_session(
                deck['mode'], deck['title'], deck['config_path'], deck['cfg_hash'], deck['wrong_prob'],
            )
            session['stats'] = _empty_stats()
            session['item_order'] = srs.get_due_order(lines)
            session['due_count'] = min(len(lines), srs.get_due_count(lines))

    def _build_display(line: str, wrong_prob: float, mode: str) -> dict:
        if mode == 'acronym':
            d = make_acronym_display(line, wrong_prob)
            return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_letters}
        if mode == 'digits':
            d = make_digit_display(line, wrong_prob)
            return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_digits}
        d = make_line_display(line, wrong_prob)
        return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_words}

    def _score(disp: dict, user_pos: set[int], mode: str) -> tuple[bool, str]:
        if mode == 'acronym':
            d = AcronymDisplay(display=disp['display'], has_wrong=disp['has_wrong'], wrong_letters=disp['wrong_positions'])
            return score_acronym_response(d, user_pos)
        if mode == 'digits':
            d = DigitDisplay(display=disp['display'], has_wrong=disp['has_wrong'], wrong_digits=disp['wrong_positions'])
            return score_digit_response(d, user_pos)
        d = LineDisplay(display=disp['display'], has_wrong=disp['has_wrong'], wrong_words=disp['wrong_positions'])
        return score_response(d, user_pos)

    @app.route('/')
    def home():
        decks = discover_decks(config_dir, logger)
        return render_template('home.html', decks=decks)

    @app.route('/start', methods=['POST'])
    def start():
        config_path = request.form['config_path']
        deck_type = request.form['deck_type']
        poem_title = request.form.get('poem_title', '')

        with _load_lock:
            app.config['LOAD_STATE'] = 'loading'
            app.config['LOAD_ERROR'] = None
            app.config['DECK'] = None

        session.clear()

        def _load():
            try:
                if deck_type == 'poetry':
                    lines, title = load_poetry_deck(Path(config_path), poem_title)
                    mode, item_labels = 'words', None
                else:
                    lines, title, item_labels = load_monarchs_deck(Path(config_path))
                    mode = 'digits'

                wrong_prob = 0.15 if mode == 'words' else 0.2
                srs = _make_srs(logger)

                with _load_lock:
                    app.config['DECK'] = {
                        'lines': lines,
                        'title': title,
                        'mode': mode,
                        'wrong_prob': wrong_prob,
                        'item_labels': item_labels,
                        'config_path': config_path,
                        'cfg_hash': config_hash(Path(config_path)),
                        'srs': srs,
                    }
                    app.config['LOAD_STATE'] = 'ready'
            except Exception as e:
                with _load_lock:
                    app.config['LOAD_STATE'] = 'error'
                    app.config['LOAD_ERROR'] = str(e)

        threading.Thread(target=_load, daemon=True).start()
        return redirect(url_for('loading'))

    @app.route('/loading')
    def loading():
        return render_template('loading.html')

    @app.route('/status')
    def status():
        return {'state': app.config.get('LOAD_STATE', 'idle'), 'error': app.config.get('LOAD_ERROR')}

    @app.route('/quiz', methods=['GET', 'POST'])
    def quiz():
        deck = app.config.get('DECK')
        if deck is None:
            return redirect(url_for('home'))

        _init_session(deck)
        lines_ = deck['lines']
        title_ = deck['title']
        wrong_prob_ = deck['wrong_prob']
        mode_ = deck['mode']
        labels_ = deck['item_labels'] or []
        srs = deck['srs']
        config_path_ = deck['config_path']
        cfg_hash_ = deck['cfg_hash']
        item_label = 'digit' if mode_ == 'digits' else ('letter' if mode_ == 'acronym' else 'word')

        if request.method == 'POST':
            if not session.get('display'):
                return redirect(url_for('quiz'))

            response_secs = time.time() - session.get('display_time', time.time())
            actual_idx = session['item_order'][session['line_idx']]
            item_text = lines_[actual_idx]
            raw = request.form.get('answer', '').strip()
            user_pos: set[int] = set()
            if raw and raw != '0':
                try:
                    user_pos = {int(x) for x in raw.split()}
                except ValueError:
                    pass

            try:
                keystrokes = json.loads(request.form.get('keystrokes', '[]'))
            except (ValueError, TypeError):
                keystrokes = []

            correct, feedback = _score(session['display'], user_pos, mode_)
            actual = set(session['display']['wrong_positions'])
            session['display'] = None

            if correct:
                session['line_idx'] += 1
            else:
                session['health'] -= len(actual - user_pos) * _MISS_COST + len(user_pos - actual) * _FALSE_ALARM_COST

            health_exhausted = session['health'] <= 0
            if health_exhausted:
                session['line_idx'] = 0
                session['health'] = _MAX_HEALTH

            if session.get('log_sid') and session.get('attempt_id'):
                logger.log_response(
                    session['attempt_id'], raw, keystrokes,
                    sorted(user_pos), correct, session['health'],
                )

            rating = srs.review(item_text, mode_, response_secs, correct)

            stats = session.get('stats') or _empty_stats()
            stats['total_time'] += response_secs
            stats['completed'] += 1
            stats[rating.name.lower()] = stats.get(rating.name.lower(), 0) + 1
            session['stats'] = stats

            if correct:
                flash(feedback, 'correct')
            elif health_exhausted:
                session['log_sid'] = logger.start_session(mode_, title_, config_path_, cfg_hash_, wrong_prob_)
                session['stats'] = _empty_stats()
                flash('Health exhausted — restarting from the beginning.', 'restart')
            else:
                flash(feedback, 'wrong')

            session['attempt_id'] = None
            session.modified = True
            return redirect(url_for('quiz'))

        # GET
        line_idx = session['line_idx']
        due_count = session['due_count']
        if line_idx >= due_count:
            return render_template('complete.html', title=title_, show_back=True)

        actual_idx = session['item_order'][line_idx]

        if session.get('display') is None:
            session['display'] = _build_display(lines_[actual_idx], wrong_prob_, mode_)
            session['display_time'] = time.time()
            label = labels_[actual_idx] if labels_ and actual_idx < len(labels_) else None
            if session.get('log_sid'):
                session['attempt_id'] = logger.log_display(
                    session['log_sid'], actual_idx, label,
                    lines_[actual_idx], session['display']['display'],
                    session['health'],
                )
            session.modified = True

        tokens = session['display']['display'].split('  ')
        health = session['health']
        stats = session.get('stats') or _empty_stats()
        completed = stats['completed']
        avg_time_str = f"{stats['total_time'] / completed:.1f}s" if completed else '—'

        if labels_ and actual_idx < len(labels_):
            progress_text = labels_[actual_idx]
        else:
            progress_text = f"Item {line_idx + 1} of {due_count}"

        phase = srs.get_phase(lines_[actual_idx])

        return render_template(
            'quiz.html',
            title=title_,
            progress_text=progress_text,
            phase=phase,
            health=health,
            max_health=_MAX_HEALTH,
            health_pct=max(0, health * 100 // _MAX_HEALTH),
            tokens=tokens,
            item_label=item_label,
            mode=mode_,
            stats=stats,
            avg_time_str=avg_time_str,
            total_items=due_count,
            display_time=session.get('display_time', time.time()),
            show_back=True,
        )

    @app.route('/restart')
    def restart():
        session.clear()
        return redirect(url_for('quiz'))

    return app


def main() -> None:
    import webview  # imported here so the module loads without pywebview installed

    logger = QuizLogger(db_path=_ROOT / 'logs' / 'quiz.db')
    app = create_full_app(_CONFIG_DIR, logger)

    server = threading.Thread(
        target=lambda: app.run(port=_PORT, debug=False, use_reloader=False),
        daemon=True,
    )
    server.start()
    time.sleep(0.8)  # wait for Flask to bind

    webview.create_window('Quiz', f'http://localhost:{_PORT}', width=960, height=720, min_size=(600, 480))
    webview.start()
    logger.close()
