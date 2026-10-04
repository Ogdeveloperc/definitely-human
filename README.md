# Definitely Human™

**Offline, explainable AI-text checker for English essays, papers and theses.**
Paste text or drop a Word/PDF file. Instead of one opaque percentage, the app shows
**which regions** read as AI-written, on a green / yellow / red map of the text.

- 100% local: no API, no cloud. Text never leaves the computer.
  Network is used only for: installation, the one-time *Full calibration*, and a version check at start
  (only the latest release number is fetched; can be turned off in Settings).
- Detector: [MELD](https://huggingface.co/anon-review-meld-2026/meld), the top open-source model on the RAID benchmark
  (a 1B-parameter encoder, not a chat LLM).
- Explanations come from measurements, never generated text: per-region model scores, per-word emphasis,
  measured style statistics (sentence-length variety, stock phrases, em dashes).
- Fix and rescan: click a flagged paragraph, rewrite it in place, rescan; see the before/after numbers.
- Export the edited text (.docx / .txt) or a coloured analysis report (.html, printable to PDF).
- "Learn my writing": add a few pre-2022 texts you wrote; your own style won't be flagged.
- Word, PDF and text files. References, running headers and page numbers are removed.
  Scanned PDFs are read offline with docTR OCR (runs on the GPU).
- English only: other languages are detected and not scored.

> No AI detector is proof. Treat red regions as places to review, not as a verdict.

## Install (Windows, NVIDIA GPU recommended)

**Easiest:** download [`DefinitelyHuman-Indir-Kur.cmd`](https://github.com/Ogdeveloperc/definitely-human/releases/latest/download/DefinitelyHuman-Indir-Kur.cmd)
and double-click it. It fetches the newest installer and runs it. Run it again any time to update.

Or by hand:

1. Download `DefinitelyHuman-Setup-x.y.z.exe` from [Releases](https://github.com/Ogdeveloperc/definitely-human/releases/latest).
2. Run it. It installs to `C:\DefinitelyHuman`, then downloads Python, the GPU build of PyTorch,
   the detector and the OCR model (~7 GB in total, needs internet once).
3. Open **Definitely Human** from the desktop. On first start, run **Finish setup → Start calibration**
   (15–30 min on an RTX 5070). After that everything runs offline.

Updates: the app tells you when a new version is out; run the new Setup.exe over the old one.
The model, settings and calibration are kept.

## How it works

1. **Whole document** — MELD's calibrated document score (fp32, 2048-token windows, top-quantile pooling).
   This gives the overall verdict and which model family / writing mode it most resembles.
2. **Regions** — MELD attends to its whole input, so AI text bleeds into neighbouring human text.
   Each sentence therefore starts its own window of about *N* words, every window is scored on its own,
   and a sentence's score is the **minimum** over the windows that contain it: if any window around a
   sentence reads clean, so does the sentence.
3. **Calibration** — red/yellow thresholds are chosen so that only ~2% of fully human long documents show
   *any* red region (with a minimum run of 2 sentences). The calibration also reports how many AI sentences
   are caught in mixed human+AI documents. See `backend/definitely_human/calib.py`.

## Develop

```bash
uv sync                                # Python 3.12 + deps (macOS: CPU/MPS torch; Windows: CUDA 12.8 torch)
uv run definitely-human download       # fetch the model into models/meld
cd frontend && npm install && npm run build && cd ..
uv run definitely-human serve          # http://127.0.0.1:8765
uv run definitely-human check essay.docx --domain essay
PYTHONPATH=backend uv run pytest -q tests
```

Calibrate from the command line (GPU strongly recommended):

```bash
uv run python eval/run_windows.py --per-kind 150
uv run python eval/calibrate.py --write
```

Release: bump `version` in `pyproject.toml`, tag `vX.Y.Z`, push. GitHub Actions builds the installer,
installs it on a Windows runner, analyzes sample files, and attaches the `.exe` to the release.

## License

MIT. See [THIRD_PARTY.md](THIRD_PARTY.md) for bundled and downloaded components.
