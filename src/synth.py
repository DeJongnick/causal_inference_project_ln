"""Cross-country synthetic control (Abadie, Diamond and Hainmueller, 2010) on OECD GFCF rebased to 100 = 2019.

All functions take the wide index `oecd_gfcf_index2019_quarterly` (data/processed/):
one `quarter` column, one column per country. The synthetic twin is a weighted average of the donors,
with non-negative weights summing to 1, chosen to track the treated unit as closely as possible before treatment.
"""

from datetime import date

import numpy as np
import polars as pl
from scipy.optimize import minimize

from data_processing import TREATED_COUNTRY

PRE = (date(2015, 1, 1), date(2022, 4, 1))  # 2015-Q1 → 2022-Q2
START = date(2022, 7, 1)  # 2022-Q3, quarter of the laws


def _donors(df: pl.DataFrame, treated: str, exclude: tuple[str, ...] = ()) -> list[str]:
    return [c for c in df.columns if c not in ("quarter", treated, *exclude)]


def weights(df: pl.DataFrame, treated: str = TREATED_COUNTRY, donors: list[str] | None = None,
            pre: tuple[date, date] = PRE) -> pl.DataFrame:
    """Weights w_j ≥ 0, Σ w_j = 1, minimising the pre-treatment mean squared gap between the treated unit and Σ w_j Y_j."""
    donors = donors or _donors(df, treated)
    d = df.filter(pl.col("quarter").is_between(*pre))
    X, y = d.select(donors).to_numpy(), d[treated].to_numpy()
    n = len(donors)
    res = minimize(lambda w: np.mean((y - X @ w) ** 2), np.full(n, 1 / n), method="SLSQP", bounds=[(0, 1)] * n,
                   constraints={"type": "eq", "fun": lambda w: w.sum() - 1})
    return pl.DataFrame({"country": donors, "weight": res.x}).sort("weight", descending=True)


def synthetic(df: pl.DataFrame, treated: str = TREATED_COUNTRY, donors: list[str] | None = None,
              pre: tuple[date, date] = PRE) -> pl.DataFrame:
    """Treated unit, synthetic twin and gap (treated − synthetic) for each quarter."""
    w = weights(df, treated, donors, pre)
    synth = pl.sum_horizontal(pl.col(c) * v for c, v in w.iter_rows())
    return df.select("quarter", pl.col(treated).alias("treated"), synth.alias("synthetic")) \
        .with_columns((pl.col("treated") - pl.col("synthetic")).alias("gap"))


def summary(s: pl.DataFrame, pre: tuple[date, date] = PRE, start: date = START, end: date = date.max) -> dict:
    """Pre and post RMSPE, their ratio, mean gap and peak gap (index points) after `start`."""
    rmspe = lambda d: d.select((pl.col("gap") ** 2).mean().sqrt()).item()
    post = s.filter(pl.col("quarter").is_between(start, end))
    peak = post.sort(pl.col("gap").abs(), descending=True).row(0, named=True)
    before, after = rmspe(s.filter(pl.col("quarter").is_between(*pre))), rmspe(post)
    return {"rmspe_pre": before, "rmspe_post": after, "ratio": after / before, "mean_gap": post["gap"].mean(),
            "peak_gap": peak["gap"], "peak_quarter": f"{peak['quarter'].year}-Q{(peak['quarter'].month - 1) // 3 + 1}"}


def space_placebos(df: pl.DataFrame, treated: str = TREATED_COUNTRY) -> tuple[pl.DataFrame, pl.DataFrame]:
    """In-space placebos (true treated unit excluded from donors): gaps in long format and ranking by RMSPE ratio."""
    gaps, rows = [], []
    for c in [treated, *_donors(df, treated)]:
        s = synthetic(df, c, _donors(df, c, exclude=(treated,)) if c != treated else None)
        gaps.append(s.filter(pl.col("quarter") >= PRE[0]).select(pl.lit(c).alias("country"), "quarter", "gap"))
        rows.append({"country": c, **{k: v for k, v in summary(s).items() if k.startswith(("rmspe", "ratio"))}})
    ratios = pl.DataFrame(rows).sort("ratio", descending=True).with_row_index("rank", offset=1)
    return pl.concat(gaps), ratios


def p_values(ratios: pl.DataFrame, treated: str = TREATED_COUNTRY, max_fit: float = 2) -> pl.DataFrame:
    """Rank p-value on the RMSPE ratio, with all countries then without those whose pre RMSPE exceeds `max_fit` times the treated one."""
    t = ratios.filter(pl.col("country") == treated).row(0, named=True)
    rows = [("All countries", ratios),
            (f"Pre RMSPE ≤ {max_fit:g} × USA", ratios.filter(pl.col("rmspe_pre") <= max_fit * t["rmspe_pre"]))]
    return pl.DataFrame([{"placebos": name, "countries": r.height, "usa_rank": (r["ratio"] >= t["ratio"]).sum(),
                          "p": (r["ratio"] >= t["ratio"]).mean()} for name, r in rows])


def robustness(df: pl.DataFrame, donor_fit: pl.DataFrame, n_best: int = 5, treated: str = TREATED_COUNTRY) -> pl.DataFrame:
    """Mean post-treatment gap (index points) by specification."""
    main = weights(df, treated)
    specs = {"Main (2022-Q3)": (None, PRE, START, date.max)}
    specs |= {f"Without {c}": (_donors(df, treated, exclude=(c,)), PRE, START, date.max)
              for c in main.filter(pl.col("weight") > 0.01)["country"]}
    specs |= {f"{n_best} best-correlated donors": (donor_fit.head(n_best)["country"].to_list(), PRE, START, date.max),
              "Treatment moved to 2021-Q3": (None, (PRE[0], date(2021, 4, 1)), date(2021, 7, 1), date.max),
              "In-time placebo (2019-Q1)": (None, (PRE[0], date(2018, 10, 1)), date(2019, 1, 1), date(2021, 10, 1))}
    return pl.DataFrame([{"specification": name,
                          "mean_gap": summary(synthetic(df.filter(pl.col("quarter") <= end), treated, donors, pre),
                                              pre, start, end)["mean_gap"]}
                         for name, (donors, pre, start, end) in specs.items()])
