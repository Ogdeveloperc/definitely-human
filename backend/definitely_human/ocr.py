"""OCR for scanned PDFs with Windows' built-in, offline OCR engine (Windows.Media.Ocr).

Windows only: the app targets Windows, and the open-source engines we tried
(RapidOCR's default models) mangle English (dropped spaces, missed lines).
OCR mistakes ("rn" read as "m") also distort the detector, so OCR'd text is
flagged in the UI as less reliable.
"""
from __future__ import annotations

import io
import logging
import sys

log = logging.getLogger(__name__)
DPI = 200


def _pages(data: bytes):
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    for i in range(len(pdf)):
        yield pdf[i].render(scale=DPI / 72).to_pil().convert("RGB")


def _windows_engine():
    from winrt.windows.globalization import Language
    from winrt.windows.media.ocr import OcrEngine

    for tag in ("en-US", "en-GB", "en"):
        lang = Language(tag)
        if OcrEngine.is_language_supported(lang):
            return OcrEngine.try_create_from_language(lang), tag
    eng = OcrEngine.try_create_from_user_profile_languages()
    return eng, "user-profile"


def _windows_ocr(img, engine) -> str:
    import asyncio

    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    async def run() -> str:
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(list(buf.getvalue()))
        await writer.store_async()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        return "\n".join(line.text for line in result.lines)

    return asyncio.run(run())


class OcrUnavailable(RuntimeError):
    pass


def ocr_pdf(data: bytes) -> tuple[list[str], str]:
    """Return per-page text and the engine used."""
    if sys.platform != "win32":
        raise OcrUnavailable("This PDF is a scanned image. Reading scanned PDFs (OCR) works on Windows only.")
    try:
        engine, tag = _windows_engine()
    except Exception as e:  # noqa: BLE001
        raise OcrUnavailable(f"Windows OCR isn't available on this PC ({e}).") from e
    if engine is None:
        raise OcrUnavailable("Windows OCR has no language installed. Add English in Settings > Time & language.")
    return [_windows_ocr(img, engine) for img in _pages(data)], f"windows-ocr ({tag})"
