"""Tiny Korean grammar helpers (particle selection) used by the template-based script generator."""
from __future__ import annotations


def _has_final(word: str) -> bool:
    """True if the last Hangul syllable has a final consonant (batchim)."""
    for ch in reversed(word):
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28 != 0
    return False


def _final_is_rieul(word: str) -> bool:
    for ch in reversed(word):
        if "가" <= ch <= "힣":
            return (ord(ch) - 0xAC00) % 28 == 8
    return False


def josa(word: str, kind: str) -> str:
    """Return word + the right particle. kind in {'은/는','을/를','이/가','과/와','으로/로'}."""
    f = _has_final(word)
    if kind == "은/는":
        return word + ("은" if f else "는")
    if kind == "을/를":
        return word + ("을" if f else "를")
    if kind == "이/가":
        return word + ("이" if f else "가")
    if kind == "과/와":
        return word + ("과" if f else "와")
    if kind == "으로/로":
        return word + ("로" if (not f or _final_is_rieul(word)) else "으로")
    raise ValueError(kind)


KO_FREQ = {1: "한 번", 2: "두 번", 3: "세 번", 4: "네 번"}
KO_AMOUNT = {0.5: "반 알씩", 1: "한 알씩", 2: "두 알씩"}
KO_DAYS_COLLOQ = {2: "이틀", 3: "사흘", 5: "닷새", 7: "일주일"}
