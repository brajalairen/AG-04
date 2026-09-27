# LoRA adaptation of Falcon on BigEarthNet.txt

This folder holds the code and the recorded evidence for SatQuery AI's fine-tuned component: a LoRA adapter that
the team trained on **BigEarthNet.txt** yes/no questions about Sentinel-2 image patches. The adapter itself is in
[`adapters/falcon-bigearthnet-vqa-lora/`](../../adapters/falcon-bigearthnet-vqa-lora/), and the app loads it by
default.

**Every number reported here is read from a file in `results/`.** `results/report.md` is generated from those
files by `make_report.py`.

## What was adapted, and what was not

The base model, [`mehmetbayik/Falcon-Single-Instruction-Large`](https://huggingface.co/mehmetbayik/Falcon-Single-Instruction-Large),
was pre-trained on remote-sensing data by its own authors. This adapter is the part the SatQuery AI team trained:

- **Task: binary (yes/no) visual question answering** about Sentinel-2 patches: presence, count, area and adjacency
  of land-cover classes. Bounding-box rows need Falcon's coordinate-token grammar and were not trained.
- **Data: BigEarthNet.txt** with BigEarthNet v2.0 Sentinel-2 patches (120 x 120 px, 10 m), rendered to RGB by the
  same code the app uses at inference (`satquery.imaging`).
- **Not trained:** captioning, grounding, change detection, SAR, weather, or any other SatQuery AI capability. A
  regression check on the demo scenarios found no degradation with the adapter on: identical grounding boxes, a
  change mask within 0.5%, and different but coherent captions (`results/regression_check.json`).

## Results (full held-out test set)

Exact-match on **all 1,794 held-out test rows** (500 patches never seen in training), identical code and settings
before and after training:

| | Base model | With adapter | Change |
|---|---|---|---|
| **Overall** | 0.4972 | **0.6633** | **+16.61 pp** |
| adjacency (n=325) | 0.5631 | 0.6738 | +11.07 pp |
| area (n=483) | 0.4638 | 0.6190 | +15.52 pp |
| count (n=482) | 0.4315 | 0.6411 | +20.96 pp |
| presence (n=504) | 0.5496 | 0.7202 | +17.06 pp |

The test set is balanced (50% yes), so always giving the same answer scores 0.50; the base model is at that level,
and the adapted model is not. Details, the answer distributions and the training setup: `results/report.md`.

## Limitations

- **Sentinel-2 only** (120 x 120 px at 10 m). No claim is made for other sensors or resolutions.
- **Yes/no questions only.** Exact-match on short binary answers is a narrow metric.
- **Land-cover class balance was not controlled:** patches were selected from BigEarthNet.txt's own split column
  and stratified by question category, because the BigEarthNet land-cover metadata file was not available.

## Files

| File | Purpose |
|---|---|
| `falcon_lora.py` | model loading (the same path as the app), LoRA attachment, data helpers |
| `build_dataset.py` | patch and row selection, RGB rendering, balanced JSONL splits and manifest |
| `train_lora.py` | LoRA training with a per-step loss log |
| `evaluate.py` | exact-match overall and per category; the same code before and after |
| `make_report.py` | writes `results/report.md` from the recorded files |
| `results/` | recorded evidence: dataset manifest, training config and loss log, overfit check, evaluations before and after, regression check, report |
| `test_split/` | the 1,794 held-out test rows and their 500 rendered patches (CDLA-Permissive-1.0, see its README) |

## Re-running the evaluation (no dataset download needed)

Install the app with its `adaptation` extra (see the main README), then:

```powershell
# with the adapter (on CPU add: --device cpu --dtype fp32; for a quick check add: --limit 100)
.venv\Scripts\python experiments\adaptation\evaluate.py --data experiments\adaptation\test_split --split test `
    --adapter adapters\falcon-bigearthnet-vqa-lora --out eval_after.json

# the base model, for comparison
.venv\Scripts\python experiments\adaptation\evaluate.py --data experiments\adaptation\test_split --split test `
    --out eval_before.json
```

The recorded results used a CUDA GPU in fp16 with 3-beam decoding (the defaults).

## Re-training (needs the source datasets)

Training data is not redistributed here. To rebuild it, download BigEarthNet.txt
(https://huggingface.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt) and the BigEarthNet v2.0 Sentinel-1 and
Sentinel-2 patches (https://bigearth.net/), install `pip install -e ".[models,adaptation,data]"`, and run:

```powershell
# 1. dataset (manifest records the parquet SHA-256 and selection settings; seed 7)
.venv\Scripts\python experiments\adaptation\build_dataset.py --parquet <BigEarthNet.txt.parquet> `
    --s2-dir <BigEarthNet-S2 root> --s1-dir <BigEarthNet-S1 root> --out data\adaptation

# 2. sanity check: the loss must collapse on 20 samples before a full epoch is worth running
.venv\Scripts\python experiments\adaptation\train_lora.py --overfit 20 --epochs 25 --lr 5e-4 --grad-accum 4 `
    --out runs\adaptation\overfit

# 3. baseline before training
.venv\Scripts\python experiments\adaptation\evaluate.py --split test --out eval_before.json

# 4. train (the recorded run: 1 epoch, learning rate 2e-4, effective batch 8, seed 7)
.venv\Scripts\python experiments\adaptation\train_lora.py --lr 2e-4 --out runs\adaptation\adapter

# 5. after training
.venv\Scripts\python experiments\adaptation\evaluate.py --split test --adapter runs\adaptation\adapter `
    --out eval_after.json
```

The recorded run took 27.4 minutes on an NVIDIA GeForce RTX 4050 Laptop GPU (peak 2.09 GB VRAM).
