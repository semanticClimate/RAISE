/**
 * Kruti Dev 010 to Unicode Devanagari Converter
 * ==============================================
 * Automatically converts legacy Kruti Dev 010 / Chanakya non-Unicode font encodings
 * commonly found in Indian government and institutional PDFs (e.g., NIPGR reports)
 * into canonical UTF-8 Devanagari Unicode.
 *
 * Example:
 *   "^ AvkWuykbu fganh \"kCndks\"k ,oa fofHkUu fganh VwYI***"
 *   -> "^ ऑनलाइन हिंदी शब्दकोश एवं विभिन्न हिंदी टूल्स***"
 */

// Heuristic pattern to detect Kruti Dev mojibake in text streams
export const KRUTI_DEV_PATTERN =
  /\b(fganh|vkW|dks|kCnd|,oa|fofHk|VwYI|iz|ds|dh|esa|gS|AvkW|"kCnd|'kCnd)\b/i;

// Multi-character substitutions ordered by length descending
const RAW_KRUTI_PAIRS: [string, string][] = [
  ['fofHkUu', 'विभिन्न'],
  ['AvkWuykbu', 'ऑनलाइन'],
  ['vkWuykbu', 'ऑनलाइन'],
  ['"kCndks"k', 'शब्दकोश'],
  ["'kCndks'k", 'शब्दकोश'],
  ['"kCndks', 'शब्दको'],
  ["'kCndks", 'शब्दको'],
  ['fganh', 'हिंदी'],
  ['VwYI', 'टूल्स'],
  ['AvkW', 'ऑ'],
  ['vkW', 'ऑ'],
  ['vkS', 'औ'],
  ['vks', 'ओ'],
  ['vk', 'आ'],
  ['v', 'अ'],
  ['bZ', 'ई'],
  ['b', 'इ'],
  ['m', 'उ'],
  ['Å', 'ऊ'],
  [',oa', 'एवं'],
  [',', 'ए'],
  ['"k', 'श'],
  ["'k", 'श'],
  ['"', 'श्'],
  ["'", 'श्'],
  ['[k', 'ख'],
  ['[', 'ख्'],
  ['?k', 'घ'],
  ['?', 'घ्'],
  ['>k', 'झ'],
  ['>', 'झ्'],
  ['N', 'छ'],
  ['/k', 'ध'],
  ['/', 'ध्'],
  ['Fk', 'थ'],
  ['F', 'थ्'],
  ['Hk', 'भ'],
  ['H', 'भ्'],
  ['{k', 'क्ष'],
  ['{', 'क्ष्'],
  ['=k', 'त्र'],
  ['=', 'त्र्'],
  ['K', 'ज्ञ'],
  ['J', 'श्र'],
  ['dks', 'को'],
  ['dkS', 'कौ'],
  ['ds', 'के'],
  ['dS', 'कै'],
  ['dk', 'का'],
  ['dh', 'की'],
  ['xks', 'गो'],
  ['xkS', 'गौ'],
  ['xs', 'गे'],
  ['xS', 'गै'],
  ['xk', 'गा'],
  ['xh', 'गी'],
  ['tks', 'जो'],
  ['tkS', 'जौ'],
  ['ts', 'जे'],
  ['tS', 'जै'],
  ['tk', 'जा'],
  ['th', 'जी'],
  ['rks', 'तो'],
  ['rkS', 'तौ'],
  ['rs', 'ते'],
  ['rS', 'तै'],
  ['rk', 'ता'],
  ['rh', 'ती'],
  ['nks', 'दो'],
  ['nkS', 'दौ'],
  ['ns', 'दे'],
  ['nS', 'दै'],
  ['nk', 'दा'],
  ['nh', 'दी'],
  ['uks', 'नो'],
  ['ukS', 'नौ'],
  ['us', 'ने'],
  ['uS', 'नै'],
  ['uk', 'ना'],
  ['uh', 'नी'],
  ['iks', 'पो'],
  ['ikS', 'पौ'],
  ['is', 'पे'],
  ['iS', 'पै'],
  ['ik', 'पा'],
  ['ih', 'पी'],
  ['cks', 'बो'],
  ['ckS', 'बौ'],
  ['cs', 'बे'],
  ['cS', 'बै'],
  ['ck', 'बा'],
  ['ch', 'बी'],
  ['eks', 'मो'],
  ['ekS', 'मौ'],
  ['es', 'मे'],
  ['eS', 'मै'],
  ['ek', 'मा'],
  ['eh', 'मी'],
  ['yks', 'लो'],
  ['ykS', 'लौ'],
  ['ys', 'ले'],
  ['yS', 'लै'],
  ['yk', 'ला'],
  ['yh', 'ली'],
  ['oks', 'वो'],
  ['okS', 'वौ'],
  ['os', 'वे'],
  ['oS', 'वै'],
  ['ok', 'वा'],
  ['oh', 'वी'],
  ['lks', 'सो'],
  ['lkS', 'सौ'],
  ['ls', 'से'],
  ['lS', 'सै'],
  ['lk', 'सा'],
  ['lh', 'सी'],
  ['gks', 'हो'],
  ['gkS', 'हौ'],
  ['gs', 'हे'],
  ['gS', 'है'],
  ['gk', 'हा'],
  ['gh', 'ही'],
];

const KRUTI_DEV_PAIRS: [string, string][] = [...RAW_KRUTI_PAIRS].sort(
  (a, b) => b[0].length - a[0].length
);

// Single character mappings
const KRUTI_CHAR_MAP: Record<string, string> = {
  d: 'क',
  D: 'क्',
  k: 'ा',
  x: 'ग',
  X: 'ग्',
  p: 'च',
  P: 'च्',
  t: 'ज',
  T: 'ज्',
  V: 'ट',
  B: 'ठ',
  M: 'ड',
  '<': 'ढ',
  '.': 'ण्',
  r: 'त',
  R: 'त्',
  n: 'द',
  u: 'न',
  U: 'न्',
  i: 'प',
  I: 'स',
  Q: 'फ',
  c: 'ब',
  C: 'ब्',
  e: 'म',
  E: 'म्',
  ';': 'य',
  j: 'र',
  y: 'ल',
  Y: 'ल्',
  o: 'व',
  O: 'व्',
  l: 'स',
  L: 'स्',
  g: 'ह',
  h: 'ी',
  q: 'ु',
  w: 'ू',
  s: 'े',
  S: 'ै',
  a: 'ं',
  '¡': 'ँ',
  '%': 'ः',
};

/**
 * Converts a string from Kruti Dev 010 encoding to Unicode Devanagari.
 */
export function krutiDevToUnicode(krutiText: string): string {
  if (!krutiText) return '';
  let str = krutiText;

  // 1. Substitute multi-character pairs (longest match first)
  for (const [k, u] of KRUTI_DEV_PAIRS) {
    if (str.includes(k)) {
      str = str.replaceAll(k, u);
    }
  }

  // 2. Handle reph 'Z' (which appears after letter in Kruti Dev, e.g. XZ -> र्ग)
  str = str.replace(/([क-हA-Za-z])Z/g, 'र्$1');

  // 3. Handle 'f' matra (preceding short i in Kruti Dev: f + char -> char + ि)
  str = str.replace(/f([a-zA-Z\u0900-\u097F])/g, (_, c) => (KRUTI_CHAR_MAP[c] || c) + 'ि');

  // 4. Map single characters
  str = str
    .split('')
    .map((c) => KRUTI_CHAR_MAP[c] || c)
    .join('');

  // 5. Strip accidental Zero-Width Spaces (\u200B) that detach Hindi matras
  str = str.replace(/\u200B|\u200C|\u200D|\uFEFF/g, '');

  // 6. Canonical Unicode NFC normalization (merges decomposed accents/matras cleanly)
  return str.normalize('NFC');
}

/**
 * Sanitizes and upgrades any text that may contain multilingual Indic or legacy Kruti Dev encodings.
 */
export function sanitizeMultilingualText(rawText: string): string {
  if (!rawText) return '';

  // 1. Strip accidental Zero-Width Spaces (\u200B) that detach Hindi matras
  let cleaned = rawText.replace(/\u200B|\u200C|\u200D|\uFEFF/g, '');

  // 2. Convert legacy Kruti Dev segments if detected
  if (KRUTI_DEV_PATTERN.test(cleaned)) {
    cleaned = krutiDevToUnicode(cleaned);
  }

  // 3. Canonical Unicode NFC normalization
  return cleaned.normalize('NFC');
}
