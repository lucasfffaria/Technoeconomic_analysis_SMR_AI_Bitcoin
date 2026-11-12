"""prepare_prices.py - convert the raw price files downloaded from the market operators into the
compact hourly tables used by markets.py. Self-contained (pandas, numpy, openpyxl only).

    python prepare_prices.py <folder with the raw downloads> <output folder (data/raw)>

Raw inputs expected in the first folder (sub-folders are searched too):
  * ERCOT  'DAM Settlement Point Prices' yearly reports  rpt.00013060.*.DAMLZHBSPP_<year>.xlsx
  * CCEE   hourly PLD                                    pld_horario_<year>.csv
  * Ember  'European wholesale electricity price data'   <Country>.csv (hourly)
Outputs:
  ercot_dam_hourly.csv.gz   hour-beginning local time; hub and load-zone prices, USD/MWh (nominal)
  ccee_pld_hourly.csv.gz    hour-beginning local time; four submarkets, BRL/MWh (nominal)
  ember_europe_hourly.csv.gz  hour-beginning UTC; one column per country, EUR/MWh (nominal)
"""
import os, sys, glob
import numpy as np
import pandas as pd


def find(root, pattern):
    return sorted(glob.glob(os.path.join(root, "**", pattern), recursive=True))


def ercot(root):
    frames = []
    for f in find(root, "*DAMLZHBSPP_*.xlsx"):
        x = pd.ExcelFile(f)
        for sh in x.sheet_names:
            d = x.parse(sh)
            d.columns = [c.strip() for c in d.columns]
            hour = d["Hour Ending"].astype(str).str.slice(0, 2).astype(int) - 1      # hour beginning 0..23
            t = pd.to_datetime(d["Delivery Date"], format="%m/%d/%Y") + pd.to_timedelta(hour, unit="h")
            frames.append(pd.DataFrame({"time": t, "flag": d["Repeated Hour Flag"].astype(str), "point": d["Settlement Point"].astype(str),
                                        "price": d["Settlement Point Price"].astype(float)}))
    d = pd.concat(frames)
    d = d[d.flag != "Y"]                                   # drop the repeated hour at the end of daylight saving time
    w = d.pivot_table(index="time", columns="point", values="price", aggfunc="first").sort_index()
    return w.round(2)


def ccee(root):
    frames = []
    for f in find(root, "pld_horario_*.csv"):
        d = pd.read_csv(f, sep=";", dtype=str)
        d.columns = [c.strip('"') for c in d.columns]
        ym = d["MES_REFERENCIA"].str.strip('"')
        t = pd.to_datetime(ym + d["DIA"].str.strip('"').str.zfill(2), format="%Y%m%d") + \
            pd.to_timedelta(d["HORA"].str.strip('"').astype(int), unit="h")
        frames.append(pd.DataFrame({"time": t, "sub": d["SUBMERCADO"].str.strip('"'), "price": d["PLD_HORA"].astype(float)}))
    d = pd.concat(frames)
    w = d.pivot_table(index="time", columns="sub", values="price", aggfunc="first").sort_index()
    return w.rename(columns={"SUDESTE": "SE_CO", "SUL": "S", "NORDESTE": "NE", "NORTE": "N"}).round(2)


def ember(root):
    cols = {}
    for f in find(root, "*.csv"):
        head = open(f, encoding="utf-8").readline()
        if "Price (EUR/MWhe)" not in head or os.path.basename(f).startswith("all_countries"):
            continue
        d = pd.read_csv(f, usecols=["Country", "Datetime (UTC)", "Price (EUR/MWhe)"])
        s = pd.Series(d["Price (EUR/MWhe)"].values, index=pd.to_datetime(d["Datetime (UTC)"]))
        cols[d["Country"].iloc[0]] = s[~s.index.duplicated()]
    w = pd.DataFrame(cols).sort_index()
    w.index.name = "time_utc"
    return w.round(2)


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for name, fn in (("ercot_dam_hourly", ercot), ("ccee_pld_hourly", ccee), ("ember_europe_hourly", ember)):
        w = fn(src)
        w.to_csv(os.path.join(out, name + ".csv.gz"), compression={"method": "gzip", "mtime": 0})
        print(f"{name}: {w.shape[0]} hours x {w.shape[1]} series, {w.index[0]} .. {w.index[-1]}")
