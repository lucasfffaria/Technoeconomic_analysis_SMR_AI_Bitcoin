"""common.py - shared helpers for the analysis scripts."""
import os
import numpy as np
import pandas as pd
from dataclasses import replace
from model import *
import markets

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")
os.makedirs(RES, exist_ok=True)

MK = markets.all_markets()
# reference market: ERCOT, the four most recent complete calendar years (after the February 2021 winter storm)
BASE_YEARS = {"ERCOT": ["2022", "2023", "2024", "2025"]}
N_PATHS = 500
SEED = 20261110


def market_years(market, years=None):
    yrs = years or BASE_YEARS.get(market) or [y for y in MK[market] if y != "2021"] or list(MK[market])
    return [MK[market][y] for y in yrs]


def hourly_record(tech, market="ERCOT", years=None, lf=0.80, n_real=5, seed=SEED):
    rng = np.random.default_rng(seed)
    hr = make_hourly(tech, market_years(market, years), rng, lf=lf, n_real=n_real)
    hr["intra"] = intra_year_profile(rng, sd=0.25, years=len(hr["avail"]) // H)
    return hr


def paths(mining, T=40, n=N_PATHS, seed=SEED + 1):
    rng = np.random.default_rng(seed)
    return [frontier_path(rng, T, mining) for _ in range(n)]


def expected(tech, cfg, econ, mining, hr, P=None, table=None):
    """Mean of the life-cycle indicators over the netback paths (common random numbers)."""
    if table is None:
        table = flow_table(tech, cfg, econ, mining, hr, hr.get("intra"))
    if cfg.M <= 0:
        o = evaluate(tech, cfg, econ, mining, table=table, RF=None)
        o = {k: (float(v) if isinstance(v, (np.floating, np.ndarray)) and np.ndim(v) == 0 else v) for k, v in o.items()}
        o["lcai_p10"] = o["lcai_p90"] = o["lcai"]
        o["npv_p10"] = o["npv_p90"] = o["npv"]
        o["_lcai"] = np.array([o["lcai"]])
        o["_npv"] = np.array([o["npv"]])
        return o
    if P is None:
        P = paths(mining, tech.life)
    outs = [evaluate(tech, cfg, econ, mining, table=table, RF=rf) for rf in P]
    o = {k: (np.mean([x[k] for x in outs]) if isinstance(outs[0][k], (int, float, np.floating)) else outs[0][k])
         for k in outs[0]}
    lc = np.array([x["lcai"] for x in outs])
    nv = np.array([x["npv"] for x in outs])
    o["lcai_p10"], o["lcai_p90"] = np.nanquantile(lc, [.1, .9]) if cfg.p_ai > 0 else (np.nan, np.nan)
    o["npv_p10"], o["npv_p90"] = np.quantile(nv, [.1, .9])
    o["_lcai"], o["_npv"] = lc, nv
    return o


def optimise_M(tech, regime, econ, mining, hr, P, grid=None, p_ai=None):
    """Mining capacity that maximises the expected NPV of the shared configuration."""
    grid = grid if grid is not None else np.arange(0, tech.cap + 1, 10.0)
    best = None
    rows = []
    for M in grid:
        cfg = std_configs(tech, {regime: M})[f"AI+BTC-{regime}"]
        if p_ai is not None:
            cfg = replace(cfg, p_ai=p_ai)
        o = expected(tech, cfg, econ, mining, hr, P)
        rows.append((M, o["npv"], o["lcai"], o["mine_cf"], o["pv_min_net"]))
        if best is None or o["npv"] > best[1]:
            best = (M, o["npv"], o)
    return best[0], best[2], pd.DataFrame(rows, columns=["M", "npv", "lcai", "mine_cf", "pv_min_net"])


def clean(o):
    return {k: v for k, v in o.items() if not k.startswith("_")}
