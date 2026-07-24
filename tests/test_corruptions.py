import pytest

from deck_generator.corruptions import (
    _constant_spans, _variable_swap_spans, pool_warnings, valid_pairs,
    _Span, _exponent_spans, _sign_flip_spans, apply_spans, build_pool, classify, differs,
)
from deck_generator.equations import Equation

ALL = ['sign_flip', 'exponent_off_by_one', 'constant_perturb', 'variable_swap']


# --- span generation -------------------------------------------------------

def test_sign_flip_finds_binary_operators():
    spans = _sign_flip_spans(r'a + b - c')
    assert {s.text for s in spans} == {'+', '-'}


def test_sign_flip_skips_macro_internals():
    """A '-' inside a macro name would corrupt the markup, not the maths."""
    assert _sign_flip_spans(r'\pm x') == []


def test_exponent_spans_nudge_by_one_both_ways():
    assert {s.text for s in _exponent_spans(r'mc^2')} == {'1', '3'}


def test_exponent_spans_never_produce_zero():
    assert '0' not in {s.text for s in _exponent_spans(r'x^1')}


def test_apply_spans_composes_right_to_left():
    latex = r'a + b + c'
    spans = [_Span(2, 3, '-', 'sign_flip'), _Span(6, 7, '-', 'sign_flip')]
    assert apply_spans(latex, spans) == r'a - b - c'


# --- the equivalence predicate (fixtures from the sympy spike) -------------

@pytest.mark.parametrize('clean, corrupted', [
    (r'E = \frac{1}{2}mv^2', r'E = -\frac{1}{2}mv^2'),   # sign flip
    (r'E = mc^2', r'E = mc^3'),                          # exponent
    (r'y = \frac{a}{b}', r'y = \frac{a}{3b}'),           # constant
])
def test_differs_accepts_real_corruptions(clean, corrupted):
    assert differs(clean, corrupted) is True


@pytest.mark.parametrize('clean, corrupted', [
    (r'F = ma', r'F = am'),                              # commutative reorder
    (r'S = a + b', r'S = b + a'),                        # operand reorder
    (r'y = \frac{a}{b}', r'y = a b^{-1}'),               # algebraic restatement
    (r'E = \frac{1}{2}mv^2', r'-E = -\frac{1}{2}mv^2'),  # negate both sides
])
def test_differs_rejects_equivalent_rewrites(clean, corrupted):
    """These are the traps: each *looks* changed but the equation is the same, so shipping
    one would mark the user wrong for correctly finding no error."""
    assert differs(clean, corrupted) is False


def test_differs_fails_closed_on_misparse():
    """sympy turns \\mathbf into a stray symbol instead of raising, so no verdict is
    trustworthy — the guard must reject rather than guess."""
    assert differs(r'\nabla \times \mathbf{E} = 0', r'\nabla \times \mathbf{E} = 1') is False


def test_differs_fails_closed_on_garbage():
    assert differs(r'\zzz{', r'\zzz{{') is False


def test_differs_accepts_expanded_form_equivalence_via_numeric_sampling():
    """A structural ``a - b != 0`` that is nonetheless mathematically zero (expanded vs
    factored) must be rejected — numeric sampling catches what structural equality misses."""
    assert differs(r'y = (x+1)^2', r'y = x^2 + 2x + 1') is False


class _Timer:
    def __enter__(self):
        import time
        self._t = time.time()
        return self

    def __exit__(self, *a):
        pass

    @property
    def elapsed(self):
        import time
        return time.time() - self._t


@pytest.mark.parametrize('clean, corrupted, want', [
    # corruption OUTSIDE the integral: the ∫ cancels in a-b, residue is algebraic → verifiable
    (r'\int_{-\infty}^{\infty} e^{-x^2}\, dx = \sqrt{\pi}',
     r'\int_{-\infty}^{\infty} e^{-x^2}\, dx = \sqrt{2\pi}', True),
    # corruption INSIDE the integral: residue keeps the ∫ → fail closed, no evaluation
    (r'\int_{-\infty}^{\infty} e^{-x^2}\, dx = \sqrt{\pi}',
     r'\int_{-\infty}^{\infty} e^{-x^3}\, dx = \sqrt{\pi}', False),
])
def test_differs_never_evaluates_infinite_integral(clean, corrupted, want):
    """The Gaussian integral hangs sympy's ``simplify``; the residue approach must return
    quickly for both an outside-corruption (verifiable) and an inside one (fail closed)."""
    with _Timer() as t:
        assert differs(clean, corrupted) is want
    assert t.elapsed < 10, f'took {t.elapsed:.1f}s — integral was evaluated'


def test_differs_verifies_finite_derivative():
    """A single-token corruption inside a FINITE heavy op (here d/dx) must still verify via
    the finite-doit hybrid, not be dropped like the infinite integral."""
    with _Timer() as t:
        assert differs(r'\frac{d}{dx} x^n = n x^{n-1}',
                       r'\frac{d}{dx} x^n = n x^{n-2}') is True
    assert t.elapsed < 10


# --- pool construction -----------------------------------------------------

def test_pool_entries_have_stable_content_derived_ids():
    eq = Equation(label='Kinetic energy', latex=r'E = \frac{1}{2}mv^2')
    first, _ = build_pool(eq, ALL)
    second, _ = build_pool(eq, ALL)
    assert first and [e['id'] for e in first] == [e['id'] for e in second]


def test_pool_indices_are_one_based_into_eligible_tokens():
    eq = Equation(label='Einstein', latex=r'E = mc^2')
    pool, _ = build_pool(eq, ALL)
    assert pool and all(e['i'] >= 1 for e in pool)


def test_pool_respects_pin():
    eq = Equation(label='Einstein', latex=r'E = mc^2')
    unpinned, _ = build_pool(eq, ALL)
    exponent_pos = [e['i'] for e in unpinned if e['type'] == 'exponent_off_by_one']
    assert exponent_pos
    pinned, _ = build_pool(Equation('Einstein', r'E = mc^2', pin=[exponent_pos[0]]), ALL)
    assert all(e['i'] != exponent_pos[0] for e in pinned)


def test_pool_is_capped_never_padded():
    eq = Equation(label='Long', latex=r'y = a + b + c + d + e + f + g')
    pool, _ = build_pool(eq, ALL, pool_size=3)
    assert len(pool) == 3
    tiny, _ = build_pool(Equation('Tiny', r'F = ma'), ALL)
    assert len(tiny) < 12  # fewer survivors ship as fewer, not duplicated


def test_bad_pairs_block_overlapping_edits():
    """Two edits to the same span can't both be shown; they'd fight over one token."""
    eq = Equation(label='Einstein', latex=r'E = mc^2')
    pool, bad = build_pool(eq, ALL)
    exps = [e['id'] for e in pool if e['type'] == 'exponent_off_by_one']
    if len(exps) >= 2:
        assert any(sorted(p) == sorted(exps[:2]) for p in bad)


def test_bad_pairs_are_ids_not_positions():
    eq = Equation(label='Kinetic energy', latex=r'E = \frac{1}{2}mv^2')
    pool, bad = build_pool(eq, ALL)
    ids = {e['id'] for e in pool}
    assert all(a in ids and b in ids for a, b in bad)


# --- broader taxonomy ------------------------------------------------------

def test_variable_swap_treats_adjacent_letters_as_separate_variables():
    """``mc`` is m·c in LaTeX, not a two-letter name — both must be swappable."""
    assert {s.text for s in _variable_swap_spans(r'E = mc^2')} == {'E', 'm', 'c'}


def test_variable_swap_treats_greek_as_whole_variable_not_letters():
    """\sigma is one variable (swappable as a whole), never its internal letters s,i,g,m,a."""
    texts = {s.text for s in _variable_swap_spans(r'f = \sigma x')}
    assert 's' not in texts and 'i' not in texts   # no macro-internal corruption
    assert '\\sigma' in texts                       # but sigma itself is a candidate


def test_variable_swap_needs_two_distinct_variables():
    assert _variable_swap_spans(r'x = x') == []


def test_constant_perturb_ignores_exponents():
    """Exponents are `exponent_off_by_one`'s job; double-generating them would collide."""
    assert _constant_spans(r'mc^2') == []
    assert {s.text for s in _constant_spans(r'\frac{1}{2}')} == {'2', '1', '3'}


# --- pool health -----------------------------------------------------------

def test_pool_warnings_flag_unusable_card():
    eq = Equation(label='Vector', latex=r'\nabla \times \mathbf{E} = 0')
    pool, bad = build_pool(eq, ALL)
    assert any('unusable' in w for w in pool_warnings(eq, pool, bad))


def test_pool_warnings_silent_on_healthy_pool():
    eq = Equation(label='Lorentz', latex=r'\gamma = \frac{1}{\sqrt{1-\frac{v^2}{c^2}}}')
    pool, bad = build_pool(eq, ALL)
    assert pool_warnings(eq, pool, bad) == []


def test_valid_pairs_excludes_blocked():
    pool = [{'id': 'a'}, {'id': 'b'}, {'id': 'c'}]
    assert valid_pairs(pool, [['a', 'b']]) == 2


def test_variable_swap_never_touches_an_operator_name():
    """Corrupting the 'a' in \\operatorname{Var} yields "VVr" — nonsense that gives itself
    away without knowing the formula. Found by driving the real deck, not by unit tests."""
    spans = _variable_swap_spans(r'\operatorname{Var}(X) = Y')
    assert {s.text for s in spans} == {'X', 'Y'}


def test_variable_swap_still_works_around_name_macros():
    assert {s.text for s in _variable_swap_spans(r'\operatorname{Var}(X) = n p')} == {'X', 'n', 'p'}


# --- deck classification (2-error vs 1-error split) ------------------------

def test_classify_drops_empty_pool():
    assert classify([], []) == 'drop'


def test_classify_two_needs_enough_pairs():
    eq = Equation(label='Lorentz', latex=r'\gamma = \frac{1}{\sqrt{1-\frac{v^2}{c^2}}}')
    pool, bad = build_pool(eq, ALL)
    assert classify(pool, bad) == 'two'   # many valid pairs


def test_classify_one_for_thin_pool():
    # exactly one valid pair (< the 3-pair threshold) → the one-error deck
    pool = [{'id': 'a', 'i': 1, 'to': 'x', 'type': 't'},
            {'id': 'b', 'i': 2, 'to': 'y', 'type': 't'}]
    assert classify(pool, []) == 'one'


# --- Greek-letter variables ------------------------------------------------

def test_variable_swap_recognizes_greek_letters():
    """Greek letters are variables/parameters; confusing X for lambda is a real error."""
    texts = {s.text for s in _variable_swap_spans(r'\operatorname{Var}(X) = \lambda')}
    assert texts == {'X', r'\lambda'}


def test_variable_swap_excludes_pi_as_a_constant():
    """\\pi is the constant, not a free variable — never a swap candidate."""
    texts = {s.text for s in _variable_swap_spans(r'f = \frac{1}{\sigma\sqrt{2\pi}}')}
    assert r'\pi' not in texts


def test_poisson_is_usable_after_greek_support():
    """Var(X)=lambda was dropped (pool=0) when Greek letters were invisible; now it has a
    verified corruption (the RHS lambda->X; the LHS X is inside Var(...) and stays opaque)."""
    eq = Equation(label='Poisson', latex=r'\operatorname{Var}(X) = \lambda')
    pool, bad = build_pool(eq, ALL)
    assert pool and classify(pool, bad) == 'one'
