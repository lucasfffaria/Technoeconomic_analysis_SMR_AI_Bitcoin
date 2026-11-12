"""run_markets.py - value of the grid-export and mining outlets across market-years."""
import sys, json
from common import *

E = Econ()
MI = Mining()
which = sys.argv[1] if len(sys.argv) > 1 else "iPWR"
tech = ipwr() if which == "iPWR" else fhr()
P = paths(MI, tech.life, n=300)
Mgrid = np.arange(0, 201, 20.0)
rows = []
# market-independent islanded results
_b = pd.read_csv(os.path.join(RES, "base_results.csv")).query("tech == @tech.name").set_index("config")
ai_i, c_i = _b.loc["AI-I", "lcai"], _b.loc["AI+BTC-I", "lcai"]
for market, yrs in MK.items():
    for y, p in yrs.items():
        hr = hourly_record(tech, market, years=[y], n_real=4, seed=SEED + 7)
        res = dict(tech=tech.name, market=market, region=markets.region(market), year=y, **{f"p_{k}": v for k, v in markets.describe(p).items()},
                   lcai_AI_I=ai_i, lcai_C_I=c_i)
        for reg in ("X", "G"):
            a = expected(tech, std_configs(tech)[f"AI-{reg}"], E, MI, hr, P)
            best = None
            for M in Mgrid:
                o = expected(tech, std_configs(tech, {reg: M})[f"AI+BTC-{reg}"], E, MI, hr, P)
                if best is None or o["npv"] > best[1]["npv"]:
                    best = (M, o)
            res.update({f"lcai_AI_{reg}": a["lcai"], f"lcai_C_{reg}": best[1]["lcai"], f"M_{reg}": best[0],
                        f"Eexp_AI_{reg}": a["E_exp"], f"Emine_C_{reg}": best[1]["E_mine"],
                        f"Eexp_C_{reg}": best[1]["E_exp"]})
        g = expected(tech, std_configs(tech)["GRID"], E, MI, hr, P)
        b = expected(tech, std_configs(tech)["BTC-G"], E, MI, hr, P)
        res.update(npv_GRID=g["npv"], npv_BTC_G=b["npv"])
        rows.append(res)
        print(market, y, round(res["p_mean"], 1), {k: round(v, 1) for k, v in res.items() if k.startswith(("lcai", "M_"))}, flush=True)
pd.DataFrame(rows).to_csv(os.path.join(RES, f"markets_{tech.name}.csv"), index=False)
