import { describe, it, expect } from 'vitest';
import {
  pickDigitConfusable, pickConfusable, alphaIndices,
  twoLetterDisplay, makeLineDisplay, makeAcronymDisplay,
  makeDigitDisplay, scoreResponse, scoreAcronymResponse,
  scoreDigitResponse, CONFUSABLES, DIGIT_CONFUSABLES,
} from '../quiz.js';

describe('alphaIndices', () => {
  it('pure alpha', () => expect(alphaIndices('hello')).toEqual([0,1,2,3,4]));
  it('with digits', () => expect(alphaIndices('h3llo')).toEqual([0,2,3,4]));
  it('empty', () => expect(alphaIndices('')).toEqual([]));
});

describe('twoLetterDisplay', () => {
  it('shows first + one extra, rest as underscores', () => {
    expect(twoLetterDisplay('hello', 2, 'x')).toBe('h_x__');
  });
  it('single alpha word unchanged', () => {
    expect(twoLetterDisplay('a', 0, 'b')).toBe('a');
  });
  it('preserves non-alpha chars', () => {
    expect(twoLetterDisplay('h-llo', 3, 'x')).toBe('h-_x_');
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
