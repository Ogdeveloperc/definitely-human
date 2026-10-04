"""OCR for scanned PDFs with docTR (Mindee, Apache-2.0), fully offline.

docTR runs on the same PyTorch as the detector, so on the RTX it reads a page in
well under a second. Its weights live in models/doctr and are fetched once by
`definitely-human download`; the app never goes online when a scanned file
comes in. OCR mistakes ("rn" read as "m") also distort the detector, so OCR'd
text is flagged in the UI as less reliable.
"""
from __future__ import annotations

import logging
import os
import threading

from .paths import DOCTR_DIR

os.environ.setdefault("DOCTR_CACHE_DIR", str(DOCTR_DIR))
log = logging.getLogger(__name__)

DET_ARCH, RECO_ARCH = "db_resnet50", "crnn_vgg16_bn"
_lock = threading.Lock()
_predictor = None


class OcrUnavailable(RuntimeError):
    pass


def _get(allow_download: bool = False):
    global _predictor
    with _lock:
        if _predictor is None:
            if not allow_download and not any(DOCTR_DIR.rglob("*.pt")):
                raise OcrUnavailable("This PDF is a scanned image and the OCR model isn't installed. "
                                     "Run the Repair shortcut (or `definitely-human download`) once with internet.")
            import torch
            from doctr.models import ocr_predictor

            p = ocr_predictor(det_arch=DET_ARCH, reco_arch=RECO_ARCH, pretrained=True,
                              assume_straight_pages=True)
            if torch.cuda.is_available():
                p = p.cuda()
            _predictor = p
        return _predictor


def prefetch() -> None:
    """Download the OCR weights into models/doctr (installer step)."""
    _get(allow_download=True)


def ocr_pdf(data: bytes) -> tuple[list[str], str]:
    """Return per-page text (lines; a blank line between text blocks) and the engine used."""
    from doctr.io import DocumentFile

    pages = DocumentFile.from_pdf(data, scale=2)  # 144 dpi: plenty for body text
    result = _get()(pages)
    texts = []
    for page in result.pages:
        lines: list[str] = []
        for block in page.blocks:
            for line in block.lines:
                t = " ".join(w.value for w in line.words).strip()
                if t:
                    lines.append(t)
            lines.append("")
        texts.append("\n".join(lines))
    return texts, f"doctr ({DET_ARCH} + {RECO_ARCH})"
