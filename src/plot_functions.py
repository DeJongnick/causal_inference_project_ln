"""Fonctions plotly de l'EDA du projet IRA / CHIPS Act.

Toutes les séries sont ramenées à un point par année (`annual`), pour des graphes lisibles d'un coup d'œil.
Chaque fonction prend un DataFrame polars au format large (une colonne date ou trimestre, une colonne par série)
et renvoie une go.Figure.
"""

from datetime import date

import plotly.graph_objects as go
import plotly.io as pio
import polars as pl
from plotly.subplots import make_subplots

from data_processing import TREATMENT_DATE, to_date

TREATED = "#eb6834"  # groupe traité
CONTROL = "#b8b8b8"  # contrôles
NEUTRAL = "#1b2a41"  # séries neutres (bleu nuit)
COLORWAY = [NEUTRAL, TREATED, "#2a78d6", "#1baf7a", "#eda100", "#6250d6"]
INK, MUTED = "#222", "#6b6b6b"

# Libellés lisibles des codes FRED et des colonnes au nom peu parlant
LABELS = {
    "TLMFGCONS": "Nominal",
    "TLMFGCONS_real": "Réel (dollars 2019)",
    "FEDFUNDS": "Fed funds (%)",
    "GS10": "Taux 10 ans (%)",
    "WPUSI012011": "Prix des matériaux",
    "IPG3344S": "Production semi-conducteurs",
    "CES3133440001": "Emploi semi-conducteurs",
    "mfg_computer_electronic_electrical": "Électronique / électrique",
    "mfg_food_bev_tobacco": "Agroalimentaire",
    "mfg_chemical": "Chimie",
    "mfg_plastic_rubber": "Plastique / caoutchouc",
    "mfg_nonmetallic_mineral": "Minéraux non métalliques",
    "mfg_fabricated_metal": "Produits métalliques",
    "mfg_transportation_equipment": "Équipement de transport",
    "controls": "Autres sous-secteurs (moyenne)",
}


def set_theme() -> None:
    """Template sobre : fond blanc, grille légère, légende horizontale en haut."""
    axis = dict(showgrid=True, gridcolor="#ececec", zeroline=False, linecolor="#9a9a9a", title_standoff=8)
    pio.templates["causal"] = go.layout.Template(layout=dict(
        font=dict(family="Inter, Helvetica, Arial, sans-serif", size=13, color=INK),
        title=dict(x=0, xref="container", xanchor="left", pad=dict(l=8), font=dict(size=17)),
        paper_bgcolor="white", plot_bgcolor="white", colorway=COLORWAY,
        xaxis=dict(axis, dtick=1, tickangle=0, showgrid=False), yaxis=axis,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0, title_text=""),
        hovermode="x unified", separators=", ",  # décimale française, espace pour les milliers
        margin=dict(l=60, r=30, t=120, b=40), height=470,
    ))
    pio.templates.default = "plotly_white+causal"


def label(col: str) -> str:
    """Nom de colonne lisible : 'mfg_chemical' -> 'Chimie', 'FEDFUNDS' -> 'Fed funds (%)'."""
    return LABELS.get(col, col.replace("_", " ").capitalize() if not col.isupper() else col)


def annual(df: pl.DataFrame, x: str, cols: list[str], how: str = "mean", base_year: int | None = None) -> pl.DataFrame:
    """Un point par année : moyenne (niveaux, taux, indices) ou somme (flux trimestriels).

    La colonne `partiel` signale une année incomplète ; en somme elle est retirée pour ne pas fausser le total.
    `base_year` : chaque série en base 100 = cette année.
    """
    d = to_date(df, x).with_columns(pl.col(x).dt.year().alias("année"))
    agg = pl.col(cols).mean() if how == "mean" else pl.col(cols).sum()
    d = d.group_by("année").agg(agg, pl.len().alias("n")).sort("année")
    d = d.with_columns((pl.col("n") < pl.col("n").max()).alias("partiel")).drop("n")
    if how == "sum":
        d = d.filter(~pl.col("partiel"))
    if base_year:
        d = d.with_columns(pl.col(c) / pl.col(c).filter(pl.col("année") == base_year).first() * 100 for c in cols)
    return d


def _line(fig: go.Figure, d: pl.DataFrame, series: str, name: str, color: str, width: float = 2.5,
          dash: str | None = None, **kw) -> None:
    """Courbe annuelle avec marqueurs ; l'année partielle a un marqueur creux."""
    symbols = ["circle-open" if p else "circle" for p in d["partiel"]]
    fig.add_scatter(x=d["année"], y=d[series], name=name, mode="lines+markers",
                    line=dict(color=color, width=width, dash=dash),
                    marker=dict(size=7, symbol=symbols, color=color, line=dict(color=color, width=1.5)),
                    hovertemplate=f"{name} : %{{y:,.0f}}<extra></extra>", **kw)


def _treatment(fig: go.Figure, x=TREATMENT_DATE.year, **ref) -> None:
    """Trait vertical au traitement (CHIPS / IRA, août 2022) : l'année par défaut, `x=TREATMENT_DATE` sur un axe de dates."""
    fig.add_vline(x=x, line=dict(color=MUTED, width=1, dash="dot"), **ref)
    if not ref:
        fig.add_annotation(x=x, y=1, yref="paper", text="CHIPS / IRA", showarrow=False,
                           xanchor="center", yanchor="bottom", font=dict(size=11, color=MUTED))


def _layout(fig: go.Figure, title: str | None, subtitle: str | None, ytitle: str | None) -> go.Figure:
    fig.update_layout(title=dict(text=title, subtitle=dict(text=subtitle)), yaxis_title=ytitle)
    return fig


def plot_years(df: pl.DataFrame, x: str, cols: list[str], how: str = "mean", base_year: int | None = None,
               scale: float = 1, title: str | None = None, subtitle: str | None = None,
               ytitle: str | None = None) -> go.Figure:
    """Une courbe annuelle par série. `scale` divise les valeurs (ex. 1000 pour passer de M$ à Md$)."""
    d = annual(df, x, cols, how, base_year).with_columns(pl.col(cols) / scale)
    fig = go.Figure()
    for i, c in enumerate(cols):
        _line(fig, d, c, label(c), COLORWAY[i % len(COLORWAY)])
    _treatment(fig)
    fig.update_layout(showlegend=len(cols) > 1)
    return _layout(fig, title, subtitle, ytitle or (f"Base 100 = {base_year}" if base_year else None))


def plot_treated_vs_controls(df: pl.DataFrame, x: str, treated: str, controls: list[str], base_year: int = 2019,
                             title: str | None = None, subtitle: str | None = None) -> go.Figure:
    """Série traitée (orange) contre la moyenne des contrôles (gris), en base 100."""
    d = annual(df, x, [treated, *controls], base_year=base_year)
    d = d.with_columns(pl.mean_horizontal(controls).alias("controls"))
    fig = go.Figure()
    _line(fig, d, "controls", label("controls"), CONTROL)
    _line(fig, d, treated, label(treated), TREATED, width=3)
    _treatment(fig)
    return _layout(fig, title, subtitle, f"Base 100 = {base_year}")


def plot_small_multiples(df: pl.DataFrame, x: str, cols: list[str], how: str = "mean", base_year: int | None = None,
                         highlight: str | None = None, ncols: int = 3, title: str | None = None,
                         subtitle: str | None = None) -> go.Figure:
    """Un petit graphe annuel par série, chacun avec sa propre échelle."""
    d = annual(df, x, cols, how, base_year)
    nrows = -(-len(cols) // ncols)
    fig = make_subplots(rows=nrows, cols=ncols, subplot_titles=[label(c) for c in cols], shared_xaxes=True,
                        vertical_spacing=0.12, horizontal_spacing=0.07)
    fig.update_annotations(font_size=13)
    for i, c in enumerate(cols):
        ref = dict(row=i // ncols + 1, col=i % ncols + 1)
        _line(fig, d, c, label(c), TREATED if c == highlight else NEUTRAL, width=2, showlegend=False, **ref)
        _treatment(fig, **ref)
    fig.update_xaxes(dtick=4, showticklabels=True)
    fig.update_layout(height=240 * nrows + 90, hovermode="closest")
    return _layout(fig, title, subtitle, None)


def plot_spaghetti(df: pl.DataFrame, x: str, treated: str = "USA", base_year: int = 2019,
                   title: str | None = None, subtitle: str | None = None) -> go.Figure:
    """Pays traité en orange, autres pays en gris fin et leur médiane en pointillé, en base 100."""
    donors = [c for c in df.columns if c not in (x, treated)]
    d = annual(df, x, [treated, *donors], base_year=base_year)
    d = d.with_columns(pl.concat_list(donors).list.median().alias("median"))
    fig = go.Figure()
    for c in donors:
        fig.add_scatter(x=d["année"], y=d[c], name=c, mode="lines", line=dict(color=CONTROL, width=1),
                        opacity=0.6, showlegend=False, hovertemplate=f"{c} : %{{y:.0f}}<extra></extra>")
    _line(fig, d, "median", "Médiane des autres pays", NEUTRAL, width=2, dash="dash")
    _line(fig, d, treated, treated, TREATED, width=3)
    _treatment(fig)
    fig.update_layout(hovermode="closest")
    return _layout(fig, title, subtitle, f"Base 100 = {base_year}")


def plot_monthly(df: pl.DataFrame, x: str, cols: list[str], start: date, end: date, highlight: str | None = None,
                 scale: float = 1, title: str | None = None, subtitle: str | None = None,
                 ytitle: str | None = None) -> go.Figure:
    """Séries mensuelles sur [start, end], traitement à août 2022. `highlight` en orange, `controls` en gris."""
    d = to_date(df, x).filter(pl.col(x).is_between(start, end)).sort(x).with_columns(pl.col(cols) / scale)
    fig = go.Figure()
    for i, c in enumerate(cols):
        color = TREATED if c == highlight else CONTROL if c == "controls" else COLORWAY[i % len(COLORWAY)]
        fig.add_scatter(x=d[x], y=d[c], name=label(c), mode="lines", line=dict(color=color, width=3 if c == highlight else 2),
                        hovertemplate=f"{label(c)} : %{{y:,.0f}}<extra></extra>")
    _treatment(fig, x=TREATMENT_DATE)
    fig.update_xaxes(dtick="M6", tickformat="%m/%Y")
    return _layout(fig, title, subtitle, ytitle)


def plot_ranking(df: pl.DataFrame, name: str, value: str, n: int = 15, title: str | None = None,
                 subtitle: str | None = None, xtitle: str | None = None) -> go.Figure:
    """Top `n` de `value` en barres horizontales, le premier en haut."""
    d = df.sort(value, descending=True).head(n)
    fig = go.Figure(go.Bar(x=d[value], y=d[name], orientation="h", marker_color=NEUTRAL,
                           hovertemplate="%{y} : %{x:.2f}<extra></extra>"))
    fig.update_xaxes(tickmode="auto", showgrid=True, title_text=xtitle)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_layout(height=30 * n + 160, hovermode="closest")
    return _layout(fig, title, subtitle, None)
