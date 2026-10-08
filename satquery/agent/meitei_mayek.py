"""Meitei Mayek -> Latin Manipuri, letter by letter, so a question typed (or dictated) in Meitei Mayek is read by
the same Latin lexicon and rules as one typed in Latin script.

The Latin spelling is the one of the corpus's `romanstandard` column (CompiledDataEnglishToMeitei.xlsx), which
Member A's lexicon uses: a consonant carries an inherent "a" unless a vowel sign or apun iyek follows, the long
vowel sign is "ā", and a lonsum (final) letter carries no vowel. Where romanstandard itself spells one thing
several ways, the most frequent spelling is used (word-initial ꯏ as "ee", ꯥꯎ as "ao", no vowel at apun). This is a
fixed transliteration, not a translation: no word is looked up or guessed, and text in any other script passes
through unchanged.
"""

import re

CONSONANTS = {
    "ꯀ": "k", "ꯁ": "s", "ꯂ": "l", "ꯃ": "m", "ꯄ": "p", "ꯅ": "n", "ꯆ": "ch", "ꯇ": "t", "ꯈ": "kh", "ꯉ": "ng",
    "ꯊ": "th", "ꯋ": "w", "ꯌ": "y", "ꯍ": "h", "ꯐ": "ph", "ꯒ": "g", "ꯓ": "jh", "ꯔ": "r", "ꯕ": "b", "ꯖ": "j",
    "ꯗ": "d", "ꯘ": "gh", "ꯙ": "dh", "ꯚ": "bh",
}
INDEPENDENT_VOWELS = {"ꯑ": "a", "ꯎ": "u", "ꯏ": "i"}  # ꯑ (atiya) also carries a following vowel sign: ꯑꯩ = ei
VOWEL_SIGNS = {"ꯣ": "o", "ꯤ": "i", "ꯥ": "ā", "ꯦ": "e", "ꯧ": "ou", "ꯨ": "u", "ꯩ": "ei"}
FINALS = {"ꯛ": "k", "ꯜ": "l", "ꯝ": "m", "ꯞ": "p", "ꯟ": "n", "ꯠ": "t", "ꯡ": "ng", "ꯢ": "i", "ꯪ": "ng"}
APUN = "꯭"        # joins two consonants: no vowel in between
LUM = "꯬"         # tone mark: not written in the Latin spelling
OTHER = {"꯫": ".", **{chr(0xABF0 + d): str(d) for d in range(10)}}
MEITEI_MAYEK = re.compile("[ꯀ-꯿]")


def has_meitei_mayek(text: str) -> bool:
    return bool(MEITEI_MAYEK.search(text))


def to_latin(text: str) -> str:
    """`text` with every Meitei Mayek letter in the romanstandard Latin spelling; other characters unchanged."""
    if not has_meitei_mayek(text):
        return text
    out: list[str] = []
    for i, ch in enumerate(text):
        after = text[i + 1] if i + 1 < len(text) else ""
        if ch in CONSONANTS:
            # the inherent vowel, unless a vowel sign or apun follows (a tone mark does not count)
            nxt = text[i + 2] if after == LUM and i + 2 < len(text) else after
            out.append(CONSONANTS[ch] + ("" if nxt in VOWEL_SIGNS or nxt == APUN else "a"))
        elif ch == "ꯑ":
            out.append("" if after in VOWEL_SIGNS else "a")
        elif ch == "ꯏ" and not (i and MEITEI_MAYEK.match(text[i - 1])):
            out.append("ee")  # word-initial I: romanstandard writes ee (ꯏꯡ = eeng) more often than i
        elif ch == "ꯎ" and i and text[i - 1] == "ꯥ":
            out[-1] = out[-1][:-1] + "a"  # ā + U: romanstandard writes ao (ꯐꯥꯎꯕ = phaoba) more often than āu
            out.append("o")
        elif ch in INDEPENDENT_VOWELS:
            out.append(INDEPENDENT_VOWELS[ch])
        elif ch in VOWEL_SIGNS:
            out.append(VOWEL_SIGNS[ch])
        elif ch in FINALS:
            out.append(FINALS[ch])
        elif ch in (APUN, LUM):
            continue
        else:
            out.append(OTHER.get(ch, ch))
    return "".join(out)
