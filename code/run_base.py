"""run_base.py - base-case results: scenario table for both technologies (reference market ERCOT)."""
import json, time
from common import *

E = Econ()
MI = Mining()
rows, opt_curves, Mstar = [], [], {}
t0 = time.time()
for tech in (ipwr(), fhr()):
    hr = hourly_record(tech)
    P = paths(MI, tech.life)
    Mstar[tech.name] = {}
    for reg in ("I", "X", "G"):
        M, o, curve = optimise_M(tech, reg, E, MI, hr, P)
        Mstar[tech.name][reg] = float(M)
        curve["tech"], curve["regime"] = tech.name, reg
        opt_curves.append(curve)
    cfgs = std_configs(tech, Mstar[tech.name])
    for name, cfg in cfgs.items():
        o = clean(expected(tech, cfg, E, MI, hr, P))
        o.update(M=cfg.M, p_ai=cfg.p_ai, avail=hr["avail"].mean() / tech.cap)
        rows.append(o)
    print(tech.name, "done", round(time.time() - t0, 1), "s", Mstar[tech.name])

df = pd.DataFrame(rows)
df.to_csv(os.path.join(RES, "base_results.csv"), index=False)
pd.concat(opt_curves).to_csv(os.path.join(RES, "base_M_curves.csv"), index=False)
json.dump(Mstar, open(os.path.join(RES, "Mstar_base.json"), "w"), indent=1)

pd.set_option("display.width", 250)
show = df[["tech", "config", "p_ai", "M", "lcoe", "lcai", "lcai_p10", "lcai_p90", "npv", "npv_per_kw", "util",
           "mine_cf", "E_ai", "E_mine", "E_exp", "E_imp", "E_bak", "ai_nuc_share"]].copy()
for c in ("npv",):
    show[c] /= 1e6
for c in ("E_ai", "E_mine", "E_exp", "E_imp", "E_bak"):
    show[c] /= 1e3
print(show.round(2).to_string(index=False))
