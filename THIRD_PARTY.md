# Third-party components

| Component | Use | License |
|---|---|---|
| [MELD](https://huggingface.co/anon-review-meld-2026/meld) (Li, Wan, Chen, Paetzold, arXiv:2605.06903) | Detector model; scoring code vendored in `backend/definitely_human/engine/meld_model.py` | MIT |
| [Ettin encoder 1B](https://huggingface.co/jhu-clsp/ettin-encoder-1b) | MELD's backbone | MIT |
| [Outfit](https://github.com/Outfitio/Outfit-Fonts) | UI and icon font (`assets/fonts`) | SIL OFL 1.1 |
| [MELD-eval](https://huggingface.co/datasets/anon-review-meld-2026/meld-eval) | Calibration data, downloaded on demand, not shipped | CC-BY-4.0 (texts: upstream licenses) |
| [DAIGT / PERSUADE 2.0 essays](https://huggingface.co/datasets/Yunij/kaggle-comp-daigt) | Calibration data, downloaded on demand, not shipped | upstream licenses |
| PyTorch, Transformers, FastAPI, React, Framer Motion, uv, Inno Setup | Runtime / build | BSD / Apache-2.0 / MIT |
