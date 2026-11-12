"""run_firming.py - alternative ways of firming an off-grid AI campus (reference market irrelevant:
all configurations are islanded) and where Bitcoin mining fits."""
import json
from common import *

E = Econ()
MI = Mining()
GAS = dict(b1_cap=75.0, b1_cost=50.0, b1_delivers=True, b1_capex=1800.0, b1_fom=20.0)
rows, sweep = [], []
for tech in (ipwr(), fhr()):
    hr = hourly_record(tech)
    P = paths(MI, tech.life)
    C, c = tech.cap, tech.cap_mod
    Mgrid = np.arange(0, 201, 10.0)

    def best(cfg0):
        b = None
        for M in Mgrid:
            o = expected(tech, replace(cfg0, M=M), E, MI, hr, P)
            if b is None or o["npv"] > b["npv"]:
                b = o; b["M"] = M
        return b

    # R: nuclear redundancy (N-1)
    a = expected(tech, Config("R", C - c, 0, 0, 0), E, MI, hr, P); a["M"] = 0
    b = best(Config("R+BTC", C - c, 0, 0, 0))
    rows += [{**clean(a), "firming": "Nuclear redundancy (N-1)", "mining": False},
             {**clean(b), "firming": "Nuclear redundancy (N-1)", "mining": True}]
    # B: on-site gas backup for one module
    a = expected(tech, Config("B", C, 0, 0, 0, **GAS), E, MI, hr, P); a["M"] = 0
    b = best(Config("B+BTC", C, 0, 0, 0, **GAS))
    rows += [{**clean(a), "firming": "On-site gas backup", "mining": False},
             {**clean(b), "firming": "On-site gas backup", "mining": True}]
    # F: flexible AI (curtail up to 25 % of peak), for several idle-compute costs
    for kappa in (0, 250, 500, 1000, 2000, 3000, 4000, 6000):
        F = dict(b1_cap=0.25 * C, b1_cost=float(kappa), b1_delivers=False)
        a = expected(tech, Config("F", C, 0, 0, 0, **F), E, MI, hr, P); a["M"] = 0
        b = best(Config("F+BTC", C, 0, 0, 0, **F))
        sweep.append(dict(tech=tech.name, kappa=kappa, lcai=a["lcai"], lcai_btc=b["lcai"], M=b["M"],
                          curt_share=a["E_b1"] / a["E_ai"], E_b1=a["E_b1"]))
        if kappa == 1000:
            rows += [{**clean(a), "firming": "Flexible AI (25 % sheddable)", "mining": False},
                     {**clean(b), "firming": "Flexible AI (25 % sheddable)", "mining": True}]
    # G: grid backup, for reference (ERCOT)
    Mst = json.load(open(os.path.join(RES, "Mstar_base.json")))[tech.name]
    cf = std_configs(tech, Mst)
    a = expected(tech, cf["AI-G"], E, MI, hr, P); a["M"] = 0
    b = expected(tech, cf["AI+BTC-G"], E, MI, hr, P); b["M"] = Mst["G"]
    rows += [{**clean(a), "firming": "Grid backup (ERCOT)", "mining": False},
             {**clean(b), "firming": "Grid backup (ERCOT)", "mining": True}]

df = pd.DataFrame(rows)
df.to_csv(os.path.join(RES, "firming.csv"), index=False)
sw = pd.DataFrame(sweep)
sw.to_csv(os.path.join(RES, "firming_flex_sweep.csv"), index=False)
pd.set_option("display.width", 250)
d = df[["tech", "firming", "mining", "M", "lcai", "E_del", "E_mine", "E_b1", "E_bak", "util", "mine_cf"]].copy()
for k in ("E_del", "E_mine", "E_b1", "E_bak"):
    d[k] /= 1e3
print(d.round(2).to_string(index=False))
print(sw.round(4).to_string(index=False))
