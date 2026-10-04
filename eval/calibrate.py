"""Choose local thresholds from eval/results/raw/*.pkl (see definitely_human.calib).

    python eval/calibrate.py            # report
    python eval/calibrate.py --write    # write backend/definitely_human/engine/calibration.json
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from definitely_human.calib import choose, load_records  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--doc-fpr", type=float, default=0.05, help="share of ~8k-word human docs with any red")
ap.add_argument("--yellow-sentence-fpr", type=float, default=0.03)
ap.add_argument("--run", type=int, default=2)
ap.add_argument("--write", action="store_true")
a = ap.parse_args()
recs = load_records(ROOT / "eval" / "results" / "raw")
print(len(recs), "documents")
cfg, _ = choose(recs, a.doc_fpr, a.yellow_sentence_fpr, a.run)
kinds = {}
for r in recs:
    kinds.setdefault(r["kind"].split("/")[0], []).append(r["doc_score"])
for k, v in kinds.items():
    print(f"doc score {k:13s} n={len(v):3d} median {np.median(v):+.2f} min {min(v):+.2f} max {max(v):+.2f}")
print("BEST", json.dumps(cfg))
if a.write:
    out = ROOT / "backend" / "definitely_human" / "engine" / "calibration.json"
    out.write_text(json.dumps(cfg, indent=2))
    print("wrote", out)
