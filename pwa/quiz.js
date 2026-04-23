/** Blindman's bluff quiz display + scoring. Port of quiz.py. */

export const DIGIT_CONFUSABLES = {
  '0': ['8', '6'], '1': ['7', '4'], '2': ['7', '3'], '3': ['8', '2'],
  '4': ['1', '9'], '5': ['6', '3'], '6': ['9', '0'], '7': ['1', '2'],
  '8': ['3', '0'], '9': ['6', '4'],
};

export const CONFUSABLES = {
  'a': ['e','o','u'], 'b': ['d','p','q','h'], 'c': ['e','o','g'],
  'd': ['b','p','q'], 'e': ['a','c','o'], 'f': ['t','i','l'],
  'g': ['q','c','o'], 'h': ['b','n','m'], 'i': ['l','j','t'],
  'j': ['i','l'],     'k': ['h','x'],     'l': ['i','j','t'],
  'm': ['n','h','w'], 'n': ['m','h','u'], 'o': ['a','c','e'],
  'p': ['b','d','q'], 'q': ['g','p','d'], 'r': ['n','v'],
  's': ['z','c'],     't': ['f','l','i'], 'u': ['n','v'],
  'v': ['u','w','r'], 'w': ['v','m','n'], 'x': ['k','z'],
  'y': ['v','j'],     'z': ['s','x'],
};

function choice(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function pickDigitConfusable(digit) {
  const options = DIGIT_CONFUSABLES[digit] ?? [...'0123456789'].filter(d => d !== digit);
  return choice(options);
}

export function pickConfusable(ch) {
  const lower = ch.toLowerCase();
  const options = CONFUSABLES[lower] ?? [...'abcdefghijklmnopqrstuvwxyz'].filter(c => c !== lower);
  const chosen = choice(options);
  return ch !== ch.toLowerCase() ? chosen.toUpperCase() : chosen;
}

export function alphaIndices(word) {
  return [...word].map((c, i) => [c, i]).filter(([c]) => /[a-zA-Z]/.test(c)).map(([, i]) => i);
}

/** Returns Set of char indices auto-shown: first letter, plus every 4th alpha (positions 4,8,12…) for words with 5+ alpha chars. */
export function pinnedIndices(word) {
  const alpha = alphaIndices(word);
  const pinned = new Set(alpha.length > 0 ? [alpha[0]] : []);
  if (alpha.length >= 5) {
    for (let i = 3; i < alpha.length; i += 4) pinned.add(alpha[i]);
  }
  return pinned;
}

export function twoLetterDisplay(word, extraPos, extraCh) {
  const alpha = alphaIndices(word);
  if (alpha.length <= 1) return word;
  const pinned = pinnedIndices(word);
  return [...word].map((c, i) => {
    if (!/[a-zA-Z]/.test(c) || pinned.has(i)) return c;
    if (i === extraPos) return extraCh;
    return '_';
  }).join('');
}

export function makeLineDisplay(line, wrongProb = 0.15) {
  const words = line.split(' ');
  const wrongWords = [];
  const parts = [];

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    const pinned = pinnedIndices(w);
    const nonPinned = alphaIndices(w).filter(idx => !pinned.has(idx));
    if (nonPinned.length === 0) {
      parts.push(`${i + 1}:${w}`);
      continue;
    }
    const ci = choice(nonPinned);
    const actualCh = w[ci];
    const hasWrong = Math.random() < wrongProb;
    const shownCh = hasWrong ? pickConfusable(actualCh) : actualCh;
    if (hasWrong) wrongWords.push(i + 1);
    parts.push(`${i + 1}:${twoLetterDisplay(w, ci, shownCh)}`);
  }

  return { display: parts.join('  '), hasWrong: wrongWords.length > 0, wrongPositions: wrongWords };
}

export function makeAcronymDisplay(line, wrongProb = 0.2) {
  const wrongLetters = [];
  const parts = [];
  const words = line.split(' ');

  for (let i = 0; i < words.length; i++) {
    const clean = words[i].replace(/^[^a-zA-Z]+/, '');
    if (!clean) continue;
    const actualCh = clean[0];
    const hasWrong = Math.random() < wrongProb;
    const shownCh = hasWrong ? pickConfusable(actualCh) : actualCh;
    if (hasWrong) wrongLetters.push(i + 1);
    parts.push(`${i + 1}:${shownCh}`);
  }

  return { display: parts.join('  '), hasWrong: wrongLetters.length > 0, wrongPositions: wrongLetters };
}

export function makeDigitDisplay(transitionString, wrongProb = 0.2) {
  const wrongDigits = [];
  const parts = [];

  for (let i = 0; i < transitionString.length; i++) {
    const digit = transitionString[i];
    const hasWrong = Math.random() < wrongProb;
    const shown = hasWrong ? pickDigitConfusable(digit) : digit;
    if (hasWrong) wrongDigits.push(i + 1);
    parts.push(`${i + 1}:${shown}`);
  }

  return { display: parts.join('  '), hasWrong: wrongDigits.length > 0, wrongPositions: wrongDigits };
}

function scoreGeneric(display, userPositions, itemLabel) {
  const actual = new Set(display.wrongPositions);
  const user = new Set(userPositions);
  const missed = [...actual].filter(x => !user.has(x)).sort((a, b) => a - b);
  const falseAlarms = [...user].filter(x => !actual.has(x)).sort((a, b) => a - b);
  const correct = missed.length === 0 && falseAlarms.length === 0;

  if (correct) {
    return [true, actual.size > 0 ? 'Correct!' : `Correct — no wrong ${itemLabel}s.`];
  }
  const parts = [];
  if (missed.length > 0)
    parts.push(`missed ${itemLabel}${missed.length > 1 ? 's' : ''} ${missed.join(', ')}`);
  if (falseAlarms.length > 0)
    parts.push(`false alarm on ${itemLabel}${falseAlarms.length > 1 ? 's' : ''} ${falseAlarms.join(', ')}`);
  const msg = parts.join('; ');
  return [false, msg[0].toUpperCase() + msg.slice(1) + '.'];
}

export function scoreResponse(display, userPositions) {
  return scoreGeneric(display, userPositions, 'word');
}

export function scoreAcronymResponse(display, userPositions) {
  return scoreGeneric(display, userPositions, 'letter');
}

export function scoreDigitResponse(display, userPositions) {
  return scoreGeneric(display, userPositions, 'digit');
}
