"""Flask web app for blindman's bluff poetry quiz."""

from __future__ import annotations

import os
import secrets

from flask import Flask, flash, get_flashed_messages, redirect, render_template, request, session, url_for

from .quiz import (
    AcronymDisplay, LineDisplay,
    make_acronym_display, make_line_display,
    score_acronym_response, score_response,
)

_MISS_COST = 3
_FALSE_ALARM_COST = 1
_MAX_HEALTH = 10
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


def create_app(lines: list[str], title: str, wrong_prob: float = 0.15, mode: str = 'words') -> Flask:
    app = Flask(__name__, template_folder=_TEMPLATE_DIR)
    app.secret_key = secrets.token_hex(16)
    app.config['LINES'] = lines
    app.config['TITLE'] = title
    app.config['WRONG_PROB'] = wrong_prob
    app.config['MODE'] = mode  # 'words' or 'acronym'

    def _init_session() -> None:
        if 'line_idx' not in session:
            session['line_idx'] = 0
            session['health'] = _MAX_HEALTH
            session['display'] = None

    def _build_display(line: str, wrong_prob: float, mode: str) -> dict:
        if mode == 'acronym':
            d = make_acronym_display(line, wrong_prob)
            return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_letters}
        else:
            d = make_line_display(line, wrong_prob)
            return {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_positions': d.wrong_words}

    def _score(disp: dict, user_pos: set[int], mode: str) -> tuple[bool, str]:
        if mode == 'acronym':
            d = AcronymDisplay(display=disp['display'], has_wrong=disp['has_wrong'], wrong_letters=disp['wrong_positions'])
            return score_acronym_response(d, user_pos)
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
        item_label = 'letter' if mode_ == 'acronym' else 'word'

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

            correct, feedback = _score(session['display'], user_pos, mode_)
            actual = set(session['display']['wrong_positions'])
            session['display'] = None

            if correct:
                session['line_idx'] += 1
                flash(feedback, 'correct')
            else:
                session['health'] -= len(actual - user_pos) * _MISS_COST + len(user_pos - actual) * _FALSE_ALARM_COST
                if session['health'] <= 0:
                    session['line_idx'] = 0
                    session['health'] = _MAX_HEALTH
                    flash('Health exhausted — restarting from the beginning.', 'restart')
                else:
                    flash(feedback, 'wrong')

            session.modified = True
            return redirect(url_for('quiz'))

        # GET
        line_idx = session['line_idx']
        if line_idx >= len(lines_):
            return render_template('complete.html', title=title_)

        if session.get('display') is None:
            session['display'] = _build_display(lines_[line_idx], wrong_prob_, mode_)
            session.modified = True

        tokens = session['display']['display'].split('  ')
        health = session['health']

        return render_template(
            'quiz.html',
            title=title_,
            line_num=line_idx + 1,
            total_lines=len(lines_),
            health=health,
            max_health=_MAX_HEALTH,
            health_pct=max(0, health * 100 // _MAX_HEALTH),
            tokens=tokens,
            item_label=item_label,
            mode=mode_,
        )

    return app
