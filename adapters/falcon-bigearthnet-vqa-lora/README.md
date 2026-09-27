---
base_model: mehmetbayik/Falcon-Single-Instruction-Large
base_model_relation: adapter
library_name: peft
tags:
- lora
- peft
- remote-sensing
- sentinel-2
- bigearthnet
- visual-question-answering
datasets:
- BIFOLD-BigEarthNetv2-0/BigEarthNet.txt
---

# Falcon LoRA adapter: BigEarthNet.txt yes/no VQA (Sentinel-2)

A LoRA adapter for the remote-sensing vision-language model
[`mehmetbayik/Falcon-Single-Instruction-Large`](https://huggingface.co/mehmetbayik/Falcon-Single-Instruction-Large),
trained by the SatQuery AI team on **yes/no questions about Sentinel-2 image patches** from BigEarthNet.txt.
SatQuery AI loads it by default (see the repository README).

## What it adapts

| | |
|---|---|
| Base model | `mehmetbayik/Falcon-Single-Instruction-Large`, snapshot `0df0629ba8797cc9f6c345e742d17734669f02c9` (837.4 M parameters) |
| Method | LoRA (PEFT 0.17.1): rank 8, alpha 16, dropout 0.05 |
| Adapted modules | 96 attention projections of the text decoder: self-attention and cross-attention q/k/v/out in all 12 decoder layers. The vision tower is frozen. |
| Trainable parameters | 1,572,864 (0.188% of the model) |
| Weights | `adapter_model.safetensors`, 6.3 MB, SHA-256 `b7b1388f6c60918877c587e28707c994b64a0798a9ccf9f5c4d9fb0a31336100` |

## Training

- **Data:** BigEarthNet.txt (`BIFOLD-BigEarthNetv2-0/BigEarthNet.txt`, CDLA-Permissive-1.0), binary (yes/no) rows
  only, categories presence, count, area and adjacency. 7,360 training rows from 2,000 patches; 1,064 validation
  and 1,794 test rows from separate patches (splits are disjoint by patch). Answers balanced to 50% yes per split.
- **Images:** BigEarthNet v2.0 Sentinel-2 L2A patches (120 x 120 px, 10 m), bands B04/B03/B02 rendered to RGB with
  the same code path SatQuery AI uses at inference.
- **Run:** 1 epoch (920 optimizer steps), learning rate 2e-4 with cosine decay, batch size 1 with gradient
  accumulation 8 (effective batch 8), seed 7; fp16 base weights, fp32 LoRA weights. 27.4 minutes on an NVIDIA
  GeForce RTX 4050 Laptop GPU, peak reserved memory 2.09 GB.
- `train_config.json` and `train_log.csv` (per-step loss, 5.29 at the start to 0.14 at the end) are the run's own
  outputs.

## Evaluation

Exact-match on all **1,794 held-out test rows** (patches never seen in training), same code and settings (3-beam
decoding) before and after:

| | Base model | With adapter | Change |
|---|---|---|---|
| **Overall** | 0.4972 | **0.6633** | **+16.61 pp** |
| adjacency (n=325) | 0.5631 | 0.6738 | +11.07 pp |
| area (n=483) | 0.4638 | 0.6190 | +15.52 pp |
| count (n=482) | 0.4315 | 0.6411 | +20.96 pp |
| presence (n=504) | 0.5496 | 0.7202 | +17.06 pp |

The test set is balanced (50% yes), so always giving the same answer scores 0.50. Full results, the regression
check on untrained tasks and the code are in `experiments/adaptation/`.

## Scope and limitations

- **Sentinel-2 only**, 120 x 120 px patches at 10 m. No claim is made for other sensors or resolutions.
- **Yes/no questions only.** Captioning, grounding, change detection and every other SatQuery AI capability were
  not trained; a regression check found no degradation in captioning, grounding or change detection
  (`experiments/adaptation/results/regression_check.json`).
- **Land-cover class balance was not controlled** when selecting patches.
- Exact-match on short binary answers is a narrow metric.

## Licence and attribution

This file set is distributed with the SatQuery AI repository. The adapter only works on top of the base model,
whose own licence applies to that combined use; the base model's published licence metadata is inconsistent
across its listings, so check it before any use beyond research and evaluation.

Trained on BigEarthNet.txt and BigEarthNet v2.0 (CDLA-Permissive-1.0), which contain modified Copernicus Sentinel
data. See `experiments/adaptation/test_split/README.md` for citations.
