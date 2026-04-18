"""Flask web app for blindman's bluff poetry quiz."""

from __future__ import annotations

import os
import secrets

from flask import Flask, flash, get_flashed_messages, redirect, render_template, request, session, url_for

from .quiz import LineDisplay, make_line_display, score_response

_MISS_COST = 3
_FALSE_ALARM_COST = 1
_MAX_HEALTH = 10
_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')


def create_app(lines: list[str], title: str, wrong_prob: float = 0.15) -> Flask:
    app = Flask(__name__, template_folder=_TEMPLATE_DIR)
    app.secret_key = secrets.token_hex(16)
    app.config['LINES'] = lines
    app.config['TITLE'] = title
    app.config['WRONG_PROB'] = wrong_prob

    def _init_session() -> None:
        if 'line_idx' not in session:
            session['line_idx'] = 0
            session['health'] = _MAX_HEALTH
            session['display'] = None

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

        if request.method == 'POST':
            if not session.get('display'):
                return redirect(url_for('quiz'))

            d = LineDisplay(
                display=session['display']['display'],
                has_wrong=session['display']['has_wrong'],
                wrong_words=session['display']['wrong_words'],
            )
            raw = request.form.get('answer', '').strip()
            user_words: set[int] = set()
            if raw and raw != '0':
                try:
                    user_words = {int(x) for x in raw.split()}
                except ValueError:
                    pass

            correct, feedback = score_response(d, user_words)
            session['display'] = None

            if correct:
                session['line_idx'] += 1
                flash(feedback, 'correct')
            else:
                actual = set(d.wrong_words)
                session['health'] -= len(actual - user_words) * _MISS_COST + len(user_words - actual) * _FALSE_ALARM_COST
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
            d = make_line_display(lines_[line_idx], wrong_prob_)
            session['display'] = {'display': d.display, 'has_wrong': d.has_wrong, 'wrong_words': d.wrong_words}
            session.modified = True

        words = session['display']['display'].split('  ')
        health = session['health']
        health_pct = max(0, health * 100 // _MAX_HEALTH)

        return render_template(
            'quiz.html',
            title=title_,
            line_num=line_idx + 1,
            total_lines=len(lines_),
            health=health,
            max_health=_MAX_HEALTH,
            health_pct=health_pct,
            words=words,
        )

    return app
