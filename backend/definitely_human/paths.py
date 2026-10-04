from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = Path(os.environ.get("DH_MODEL_DIR", ROOT / "models" / "meld"))
DOCTR_DIR = Path(os.environ.get("DH_DOCTR_DIR", ROOT / "models" / "doctr"))
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR = Path(os.environ.get("DH_DATA_DIR", ROOT / "data"))
PROFILE = DATA_DIR / "profile.json"
LOCAL_CALIBRATION = DATA_DIR / "calibration.json"
CALIB_DIR = DATA_DIR / "calibration-work"

MELD_REPO = "anon-review-meld-2026/meld"
MELD_REVISION = "8990324abd92e1fa17072f6887ea1e5c1cef5abc"
MELD_FILES = ["config.json", "meld_config.json", "tokenizer.json", "tokenizer_config.json",
              "model.safetensors", "README.md"]

# GitHub repository used by "Check for updates" (owner/name). Set once the repo exists.
GITHUB_REPO = os.environ.get("DH_GITHUB_REPO", "OWNER/definitely-human")
