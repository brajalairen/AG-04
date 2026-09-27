# Held-out test split (BigEarthNet.txt yes/no VQA)

The 1,794 test rows used to evaluate the SatQuery AI LoRA adapter, with the 500 rendered image patches they refer to.
No row or patch here was used in training (splits are disjoint by patch). This lets anyone re-run the evaluation
without downloading the full BigEarthNet dataset:

```powershell
.venv\Scripts\python experiments\adaptation\evaluate.py --data experiments\adaptation\test_split --split test `
    --adapter adapters\falcon-bigearthnet-vqa-lora --out eval_after.json
```

Add `--device cpu --dtype fp32` on a machine without a CUDA GPU, and `--limit N` for a quick check on the first N
rows. Omit `--adapter` to evaluate the base model.

## Contents

- `test.jsonl`: one question per line: `question`, reference `answer` (`yes`/`no`), `category` (presence, count,
  area, adjacency), `patch_id` and `s1_name` (BigEarthNet v2.0 patch names), `country`, `split`, and `image_path`.
- `images/test/*.png`: 500 Sentinel-2 patches, 120 x 120 px at 10 m.
- `LICENSE-CDLA-Permissive-1.0.txt`: the licence these data are published under.

## Notice of changes

**These files are modified from the original data.** Changes made by the SatQuery AI team:

- **Rows:** a subset of BigEarthNet.txt: `binary` (yes/no) rows only, from the dataset's own `test` split, at most
  4 rows per patch, stratified by question category and downsampled so that 50% of answers are yes; fields renamed
  (`input` to `question`, `output` to `answer`) and reduced to those listed above.
- **Images:** each PNG is rendered from the BigEarthNet v2.0 Sentinel-2 L2A bands B04/B03/B02 (red/green/blue)
  with a 2-98 percentile contrast stretch, and saved as 8-bit RGB. They are not the original multispectral GeoTIFFs.

The selection settings and the SHA-256 of the source parquet are recorded in `../results/dataset_manifest.json`.

## Licence and attribution

BigEarthNet.txt and BigEarthNet v2.0 are published under the
[Community Data License Agreement - Permissive, Version 1.0](https://cdla.dev/permissive-1-0/) (full text in
`LICENSE-CDLA-Permissive-1.0.txt`). This modified subset is published under the same agreement.

- **BigEarthNet.txt** (questions and answers): https://huggingface.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt
  J. Herzog, M. Adler, L. Hackel, Y. Shu, A. Zavras, I. Papoutsis, P. Rota, B. Demir, "BigEarthNet.txt: A
  Large-Scale Multi-Sensor Image-Text Dataset and Benchmark for Earth Observation", arXiv preprint
  arXiv:2603.29630, 2026.
- **BigEarthNet v2.0** (image patches): https://bigearth.net/
  K. Clasen, L. Hackel, T. Burgert, G. Sumbul, B. Demir, V. Markl, "reBEN: Refined BigEarthNet Dataset for Remote
  Sensing Image Analysis", IEEE International Geoscience and Remote Sensing Symposium (IGARSS), 2025.
- **Contains modified Copernicus Sentinel data (2017-2018).**
