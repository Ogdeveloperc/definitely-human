---
language: en
license: mit
inference: false
tags:
  - ai-text-detection
base_model: jhu-clsp/ettin-encoder-1b
---

# MELD (mirror)

This is an unmodified mirror of [`anon-review-meld-2026/meld`](https://huggingface.co/anon-review-meld-2026/meld)
at revision `8990324abd92e1fa17072f6887ea1e5c1cef5abc`, kept so that
[Definitely Human™](https://github.com/Ogdeveloperc/definitely-human) installs keep working if the original
anonymous-review repository moves. All credit goes to the authors.

> **MELD: Multi-Task Equilibrated Learning Detector for AI-Generated Text**
> Chenjun Li, Cheng Wan, Haomiao Chen, Johannes C. Paetzold (Cornell University).
> [arXiv:2605.06903](https://arxiv.org/abs/2605.06903)

An AI-generated text detector for English (Ettin-1B / ModernBERT encoder with a custom scoring head).
Usage is unchanged from the original:

```bash
pip install torch transformers safetensors
python meld.py "Paste the text to check here."
```

The scoring head is custom, so `pipeline()` and `AutoModel` do not apply; use `meld.py` or its `Scorer` class.
Inputs should be at least about 100 words. License: MIT, as released by the authors.
