"""facts.py - collect every result number quoted in the manuscript from the result files."""
import os, json
import numpy as np, pandas as pd
from scipy.stats import spearmanr
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "..", "results")
R = lambda f: pd.read_csv(os.path.join(RES, f))
F = {}


def put(k, v, d=0):
    F[k] = f"{v:,.{d}f}".replace("-", "−")


b = R("base_results.csv").set_index(["tech", "config"])
L = {"iPWR": dict(ai="A", btc="B", sh="C"), "FHR": dict(ai="D", btc="E", sh="F")}
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    put(f"{t}_lcoe", b.loc[(tech, "AI-I"), "lcoe"], 0)
    put(f"{t}_lcoe1", b.loc[(tech, "AI-I"), "lcoe"], 1)
    put(f"{t}_avail", 100 * b.loc[(tech, "AI-I"), "avail"], 1)
    for reg in "IXG":
        a, c = b.loc[(tech, f"AI-{reg}")], b.loc[(tech, f"AI+BTC-{reg}")]
        put(f"{t}_ai_{reg}", a["lcai"]); put(f"{t}_ai_{reg}1", a["lcai"], 1)
        put(f"{t}_sh_{reg}", c["lcai"]); put(f"{t}_sh_{reg}1", c["lcai"], 1)
        put(f"{t}_sh_{reg}_p10", c["lcai_p10"]); put(f"{t}_sh_{reg}_p90", c["lcai_p90"])
        put(f"{t}_d_{reg}", a["lcai"] - c["lcai"], 1)
        put(f"{t}_dpct_{reg}", 100 * (a["lcai"] - c["lcai"]) / a["lcai"], 1)
        put(f"{t}_M_{reg}", c["M"])
        put(f"{t}_minecf_{reg}", 100 * c["mine_cf"])
        put(f"{t}_Emine_{reg}", c["E_mine"] / 1e3)
        put(f"{t}_npv_ai_{reg}", a["npv"] / 1e9, 2); put(f"{t}_npv_sh_{reg}", c["npv"] / 1e9, 2)
        put(f"{t}_util_ai_{reg}", 100 * a["util"]); put(f"{t}_util_sh_{reg}", 100 * c["util"])
        put(f"{t}_Eexp_ai_{reg}", a["E_exp"] / 1e3); put(f"{t}_Eexp_sh_{reg}", c["E_exp"] / 1e3)
    put(f"{t}_Eai_I", b.loc[(tech, "AI-I"), "E_ai"] / 1e3); put(f"{t}_Eai_G", b.loc[(tech, "AI-G"), "E_ai"] / 1e3)
    put(f"{t}_Ebak_I", b.loc[(tech, "AI-I"), "E_bak"] / 1e3, 1)
    put(f"{t}_Eimp_G", b.loc[(tech, "AI-G"), "E_imp"] / 1e3, 1)
    put(f"{t}_imp_share_G", 100 * b.loc[(tech, "AI-G"), "E_imp"] / b.loc[(tech, "AI-G"), "E_ai"], 1)
    put(f"{t}_islanding_penalty", b.loc[(tech, "AI-I"), "lcai"] - b.loc[(tech, "AI-G"), "lcai"], 0)
    put(f"{t}_pen_recovered", 100 * (b.loc[(tech, "AI-I"), "lcai"] - b.loc[(tech, "AI+BTC-I"), "lcai"]) /
        (b.loc[(tech, "AI-I"), "lcai"] - b.loc[(tech, "AI-G"), "lcai"]), 0)
    put(f"{t}_export_value", b.loc[(tech, "AI-I"), "lcai"] - b.loc[(tech, "AI-X"), "lcai"], 1)
    put(f"{t}_both_value", b.loc[(tech, "AI-I"), "lcai"] - b.loc[(tech, "AI+BTC-X"), "lcai"], 1)
    for cfg, key in (("BTC-I", "btc_I"), ("BTC-G", "btc_G"), ("GRID", "grid")):
        r = b.loc[(tech, cfg)]
        put(f"{t}_npv_{key}", r["npv"] / 1e9, 2); put(f"{t}_npvkw_{key}", r["npv_per_kw"], 0)
        put(f"{t}_cover_{key}", 100 * r["pv_coprod"] / r["pv_cost_total"], 0)
    put(f"{t}_minecf_btcI", 100 * b.loc[(tech, "BTC-I"), "mine_cf"])
    put(f"{t}_util_grid", 100 * b.loc[(tech, "GRID"), "util"])
put("tech_gap_G", b.loc[("FHR", "AI-G"), "lcai"] - b.loc[("iPWR", "AI-G"), "lcai"], 0)
put("tech_gap_lcoe", b.loc[("FHR", "AI-I"), "lcoe"] - b.loc[("iPWR", "AI-I"), "lcoe"], 0)

# waterfall
fl = R("firming_flex_sweep.csv")
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    slack = fl.query("tech==@tech and kappa==0")["lcai"].iloc[0]
    put(f"{t}_slack_level", slack)
    put(f"{t}_wf_slack", slack - b.loc[(tech, "AI-I"), "lcoe"]); put(f"{t}_wf_red", b.loc[(tech, "AI-I"), "lcai"] - slack)
    put(f"{t}_curt_share", 100 * fl.query("tech==@tech and kappa==0")["curt_share"].iloc[0], 1)

# firming
f = R("firming.csv")
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    for key, name in (("red", "Nuclear redundancy (N-1)"), ("gas", "On-site gas backup"), ("flex", "Flexible AI (25 % sheddable)"),
                      ("gridb", "Grid backup (ERCOT)")):
        a = f.query("tech==@tech and firming==@name and mining==False").iloc[0]
        m = f.query("tech==@tech and firming==@name and mining==True").iloc[0]
        put(f"{t}_{key}", a["lcai"]); put(f"{t}_{key}_btc", m["lcai"]); put(f"{t}_{key}_d", a["lcai"] - m["lcai"], 1)
        put(f"{t}_{key}_M", m["M"])
    d = fl[fl.tech == tech]
    red = f.query("tech==@tech and firming=='Nuclear redundancy (N-1)'")
    put(f"{t}_kstar_red", np.interp(red[red.mining == False].lcai.iloc[0], d.lcai, d.kappa), 0)
    put(f"{t}_kstar_redbtc", np.interp(red[red.mining == True].lcai.iloc[0], d.lcai, d.kappa), 0)
    gas = f.query("tech==@tech and firming=='On-site gas backup' and mining==False").lcai.iloc[0]
    put(f"{t}_kstar_gas", np.interp(gas, d.lcai, d.kappa), 0)
    g = f.query("tech==@tech and firming=='On-site gas backup' and mining==False").iloc[0]
    put(f"{t}_gas_energy", g["E_b1"] / 1e3, 0); put(f"{t}_gas_share", 100 * g["E_b1"] / g["E_del"], 1)

# policy
p = R("policy.csv")
keys = {"Base (BOAK, 7 %, no credit)": "base", "30 % investment tax credit": "itc30", "40 % investment tax credit": "itc40",
        "Real WACC 5 %": "w5", "INL advanced OCC (6,050 $/kW)": "adv", "INL conservative OCC (11,000 $/kW)": "cons",
        "NOAK OCC (4,400 $/kW)": "noak", "NOAK OCC + WACC 5 %": "noak5", "30 % ITC + WACC 5 %": "itc30w5",
        "UAMPS-type overrun (15,000 $/kW)": "uamps"}
for _, r in p.iterrows():
    t, k = r["tech"].lower(), keys[r["case"]]
    put(f"pol_{t}_{k}_lcoe", r["lcoe"]); put(f"pol_{t}_{k}_G", r["AI-G"]); put(f"pol_{t}_{k}_I", r["AI-I"])
    put(f"pol_{t}_{k}_CI", r["AI+BTC-I"]); put(f"pol_{t}_{k}_btcI", r["BTC-I"]); put(f"pol_{t}_{k}_grid", r["GRID"])

# break-even dedicated mining
be = R("breakeven_btc.csv")
for _, r in be.iterrows():
    k = f"{r['tech'].lower()}_{'btcI' if r['config']=='BTC-I' else 'btcG'}"
    put(f"{k}_rstar", r["rbar_star"]); put(f"{k}_occstar", round(r["occ_star"], -1)); put(f"{k}_rstar_x", r["rbar_star"] / 150, 1)
    put(f"{k}_numean", r["nu_mean"])

# markets
ms = R("market_stats.csv")
REG = (("United States", "us"), ("Brazil", "br"), ("Europe", "eu"))
put("mk_n", len(ms)); put("mk_markets", ms.market.nunique())
for reg, k in REG:
    put(f"mk_n_{k}", (ms.region == reg).sum()); put(f"mk_markets_{k}", ms[ms.region == reg].market.nunique())
put("mk_n_above130", (ms["mean"] >= 130).sum()); put("mk_n_fit", (ms["mean"] < 130).sum())
put("mk_n_below45", (ms["mean"] < 45).sum()); put("mk_pct_below45", 100 * (ms["mean"] < 45).mean())
CASES = [("ERCOT", y, f"e{y % 100}") for y in range(2021, 2027)] + [("Brazil SE/CO", y, f"br{y % 100}") for y in range(2021, 2027)] + \
        [("Germany", 2025, "de25"), ("Germany", 2022, "de22"), ("Norway", 2020, "no20"), ("Finland", 2025, "fi25"), ("France", 2025, "fr25"),
         ("Spain", 2025, "es25")]
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    m = R(f"markets_{tech}.csv")
    m["v_exp"] = m.lcai_AI_I - m.lcai_AI_X
    m["v_min"] = m.lcai_AI_I - m.lcai_C_I
    m["v_both"] = m.lcai_AI_I - np.minimum(m.lcai_C_X, m.lcai_AI_X)
    m["incr_X"] = m.lcai_AI_X - np.minimum(m.lcai_C_X, m.lcai_AI_X)
    m["incr_G"] = m.lcai_AI_G - np.minimum(m.lcai_C_G, m.lcai_AI_G)
    mm = m[m.p_mean < 130]
    z = np.polyfit(mm.p_mean, mm.v_exp, 1)
    put(f"{t}_cross", (m.v_min.iloc[0] - z[1]) / z[0]); put(f"{t}_slope_exp", z[0], 2)
    put(f"{t}_fit_resid", np.std(mm.v_exp - np.polyval(z, mm.p_mean)), 1)
    win = m.v_min > m.v_exp
    put(f"{t}_minewins_maxp", m[win].p_mean.max()); put(f"{t}_expwins_minp", m[~win].p_mean.min())
    put(f"{t}_all_minewins", win.sum()); put(f"{t}_all_minewins_pct", 100 * win.mean())
    for reg, k in REG:
        g = m[m.region == reg]
        put(f"{t}_{k}_n", len(g)); put(f"{t}_{k}_minewins", (g.v_min > g.v_exp).sum())
        put(f"{t}_{k}_incrX", g.incr_X.mean(), 1); put(f"{t}_{k}_incrG", g.incr_G.mean(), 1)
        put(f"{t}_{k}_incrX_max", g.incr_X.max(), 1); put(f"{t}_{k}_M0", (g.M_X == 0).sum())
    eu = m[m.region == "Europe"]
    put(f"{t}_eu_minewins_pre21", ((eu.year <= 2020) & (eu.v_min > eu.v_exp)).sum()); put(f"{t}_eu_n_pre21", (eu.year <= 2020).sum())
    put(f"{t}_eu_minewins_post21", ((eu.year >= 2021) & (eu.v_min > eu.v_exp)).sum()); put(f"{t}_eu_n_post21", (eu.year >= 2021).sum())
    for market, year, key in CASES:
        r = m[(m.market == market) & (m.year == year)].iloc[0]
        put(f"{key}_price", r.p_mean); put(f"{t}_{key}_vexp", r.v_exp, 1); put(f"{t}_{key}_vboth", r.v_both, 1)
        put(f"{t}_{key}_incrX", r.incr_X, 1); put(f"{t}_{key}_MX", r.M_X); put(f"{t}_{key}_AIX", r.lcai_AI_X)
        put(f"{t}_{key}_AIG", r.lcai_AI_G); put(f"{t}_{key}_CG", r.lcai_C_G)
    e21 = m[(m.market == "ERCOT") & (m.year == 2021)].iloc[0]
    put(f"{t}_e21_grid", e21.npv_GRID / 1e9, 2)
    put(f"{t}_vmin", m.v_min.iloc[0], 1)
    br = m[m.region == "Brazil"]
    put(f"{t}_br_vexp_min", br.v_exp.min(), 1); put(f"{t}_br_vexp_max", br.v_exp.max(), 1)
    put(f"{t}_ratio_br24", m.v_min.iloc[0] / m[(m.market == "Brazil SE/CO") & (m.year == 2024)].v_exp.iloc[0], 1)
from common import BASE_YEARS
e = ms[(ms.market == "ERCOT") & (ms.year.astype(str).isin(BASE_YEARS["ERCOT"]))]
put("ercot_mean", e["mean"].mean(), 1); put("ercot_mean0", e["mean"].mean(), 0); put("ercot_med", e["median"].mean(), 0)
put("ercot_ymin", e["mean"].min()); put("ercot_ymax", e["mean"].max())
e3 = ms[(ms.market == "ERCOT") & (ms.year.astype(str).isin(["2024", "2025", "2026"]))]
put("ercot_recent_min", e3["mean"].min()); put("ercot_recent_max", e3["mean"].max())
de = ms[(ms.market == "Germany")]
put("de_post21_min", de[de.year >= 2021]["mean"].min()); put("de_post21_max", de[de.year >= 2021]["mean"].max())
put("de25_neg", de[de.year == 2025]["neg_hours"].iloc[0])
pld = pd.read_csv(os.path.join(RES, "..", "data", "raw", "ccee_pld_hourly.csv.gz"), index_col=0, parse_dates=True)["SE_CO"]
for y in range(2021, 2026):
    g = pld[pld.index.year == y]
    put(f"br{y % 100}_floor_share", 100 * (g <= g.min() + 0.01).mean()); put(f"br{y % 100}_brl", g.mean()); put(f"br{y % 100}_floor", g.min(), 2)

# sensitivities
s = R("sens_oneway.csv")
def sv(tech, param, side, col): return s[(s.tech == tech) & (s.param == param) & (s.side == side)][col].iloc[0]
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    for prm, key in (("Overnight capital cost", "occ"), ("Real WACC", "wacc"), ("AI load factor", "lf"), ("Frontier netback", "rbar"),
                     ("ASIC efficiency progress g", "g"), ("ASIC capex", "kasic"), ("Avoidable share of fuel cost", "kappa"),
                     ("Fuel cost", "fuel"), ("Forced outage rate", "for"), ("Fixed O&M", "fom"), ("Economic life", "life"),
                     ("Construction time", "tcon"), ("Mining infrastructure capex", "kinfra")):
        for side in ("low", "high"):
            put(f"s_{t}_{key}_{side}_G", sv(tech, prm, side, "lcai_G")); put(f"s_{t}_{key}_{side}_CI", sv(tech, prm, side, "lcai_CI"))
            put(f"s_{t}_{key}_{side}_d", sv(tech, prm, side, "d_mining"), 1); put(f"s_{t}_{key}_{side}_M", sv(tech, prm, side, "M"))
            put(f"s_{t}_{key}_{side}_I", sv(tech, prm, side, "lcai_I"))

# viability thresholds from the OCC x WACC map
mp = R("map_occ_wacc.csv")
def occ_star(tech, wacc, itc, col, target):
    d = mp[(mp.tech == tech) & (np.isclose(mp.wacc, wacc)) & (mp.itc == itc)].sort_values("occ")
    return np.interp(target, d[col], d["occ"])
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    for w in (0.05, 0.07, 0.10):
        for itc in (0.0, 0.3):
            for tgt in (100, 115):
                put(f"occ_{t}_w{int(100*w)}_itc{int(100*itc)}_{tgt}", round(occ_star(tech, w, itc, "AI-G", tgt), -2))
    put(f"occ_{t}_CI_w7_115", round(occ_star(tech, 0.07, 0.0, "AI+BTC-I", 115), -2))
# FHR parity overnight cost (grid-backed, 7 %)
fhr_par = occ_star("FHR", 0.07, 0.0, "AI-G", b.loc[("iPWR", "AI-G"), "lcai"])
put("fhr_parity_occ", round(fhr_par, -1)); put("fhr_parity_pct", 100 * (1 - fhr_par / 8800), 0); put("fhr_parity_abs", round(8800 - fhr_par, -1))
fhr_par_i = occ_star("FHR", 0.07, 0.0, "AI+BTC-I", b.loc[("iPWR", "AI+BTC-I"), "lcai"])
put("fhr_parity_pct_CI", 100 * (1 - fhr_par_i / 8800), 0)

# outlet map: netback threshold for mining to add value in the islanded design
try:
    om = R("map_outlet.csv")
    g = om.groupby("rbar").first()
    put("rbar_first_M", g[g.M_mining > 0].index.min())
    v = (g.lcai_none - g.lcai_mining)
    put("rbar_break", np.interp(0.5, v.values, v.index.values))
    for rb in (100, 120, 180, 220, 300):
        if rb in v.index: put(f"vmin_r{rb}", v.loc[rb], 1)
except Exception as ex:
    print("outlet map not ready", ex)

# Monte Carlo
mc = R("mc.csv")
put("mc_n", len(mc))
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    for col, key in (("lcoe", "lcoe"), ("AI-G", "G"), ("AI-I", "I"), ("AI+BTC-I", "CI"), ("AI-B", "B")):
        x = mc[f"{tech}_{col}"]
        for q, qn in ((.05, "p05"), (.5, "p50"), (.95, "p95")):
            put(f"mc_{t}_{key}_{qn}", x.quantile(q))
        put(f"mc_{t}_{key}_mean", x.mean()); put(f"mc_{t}_{key}_cv", x.std() / x.mean(), 2)
    put(f"mc_{t}_lcoe_p9010", mc[f"{tech}_lcoe"].quantile(.9) / mc[f"{tech}_lcoe"].quantile(.1), 2)
    for reg in "IXG":
        dl = mc[f"{tech}_AI-{reg}"] - mc[f"{tech}_AI+BTC-{reg}"]
        put(f"mc_{t}_d{reg}_mean", dl.mean(), 1); put(f"mc_{t}_d{reg}_med", dl.median(), 1); put(f"mc_{t}_d{reg}_p05", dl.quantile(.05), 1)
        put(f"mc_{t}_d{reg}_p95", dl.quantile(.95), 1); put(f"mc_{t}_d{reg}_ppos", 100 * (dl > 0).mean())
    for thr in (100, 115, 130, 150):
        put(f"mc_{t}_pG_{thr}", 100 * (mc[f"{tech}_AI-G"] <= thr).mean(), 1); put(f"mc_{t}_pCI_{thr}", 100 * (mc[f"{tech}_AI+BTC-I"] <= thr).mean(), 1)
    put(f"mc_{t}_pbtcI", 100 * (mc[f"{tech}_BTC-I"] > 0).mean(), 1); put(f"mc_{t}_pbtcG", 100 * (mc[f"{tech}_BTC-G"] > 0).mean(), 1)
    put(f"mc_{t}_pgrid", 100 * (mc[f"{tech}_GRID"] > 0).mean(), 1)
    put(f"mc_{t}_rho_occ", spearmanr(mc[f"{tech}_occ"], mc[f"{tech}_AI-G"])[0], 2); put(f"mc_{t}_rho_wacc", spearmanr(mc["wacc"], mc[f"{tech}_AI-G"])[0], 2)
    put(f"mc_{t}_rho_lf", spearmanr(mc["lf"], mc[f"{tech}_AI-G"])[0], 2)
    dl = mc[f"{tech}_AI-I"] - mc[f"{tech}_AI+BTC-I"]
    put(f"mc_{t}_rho_d_rbar", spearmanr(mc["rbar"], dl)[0], 2); put(f"mc_{t}_rho_d_rf", spearmanr(mc["rf_mean"], dl)[0], 2)
    put(f"mc_{t}_rho_d_g", spearmanr(mc["g"], dl)[0], 2); put(f"mc_{t}_rho_d_kasic", spearmanr(mc["k_asic"], dl)[0], 2)
put("mc_fhr_cheaper", 100 * (mc["FHR_AI-G"] < mc["iPWR_AI-G"]).mean()); put("mc_fhr_cheaper_lcoe", 100 * (mc.FHR_lcoe < mc.iPWR_lcoe).mean())

# design levers
g = R("granularity.csv")
for _, r in g.iterrows():
    k = f"gr_{r['tech'].lower()}_{int(r['n'])}"
    put(k + "_I", r.lcai_I); put(k + "_CI", r.lcai_CI); put(k + "_d", r.lcai_I - r.lcai_CI, 1); put(k + "_G", r.lcai_G)
    put(k + "_prem", r.lcai_I - r.lcai_G)
rp = R("rampup.csv")
for _, r in rp.iterrows():
    k = f"rp_{r['tech'].lower()}_{r['regime']}_{r['ramp'][0]}"
    put(k + "_ai", r.lcai_ai); put(k + "_sh", r.lcai_shared); put(k + "_d", r.lcai_ai - r.lcai_shared, 1); put(k + "_M1", r.M_first)
ec = R("export_cap.csv").set_index("X")
for X in (30, 60, 100, 300):
    put(f"xc_{X}_ai", ec.loc[X, "lcai_ai"], 1); put(f"xc_{X}_sh", ec.loc[X, "lcai_shared"], 1)
put("xc_100_share", 100 * (ec.loc[0, "lcai_ai"] - ec.loc[100, "lcai_ai"]) / (ec.loc[0, "lcai_ai"] - ec.loc[150, "lcai_ai"]))
st = R("stress.csv")
skeys = {"Base": "base", "Mining revenue falls to zero from year 3": "z3", "Mining revenue falls to zero from year 8": "z8",
         "Mining revenue falls to zero from year 15": "z15", "Frontier netback declines 2 %/yr": "t2",
         "Frontier netback declines 5 %/yr": "t5", "One 3-year bull cycle (x3) in years 6-8": "bull"}
for _, r in st.iterrows():
    put(f"st_{r['tech'].lower()}_{skeys[r['case']]}", r.d_mean, 1)

# mining economics: empirical and equilibrium
hf = pd.read_csv(os.path.join(RES, "hashprice_frontier.csv"), parse_dates=["time"]).set_index("time")
Rf = hf["frontier_netback"].dropna()
put("emp_med_2020", Rf.loc["2020":].median()); put("emp_last", Rf.iloc[-30:].mean()); put("emp_hp_last", hf["hashprice"].iloc[-30:].mean(), 1)
ann = Rf.resample("YE").mean()
for y in range(2020, 2027):
    put(f"emp_{y}", ann.loc[str(y)].iloc[0])
put("emp_logsd", np.log(ann.loc["2020":]).std(), 2)
hp = hf["hashprice"].loc["2019":]
tt = (hp.index - hp.index[0]).days / 365.25
put("emp_hp_trend", 100 * (np.exp(np.polyfit(tt, np.log(hp.values), 1)[0]) - 1))
put("emp_eta_rate", 100 * np.log(29.5 / 9.5) / ((pd.Timestamp("2026-01-01") - pd.Timestamp("2020-05-01")).days / 365.25))
# zero-profit power price of a stand-alone miner under the base mining parameters
import sys; sys.path.insert(0, HERE)
from model import Mining
mi = Mining()
r_, h = 0.07, 8760 * 0.95
nu = [mi.rbar * mi.cls_ratio * np.exp(-mi.g * (y - 0.5)) * (1 - mi.pool_fee) / mi.pue for y in range(1, mi.L + 1)]
disc = [(1 + r_) ** -(y - 0.5) for y in range(1, mi.L + 1)]
crf20 = r_ / (1 - (1 + r_) ** -20)
fixed = mi.k_asic + sum(d * (mi.k_infra * crf20 + mi.fom * 1000) for d in disc)
cstar = (sum(n * d for n, d in zip(nu, disc)) * h - fixed) / (sum(disc) * h)
put("cstar", cstar); put("nu_y1", nu[0]); put("nu_y5", nu[-1]); put("nu_avg", np.mean(nu))
put("asic_annuity_mwh", mi.k_asic * (r_ / (1 - (1 + r_) ** -mi.L)) / h)

put("mc_pbtc_max", max(100 * (mc[f"{T}_{c}"] > 0).mean() for T in ("iPWR", "FHR") for c in ("BTC-I", "BTC-G")), 1)
put("mc_pgrid_max", max(100 * (mc[f"{T}_GRID"] > 0).mean() for T in ("iPWR", "FHR")), 1)

# complementary indicators
EF_N, EF_GRID, EF_DIESEL, EF_GAS = 12.0, 350.0, 700.0, 500.0
W = {"iPWR": 1.25 * (1 - 0.31) / 0.31, "FHR": 1.25 * (1 - 0.42) / 0.42}
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    put(f"{t}_water", W[tech], 2); put(f"{t}_heat", (1 - (0.31 if tech == 'iPWR' else 0.42)) / (0.31 if tech == 'iPWR' else 0.42), 2)
    for cfg, key in (("AI-I", "ai_I"), ("AI+BTC-I", "sh_I"), ("AI-G", "ai_G")):
        r = b.loc[(tech, cfg)]
        ci = (r.E_ai_nuc * EF_N + r.E_imp * EF_GRID + r.E_bak * EF_DIESEL) / r.E_ai
        put(f"{t}_ci_{key}", ci, 0)
        put(f"{t}_avoid_{key}", (EF_GRID - ci) * r.E_ai / 1e9, 2)
        put(f"{t}_h2o_{key}", W[tech] * r.E_gen / 1e6, 1)
        put(f"{t}_gen_{key}", r.E_gen / 1e3)
    gz = f.query("tech==@tech and firming=='On-site gas backup' and mining==False").iloc[0]
    put(f"{t}_ci_gas", (gz.E_ai_nuc * EF_N + gz.E_b1 * EF_GAS + gz.E_bak * EF_DIESEL) / gz.E_del, 0)
    put(f"{t}_mine_co2", b.loc[(tech, "AI+BTC-I"), "E_mine"] * EF_N / 1e6, 0)
    put(f"{t}_mine_co2_grid", b.loc[(tech, "AI+BTC-I"), "E_mine"] * EF_GRID / 1e6, 0)
put("water_saving", 100 * (1 - W["FHR"] / W["iPWR"]))

# ---- additional derived facts used in the text
put("emp_hp_trend_abs", abs(100 * (np.exp(np.polyfit(tt, np.log(hp.values), 1)[0]) - 1)))
for tech in ("iPWR", "FHR"):
    t = tech.lower()
    for cfg, key in (("BTC-I", "btc_I"), ("BTC-G", "btc_G")):
        put(f"{t}_util_{key}", 100 * b.loc[(tech, cfg), "util"])
        put(f"{t}_npv_{key}_abs", abs(b.loc[(tech, cfg), "npv"]) / 1e9, 2)
    a = b.loc[(tech, "AI-I")]
    put(f"{t}_surplus_mw", (a.E_avail - a.E_ai_nuc) / 8760)
    put(f"{t}_islanding_pct", 100 * (a.lcai - b.loc[(tech, "AI-G"), "lcai"]) / b.loc[(tech, "AI-G"), "lcai"])
    put(f"{t}_prem_pct", 100 * (b.loc[(tech, "AI-G"), "lcai"] / 115.0 - 1))
    gas = f.query("tech==@tech and firming=='On-site gas backup' and mining==False").lcai.iloc[0]
    put(f"{t}_gas_vs_red", a.lcai - gas); put(f"{t}_gas_vs_grid", gas - b.loc[(tech, "AI-G"), "lcai"])
    put(f"st_{t}_z3_abs", abs(st[(st.tech == tech) & (st.case == "Mining revenue falls to zero from year 3")].d_mean.iloc[0]), 1)
    c = b.loc[(tech, "AI+BTC-I")]
    init = c.M * (mi.k_asic + mi.k_infra)
    put(f"{t}_mine_init", init / 1e6); 
    if tech == "iPWR":
        put("mine_init_share", 100 * init / (init + 8800 * 300e3)); put("mine_capex_share", 100 * init / (init + 8800 * 300e3))
    put(f"{t}_mine_pvshare", 100 * c.pv_min_capex / (c.pv_min_capex + c.pv_capex))
    put(f"{t}_brmult", (a.lcai - c.lcai) / F_num(f"{t}_br_vexp"), 1) if False else None
try:
    for rb in (120, 150, 220):
        d = om[om.rbar == rb].sort_values("price")
        diff = (d.lcai_export - d.lcai_mining).values          # >0 where mining is better
        put(f"bound_p_r{rb}", np.interp(0.0, -diff, d.price.values))
except Exception as ex:
    print("boundary facts not available", ex)
put("fhr_avail", 100 * b.loc[("FHR", "AI-I"), "avail"], 1)

json.dump(F, open(os.path.join(RES, "facts.json"), "w"), indent=0, ensure_ascii=False)
if __name__ == "__main__":
    print(len(F), "facts")
    for k in ("cstar", "nu_y1", "nu_y5", "nu_avg", "asic_annuity_mwh", "fhr_parity_occ", "fhr_parity_pct", "fhr_parity_pct_CI", "emp_med_2020",
              "emp_last", "emp_hp_last", "emp_logsd", "emp_hp_trend", "emp_eta_rate", "ercot_mean", "ipwr_cross", "fhr_cross",
              "occ_ipwr_w7_itc0_115", "occ_ipwr_w7_itc30_115", "occ_ipwr_w5_itc0_115", "occ_ipwr_w7_itc0_100", "occ_fhr_w7_itc0_115",
              "occ_ipwr_CI_w7_115", "ipwr_ci_ai_I", "ipwr_ci_ai_G", "ipwr_ci_gas", "ipwr_avoid_ai_I", "ipwr_avoid_ai_G", "ipwr_h2o_sh_I",
              "fhr_h2o_sh_I", "ipwr_water", "fhr_water", "water_saving", "ipwr_mine_co2", "ipwr_mine_co2_grid", "ipwr_us_n",
              "ipwr_us_minewins", "ipwr_us_incrX", "ipwr_us_incrG", "rbar_break", "rbar_first_M", "ipwr_pen_recovered", "fhr_pen_recovered",
              "ipwr_wf_slack", "ipwr_wf_red", "ipwr_slack_level", "xc_100_share"):
        print(f"  {k}: {F.get(k)}")
