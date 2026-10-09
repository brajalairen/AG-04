# Expert review checklist: rice blast and BPH rules for Manipur

**For:** a qualified Manipur agriculture expert (for example from the Department of Agriculture, CAU Imphal, ICAR RC NEH Manipur Centre or a KVK).

**Purpose:** confirm, correct or reject each rule before AG-04 marks it VERIFIED. AG-04 is a prototype that helps prioritise field inspections. A HIGH risk level is not a confirmed infestation. Rule details and page references are in `SOURCES.md`.

No rule is verified for Manipur yet. **Expert decisions recorded: none.**

## How to record a decision

For each row, mark **Approve / Approve with changes / Reject** and add the expert's name, designation, institution, date (YYYY-MM-DD) and any corrected value. Only rows approved this way can move to `verified_pest_rules.json` / `verified_observation_rules.json` with `verified_by` and `verified_on`.

## Rules to review

| # | Rule | Current status | Decision | Corrected value / notes | Expert, institution, date |
|---|---|---|---|---|---|
| R1 | Blast favoured by 22-28 °C, RH > 95%, leaf wetness > 10 h (S2 p.1) | SOURCE-DOCUMENTED; PENDING-MANIPUR-EXPERT-VERIFICATION | | | |
| R2 | Replace the AG-04 placeholder blast rule (≥ 8 h RH ≥ 90%, mean 20-28 °C) | PLACEHOLDER-UNSUPPORTED | | | |
| R3 | AG-04 placeholder BPH weather rule (mean 25-32 °C, RH ≥ 80%): keep, replace or remove? No source gives a BPH weather threshold. | PLACEHOLDER-UNSUPPORTED | | | |
| R4 | BPH/WBPH ETL 10-15 hoppers/hill (tillering); 15-20 (PI-booting) (S1 p.9) | SOURCE-DOCUMENTED; PENDING-MANIPUR-EXPERT-VERIFICATION | | | |
| R5 | Foliar blast ETL 3-5 lesions/leaf (tillering) (S1 p.9) | SOURCE-DOCUMENTED; PENDING-MANIPUR-EXPERT-VERIFICATION | | | |
| R6 | Neck blast ETL 2-5 neck-infected plants/m² (PI-booting) (S1 p.9) | SOURCE-DOCUMENTED; PENDING-MANIPUR-EXPERT-VERIFICATION | | | |
| R7 | Sampling: AESA, 20 hills per field from 20 days after transplanting; scouting every 3-5 days (S1 pp.5-6) | SOURCE-DOCUMENTED; PENDING-MANIPUR-EXPERT-VERIFICATION | | | |
| R8 | AG-04 weather window (7 past + 3 forecast days; full score at 5 favourable days) | PLACEHOLDER-UNSUPPORTED | | | |
| R9 | Reading an ETL range: below = low, within = moderate, at or above top = high | PLACEHOLDER-UNSUPPORTED | | | |

## Questions for the expert

1. **Blast weather criteria.**
   - Is the 22-28 °C range a daily mean, a night minimum, or something else?
   - Should RH > 95% hold for a minimum number of hours a day?
   - Must the temperature, RH and leaf-wetness conditions occur together on the same day?
2. **Leaf wetness.** AG-04 has no leaf-wetness sensor data. Is "hours with RH above X%" (or dew point close to air temperature) an acceptable proxy for "leaf wetness > 10 h" in Manipur? If yes, at what X?
3. **Number of days.** How many favourable days, over what look-back period, should raise blast concern? Should forecast days count the same as past days?
4. **BPH weather.** Is there any Manipur or Northeast source (CAU Imphal, ICAR RC NEH, AICRP-Rice) giving temperature or humidity conditions for BPH build-up? If not, should AG-04 drop BPH weather scoring and rely only on field counts?
5. **BPH field thresholds.** Do 10-15 and 15-20 hoppers/hill apply to Manipur's main kharif varieties? When a count falls inside the range, which end should trigger action?
6. **Crop stages.**
   - What are the usual transplanting, tillering, panicle-initiation, booting and flowering dates for kharif rice in the valley districts and in the hill districts?
   - Can AG-04 estimate the stage from the transplanting date?
7. **Neck blast.** S1 gives no ETL at flowering. What should field staff use at that stage?
8. **Local applicability.** Should any thresholds differ between valley and hill rice, local or aromatic varieties (e.g. Chakhao), or the boro and kharif seasons?
9. **Field data.** Do Department of Agriculture, KVK or ATMA staff in Manipur already record hoppers/hill or blast lesion counts? In what format, and could AG-04 receive them?
10. **Natural enemies.** Should the P:D ratio of 2:1 for plant hoppers (S1 p.17) be part of AG-04's advice?

## Not to be decided here

- Pesticide products, doses or spray timing. AG-04 only points to the official package (S1 §3.6) and label claims (S2).
- Risk weights and bands (50/30/20, 35/60/80). These stay uncalibrated until validated against field outcomes.
