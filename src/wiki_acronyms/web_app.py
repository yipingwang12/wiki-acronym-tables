"""Flask web app for blindman's bluff poetry quiz."""

from __future__ import annotations

import json
import os
import secrets

from flask import Flask, flash, get_flashed_messages, redirect, render_template, request, session, url_for

from .logger import QuizLogger
from .quiz import (
    AcronymDisplay, DigitDisplay, LineDisplay,
    make_acronym_display, make_digit_display, make_line_display,
    score_acronym_response, score_digit_response, score_response,
)

_MISS_COST = 3
_FALSE_ALARM_COST = 1
_MAX_HEALTH = 10
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


def create_app(
    lines: list[str],
    title: str,
    wrong_prob: float = 0.15,
    mode: str = 'words',
    item_labels: list[str] | None = None,
    logger: QuizLogger | None = None,
    config_path: str | None = None,
    cfg_hash: str | None = None,
) -> Flask:
    app = Flask(__name__, template_folder=_TEMPLATE_DIR)
    app.secret_key = secrets.token_hex(16)
    app.config['LINES'] = lines
    app.config['TITLE'] = title
    app.config['WRONG_PROB'] = wrong_prob
    app.config['MODE'] = mode
    app.config['ITEM_LABELS'] = item_labels or []

    def _start_log_session() -> str | None:
        if not logger:
            return None
        return logger.start_session(mode, title, config_path, cfg_hash, wrong_prob)

    def _init_session() -> None:
        if 'line_idx' not in session:
            session['line_idx'] = 0
            session['health'] = _MAX_HEALTH
            session['display'] = None
            session['attempt_id'] = None
            session['log_sid'] = _start_log_session()

    def _build_display(line: str, wrong_prob: float, mode: str) -> dict:
        if mode == 'acronym':
            d = make_acronym_display(line, wrong_prob)
            return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_letters}
        elif mode == 'digits':
            d = make_digit_display(line, wrong_prob)
            return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_digits}
        else:
            d = make_line_display(line, wrong_prob)
            return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_words}

    def _score(disp: dict, user_pos: set[int], mode: str) -> tuple[bool, str]:
        if mode == 'acronym':
            d = AcronymDisplay(display=disp['display'], has_wrong=disp['has_wrong'], wrong_letters=disp['wrong_positions'])
            return score_acronym_response(d, user_pos)
        elif mode == 'digits':
            d = DigitDisplay(display=disp['display'], has_wrong=disp['has_wrong'], wrong_digits=disp['wrong_positions'])
            return score_digit_response(d, user_pos)
        else:
            d = LineDisplay(display=disp['display'], has_wrong=disp['has_wrong'], wrong_words=disp['wrong_positions'])
            return score_response(d, user_pos)

    @app.route('/')
    def index():
        session.clear()
        return redirect(url_for('quiz'))

    @app.route('/quiz', methods=['GET', 'POST'])
    def quiz():
        _init_session()
        lines_ = app.config['LINES']
        title_ = app.config['TITLE']
        wrong_prob_ = app.config['WRONG_PROB']
        mode_ = app.config['MODE']
        labels_ = app.config['ITEM_LABELS']
        item_label = 'digit' if mode_ == 'digits' else ('letter' if mode_ == 'acronym' else 'word')

        if request.method == 'POST':
            if not session.get('display'):
                return redirect(url_for('quiz'))

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

            if logger and session.get('log_sid') and session.get('attempt_id'):
                logger.log_response(
                    session['attempt_id'], raw, keystrokes,
                    sorted(user_pos), correct, session['health'],
                )

            if correct:
                flash(feedback, 'correct')
            elif health_exhausted:
                session['log_sid'] = _start_log_session()
                flash('Health exhausted — restarting from the beginning.', 'restart')
            else:
                flash(feedback, 'wrong')

            session['attempt_id'] = None
            session.modified = True
            return redirect(url_for('quiz'))

        # GET
        line_idx = session['line_idx']
        if line_idx >= len(lines_):
            return render_template('complete.html', title=title_)

        if session.get('display') is None:
            session['display'] = _build_display(lines_[line_idx], wrong_prob_, mode_)
            label = labels_[line_idx] if labels_ and line_idx < len(labels_) else None
            if logger and session.get('log_sid'):
                session['attempt_id'] = logger.log_display(
                    session['log_sid'], line_idx, label,
                    lines_[line_idx], session['display']['display'],
                    session['health'],
                )
            session.modified = True

        tokens = session['display']['display'].split('  ')
        health = session['health']

        if labels_ and line_idx < len(labels_):
            progress_text = labels_[line_idx]
        else:
            progress_text = f"Line {line_idx + 1} of {len(lines_)}"

        return render_template(
            'quiz.html',
            title=title_,
            progress_text=progress_text,
            health=health,
            max_health=_MAX_HEALTH,
            health_pct=max(0, health * 100 // _MAX_HEALTH),
            tokens=tokens,
            item_label=item_label,
            mode=mode_,
        )

    return app
