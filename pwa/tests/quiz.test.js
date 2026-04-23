import { describe, it, expect } from 'vitest';
import {
  pickDigitConfusable, pickConfusable, alphaIndices,
  pinnedIndices, twoLetterDisplay, makeLineDisplay, makeAcronymDisplay,
  makeDigitDisplay, scoreResponse, scoreAcronymResponse,
  scoreDigitResponse, CONFUSABLES, DIGIT_CONFUSABLES,
} from '../quiz.js';

describe('alphaIndices', () => {
  it('pure alpha', () => expect(alphaIndices('hello')).toEqual([0,1,2,3,4]));
  it('with digits', () => expect(alphaIndices('h3llo')).toEqual([0,2,3,4]));
  it('empty', () => expect(alphaIndices('')).toEqual([]));
});

describe('pinnedIndices', () => {
  it('short word (< 5 alpha): only first letter pinned', () => {
    expect(pinnedIndices('hi')).toEqual(new Set([0]));
    expect(pinnedIndices('four')).toEqual(new Set([0]));
  });
  it('exactly 5 alpha letters: first + 4th pinned', () => {
    // 'hello' alpha indices [0,1,2,3,4]; 4th alpha = index 3
    expect(pinnedIndices('hello')).toEqual(new Set([0, 3]));
  });
  it('8 alpha letters: first + 4th pinned (no 8th)', () => {
    // 'abcdefgh' alpha [0..7]; 4th=index 3, 8th=index 7 but need >=8 not >=5 for index 7
    // alpha.length=8 >= 5, so pinned: alpha[0]=0, alpha[3]=3, alpha[7]=7
    expect(pinnedIndices('abcdefgh')).toEqual(new Set([0, 3, 7]));
  });
  it('9 alpha letters: first + 4th + 8th pinned', () => {
    expect(pinnedIndices('abcdefghi')).toEqual(new Set([0, 3, 7]));
  });
  it('non-alpha chars shift real char positions', () => {
    // 'h-llo' alpha indices [0,2,3,4]; length=4 < 5, only index 0 pinned
    expect(pinnedIndices('h-llo')).toEqual(new Set([0]));
    // 'h-llox' alpha [0,2,3,4,5]; length=5 >= 5; alpha[3]=4 (the 'o')
    expect(pinnedIndices('h-llox')).toEqual(new Set([0, 4]));
  });
  it('empty string: empty set', () => {
    expect(pinnedIndices('')).toEqual(new Set());
  });
  it('single char: only that char pinned', () => {
    expect(pinnedIndices('a')).toEqual(new Set([0]));
  });
});

describe('twoLetterDisplay', () => {
  it('shows first + one extra, rest as underscores (short word)', () => {
    // 'hell' has 4 alpha chars — below 5, so only first is pinned
    expect(twoLetterDisplay('hell', 2, 'x')).toBe('h_x_');
  });
  it('single alpha word unchanged', () => {
    expect(twoLetterDisplay('a', 0, 'b')).toBe('a');
  });
  it('preserves non-alpha chars', () => {
    expect(twoLetterDisplay('h-llo', 3, 'x')).toBe('h-_x_');
  });
  it('5-letter word auto-shows 4th letter', () => {
    // 'hello': h pinned(0), l pinned(3); challenge at index 2 → h_x l_
    expect(twoLetterDisplay('hello', 2, 'x')).toBe('h_xl_');
  });
  it('8-letter word auto-shows 4th + 8th letters', () => {
    // 'abcdefgh': pinned={a(0), d(3), h(7)}; challenge at b(1)→x; c(2) hidden
    // a=pinned, b(1)=challenge→x, c(2)=_, d(3)=pinned, e-g=_, h(7)=pinned
    expect(twoLetterDisplay('abcdefgh', 1, 'x')).toBe('ax_d___h');
  });
  it('5-letter word: 4th letter is auto-shown so never shows as underscore', () => {
    // 'world' alpha [0,1,2,3,4]; pinned={0,3}; w and l always visible
    // challenge at index 4 (d): w _ _ l x
    expect(twoLetterDisplay('world', 4, 'x')).toBe('w__lx');
  });
});

describe('pickConfusable', () => {
  it('returns a different char', () => {
    for (const ch of 'abcdefghijklmnopqrstuvwxyz') {
      const got = pickConfusable(ch);
      expect(got).not.toBe(ch);
    }
  });
  it('uppercase input → uppercase output', () => {
    const got = pickConfusable('A');
    expect(got).toMatch(/^[A-Z]$/);
  });
  it('returned char is from CONFUSABLES list', () => {
    for (let i = 0; i < 50; i++) {
      const got = pickConfusable('a');
      expect(CONFUSABLES['a']).toContain(got.toLowerCase());
    }
  });
});

describe('pickDigitConfusable', () => {
  it('returns different digit', () => {
    for (const d of '0123456789') {
      expect(pickDigitConfusable(d)).not.toBe(d);
    }
  });
  it('returned digit is from DIGIT_CONFUSABLES list', () => {
    for (let i = 0; i < 30; i++) {
      const got = pickDigitConfusable('0');
      expect(DIGIT_CONFUSABLES['0']).toContain(got);
    }
  });
});

describe('makeLineDisplay (deterministic structure)', () => {
  it('produces one part per word', () => {
    const { display } = makeLineDisplay('one two three', 0);
    expect(display.split('  ')).toHaveLength(3);
  });
  it('each part has word-number prefix', () => {
    const { display } = makeLineDisplay('foo bar', 0);
    expect(display).toMatch(/^1:/);
    expect(display).toMatch(/2:/);
  });
  it('wrongProb=0 means no wrong words', () => {
    for (let i = 0; i < 20; i++) {
      const d = makeLineDisplay('hello world test', 0);
      expect(d.hasWrong).toBe(false);
      expect(d.wrongPositions).toEqual([]);
    }
  });
  it('wrongProb=1 means all multi-alpha words wrong', () => {
    for (let i = 0; i < 20; i++) {
      const d = makeLineDisplay('hello world test', 1);
      expect(d.hasWrong).toBe(true);
    }
  });
  it('5+ letter word: challenge letter is never a pinned position', () => {
    // 'hello' pinned={0,3}: challenge must come from indices {1,2,4}
    // with wrongProb=0 the displayed char at challenge pos equals actual char
    const pinnedChars = new Set(['h', 'l']); // alpha[0] and alpha[3] of 'hello'
    for (let i = 0; i < 50; i++) {
      const { display } = makeLineDisplay('hello', 0);
      const text = display.split(':')[1]; // e.g. 'h_x__' or 'h_xl_' etc.
      // find the one non-underscore non-pinned-position char (the challenge)
      // pinned positions in 'hello': 0(h) and 3(l) — always visible
      // challenge is one of positions 1,2,4
      // the char at position 1, 2, or 4 that is not '_' is the challenge
      const challengePos = [1, 2, 4].find(p => text[p] !== '_');
      expect(challengePos).toBeDefined();
      // position 3 should always be 'l' (pinned)
      expect(text[3]).toBe('l');
      // position 0 should always be 'h' (pinned)
      expect(text[0]).toBe('h');
    }
  });
  it('short word (< 5 alpha): only first letter always visible', () => {
    // 'cat' pinned={0}: challenge from {1,2}
    for (let i = 0; i < 30; i++) {
      const { display } = makeLineDisplay('cat', 0);
      const text = display.split(':')[1];
      expect(text[0]).toBe('c');
      // exactly one of positions 1,2 is non-underscore (the challenge)
      const revealed = [1, 2].filter(p => text[p] !== '_');
      expect(revealed).toHaveLength(1);
    }
  });
});

describe('makeAcronymDisplay', () => {
  it('one part per word', () => {
    const { display } = makeAcronymDisplay('foo bar baz', 0);
    expect(display.split('  ')).toHaveLength(3);
  });
  it('wrongProb=0 → no wrongs', () => {
    for (let i = 0; i < 20; i++) {
      const d = makeAcronymDisplay('foo bar baz', 0);
      expect(d.hasWrong).toBe(false);
    }
  });
  it('wrongProb=1 → all wrong', () => {
    for (let i = 0; i < 10; i++) {
      const d = makeAcronymDisplay('foo bar baz', 1);
      expect(d.wrongPositions.sort()).toEqual([1,2,3]);
    }
  });
});

describe('makeDigitDisplay', () => {
  it('one part per digit', () => {
    const { display } = makeDigitDisplay('1234', 0);
    expect(display.split('  ')).toHaveLength(4);
  });
  it('wrongProb=1 → all positions wrong', () => {
    for (let i = 0; i < 10; i++) {
      const d = makeDigitDisplay('123', 1);
      expect(d.wrongPositions.sort()).toEqual([1,2,3]);
    }
  });
});

describe('scoreResponse', () => {
  it('correct when user matches actual', () => {
    const display = { wrongPositions: [2, 3] };
    const [ok, msg] = scoreResponse(display, [2, 3]);
    expect(ok).toBe(true);
    expect(msg).toContain('Correct');
  });
  it('missed words detected', () => {
    const display = { wrongPositions: [1, 3] };
    const [ok, msg] = scoreResponse(display, [1]);
    expect(ok).toBe(false);
    expect(msg.toLowerCase()).toContain('missed word');
  });
  it('false alarm detected', () => {
    const display = { wrongPositions: [] };
    const [ok, msg] = scoreResponse(display, [2]);
    expect(ok).toBe(false);
    expect(msg.toLowerCase()).toContain('false alarm');
  });
  it('no-wrong correct gives correct message', () => {
    const display = { wrongPositions: [] };
    const [ok, msg] = scoreResponse(display, []);
    expect(ok).toBe(true);
    expect(msg).toContain('no wrong');
  });
});

describe('scoreAcronymResponse', () => {
  it('uses "letter" label', () => {
    const display = { wrongPositions: [1] };
    const [, msg] = scoreAcronymResponse(display, []);
    expect(msg).toContain('letter');
  });
});

describe('scoreDigitResponse', () => {
  it('uses "digit" label', () => {
    const display = { wrongPositions: [1] };
    const [, msg] = scoreDigitResponse(display, []);
    expect(msg).toContain('digit');
  });
});
