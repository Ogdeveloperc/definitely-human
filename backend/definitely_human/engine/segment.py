"""Split plain text into paragraphs and sentences, keeping character offsets."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Abbreviations that end with a period but don't end a sentence.
_ABBREV = {
    "e.g", "i.e", "etc", "vs", "cf", "al", "fig", "figs", "eq", "eqs", "no", "nos",
    "vol", "pp", "p", "ch", "sec", "dr", "mr", "mrs", "ms", "prof", "jr", "sr", "st",
    "inc", "ltd", "co", "corp", "approx", "dept", "est", "u.s", "u.k", "ph.d", "resp",
}
_SENT_END = re.compile(r"[.!?]+[\"')\]]*(?=\s+|$)")


@dataclass
class Span:
    start: int
    end: int


@dataclass
class Paragraph(Span):
    sentences: list[Span] = field(default_factory=list)


def _is_abbrev(text: str, dot_pos: int) -> bool:
    m = re.search(r"([A-Za-z][A-Za-z.]*)\.?$", text[max(0, dot_pos - 12):dot_pos + 1])
    if not m:
        return False
    word = m.group(1).rstrip(".").lower()
    if word in _ABBREV:
        return True
    return len(word) == 1 and word.isalpha()  # initials like "J. Smith"


def split_sentences(text: str, start: int, end: int) -> list[Span]:
    spans, s = [], start
    for m in _SENT_END.finditer(text, start, end):
        stop = m.end()
        if text[m.start()] == "." and m.end() - m.start() == 1 and _is_abbrev(text, m.start()):
            continue
        nxt = text[stop:stop + 3].lstrip()
        if nxt and nxt[0].islower():  # "... 3.5 percent" or mid-sentence period
            continue
        if text[s:stop].strip():
            spans.append(Span(s, stop))
        s = stop
        while s < end and text[s].isspace():
            s += 1
    if s < end and text[s:end].strip():
        spans.append(Span(s, end))
    return spans


def split_document(text: str) -> list[Paragraph]:
    paras = []
    for m in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]+)*", text):
        if m.group().strip():
            p = Paragraph(m.start(), m.end())
            p.sentences = split_sentences(text, m.start(), m.end())
            paras.append(p)
    return paras
