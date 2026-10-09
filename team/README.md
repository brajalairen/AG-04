# Team deliverables: one folder per member

Everyone works in **their own folder, on their own branch**, so no two people ever edit the same file. The application code (`satquery/`, `web/`) is changed only by the integration lead, after review.

| Member | Folder | Branch | Deliverables |
|---|---|---|---|
| A: Manipuri and agronomy | `team/member-a-agronomy/` | `feature/manipuri-agronomy` | `manipuri_queries.json`, `agri_terms_manipuri.json`, `verified_pest_rules.json`, `verified_risk_model.json` (if reviewed), `advisory.json` (only verified content), `SOURCES.md` |
| B: Geography | `team/member-b-geo/` | `feature/district-boundaries` | `manipur_districts.geojson`, `SOURCES.md`, `geo_validation.md` |
| C: UI/UX and QA | `team/member-c-qa/` | `feature/ui-qa` (a separate `feature/ui-fixes` branch only if code changes are proposed) | `UI_REVIEW.md`, `QA_REPORT.md`, `TEST_MATRIX.md`, `screenshots/` |
| D: Pitch and demo | `team/member-d-pitch/` | `feature/pitch` | `AG04_Pitch.pptx`, `DEMO_SCRIPT.md`, `JUDGE_QA.md`, `media/` (large videos go to shared storage instead; put the link in `media/LINKS.md`) |

Each folder's `README.md` gives the exact file format.

## How to submit

```bash
git clone https://github.com/brajalairen/AG-04.git && cd AG-04
git switch ag04-prototype && git switch -c feature/<your-branch>
# add files ONLY inside your team/ folder
python team/check_deliverables.py          # must show no ERROR for your files
git add team/<your-folder> && git commit -m "Member X: <what>"
git push -u origin feature/<your-branch>   # AG-04 only; never the SatQuery-AI repo
```

Then tell the integration lead. Nobody merges into `ag04-prototype` except the integration lead.

## How integration works

1. **Review.** The integration lead reads every changed file and the sources it cites.
2. **Check.** `python team/check_deliverables.py` validates the files with the application's own loaders. For example, the thresholds go through the same schema the risk engine uses, so VERIFIED without cited sources fails.
3. **Integrate** through the existing configuration, never by changing the risk method:
   - verified thresholds: `SATQUERY_AGRI_PEST_RULES` / `SATQUERY_AGRI_RISK_MODEL` (or the reviewed copy replaces `satquery/agri/assets/*.json`)
   - districts: `SATQUERY_AGRI_AREAS=team/member-b-geo/manipur_districts.geojson` (or the reviewed copy moves into `satquery/agri/assets/`)
   - Manipuri queries: mapped onto the existing AG-04 intents in a later phase
4. **Test.** The full backend and frontend tests, the typecheck, the production build, and a look at the map.

## Rules for everyone

- **Never invent** thresholds, Manipuri text, district boundaries, government contacts or helplines, outbreak statistics or scientific sources. If something cannot be verified, leave it out or mark it PLACEHOLDER/DRAFT.
- **Synthetic data stays labelled** "SAMPLE DATA — PROTOTYPE SIMULATION". Placeholder thresholds stay labelled PLACEHOLDER until replaced by verified ones.
- **Never commit** `.env`, keys, `runs/`, `.venv`, `node_modules`, `web/dist`, or large datasets and videos.
- **The original SatQuery-AI repository is frozen.** Never push to it.
