"""
markets.py - hourly wholesale electricity prices used as the opportunity cost of surplus energy and
as the cost of grid backup. All series are observed hourly day-ahead (or equivalent) prices:

  United States  seven ISO/RTOs, 2017-2021, COVID-EMDA+ data hub (Ruan et al., Joule 2020);
                 ERCOT hub-average day-ahead settlement point prices 2020-2026 (ERCOT report
                 NP4-180-ER 'DAM Settlement Point Prices'), which continue the data-hub series
  Brazil         hourly spot price (PLD) of the SE/CO and NE submarkets, 2021-2026 (CCEE)
  Europe         hourly day-ahead prices by country, 2015-2026 (Ember, European wholesale
                 electricity price data)

Prices are converted to US dollars at the average exchange rate of the year and escalated to
constant 2025 USD with the US consumer price index. Each market-year is an array of 8,760 hourly
values in local standard time. The label '2026' denotes the twelve months from November 2025 to
October 2026 (the latest complete twelve months available when the data were retrieved).
"""
import os
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw")
H = 8760

# US CPI-U, annual averages (BLS). No index was published for October 2025; the 2025 average
# interpolates that month. '2026' = average of November 2025 - October 2026.
CPI = {2015: 237.02, 2016: 240.01, 2017: 245.12, 2018: 251.11, 2019: 255.66, 2020: 258.81, 2021: 270.97,
       2022: 292.66, 2023: 304.70, 2024: 313.69, 2025: 322.2, 2026: 331.3}
# Exchange rates, annual averages of daily rates (Federal Reserve H.10); '2026' as above.
USD_PER_EUR = {2015: 1.1096, 2016: 1.1072, 2017: 1.1301, 2018: 1.1817, 2019: 1.1194, 2020: 1.1410, 2021: 1.1830,
               2022: 1.0534, 2023: 1.0817, 2024: 1.0820, 2025: 1.1306, 2026: 1.1584}
BRL_PER_USD = {2021: 5.3958, 2022: 5.1605, 2023: 4.9946, 2024: 5.3872, 2025: 5.5891, 2026: 5.1862}
BASE_YEAR = 2025
ROLLING = ("2025-11-01", "2026-10-31 23:00")      # the twelve months labelled '2026'
MIN_COVERAGE = 0.99


def to_base(year):
    return CPI[BASE_YEAR] / CPI[int(year)]


# ----------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------
def _window(s, start, end):
    """8,760 hourly values of series s between start and end, or None if coverage is insufficient.
    Gaps of up to six hours are interpolated, longer gaps take the preceding value."""
    full = pd.date_range(start, end, freq="h")
    v = s.reindex(full)
    if v.notna().sum() < MIN_COVERAGE * min(len(full), H):
        return None
    v = v.interpolate(limit=6).ffill().bfill().values[:H]
    if len(v) < H:
        v = np.concatenate([v, np.full(H - len(v), v[-1])])
    return v


def _years(s, years, rolling=True):
    out = {}
    for y in years:
        v = _window(s, f"{y}-01-01", f"{y}-12-31 23:00")
        if v is not None:
            out[str(y)] = v
    if rolling:
        v = _window(s, *ROLLING)
        if v is not None:
            out["2026"] = v
    return out


# ----------------------------------------------------------------------------------------------
# United States
# ----------------------------------------------------------------------------------------------
US_ISOS = ["ercot", "pjm", "caiso", "miso", "nyiso", "isone", "spp"]


def _load_emda(iso):
    d = pd.read_csv(os.path.join(RAW, f"emda_{iso}_lmp.csv"), parse_dates=["date"]).set_index("date")
    d = d[~d.index.duplicated(keep="first")]
    s = d.stack()
    idx = [pd.Timestamp(a) + pd.Timedelta(hours=int(b[:2])) for a, b in s.index]
    s = pd.Series(s.values, index=pd.DatetimeIndex(idx)).sort_index()
    full = pd.date_range(s.index[0], s.index[-1], freq="h")
    s = s.reindex(full).interpolate(limit=6).ffill().bfill()
    return s


def us_market_years(iso):
    """{label: 8760-array in 2025 USD/MWh} from the COVID-EMDA+ hub. Years 2017-2020 are calendar
    years; '2021' is December 2020 - November 2021 (the hub ends on 30 November 2021)."""
    s = _load_emda(iso)
    out = {}
    for y in (2017, 2018, 2019, 2020):
        v = s[s.index.year == y].values
        v = v[:H]
        if len(v) < H:
            v = np.concatenate([v, np.full(H - len(v), np.nanmedian(v))])
        out[str(y)] = v * to_base(y)
    v = s["2020-12-01":"2021-11-30"].values[:H]
    out["2021"] = v * to_base(2021)
    return out


def ercot_market_years(point="HB_HUBAVG"):
    """ERCOT: data-hub series for 2017-2019 (identical to the hub-average day-ahead price), official
    day-ahead settlement point prices for calendar years 2020-2025 and for '2026'."""
    out = {y: v for y, v in us_market_years("ercot").items() if y in ("2017", "2018", "2019")}
    d = pd.read_csv(os.path.join(RAW, "ercot_dam_hourly.csv.gz"), index_col=0, parse_dates=True)[point]
    for y, v in _years(d, range(2020, 2026)).items():
        out[y] = v * to_base(y)
    return out


# ----------------------------------------------------------------------------------------------
# Brazil
# ----------------------------------------------------------------------------------------------
def brazil_market_years(sub="SE_CO"):
    d = pd.read_csv(os.path.join(RAW, "ccee_pld_hourly.csv.gz"), index_col=0, parse_dates=True)[sub]
    return {y: v / BRL_PER_USD[int(y)] * to_base(y) for y, v in _years(d, range(2021, 2026)).items()}


# ----------------------------------------------------------------------------------------------
# Europe
# ----------------------------------------------------------------------------------------------
UTC_OFFSET = {"Ireland": 0, "Portugal": 0, "United Kingdom": 0,
              "Bulgaria": 2, "Estonia": 2, "Finland": 2, "Greece": 2, "Latvia": 2, "Lithuania": 2, "Romania": 2}
EUROPE_EXCLUDE = ("Luxembourg",)        # same bidding zone as Germany


def europe_market_years():
    w = pd.read_csv(os.path.join(RAW, "ember_europe_hourly.csv.gz"), index_col=0, parse_dates=True)
    out = {}
    for c in w.columns:
        if c in EUROPE_EXCLUDE:
            continue
        s = w[c].dropna()
        s.index = s.index + pd.Timedelta(hours=UTC_OFFSET.get(c, 1))      # local standard time
        yrs = {y: v * USD_PER_EUR[int(y)] * to_base(y) for y, v in _years(s, range(2015, 2026)).items()}
        if yrs:
            out[c] = yrs
    return out


# ----------------------------------------------------------------------------------------------
def all_markets():
    """dict market -> dict year-label -> 8760 array (2025 USD/MWh)."""
    mk = {"ERCOT": ercot_market_years()}
    for iso in US_ISOS[1:]:
        mk[iso.upper()] = us_market_years(iso)
    mk["Brazil SE/CO"] = brazil_market_years("SE_CO")
    mk["Brazil NE"] = brazil_market_years("NE")
    mk.update(europe_market_years())
    return mk


US_MARKETS = [i.upper() for i in US_ISOS]


def region(market):
    return "United States" if market in US_MARKETS else ("Brazil" if market.startswith("Brazil") else "Europe")


def describe(p):
    return dict(mean=float(np.mean(p)), median=float(np.median(p)), p05=float(np.quantile(p, .05)),
                p95=float(np.quantile(p, .95)), max=float(np.max(p)), neg_hours=int((p < 0).sum()),
                sd=float(np.std(p)))


if __name__ == "__main__":
    mk = all_markets()
    rows = []
    for m, yrs in mk.items():
        for y, p in yrs.items():
            rows.append(dict(market=m, region=region(m), year=y, **describe(p)))
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(df.groupby("region").size().to_dict(), len(df), "market-years in", df.market.nunique(), "markets")
    print(df[df.region != "Europe"].round(1).to_string(index=False))
    df.to_csv(os.path.join(HERE, "..", "results", "market_stats.csv"), index=False)
