"""LaTeX equations → MathML with per-token handles, for the quiz's `error-spot` mode.

The quiz shows a rendered equation with exactly two tokens silently corrupted and asks
which ones are wrong. That needs every candidate token to be individually selectable, so
the artifact ships **baked MathML** with an ``id`` on each eligible token — the client
injects the markup and never runs a math library (works offline, and there is no
Python↔JS rendering parity to maintain).

Markup is identical for clean and corrupted tokens: a corruption is applied by the client
swapping one token's *text*, never by wrapping it. Anything else would leak the answer
through the DOM or through renderer spacing.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import latex2mathml.converter

_MML = 'http://www.w3.org/1998/Math/MathML'
_TOKEN_TAGS = ('mi', 'mn', 'mo')

# Tokens a user can click but that must never be corrupted. Delimiters would render
# malformed or be spotted without knowing the formula; accents emit as standalone <mo>
# (``\hat{H}`` → ``H`` plus a bare ``^``), which is meaningless to corrupt on its own.
_DELIMITERS = frozenset('()[]{}|⟨⟩‖')
_ACCENTS = frozenset('^~¯˙˜→')


@dataclass
class Equation:
    """One studied equation. ``latex`` is canonical and *is* the FSRS item string, so it
    must never be regenerated from the MathML — a whitespace drift would mint a new key."""
    label: str
    latex: str
    source: str = ''
    pin: list[int] = field(default_factory=list)


def load_equations(cfg: dict) -> list[Equation]:
    """Read the config's ``equations:`` block. Equations are **curated, not extracted** —
    an article's wikitext holds every ``<math>`` on the page (derivation steps, special
    cases), with nothing marking which is *the* formula; that choice stays human."""
    return [Equation(label=e['label'], latex=e['latex'],
                     source=e.get('source', ''), pin=list(e.get('pin', [])))
            for e in cfg.get('equations', [])]


def to_mathml(latex: str) -> str:
    """Convert LaTeX to a MathML document string."""
    return latex2mathml.converter.convert(latex)


def _token_elements(root: ET.Element) -> list[ET.Element]:
    """Every <mi>/<mn>/<mo> in document order — the tokens a reader sees as separate."""
    return [e for e in root.iter() if e.tag.split('}')[-1] in _TOKEN_TAGS]


def token_texts(mathml: str) -> list[str]:
    """Token strings in document order. Used to locate which token a corruption changed,
    by diffing a corrupted equation's tokens against the clean one's."""
    return [(e.text or '') for e in _token_elements(ET.fromstring(mathml))]


def _is_differential(elems: list[ET.Element], i: int) -> bool:
    """``dx`` in an integral: a lone ``d`` directly before another identifier. It looks
    like a variable to a tokenizer but corrupting it is meaningless."""
    e = elems[i]
    if e.tag.split('}')[-1] != 'mi' or (e.text or '') != 'd':
        return False
    nxt = elems[i + 1] if i + 1 < len(elems) else None
    return nxt is not None and nxt.tag.split('}')[-1] == 'mi'


def eligible_indices(mathml: str) -> list[int]:
    """0-based indices of tokens the user may click.

    Deliberately broader than the set we corrupt: the haystack has to stay large, or
    picking the two wrong tokens becomes a guess among a handful of candidates.
    """
    elems = _token_elements(ET.fromstring(mathml))
    out = []
    for i, e in enumerate(elems):
        text = (e.text or '').strip()
        if not text or text in _DELIMITERS or text in _ACCENTS or _is_differential(elems, i):
            continue
        out.append(i)
    return out


def annotate(mathml: str, indices: list[int]) -> str:
    """Return the MathML with ``id="tok-N"`` (N 1-based, matching ``wrong_tokens``) on each
    eligible token. Ids are assigned over eligible tokens only — the client's index space
    must equal the display's, since scoring is pure set arithmetic over those indices."""
    ET.register_namespace('', _MML)
    root = ET.fromstring(mathml)
    elems = _token_elements(root)
    for n, idx in enumerate(indices, start=1):
        elems[idx].set('id', f'tok-{n}')
    return ET.tostring(root, encoding='unicode')
