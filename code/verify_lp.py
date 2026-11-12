"""verify_lp.py - check the closed-form hourly dispatch (model.dispatch) against the linear
programme of Supplementary Section S1.2 solved with HiGHS (scipy.optimize.linprog)."""
import os, json
import numpy as np
import scipy
from scipy import sparse
from scipy.optimize import linprog
from common import *


def lp_dispatch(avail, load, price, nu, M, X, G, c_var, econ, b1_cap=0.0, b1_cost=0.0):
    """Variables per hour: Gen, m, x, g, b1, b (b1 dropped when b1_cap == 0)."""
    T = len(avail)
    s = np.maximum(load - avail, 0.0)
    names = ["gen", "m", "x", "g", "b"] + (["b1"] if b1_cap > 0 else [])
    nv = len(names)
    ix = {k: i * T + np.arange(T) for i, k in enumerate(names)}
    c = np.zeros(nv * T)                      # linprog minimises
    c[ix["gen"]] = c_var
    c[ix["m"]] = -nu
    c[ix["x"]] = -(price - econ.tau_x)
    c[ix["g"]] = price + econ.tau_g
    c[ix["b"]] = econ.c_backup
    ub = np.zeros(nv * T)
    ub[ix["gen"]] = avail
    ub[ix["m"]] = M
    ub[ix["x"]] = X
    ub[ix["g"]] = np.minimum(G, s)
    ub[ix["b"]] = s
    if b1_cap > 0:
        c[ix["b1"]] = b1_cost
        ub[ix["b1"]] = np.minimum(b1_cap, s)
    I = sparse.identity(T, format="csr")
    # balance: gen + g + b1 + b - m - x = load
    sign = {"gen": 1, "g": 1, "b": 1, "b1": 1, "m": -1, "x": -1}
    A_eq = sparse.hstack([sign[k] * I for k in names], format="csr")
    # non-nuclear supply serves the AI shortfall only: g + b1 + b <= s
    A_ub = sparse.hstack([(1 if k in ("g", "b", "b1") else 0) * I for k in names], format="csr")
    res = linprog(c, A_ub=A_ub, b_ub=s, A_eq=A_eq, b_eq=load, bounds=np.c_[np.zeros(nv * T), ub],
                  method="highs-ds")
    assert res.status == 0, res.message
    out = {k: res.x[ix[k]].sum() for k in names}
    out["obj"] = -res.fun
    out["nvar"] = nv * T
    return out


def closed_form(avail, load, price, nu, M, X, G, c_var, econ, b1_cap=0.0, b1_cost=0.0):
    f = dispatch(avail, load, price, nu, M, X, G, c_var, econ, b1_cap, b1_cost)
    obj = f["R_mine"] + f["R_exp"] - f["C_var"] - f["C_imp"] - f["C_b1"] - f["C_bak"]
    return dict(gen=f["E_gen"], m=f["E_mine"], x=f["E_exp"], g=f["E_imp"], b=f["E_bak"], b1=f["E_b1"], obj=obj)


if __name__ == "__main__":
    E, MI = Econ(), Mining()
    tech = ipwr()
    out = {"scipy": scipy.__version__}
    cases = {
        "grid-connected (CAISO 2019)": dict(market="CAISO", year="2019", p_ai=300.0, M=80.0, X=120.0, G=75.0, nu0=120.0),
        "islanded, gas-backed (ERCOT 2019)": dict(market="ERCOT", year="2019", p_ai=300.0, M=80.0, X=0.0, G=0.0, nu0=120.0,
                                                  b1_cap=75.0, b1_cost=50.0),
        "islanded N-1, low netback (ERCOT 2018)": dict(market="ERCOT", year="2018", p_ai=225.0, M=110.0, X=0.0, G=0.0, nu0=14.0),
    }
    for name, k in cases.items():
        hr = hourly_record(tech, market=k["market"], years=[k["year"]], n_real=1)
        avail, load, price = hr["avail"], k["p_ai"] * hr["ell"], hr["price"]
        nu = k["nu0"] * hr["intra"]
        args = (avail, load, price, nu, k["M"] * MI.uptime, k["X"], k["G"], tech.c_var, E,
                k.get("b1_cap", 0.0), k.get("b1_cost", 0.0))
        lp, cf = lp_dispatch(*args), closed_form(*args)
        rel = abs(lp["obj"] - cf["obj"]) / abs(cf["obj"])
        dmax = max(abs(lp[v] - cf[v]) for v in lp if v not in ("obj", "nvar"))
        out[name] = dict(variables=int(lp["nvar"]), negative_price_hours=int((price < 0).sum()),
                         shortfall_hours=int((load > avail).sum()), objective_lp=lp["obj"], objective_closed=cf["obj"],
                         rel_diff=rel, max_energy_diff_MWh=dmax,
                         mining_GWh=cf["m"] / 1e3, export_GWh=cf["x"] / 1e3, import_GWh=cf["g"] / 1e3,
                         backup_GWh=(cf["b"] + cf["b1"]) / 1e3)
        print(f"{name}: {lp['nvar']} variables, neg-price hours {int((price < 0).sum())}, "
              f"rel. diff objective {rel:.1e}, max |energy diff| {dmax:.2e} MWh")
    json.dump(out, open(os.path.join(RES, "verify_lp.json"), "w"), indent=1)
