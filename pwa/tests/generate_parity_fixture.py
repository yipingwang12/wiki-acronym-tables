"""
Generate a JSON fixture of SRS state sequences for cross-language parity testing.

Run: python pwa/tests/generate_parity_fixture.py > pwa/tests/parity_fixture.json
"""

import hashlib, json, sys, os
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
from wiki_acronyms.srs import SRSScheduler


def item_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class FakeLogger:
    def __init__(self):
        self._cards: dict[str, str] = {}
        self._introduced_today = 0

    def get_card(self, key): return self._cards.get(key)
    def save_card(self, key, val): self._cards[key] = val
    def count_introduced_today(self, date=None): return self._introduced_today


def run_scenario(name, item, mode, events, opts=None):
    """
    events: list of (delta_minutes_from_t0, response_secs, correct)
    Returns dict with scenario name + list of states after each event.
    """
    logger = FakeLogger()
    kwargs = dict(
        learning_steps=[1, 10],
        graduated_steps=[1, 2],
        relearn_steps=[1],
        new_cards_per_day=20,
        max_interval_days=365,
        difficulty_forgiveness=1.0,
        stability_forgiveness=1.0,
    )
    if opts:
        kwargs.update(opts)

    s = SRSScheduler(logger=logger, **kwargs)

    t0 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    key = item_key(item)
    states = []

    import wiki_acronyms.srs as srs_module

    class _FakeDatetime(datetime):
        _fixed: datetime | None = None

        @classmethod
        def now(cls, tz=None):
            return cls._fixed.replace(tzinfo=tz) if tz else cls._fixed

    orig_datetime = srs_module.datetime

    for delta_minutes, response_secs, correct in events:
        now = t0 + timedelta(minutes=delta_minutes)
        _FakeDatetime._fixed = now
        srs_module.datetime = _FakeDatetime
        try:
            rating = s.review(item, mode, response_secs, correct)
        finally:
            srs_module.datetime = orig_datetime
        raw = logger.get_card(key)
        state = json.loads(raw) if raw else None
        states.append({
            'delta_minutes': delta_minutes,
            'response_secs': response_secs,
            'correct': correct,
            'rating': int(rating),
            'state': state,
        })

    return {'name': name, 'item': item, 'mode': mode, 'events': states}


def main():
    scenarios = []

    # 1. Full learning → graduated → FSRS transition
    scenarios.append(run_scenario(
        name='full_progression',
        item='hello world',
        mode='words',
        events=[
            (0,    1, True),   # new card, step 0→1... wait, first review creates card
            (2,    1, True),   # step 0 → 1
            (15,   1, True),   # step 1 → graduated 0
            (1440+30,   1, True),   # graduated 0 → 1
            (1440*2+30, 1, True),   # graduated 1 → FSRS
            (1440*7,    2, True),   # FSRS review
        ],
    ))

    # 2. Learning lapse
    scenarios.append(run_scenario(
        name='learning_lapse',
        item='foo bar',
        mode='words',
        events=[
            (0,  1, True),   # create, step→0
            (2,  1, True),   # step 0→1
            (15, 1, False),  # lapse → step=0
            (16, 1, True),   # step 0→1
            (30, 1, True),   # step 1→graduated 0
        ],
    ))

    # 3. FSRS lapse → relearning (default forgiveness=1.0)
    scenarios.append(run_scenario(
        name='fsrs_lapse_default_forgiveness',
        item='alpha beta',
        mode='words',
        events=[
            (0,    1, True),
            (2,    1, True),
            (15,   1, True),
            (1470, 1, True),
            (2910, 1, True),
            (1440*8, 1, False),  # lapse
            (1440*9, 1, True),   # relearn → exits
        ],
    ))

    # 4. FSRS lapse with half forgiveness
    scenarios.append(run_scenario(
        name='fsrs_lapse_half_forgiveness',
        item='gamma delta',
        mode='words',
        opts={'difficulty_forgiveness': 0.5, 'stability_forgiveness': 0.5},
        events=[
            (0,    1, True),
            (2,    1, True),
            (15,   1, True),
            (1470, 1, True),
            (2910, 1, True),
            (1440*8, 1, False),  # lapse
        ],
    ))

    # 5. Rating thresholds
    scenarios.append(run_scenario(
        name='rating_thresholds',
        item='one two three',
        mode='words',
        events=[
            (0,    0.5, True),   # Easy
            (2,    5.0, True),   # Good
            (20,   99,  True),   # Hard
        ],
    ))

    # 6. Acronym mode thresholds
    scenarios.append(run_scenario(
        name='acronym_mode',
        item='NATO RADAR LASER',
        mode='acronym',
        events=[
            (0, 1,  True),
            (2, 10, True),
        ],
    ))

    # 7. Digits mode
    scenarios.append(run_scenario(
        name='digits_mode',
        item='12345',
        mode='digits',
        events=[
            (0, 1,  True),
            (2, 10, True),
        ],
    ))

    # 8. Interval cap
    scenarios.append(run_scenario(
        name='interval_cap',
        item='cap test',
        mode='words',
        opts={'max_interval_days': 1},
        events=[
            (0,    1, True),
            (2,    1, True),
            (15,   1, True),
            (1470, 1, True),
            (2910, 1, True),
            (1440*10, 2, True),
        ],
    ))

    print(json.dumps(scenarios, indent=2))


if __name__ == '__main__':
    main()
