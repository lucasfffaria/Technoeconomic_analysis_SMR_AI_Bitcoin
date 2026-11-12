"""export_figure_data.py - series derived from the raw data or from the model that are shown in the figures
of the article and of the Supplementary Material; they are written to ../results:

  hashprice_frontier.csv         hashprice and frontier netback (Fig. 2, Fig. S2; also used by facts.py)
  fig04_dispatch_series.csv      twelve days of hourly dispatch of the iPWR plant (Fig. 4)
  figS1_price_series.csv         hourly prices of the market-years shown as duration curves (Fig. S1)
  figS3_availability_shares.csv  distribution of available capacity in the base-case record (Fig. S3a)
  figS3_ai_load.csv              two weeks of the AI campus load (Fig. S3b)
"""
import os
import numpy as np
import pandas as pd
from common import *


def hashprice_frontier():
    d = pd.read_csv(os.path.join(HERE, "..", "data", "raw", "btc_coinmetrics.csv"), low_memory=False,
                    parse_dates=["time"]).set_index("time")
    d["rev"] = d["IssTotUSD"] + d["FeeTotNtv"] * d["PriceUSD"]
    hp = (d["rev"] / d["HashRate"] * 1000).loc["2016-01-01":"2026-05-23"].rolling(7, min_periods=1).mean()
    front = [("2016-06-01", 98.0, "S9"), ("2018-11-01", 57.0, "S15"), ("2019-04-01", 39.5, "S17 Pro"),
             ("2020-05-01", 29.5, "S19 Pro"), ("2022-07-01", 21.5, "S19 XP"), ("2024-01-01", 17.5, "S21"),
             ("2024-09-01", 13.5, "S21 XP"), ("2026-01-01", 9.5, "S23 Hyd")]
    eta = pd.Series(np.nan, index=hp.index)
    for dt, e, _ in front:
        eta.loc[dt:] = e
    R = (hp / (0.024 * eta)).dropna()
    pd.DataFrame({"hashprice": hp, "eta_frontier": eta, "frontier_netback": R}).to_csv(
        os.path.join(RES, "hashprice_frontier.csv"))
    print("hashprice_frontier.csv:", len(hp), "days; median frontier netback since 2020:", round(R.loc["2020":].median(), 1))


def dispatch_example(year="2023", netback_mean=95.0):
    """Twelve summer days with daily price spikes and one forced module outage (iPWR, ERCOT prices)."""
    tech = ipwr()
    rng = np.random.default_rng(5)
    E, MI = Econ(), Mining()
    price = MK["ERCOT"][year]
    for _ in range(50):
        avail = availability(tech, rng)
        ell = ai_profile(rng)
        ok = None
        for start in range(190 * 24, 235 * 24, 24):
            w = slice(start, start + 12 * 24)
            if 180 <= (avail[w] < 300).sum() <= 200 and avail[w].min() == 225 and price[w].max() > 400:
                ok = start
                break
        if ok is not None:
            break
    start = ok if ok is not None else 200 * 24
    w = slice(start, start + 12 * 24)
    intra = intra_year_profile(rng)
    nu = netback_mean * intra
    load = 225 * ell
    sA = dispatch(avail, load, price, np.zeros(H), 0.0, 0.0, 0.0, tech.c_var, E, series=True)
    sC = dispatch(avail, load, price, nu, 110 * MI.uptime, tech.cap, 0.0, tech.c_var, E, series=True)
    t0 = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(hours=start)
    out = pd.DataFrame({
        "time": pd.date_range(t0, periods=12 * 24, freq="h"), "day": np.arange(12 * 24) / 24.0,
        "available_MW": avail[w], "A_ai_MW": sA["gen_ai"][w], "A_unused_MW": sA["curtailed"][w],
        "C_ai_MW": sC["gen_ai"][w], "C_mining_MW": sC["mine"][w], "C_export_MW": sC["export"][w],
        "net_export_price": price[w] - E.tau_x, "mining_netback": nu[w], "nuclear_marginal_cost": tech.c_var,
        "mining_netback_annual_mean": netback_mean})
    out.to_csv(os.path.join(RES, "fig04_dispatch_series.csv"), index=False)
    print("fig04_dispatch_series.csv:", t0, "to", out["time"].iloc[-1], "| max price", round(price[w].max()),
          "| netback in window", round(nu[w].min(), 1), "-", round(nu[w].max(), 1))


def price_duration():
    cols = {f"ERCOT {y}": MK["ERCOT"][y] for y in ("2021", "2022", "2023", "2024", "2025")}
    cols.update({"PJM 2019": MK["PJM"]["2019"], "Brazil SE/CO 2024": MK["Brazil SE/CO"]["2024"],
                 "Brazil SE/CO 2025": MK["Brazil SE/CO"]["2025"], "Germany 2025": MK["Germany"]["2025"],
                 "Finland 2024": MK["Finland"]["2024"]})
    pd.DataFrame(cols).round(3).to_csv(os.path.join(RES, "figS1_price_series.csv"), index=False)
    print("figS1_price_series.csv:", list(cols))


def availability_load():
    lv = np.array([0, 75, 150, 225, 300])
    sh = {"available_MW": lv}
    for tech in (ipwr(), fhr()):
        hr = hourly_record(tech)
        sh[tech.name] = np.array([(hr["avail"] == v).mean() for v in lv]) * 100
    pd.DataFrame(sh).to_csv(os.path.join(RES, "figS3_availability_shares.csv"), index=False)
    hr = hourly_record(ipwr())
    n = 14 * 24
    pd.DataFrame({"day": np.arange(n) / 24, "ai_load_MW": 225 * hr["ell"][:n], "contracted_peak_MW": 225.0,
                  "mean_load_MW": 225 * hr["ell"].mean()}).to_csv(os.path.join(RES, "figS3_ai_load.csv"), index=False)
    print("figS3 tables written; mean load factor", round(hr["ell"].mean(), 3))


if __name__ == "__main__":
    hashprice_frontier()
    dispatch_example()
    price_duration()
    availability_load()
