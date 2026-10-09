# AG-04 pest and disease data: source assessment

Checked on **2026-10-08**, with a second pass late on 2026-10-08 / 2026-10-09 IST covering NPSS access, NRIIPM online systems, NISPM and Manipur blast research. Done by the integration lead for the pest/disease data task. "Not found" means not found by the method stated, not proof that nothing exists.

## Conclusion

**No public, machine-readable pest or disease *observation* dataset for Manipur was found.** Authoritative surveillance systems exist (NPSS, ICAR-NRIIPM e-pest surveillance, AICRP-Rice surveys), but their field observations are not published for download or through an API, and none of the published survey reports covers Manipur.

> Authoritative source exists, but machine-readable public observations were not found.

The prototype therefore uses **Strategy C** (named Strategy 3 in the first pass): verified rules + real weather + real NDVI + SAMPLE pest data. Strategy A (real geospatial surveillance) and Strategy B (real historical surveillance) are not possible, because no such observations are accessible for Manipur.

```text
verified agronomic rules (PLACEHOLDER until Member A verifies them)
+ real weather (Open-Meteo, model data)
+ real NDVI (Copernicus Sentinel-2, when credentials are configured)
+ SAMPLE pest/disease observations, labelled "SAMPLE DATA — PROTOTYPE SIMULATION"
```

The engine is ready for real observations (`satquery/agri/observations.py`). A dataset in the schema below, named in `SATQUERY_AGRI_OBSERVATIONS`, replaces the SAMPLE generator. Nothing synthetic is ever presented as real.

## Three kinds of data that must not be mixed

| Kind | Example | What it can do here | What it cannot do |
|---|---|---|---|
| **Surveillance observations** | date, district/block/village, crop, pest, count or % damage | Evidence that a pest is present in a monitored area now | Nothing, if it is historical, out of area, or of unknown coverage |
| **Agronomic rules / calibration** | weather criteria for BPH build-up; ETL of 10–15 hoppers/hill | Turn weather and observations into a risk signal | Show that a pest is present |
| **Image datasets** | `leaf.jpg` labelled `blast` | Train a disease *recogniser* (AG-01, future) | Geographic prevalence. Image counts are never used as disease prevalence |

## Candidate sources scored (Step 7)

Grades: **A** directly suitable · **B** usable with preprocessing or limitations · **C** agronomic knowledge only · **D** not suitable for the risk engine.

| # | Source | Official? | Manipur relevance | Spatial data | Temporal data | Pest/Disease | Severity/count | API/download | Licence | Suitable for risk engine? | Grade |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | National Pest Surveillance System (NPSS), DA&FW / DPPQ&S + ICAR-NRIIPM | Yes | Unknown: national (583 districts listed), Manipur not mentioned | District / sub-district (per NRIIPM) | Real time (app) | Yes, rice included | Yes, per NRIIPM methods | **None public**: app and stakeholder portal only | Not published | Would be **A** if access were granted; today not accessible | **D** (today) |
| 2 | ICAR-NRIIPM ICT e-pest surveillance programmes (CROPSAP, HORTSAP, Odisha rice, A3P, Haryana) | Yes | None (other states) | District / block / village | Weekly | Yes | Yes (ETL-based) | None public | Not published | No: other states, no access | **D** (data); **C** (method) |
| 3 | Tripura Boro rice e-pest surveillance (ICAR-NCIPM + Dept of Agriculture, Tripura), 2016–2018 | Yes | Neighbouring NE state, same rice type | 7 districts, 54 talukas, 496 villages | Weekly, Boro seasons 2016–18 | Rice pests and diseases | Yes (no./hill, % severity, % dead heart) | **None**: only aggregates published | Not published | No: no observations available, not Manipur | **C** (method; informs the schema) |
| 4 | NICRA Technical Bulletin 39 (ICAR-NCIPM, 2016): weather-based prediction rules for rice insect pests | Yes | None: 7 locations, none in NE | Point (light-trap stations) | Weekly (SMW), 2000–2014 | YSB, BPH, WBPH, GLH, leaf folder, gall midge, caseworm | Light-trap catch classes | PDF | ICAR publication | Rules only: location-specific, need validation for Manipur | **C** |
| 5 | ICAR-CRIDA CropPest DSS crop–pest–disease–weather database (NAIP) | Yes | None: 12 locations, none in NE | Point (research stations) | Weekly, historical (query years to 2011) | 11 rice pests/diseases incl. BPH, leaf blast, neck blast | Weekly counts | Web query form (no API documented) | Not stated | Calibration only; historical; not Manipur | **C** |
| 6 | AICRP-Rice Production Oriented Survey 2025 (ICAR-IIRR) and IIRR "3-decadal" POS database | Yes | **None in 2025** (15 states, no NE state); Manipur in earlier years not verified | District | Seasonal (kharif 2025, rabi 2025–26) | Insects and diseases | Intensity L/M/H with % ranges | PDF tables; database access not verified | Not stated | Structure fits (district, season, intensity) but no Manipur rows | **D** for Manipur; **B** if a Manipur year is found |
| 7 | IPM Package for Rice (NCIPM / DPPQ&S, 2014), ETL table 3.1.2 | Yes | National; not calibrated for Manipur | n/a | Crop stage | 20+ rice pests/diseases | ETL values | PDF | Government publication | Reads observations; not evidence itself | **C** (transcribed as PLACEHOLDER) |
| 8 | data.gov.in (OGD Platform India) | Yes | State/district crop statistics include Manipur | District / state | Annual | **No pest/disease dataset found** | No | Download / API | NDSAP / GODL | Crop area or production only | **D** |
| 9 | Manipur: GKMS district agromet advisories (AMFU Lamphelpat, ICAR RC NEH Manipur Centre, with IMD) | Yes | High (Manipur districts) | District | Twice weekly (bulletins 2018–19 found) | Advisory text may mention pests | No | PDF bulletins | Not stated | Advice, not observations | **C/D** |
| 10 | Manipur Department of Agriculture, CAU Imphal, KVKs, ICAR RC NEH Manipur Centre | Yes | High | Unknown | Unknown | Expected (pest scouts, AESA, KVK diagnostics) | Unknown | **No public dataset found** | n/a | Best real source **if** a data-sharing agreement is made | **D** (today) |
| 11 | GBIF occurrence API (*Nilaparvata lugens*, *Pyricularia oryzae*) | No (aggregator) | **0 records in Manipur** | Point | Opportunistic | Species presence | No | API | Per-record CC licences | Presence-only, no severity, no Manipur | **D** |
| 12 | Image datasets (Mendeley rice-leaf sets, IP102, RP11) | No (research) | None | None | None | Disease/pest classes | No | Download | CC (varies) | Image classification only | **D** (AG-01 candidate) |
| 13 | Peer-reviewed pest–weather correlation studies (various Indian locations) | Research | Low (no Manipur study found) | Plot / station | Seasonal | YSB, BPH, sheath blight | Yes | Papers | Journal | Context for Member A's rule review | **C** |

## Access, authentication and joinability

| # | Source | Access method | API | Download | Authentication | Observations actually accessible? | Current or historical | Joinable to our zone polygons? |
|---|---|---|---|---|---|---|---|---|
| 1 | NPSS | Mobile app (Google Play `com.npss`, Apple App Store); web portal https://npss.dac.gov.in/ (linked as the official portal from the NRIIPM home page) | None published | None | App and portal accounts for farmers and plant-protection staff (role-based per NRIIPM; the login could not be inspected: the portal's DNS did not resolve from our network) | **No** | Current (real time), if shared | Only if records carry GPS or a village/block/district (per NRIIPM: reverse-geocoded, sub-district) |
| 2 | ICAR-NRIIPM e-pest programmes; "ICAR-Pest Monitoring and Advisory System" | NRIIPM website | None | None | Not determinable: the system link redirects to an error page (checked) | **No** | Historical | Village/block, if shared |
| 3 | Tripura Boro rice e-pest surveillance | Annual reports (PDF) | None | Aggregates only | None for the PDFs | **No** (aggregates only) | Historical (2016–18) | No: Tripura, not Manipur |
| 4 | NICRA Bulletin 39 | PDF | None | PDF | None | Rules only | Historical data behind the rules | No: station rules |
| 5 | ICAR-CRIDA CropPest DSS | Web query form | None documented | Tables per query | None (query worked) | Yes, but not for Manipur | Historical (to 2011) | No: 12 stations outside the Northeast |
| 6 | AICRP-Rice POS 2025 and IIRR POS database | PDF; database page | None | PDF tables | None for the PDF; database not tested | District tables, no Manipur rows | Seasonal (2025) | District-level only; no Manipur rows |
| 7 | IPM Package for Rice (ETLs) | PDF | None | PDF | None | Rules only | 2014 | Not applicable |
| 8 | data.gov.in | Portal / OGD API | Yes (API key) | Yes | Free API key for the API | No pest dataset found | Annual statistics | District statistics only |
| 9 | Manipur GKMS advisories | PDF bulletins | None | PDF | None | Advisories, not observations | Twice weekly (2018–19 seen) | District-level text |
| 10 | Manipur Dept of Agriculture, KVKs, CAU, ICAR RC NEH | None public | None | None | n/a | **No public data found** | Unknown | Unknown |
| 11 | GBIF | API | Yes | Yes | None for search | Yes, but 0 Manipur records | Opportunistic | Points, none in Manipur |
| 12 | Image datasets | Download | Some | Yes | Varies | Images, not observations | n/a | **Never**: no geographic or temporal link |

## Status vocabulary used by the engine and API

| Applies to | Values | Meaning |
|---|---|---|
| A field observation (`status`) | REAL / SAMPLE | REAL: from a named source. SAMPLE: synthetic, labelled "SAMPLE DATA — PROTOTYPE SIMULATION" |
| An observation's age | HISTORICAL | Older than the 14-day look-back window: counted and shown, never current evidence (`evidence_state: HISTORICAL_ONLY`, `historical_count`) |
| The data behind a factor (`provenance.state`) | LIVE / CACHED / SNAPSHOT / SAMPLE / UNAVAILABLE | How and when the data was obtained |
| A rule or threshold | PLACEHOLDER / VERIFIED | VERIFIED needs a cited source with `verified_by` and `verified_on`; otherwise PLACEHOLDER |
| The score as a whole (`calibration`) | UNCALIBRATED / VALIDATED | UNCALIBRATED until the weights and bands are validated against field outcomes, even when every threshold is VERIFIED |
| Field evidence for one pest (`details.evidence_state`) | NO_SOURCE / NOT_COVERED / NOT_SURVEYED / COVERAGE_UNKNOWN / HISTORICAL_ONLY / NONE_OBSERVED / SAMPLE_NONE / OBSERVED | "No observations available" (the first five: the factor is unavailable) is never read as "no pest observed" (NONE_OBSERVED, REAL surveillance only) |
| A pest in an area | assessed (`pest_risks`) / not assessed (`pests_not_assessed`) | A known pest with neither a weather rule nor field evidence gets no score |

## Source details (Step 20 template)

### 1. National Pest Surveillance System (NPSS)

- **Publisher:** Ministry of Agriculture & Farmers Welfare. Implemented by the Directorate of Plant Protection, Quarantine & Storage (DPPQ&S), Faridabad, and ICAR-National Research Centre/Institute for Integrated Pest Management (NRCIPM/NRIIPM), New Delhi.
- **URL:** PIB release "National Pest Surveillance System", 25 Mar 2025, https://www.pib.gov.in/PressReleasePage.aspx?PRID=2114896 ; ICAR-NRIIPM, "ICT-based pest surveillance & advisory system: a path breaking initiative", https://nriipm.res.in/NCIPMPDFs/successstories/NRIIPM-ICT.pdf
- **Dataset:** none published. The system has a mobile app, a web portal (admin panel, dashboard, pest reporting, advisory submission) and a central database (NRIIPM).
- **Type:** surveillance and advisory system.
- **Geographic coverage:** all India. The NRIIPM table lists 583 districts and 2,075 sub-districts. Manipur is not named in the documents found.
- **Temporal coverage:** launched 15 Aug 2024; real-time capture.
- **Variables:** per NRIIPM, quantitative pest observations "recorded according to pest specific scientific methods". The exact public schema is not documented.
- **Crops:** PIB: identification for 61 crops and advisories for 15 major crops including paddy. NRIIPM: AI identification for 65 crops and surveillance of key pests of 31 crops; rice is listed.
- **Access method:**
  - The mobile app is on Google Play (`com.npss`) and the Apple App Store.
  - The web portal is https://npss.dac.gov.in/. The ICAR-NRIIPM home page links it as "NPSS: new web portal launched".
  - No download, open API or data.gov.in release was found.
  - Access to the underlying observations would need a request to DPPQ&S / ICAR-NRIIPM.
- **Authentication:** app and portal accounts (users are central and state plant-protection staff and farmers, per the app listing). The portal's domain did not resolve from our network on 2026-10-08, so its login and any public view could not be inspected.
- **Licence:** not published.
- **Verification status:** existence, description and official portal URL verified from PIB and NRIIPM pages. **Data access: not verified, and assumed unavailable.**
- **Suitable for:** the best real source for production, if a data-sharing agreement gives Manipur rice observations (district/block, weekly, with ETL-based counts).
- **Not suitable for:** this prototype, today, because no observations can be obtained.
- **Open questions to put to DPPQ&S / NRIIPM:** Are Manipur rice observations recorded? At what resolution (GPS, village, block)? Which pests (BPH, blast, stem borer)? Can an export be shared, and under what terms?

### 2–3. ICAR-NRIIPM e-pest surveillance, including Tripura Boro rice (the Northeast example)

- **Publisher:** ICAR-NCIPM (now NRIIPM) with the Department of Agriculture, Tripura, under NFSM-Rice.
- **URLs:** ICAR news, "ICT based e-Pest surveillance and advisory services for rice farmers of Tripura during Boro 2018", https://icar.org.in/en/node/2950 ; ICAR-NCIPM Annual Report 2016-17, https://nriipm.res.in/NCIPMPDFs/AnnualReport/AR2016-17_.pdf ; Annual Report 2017-18, https://nriipm.res.in/NCIPMPDFs/AnnualReport/NCIPMAR2017-18_.pdf
- **The three layers, kept separate:**
  1. **Documented methodology (available).**
     - Trained pest scouts record "field level data on prevalence of pest and disease … on weekly basis". The data are uploaded to the NCIPM server, and area-specific advisories are sent by SMS.
     - Variables (AR 2017-18): bacterial blight (% severity), neck blast (% severity), ear head bug (number/hill), hispa (number/hill), leaf folder (% folded and damaged leaves), plant hopper (number/hill), yellow stem borer (% dead heart / white ear head), swarming and other caterpillars (number/hill).
  2. **Published statistics (available, aggregates only).**
     - 2016-17 pilot: Dhalai district, 55 villages, 515 farmers, 12 field scouts, 133 advisories, 8,000 SMS.
     - 2017-18: 7 districts (Dhalai, Gomti, Khowai, North Tripura, Sepahijala, South Tripura, West Tripura), 54 talukas, 496 villages, 5,895 farmers, 826 advisories, 68,670 SMS.
     - Boro 2018: rolled out in six districts over about 79,000 ha.
     - The finding reported: "no rice pest had crossed ETL" during surveillance.
  3. **Downloadable observations: none found.** Neither the per-village, per-week records nor any export is published.
- **Spatial resolution:** village / taluka (block) within districts. **Temporal:** weekly, Boro and kharif seasons 2016–2018.
- **Authentication:** none for the reports. The underlying records sit on the NRIIPM server, with no public access.
- **Other NRIIPM systems checked on 2026-10-08:**
  - The "ICAR-Pest Monitoring and Advisory System" link on the NRIIPM "ICT Applications / Databases" page redirects to an error page.
  - The NRIIPM "Pest Alerts" page lists advisory PDFs only, the latest from Jan 2023. The last paddy alert is dated 6 Oct 2022.
  - **NISPM / OPMAS** (the older National Information System for Pest Management / online pest monitoring) is named in secondary sources. No live system or data for it was found on the NRIIPM site.
- **Licence:** not published.
- **Verification status:** methodology and statistics verified from the ICAR and NCIPM documents. Observations: not accessible.
- **What it gives this prototype:** the observation schema follows this methodology (weekly field survey, ETL-based count or % damage per pest, village/block resolution, crop stage). It is the model for a Manipur programme and the strongest argument for one.
- **Not suitable for:** evidence in Manipur zones. It covers a different state, the data are historical, and they are not available.

### 4. NICRA Technical Bulletin 39: weather-based prediction for rice insect pests

- **Publisher:** ICAR-NCIPM, 2016. Vennila S., Singh J., Wahi P., Bagri M., Das D.K., Srinivasa Rao M. *Web enabled weather based prediction for insect pests of rice*. https://nriipm.res.in/NCIPMPDFs/Publication/InsectPestsRice_.pdf
- **Type:** agronomic rules (calibration).
- **Geographic coverage:** 7 real-time pest dynamics centres: Ludhiana, Chinsurah, Raipur, Karjat, Hyderabad, Mandya and Aduthurai. **None is in the Northeast.** The agro-ecologically nearest is Chinsurah (West Bengal), in eco-region R15, "Bengal and Assam plain".
- **Temporal coverage:** light-trap and weather data, 2000–2010 or 2011–2014 depending on the station.
- **Variables:** weekly (standard meteorological week, SMW) Tmax, Tmin, morning and evening RH, rainfall, sunshine and wind, lagged one week. The pest variable is light-trap catches classed low/moderate/high.
- **Rule form:** severity is predicted from **how many** of a set of weather criteria are met in a week. Example (Table 5): Chinsurah BPH "High (>200)" when more than four of Tmax 33–34, Tmin 22–25, RF 0–10, RH-I 89–92, RH-II 55–65, SSH 6–9 hold. NCIPM's 2017-18 report gives 87% validation accuracy for BPH at Raipur.
- **Suitable for:** Member A's review of the BPH, stem borer and leaf folder weather rules.
- **Not suitable for:** direct use in Manipur. The rules are location-specific, and porting Chinsurah numbers to the Imphal valley would be unvalidated.
- **Engine gap (for the integration lead, not a threshold choice):** `pest_rules.json` cannot yet express this rule form. It would need four things:
  - an "N of M criteria" match
  - weekly aggregation
  - RH at fixed hours (morning/evening)
  - sunshine and wind (not fetched today)

### 5. ICAR-CRIDA CropPest DSS: crop–pest–disease–weather database

- **Publisher:** ICAR-Central Research Institute for Dryland Agriculture (CRIDA) / NAIP. http://www.icar-crida.res.in:8080/naip/AccessData.jsp
- **Dataset:** "34,472 weekly pest records for 11 insect pests and diseases in rice and 13 in cotton, with weather, across 12 locations". The page was last updated 21 Oct 2014.
- **Coverage:** rice centres offered for BPH are Cuttack, Ludhiana, Maruteru, Palampur, Raipur and Rajendranagar. Nothing in the Northeast. The query's year list runs from 1959 to 2011.
- **Access method:** interactive web form. A query was confirmed to work on 2026-10-08; no API is documented.
- **Licence:** not stated. Permission is needed before reuse.
- **Suitable for:** historical calibration of pest–weather relations (Member A).
- **Not suitable for:** current or Manipur evidence.

### 6. AICRP-Rice Production Oriented Survey (ICAR-IIRR)

- **Publisher:** ICAR-Indian Institute of Rice Research with the agricultural universities and state departments of agriculture. Report "Production Oriented Survey 2025": http://aicrip-intranet.in/Documents/AicripSite/2025/Production%20Oriented%20Survey%202025.pdf . Database page: https://www.icar-iirr.org/index.php/en/services/databases?id=220
- **2025 coverage:** 15 states (Andhra Pradesh, Gujarat, Haryana, J&K, Karnataka, Kerala, Maharashtra, Odisha, Puducherry, Punjab, Tamil Nadu, Telangana, Uttar Pradesh, Uttarakhand, West Bengal); 133 districts, 979 villages, 1,400 farmers. **No Manipur or other NE state** (0 matches for Manipur district names in the report text).
- **Variables:** district tables of intensity per pest (stem borer, leaf folder, BPH, WBPH, gundhi bug, gall midge) and per disease, as L / M / H with % ranges.
- **Database:** "distribution and intensity of rice insect pests at district level over 3 decades". Interactive access and Manipur coverage were **not verified**.
- **Suitable for:** if an earlier POS year covers Manipur districts, those rows are **historical, district-level** evidence (Strategy 2). They would be labelled historical and kept out of the current score; the engine already does this.
- **Not suitable for:** current Manipur risk (the 2025 report has no Manipur rows).

### 7. IPM Package for Rice: economic threshold levels (ETL)

- **Publisher:** National Centre for Integrated Pest Management and DPPQ&S, 2014 (revising the 2001-02 package). https://niphm.gov.in/IPMPackages/Rice.pdf
- **Used:** Table 3.1.2, "Economic Threshold Level (ETL) of major pests of rice crop stage wise" (package p. 9).
- **Transcribed to** `satquery/agri/assets/observation_rules.json`, with page notes. This covers BPH/WBPH, foliar and neck blast, yellow stem borer, leaf folder, gall midge, bacterial leaf blight and gundhi bug.
- **Left out:** multi-part ETLs that need two measurements together (brown spot, sheath blight, sheath rot, tungro), rather than simplifying them.
- **Status: PLACEHOLDER.** These values are cited but not yet verified by Member A. The low/moderate/high mapping from an ETL range is an engineering choice, also PLACEHOLDER.
- **Suitable for:** reading a real field count (for example 18 hoppers/hill at tillering) as "at or above ETL".
- **Not suitable for:** weather risk or outbreak probability. An ETL is an action threshold.

### 8. data.gov.in (Open Government Data Platform India)

- **Method:**
  - web searches restricted to data.gov.in for pest, disease, surveillance and rice terms
  - the portal's own search page, which builds its results in JavaScript, so no results came back in the HTML
  - the OGD API, which could not be reached from our network
- **Found:** crop statistics only. Examples: "District-wise, season-wise crop production statistics" (Ministry of Agriculture and Farmers Welfare), "State-wise Area under Rice from 2019-20 to 2022-23", "State-wise Damage to Crop Area Due to Heavy Rains/Floods during 2022".
- **No pest, disease or crop-surveillance observation dataset was found.**
- **Next step:** a team member with portal access searches the catalogue directly for "pest", "disease", "surveillance" and "NPSS" to confirm.

### 9–10. Manipur and Northeast sources

- **GKMS district agromet advisories:** issued by the Agro-Meteorological Field Unit (AMFU) at ICAR RC NEH Manipur Centre, Lamphelpat, with IMD. 2018–2019 bulletins appear on kiran.nic.in, for example https://www.kiran.nic.in/pdf/manipur/2018/Oct_18/2-6-10-2018.pdf . They hold district weather forecasts and crop advisories. The download failed from our network (DNS), so their content is known only from search results. They are **advisories, not observations**.
- **Manipur Department of Agriculture, CAU Imphal, KVKs, ICAR RC NEH Manipur Centre:** no public pest/disease dataset, dashboard or bulletin series with location- and date-level observations was found. ICAR RC NEH Manipur Centre research in the valley districts (Imphal East, Imphal West, Thoubal, Bishnupur) appeared in searches, but it concerned soils, not pests.
- **Literature context, from search summaries:** brown planthopper resistance screening of Manipur rice accessions, and gall midge as a key pest in parts of the Northeast. This is context only.
- **Manipur rice blast epidemiology (lead for Member A).** Search summaries describe a study in Imphal that used multiple regression on weather and airborne spore data. It found disease severity rising with plant age, airborne spore concentration, relative humidity and rainfall, with "comparatively low temperature" common to disease incidence.
  - The **full citation could not be located**. A similarly-themed 2026 *Aerobiologia* paper ("Influence of meteorological parameters on airborne rice pathogens…") was checked and is from **Brunei**, not Manipur.
  - This is the most relevant lead for a Manipur blast weather rule. Member A should locate and verify the original (likely CAU Imphal or Manipur University) before using any number from it.
- **Verdict:** authoritative institutions exist, but machine-readable public observations were not found.

### 11. GBIF occurrence records

- **Queried on 2026-10-08** through https://api.gbif.org/v1/occurrence/search :
  - *Nilaparvata lugens*: 470 records for India; **0** for state "Manipur"; **0** in the Manipur bounding box (23.8–25.7 N, 93.0–94.8 E).
  - *Pyricularia oryzae*: 619 for India; **0** for state "Manipur".
- Records are presence-only and opportunistic (iNaturalist, material samples), with no severity.
- **Not suitable** as risk evidence.

### 12. Image datasets

- Mendeley "Rice Leaf Bacterial and Fungal Disease Dataset", https://data.mendeley.com/datasets/hx6f852hw4 : Bangladesh, 1,701 original images from Jul–Oct 2023, 8 classes.
- IP102: 75,000+ insect pest images in 102 classes.
- RP11: rice adult insect images (PMC article PMC12194132).
- **Image classification only.** These have no geographic or temporal link to Manipur fields and are never used as prevalence. They are candidates for AG-01 (P2.2) only.

## Selected strategy and the path to real data

**Selected: Strategy C**, because no Strategy A (current geospatial surveillance) or Strategy B (historical surveillance) source is accessible for Manipur today:
- The engine uses real weather and real NDVI.
- The weather rules and ETLs come from official publications and stay PLACEHOLDER until Member A verifies them.
- Pest/disease observations are SAMPLE, labelled at every layer:
  - record: `status: SAMPLE`, `synthetic: true`, `label: "SAMPLE DATA — PROTOTYPE SIMULATION"`
  - factor: name suffixed "(SAMPLE)", `sample_data: true`
  - assessment: `includes_sample_data`, a reason line
  - API: `sample_label`
  - UI: badges

Path to real deployment, in order of value:

1. **Department of Agriculture, Manipur (with KVKs / CAU):** export of pest-scout or AESA field records for kharif rice, weekly by block or village, in `data/agri/observation_template.csv`. This is the quickest real source if records exist.
2. **NPSS (DPPQ&S / ICAR-NRIIPM):** request Manipur rice observations under a data-sharing agreement. This is the most systematic national source.
3. **Field-inspection workflow (P1.4):** verified inspection outcomes become REAL observations (`observation_type: inspection`, `verified: true`).
4. **AICRP-Rice POS:** check earlier years for Manipur districts. Any match is historical context only (Strategy 2).
5. **Member A:** verify `pest_rules.json` and `observation_rules.json`. The NICRA bulletin and Manipur literature are the leads.

## Internal schemas

**Observation** (`satquery/agri/models.py`, `PestObservation`). Only fields the source records are filled in:

```json
{
  "id": "…", "status": "REAL", "observed_on": "2026-10-06",
  "district": "Kakching", "block": "…", "village": "…",
  "latitude": null, "longitude": null, "spatial_resolution": "block",
  "crop": "rice", "pest": "brown_planthopper", "crop_stage": "tillering",
  "observation_type": "field_survey", "metric": "hoppers_per_hill", "value": 12, "unit": "hoppers/hill",
  "severity": null, "prevalence_pct": null,
  "source": "<publisher: dataset>", "source_url": "…", "source_date": "…", "verified": false
}
```

The loader refuses:
- REAL records without a named source
- SAMPLE and REAL records mixed in one file
- coordinates on block- or district-level records (no coordinates are invented)
- records with no measure
- duplicate ids
- non-ISO dates

Dataset metadata (publisher, licence, access date, coverage, surveyed districts and pests, method, limitations) travels with the data and becomes the provenance of the factor.

**Agronomic rules** stay separate from observations:
- Weather rules: `satquery/agri/assets/pest_rules.json` (Member A).
- ETLs for reading observations: `satquery/agri/assets/observation_rules.json` (each with source, page, `verified_by`/`verified_on`, applicability).
- Weights, bands and engineering breakpoints: `satquery/agri/assets/risk_model.json`.

None is hard-coded in Python. A rule marked VERIFIED without `verified_by` and `verified_on` fails to load.

## Data quality of the inputs in use (Step 19)

| Input | Publisher | Accessed | Observation date | Spatial resolution | Temporal resolution | Coverage | Missing values | Licence | Status / limitations |
|---|---|---|---|---|---|---|---|---|---|
| Hourly weather | Open-Meteo (best_match models) | 2026-10-08 17:03 UTC and 18:28 UTC (LIVE) | 14 past + 7 forecast days | One model grid cell per zone (e.g. 24.640 N, 93.854 E for the Bishnupur zone) | Hourly | Global | None in the 2026-10-08 run; a day with fewer than 20 hours is "unknown", not unfavourable | CC BY 4.0 | REAL but **model data, not station observations**. One point per zone. |
| NDVI vs 3-year baseline | Copernicus Sentinel-2 L2A (Statistical API) | Not fetched in this environment (no credentials) | 30-day window vs the same dates in 3 earlier years | Sentinel-2 10 m bands, statistics on an adaptive grid (at least 0.0005°, about 50 m) over the zone polygon | Every Sentinel-2 overpass, median per pixel | Global | Cloud-masked by SCL; windows under 30% clear are refused | Free, full and open | REAL when credentials are set. **Supporting evidence of vegetation change, never pest detection.** |
| Pest/disease observations | SatQuery SAMPLE generator | Generated per run | Within the last 21 days | Random point inside each zone | Daily dates | Demo zones | n/a | n/a | **SAMPLE / SYNTHETIC.** Hand-set pressure per zone in `sample_scenario.json` (Bishnupur "high"; Kakching and Thoubal "elevated"). |
| ETL table | NCIPM / DPPQ&S (2014) | 2026-10-08 | n/a | National | Crop stage | All India | Multi-part ETLs omitted | Government publication | **PLACEHOLDER** (transcribed, not yet verified) |
| Weather rules | Team (Phase 2) | n/a | n/a | n/a | Daily | n/a | n/a | n/a | **PLACEHOLDER**, no source (Member A) |

## Access log (2026-10-08, second pass late 2026-10-08 / 2026-10-09 IST)

- **Second pass:**
  - Fetched: NRIIPM home, "ICT Applications / Databases", "Database & Electronic Networking" and "Pest Alerts" pages, plus the *Aerobiologia* 2026 article metadata.
  - Searched: NISPM/OPMAS, Manipur KVK and CAU pest surveys, NPSS access, blast forewarning rules.
  - Not reachable: `www.ncipm.res.in` and `npss.dac.gov.in` (DNS from our network).

**First pass (2026-10-08):**

- **Fetched and read in full:**
  - PIB NPSS release
  - NRIIPM ICT success story
  - ICAR Tripura news item
  - NCIPM Annual Reports 2016-17 and 2017-18
  - NICRA Technical Bulletin 39
  - IPM Package for Rice (2014)
  - CRIDA CropPest DSS pages, plus one working query
  - IIRR database page
  - Production Oriented Survey 2025
- **Queried:** GBIF API.
- **Could not be reached from our network (DNS):** the Manipur agriculture department website, the ICAR RC NEH Manipur centre profile, and kiran.nic.in bulletins. Their content above comes from search results only.
- **Could not be reached:** the data.gov.in API, and the NPSS portal `npss.dac.gov.in` (DNS). The second pass confirmed this address as the official portal, linked from the NRIIPM home page.
