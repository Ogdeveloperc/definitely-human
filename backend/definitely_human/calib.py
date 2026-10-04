"""Calibration of the local (region) thresholds.

Used two ways:
  * by the developer (eval/run_windows.py + eval/calibrate.py) to produce the
    shipped engine/calibration.json, and
  * by the app's "Full calibration" button, which runs the same procedure on the
    user's own GPU with more data and writes data/calibration.json.

Thresholds are chosen per *document*: red is the lowest score at which at most
`doc_fpr` of fully human long documents show any red region (after the
minimum-run rule).
"""
from __future__ import annotations

import json
import math
import pickle
import random
from collections import defaultdict
from pathlib import Path

import numpy as np

from .engine.local import build_windows, min_run, sentence_scores
from .engine.meld_model import canonicalize, top_quantile_mean
from .engine.segment import split_document

DOMAINS = ["abstracts", "news", "wiki", "books", "reddit"]
SOURCES = {
    "meld_eval.jsonl": ("anon-review-meld-2026/meld-eval", "meld_eval.jsonl",
                        "4c80f0fdc003854e5b6bfda90f7ac41ffb12e232"),
    "daigt.parquet": ("Yunij/kaggle-comp-daigt", "data/train-00000-of-00001.parquet",
                      "8460dd337298f84efc22339f6da7f3c0137e5fbb"),
}
RHO = 0.25


def fetch_data(data_dir: Path, log=print) -> None:
    from huggingface_hub import hf_hub_download

    data_dir.mkdir(parents=True, exist_ok=True)
    for name, (repo, path, rev) in SOURCES.items():
        if (data_dir / name).exists():
            continue
        log(f"downloading {name}")
        got = hf_hub_download(repo, path, revision=rev, repo_type="dataset", local_dir=data_dir / "_dl")
        Path(got).rename(data_dir / name)


# --------------------------------------------------------------- documents
def _words(t: str) -> int:
    return len(t.split())


def assemble(pieces: list[tuple[str, int]]) -> tuple[str, list[tuple[int, int, int]]]:
    """Join (text, label) pieces into one document; return text and labelled char ranges."""
    parts, ranges, pos = [], [], 0
    for txt, lab in pieces:
        c = canonicalize(txt)
        if not c:
            continue
        if parts:
            pos += 2
        parts.append(c)
        ranges.append((pos, pos + len(c), lab))
        pos += len(c)
    return "\n\n".join(parts), ranges


def _load_sources(data_dir: Path, rng: random.Random):
    import pyarrow.parquet as pq

    human, ai_by_prompt = defaultdict(list), defaultdict(list)
    with open(data_dir / "meld_eval.jsonl", encoding="utf-8") as f:
        for line in f:
            if '"attack": "none"' not in line and '"label": 0' not in line:
                continue  # skip attacked AI rows without parsing them
            r = json.loads(line)
            if r["domain"] not in DOMAINS:
                continue
            if r["label"] == 0:
                human[r["domain"]].append(r)
            elif r["attack"] == "none":
                ai_by_prompt[r["prompt_id"]].append(r)
    t = pq.read_table(data_dir / "daigt.parquet", columns=["text", "source"]).to_pydict()
    essays = [x for x, s in zip(t["text"], t["source"]) if s == "persuade_corpus"]
    essays_ai = [x for x, s in zip(t["text"], t["source"]) if s != "persuade_corpus"]
    for lst in (*human.values(), essays, essays_ai):
        rng.shuffle(lst)
    return human, ai_by_prompt, essays, essays_ai


def build_docs(data_dir: Path, per_kind: int, seed: int = 0) -> list[tuple[str, int, list]]:
    rng = random.Random(seed)
    human, ai_by_prompt, essays, essays_ai = _load_sources(data_dir, rng)
    docs = []
    # 1) Long, fully human documents (false-positive rate per document)
    for i in range(per_kind):
        docs.append(("human_long/essays", i, [(essays[3 * i + k], 0) for k in range(3)]))
    for d in DOMAINS:
        for i in range(per_kind // 2):
            docs.append((f"human_long/{d}", i, [(s["text"], 0) for s in human[d][5 * i: 5 * i + 5]]))
    # 2) Mixed: human seed followed by its paired AI continuation (same topic)
    for d in DOMAINS:
        for i in range(per_kind // 2):
            h = human[d][-(i + 1)]
            pair = ai_by_prompt.get(h["prompt_id"])
            if pair:
                docs.append((f"mixed_tail/{d}", i, [(h["text"], 0), (pair[i % len(pair)]["text"], 1)]))
    # 3) Mixed: one AI section inserted into a human document
    for i in range(per_kind):
        e1, e2 = essays[-(3 * i + 1)], essays[-(3 * i + 2)]
        docs.append(("mixed_insert/essays", i, [(e1, 0), (essays_ai[i], 1), (e2, 0)]))
    for d in ["abstracts", "news"]:
        for i in range(per_kind // 2):
            h1, h2 = human[d][-(100 + 2 * i)], human[d][-(101 + 2 * i)]
            pair = ai_by_prompt.get(h2["prompt_id"])
            if pair:
                docs.append((f"mixed_insert/{d}", i, [(h1["text"], 0), (pair[0]["text"], 1), (h2["text"], 0)]))
    # 4) Fully AI documents
    for d in DOMAINS:
        for i in range(per_kind // 4):
            h = human[d][200 + i]
            for a in ai_by_prompt.get(h["prompt_id"], [])[:2]:
                docs.append((f"ai/{d}/{a['generator']}", i, [(a["text"], 1)]))
    return docs


# --------------------------------------------------------------- scoring
def score_docs(det, docs, sizes: list[int], out_dir: Path, log=print, progress=None) -> None:
    """Score every document's local windows; one resumable pickle per document."""
    out_dir.mkdir(parents=True, exist_ok=True)
    budget = 16384 if det.device.type == "cuda" else 4096
    for n, (kind, idx, pieces) in enumerate(docs):
        path = out_dir / f"{kind.replace('/', '__')}__{idx}.pkl"
        if progress:
            progress(n / len(docs))
        if path.exists():
            continue
        text, ranges = assemble(pieces)
        sents = [(s.start, s.end) for p in split_document(text) for s in p.sentences]
        if len(sents) < 3:
            continue
        labels = []
        for s0, s1 in sents:
            mid = (s0 + s1) // 2
            labels.append(next((l for r0, r1, l in ranges if r0 <= mid < r1), 0))
        ids = det.tok(text, add_special_tokens=False)["input_ids"]
        c_doc, _, _ = det._token_scores(ids, 1 if det.device.type == "cpu" else 4)
        rec = {"kind": kind, "idx": idx, "text": text, "sents": sents, "labels": labels,
               "doc_score": float(top_quantile_mean(c_doc, det.rho)), "windows": {}}
        for w in sizes:
            wins = build_windows(text, sents, w)
            res = det.score_spans(text, [(sents[i][0], sents[j][1]) for i, j in wins], token_budget=budget)
            rec["windows"][w] = {"wins": wins, "tok": [(st, sc.half().numpy()) for st, sc in res]}
        with open(path, "wb") as f:
            pickle.dump(rec, f)
        log(f"[{n + 1}/{len(docs)}] {kind}#{idx} {len(sents)} sentences")
    if progress:
        progress(1.0)


def load_records(out_dir: Path) -> list[dict]:
    return [pickle.load(open(p, "rb")) for p in sorted(out_dir.glob("*.pkl"))]


# --------------------------------------------------------------- choosing thresholds
def _tq(x: np.ndarray) -> float:
    k = max(1, math.ceil(len(x) * RHO))
    return float(np.sort(x)[::-1][:k].mean())


def record_sentence_scores(rec: dict, w: int, variant: str) -> list[float]:
    W = rec["windows"][w]
    wins, toks, sents = W["wins"], W["tok"], rec["sents"]
    win_scores = [_tq(sc.astype(np.float32)) for _, sc in toks]
    if variant == "a":
        return sentence_scores(len(sents), wins, win_scores)
    per = []
    for (a, b), (st, sc) in zip(wins, toks):
        st, sc = np.asarray(st), sc.astype(np.float32)
        row = []
        for s in range(a, b + 1):
            m = (st >= sents[s][0]) & (st < sents[s][1])
            row.append(_tq(sc[m]) if m.any() else None)
        per.append(row)
    return sentence_scores(len(sents), wins, win_scores, per)


def _levels(scores, red, yellow, run):
    lv = ["ai" if s >= red else "mixed" if s >= yellow else "human" for s in scores]
    return min_run(lv, "ai", run)


def _auc(pos, neg) -> float:
    if not pos or not neg:
        return float("nan")
    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort() + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def choose(recs: list[dict], doc_fpr: float = 0.02, yellow_doc_fpr: float = 0.15, run: int = 2,
           log=print) -> tuple[dict, list[dict]]:
    by = defaultdict(list)
    for r in recs:
        by[r["kind"].split("/")[0]].append(r)
    human_docs = by["human_long"]
    if not human_docs:
        raise ValueError("no human documents scored")
    sizes = sorted({w for r in recs for w in r["windows"]})
    table, best = [], None
    for w in sizes:
        for variant in ("a", "b"):
            S = {id(r): record_sentence_scores(r, w, variant) for r in recs}

            def doc_rate(t, rn):
                return sum(any(x == "ai" for x in _levels(S[id(r)], t, -99, rn)) for r in human_docs) / len(human_docs)

            cands = sorted({round(x, 2) for r in human_docs for x in S[id(r)] if not math.isnan(x)})
            cands = [c for c in cands if c > -2] + [99.0]
            red = next(t + 0.01 for t in cands if doc_rate(t + 0.01, run) <= doc_fpr)
            yel = min(red, next(t + 0.01 for t in cands if doc_rate(t + 0.01, 1) <= yellow_doc_fpr))
            hs, ais, caught, false_red = [], [], 0, 0
            for r in by["mixed_tail"] + by["mixed_insert"]:
                sc = S[id(r)]
                for s, l, lab in zip(sc, _levels(sc, red, yel, run), r["labels"]):
                    if math.isnan(s):
                        continue
                    (ais if lab else hs).append(s)
                    caught += lab and l == "ai"
                    false_red += (not lab) and l == "ai"
            ai_share = (np.mean([np.mean([l == "ai" for l in _levels(S[id(r)], red, yel, run)]) for r in by["ai"]])
                        if by["ai"] else float("nan"))
            row = {"window_words": w, "variant": variant, "red": red, "yellow": yel,
                   "sentence_auc_mixed": round(_auc(ais, hs), 3),
                   "ai_sentences_caught": round(caught / max(1, len(ais)), 3),
                   "human_sentences_red_in_mixed": round(false_red / max(1, len(hs)), 3),
                   "ai_docs_red_share": round(float(ai_share), 3)}
            log(json.dumps(row))
            table.append(row)
            key = row["ai_sentences_caught"] - 2 * row["human_sentences_red_in_mixed"]
            if best is None or key > best[0]:
                best = (key, row)
    b = best[1]
    cfg = {"window_words": b["window_words"], "variant": b["variant"], "red": b["red"],
           "yellow": b["yellow"], "min_run": run, "doc_fpr": doc_fpr, "n_docs": len(recs),
           "metrics": {k: b[k] for k in ("sentence_auc_mixed", "ai_sentences_caught",
                                         "human_sentences_red_in_mixed", "ai_docs_red_share")}}
    return cfg, table
