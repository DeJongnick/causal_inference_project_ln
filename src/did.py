"""Difference-in-Differences entre secteurs sur le panel secteur × mois.

Toutes les fonctions prennent le panel long `did_panel_monthly` (data/processed/) : une ligne par secteur × mois.
Le DiD compare une fenêtre `before` et une fenêtre `after` ; les mois entre les deux (la transition) sont exclus.
"""

import math
from datetime import date

import polars as pl
import statsmodels.formula.api as smf

from data_processing import TREATED_SECTOR, TREATMENT_DATE

Y = "log_spending_real"
BEFORE = (date(2019, 7, 1), date(2021, 6, 1))  # écart traité − contrôles à peu près stable
TRANSITION = (date(2021, 7, 1), date(2022, 7, 1))  # hausse avant les lois : anticipation ou pénurie de puces
AFTER = (TREATMENT_DATE, date.max)
TRANSPORT = "mfg_transportation_equipment"


def _months(d: date) -> int:
    return d.year * 12 + d.month - 1


def _shift(d: date, months: int) -> date:
    m = _months(d) + months
    return date(m // 12, m % 12 + 1, 1)


def _periods(panel: pl.DataFrame, before: tuple[date, date], after: tuple[date, date], treated: str) -> pl.DataFrame:
    """Mois des deux fenêtres seulement, avec A_s (`treated`), Post_t (`post`) et T_st = A_s × Post_t (`T`)."""
    return panel.filter(pl.col("date").is_between(*before) | pl.col("date").is_between(*after)) \
        .with_columns((pl.col("sector") == treated).alias("treated"), (pl.col("date") >= after[0]).alias("post")) \
        .with_columns((pl.col("treated") & pl.col("post")).cast(pl.Int8).alias("T"))


def cell_means(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER,
               treated: str = TREATED_SECTOR) -> pl.DataFrame:
    """Tableau 2×2 : moyenne de y par groupe et par période, variation de chaque ligne et écart traité − contrôles."""
    m = {(a, p): v for a, p, v in
         _periods(panel, before, after, treated).group_by("treated", "post").agg(pl.col(y).mean()).iter_rows()}
    rows = [("Traité", m[True, False], m[True, True]), ("Contrôles", m[False, False], m[False, True])]
    rows.append(("Écart traité − contrôles", rows[0][1] - rows[1][1], rows[0][2] - rows[1][2]))
    return pl.DataFrame(rows, schema=["groupe", "avant", "après"], orient="row") \
        .with_columns((pl.col("après") - pl.col("avant")).alias("variation"))


def did_2x2(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER,
            treated: str = TREATED_SECTOR) -> float:
    """Double différence : variation de l'écart, la case en bas à droite de `cell_means`."""
    return cell_means(panel, y, before, after, treated)["variation"][-1]


def effect(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER) -> float:
    """Effet en % : exp(δ) − 1 en log ; en niveaux, δ rapporté au contrefactuel du traité (avant + variation des contrôles)."""
    m = cell_means(panel, y, before, after)
    if y == Y:
        return math.exp(m["variation"][-1]) - 1
    return m["variation"][-1] / (m["avant"][0] + m["variation"][1])


def twfe(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER) -> dict:
    """Y_st = α_s + λ_t + δ T_st + ε_st sur les deux fenêtres, erreur standard clusterisée par secteur."""
    d = _periods(panel, before, after, TREATED_SECTOR).with_columns(pl.col("date").cast(pl.String))
    fit = smf.ols(f"{y} ~ T + C(sector) + C(date)", data={c: d[c].to_numpy() for c in d.columns}) \
        .fit(cov_type="cluster", cov_kwds={"groups": d["sector"].rank("dense").to_numpy()})
    return {"delta": float(fit.params["T"]), "se_cluster": float(fit.bse["T"])}


def readings(panel: pl.DataFrame) -> pl.DataFrame:
    """Fourchette de l'effet : borne haute (référence = plateau) et borne basse (référence = transition)."""
    rows = [("Borne haute : anticipation", BEFORE), ("Borne basse : pénurie de puces", TRANSITION)]
    return pl.DataFrame([{"lecture": name, "avant": f"{before[0]:%Y-%m} → {before[1]:%Y-%m}",
                          "delta": did_2x2(panel, before=before), "effet": effect(panel, before=before)}
                         for name, before in rows])


def dollars(panel: pl.DataFrame) -> pl.DataFrame:
    """Effet moyen en Md$ de 2019 par an : dépense moyenne du traité après (M$ SAAR / 1 000) moins dépense / exp(δ)."""
    spent = panel.filter((pl.col("sector") == TREATED_SECTOR) & pl.col("date").is_between(*AFTER))["spending_real"].mean()
    return readings(panel).select(pl.col("lecture").alias("borne"), "effet",
                                  (spent * (1 - (-pl.col("delta")).exp()) / 1000).alias("md_par_an"))


def event_study(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, treated: str = TREATED_SECTOR,
                start: date = date(2015, 1, 1)) -> pl.DataFrame:
    """Event study : écart traité − contrôles par trimestre moins l'écart moyen de `before` (un DiD 2×2 par trimestre)."""
    a = pl.col("sector") == treated
    gap = panel.filter(pl.col("date") >= start).group_by("date").agg((pl.col(y).filter(a).mean() - pl.col(y).filter(~a).mean()).alias("gap"))
    ref = gap.filter(pl.col("date").is_between(*before))["gap"].mean()
    return gap.group_by(pl.col("date").dt.truncate("1q")).agg((pl.col("gap").mean() - ref).alias("coef")).sort("date") \
        .with_columns(pl.format("{}-T{}", pl.col("date").dt.year(), pl.col("date").dt.quarter()).alias("trimestre"))


def dynamics(es: pl.DataFrame) -> pl.DataFrame:
    """Premier trimestre après le traitement, pic et dernier trimestre observé, en écart de log et en %."""
    post = es.filter(pl.col("date") >= date(TREATMENT_DATE.year, (TREATMENT_DATE.month - 1) // 3 * 3 + 1, 1))
    return pl.concat([post.head(1).with_columns(pl.lit("Premier trimestre").alias("moment")),
                      post.top_k(1, by="coef").with_columns(pl.lit("Pic").alias("moment")),
                      post.tail(1).with_columns(pl.lit("Dernier trimestre").alias("moment"))]) \
        .select("moment", "trimestre", "coef", (pl.col("coef").exp() - 1).alias("effet"))


def time_placebos(panel: pl.DataFrame, y: str = Y, before: tuple[date, date] = BEFORE, after: tuple[date, date] = AFTER,
                  last: date = TRANSITION[0]) -> pl.DataFrame:
    """Même DiD 2×2, mêmes longueurs de fenêtres, sur toutes les fausses dates dont les fenêtres tiennent avant `last`."""
    t, start = after[0], panel["date"].min()
    b0, b1 = _months(before[0]) - _months(t), _months(before[1]) - _months(t)
    a1 = _months(min(after[1], panel["date"].max())) - _months(t)
    rows, f = [], _shift(start, -b0)
    while _shift(f, a1) < last:
        rows.append({"date": f, "delta": did_2x2(panel, y, (_shift(f, b0), _shift(f, b1)), (f, _shift(f, a1)))})
        f = _shift(f, 1)
    return pl.DataFrame(rows)


def permutation(panel: pl.DataFrame, y: str = Y) -> pl.DataFrame:
    """Test de permutation : δ recalculé en traitant chaque secteur tour à tour, p = part des |δ| ≥ |δ du traité|."""
    deltas = {s: did_2x2(panel, y, treated=s) for s in panel["sector"].unique()}
    true = deltas[TREATED_SECTOR]
    placebo = [d for s, d in deltas.items() if s != TREATED_SECTOR]
    return pl.DataFrame([{"delta_vrai": true, "placebo_min": min(placebo), "placebo_max": max(placebo),
                          "p": sum(abs(d) >= abs(true) for d in deltas.values()) / len(deltas)}])


def robustness(panel: pl.DataFrame) -> pl.DataFrame:
    """Effet en % selon la spécification ; `panel` contient aussi bureaux et commerces."""
    mfg = panel.filter(pl.col("sector").str.starts_with("mfg_"))
    return pl.DataFrame({"spécification": ["Principale (hors transition)", "Sans équipement de transport",
                                           "Contrôles + bureaux et commerces", "Outcome en niveaux",
                                           "Fenêtre avant 2015-01 → 2022-07"],
                         "effet": [effect(mfg), effect(mfg.filter(pl.col("sector") != TRANSPORT)), effect(panel),
                                   effect(mfg, y="spending_real"),
                                   effect(mfg, before=(date(2015, 1, 1), _shift(TREATMENT_DATE, -1)))]})
