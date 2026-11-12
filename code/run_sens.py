"""run_sens.py - deterministic sensitivity analyses (one-way, two-way maps, design variants)."""
import sys, json, time
from common import *

E0 = Econ()
MI0 = Mining()
MST = json.load(open(os.path.join(RES, "Mstar_base.json")))
MGRID = np.arange(0, 201, 20.0)


def best_M(tech, cfg0, econ, mining, hr, P, grid=MGRID):
    b = None
    for M in grid:
        o = expected(tech, replace(cfg0, M=float(M)), econ, mining, hr, P)
        if b is None or o["npv"] > b["npv"]:
            b = o; b["M"] = float(M)
    return b


def trio(tech, econ, mining, lf=0.80, reopt=True, n_real=5):
    """LCAI of AI-G, AI-I and AI+BTC-I (mining re-optimised)."""
    hr = hourly_record(tech, lf=lf, n_real=n_real)
    P = paths(mining, tech.life)
    cf = std_configs(tech, MST[tech.name])
    g = expected(tech, cf["AI-G"], econ, mining, hr, P)["lcai"]
    a = expected(tech, cf["AI-I"], econ, mining, hr, P)["lcai"]
    c = best_M(tech, cf["AI+BTC-I"], econ, mining, hr, P) if reopt else expected(tech, cf["AI+BTC-I"], econ, mining, hr, P)
    return dict(lcai_G=g, lcai_I=a, lcai_CI=c["lcai"], M=c.get("M", MST[tech.name]["I"]), d_mining=a - c["lcai"])


def oneway():
    rows = []
    for tech0 in (ipwr(), fhr()):
        base = trio(tech0, E0, MI0)
        rows.append(dict(tech=tech0.name, param="base", side="base", value=np.nan, **base))
        cases = [
            ("Overnight capital cost", "tech", "occ", 6050, 11000),
            ("Real WACC", "econ", "wacc", 0.05, 0.10),
            ("Fixed O&M", "tech", "fom", 130, 238),
            ("Fuel cost", "tech", "fuel", tech0.fuel * 0.75, tech0.fuel * 1.5),
            ("Construction time", "tech", "t_con", 43 / 12, 71 / 12),
            ("Forced outage rate", "tech", "for_", 0.015, 0.08),
            ("Economic life", "tech", "life", 30, 60),
            ("AI load factor", "lf", "lf", 0.65, 0.92),
            ("Frontier netback", "mining", "rbar", 90, 220),
            ("ASIC efficiency progress g", "mining", "g", 0.10, 0.30),
            ("ASIC capex", "mining", "k_asic", 1.0e6, 2.0e6),
            ("Mining infrastructure capex", "mining", "k_infra", 0.4e6, 1.0e6),
            ("Avoidable share of fuel cost", "tech", "kappa", 0.0, 1.0),
        ]
        for label, kind, attr, lo, hi in cases:
            for side, v in (("low", lo), ("high", hi)):
                tech, econ, mining, lf = tech0, E0, MI0, 0.80
                if kind == "tech":
                    tech = replace(tech0, **{attr: v})
                elif kind == "econ":
                    econ = replace(E0, **{attr: v})
                elif kind == "mining":
                    mining = replace(MI0, **{attr: v})
                else:
                    lf = v
                r = trio(tech, econ, mining, lf)
                rows.append(dict(tech=tech0.name, param=label, side=side, value=v, **r))
                print(tech0.name, label, side, {k: round(x, 1) for k, x in r.items()}, flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "sens_oneway.csv"), index=False)


def occ_wacc_map():
    rows = []
    for tech0 in (ipwr(), fhr()):
        hr = hourly_record(tech0)
        P = paths(MI0, tech0.life, n=200)
        cf = std_configs(tech0, MST[tech0.name])
        tabs = {k: flow_table(tech0, cf[k], E0, MI0, hr) for k in ("AI-G", "AI-I", "AI+BTC-I", "AI+BTC-G")}
        for occ in np.arange(3000, 15001, 500):
            for w in np.arange(0.03, 0.1001, 0.005):
                for itc in (0.0, 0.3):
                    tech = replace(tech0, occ=float(occ))
                    econ = replace(E0, wacc=float(w), itc=itc)
                    r = dict(tech=tech0.name, occ=occ, wacc=w, itc=itc)
                    for k in tabs:
                        r[k] = expected(tech, cf[k], econ, MI0, hr, P, table=tabs[k])["lcai"]
                    rows.append(r)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "map_occ_wacc.csv"), index=False)


def outlet_map():
    """Value of the mining and export outlets (regime X vs I) as a function of the frontier
    netback and of the wholesale price level (ERCOT 2017-2020 shape, scaled)."""
    tech = ipwr()
    hr = hourly_record(tech, n_real=2)
    pbar = hr["price"].mean()
    cf = std_configs(tech)
    rows = []
    rb = [60, 80, 100, 120, 150, 180, 220, 260, 300]
    sc = [0.3, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]
    ai_i = expected(tech, cf["AI-I"], E0, MI0, hr)["lcai"]
    exp_only = {s: expected(tech, cf["AI-X"], replace(E0, price_scale=s), MI0, hr)["lcai"] for s in sc}
    for r in rb:
        mining = replace(MI0, rbar=float(r))
        P = paths(mining, tech.life, n=200)
        m_only = best_M(tech, cf["AI+BTC-I"], E0, mining, hr, P)
        for s in sc:
            econ = replace(E0, price_scale=s)
            both = best_M(tech, cf["AI+BTC-X"], econ, mining, hr, P)
            rows.append(dict(rbar=r, scale=s, price=pbar * s, lcai_none=ai_i, lcai_export=exp_only[s],
                             lcai_mining=m_only["lcai"], M_mining=m_only["M"], lcai_both=both["lcai"], M_both=both["M"]))
        print("rbar", r, "done", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "map_outlet.csv"), index=False)


def granularity():
    rows = []
    for tech0 in (ipwr(), fhr()):
        for n in (2, 3, 4, 6, 8, 12):
            tech = replace(tech0, n_mod=n)
            hr = hourly_record(tech)
            P = paths(MI0, tech.life)
            C, c = tech.cap, tech.cap_mod
            a = expected(tech, Config("AI-I", C - c, 0, 0, 0), E0, MI0, hr, P)
            b = best_M(tech, Config("AI+BTC-I", C - c, 0, 0, 0), E0, MI0, hr, P, grid=np.arange(0, 0.5 * C + 1, 0.05 * C))
            g = expected(tech, Config("AI-G", C, 0, C, C, g_contract=c), E0, MI0, hr, P)
            rows.append(dict(tech=tech.name, n=n, cap=C, lcoe=a["lcoe"], lcai_I=a["lcai"], lcai_CI=b["lcai"], M=b["M"],
                             lcai_G=g["lcai"], util_I=a["util"], util_CI=b["util"], E_bak=a["E_bak"] / a["E_ai"]))
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "granularity.csv"), index=False)


def rampup():
    """AI campus that reaches its contracted load over several years; mining as a bridge load."""
    rows = []
    for tech in (ipwr(), fhr()):
        hr = hourly_record(tech)
        P = paths(MI0, tech.life)
        C, c = tech.cap, tech.cap_mod
        T = tech.life
        for regime, p_ai, kw in (("I", C - c, dict()), ("G", C, dict(X=C, G=C, g_contract=c))):
            for label, ramp in (("none", []), ("3-year", [0.25, 0.50, 0.75]), ("5-year", [0.2, 0.4, 0.6, 0.8, 0.9])):
                fr = np.ones(T); fr[:len(ramp)] = ramp
                def run(M1, M2):
                    Mby = np.full(T, float(M2)); Mby[:MI0.L] = M1
                    cache, tabs = {}, []
                    for y in range(T):
                        key = (fr[y], Mby[y])
                        if key not in cache:
                            cfg = Config("x", p_ai * fr[y], Mby[y], kw.get("X", 0.0), kw.get("G", 0.0), kw.get("g_contract", 0.0))
                            cache[key] = flow_table(tech, cfg, E0, MI0, hr)
                        tabs.append(cache[key])
                    cfg = Config("ramp", p_ai, float(M2), kw.get("X", 0.0), kw.get("G", 0.0), kw.get("g_contract", 0.0))
                    outs = [evaluate(tech, cfg, E0, MI0, RF=rf, tables_by_year=tabs, M_by_year=Mby) for rf in (P if Mby.max() > 0 else P[:1])]
                    return np.mean([o["lcai"] for o in outs]), np.mean([o["npv"] for o in outs])
                a_l, a_n = run(0, 0)
                M2 = MST[tech.name][regime]
                best = None
                for M1 in ([M2] if not ramp else np.arange(M2, C + 1, 30.0)):
                    l, nv = run(M1, M2)
                    if best is None or nv > best[2]:
                        best = (M1, l, nv)
                rows.append(dict(tech=tech.name, regime=regime, ramp=label, lcai_ai=a_l, lcai_shared=best[1], M_first=best[0], M_later=M2))
                print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "rampup.csv"), index=False)


def breakeven_btc():
    rows = []
    for tech0 in (ipwr(), fhr()):
        hr = hourly_record(tech0)
        cf = std_configs(tech0)
        for name in ("BTC-I", "BTC-G"):
            tab = flow_table(tech0, cf[name], E0, MI0, hr)
            def npv(rbar=150.0, occ=tech0.occ, itc=0.0, wacc=0.07):
                mining = replace(MI0, rbar=rbar)
                return expected(replace(tech0, occ=occ), cf[name], replace(E0, itc=itc, wacc=wacc), mining, hr,
                                paths(mining, tech0.life), table=tab)
            b = npv()
            cover = b["pv_coprod"] / b["pv_cost_total"]
            lo, hi = 50.0, 3000.0                         # break-even frontier netback
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if npv(rbar=mid)["npv"] < 0 else (lo, mid)
            r_star = 0.5 * (lo + hi)
            lo, hi = 0.0, tech0.occ                       # break-even overnight cost
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                lo, hi = (mid, hi) if npv(occ=mid)["npv"] > 0 else (lo, mid)
            rows.append(dict(tech=tech0.name, config=name, npv=b["npv"], npv_per_kw=b["npv_per_kw"], cover=cover,
                             rbar_star=r_star, occ_star=0.5 * (lo + hi), pv_min_net=b["pv_min_net"], pv_exp=b["pv_exp"],
                             pv_cost=b["pv_cost_total"], mine_cf=b["mine_cf"], nu_mean=b["nu_mean"]))
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "breakeven_btc.csv"), index=False)


def policy():
    rows = []
    cases = [("Base (BOAK, 7 %, no credit)", dict(), dict()),
             ("30 % investment tax credit", dict(), dict(itc=0.30)),
             ("40 % investment tax credit", dict(), dict(itc=0.40)),
             ("Real WACC 5 %", dict(), dict(wacc=0.05)),
             ("INL advanced OCC (6,050 $/kW)", dict(occ=6050.0), dict()),
             ("INL conservative OCC (11,000 $/kW)", dict(occ=11000.0), dict()),
             ("NOAK OCC (4,400 $/kW)", dict(occ=4400.0), dict()),
             ("NOAK OCC + WACC 5 %", dict(occ=4400.0), dict(wacc=0.05)),
             ("30 % ITC + WACC 5 %", dict(), dict(itc=0.30, wacc=0.05)),
             ("UAMPS-type overrun (15,000 $/kW)", dict(occ=15000.0), dict())]
    for tech0 in (ipwr(), fhr()):
        hr = hourly_record(tech0)
        P = paths(MI0, tech0.life)
        cf = std_configs(tech0, MST[tech0.name])
        tabs = {k: flow_table(tech0, cf[k], E0, MI0, hr) for k in cf}
        for label, tkw, ekw in cases:
            tech, econ = replace(tech0, **tkw), replace(E0, **ekw)
            r = dict(tech=tech0.name, case=label)
            for k in cf:
                o = expected(tech, cf[k], econ, MI0, hr, P, table=tabs[k])
                r["lcoe"] = o["lcoe"]
                r[k] = o["lcai"] if cf[k].p_ai > 0 else o["npv_per_kw"]
            rows.append(r)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "policy.csv"), index=False)
    print(pd.DataFrame(rows).round(1).to_string(index=False))


def export_cap():
    rows = []
    tech = ipwr()
    hr = hourly_record(tech)
    P = paths(MI0, tech.life)
    C, c = tech.cap, tech.cap_mod
    for X in (0, 15, 30, 60, 100, 150, 225, 300):
        a = expected(tech, Config("AI-X", C - c, 0, float(X), 0), E0, MI0, hr, P)
        b = best_M(tech, Config("AI+BTC-X", C - c, 0, float(X), 0), E0, MI0, hr, P, grid=np.arange(0, 161, 10.0))
        rows.append(dict(X=X, lcai_ai=a["lcai"], lcai_shared=b["lcai"], M=b["M"], util_ai=a["util"], util_shared=b["util"]))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "export_cap.csv"), index=False)


def mining_policy():
    """SI: ASIC class, replacement interval and reinvestment threshold (iPWR, islanded shared)."""
    rows = []
    tech = ipwr()
    hr = hourly_record(tech)
    cf = std_configs(tech, MST[tech.name])
    ai = expected(tech, cf["AI-I"], E0, MI0, hr)["lcai"]
    tab = flow_table(tech, cf["AI+BTC-I"], E0, MI0, hr)
    for cls, ratio, k in (("Current-generation value class (10 J/TH)", 0.95, 1.30e6), ("Previous generation (17.5 J/TH)", 0.54, 0.50e6)):
        for L in (3, 4, 5, 6, 8):
            for thr in (0, 80, 100, 120, 140):
                mi = replace(MI0, cls_ratio=ratio, k_asic=k, L=L, r_thr=float(thr))
                o = expected(tech, cf["AI+BTC-I"], E0, mi, hr, paths(mi, tech.life), table=tab)
                d = ai - o["_lcai"]
                rows.append(dict(asic=cls, L=L, r_thr=thr, d_mean=d.mean(), d_p05=np.quantile(d, .05), d_p95=np.quantile(d, .95),
                                 p_pos=np.mean(d > 0)))
    pd.DataFrame(rows).to_csv(os.path.join(RES, "mining_policy.csv"), index=False)


def stress():
    """Structural stress tests on the shared islanded configuration (iPWR and FHR)."""
    rows = []
    for tech in (ipwr(), fhr()):
        hr = hourly_record(tech)
        cf = std_configs(tech, MST[tech.name])
        ai = expected(tech, cf["AI-I"], E0, MI0, hr)["lcai"]
        tab = flow_table(tech, cf["AI+BTC-I"], E0, MI0, hr)
        P = paths(MI0, tech.life)
        def run(mod, label):
            outs = [evaluate(tech, cf["AI+BTC-I"], E0, MI0, table=tab, RF=mod(rf.copy())) for rf in P]
            d = ai - np.array([o["lcai"] for o in outs])
            rows.append(dict(tech=tech.name, case=label, d_mean=d.mean(), d_p05=np.quantile(d, .05), d_p95=np.quantile(d, .95)))
        run(lambda rf: rf, "Base")
        def collapse(year):
            def f(rf):
                rf[year:] = 0.0
                return rf
            return f
        for yr in (3, 8, 15):
            run(collapse(yr), f"Mining revenue falls to zero from year {yr}")
        def trend(rate):
            def f(rf):
                return rf * np.exp(-rate * np.arange(len(rf)))
            return f
        run(trend(0.02), "Frontier netback declines 2 %/yr")
        run(trend(0.05), "Frontier netback declines 5 %/yr")
        def bull(rf):
            rf[5:8] = rf[5:8] * 3.0
            return rf
        run(bull, "One 3-year bull cycle (x3) in years 6-8")
    pd.DataFrame(rows).to_csv(os.path.join(RES, "stress.csv"), index=False)
    print(pd.DataFrame(rows).round(2).to_string(index=False))


def threshold_check():
    """SI: effect of the reinvestment threshold (0 vs 100 USD/MWh) under the base process, declining
    netback trends and low long-run netbacks (iPWR, islanded shared, mining capacity fixed)."""
    rows = []
    tech = ipwr()
    hr = hourly_record(tech)
    cf = std_configs(tech, MST[tech.name])
    ai = expected(tech, cf["AI-I"], E0, MI0, hr)["lcai"]
    tab = flow_table(tech, cf["AI+BTC-I"], E0, MI0, hr)
    cases = (("Base process", 0.0, 150.0), ("Netback declines by 2 % per year", 0.02, 150.0),
             ("Netback declines by 5 % per year", 0.05, 150.0), ("Long-run netback 110 USD/MWh", 0.0, 110.0),
             ("Long-run netback 90 USD/MWh", 0.0, 90.0))
    for label, rate, rbar in cases:
        for thr in (0.0, 100.0):
            mi = replace(MI0, r_thr=thr, rbar=rbar)
            d = ai - np.array([evaluate(tech, cf["AI+BTC-I"], E0, mi, table=tab,
                                        RF=rf * np.exp(-rate * np.arange(len(rf))))["lcai"] for rf in paths(mi, tech.life)])
            rows.append(dict(case=label, r_thr=thr, d_mean=d.mean(), d_p05=np.quantile(d, .05), d_p95=np.quantile(d, .95)))
    pd.DataFrame(rows).to_csv(os.path.join(RES, "threshold_check.csv"), index=False)
    print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    t0 = time.time()
    for name in sys.argv[1:]:
        globals()[name]()
        print(name, "finished in", round(time.time() - t0), "s", flush=True)
