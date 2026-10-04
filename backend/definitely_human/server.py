"""Local web server. Binds to 127.0.0.1 only; nothing leaves the machine."""
from __future__ import annotations

import json
import logging
import math
import statistics
import threading
from datetime import date

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import docparse
from .paths import CALIB_DIR, GITHUB_REPO, LOCAL_CALIBRATION, MODEL_DIR, PROFILE, STATIC_DIR

log = logging.getLogger(__name__)
MAX_UPLOAD = 50 * 2**20


class _State:
    detector = None
    error: str | None = None
    lock = threading.Lock()
    calib: dict = {"running": False}


state = _State()


def load_model(device: str | None = None) -> None:
    from .engine.detector import Detector

    try:
        state.detector = Detector(MODEL_DIR, device=device)
    except Exception as e:  # noqa: BLE001
        log.exception("model load failed")
        state.error = f"{type(e).__name__}: {e}"


app = FastAPI(title="Definitely Human", docs_url=None, redoc_url=None)


class TextIn(BaseModel):
    text: str
    domain: str = "general"


_last_ping = {"t": None}


@app.post("/api/ping")
def ping():
    """The page pings while it is open; see watch_idle()."""
    import time

    _last_ping["t"] = time.monotonic()
    return {"ok": True}


def watch_idle(timeout: float = 90.0) -> None:
    """Exit once the browser tab has been closed for `timeout` seconds (desktop app mode)."""
    import os
    import time

    while True:
        time.sleep(5)
        t = _last_ping["t"]
        if t is not None and time.monotonic() - t > timeout and not state.calib.get("running"):
            log.info("no open page for %.0fs, shutting down", timeout)
            os._exit(0)


@app.get("/api/status")
def status():
    d = state.detector
    return {"ready": d is not None, "error": state.error,
            "device": d.device_info if d else None}


def _profile() -> dict | None:
    try:
        return json.loads(PROFILE.read_text()) if PROFILE.exists() else None
    except Exception:  # noqa: BLE001
        return None


def _run(text: str, domain: str) -> dict:
    if state.calib.get("running"):
        raise HTTPException(409, "Calibration is running. Please wait until it finishes.")
    if state.detector is None:
        raise HTTPException(503, state.error or "The model is still loading.")
    if not text.strip():
        raise HTTPException(400, "The text is empty.")
    with state.lock:  # one GPU, one analysis at a time
        try:
            return state.detector.analyze(text, domain, profile=_profile())
        except ValueError as e:
            raise HTTPException(400, str(e)) from e


@app.post("/api/analyze")
def analyze(body: TextIn):
    return {"source": {"kind": "text"}, **_run(body.text, body.domain)}


@app.post("/api/analyze-file")
async def analyze_file(file: UploadFile = File(...), domain: str = Form("general")):
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 50 MB.")
    try:
        text, meta = docparse.extract(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:  # noqa: BLE001
        log.exception("extract failed")
        raise HTTPException(400, f"Couldn't read this file ({type(e).__name__}).") from e
    return {"source": {"kind": "file", "name": file.filename, **meta}, **_run(text, domain)}


async def _read_upload(file: UploadFile) -> str:
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 50 MB.")
    try:
        return docparse.extract(file.filename or "", data)[0]
    except ValueError as e:
        raise HTTPException(400, f"{file.filename}: {e}") from e


@app.get("/api/profile")
def get_profile():
    p = _profile()
    return {"active": p is not None, **(p or {})}


@app.delete("/api/profile")
def delete_profile():
    PROFILE.unlink(missing_ok=True)
    return {"active": False}


@app.post("/api/profile")
async def build_profile(files: list[UploadFile] = File(...)):
    """Learn the writer's own baseline from texts they wrote before AI tools existed."""
    from .engine.detector import _WORD_SPAN, calibration
    from .engine.local import clean_threshold
    from .engine.meld_model import canonicalize
    from .engine.segment import split_document

    if state.detector is None:
        raise HTTPException(503, state.error or "The model is still loading.")
    texts = [await _read_upload(f) for f in files]
    words = sum(len(t.split()) for t in texts)
    if len(texts) < 3 or words < 1500:
        raise HTTPException(400, "Add at least 3 documents and 1,500 words in total.")
    cal = calibration()
    reds, all_scores = [], []
    with state.lock:
        for t in texts:
            canon = canonicalize(t)
            sents = [(s.start, s.end) for p in split_document(canon) for s in p.sentences]
            sc, _ = state.detector.local_scores(canon, sents, cal)
            reds.append(clean_threshold(sc, int(cal["min_run"])))
            all_scores += [v for v in sc if not math.isinf(v) and v == v]
    margin = 0.25
    q = statistics.quantiles(all_scores, n=20)[-1] if len(all_scores) >= 20 else max(all_scores)
    prof = {"red": round(max(reds) + margin, 3), "yellow": round(q + margin, 3),
            "documents": len(texts), "words": words, "created": date.today().isoformat(),
            "shipped_red": cal["red"], "shipped_yellow": cal["yellow"]}
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(json.dumps(prof, indent=2))
    eff = calibration(prof)
    return {"active": True, **prof, "effective_red": eff["red"], "effective_yellow": eff["yellow"],
            "changed": eff["personal"]}


CALIB_PER_KIND = 150  # ~1,900 documents; about 15-30 minutes on an RTX 5070


def _calibrate_job() -> None:
    from . import calib

    st = state.calib
    log_lines: list[str] = st["log"]

    def log(m: str) -> None:
        log_lines.append(m)
        del log_lines[:-200]

    try:
        st.update(phase="download", progress=0.0)
        calib.fetch_data(CALIB_DIR / "data", log)
        st.update(phase="prepare")
        docs = calib.build_docs(CALIB_DIR / "data", CALIB_PER_KIND)
        st.update(phase="score", total=len(docs))
        with state.lock:
            calib.score_docs(state.detector, docs, [60, 120], CALIB_DIR / "raw", log,
                             progress=lambda f: st.update(progress=round(f, 4)))
        st.update(phase="choose")
        cfg, table = calib.choose(calib.load_records(CALIB_DIR / "raw"), log=log)
        cfg["created"] = date.today().isoformat()
        cfg["device"] = state.detector.device_info.get("gpu", state.detector.device_info["device"])
        LOCAL_CALIBRATION.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_CALIBRATION.write_text(json.dumps(cfg, indent=2))
        st.update(phase="done", result=cfg, table=table, progress=1.0)
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).exception("calibration failed")
        st.update(phase="error", error=f"{type(e).__name__}: {e}")
    finally:
        st["running"] = False


@app.post("/api/calibrate")
def calibrate_start():
    if state.detector is None:
        raise HTTPException(503, state.error or "The model is still loading.")
    if state.calib.get("running"):
        return state.calib
    state.calib = {"running": True, "phase": "starting", "progress": 0.0, "log": []}
    threading.Thread(target=_calibrate_job, daemon=True).start()
    return state.calib


@app.get("/api/calibrate")
def calibrate_status():
    st = dict(state.calib)
    st["log"] = st.get("log", [])[-8:]
    if not st.get("running") and "result" not in st and LOCAL_CALIBRATION.exists():
        st["result"] = json.loads(LOCAL_CALIBRATION.read_text())
    return st


@app.delete("/api/calibrate")
def calibrate_reset():
    """Go back to the calibration that shipped with the app."""
    if state.calib.get("running"):
        raise HTTPException(409, "Calibration is running.")
    LOCAL_CALIBRATION.unlink(missing_ok=True)
    state.calib = {"running": False}
    return state.calib


def _version_tuple(v: str) -> tuple:
    return tuple(int(x) for x in v.lstrip("vV").split(".") if x.isdigit())


@app.get("/api/update-check")
def update_check():
    """Ask GitHub for the latest release tag. Sends nothing but the request itself."""
    import json
    import urllib.request
    from importlib.metadata import version

    current = version("definitely-human")
    req = urllib.request.Request(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "definitely-human"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            rel = json.load(r)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Update check failed: {e}") from e
    latest = rel.get("tag_name", "").lstrip("vV")
    return {"current": current, "latest": latest, "url": rel.get("html_url", ""),
            "update": bool(latest) and _version_tuple(latest) > _version_tuple(current)}


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = (STATIC_DIR / path).resolve()
        if path and f.is_file() and STATIC_DIR.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(STATIC_DIR / "index.html")
