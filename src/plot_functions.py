"""Fonctions plotly du projet IRA / CHIPS Act.

Les graphes de l'EDA ramènent les séries à un point par année (`annual`). Chaque fonction prend un DataFrame polars
et renvoie une go.Figure, avec le même thème (`set_theme`).
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
    """Un point par année (moyenne ou somme), `partiel` pour une année incomplète, base 100 = `base_year` si donné."""
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


def plot_event_study(es: pl.DataFrame, ref: tuple[date, date], transition: tuple[date, date], title: str | None = None,
                     subtitle: str | None = None) -> go.Figure:
    """Event study par trimestre (avant, transition, après), avec bandes grisées pour `ref` et `transition`."""
    d = es.with_columns(pl.col("date").dt.offset_by("45d").alias("x"))  # point au milieu du trimestre
    fig = go.Figure()
    for (x0, x1), text, opacity in [(ref, "Référence", 0.06), (transition, "Transition", 0.12)]:
        fig.add_vrect(x0=x0, x1=pl.Series([x1]).dt.offset_by("1mo")[0], fillcolor=NEUTRAL, opacity=opacity, line_width=0,
                      annotation_text=text, annotation_position="top left", annotation_font=dict(size=11, color=MUTED))
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    periods = [("Avant", pl.col("date") < transition[0], NEUTRAL),
               ("Transition", pl.col("date").is_between(transition[0], transition[1], closed="left"), CONTROL),
               ("Après", pl.col("date") >= transition[1], TREATED)]
    for name, cond, color in periods:
        p = d.filter(cond)
        fig.add_scatter(x=p["x"], y=p["coef"], name=name, mode="markers", marker=dict(color=color, size=8),
                        customdata=p["trimestre"], hovertemplate="%{customdata} : %{y:.2f}<extra></extra>")
    _treatment(fig, x=TREATMENT_DATE)
    fig.update_xaxes(dtick="M12", tickformat="%Y")
    fig.update_layout(hovermode="closest")
    return _layout(fig, title, subtitle, "Écart de log vs référence")


def plot_placebos(placebos: pl.DataFrame, true: float, title: str | None = None, subtitle: str | None = None) -> go.Figure:
    """δ placebo par fausse date (colonnes date, delta) en gris, vrai δ en ligne orange avec la part des placebos ≥ vrai δ."""
    above = (placebos["delta"] >= true).sum()
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    fig.add_scatter(x=placebos["date"], y=placebos["delta"], name="DiD placebo", mode="markers",
                    marker=dict(color=CONTROL, size=7), hovertemplate="%{x|%m/%Y} : %{y:.2f}<extra></extra>")
    fig.add_hline(y=true, line=dict(color=TREATED, width=3), annotation_text=(
        f"Vrai δ = {true:.2f} · placebos ≥ vrai δ : {above} / {placebos.height}".replace(".", ",")),
        annotation_position="top left", annotation_font=dict(color=TREATED, size=12))
    fig.update_xaxes(dtick="M12", tickformat="%Y", title_text="Fausse date de traitement")
    fig.update_layout(hovermode="closest", showlegend=False)
    return _layout(fig, title, subtitle, "δ (écart de log)")


def plot_specs(df: pl.DataFrame, name: str, value: str, highlight: str, pct: bool = True, title: str | None = None,
               subtitle: str | None = None, xtitle: str | None = None) -> go.Figure:
    """Une barre horizontale par spécification, `highlight` en orange, valeurs en % si `pct`, sinon en unités."""
    fmt = (lambda v: f"{v:+.0%}".replace("%", " %")) if pct else (lambda v: f"{v:+.1f}".replace(".", ","))
    fig = go.Figure(go.Bar(x=df[value], y=df[name], orientation="h",
                           marker_color=[TREATED if c == highlight else CONTROL for c in df[name]],
                           text=[fmt(v) for v in df[value]], textposition="outside",
                           hovertemplate="%{y} : %{x:" + (".0%" if pct else ".1f") + "}<extra></extra>"))
    lo, hi = min(df[value].min(), 0), df[value].max()
    fig.update_xaxes(tickmode="auto", tickformat=".0%" if pct else "", showgrid=True, title_text=xtitle,
                     range=[lo - 0.18 * (hi - lo) if lo < 0 else 0, hi * 1.18])
    fig.add_vline(x=0, line=dict(color=MUTED, width=1))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_layout(height=50 * df.height + 200, hovermode="closest")
    return _layout(fig, title, subtitle, None)


def plot_synth(s: pl.DataFrame, treated: str = "USA", title: str | None = None, subtitle: str | None = None) -> go.Figure:
    """Traité (orange) et jumeau synthétique (pointillé bleu nuit) par trimestre, colonnes quarter, traité, synthétique."""
    fig = go.Figure()
    for col, name, color, dash in [("synthétique", f"{treated} synthétique", NEUTRAL, "dash"), ("traité", treated, TREATED, None)]:
        fig.add_scatter(x=s["quarter"], y=s[col], name=name, mode="lines", line=dict(color=color, width=2.5, dash=dash),
                        hovertemplate=f"{name} : %{{y:.1f}}<extra></extra>")
    _treatment(fig, x=TREATMENT_DATE)
    fig.update_xaxes(dtick="M12", tickformat="%Y")
    return _layout(fig, title, subtitle, "Base 100 = 2019")


def plot_gaps(gaps: pl.DataFrame, treated: str = "USA", title: str | None = None, subtitle: str | None = None) -> go.Figure:
    """Écart traité − synthétique par trimestre : traité en orange, placebos (colonne `pays`, si présente) en gris."""
    if "pays" not in gaps.columns:
        gaps = gaps.with_columns(pl.lit(treated).alias("pays"))
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    for (c,), d in sorted(gaps.group_by("pays"), key=lambda g: g[0][0] == treated):
        t = c == treated
        fig.add_scatter(x=d["quarter"], y=d["écart"], name=treated if t else "Placebos", mode="lines",
                        line=dict(color=TREATED if t else CONTROL, width=3 if t else 1), opacity=1 if t else 0.7,
                        legendgroup=c if t else "placebos", showlegend=t or c == gaps["pays"].unique().sort()[0],
                        hovertemplate=f"{c} : %{{y:.1f}}<extra></extra>")
    _treatment(fig, x=TREATMENT_DATE)
    fig.update_xaxes(dtick="M12", tickformat="%Y")
    fig.update_layout(hovermode="closest")
    return _layout(fig, title, subtitle, "Écart (points d'indice)")
