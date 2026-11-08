# Project data

All files are in `raw/`. They are public data, downloaded on 26 October 2026 and left unmodified (only formatted as CSV). The cleaned versions, produced by `src/data_processing.py`, are in `processed/`.

Treatment date: August 2022 (CHIPS Act on 9 August, IRA on 16 August).

## Overview

| File | Source | Frequency | Period | Role in the project |
|---|---|---|---|---|
| `census_private_construction_spending_monthly.csv` | US Census Bureau | Monthly | 2010-01 → 2026-08 | Main outcome, cross-sector DiD |
| `fred_macro_industry_monthly.csv` | FRED (St. Louis Fed) | Monthly | 2010-01 → 2026-09 | Deflator, confounders, downstream effects |
| `oecd_gfcf_other_structures_quarterly.csv` | OECD | Quarterly | 2010-Q1 → 2026-Q2 | Synthetic control, United States and other countries |
| `cim_us_clean_investment_quarterly.csv` | Clean Investment Monitor | Quarterly | 2018-Q1 → 2026-Q2 | Clean tech investment by technology |
| `cim_state_investment_share_gdp.csv` | Clean Investment Monitor | Cross-section | Last 4 quarters | State exposure |

---

## 1. Census: private construction spending

`census_private_construction_spending_monthly.csv`

The file measures the value of private construction work done each month in the United States (*Value of Construction Put in Place*). These are actual expenditures, not announced projects.

Amounts are in millions of current dollars, at a seasonally adjusted annual rate (SAAR). A value of 120,000 means that, at that month's pace, 120 billion would be spent over a year.

Source: `privsatime.xlsx` file at https://www.census.gov/construction/c30/historical_data.html

| Column | Description |
|---|---|
| `date` | First day of the month |
| `flag` | `p` = preliminary, `r` = revised (the latest months may still change) |
| `nonresidential` | Total private non-residential construction |
| `office`, `data_center` | Offices, of which data centers (data centers from 2014) |
| `commercial`, `warehouse` | Commercial, of which warehouses |
| `health_care`, `educational` | Health care, educational |
| `power`, `electric` | Power, of which electric |
| `manufacturing` | Total manufacturing construction |
| `mfg_computer_electronic_electrical` | Treated sector: semiconductor, electronics and battery plants |
| `mfg_chemical`, `mfg_food_bev_tobacco`, `mfg_plastic_rubber`, `mfg_nonmetallic_mineral`, `mfg_fabricated_metal`, `mfg_transportation_equipment` | Other manufacturing subsectors, control sectors |

This file feeds the DiD, which compares `mfg_computer_electronic_electrical` with the other subsectors before and after August 2022. Since amounts are nominal and construction costs rose sharply in 2021-2022, they are deflated by `WPUSI012011` (FRED file) before the analysis.

---

## 2. FRED: macro and industry context

`fred_macro_industry_monthly.csv`

Source: https://fred.stlouisfed.org (one column per FRED series ID).

| Column | Description | Unit |
|---|---|---|
| `TTLCONS` | Total construction (public + private) | $M, SAAR |
| `TLNRESCONS` | Total non-residential construction | $M, SAAR |
| `TLMFGCONS` | Total manufacturing construction | $M, SAAR |
| `PRMFGCONS` | Private manufacturing construction | $M, SAAR |
| `TLCOMCONS` | Commercial construction | $M, SAAR |
| `TLOFCONS` | Office construction | $M, SAAR |
| `WPUSI012011` | Construction materials price index, used as deflator | Index 1982 = 100 |
| `IPMAN` | Manufacturing industrial production | Index 2017 = 100 |
| `IPG3344S` | Semiconductor industrial production | Index 2017 = 100 |
| `MANEMP` | Total manufacturing employment | Thousands |
| `CES3133400001` | Employment, computer & electronic products | Thousands |
| `CES3133440001` | Employment, semiconductors and components | Thousands |
| `CES3133500001` | Employment, electrical equipment | Thousands |
| `CES3133600101` | Employment, motor vehicles and parts | Thousands |
| `FEDFUNDS` | Fed policy rate | % |
| `GS10` | 10-year Treasury yield | % |

These series are used to deflate construction spending (`WPUSI012011`) and to track confounders. The 2022-2023 rate hikes (`FEDFUNDS`, `GS10`) slow investment exactly at the time of treatment, which biases the estimated effect downwards. Finally, they show whether investment translated into output (`IPG3344S`) and jobs (`CES` series).

---

## 3. OECD: investment in structures by country

`oecd_gfcf_other_structures_quarterly.csv`

The file measures gross fixed capital formation (GFCF) in "other buildings and structures" (code N112G), i.e. all non-residential: factories, offices, infrastructure.

Series are in chained volumes (adjusted for inflation), seasonally adjusted, in millions of national currency (dollars, euros, yen, kronor).

Source: OECD Quarterly National Accounts (`DSD_NAMAIN1@DF_QNA`), https://data-explorer.oecd.org

The file contains a `quarter` column, then one column per country (ISO code): `USA`, the treated country, and 20 donor countries (`AUS`, `AUT`, `CAN`, `CZE`, `DEU`, `DNK`, `ESP`, `FIN`, `FRA`, `GBR`, `IRL`, `ISR`, `ITA`, `JPN`, `NLD`, `NOR`, `NZL`, `POL`, `PRT`, `SWE`).

It feeds the synthetic control, which weights the donor countries to reproduce the US trajectory before 2022. Three caveats apply. Each country must be rebased (100 = 2019) before any comparison, since currencies and sizes differ. The measure is broader than the Census one, as it includes all non-residential construction, so the effect will be diluted. Finally, the donors are themselves disturbed: Europe faces the 2022 energy crisis and runs its own plans (European Chips Act).

---

## 4. Clean Investment Monitor: clean tech investment by technology

`cim_us_clean_investment_quarterly.csv`

The file measures investment in low-carbon technologies in the United States, at the national level, by segment and technology. Amounts are in billions of 2024 dollars, already adjusted for inflation.

Source: Rhodium Group and MIT, https://www.cleaninvestmentmonitor.org/us/database (CC BY 4.0 licence). Values are extracted from the charts of the public dashboard.

Columns follow the `<group>__<technology>` structure.

| Prefix | Meaning |
|---|---|
| `total__` | Total actual investment by segment: `manufacturing`, `energy_and_industry`, `retail` |
| `mfg_actual__` / `mfg_announced__` | Clean tech factories (batteries, solar, electric vehicles, critical minerals, wind, electrolyzers), actual or announced investment |
| `ei_actual__` / `ei_announced__` | Energy production and industrial decarbonization (solar, storage, wind, hydrogen, carbon capture, sustainable aviation fuels, nuclear) |
| `retail__` | Household and business purchases (electric vehicles, heat pumps, distributed solar) |

An empty cell means there is no value that quarter, `NaN` a value missing from the source.

This file shows which technologies captured investment after the IRA and allows comparing announced and actual investment, announcements reacting faster to the law. It can also serve as a robustness check against the Census, but the pre-treatment period is short (2018-2022).

---

## 5. Clean Investment Monitor: state exposure

`cim_state_investment_share_gdp.csv`

For each state, the file gives clean tech investment over the last 4 quarters as a % of its GDP, by segment (`retail`, `manufacturing`, `energy_and_industry`).

It is a snapshot at one date, not a time series. It can measure treatment intensity by state, for example in a continuous-treatment DiD if state-level employment data are added.

---

## How the files fit together

| Analysis step | Files |
|---|---|
| 1. Describe the boom | Census + FRED (`TLMFGCONS`) |
| 2. Cross-sector DiD | Census, deflated with `WPUSI012011` (FRED) |
| 3. Cross-country synthetic control | OECD |
| 4. Technologies involved | Quarterly CIM |
| 5. Downstream effects (output, employment) | FRED |
| 6. Robustness (rates, placebos) | FRED + all other files |

## Not included

The state × quarter × technology panel and the plant-by-plant database of the Clean Investment Monitor are only available on ClimateDeck (Rhodium), with a free account. To use them, download them manually and place them in `raw/`.
