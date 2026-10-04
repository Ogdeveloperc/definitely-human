"""MELD-based detector that scores a document and every sentence/word in it.

The document score follows MELD's canonical scoring contract (fp32, 2046-token
windows without overlap, top-quantile mean of per-token scores). Sentence and
word scores reuse the same per-token scores, so the heatmap and the overall
score always come from the same model pass.
"""
from __future__ import annotations

import bisect
import json
import logging
import math
import re
import time
from pathlib import Path

import torch
from transformers import AutoTokenizer

from . import style
from .meld_model import Meld, canonicalize, top_quantile_mean
from .local import build_windows, min_run
from .segment import split_document

log = logging.getLogger(__name__)

DOMAINS = {
    "essay": "student_essay",
    "paper": "scientific_paper",
    "general": "overall",
}
MIN_WORDS = 100  # MELD is unreliable below ~100 words.
CALIBRATION = Path(__file__).with_name("calibration.json")
# Used until eval/calibrate.py has written calibration.json.
_DEFAULT_CAL = {"window_words": 60, "variant": "b", "red": 3.0, "yellow": 1.5, "min_run": 2}


def calibration(profile: dict | None = None) -> dict:
    """Shipped local thresholds, optionally raised (never lowered) by a personal profile."""
    cal = dict(_DEFAULT_CAL)
    from ..paths import LOCAL_CALIBRATION

    for f in (CALIBRATION, LOCAL_CALIBRATION):  # a calibration run on this PC wins
        if f.exists():
            cal.update(json.loads(f.read_text()))
    cal["personal"] = False
    if profile and (profile.get("window_words"), profile.get("variant")) != (cal["window_words"], cal["variant"]):
        profile = None  # built for a different scoring setup (e.g. before calibration): its numbers don't apply
    if profile:
        for k in ("red", "yellow"):
            if profile.get(k, -math.inf) > cal[k]:
                cal[k] = float(profile[k])
                cal["personal"] = True
        cal["yellow"] = min(cal["yellow"], cal["red"])
    return cal
_WORD_SPAN = re.compile(r"\S+")


def pick_device(prefer: str | None = None) -> tuple[torch.device, dict]:
    """Choose CUDA when it really works, otherwise CPU. Returns (device, info).

    info also carries the NVIDIA driver check (see gpu.driver_status) so the UI
    can say whether the driver needs updating.
    """
    from . import gpu

    info: dict = {"torch": torch.__version__, "cuda_build": torch.version.cuda}
    nvidia = gpu.query_nvidia()
    dev, cuda_works = torch.device("cpu"), False
    if prefer == "cpu":
        info["device"] = "cpu"
    elif torch.cuda.is_available():
        try:
            name = torch.cuda.get_device_name(0)
            cap = torch.cuda.get_device_capability(0)
            x = torch.randn(256, 256, device="cuda")
            float((x @ x).sum())  # fails with "no kernel image" on unsupported GPUs
            total = torch.cuda.get_device_properties(0).total_memory
            dev, cuda_works = torch.device("cuda"), True
            info.update(device="cuda", gpu=name, capability=f"{cap[0]}.{cap[1]}",
                        vram_gb=round(total / 2**30, 1))
        except Exception as e:  # noqa: BLE001
            info["warning"] = f"GPU found but unusable ({e}); running on CPU, which is slower."
    else:
        info["warning"] = "No CUDA GPU detected; running on CPU, which is slower."
    info.setdefault("device", "cpu")
    if prefer != "cpu":
        info["driver_check"] = gpu.driver_status(cuda_works, nvidia)
    return dev, info


def _load_meld(model_dir: str, device: torch.device) -> Meld:
    """Build MELD on `device` and stream the weights in one tensor at a time.

    Meld.__init__ reads the whole 4 GB state dict into RAM and copies it into an
    equally large freshly initialised model, so loading peaks at twice the model
    size. Here the model is built directly on the device and each tensor is read
    from the memory-mapped safetensors file and copied in place.
    """
    from safetensors import safe_open

    from . import meld_model

    orig_load_file, orig_lsd = meld_model.load_file, Meld.load_state_dict
    meld_model.load_file = lambda _path: None
    Meld.load_state_dict = lambda self, *a, **k: None
    try:
        from transformers.initialization import no_init_weights

        # every tensor is overwritten from the file below, so skip the random init
        with device, no_init_weights():
            model = Meld(model_dir)
    finally:
        meld_model.load_file, Meld.load_state_dict = orig_load_file, orig_lsd
    targets = {**dict(model.named_parameters()), **dict(model.named_buffers())}
    expected = set(model.state_dict().keys())
    with torch.no_grad(), safe_open(str(Path(model_dir) / "model.safetensors"), framework="pt", device="cpu") as f:
        keys = set(f.keys())
        if keys != expected:  # same guarantee as load_state_dict(strict=True)
            raise RuntimeError(f"weights don't match the model: missing {sorted(expected - keys)[:5]}, "
                               f"unexpected {sorted(keys - expected)[:5]}")
        for k in keys:
            targets[k].copy_(f.get_tensor(k))
    return model.eval()


def _level(score: float, strong: float, weak: float) -> str:
    if score >= strong:
        return "ai"
    if score >= weak:
        return "mixed"
    return "human"


def _softmax(v: torch.Tensor, labels: list[str]) -> list[dict]:
    p = torch.softmax(v.float(), dim=0).tolist()
    return sorted(({"label": l, "p": round(x, 4)} for l, x in zip(labels, p)), key=lambda d: -d["p"])


class Detector:
    def __init__(self, model_dir: str | Path, device: str | None = None):
        self.model_dir = str(model_dir)
        self.device, self.device_info = pick_device(device)
        t = time.time()
        # Build directly on the target device so the weights exist once in VRAM
        # instead of being created in RAM and copied over. fp32, per the scoring contract.
        self.model = _load_meld(self.model_dir, self.device)
        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        self.tok = AutoTokenizer.from_pretrained(self.model_dir)
        self.cfg = self.model.cfg
        self.window = int(self.cfg["max_length"]) - 2
        self.rho = float(self.cfg["rho"])
        self.cls_id = int(self.tok.cls_token_id)
        self.sep_id = int(self.tok.sep_token_id)
        self.pad_id = int(self.tok.pad_token_id or 0)
        log.info("MELD loaded on %s in %.1fs", self.device, time.time() - t)

    def thresholds(self, domain: str) -> dict:
        offs = self.cfg["score_offsets"]
        key = DOMAINS.get(domain, "overall")
        t = offs["overall"] if key == "overall" else offs["strata"][key]
        return {"domain": key, "strong": t["fpr_0.01"], "medium": t["fpr_0.05"], "weak": t["fpr_0.1"]}

    @torch.inference_mode()
    def _token_scores(self, ids: list[int], batch_size: int, progress=None):
        windows = [ids[i:i + self.window] for i in range(0, len(ids), self.window)]
        c_parts, s_parts, o_parts = [], [], []
        for b0 in range(0, len(windows), batch_size):
            batch = windows[b0:b0 + batch_size]
            width = max(len(w) for w in batch) + 2
            inp = torch.full((len(batch), width), self.pad_id, dtype=torch.long)
            att = torch.zeros((len(batch), width), dtype=torch.long)
            for j, w in enumerate(batch):
                inp[j, 0] = self.cls_id
                inp[j, 1:1 + len(w)] = torch.tensor(w, dtype=torch.long)
                inp[j, 1 + len(w)] = self.sep_id
                att[j, : len(w) + 2] = 1
            s_tok, c_tok, o_tok = self.model.token_scores(inp.to(self.device), att.to(self.device))
            for j, w in enumerate(batch):
                sl = slice(1, 1 + len(w))
                c_parts.append(c_tok[j, sl].cpu())
                s_parts.append(s_tok[j, sl].cpu())
                o_parts.append(o_tok[j, sl].cpu())
            if progress:
                progress(min(b0 + batch_size, len(windows)) / len(windows))
        return torch.cat(c_parts), torch.cat(s_parts), torch.cat(o_parts)

    @torch.inference_mode()
    def score_spans(self, text: str, spans: list[tuple[int, int]], token_budget: int | None = None,
                    progress=None) -> list[tuple[list[int], torch.Tensor]]:
        """Score each text[a:b] as its own short document.

        Returns, per span, the absolute character start of every token and its
        per-token AI score. Spans must fit in one model window.
        """
        if token_budget is None:
            token_budget = 16384 if self.device.type == "cuda" else 1024
        encs = []
        for a, b in spans:
            e = self.tok(text[a:b], add_special_tokens=False, return_offsets_mapping=True)
            ids = e["input_ids"][: self.window]
            encs.append((ids, [a + o[0] for o in e["offset_mapping"][: len(ids)]]))
        order = sorted(range(len(spans)), key=lambda k: len(encs[k][0]))
        out: list = [None] * len(spans)
        done, k = 0, 0
        while k < len(order):
            width = len(encs[order[k]][0]) + 2
            group = [order[k]]
            k += 1
            while k < len(order):
                w = len(encs[order[k]][0]) + 2
                if w * (len(group) + 1) > token_budget:
                    break
                group.append(order[k])
                width = w
                k += 1
            inp = torch.full((len(group), width), self.pad_id, dtype=torch.long)
            att = torch.zeros((len(group), width), dtype=torch.long)
            for r, idx in enumerate(group):
                ids = encs[idx][0]
                inp[r, 0] = self.cls_id
                inp[r, 1:1 + len(ids)] = torch.tensor(ids, dtype=torch.long)
                inp[r, 1 + len(ids)] = self.sep_id
                att[r, : len(ids) + 2] = 1
            _, c_tok, _ = self.model.token_scores(inp.to(self.device), att.to(self.device))
            for r, idx in enumerate(group):
                n = len(encs[idx][0])
                out[idx] = (encs[idx][1], c_tok[r, 1:1 + n].cpu())
            done += len(group)
            if progress:
                progress(done / len(spans))
        return out

    def _doc_pass(self, canon: str, progress=None):
        """MELD's canonical whole-document scoring: overall score, family and task."""
        ids = self.tok(canon, add_special_tokens=False, truncation=False)["input_ids"]
        if not ids:
            raise ValueError("The document has no readable text.")
        c, s, o = self._token_scores(ids, 4 if self.device.type == "cuda" else 1, progress)
        return (len(ids), float(top_quantile_mean(c, self.rho)),
                top_quantile_mean(s, self.rho), top_quantile_mean(o, self.rho))

    def local_scores(self, canon: str, sents: list[tuple[int, int]], cal: dict, progress=None):
        """Per-sentence scores from local windows, plus per-word heat from the window used."""
        wins = build_windows(canon, sents, int(cal["window_words"]))
        spans = [(sents[i][0], sents[j][1]) for i, j in wins]
        res = self.score_spans(canon, spans, progress=progress)
        best = [(math.inf, -1)] * len(sents)
        for k, ((a, b), (st, sc)) in enumerate(zip(wins, res)):
            whole = float(top_quantile_mean(sc, self.rho))
            for si in range(a, b + 1):
                if cal["variant"] == "a":
                    v = whole
                else:
                    i0, i1 = bisect.bisect_left(st, sents[si][0]), bisect.bisect_left(st, sents[si][1])
                    if i1 <= i0:
                        continue
                    v = float(top_quantile_mean(sc[i0:i1], self.rho))
                if v < best[si][0]:
                    best[si] = (v, k)
        words = []
        for si, (v, k) in enumerate(best):
            ws = []
            if k >= 0:
                st, sc = res[k]
                cl = sc.tolist()
                for m in _WORD_SPAN.finditer(canon, *sents[si]):
                    i0, i1 = bisect.bisect_left(st, m.start()), bisect.bisect_left(st, m.end())
                    if i1 > i0:
                        ws.append([m.start(), m.end(), round(sum(cl[i0:i1]) / (i1 - i0), 2)])
            words.append(ws)
        return [b[0] for b in best], words

    def analyze(self, text: str, domain: str = "general", progress=None, profile: dict | None = None) -> dict:
        t0 = time.time()
        cal = calibration(profile)
        canon = canonicalize(text)
        paras = split_document(canon)
        flat = [(p_i, s) for p_i, p in enumerate(paras) for s in p.sentences]
        sents = [(s.start, s.end) for _, s in flat]
        if not sents:
            raise ValueError("The document has no readable text.")
        # progress: whole-document pass ~25%, local windows ~75% of the work
        p_doc = (lambda f: progress(0.25 * f)) if progress else None
        p_loc = (lambda f: progress(0.25 + 0.75 * f)) if progress else None
        n_tok, score, fam, ops = self._doc_pass(canon, p_doc)
        sc, words = self.local_scores(canon, sents, cal, p_loc)
        raw = ["ai" if v >= cal["red"] else "mixed" if v >= cal["yellow"] else "human" for v in sc]
        lv = min_run(raw, "ai", int(cal["min_run"]))

        paragraphs: list[dict] = [{"start": p.start, "end": p.end, "sentences": []} for p in paras]
        total_w = ai_w = mixed_w = 0
        for (p_i, s), v, l, ws in zip(flat, sc, lv, words):
            if math.isinf(v):
                v, l = float("nan"), "human"
            paragraphs[p_i]["sentences"].append({
                "start": s.start, "end": s.end, "score": round(v, 3) if v == v else None, "level": l,
                "words": ws, "phrases": style.phrase_hits(canon, s.start, s.end)})
            total_w += len(ws)
            ai_w += len(ws) if l == "ai" else 0
            mixed_w += len(ws) if l == "mixed" else 0
        rank = {"human": 0, "mixed": 1, "ai": 2}
        for p in paragraphs:
            p["level"] = max((x["level"] for x in p["sentences"]), key=rank.get, default="human")
        paragraphs = [p for p in paragraphs if p["sentences"]]

        th = self.thresholds(domain)
        n_words = len(_WORD_SPAN.findall(canon))
        return {
            "text": canon,
            "document": {
                "score": round(score, 3),
                "p_ai": round(1 / (1 + math.exp(-score)), 4),
                "level": _level(score, th["strong"], th["weak"]),
                "thresholds": th,
                "local": {k: cal[k] for k in ("red", "yellow", "window_words", "personal")},
                "ai_share": round(ai_w / total_w, 3) if total_w else 0.0,
                "mixed_share": round(mixed_w / total_w, 3) if total_w else 0.0,
                "families": _softmax(fam, self.cfg["families"]),
                "tasks": _softmax(ops, self.cfg["ops"]),
                "n_tokens": n_tok,
                "n_words": n_words,
                "too_short": n_words < MIN_WORDS,
                "language": style.language_check(canon),
            },
            "paragraphs": paragraphs,
            "style": style.document_stats(canon, sents),
            "runtime": {"seconds": round(time.time() - t0, 2), **self.device_info},
        }
