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
_WORD = re.compile(r"[A-Za-z']+")


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
