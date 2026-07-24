"""Generated, verified corruptions for `error-spot` equation decks.

A corruption is a **single-token substitution**: the client renders the clean MathML once
and swaps two tokens' text. That keeps artifacts small and makes clean and corrupted
markup structurally identical, but it also means structural errors (swapped
numerator/denominator, dropped factor) are out of scope — they don't map to one token.

Candidates are generated on the **LaTeX**, because that is what sympy can verify, and the
token index is then *derived* by diffing the corrupted MathML's tokens against the clean
one's. Deriving rather than assuming means the index and the verification can never
disagree about which token changed.

Verification fails **closed**: a candidate ships only if sympy positively proves it
differs from the original. sympy's LaTeX parser silently turns unknown macros (``\\mathbf``,
``\\hat``, ``\\operatorname``, ``\\pm``) into ordinary symbols rather than raising, so a
parse "succeeding" proves nothing — hence the mis-parse guard below.
"""

from __future__ import annotations

import hashlib
import re
import warnings
from dataclasses import dataclass

from .equations import Equation, eligible_indices, to_mathml, token_texts
from .normalise import in_opaque, normalise, opaque_spans

# Macro names sympy invents as free symbols when it cannot parse the real notation.
# Their presence means the parse is not faithful, so no verdict can be trusted.
_MISPARSE_MARKERS = frozenset({'mathbf', 'hat', 'operatorname', 'pm', 'nabla', 'vec', 'mathrm'})

# Macros whose braced argument names a function or is styled text, not variables.
_NAME_MACROS = frozenset({'operatorname', 'mathrm', 'text', 'textbf', 'mathbf', 'mathit'})

# Single-symbol Greek letters used as variables/parameters, so variable_swap can confuse
# them like ASCII letters. Deliberately excludes \pi/\Pi (usually the constant / a product)
# and every operator macro (\sum, \int, \partial, \nabla), which are not variables.
_GREEK_VARS = frozenset({
    'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'varepsilon', 'zeta', 'eta', 'theta',
    'vartheta', 'iota', 'kappa', 'lambda', 'mu', 'nu', 'xi', 'rho', 'varrho', 'sigma',
    'varsigma', 'tau', 'upsilon', 'phi', 'varphi', 'chi', 'psi', 'omega',
    'Gamma', 'Delta', 'Theta', 'Lambda', 'Xi', 'Sigma', 'Upsilon', 'Phi', 'Psi', 'Omega',
})

_SUP_BRACED = re.compile(r'\^\{(\d+)\}')
_SUP_BARE = re.compile(r'\^(\d)')


@dataclass(frozen=True)
class _Span:
    """A candidate edit to the LaTeX source: replace [start, end) with ``text``."""
    start: int
    end: int
    text: str
    type: str


def _sign_flip_spans(latex: str) -> list[_Span]:
    """Flip a binary + / −. The commonest real error and the one dimensional analysis
    cannot catch, so it stays useful even once the deck is familiar."""
    out = []
    for m in re.finditer(r'[+-]', latex):
        i = m.start()
        if latex[max(0, i - 1):i] == '\\':  # part of a macro, not an operator
            continue
        out.append(_Span(i, i + 1, '-' if m.group() == '+' else '+', 'sign_flip'))
    return out


def _exponent_spans(latex: str) -> list[_Span]:
    """Nudge an integer exponent by one. Dimensionally detectable, which makes it a good
    early-difficulty corruption and a candidate for retirement once that gets automatic."""
    out = []
    for rx, wrap in ((_SUP_BRACED, '{%s}'), (_SUP_BARE, '%s')):
        for m in rx.finditer(latex):
            n = int(m.group(1))
            for new in {n + 1, n - 1} - {n, 0}:
                out.append(_Span(m.start(1) - (1 if wrap == '{%s}' else 0),
                                 m.end(1) + (1 if wrap == '{%s}' else 0),
                                 wrap % new, 'exponent_off_by_one'))
    return out


def _constant_spans(latex: str) -> list[_Span]:
    """Nudge a standalone integer coefficient. Applies far more widely than the exponent
    and sign rules, which each need a specific feature the equation may simply not have."""
    out = []
    for m in re.finditer(r'(?<![\^\\\d])(\d+)', latex):
        n = int(m.group(1))
        for new in {n + 1, n - 1} - {n, 0}:
            out.append(_Span(m.start(1), m.end(1), str(new), 'constant_perturb'))
    return out


def _variable_swap_spans(latex: str) -> list[_Span]:
    """Substitute one variable for another already in the equation. Confusing ``m`` for
    ``v`` — or a random variable ``X`` for a parameter ``\\lambda`` — is a real recall
    failure, and reusing an in-equation symbol keeps the result plausible."""
    toks = _variable_tokens(latex)
    distinct = sorted({raw for _, _, raw in toks})
    if len(distinct) < 2:
        return []
    return [_Span(start, end, other, 'variable_swap')
            for start, end, raw in toks for other in distinct if other != raw]


def _variable_tokens(latex: str) -> list[tuple[int, int, str]]:
    """``(start, end, raw)`` for each single-symbol variable — an ASCII letter or a
    whitelisted Greek macro (``\\lambda``, ``\\mu``, …).

    Greek letters *are* variables (a rate ``\\lambda``, a mean ``\\mu``); collecting only
    ASCII silently thinned pools and dropped equations whose only symbols were Greek (e.g.
    Poisson ``Var(X)=\\lambda``). Operators (``\\sum``, ``\\int``, ``\\partial``) stay out
    because they aren't in the whitelist. Adjacent ASCII letters are *separate* variables
    (``mc`` is m·c), so macros must be consumed explicitly rather than by letter runs.
    """
    out, i, n = [], 0, len(latex)
    while i < n:
        if latex[i] == '\\':
            start = i
            i += 1
            name_start = i
            while i < n and latex[i].isalpha():  # consume the macro name
                i += 1
            name = latex[name_start:i]
            if name in _GREEK_VARS:
                out.append((start, i, latex[start:i]))
                continue
            # A name-carrying macro's argument is an *identifier*, not variables: corrupting
            # the 'a' in \operatorname{Var} yields "VVr", nonsense that gives itself away.
            if name in _NAME_MACROS and i < n and latex[i] == '{':
                depth = 0
                while i < n:
                    if latex[i] == '{':
                        depth += 1
                    elif latex[i] == '}':
                        depth -= 1
                        if depth == 0:
                            i += 1
                            break
                    i += 1
            continue
        if latex[i].isalpha():
            out.append((i, i + 1, latex[i]))
        i += 1
    return out


_GENERATORS = {
    'sign_flip': _sign_flip_spans,
    'exponent_off_by_one': _exponent_spans,
    'constant_perturb': _constant_spans,
    'variable_swap': _variable_swap_spans,
}


def apply_spans(latex: str, spans: list[_Span]) -> str:
    """Apply non-overlapping spans right-to-left so earlier offsets stay valid."""
    out = latex
    for s in sorted(spans, key=lambda s: s.start, reverse=True):
        out = out[:s.start] + s.text + out[s.end:]
    return out


def _diff_expr(latex: str):
    """Parse to ``lhs - rhs`` (or the bare expression), or None if unparseable/mis-parsed.

    Parses the **normalised** form: the notation worth studying (``P(A\\mid B)``,
    ``\\operatorname{Var}(X)``, ``E[X^2]``) is not what sympy accepts. Only verification
    sees this rewrite — the displayed MathML is always built from the original LaTeX.
    """
    from sympy.parsing.latex import parse_latex
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            e = parse_latex(normalise(latex))
    except Exception:
        return None
    expr = e.lhs - e.rhs if hasattr(e, 'lhs') else e
    if {str(s) for s in expr.free_symbols} & _MISPARSE_MARKERS:
        return None
    return expr


# Unevaluated operators whose *value* we must never force. If a single-token corruption
# lands outside one of these, the operator subtree is identical on both sides and cancels in
# ``a - b`` before it is ever evaluated; if the residue still contains one, the corruption
# landed *inside* it and we cannot verify cheaply — reject (fail closed), exactly as
# ``opaque_spans`` bars corruption inside argument lists.
_HEAVY_OPS = ('Integral', 'Sum', 'Product', 'Limit', 'Derivative', 'Order')
_SAMPLE_VALUES = (
    (2, 3, 5, 7, 11, 13, 17, 19),
    (23, 4, 9, 6, 15, 8, 21, 10),
    (3, 7, 2, 13, 5, 11, 19, 17),
    (5, 2, 7, 3, 11, 4, 6, 8),
    (7, 11, 13, 2, 3, 5, 23, 9),
)


def _heavy_ops():
    import sympy
    return tuple(getattr(sympy, n) for n in _HEAVY_OPS if hasattr(sympy, n))


def _numeric_verdict(a, b, d) -> bool:
    """Decide differ-vs-equivalent for a residue ``d = a - b`` by numeric sampling — never
    symbolic ``simplify`` (which would evaluate an integral and hang).

    Returns True only when the two are proven different: ``d`` is non-zero at some sample
    *and* ``a``/``b`` are not a constant multiple of each other (which would be the same
    equation, e.g. negated both sides). Inconclusive → False (fail closed).
    """
    from sympy.core.function import AppliedUndef
    from sympy import Derivative, Limit
    # Atoms sympy can't ``evalf`` to a number — undefined function applications (Var(X),
    # E[X^2]→E(X^2), P(A,B)) and unevaluated Derivative/Limit of an undefined function. Treat
    # each as opaque and give it a numeric value, substituted *before* inner symbols. (Definite
    # integrals/sums DO evalf to a value via quadrature, so they are left for evalf.)
    opaque = a.atoms(AppliedUndef, Derivative, Limit) | b.atoms(AppliedUndef, Derivative, Limit)
    funcs = sorted(opaque, key=str)
    syms = sorted(a.free_symbols | b.free_symbols, key=str)
    atoms = funcs + syms
    d_vals, ratios, valid = [], [], 0
    for row in _SAMPLE_VALUES:
        assign = {atom: row[i % len(row)] + i for i, atom in enumerate(atoms)}
        fmap = {f: assign[f] for f in funcs}
        smap = {s: assign[s] for s in syms}
        try:
            dv = complex(d.subs(fmap).subs(smap).evalf())
            av = complex(a.subs(fmap).subs(smap).evalf())
            bv = complex(b.subs(fmap).subs(smap).evalf())
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if any(x != x or abs(x) == float('inf') for x in (dv.real, dv.imag)):
            continue
        valid += 1
        d_vals.append(dv)
        if abs(bv) > 1e-9:
            ratios.append(av / bv)
    if valid < 2:
        return False                                   # inconclusive → fail closed
    if all(abs(v) < 1e-9 for v in d_vals):
        return False                                   # numerically equivalent
    if (len(ratios) >= 2 and abs(ratios[0]) > 1e-9
            and all(abs(r - ratios[0]) < 1e-6 for r in ratios)):
        return False                                   # same equation up to a nonzero constant
    return True


def differs(clean: str, corrupted: str) -> bool:
    """True only when the two equations are *proven* to differ.

    Works on the residue ``a - b`` (``lhs - rhs`` of each). Identical subtrees cancel, so a
    corruption outside an ``\\int``/``\\sum``/``\\lim`` never forces that operator's value;
    a residue that still holds one is rejected (the corruption was inside it). The remaining
    algebraic residue is judged by numeric sampling, up to a nonzero constant factor so
    negating both sides reads as equivalent. Anything unparseable, mis-parsed, operator-bound,
    or inconclusive returns False — discarding a possibly-good corruption rather than risking a
    "mistake" the user is right not to find.
    """
    from sympy import S
    a, b = _diff_expr(clean), _diff_expr(corrupted)
    if a is None or b is None:
        return False
    try:
        inf = (S.Infinity, S.NegativeInfinity, S.ComplexInfinity)
        # Symbolically evaluate only when there is no infinite bound: ``.doit()`` on
        # ``\int_{-\infty}^{\infty}`` is the sole real hang; finite integrals, definite sums
        # and derivatives evaluate fast, recovering e.g. ``d/dx x^n = n x^{n-1}``.
        if not (a.has(*inf) or b.has(*inf)):
            a, b = a.doit(), b.doit()
        d = a - b
        if d == 0:
            return False
        # A residue still holding a heavy op is unprovable here: either an infinite-bound
        # operator (never evaluated) or a corruption *inside* an unevaluable one — reject.
        # (Numerically-valued definite integrals/sums cancel out or fall to evalf.)
        if d.has(*_heavy_ops()):
            return False
        return _numeric_verdict(a, b, d)
    except Exception:
        return False


def _entry_id(index: int, to: str, type_: str) -> str:
    """Content-derived so an unchanged corruption keeps its id across re-exports — the
    quiz's retirement config and ``bad_pairs`` both reference these."""
    return hashlib.sha256(f'{index}|{to}|{type_}'.encode()).hexdigest()[:6]


def _single_token_change(clean_tokens: list[str], corrupted_latex: str) -> tuple[int, str] | None:
    """Locate the one token a corruption changed, or None if it changed zero or several
    (a substitution that perturbs the whole tree isn't a single-token corruption)."""
    try:
        after = token_texts(to_mathml(corrupted_latex))
    except Exception:
        return None
    if len(after) != len(clean_tokens):
        return None
    diffs = [i for i, (a, b) in enumerate(zip(clean_tokens, after)) if a != b]
    return (diffs[0], after[diffs[0]]) if len(diffs) == 1 else None


def build_pool(eq: Equation, types: list[str], pool_size: int = 12) -> tuple[list[dict], list[list[str]]]:
    """Verified corruption pool + blocked pairs for one equation.

    Never padded: an equation that yields fewer survivors ships with fewer, mirroring
    ``build_choices``. ``bad_pairs`` lists id pairs whose two corruptions cancel back into
    a true equation — the pairwise check is the load-bearing one here, since the quiz shows
    exactly two at once and each would pass a solo check.
    """
    mathml = to_mathml(eq.latex)
    clean_tokens = token_texts(mathml)
    eligible = eligible_indices(mathml)
    pinned = {eligible[p - 1] for p in eq.pin if 1 <= p <= len(eligible)}

    opaque = opaque_spans(eq.latex)
    pool: list[dict] = []
    spans_by_id: dict[str, _Span] = {}
    for t in types:
        for span in _GENERATORS[t](eq.latex):
            if len(pool) >= pool_size:
                break
            if in_opaque(opaque, span.start, span.end):
                continue  # verification can't see inside an argument list — see normalise
            corrupted = apply_spans(eq.latex, [span])
            change = _single_token_change(clean_tokens, corrupted)
            if change is None:
                continue
            idx, to = change
            if idx not in eligible or idx in pinned:
                continue
            if not differs(eq.latex, corrupted):
                continue
            eid = _entry_id(idx, to, t)
            if eid in spans_by_id:
                continue
            pool.append({'id': eid, 'i': eligible.index(idx) + 1, 'to': to, 'type': t})
            spans_by_id[eid] = span

    bad_pairs = []
    for a in range(len(pool)):
        for b in range(a + 1, len(pool)):
            sa, sb = spans_by_id[pool[a]['id']], spans_by_id[pool[b]['id']]
            if not (sa.end <= sb.start or sb.end <= sa.start):
                bad_pairs.append([pool[a]['id'], pool[b]['id']])  # overlapping edits
                continue
            if not differs(eq.latex, apply_spans(eq.latex, [sa, sb])):
                bad_pairs.append([pool[a]['id'], pool[b]['id']])
    return pool, bad_pairs


def valid_pairs(pool: list[dict], bad_pairs: list[list[str]]) -> int:
    """How many distinct two-error displays this equation can actually produce."""
    blocked = {tuple(sorted(p)) for p in bad_pairs}
    ids = [e['id'] for e in pool]
    return sum(1 for i, a in enumerate(ids) for b in ids[i + 1:]
               if tuple(sorted((a, b))) not in blocked)


def pool_warnings(eq: Equation, pool: list[dict], bad_pairs: list[list[str]]) -> list[str]:
    """Flag equations whose pool can't sustain the quiz's two-error display.

    Silent thinness is the failure mode to avoid: a card that always shows the same pair
    teaches token positions, and one with no valid pair can't be shown at all.
    """
    out = []
    if not (pairs := valid_pairs(pool, bad_pairs)):
        out.append(f'{eq.label!r}: no valid two-error pair (pool={len(pool)}) — card unusable')
    elif pairs < 3:
        out.append(f'{eq.label!r}: only {pairs} distinct two-error pair(s) — positions will repeat')
    if pool and len({e['type'] for e in pool}) == 1:
        out.append(f'{eq.label!r}: every corruption is {pool[0]["type"]} — one trick to learn')
    return out


_TWO_ERROR_MIN_PAIRS = 3


def classify(pool: list[dict], bad_pairs: list[list[str]]) -> str:
    """Which fixed-count deck an equation belongs in.

    Splitting by supportable count (rather than varying the count per showing) keeps each
    deck's difficulty honest: a "2 errors" card the pool can't vary would repeat the same
    two positions, teaching positions instead of the formula.

    - ``'two'``  — enough distinct valid pairs to vary a two-error display
    - ``'one'``  — a usable pool but too few pairs; show a single error
    - ``'drop'`` — no verified corruption at all; the equation is unusable
    """
    if not pool:
        return 'drop'
    if valid_pairs(pool, bad_pairs) >= _TWO_ERROR_MIN_PAIRS:
        return 'two'
    return 'one'
