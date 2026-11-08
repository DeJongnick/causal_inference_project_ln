# IRA & CHIPS Act: did they cause the US industrial investment boom?

Project for the *Causal Inference & Experimentation* course (Albert School).

## Members

- Léo Bouchand
- Nicolas Le Jeune

## Context

In August 2022, the United States passed two major industrial policy laws.

- The CHIPS and Science Act (9 August 2022) provides about \$52bn in subsidies and tax credits to bring semiconductor production back to the United States.
- The Inflation Reduction Act, or IRA (16 August 2022), grants large tax credits to clean energy and its manufacturing supply chain (batteries, solar, electric vehicles, hydrogen).

In the following months, US factory construction spending soared. Construction in the computer, electronic and electrical sector went from about \$8bn (annual rate) in early 2021 to more than \$120bn in mid-2024.

## Research question

> How much of this boom can be causally attributed to the IRA and the CHIPS Act?

The boom coincides with other factors: post-COVID reshoring, supply chain tensions, construction cost inflation and the Fed's rate hikes. The goal is to isolate the laws' own effect by building a counterfactual, i.e. what would have happened without them.

## Approach

The project combines two methods.

1. A Difference-in-Differences compares, before and after August 2022, computer, electronic and electrical factory construction, directly targeted by the laws, with the other manufacturing subsectors (`ntb/did.ipynb`).
2. A synthetic control builds a synthetic United States from a combination of OECD countries that reproduces the US trajectory before 2022. The gap after 2022 measures the effect of the laws at the country level (`ntb/synthetic_control.ipynb`).

Placebos (fake dates, untreated sectors or countries) are used for inference and robustness checks. The exploratory analysis is in `ntb/eda.ipynb`.

## Stakes

The topic can also be read from an investor's point of view (private equity, infrastructure). The question is which sectors and states captured the capital, and whether public policy created investment or only shifted projects that would have happened anyway. The slowdown observed from 2025, as some credits are being called into question, also raises the question of how durable the boom is and offers a second event to study.

## Data

All data are public: Census Bureau, FRED, OECD and Clean Investment Monitor. They are described in detail in [`data/README.md`](data/README.md).

## Repository structure

```
data/
  raw/                       source files, unmodified
  processed/                 cleaned files written by src/data_processing.py
src/
  data_processing.py         loading, deflation, DiD panel, OECD index, donor fit
  did.py                     2×2 DiD, TWFE, event study, placebos, robustness
  synth.py                   synthetic control weights, in-space placebos, p-values, robustness
  plot_functions.py          plotly theme and charts
ntb/
  eda.ipynb                  exploratory analysis
  did.ipynb                  cross-sector Difference-in-Differences
  synthetic_control.ipynb    cross-country synthetic control
reports/                     project report and figures
```

## Reproduce

```bash
uv sync --group dev
uv run python src/data_processing.py
uv run jupyter nbconvert --to notebook --execute --inplace ntb/eda.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace ntb/did.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace ntb/synthetic_control.ipynb
```

The notebooks can also be opened and run in Jupyter.

## Main results

The DiD estimates that the laws raised factory construction in the computer, electronic and electrical sector by +189% (lower bound, chip shortage) to +452% (upper bound, anticipation) since August 2022, i.e. \$43.0bn to \$53.9bn (2019 dollars) per year. The effect peaks at +689% in 2023-Q4, then falls to +221% in mid-2026 (upper-bound reading). At the country level, the synthetic control finds that US non-residential investment exceeds its synthetic twin by +8.3 index points on average after 2022-Q3, a gap that does not stand out from the placebos (p = 0.286). This result is fragile: without Ireland among the donors, the gap falls to +1.7 points.
