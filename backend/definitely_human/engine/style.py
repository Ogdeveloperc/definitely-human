"""Measurable style hints. These are shown next to the model score but never change it."""
from __future__ import annotations

import re
import statistics

# Words and phrases that chat models use far more often than human writers.
# Each hit is only a hint: humans use all of these too.
PHRASES = [
    "delve", "delves", "delving", "tapestry", "testament to", "underscore", "underscores",
    "underscoring", "pivotal", "intricate", "intricacies", "multifaceted", "nuanced",
    "realm", "digital landscape", "evolving landscape", "ever-evolving", "rapidly evolving", "navigate the", "navigating the",
    "embark", "foster", "fostering", "leverage", "leveraging", "harness", "harnessing",
    "showcase", "showcasing", "seamless", "seamlessly", "holistic", "paramount",
    "crucial role", "plays a crucial", "plays a vital", "plays a pivotal", "vital role",
    "it is important to note", "it's important to note", "it is worth noting",
    "it's worth noting", "in today's", "in the realm of", "a myriad of", "myriad",
    "furthermore", "moreover", "additionally", "in conclusion", "overall,", "in summary",
    "ultimately,", "serves as", "stands as", "shed light",
    "sheds light", "a deeper understanding", "commendable", "meticulous", "meticulously",
    "noteworthy", "invaluable", "groundbreaking", "transformative", "unwavering",
    "resonate", "resonates", "bustling", "vibrant", "intertwined", "interplay",
    "at its core", "key takeaway", "game-changer", "a testament", "endeavor", "endeavors", "elevate", "streamline", "streamlining", "notably", ]
_PHRASE_RE = re.compile(
    r"(?<![A-Za-z])(" + "|".join(re.escape(p) for p in sorted(PHRASES, key=len, reverse=True)) + r")(?![A-Za-z])",
    re.I,
)
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")  # letters in any script, with apostrophes


def phrase_hits(text: str, start: int, end: int) -> list[dict]:
    return [{"start": m.start(), "end": m.end(), "phrase": m.group().lower()}
            for m in _PHRASE_RE.finditer(text, start, end)]


def document_stats(text: str, sentences: list[tuple[int, int]]) -> dict:
    words = _WORD.findall(text)
    n = len(words)
    lengths = [len(_WORD.findall(text[s:e])) for s, e in sentences]
    lengths = [x for x in lengths if x]
    hits = len(_PHRASE_RE.findall(text))
    mean = statistics.fmean(lengths) if lengths else 0.0
    sd = statistics.pstdev(lengths) if len(lengths) > 1 else 0.0
    # Type-token ratio over a fixed 400-word window so length doesn't dominate.
    win = [w.lower() for w in words[:400]]
    return {
        "words": n,
        "sentences": len(lengths),
        "sentence_len_mean": round(mean, 1),
        "sentence_len_sd": round(sd, 1),
        # Low variation in sentence length ("low burstiness") is typical of model text.
        "burstiness": round(sd / mean, 2) if mean else 0.0,
        "type_token_ratio": round(len(set(win)) / len(win), 2) if win else 0.0,
        "ai_phrases_per_1k": round(1000 * hits / n, 1) if n else 0.0,
        "em_dashes_per_1k": round(1000 * text.count("—") / n, 1) if n else 0.0,
    }


_EN_FUNCTION = set("""the of and to a in is that it for was on are as with be by this at from or have an
not but which they his her their its were has had been can will would there what all we one
you he she if so do more about when also than into some these other could our may who no only
then them how my your any each such those most over after should""".split())
_NON_EN_CHARS = set("çğışöüâêîôûäëïñãõåøæœßéèàùáíóú")


def language_check(text: str) -> dict:
    """Rough English check: share of common English function words, and of non-English letters."""
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return {"english": False, "en_ratio": 0.0}
    en = sum(w in _EN_FUNCTION for w in words) / len(words)
    letters = [c for c in text.lower() if c.isalpha()]
    foreign = sum(c in _NON_EN_CHARS for c in letters) / max(1, len(letters))
    # Real English prose is ~35-50% function words; other languages score well under 10%.
    # Loanwords (café, naïve) add a few accented letters to English, so plenty of
    # function words outweighs them.
    return {"english": en >= 0.25 or (en >= 0.15 and foreign < 0.02), "en_ratio": round(en, 3)}
