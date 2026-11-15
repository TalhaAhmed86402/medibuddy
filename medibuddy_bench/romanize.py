"""Revised Romanization of Korean (simplified), for English names of real places and institutions.

Covers the rules that matter for names: syllable decomposition, liaison of a final consonant before a vowel, and the
common assimilations (nasalisation, ㄹ before/after ㄴ, ㄹ after ㅁ/ㅇ).  It is not a full implementation of the
2000 standard (no tensification, no aspiration with ㅎ beyond the basic cases); official spellings of well-known places
override it where the benchmark has them (knowledge.DISTRICTS).

>>> romanize("강남"), romanize("종로"), romanize("덕양"), romanize("해운대"), romanize("신라")
('Gangnam', 'Jongno', 'Deogyang', 'Haeundae', 'Silla')
>>> romanize("연세패밀리"), romanize("굿모닝"), romanize("백리")
('Yeonsepaemilli', 'Gunmoning', 'Baengni')
"""
from __future__ import annotations

_INITIAL = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_MEDIAL = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu",
           "eu", "ui", "i"]
# final consonant: (sound at the end of a word / before a consonant, sound carried over before a vowel)
_FINAL = [("", ""), ("k", "g"), ("k", "kk"), ("k", "gs"), ("n", "n"), ("n", "nj"), ("n", "nh"), ("t", "d"),
          ("l", "r"), ("k", "lg"), ("m", "lm"), ("l", "lb"), ("l", "ls"), ("l", "lt"), ("p", "lp"), ("l", "lh"),
          ("m", "m"), ("p", "b"), ("p", "bs"), ("t", "s"), ("t", "ss"), ("ng", "ng"), ("t", "j"), ("t", "ch"),
          ("k", "k"), ("t", "t"), ("p", "p"), ("t", "h")]
_BASE, _N_MED, _N_FIN = 0xAC00, 21, 28


def _parts(ch: str):
    o = ord(ch) - _BASE
    if not 0 <= o < 11172:
        return None
    return o // (_N_MED * _N_FIN), (o // _N_FIN) % _N_MED, o % _N_FIN


def romanize(text: str, capitalize: bool = True) -> str:
    """Romanize Hangul; other characters (digits, Latin letters, spaces) pass through unchanged."""
    out: list[str] = []
    syl = [_parts(c) for c in text]
    for i, (c, p) in enumerate(zip(text, syl)):
        if p is None:
            out.append(c)
            continue
        ini, med, fin = p
        prev = syl[i - 1] if i > 0 else None
        nxt = syl[i + 1] if i + 1 < len(text) else None
        # initial consonant, after the previous syllable's final
        s_ini = _INITIAL[ini]
        if prev is not None:
            pf = prev[2]
            if ini == 11:                          # ㅇ: the previous final was carried over already
                s_ini = ""
            elif ini == 5:                         # ㄹ
                if pf in (8, 4):                   # ㄹ+ㄹ, ㄴ+ㄹ -> ll
                    s_ini = "l"
                elif pf in (16, 21, 1, 17):        # ㅁ/ㅇ/ㄱ/ㅂ + ㄹ -> n
                    s_ini = "n"
            elif ini == 2 and pf == 8:             # ㄹ+ㄴ -> ll
                s_ini = "l"
        s = s_ini + _MEDIAL[med]
        if fin:
            end, carry = _FINAL[fin]
            if nxt is not None and nxt[0] == 11:   # before a vowel: liaison
                s += carry
            elif nxt is not None:
                ni = nxt[0]
                if ni in (2, 6) or (ni == 5 and fin not in (8, 4)):      # before ㄴ/ㅁ (or ㄹ): nasalise
                    s += {"k": "ng", "t": "n", "p": "m"}.get(end, end)
                elif ni == 5 and fin == 4:         # ㄴ+ㄹ -> l (the ㄹ side adds the second l)
                    s += "l"
                else:
                    s += end
            else:
                s += end
        out.append(s)
    word = "".join(out)
    if capitalize:
        word = " ".join(w[:1].upper() + w[1:] if w else w for w in word.split(" "))
    return word
