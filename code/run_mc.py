"""run_mc.py - Monte Carlo uncertainty propagation and global sensitivity analysis."""
import sys, json, time
import multiprocessing as mp
import model
from common import *

model.NU_GRID = np.concatenate([[0.0], np.geomspace(5.0, 2500.0, 40)])
MST = json.load(open(os.path.join(RES, "Mstar_base.json")))
ERCOT_YEARS = BASE_YEARS["ERCOT"]
GAS = dict(b1_cap=75.0, b1_cost=50.0, b1_delivers=True, b1_capex=1800.0, b1_fom=20.0)


def tri(rng, a, b, c):
    return rng.triangular(a, b, c)


def draw(seed):
    rng = np.random.default_rng(seed)
    com = dict(wacc=tri(rng, 0.05, 0.07, 0.10), lf=tri(rng, 0.65, 0.80, 0.92),
               year=ERCOT_YEARS[rng.integers(0, len(ERCOT_YEARS))], pscale=tri(rng, 0.7, 1.0, 1.6),
               rbar=tri(rng, 90, 150, 220), g=tri(rng, 0.10, 0.20, 0.30),
               k_asic=tri(rng, 1.0, 1.3, 2.0) * 1e6, k_infra=tri(rng, 0.4, 0.7, 1.0) * 1e6)
    mining = Mining(rbar=com["rbar"], g=com["g"], k_asic=com["k_asic"], k_infra=com["k_infra"])
    econ = Econ(wacc=com["wacc"], price_scale=com["pscale"])
    RF = frontier_path(rng, 40, mining)
    intra = intra_year_profile(rng)
    ell = ai_profile(rng, lf=com["lf"])
    price = MK["ERCOT"][com["year"]]
    out = dict(seed=seed, **com, rf_mean=RF.mean())
    spec = {
        "iPWR": dict(occ=8800 * np.exp(0.25 * rng.normal()), fom=tri(rng, 130, 150, 238), fuel=tri(rng, 11.0, 12.1, 13.3),
                     vom=tri(rng, 2.4, 2.9, 3.1), t_con=tri(rng, 43, 55, 71) / 12, for_=tri(rng, 0.015, 0.03, 0.06)),
        "FHR": dict(occ=8800 * np.exp(0.40 * rng.normal()), fom=tri(rng, 130, 165, 290), fuel=tri(rng, 13.0, 18.0, 30.0),
                    vom=tri(rng, 2.4, 2.9, 3.1), t_con=tri(rng, 43, 60, 84) / 12, for_=tri(rng, 0.02, 0.04, 0.12)),
    }
    for name, base in (("iPWR", ipwr()), ("FHR", fhr())):
        tech = replace(base, **spec[name])
        hr = dict(avail=availability(tech, rng), ell=ell, price=price, intra=intra)
        C, c = tech.cap, tech.cap_mod
        cf = std_configs(tech, MST[name])
        cf["AI-B"] = Config("AI-B", C, 0, 0, 0, **GAS)
        cf["AI+BTC-B"] = Config("AI+BTC-B", C, 50.0, 0, 0, **GAS)
        for k, v in spec[name].items():
            out[f"{name}_{k}"] = v
        out[f"{name}_avail"] = hr["avail"].mean() / C
        for k, cfg in cf.items():
            o = evaluate(tech, cfg, econ, mining, hourly=hr, RF=RF)
            out[f"{name}_lcoe"] = o["lcoe"]
            out[f"{name}_{k}"] = o["lcai"] if cfg.p_ai > 0 else o["npv_per_kw"]
            if k == "AI+BTC-I":
                out[f"{name}_pvmin_I"] = (o["pv_min_net"] - (tech.c_var) * o["pv_E_mine"]) / (tech.cap * 1000)
    return out


if __name__ == "__main__":
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
    t0 = time.time()
    with mp.Pool(2) as pool:
        rows = pool.map(draw, range(1000, 1000 + N), chunksize=25)
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RES, "mc.csv"), index=False)
    print("MC done", N, round(time.time() - t0), "s")
    print(df[[c for c in df.columns if "lco" in c or "AI" in c]].describe().round(1).T.to_string())
