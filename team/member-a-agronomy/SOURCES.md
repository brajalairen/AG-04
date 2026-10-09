# AG-04 agronomy sources: rice blast and brown planthopper (BPH)

AG-04 is a prototype for prioritising field inspections. It is not a validated outbreak-prediction system. Nothing here is verified for Manipur until a qualified local expert signs it off in `EXPERT_REVIEW_CHECKLIST.md`.

Prepared 2026-10-09 from the two PDFs supplied by the integration lead. Page numbers are the **printed** page numbers of each document.

**Status labels**
- **SOURCE-DOCUMENTED:** stated explicitly in the cited source.
- **PENDING-MANIPUR-EXPERT-VERIFICATION:** sourced, but not yet confirmed for Manipur conditions (crop calendar, varieties, valley or hill).
- **PLACEHOLDER-UNSUPPORTED:** not adequately supported by these sources.

Every SOURCE-DOCUMENTED item below is also PENDING-MANIPUR-EXPERT-VERIFICATION.

## Sources

| ID | Title | Issued by | Date | Notes |
|---|---|---|---|---|
| S1 | *Integrated Pest Management Package for Rice* (Anand Prakash et al.) | Directorate of Plant Protection, Quarantine & Storage (DPPQ&S), Faridabad, with NCIPM, New Delhi and NIPHM, Hyderabad; published by NCIPM for DPPQ&S | 2014 | National package (all India). Online copy: https://niphm.gov.in/IPMPackages/Rice.pdf |
| S2 | *Advisory on blast disease (Magnaporthe oryzae) on rice crop*, F.No 3-6/2022-23/IPM/Advisory | DPPQ&S, Ministry of Agriculture & Farmers Welfare; signed by Dr J.P. Singh, Plant Protection Adviser | 22 Jul 2022 | Addressed to the Directors of Agriculture of all States/UTs. A circular, not a forecasting model. The supplied copy is a scan; the URL it came from was not provided. |

## Rice blast

| # | Rule type | Exact content (as stated) | Units / stage / method | Source | Status | Limitation for Manipur |
|---|---|---|---|---|---|---|
| B1 | Weather favourability | "Rice blast is favored by low temperatures (22-28°C), high relative humidity (>95%), dew deposits, leaf wetness for more than 10 hours, application of high nitrogen and aerobic soils." | °C, % RH, hours of leaf wetness. All stages ("can infect rice crop at all growth stages"). | S2 p.1 | SOURCE-DOCUMENTED (qualitative) | The source does not say whether temperature is a daily mean, minimum or night value, how long RH must exceed 95%, or whether the conditions must coincide on the same day. No look-back or forecast window and no number of favourable days are given. |
| B2 | Disease context | Infects leaves, neck, nodes and seeds; leaf and neck infections are more severe; seedling-stage infection may cause severe damage. Blast is more severe where field water falls below recommended levels. | — | S2 p.1 | SOURCE-DOCUMENTED | Context only; not a threshold. |
| B3 | Field threshold (ETL) | Foliar blast: **3-5 lesions/leaf** | Early to late tillering | S1 p.9, §3.1.2 | SOURCE-DOCUMENTED | National ETL; leaves sampled per hill or per field are not specified. |
| B4 | Field threshold (ETL) | Neck blast: **2-5 neck-infected plants/m²** | Panicle initiation to booting | S1 p.9, §3.1.2 | SOURCE-DOCUMENTED | No ETL for nursery or flowering. The flowering-stage spray row (S1 p.18) has no threshold. |
| B5 | Management advisory | Monitor regularly; adopt integrated disease management; resistant varieties listed (Rasi, Vikas, Krishna Hamsa, Tulasi, IR 64, Aditya, Swarnadhan, Himalaya 1/2/2216, Pant dhan 10, HKR 228, PNR 519) | — | S2 pp.1-2; S1 p.13 §3.3 | SOURCE-DOCUMENTED | Varieties are not Manipur-specific. Chemical options exist in S1 pp.17-18 §3.6 and the S2 Annexure-I, to be used "as per label claim" and "only when pest population cross ETL" (S1 p.17). AG-04 must not reproduce doses or give spray advice. |

## Brown planthopper (BPH / WBPH)

| # | Rule type | Exact content (as stated) | Units / stage / method | Source | Status | Limitation for Manipur |
|---|---|---|---|---|---|---|
| P1 | Field threshold (ETL) | **10-15 hoppers/hill** | Early to late tillering | S1 p.9, §3.1.2 | SOURCE-DOCUMENTED | Counts are per hill; S1 does not say how a range ETL should be applied (low or high end). |
| P2 | Field threshold (ETL) | **15-20 hoppers/hill** | Panicle initiation to booting | S1 p.9, §3.1.2 | SOURCE-DOCUMENTED | No ETL for nursery or flowering. |
| P3 | Favouring conditions | "High dosages of nitrogenous fertilizers, close spacing, and high relative humidity increases planthopper populations." | **No numeric value** | S1 p.12, §3.2 | SOURCE-DOCUMENTED (qualitative only) | **No BPH temperature or humidity threshold exists in either source.** |
| P4 | Pest:defender ratio | "P:D ratio 2:1 may be useful to avoid application of pesticides against plant hoppers." | Ratio from field counts | S1 p.17, §3.5.2 | SOURCE-DOCUMENTED | Needs counts of natural enemies, which AG-04 does not have. |
| P5 | Management advisory | Drain fields 3-4 days under heavy infestation; split nitrogen; synchronous planting; no more than two crops a year; 30 cm alleys every 2.5-3 m and alternate wetting and drying in planthopper-endemic areas; resistant varieties listed | — | S1 p.12 §3.2, p.10 §3.2(k,l), p.13 §3.3 | SOURCE-DOCUMENTED | Varieties are not Manipur-specific. Chemical options exist (S1 §3.6), but AG-04 must not reproduce doses. |

## Sampling method (both pests)

| # | Content | Source | Status |
|---|---|---|---|
| M1 | Roving survey every 10 km at 7-10 day intervals, at least 20 spots a day. Field scouting once in 3-5 days to work out the ETL. Plant protection only when pests cross the ETL. | S1 p.5, §3.1 | SOURCE-DOCUMENTED |
| M2 | AESA: start 20 days after transplanting. Per field, 5 spots (four corners at least 5 ft inside the border, plus the centre), 4 hills per spot, **20 hills per field**. Weekly, preferably before 9 a.m. | S1 p.6 §3.1.1; p.21 | SOURCE-DOCUMENTED |

## Comparison with the AG-04 rules in use

Rules load from `satquery/agri/assets/pest_rules.json` (`config.load_pest_rules`) and `satquery/agri/assets/observation_rules.json` (`config.load_observation_rules`). Nothing in the application was changed.

| AG-04 rule | Current value | Against the sources | Status |
|---|---|---|---|
| Blast weather rule | ≥ 8 h with RH ≥ 90% and daily mean temperature 20-28 °C | S2 gives RH > 95%, temperature 22-28 °C and leaf wetness > 10 h. The current numbers match none of these. | PLACEHOLDER-UNSUPPORTED |
| BPH weather rule | Daily mean temperature 25-32 °C and daily mean RH ≥ 80% | No source gives any BPH weather threshold. | PLACEHOLDER-UNSUPPORTED |
| Weather window and saturation | 7 past + 3 forecast days; full score at 5 favourable days | Not in either source. | PLACEHOLDER-UNSUPPORTED |
| BPH ETLs (`observation_rules.json`) | 10-15 hoppers/hill (tillering); 15-20 (PI-booting) | Match S1 p.9 exactly. | SOURCE-DOCUMENTED; PENDING-MANIPUR-EXPERT-VERIFICATION |
| Blast ETLs (`observation_rules.json`) | 3-5 lesions/leaf (tillering); 2-5 neck-infected plants/m² (PI-booting) | Match S1 p.9 exactly. | SOURCE-DOCUMENTED; PENDING-MANIPUR-EXPERT-VERIFICATION |
| ETL range to low/moderate/high severity | Below range = low, within = moderate, at or above top = high | Engineering choice, not in S1. | PLACEHOLDER-UNSUPPORTED |
| Weights 50/30/20, risk bands | — | Not in either source. | PLACEHOLDER-UNSUPPORTED (uncalibrated) |

## Inputs AG-04 lacks to apply the sourced rules

- **Leaf-wetness duration** (B1). AG-04 fetches hourly temperature, RH, dew point and precipitation only. Hours of RH > 95% are a possible proxy, but the source does not state that proxy and an expert must approve it.
- **Crop stage per area.** Every ETL is stage-specific; without the stage, the BPH ETL is ambiguous (10-15 vs 15-20 hoppers/hill).
- **Real field scouting counts.** Hoppers/hill, lesions/leaf and neck-infected plants/m² sampled per M2. Today all pest observations are SAMPLE (synthetic).
- **Natural-enemy counts** for the P:D ratio (P4).
- **Nitrogen dose, plant spacing and field water level:** favouring factors named by both sources (B1, B2, P3).

These sources support **checking field counts against ETLs** once real scouting data exists. They do **not** support numeric weather-risk rules for BPH, and they support blast weather risk only qualitatively.
