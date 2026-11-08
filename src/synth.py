"""Synthetic control (Abadie, Diamond et Hainmueller, 2010) entre pays, sur la FBCF OCDE en base 100 = 2019.

Toutes les fonctions prennent l'indice large `oecd_gfcf_index2019_quarterly` (data/processed/) :
une colonne `quarter`, une colonne par pays. Le jumeau synthétique est une moyenne pondérée des donneurs,
avec des poids positifs de somme 1 choisis pour suivre le traité au mieux avant le traitement.
"""

from datetime import date

import numpy as np
import polars as pl
from scipy.optimize import minimize

from data_processing import TREATED_COUNTRY

PRE = (date(2015, 1, 1), date(2022, 4, 1))  # 2015-T1 → 2022-T2
START = date(2022, 7, 1)  # 2022-T3, trimestre des lois


def _donors(df: pl.DataFrame, treated: str, exclude: tuple[str, ...] = ()) -> list[str]:
    return [c for c in df.columns if c not in ("quarter", treated, *exclude)]


def weights(df: pl.DataFrame, treated: str = TREATED_COUNTRY, donors: list[str] | None = None,
            pre: tuple[date, date] = PRE) -> pl.DataFrame:
    """Poids w_j ≥ 0, Σ w_j = 1, qui minimisent l'écart quadratique moyen avant traitement entre le traité et Σ w_j Y_j."""
    donors = donors or _donors(df, treated)
    d = df.filter(pl.col("quarter").is_between(*pre))
    X, y = d.select(donors).to_numpy(), d[treated].to_numpy()
    n = len(donors)
    res = minimize(lambda w: np.mean((y - X @ w) ** 2), np.full(n, 1 / n), method="SLSQP", bounds=[(0, 1)] * n,
                   constraints={"type": "eq", "fun": lambda w: w.sum() - 1})
    return pl.DataFrame({"pays": donors, "poids": res.x}).sort("poids", descending=True)


def synthetic(df: pl.DataFrame, treated: str = TREATED_COUNTRY, donors: list[str] | None = None,
              pre: tuple[date, date] = PRE) -> pl.DataFrame:
    """Traité, jumeau synthétique et écart (traité − synthétique) à chaque trimestre."""
    w = weights(df, treated, donors, pre)
    synth = pl.sum_horizontal(pl.col(c) * v for c, v in w.iter_rows())
    return df.select("quarter", pl.col(treated).alias("traité"), synth.alias("synthétique")) \
        .with_columns((pl.col("traité") - pl.col("synthétique")).alias("écart"))


def summary(s: pl.DataFrame, pre: tuple[date, date] = PRE, start: date = START, end: date = date.max) -> dict:
    """RMSPE avant et après, leur ratio, écart moyen et écart au pic (en points d'indice) après `start`."""
    rmspe = lambda d: d.select((pl.col("écart") ** 2).mean().sqrt()).item()
    post = s.filter(pl.col("quarter").is_between(start, end))
    peak = post.sort(pl.col("écart").abs(), descending=True).row(0, named=True)
    before, after = rmspe(s.filter(pl.col("quarter").is_between(*pre))), rmspe(post)
    return {"rmspe_avant": before, "rmspe_après": after, "ratio": after / before, "écart_moyen": post["écart"].mean(),
            "écart_pic": peak["écart"], "trimestre_pic": f"{peak['quarter'].year}-T{(peak['quarter'].month - 1) // 3 + 1}"}


def space_placebos(df: pl.DataFrame, treated: str = TREATED_COUNTRY) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Placebos en espace (vrai traité exclu des donneurs) : écarts en format long et classement par ratio RMSPE."""
    gaps, rows = [], []
    for c in [treated, *_donors(df, treated)]:
        s = synthetic(df, c, _donors(df, c, exclude=(treated,)) if c != treated else None)
        gaps.append(s.filter(pl.col("quarter") >= PRE[0]).select(pl.lit(c).alias("pays"), "quarter", "écart"))
        rows.append({"pays": c, **{k: v for k, v in summary(s).items() if k.startswith(("rmspe", "ratio"))}})
    ratios = pl.DataFrame(rows).sort("ratio", descending=True).with_row_index("rang", offset=1)
    return pl.concat(gaps), ratios


def p_values(ratios: pl.DataFrame, treated: str = TREATED_COUNTRY, max_fit: float = 2) -> pl.DataFrame:
    """p-valeur de rang sur le ratio RMSPE, avec tous les pays puis sans ceux dont le RMSPE avant dépasse `max_fit` fois celui du traité."""
    t = ratios.filter(pl.col("pays") == treated).row(0, named=True)
    rows = [("Tous les pays", ratios),
            (f"RMSPE avant ≤ {max_fit:g} × USA", ratios.filter(pl.col("rmspe_avant") <= max_fit * t["rmspe_avant"]))]
    return pl.DataFrame([{"placebos": name, "pays": r.height, "rang_usa": (r["ratio"] >= t["ratio"]).sum(),
                          "p": (r["ratio"] >= t["ratio"]).mean()} for name, r in rows])


def robustness(df: pl.DataFrame, donor_fit: pl.DataFrame, n_best: int = 5, treated: str = TREATED_COUNTRY) -> pl.DataFrame:
    """Écart moyen après traitement (points d'indice) selon la spécification."""
    main = weights(df, treated)
    specs = {"Principale (2022-T3)": (None, PRE, START, date.max)}
    specs |= {f"Sans {c}": (_donors(df, treated, exclude=(c,)), PRE, START, date.max)
              for c in main.filter(pl.col("poids") > 0.01)["pays"]}
    specs |= {f"{n_best} donneurs les mieux corrélés": (donor_fit.head(n_best)["pays"].to_list(), PRE, START, date.max),
              "Traitement avancé à 2021-T3": (None, (PRE[0], date(2021, 4, 1)), date(2021, 7, 1), date.max),
              "Placebo dans le temps (2019-T1)": (None, (PRE[0], date(2018, 10, 1)), date(2019, 1, 1), date(2021, 10, 1))}
    return pl.DataFrame([{"spécification": name,
                          "écart_moyen": summary(synthetic(df.filter(pl.col("quarter") <= end), treated, donors, pre),
                                                 pre, start, end)["écart_moyen"]}
                         for name, (donors, pre, start, end) in specs.items()])
