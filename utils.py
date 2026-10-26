import re
from difflib import SequenceMatcher


def normalize_translate(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s)
    return s


def translate_matches(user_answer: str, correct: str) -> bool:
    a = normalize_translate(user_answer)
    b = normalize_translate(correct)
    if a == b:
        return True
    if not b:
        return False
    ratio = SequenceMatcher(None, a, b).ratio()
    allowed = 1 - (1 / max(len(b), 2))
    return ratio >= allowed


def exact_matches(user_answer: str, correct: str) -> bool:
    return (user_answer or "").strip().lower() == (correct or "").strip().lower()
