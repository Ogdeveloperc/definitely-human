"""Turn .docx / .pdf / .txt files into clean plain-text paragraphs for scoring.

Academic files carry a lot of text that is not the author's prose (references,
running headers, page numbers, tables, hyphenated line breaks). Leaving it in
produces meaningless scores, so it is removed here.
"""
from __future__ import annotations

import io
import re
from collections import Counter

_REF_HEADING = re.compile(
    r"^\s*(\d+(\.\d+)*\.?\s*)?(references|bibliography|works cited|literature cited|"
    r"reference list|sources|kaynakça|kaynaklar)\s*:?\s*$", re.I)
_PAGE_NUM = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$", re.I)


def _cut_references(paras: list[str]) -> tuple[list[str], bool]:
    # Only cut at a heading in the second half, so a table of contents doesn't trigger it.
    for i, p in enumerate(paras):
        if i >= len(paras) // 2 and _REF_HEADING.match(p):
            return paras[:i], True
    return paras, False


def from_docx(data: bytes) -> tuple[list[str], dict]:
    import docx

    d = docx.Document(io.BytesIO(data))
    paras = []
    for p in d.paragraphs:  # body paragraphs only: tables, headers and footers are skipped
        t = p.text.strip()
        if not t:
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        if _REF_HEADING.match(t):
            paras.append(t)  # kept so _cut_references can find it
        elif any(k in style for k in ("caption", "toc", "quote", "code", "heading", "title")):
            continue
        else:
            paras.append(t)
    paras, cut = _cut_references(paras)
    return paras, {"references_removed": cut}


def from_pdf(data: bytes) -> tuple[list[str], dict]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [(pg.extract_text() or "").splitlines() for pg in reader.pages]
    # Lines repeated on many pages are running headers/footers.
    counts = Counter(l.strip() for lines in pages for l in set(lines) if l.strip())
    repeated = {l for l, n in counts.items() if len(pages) >= 3 and n >= max(3, len(pages) // 2)}
    lines = []
    for pl in pages:
        for l in pl:
            s = l.strip()
            if not s:
                lines.append("")
            elif s not in repeated and not _PAGE_NUM.match(s):
                lines.append(s)
        lines.append("")
    paras, cur = [], ""
    widths = sorted(len(l) for l in lines if l)
    full = widths[int(len(widths) * 0.8)] if widths else 80
    for l in lines:
        if not l:
            if cur:
                paras.append(cur)
                cur = ""
            continue
        if _REF_HEADING.match(l):  # headings like "References" stand alone
            if cur:
                paras.append(cur)
            paras.append(l)
            cur = ""
            continue
        if cur.endswith("-") and l[:1].islower():
            cur = cur[:-1] + l  # re-join hyphenated line breaks
        else:
            cur = f"{cur} {l}" if cur else l
        # A clearly short line ending a sentence closes the paragraph.
        if l[-1:] in ".!?:" and len(l) < 0.7 * full:
            paras.append(cur)
            cur = ""
    if cur:
        paras.append(cur)
    paras = [re.sub(r"\s+", " ", p).strip() for p in paras]
    paras = [p for p in paras if len(p.split()) >= 3 or _REF_HEADING.match(p)]
    paras, cut = _cut_references(paras)
    return paras, {"references_removed": cut, "pages": len(pages)}


def extract(filename: str, data: bytes) -> tuple[str, dict]:
    name = filename.lower()
    if name.endswith(".docx"):
        paras, meta = from_docx(data)
    elif name.endswith(".pdf"):
        paras, meta = from_pdf(data)
    elif name.endswith((".txt", ".md")):
        text = data.decode("utf-8", errors="replace")
        paras, cut = _cut_references([p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()])
        meta = {"references_removed": cut}
    elif name.endswith(".doc"):
        raise ValueError("Old .doc files aren't supported. Open it in Word and save as .docx.")
    else:
        raise ValueError("Unsupported file type. Use .docx, .pdf or .txt.")
    if not paras:
        raise ValueError("No text found. If this is a scanned PDF, it has no selectable text.")
    return "\n\n".join(paras), meta
