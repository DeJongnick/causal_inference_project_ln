"""Cross-sector Difference-in-Differences on the sector × month panel.

All functions take the long panel `did_panel_monthly` (data/processed/): one row per sector × month.
The DiD compares a `before` window and an `after` window; the months in between (the transition) are excluded.
"""

import math
from datetime import date

import polars as pl
import statsmodels.formula.api as smf

from data_processing import TREATED_SECTOR, TREATMENT_DATE

Y = "log_spending_real"
BEFORE = (date(2019, 7, 1), date(2021, 6, 1))  # treated − controls gap roughly stable
TRANSITION = (date(2021, 7, 1), date(2022, 7, 1))  # rise before the laws: anticipation or chip shortage
AFTER = (TREATMENT_DATE, date.max)
TRANSPORT = "mfg_transportation_equipment"


def _months(d: date) -> int:
    return d.year * 12 + d.month - 1


def _shift(d: date, months: int) -> date:
    m = _months(d) + months
    return date(m // 12, m % 12 + 1, 1)


def _periods(panel: pl.DataFrame, before: tuple[date, date], after: tuple[date, date], treated: str) -> pl.DataFrame:
    """Months of the two windows only, with A_s (`treated`), Post_t (`post`) and T_st = A_s × Post_t (`T`)."""
    return panel.filter(pl.col("date").is_between(*before) | pl.col("date").is_between(*after)) \
        .with_columns((pl.col("sector") == treated).alias("treated"), (pl.col("date") >= after[0]).alias("post")) \
        .with_columns((pl.col("treated") & pl.col("post")).cast(pl.Int8).alias("T"))


def cell_means(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER,
               treated: str = TREATED_SECTOR) -> pl.DataFrame:
    """2×2 table: mean of y by group and period, change in each row and treated − controls gap."""
    m = {(a, p): v for a, p, v in
         _periods(panel, before, after, treated).group_by("treated", "post").agg(pl.col(y).mean()).iter_rows()}
    rows = [("Treated", m[True, False], m[True, True]), ("Controls", m[False, False], m[False, True])]
    rows.append(("Gap treated − controls", rows[0][1] - rows[1][1], rows[0][2] - rows[1][2]))
    return pl.DataFrame(rows, schema=["group", "before", "after"], orient="row") \
        .with_columns((pl.col("after") - pl.col("before")).alias("change"))


def did_2x2(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER,
            treated: str = TREATED_SECTOR) -> float:
    """Double difference: change in the gap, the bottom-right cell of `cell_means`."""
    return cell_means(panel, y, before, after, treated)["change"][-1]


def effect(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER) -> float:
    """Effect in %: exp(δ) − 1 in logs; in levels, δ over the treated counterfactual (before + change in controls)."""
    m = cell_means(panel, y, before, after)
    if y == Y:
        return math.exp(m["change"][-1]) - 1
    return m["change"][-1] / (m["before"][0] + m["change"][1])


def twfe(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER) -> dict:
    """Y_st = α_s + λ_t + δ T_st + ε_st on the two windows, standard error clustered by sector."""
    d = _periods(panel, before, after, TREATED_SECTOR).with_columns(pl.col("date").cast(pl.String))
    fit = smf.ols(f"{y} ~ T + C(sector) + C(date)", data={c: d[c].to_numpy() for c in d.columns}) \
        .fit(cov_type="cluster", cov_kwds={"groups": d["sector"].rank("dense").to_numpy()})
    return {"delta": float(fit.params["T"]), "se_cluster": float(fit.bse["T"])}


def readings(panel: pl.DataFrame) -> pl.DataFrame:
    """Range of the effect: upper bound (reference = plateau) and lower bound (reference = transition)."""
    rows = [("Upper bound: anticipation", BEFORE), ("Lower bound: chip shortage", TRANSITION)]
    return pl.DataFrame([{"reading": name, "before": f"{before[0]:%Y-%m} → {before[1]:%Y-%m}",
                          "delta": did_2x2(panel, before=before), "effect": effect(panel, before=before)}
                         for name, before in rows])


def dollars(panel: pl.DataFrame) -> pl.DataFrame:
    """Average effect in 2019 $bn per year: treated mean spending after ($M SAAR / 1,000) minus spending / exp(δ)."""
    spent = panel.filter((pl.col("sector") == TREATED_SECTOR) & pl.col("date").is_between(*AFTER))["spending_real"].mean()
    return readings(panel).select(pl.col("reading").alias("bound"), "effect",
                                  (spent * (1 - (-pl.col("delta")).exp()) / 1000).alias("bn_per_year"))


def event_study(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, treated: str = TREATED_SECTOR,
                start: date = date(2015, 1, 1)) -> pl.DataFrame:
    """Event study: treated − controls gap per quarter minus the mean gap over `before` (one 2×2 DiD per quarter)."""
    a = pl.col("sector") == treated
    gap = panel.filter(pl.col("date") >= start).group_by("date").agg((pl.col(y).filter(a).mean() - pl.col(y).filter(~a).mean()).alias("gap"))
    ref = gap.filter(pl.col("date").is_between(*before))["gap"].mean()
    return gap.group_by(pl.col("date").dt.truncate("1q")).agg((pl.col("gap").mean() - ref).alias("coef")).sort("date") \
        .with_columns(pl.format("{}-Q{}", pl.col("date").dt.year(), pl.col("date").dt.quarter()).alias("quarter"))


def dynamics(es: pl.DataFrame) -> pl.DataFrame:
    """First quarter after treatment, peak and last observed quarter, as a log gap and in %."""
    post = es.filter(pl.col("date") >= date(TREATMENT_DATE.year, (TREATMENT_DATE.month - 1) // 3 * 3 + 1, 1))
    return pl.concat([post.head(1).with_columns(pl.lit("First quarter").alias("moment")),
                      post.top_k(1, by="coef").with_columns(pl.lit("Peak").alias("moment")),
                      post.tail(1).with_columns(pl.lit("Last quarter").alias("moment"))]) \
        .select("moment", "quarter", "coef", (pl.col("coef").exp() - 1).alias("effect"))


def time_placebos(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER,
                  last: date = TRANSITION[0]) -> pl.DataFrame:
    """Same 2×2 DiD, same window lengths, on every fake date whose windows end before `last`."""
    t, start = after[0], panel["date"].min()
    b0, b1 = _months(before[0]) - _months(t), _months(before[1]) - _months(t)
    a1 = _months(min(after[1], panel["date"].max())) - _months(t)
    rows, f = [], _shift(start, -b0)
    while _shift(f, a1) < last:
        rows.append({"date": f, "delta": did_2x2(panel, y, (_shift(f, b0), _shift(f, b1)), (f, _shift(f, a1)))})
        f = _shift(f, 1)
    return pl.DataFrame(rows)


def permutation(panel: pl.DataFrame, y: str = Y) -> pl.DataFrame:
    """Permutation test: δ recomputed treating each sector in turn, p = share of |δ| ≥ |treated δ|."""
    deltas = {s: did_2x2(panel, y, treated=s) for s in panel["sector"].unique()}
    true = deltas[TREATED_SECTOR]
    placebo = [d for s, d in deltas.items() if s != TREATED_SECTOR]
    return pl.DataFrame([{"delta_true": true, "placebo_min": min(placebo), "placebo_max": max(placebo),
                          "p": sum(abs(d) >= abs(true) for d in deltas.values()) / len(deltas)}])


def robustness(panel: pl.DataFrame) -> pl.DataFrame:
    """Effect in % by specification; `panel` also contains offices and commercial."""
    mfg = panel.filter(pl.col("sector").str.starts_with("mfg_"))
    return pl.DataFrame({"specification": ["Main (transition excluded)", "Without transportation equipment",
                                           "Controls + offices and commercial", "Outcome in levels",
                                           "Before window 2015-01 → 2022-07"],
                         "effect": [effect(mfg), effect(mfg.filter(pl.col("sector") != TRANSPORT)), effect(panel),
                                    effect(mfg, y="spending_real"),
                                    effect(mfg, before=(date(2015, 1, 1), _shift(TREATMENT_DATE, -1)))]})
