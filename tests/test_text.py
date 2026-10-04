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
