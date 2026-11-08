"""Data loading and transformations for the IRA / CHIPS Act project.

Unless stated otherwise, all functions take and return wide polars DataFrames
(one date or quarter column, one column per series).
`python src/data_processing.py` writes the cleaned datasets as CSV to data/processed/.
"""

from datetime import date
from pathlib import Path

import polars as pl

DATA = Path(__file__).resolve().parents[1] / "data"
RAW, PROCESSED = DATA / "raw", DATA / "processed"

TREATMENT_DATE = date(2022, 8, 1)
TREATED_SECTOR = "mfg_computer_electronic_electrical"
TREATED_COUNTRY = "USA"
DEFLATOR = "WPUSI012011"  # construction materials prices
BASE_YEAR = 2019


# --- Helpers ----------------------------------------------------------------

def to_date(df: pl.DataFrame, x: str) -> pl.DataFrame:
    """Converts column x to pl.Date (accepts 'YYYY-MM-DD' or 'YYYY-Qn')."""
    if df.schema[x] in (pl.Date, pl.Datetime):
        return df.with_columns(pl.col(x).cast(pl.Date))
    s = pl.col(x)
    quarter = pl.date(s.str.slice(0, 4).cast(pl.Int32), (s.str.slice(-1).cast(pl.Int32) - 1) * 3 + 1, 1)
    return df.with_columns(
        pl.when(s.str.contains("Q")).then(quarter).otherwise(s.str.to_date("%Y-%m-%d", strict=False)).alias(x)
    )


def rebase(df: pl.DataFrame, x: str, cols: list[str], year: int = BASE_YEAR) -> pl.DataFrame:
    """Rebases each series to 100 = average of year `year`."""
    in_year = pl.col(x).dt.year() == year
    return df.with_columns(pl.col(c) / pl.col(c).filter(in_year).mean() * 100 for c in cols)


def mfg_sectors(census: pl.DataFrame) -> list[str]:
    """Census manufacturing subsectors (`mfg_*` columns)."""
    return [c for c in census.columns if c.startswith("mfg_")]


# --- Loading ----------------------------------------------------------------

def load_raw() -> dict[str, pl.DataFrame]:
    """The five raw files, dates converted to pl.Date."""
    return {
        "census": pl.read_csv(RAW / "census_private_construction_spending_monthly.csv", try_parse_dates=True),
        "fred": pl.read_csv(RAW / "fred_macro_industry_monthly.csv", try_parse_dates=True),
        "oecd": to_date(pl.read_csv(RAW / "oecd_gfcf_other_structures_quarterly.csv"), "quarter"),
        "cim_us": to_date(pl.read_csv(RAW / "cim_us_clean_investment_quarterly.csv", null_values=["NaN"]), "quarter"),
        "cim_state": pl.read_csv(RAW / "cim_state_investment_share_gdp.csv"),
    }


def overview(raw: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """One row per file: size, period covered and share of null cells."""
    rows = []
    for name, df in raw.items():
        x = next((c for c in ("date", "quarter") if c in df.columns), None)
        rows.append({
            "file": name, "rows": df.height, "columns": df.width,
            "start": str(df[x].min()) if x else "-", "end": str(df[x].max()) if x else "-",
            "% null": round(df.null_count().sum_horizontal().item() / (df.height * df.width) * 100, 1),
        })
    return pl.DataFrame(rows)


# --- Deflation --------------------------------------------------------------

def deflator(fred: pl.DataFrame) -> pl.DataFrame:
    """Materials price index, `BASE_YEAR` average = 1."""
    p = pl.col(DEFLATOR)
    return fred.select("date", (p / p.filter(pl.col("date").dt.year() == BASE_YEAR).mean()).alias("deflator"))


def real_fred(fred: pl.DataFrame) -> pl.DataFrame:
    """FRED with manufacturing construction in 2019 $M (`TLMFGCONS_real`)."""
    return fred.join(deflator(fred), on="date") \
        .with_columns((pl.col("TLMFGCONS") / pl.col("deflator")).alias("TLMFGCONS_real"))


def real_census(census: pl.DataFrame, fred: pl.DataFrame) -> pl.DataFrame:
    """Deflated Census (2019 $M, SAAR) for manufacturing subsectors, offices and commercial."""
    cols = [*mfg_sectors(census), "office", "commercial", "manufacturing"]
    return census.join(deflator(fred), on="date") \
        .with_columns(pl.col(c) / pl.col("deflator") for c in cols) \
        .drop("flag", "deflator")


# --- Cross-sector DiD -------------------------------------------------------

def did_panel(census_real: pl.DataFrame, treated: str = TREATED_SECTOR) -> pl.DataFrame:
    """Long sector × month panel, in logs, with treated / post dummies."""
    return census_real.select("date", *mfg_sectors(census_real), "office", "commercial") \
        .unpivot(index="date", variable_name="sector", value_name="spending_real") \
        .with_columns(
            pl.col("spending_real").log().alias("log_spending_real"),
            (pl.col("sector") == treated).alias("treated"),
            (pl.col("date") >= TREATMENT_DATE).alias("post"),
        )


# --- Cross-country Synthetic Control ---------------------------------------

def oecd_index(oecd: pl.DataFrame) -> pl.DataFrame:
    """OECD GFCF rebased to 100 = 2019 for each country."""
    return rebase(oecd, "quarter", [c for c in oecd.columns if c != "quarter"])


def donor_fit(oecd_idx: pl.DataFrame, treated: str = TREATED_COUNTRY,
              pre: tuple[date, date] = (date(2015, 1, 1), date(2022, 4, 1)),
              post_start: date = date(2024, 1, 1)) -> pl.DataFrame:
    """Per donor: correlation and RMSE with the treated unit over `pre`, average index from `post_start`."""
    donors = [c for c in oecd_idx.columns if c not in ("quarter", treated)]
    p = oecd_idx.filter(pl.col("quarter").is_between(*pre))
    post = oecd_idx.filter(pl.col("quarter") >= post_start)
    return pl.DataFrame([
        {"country": c,
         "corr_pre": p.select(pl.corr(treated, c)).item(),
         "rmse_pre": p.select(((pl.col(treated) - pl.col(c)) ** 2).mean().sqrt()).item(),
         "index_post": post[c].mean()}
        for c in donors
    ]).sort("corr_pre", descending=True).with_columns(pl.exclude("country").round(2))


# --- Clean Investment Monitor -----------------------------------------------

def cim_columns(cim_us: pl.DataFrame, kind: str = "actual") -> list[str]:
    """Manufacturing investment columns by technology: `kind` = 'actual' or 'announced'."""
    return [c for c in cim_us.columns if c.startswith(f"mfg_{kind}__")]


def cim_totals(cim_us: pl.DataFrame) -> pl.DataFrame:
    """Total clean tech manufacturing investment, announced and actual (2024 $bn per quarter)."""
    return cim_us.select("quarter", pl.sum_horizontal(cim_columns(cim_us, "announced")).alias("announced"),
                         pl.sum_horizontal(cim_columns(cim_us, "actual")).alias("actual"))


# --- Export -----------------------------------------------------------------

def load_processed() -> dict[str, pl.DataFrame]:
    """Files written by `main()` to data/processed/, key = file name, dates converted to pl.Date."""
    return {p.stem: pl.read_csv(p, try_parse_dates=True) for p in sorted(PROCESSED.glob("*.csv"))}


def main() -> None:
    raw = load_raw()
    census_real = real_census(raw["census"], raw["fred"])
    oecd_idx = oecd_index(raw["oecd"])
    outputs = {
        "census_construction_real_monthly": census_real,
        "did_panel_monthly": did_panel(census_real),
        "fred_monthly": real_fred(raw["fred"]),
        "oecd_gfcf_index2019_quarterly": oecd_idx,
        "oecd_donor_fit": donor_fit(oecd_idx),
        "cim_us_clean_investment_quarterly": raw["cim_us"],
        "cim_totals_quarterly": cim_totals(raw["cim_us"]),
        "cim_state_investment_share_gdp": raw["cim_state"],
    }
    PROCESSED.mkdir(exist_ok=True)
    for name, df in outputs.items():
        df.write_csv(PROCESSED / f"{name}.csv")
        print(f"{name}.csv : {df.height} rows")


if __name__ == "__main__":
    main()
