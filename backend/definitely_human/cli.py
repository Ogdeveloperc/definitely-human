"""Command line: `definitely-human serve | check FILE | download | doctor`."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

from .paths import MELD_FILES, MELD_REPO, MELD_REVISION, MODEL_DIR


def _offline() -> None:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def cmd_download(_a) -> int:
    from huggingface_hub import hf_hub_download

    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for f in MELD_FILES:
        if (MODEL_DIR / f).exists():
            print(f"  ok   {f}")
            continue
        print(f"  get  {f} ...", flush=True)
        hf_hub_download(MELD_REPO, f, revision=MELD_REVISION, local_dir=MODEL_DIR)
    print(f"Model ready in {MODEL_DIR}")
    return 0


def cmd_doctor(a) -> int:
    _offline()
    from .engine.detector import pick_device

    _, info = pick_device(a.device)
    info["model_dir"] = str(MODEL_DIR)
    info["model_present"] = (MODEL_DIR / "model.safetensors").exists()
    print(json.dumps(info, indent=2))
    return 0 if info["model_present"] else 1


def cmd_check(a) -> int:
    _offline()
    from . import docparse
    from .engine.detector import Detector

    p = Path(a.file)
    text, meta = docparse.extract(p.name, p.read_bytes())
    r = Detector(MODEL_DIR, device=a.device).analyze(text, a.domain)
    if a.json:
        print(json.dumps(r))
        return 0
    d = r["document"]
    print(f"{p.name}: score {d['score']:+.2f} (AI threshold {d['thresholds']['strong']:+.2f}) "
          f"-> {d['level'].upper()}  | AI-flagged words {d['ai_share']:.0%}  | {r['runtime']['seconds']}s on {r['runtime']['device']}")
    for para in r["paragraphs"]:
        for s in para["sentences"]:
            mark = {"ai": "!!", "mixed": "? ", "human": "  "}[s["level"]]
            sc = f"{s['score']:+6.2f}" if s["score"] is not None else "   n/a"
            print(f"{mark} {sc}  {r['text'][s['start']:s['end']][:110]}")
    return 0


def _already_running(port: int) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1.5) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def cmd_serve(a) -> int:
    _offline()
    url = f"http://127.0.0.1:{a.port}"
    if _already_running(a.port):  # second double-click: just show the open app
        webbrowser.open(url)
        return 0
    import uvicorn

    from . import server
    from .paths import DATA_DIR

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if sys.stdout is None or sys.stderr is None:  # pythonw: libraries writing to them would crash
        sink = open(DATA_DIR / "console.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or sink
        sys.stderr = sys.stderr or sink
    handlers = [logging.FileHandler(DATA_DIR / "app.log", encoding="utf-8")]
    if sys.stdout is not None and sys.stdout.isatty():
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)
    threading.Thread(target=server.load_model, args=(a.device,), daemon=True).start()
    if a.exit_when_closed:
        threading.Thread(target=server.watch_idle, daemon=True).start()
    if not a.no_browser:
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True).start()
    print(f"Definitely Human is running at {url}  (close this window to stop)")
    uvicorn.run(server.app, host="127.0.0.1", port=a.port, log_level="warning", log_config=None)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="definitely-human")
    ap.add_argument("--device", choices=["cuda", "cpu"], default=None)
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--no-browser", action="store_true")
    s.add_argument("--exit-when-closed", action="store_true", help="quit after the browser tab closes")
    c = sub.add_parser("check")
    c.add_argument("file")
    c.add_argument("--domain", choices=["essay", "paper", "general"], default="general")
    c.add_argument("--json", action="store_true")
    sub.add_parser("download")
    sub.add_parser("doctor")
    a = ap.parse_args()
    fn = {"serve": cmd_serve, "check": cmd_check, "download": cmd_download,
          "doctor": cmd_doctor}.get(a.cmd or "serve")
    return fn(a) if a.cmd else cmd_serve(ap.parse_args(["serve"]))


if __name__ == "__main__":
    sys.exit(main())
