"""Model-free tests: segmentation, local windows, document parsing, style hints."""
from pathlib import Path

from definitely_human import docparse
from definitely_human.engine import style
from definitely_human.engine.local import build_windows, clean_threshold, min_run, sentence_scores
from definitely_human.engine.segment import split_document

FIX = Path(__file__).parent / "fixtures"


def test_sentences_keep_abbreviations_and_offsets():
    t = "Smith et al. found a 3.5 percent rise, e.g. in Fig. 2. It held. Did it? Yes!\n\nNew para here."
    paras = split_document(t)
    assert len(paras) == 2
    sents = [t[s.start:s.end] for s in paras[0].sentences]
    assert sents == ["Smith et al. found a 3.5 percent rise, e.g. in Fig. 2.", "It held.", "Did it?", "Yes!"]


def test_windows_reach_target_and_cover_all_sentences():
    text = " ".join(f"Sentence number {i} has exactly seven words." for i in range(20))
    sents = [(s.start, s.end) for p in split_document(text) for s in p.sentences]
    wins = build_windows(text, sents, 30)
    covered = {i for a, b in wins for i in range(a, b + 1)}
    assert covered == set(range(len(sents)))
    for a, b in wins:
        assert sum(len(text[sents[i][0]:sents[i][1]].split()) for i in range(a, b + 1)) >= 30
    assert len(set(wins)) == len(wins)


def test_sentence_score_is_min_over_windows():
    # sentence 2 sits in a high window and a low one: the low one wins
    wins = [(0, 2), (2, 4)]
    assert sentence_scores(5, wins, [5.0, -1.0]) == [5.0, 5.0, -1.0, -1.0, -1.0]


def test_min_run_drops_isolated_red():
    assert min_run(["human", "ai", "human", "ai", "ai"], "ai", 2) == ["human", "mixed", "human", "ai", "ai"]


def test_clean_threshold():
    assert clean_threshold([0.0, 3.0, 1.0, 2.5, 2.8], 2) == 2.5


def test_docx_drops_headings_and_references():
    text, meta = docparse.extract("x.docx", (FIX / "sample.docx").read_bytes())
    assert meta["references_removed"]
    assert "Springer" not in text and "Restoring an Old Radio" not in text
    assert text.startswith("I spent most of last summer")


def test_pdf_drops_headers_page_numbers_and_references():
    text, meta = docparse.extract("x.pdf", (FIX / "sample.pdf").read_bytes())
    assert meta["references_removed"]
    assert "Running Header" not in text and "Springer" not in text
    assert "\n\n1\n\n" not in text
    assert "grandfather's old radio" in text and "algorithmic bias" in text


def test_style_hits():
    t = "Moreover, it is important to note that we delve into this."
    hits = [h["phrase"] for h in style.phrase_hits(t, 0, len(t))]
    assert hits == ["moreover", "it is important to note", "delve"]


def test_language_check():
    assert not style.language_check("Yapraklar dökülüyor, fiyatlar da! Güneş gözlükleri şimdi yüzde elli indirimli.")["english"]
    assert not style.language_check("Der Hund läuft schnell über die Straße und die Katze schläft im Haus.")["english"]
    assert style.language_check("The café served crème brûlée and the naïve customers loved it, which was not surprising.")["english"]
    assert style.language_check("I spent most of last summer trying to get my grandfather's old radio working again.")["english"]


def test_driver_check():
    from definitely_human.engine import gpu

    out = "NVIDIA GeForce RTX 5070 Laptop GPU, 581.42, 8151\n"
    g = gpu.parse_smi(out)
    assert g == [{"name": "NVIDIA GeForce RTX 5070 Laptop GPU", "driver": "581.42", "vram_gb": 8.0}]
    assert gpu.driver_status(True, g)["status"] == "ok"
    old = gpu.parse_smi("NVIDIA GeForce RTX 5070 Laptop GPU, 556.12, 8151")
    assert gpu.driver_status(False, old)["status"] == "outdated"
    assert gpu.driver_status(False, g)["status"] == "cuda_error"
    assert gpu.driver_status(False, [])["status"] == "no_nvidia"
    assert gpu.parse_version("570.65") >= (570, 65) > gpu.parse_version("566.36")


def test_device_picker_uses_mps_when_cuda_is_absent(monkeypatch):
    from definitely_human.engine import detector, gpu

    monkeypatch.setattr(gpu, "query_nvidia", lambda: [])
    monkeypatch.setattr(detector.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(detector.torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(detector.torch.backends.mps, "get_name", lambda: "Apple Test GPU")
    monkeypatch.setattr(detector, "_probe_device", lambda kind: None)

    dev, info = detector.pick_device()
    assert dev.type == "mps"
    assert info["device"] == "mps"
    assert info["gpu"] == "Apple Test GPU"
    assert "driver_check" not in info


def test_device_picker_falls_back_when_mps_probe_fails(monkeypatch):
    from definitely_human.engine import detector, gpu

    def fail(_kind):
        raise RuntimeError("Metal failed")

    monkeypatch.setattr(gpu, "query_nvidia", lambda: [])
    monkeypatch.setattr(detector.torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(detector.torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(detector, "_probe_device", fail)

    dev, info = detector.pick_device()
    assert dev.type == info["device"] == "cpu"
    assert "Metal failed" in info["warning"]
    assert "driver_check" not in info


def test_device_picker_still_prefers_cuda(monkeypatch):
    from types import SimpleNamespace

    from definitely_human.engine import detector, gpu

    probed = []
    monkeypatch.setattr(gpu, "query_nvidia", lambda: [])
    monkeypatch.setattr(detector.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(detector.torch.cuda, "get_device_name", lambda _index: "NVIDIA Test GPU")
    monkeypatch.setattr(detector.torch.cuda, "get_device_capability", lambda _index: (12, 0))
    monkeypatch.setattr(detector.torch.cuda, "get_device_properties",
                        lambda _index: SimpleNamespace(total_memory=8 * 2**30))
    monkeypatch.setattr(detector.torch.backends.mps, "is_available", lambda: True)
    monkeypatch.setattr(detector, "_probe_device", probed.append)

    dev, info = detector.pick_device()
    assert dev.type == info["device"] == "cuda"
    assert probed == ["cuda"]


def test_ocr_uses_mps_when_cuda_is_absent(monkeypatch):
    import torch
    from doctr import models

    from definitely_human import ocr

    class Predictor:
        device = "cpu"

        def to(self, device):
            self.device = device
            return self

    predictor = Predictor()
    monkeypatch.setattr(ocr, "_predictor", None)
    monkeypatch.setattr(models, "ocr_predictor", lambda **_kwargs: predictor)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)

    assert ocr._get(allow_download=True).device == "mps"
