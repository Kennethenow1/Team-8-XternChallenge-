# Deferred county/tract enrichment (until FIPS coverage OK)

Do **not** enable until panel `county_fips` coverage is acceptable (especially observation year 2026)
and tract matching exists where Energy Communities require it.

Enable by setting `RUN_DEFERRED_COUNTY_JOINS = True` in `scripts/run_enrichment_sprint.py`
or `populate_all(run_deferred_county_joins=True)`.

## FEMA National Risk Index (v1.20)

- Prefer official ZIP under `data/bronze/fema/nri_v1_20/` if automated download returns 403/HTML.
- Join on `county_fips`.
- Keep: `nri_version`, `nri_overall_risk_score`, `nri_expected_annual_loss`,
  `nri_social_vulnerability`, `nri_community_resilience`,
  `flood_risk_score`, `tornado_risk_score`, `wildfire_risk_score`.
- **PIT note:** NRI v1.20 is a static geographic characteristic. Do not pretend the 2025
  release was available in 2020; document backcast assumption or exclude from strict PIT experiments.

## Census PEP (2020–2023)

- API: `https://api.census.gov/data/2023/pep/charv` with `YEAR=2020..2023`, `pep_vintage=2023`.
- Requires `CENSUS_API_KEY` in `.env` (never commit).
- Columns: `county_fips`, `year`, `population`, `population_yoy_pct`,
  `population_change_since_2020`, `pep_vintage`, `available_date`.
- Do not apply a single 2024 estimate backward to 2020–2023.

## Energy Communities (versioned Treasury lists)

Effective periods:

- 2023-01-01 through 2024-06-06
- 2024-06-07 through 2025-06-22
- 2025-06-23 through 2026-06-09
- 2026-06-10 onward

Columns: `geography_id`, `geography_type`, `eligible_flag`, `eligibility_category`,
`effective_start`, `effective_end`, `source_notice`, `available_date`.

Rules:

- Before 2023: `energy_community_applicable = 0`.
- Missing location → `unknown`, never `eligible = 0` solely due to missing FIPS/tract.
- Preserve which IRS notice produced the determination.
