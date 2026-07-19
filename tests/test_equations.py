import xml.etree.ElementTree as ET

from deck_generator.equations import (
    Equation, annotate, eligible_indices, to_mathml, token_texts,
)


def test_token_texts_in_document_order():
    assert token_texts(to_mathml(r'E = mc^2')) == ['E', '=', 'm', 'c', '2']


def test_delimiters_are_tokens_but_not_eligible():
    mathml = to_mathml(r'f(x) = a')
    assert '(' in token_texts(mathml)          # they *are* tokens…
    kept = [token_texts(mathml)[i] for i in eligible_indices(mathml)]
    assert '(' not in kept and ')' not in kept  # …but never clickable


def test_accent_token_is_excluded():
    """``\\hat{H}`` emits H plus a standalone caret; the caret must not be clickable."""
    mathml = to_mathml(r'\hat{H}\Psi')
    kept = [token_texts(mathml)[i] for i in eligible_indices(mathml)]
    assert '^' not in kept
    assert 'H' in kept


def test_differential_d_is_excluded():
    mathml = to_mathml(r'\int e^{-x^2} dx = 1')
    toks = token_texts(mathml)
    kept_idx = eligible_indices(mathml)
    d_positions = [i for i, t in enumerate(toks) if t == 'd']
    assert d_positions and all(i not in kept_idx for i in d_positions)


def test_eligible_is_broader_than_corruptible():
    """The haystack must stay large — variables and relations are clickable too."""
    mathml = to_mathml(r'E = mc^2')
    kept = {token_texts(mathml)[i] for i in eligible_indices(mathml)}
    assert {'E', 'm', 'c', '2', '='} <= kept


def test_annotate_numbers_eligible_tokens_one_based():
    mathml = to_mathml(r'E = mc^2')
    idx = eligible_indices(mathml)
    out = annotate(mathml, idx)
    ids = [e.get('id') for e in ET.fromstring(out).iter() if e.get('id')]
    assert ids == [f'tok-{n}' for n in range(1, len(idx) + 1)]


def test_annotate_leaves_ineligible_tokens_unmarked():
    mathml = to_mathml(r'f(x) = a')
    out = annotate(mathml, eligible_indices(mathml))
    marked = [(e.tag.split('}')[-1], e.text) for e in ET.fromstring(out).iter() if e.get('id')]
    assert all(text not in ('(', ')') for _, text in marked)


def test_equation_defaults():
    eq = Equation(label='Newton', latex='F = ma')
    assert eq.pin == [] and eq.source == ''
