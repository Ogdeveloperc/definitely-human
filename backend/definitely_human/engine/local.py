"""Local (windowed) scoring.

MELD reads a whole window at once and pools the top quarter of its token scores,
so AI text anywhere in a window raises every token in it. To localize, each
sentence starts a window of consecutive sentences of about `target_words`, every
window is scored on its own, and a sentence's score is the *minimum* over the
windows that contain it: if any window around it reads clean, the sentence does.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"\S+")


def build_windows(text: str, sents: list[tuple[int, int]], target_words: int) -> list[tuple[int, int]]:
    """Return (first, last) sentence indices for a window starting at every sentence."""
    counts = [len(_WORD.findall(text[a:b])) for a, b in sents]
    out: dict[tuple[int, int], None] = {}
    n = len(sents)
    for i in range(n):
        j, w = i, counts[i]
        while w < target_words and j + 1 < n:
            j += 1
            w += counts[j]
        while w < target_words and i > 0:  # tail: extend backwards instead of scoring a stub
            i -= 1
            w += counts[i]
        out[(i, j)] = None
    return list(out)


def sentence_scores(n_sents: int, windows: list[tuple[int, int]], win_scores: list[float],
                    sent_in_win: list[list[float | None]] | None = None) -> list[float]:
    """Minimum over windows containing each sentence.

    win_scores[k] is window k's pooled score. If sent_in_win is given,
    sent_in_win[k][s - first] is the pooled score of sentence s's own tokens inside
    window k, and that is used instead (variant "b").
    """
    best = [float("inf")] * n_sents
    for k, (a, b) in enumerate(windows):
        for s in range(a, b + 1):
            v = win_scores[k] if sent_in_win is None else sent_in_win[k][s - a]
            if v is not None and v < best[s]:
                best[s] = v
    return [b if b != float("inf") else float("nan") for b in best]


def min_run(levels: list[str], target: str, run: int) -> list[str]:
    """Downgrade `target` labels that don't form a run of at least `run` sentences."""
    out, i, n = list(levels), 0, len(levels)
    while i < n:
        if levels[i] == target:
            j = i
            while j + 1 < n and levels[j + 1] == target:
                j += 1
            if j - i + 1 < run:
                for k in range(i, j + 1):
                    out[k] = "mixed" if target == "ai" else "human"
            i = j + 1
        else:
            i += 1
    return out


def clean_threshold(scores: list[float], run: int) -> float:
    """Lowest red threshold at which these (known human) sentences show no red run.

    A run of `run` sentences turns red only if all of them reach the threshold,
    so the run's weakest sentence is what matters.
    """
    vals = [v for v in scores if v == v and v != float("inf")]
    if len(vals) < run:
        return float("-inf")
    return max(min(vals[i:i + run]) for i in range(len(vals) - run + 1))
