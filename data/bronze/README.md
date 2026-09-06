# Bronze — immutable source copies

**What Bronze is:** the first warehouse shelf. Every external or intake file is **copied** here with a content hash. We never “clean in place.” If a source is wrong, we fix upstream and re-ingest.

**What Bronze is not:** analysis tables. Do not join Bronze for modeling — use Silver/Gold.

## Layout

| Path | Contents | Origin |
|------|----------|--------|
| `berkeley/` | LBNL interconnection queue workbook copies | `data/intake/` |
| `miso/` | Current MISO queue CSV copies | `data/intake/` |
| `enrichment/` | External feeds used for features | APIs / public downloads / harvests |

## Enrichment bronze subfolders (by source)

| Subfolder | Source | Prediction role |
|-----------|--------|-----------------|
| `census_county_fips` / `census_county_gazetteer` / `census_acs` | US Census | Geography keys, population / rurality |
| `fema_nri` | FEMA National Risk Index | Local disaster risk |
| `treasury_energy_communities` | Treasury / DOE IRA lists | Energy-community incentive |
| `fred_rates` | FRED (DGS10, PPI) | Cost of capital / construction cost |
| `eia930` | EIA-930 MISO BA | System demand / generation pressure |
| `eia860` | EIA-860 plants | Operating fleet context (sparse match) |
| `noaa_storm_events` | NOAA Storm Events | Extreme weather pressure |
| `hifld_transmission` | HIFLD transmission lines | Distance / voltage near POI |
| `miso_dpp_studies` | MISO DPP GI PDFs / Optics | Study cost & delay extracts |
| `miso_mtep` | MISO MTEP Appendix A | Nearby transmission investment |
| `gdelt_news` | GDELT GKG (bounded) | Local news volume / tone |
| `queue_derived_study` | Derived from queue (no external file) | Study/POI pressure markers |

Next layer: [`../silver/README.md`](../silver/README.md).
