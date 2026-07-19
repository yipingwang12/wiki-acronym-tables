"""Rewrite real mathematical notation into a form sympy's LaTeX parser handles.

Used **only for verification**. The displayed MathML is always built from the original
LaTeX, so normalisation can be as ugly as it needs to be — it never reaches the user.

The problem it solves: the formulas worth memorising are written in notation sympy cannot
parse (``P(A\\mid B)``, ``\\operatorname{Var}(X)``, ``E[X^2]``, bold vectors). Worse, sympy
does not raise on them — it invents free symbols and returns a confident wrong expression,
so without this layer those equations either fail closed (empty pool) or, if the guard were
relaxed, would ship unverified corruptions.

Rewrites preserve *distinctness*: two expressions that differ must still differ after
normalisation. Where that cannot be guaranteed — an argument list whose internal structure
sympy would not see — the region is reported as **opaque** and corruption is barred inside
it, since an equivalence-preserving edit there (``Var(X+Y)`` → ``Var(Y+X)``) would otherwise
be shipped as a false error.
"""

from __future__ import annotations

import re

# Formatting wrappers with no bearing on the mathematics: strip to the inner symbol.
_STRIP_WRAPPERS = ('mathbf', 'mathrm', 'boldsymbol', 'textbf', 'mathit')
# Wrappers that mean something (an operator, an estimate) — keep them distinct by folding
# the accent into the symbol name rather than discarding it.
_NAME_WRAPPERS = {'hat': 'hat', 'bar': 'bar', 'tilde': 'tilde', 'vec': 'vec'}


def _strip_wrappers(latex: str) -> str:
    for name in _STRIP_WRAPPERS:
        latex = re.sub(r'\\' + name + r'\{([^{}]*)\}', r'\1', latex)
    for name, suffix in _NAME_WRAPPERS.items():
        latex = re.sub(r'\\' + name + r'\{([A-Za-z])\}', r'\1' + suffix, latex)
    return latex


def _operator_names(latex: str) -> str:
    r"""``\operatorname{Var}`` → ``Var``: sympy then reads ``Var(X)`` as a function
    application, which compares correctly (and sees ``Var(X+Y) == Var(Y+X)``)."""
    return re.sub(r'\\operatorname\{([A-Za-z]+)\}', r'\1', latex)


def _expectation_brackets(latex: str) -> str:
    """``E[X^2]`` → ``E(X^2)``. Square brackets around an expectation parse as a list;
    parentheses make it a function application, keeping ``E[X]^2`` and ``E[X^2]`` distinct."""
    return re.sub(r'([A-Z])\[([^\[\]]*)\]', r'\1(\2)', latex)


def _conditionals(latex: str) -> str:
    r"""``P(A\mid B)`` → ``P(A, B)``. A bare ``|`` parses as absolute value; a comma makes it
    an ordered argument list, so ``P(A|B)`` and ``P(B|A)`` stay distinct — which is all
    verification needs, even though the comma loses the 'given' reading."""
    return re.sub(r'\\mid\s*|\s*\|\s*', ', ', latex)


_RULES = (_strip_wrappers, _operator_names, _expectation_brackets, _conditionals)


def normalise(latex: str) -> str:
    """Rewrite ``latex`` into sympy-parsable form. Purely textual and idempotent-ish; the
    result is never displayed."""
    for rule in _RULES:
        latex = rule(latex)
    return latex


def opaque_spans(latex: str) -> list[tuple[int, int]]:
    """Character ranges in the ORIGINAL latex whose internal structure verification cannot
    see through — the argument lists of function-style applications.

    Corruption is barred inside these: sympy compares ``Var(X+Y)`` and ``Var(Y+X)`` as
    equal (good — that is a true equivalence), but a normaliser that flattened arguments
    would not, and any future rule that does would silently ship false errors. Barring
    edits inside argument lists keeps that class of bug unreachable.
    """
    spans = []
    for m in re.finditer(r'(?:\\operatorname\{[A-Za-z]+\}|[A-Za-z])\s*[\(\[]', latex):
        depth, i = 0, m.end() - 1
        while i < len(latex):
            if latex[i] in '([':
                depth += 1
            elif latex[i] in ')]':
                depth -= 1
                if depth == 0:
                    spans.append((m.end(), i))
                    break
            i += 1
    return spans


def in_opaque(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    """True if [start, end) falls inside any opaque region."""
    return any(s <= start and end <= e for s, e in spans)
