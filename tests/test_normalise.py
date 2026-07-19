from deck_generator.corruptions import build_pool, differs
from deck_generator.equations import Equation
from deck_generator.normalise import in_opaque, normalise, opaque_spans

ALL = ['sign_flip', 'exponent_off_by_one', 'constant_perturb', 'variable_swap']


# --- rewrites --------------------------------------------------------------

def test_formatting_wrappers_are_stripped():
    assert normalise(r'\nabla \times \mathbf{E}') == r'\nabla \times E'


def test_meaningful_accents_fold_into_the_name():
    """``\\hat{H}`` is an operator, not decoration — it must stay distinct from plain H."""
    assert normalise(r'\hat{H}\Psi') == r'Hhat\Psi'
    assert normalise(r'\bar{x}') == 'xbar'


def test_operatorname_becomes_a_function():
    assert normalise(r'\operatorname{Var}(X)') == 'Var(X)'


def test_expectation_brackets_become_parentheses():
    assert normalise(r'E[X^2]') == 'E(X^2)'


def test_expectation_of_square_stays_distinct_from_square_of_expectation():
    assert normalise(r'E[X^2]') != normalise(r'(E[X])^2')


def test_conditional_bar_becomes_an_ordered_argument():
    assert normalise(r'P(A\mid B)') == 'P(A, B)'


def test_conditional_direction_is_preserved():
    """P(A|B) and P(B|A) are different probabilities; normalisation must not merge them."""
    assert normalise(r'P(A\mid B)') != normalise(r'P(B\mid A)')


# --- what it unlocks -------------------------------------------------------

def test_real_notation_now_verifies():
    """Before the normaliser these failed closed, so their pools came back empty."""
    assert differs(r'\operatorname{Var}(X) = E[X^2] - (E[X])^2',
                   r'\operatorname{Var}(X) = E[X^2] + (E[X])^2') is True


def test_conditional_swap_is_detected():
    assert differs(r'P(A\mid B) = \frac{P(B\mid A)P(A)}{P(B)}',
                   r'P(A\mid B) = \frac{P(A\mid A)P(A)}{P(B)}') is True


def test_vector_calculus_still_fails_closed():
    """Textual rewriting can't give sympy vector algebra — \\nabla survives as a symbol."""
    assert differs(r'\nabla \times \mathbf{E} = 0', r'\nabla \times \mathbf{E} = 1') is False


# --- opaque regions --------------------------------------------------------

def test_opaque_spans_cover_argument_lists():
    latex = r'\operatorname{Var}(X+Y)'
    spans = opaque_spans(latex)
    assert spans and all(latex[s:e] == 'X+Y' for s, e in spans)


def test_in_opaque_detects_containment():
    assert in_opaque([(5, 10)], 6, 7) is True
    assert in_opaque([(5, 10)], 11, 12) is False


def test_corruption_is_barred_inside_argument_lists():
    """``Var(X+Y)`` → ``Var(Y+X)`` is an equivalence, so an edit in there could ship a
    'mistake' the user is right not to find. Bar the region rather than rely on the CAS."""
    eq = Equation(label='Var of a sum', latex=r'\operatorname{Var}(X+Y) = Z')
    pool, _ = build_pool(eq, ALL)
    inner = opaque_spans(eq.latex)
    assert inner
    assert all(e['type'] != 'sign_flip' for e in pool)  # the only sign lives inside Var(...)
