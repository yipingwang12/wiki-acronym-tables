import random

import pytest
import yaml

from deck_generator.corruptions import build_pool
from deck_generator.equations import Equation, eligible_indices, to_mathml, token_texts
from deck_generator.equations_cli import _sample_display, main

ALL = ['sign_flip', 'exponent_off_by_one', 'constant_perturb', 'variable_swap']

CONFIG = {
    'deck_name': 'Test equations',
    'corruption': {'pool_size': 6, 'types': ALL},
    'equations': [
        {'label': 'Kinetic energy', 'latex': r'E = \frac{1}{2}mv^2'},
        {'label': 'Poisson variance', 'latex': 'V = L'},   # unusable: two tokens
    ],
}


@pytest.fixture
def config_file(tmp_path):
    d = tmp_path / 'equations'
    d.mkdir()
    p = d / 'test.yaml'
    p.write_text(yaml.safe_dump(CONFIG))
    return p


def _sample_for(latex: str, seed: int = 0) -> str:
    eq = Equation(label='x', latex=latex)
    mathml = to_mathml(latex)
    pool, bad = build_pool(eq, ALL)
    return _sample_display(token_texts(mathml), eligible_indices(mathml), pool, bad,
                           random.Random(seed))


def test_sample_marks_exactly_two_tokens():
    out = _sample_for(r'E = \frac{1}{2}mv^2')
    assert out.count('[') == 2


def test_sample_reports_which_tokens_are_wrong():
    assert 'wrong: tok-' in _sample_for(r'E = \frac{1}{2}mv^2')


def test_sample_is_seed_reproducible():
    assert _sample_for(r'E = \frac{1}{2}mv^2', 7) == _sample_for(r'E = \frac{1}{2}mv^2', 7)


def test_sample_handles_unusable_equation():
    """A card with no valid pair must report that, not crash or invent one."""
    assert _sample_display(['V', '=', 'L'], [0, 1, 2], [], [], random.Random(0)) == \
        '(no valid two-error pair)'


def test_preview_reports_usable_count(config_file, capsys):
    main(['--config', str(config_file)])
    out = capsys.readouterr().out
    assert '1/2 equations usable' in out


def test_preview_surfaces_pool_warnings(config_file, capsys):
    main(['--config', str(config_file)])
    assert 'unusable' in capsys.readouterr().out


def test_preview_writes_nothing(config_file, tmp_path, capsys):
    """Preview is the tuning loop — it must never touch the decks dir."""
    out_dir = tmp_path / 'decks'
    main(['--config', str(config_file), '--out', str(out_dir)])
    capsys.readouterr()
    assert not out_dir.exists()


def test_sample_flag_adds_display(config_file, capsys):
    main(['--config', str(config_file), '--sample'])
    assert '[' in capsys.readouterr().out
