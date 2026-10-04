---
language: en
license: cc-by-4.0
task_categories:
  - text-classification
tags:
  - ai-text-detection
  - mgt-detection
  - benchmark
size_categories:
  - 100K<n<1M
---

# MELD-eval (mirror)

Unmodified mirror of [`anon-review-meld-2026/meld-eval`](https://huggingface.co/datasets/anon-review-meld-2026/meld-eval)
at revision `4c80f0fdc003854e5b6bfda90f7ac41ffb12e232`, used by
[Definitely Human™](https://github.com/Ogdeveloperc/definitely-human) to calibrate its thresholds.
All credit goes to the MELD authors ([arXiv:2605.06903](https://arxiv.org/abs/2605.06903)).

Held-out evaluation pool for AI-text detectors: four 2026 chat models (`gpt-5.4-mini`, `gemini-3-flash`,
`claude-haiku`, `qwen-3.6-plus`), eight RAID-style English domains, six surface attacks, and the matched
human seeds each AI row was conditioned on. File: `meld_eval.jsonl`, one JSON object per line
(`id`, `text`, `label` 1 = AI / 0 = human, `generator`, `domain`, `attack`, `prompt_id`).

License: CC-BY-4.0 for annotations and metadata. The `text` field combines human passages from earlier
public corpora (notably RAID) under their own licenses and machine completions from commercial chat APIs
under each provider's terms. Not a training corpus.
