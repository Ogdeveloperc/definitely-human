"""Score evaluation documents with local windows (resumable). See definitely_human.calib.

    python eval/run_windows.py --per-kind 12 --device mps   # Mac
    python eval/run_windows.py --per-kind 200               # RTX
"""
import argparse
import gc
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from definitely_human.calib import build_docs, fetch_data, score_docs  # noqa: E402
from definitely_human.engine.detector import Detector  # noqa: E402
from definitely_human.paths import MODEL_DIR  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--per-kind", type=int, default=40)
ap.add_argument("--sizes", default="60,120")
ap.add_argument("--device", default=None)
a = ap.parse_args()
data = ROOT / "eval" / "data"
fetch_data(data)
docs = build_docs(data, a.per_kind)
gc.collect()
print(len(docs), "documents", flush=True)
if a.device == "mps":  # calibration on a Mac only; the app itself uses CUDA or CPU
    import torch
    import definitely_human.engine.detector as D
    D.pick_device = lambda p=None: (torch.device("mps"), {"device": "mps"})
det = Detector(MODEL_DIR, device=a.device)
score_docs(det, docs, [int(x) for x in a.sizes.split(",")], ROOT / "eval" / "results" / "raw",
           log=lambda m: print(m, flush=True))
