"""Local web server. Binds to 127.0.0.1 only; nothing leaves the machine."""
from __future__ import annotations

import json
import logging
import math
import statistics
import threading
from datetime import date

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
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


class ExportIn(BaseModel):
    text: str
    format: str = "docx"


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


def _check_ready(text: str) -> None:
    if state.calib.get("running"):
        raise HTTPException(409, "Calibration is running. Please wait until it finishes.")
    if state.detector is None:
        raise HTTPException(503, state.error or "The model is still loading.")
    if not text.strip():
        raise HTTPException(400, "The text is empty.")


def _stream(text: str, domain: str, source: dict) -> StreamingResponse:
    """NDJSON stream: {"progress": f} lines while working, then {"result": ...} or {"error": ...}."""
    import queue

    _check_ready(text)
    q: queue.Queue = queue.Queue()

    def work():
        try:
            with state.lock:  # one GPU, one analysis at a time
                r = state.detector.analyze(text, domain, profile=_profile(),
                                           progress=lambda f: q.put({"progress": round(f, 3)}))
            q.put({"result": {"source": source, **r}})
        except ValueError as e:
            q.put({"error": str(e)})
        except Exception as e:  # noqa: BLE001
            log.exception("analysis failed")
            q.put({"error": f"{type(e).__name__}: {e}"})

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while True:
            m = q.get()
            yield json.dumps(m) + "\n"
            if "progress" not in m:
                return

    return StreamingResponse(gen(), media_type="application/x-ndjson")


@app.post("/api/analyze")
def analyze(body: TextIn):
    return _stream(body.text, body.domain, {"kind": "text"})


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
    return _stream(text, domain, {"kind": "file", "name": file.filename, **meta})


@app.post("/api/export")
def export(body: ExportIn):
    """Plain .txt or a simple .docx (one paragraph per blank-line-separated block)."""
    import io

    from fastapi.responses import Response

    paras = [p.strip() for p in body.text.split("\n\n") if p.strip()]
    if body.format == "txt":
        return Response("\n\n".join(paras) + "\n", media_type="text/plain; charset=utf-8")
    if body.format != "docx":
        raise HTTPException(400, "format must be docx or txt")
    import docx

    d = docx.Document()
    for p in paras:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return Response(buf.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


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
    from .engine.style import language_check

    texts = [await _read_upload(f) for f in files]
    # The detector only understands English; other languages would give meaningless baselines.
    not_en = [f.filename for f, t in zip(files, texts) if not language_check(t)["english"]]
    if not_en:
        raise HTTPException(400, "These files don't look like English, please remove them / "
                                 "Bu dosyalar İngilizce görünmüyor, lütfen çıkarın: " + ", ".join(not_en))
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
            "shipped_red": cal["red"], "shipped_yellow": cal["yellow"],
            "window_words": cal["window_words"], "variant": cal["variant"]}
    PROFILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE.write_text(json.dumps(prof, indent=2))
    eff = calibration(prof)
    return {"active": True, **prof, "effective_red": eff["red"], "effective_yellow": eff["yellow"],
            "changed": eff["personal"]}


import os  # noqa: E402

# ~150 per kind on an RTX 5070; overridable for testing the pipeline on slow machines.
CALIB_PER_KIND = int(os.environ.get("DH_CALIB_PER_KIND", "60"))
CALIB_SIZES = [int(x) for x in os.environ.get("DH_CALIB_SIZES", "60,120").split(",")]


def _calibrate_job() -> None:
    from . import calib

    st = state.calib
    log_lines: list[str] = st["log"]

    def log(m: str) -> None:
        log_lines.append(m)
        del log_lines[:-200]

    try:
        st.update(phase="download", progress=0.0)
        calib.fetch_data(CALIB_DIR / "data", log,
                         progress=lambda f, detail: st.update(progress=round(f, 4), detail=detail))
        st.pop("detail", None)
        st.update(phase="prepare")
        docs = calib.build_docs(CALIB_DIR / "data", CALIB_PER_KIND)
        st.update(phase="score", total=len(docs))
        with state.lock:
            calib.score_docs(state.detector, docs, CALIB_SIZES, CALIB_DIR / "raw", log,
                             progress=lambda f: st.update(progress=round(f, 4)))
        st.update(phase="choose")
        cfg, table = calib.choose(calib.load_records(CALIB_DIR / "raw"), log=log)
        cfg["created"] = date.today().isoformat()
        cfg["device"] = state.detector.device_info.get("gpu", state.detector.device_info["device"])
        LOCAL_CALIBRATION.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_CALIBRATION.write_text(json.dumps(_finite(cfg), indent=2))
        st.update(phase="done", result=cfg, table=table, progress=1.0)
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).exception("calibration failed")
        st.update(phase="error", error=f"{type(e).__name__}: {e}")
    finally:
        st["running"] = False


def _finite(o):
    """JSON can't carry NaN/inf: turn them into null (e.g. a metric with no samples)."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_finite(v) for v in o]
    return o


@app.post("/api/calibrate")
def calibrate_start():
    if state.detector is None:
        raise HTTPException(503, state.error or "The model is still loading.")
    if state.calib.get("running"):
        return state.calib
    state.calib = {"running": True, "phase": "starting", "progress": 0.0, "log": []}
    threading.Thread(target=_calibrate_job, daemon=True).start()
    return _finite(state.calib)


def _json_safe(x):
    """NaN/inf aren't valid JSON; a status poll must never fail because of one."""
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if isinstance(x, dict):
        return {k: _json_safe(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_json_safe(v) for v in x]
    return x


@app.get("/api/calibrate")
def calibrate_status():
    return _json_safe(_calibrate_status())


def _calibrate_status():
    st = dict(state.calib)
    st["log"] = st.get("log", [])[-8:]
    if not st.get("running") and "result" not in st and LOCAL_CALIBRATION.exists():
        st["result"] = json.loads(LOCAL_CALIBRATION.read_text())
    return _finite(st)


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
