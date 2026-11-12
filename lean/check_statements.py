"""Exact (rational) tests of the statements formalised in lean/SmrDispatch/Dispatch.lean.
This does not check the Lean proofs; it checks that the statements themselves hold on random instances
and that the counterexample used for `ordering_condition_needed` is right."""
import random, itertools
from fractions import Fraction as F
import numpy as np
from scipy.optimize import linprog

FIELDS = "P L M X Gi B1 nu p tx tg cv c1 cb".split()

def shortfall(h): return max(h["L"] - h["P"], F(0))
def tier1(h): return min(shortfall(h), h["B1"])
def imports(h): return min(shortfall(h) - tier1(h), h["Gi"]) if h["p"] + h["tg"] <= h["cb"] else F(0)
def emergency(h): return shortfall(h) - tier1(h) - imports(h)
def surplus(h): return h["P"] - (h["L"] - shortfall(h))
def mineFirst(h): return min(surplus(h), h["M"]) if h["cv"] < h["nu"] else F(0)
def exportAfter(h): return min(surplus(h) - mineFirst(h), h["X"]) if h["cv"] < h["p"] - h["tx"] else F(0)
def exportFirst(h): return min(surplus(h), h["X"]) if h["cv"] < h["p"] - h["tx"] else F(0)
def mineAfter(h): return min(surplus(h) - exportFirst(h), h["M"]) if h["cv"] < h["nu"] else F(0)
def mined(h): return mineFirst(h) if h["p"] - h["tx"] <= h["nu"] else mineAfter(h)
def exported(h): return exportAfter(h) if h["p"] - h["tx"] <= h["nu"] else exportFirst(h)
def merit(h):
    return dict(G=h["L"] - shortfall(h) + mined(h) + exported(h), m=mined(h), x=exported(h),
                g=imports(h), b1=tier1(h), b=emergency(h))
def feasible(h, d):
    return (d["G"] + d["g"] + d["b1"] + d["b"] == h["L"] + d["m"] + d["x"] and 0 <= d["G"] <= h["P"]
            and 0 <= d["m"] <= h["M"] and 0 <= d["x"] <= h["X"] and 0 <= d["b1"] <= h["B1"]
            and 0 <= d["g"] <= h["Gi"] and 0 <= d["b"] and d["g"] + d["b1"] + d["b"] <= shortfall(h))
def margin(h, d):
    return (h["nu"] * d["m"] + (h["p"] - h["tx"]) * d["x"] - h["cv"] * d["G"] - (h["p"] + h["tg"]) * d["g"]
            - h["c1"] * d["b1"] - h["cb"] * d["b"])
def ordered(h): return h["c1"] <= h["cb"] and (h["B1"] == 0 or h["Gi"] == 0 or h["c1"] <= h["p"] + h["tg"])
def valid(h): return all(h[k] >= 0 for k in "P L M X Gi B1".split())

def lp_opt(h):
    """Optimum of the hourly LP (S3)-(S11) with HiGHS; variables G, m, x, g, b1, b."""
    s = float(shortfall(h))
    c = -np.array([-h["cv"], h["nu"], h["p"] - h["tx"], -(h["p"] + h["tg"]), -h["c1"], -h["cb"]], dtype=float)
    A_eq = [[1, -1, -1, 1, 1, 1]]; b_eq = [float(h["L"])]
    A_ub = [[0, 0, 0, 1, 1, 1]]; b_ub = [s]
    bounds = [(0, float(h["P"])), (0, float(h["M"])), (0, float(h["X"])), (0, float(h["Gi"])), (0, float(h["B1"])), (0, None)]
    r = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    assert r.status == 0, r.message
    return -r.fun

def rnd_hour(rng, both=None):
    q = lambda lo, hi: F(rng.randint(lo * 4, hi * 4), 4)
    h = dict(P=q(0, 6), L=q(0, 6), M=q(0, 4), X=q(0, 4), Gi=q(0, 3), B1=q(0, 3), nu=q(-2, 12), p=q(-6, 14),
             tx=q(-1, 3), tg=q(-1, 3), cv=q(-1, 6), c1=q(0, 12), cb=q(0, 14))
    r = rng.random()                      # make degenerate cases frequent: zero capacities, ties
    if r < 0.2: h["B1"] = F(0)
    elif r < 0.4: h["Gi"] = F(0)
    if rng.random() < 0.15: h["M"] = F(0)
    if rng.random() < 0.15: h["X"] = F(0)
    if rng.random() < 0.15: h["nu"] = h["p"] - h["tx"]
    if rng.random() < 0.10: h["nu"] = h["cv"]
    if rng.random() < 0.10: h["L"] = h["P"]
    if rng.random() < 0.10: h["c1"] = h["cb"]
    if rng.random() < 0.10: h["p"] = h["cb"] - h["tg"]
    return h

rng = random.Random(20261111)
N = 60000
n_ord = n_unord = n_bad_unord = 0
worst = 0.0
for _ in range(N):
    h = rnd_hour(rng)
    d = merit(h)
    assert valid(h)
    assert feasible(h, d), ("feasibility fails", h, d)                       # meritOrder_feasible
    opt = lp_opt(h); val = float(margin(h, d))
    if ordered(h):
        n_ord += 1
        assert val >= opt - 1e-7 * (1 + abs(opt)), ("optimality fails", h, d, val, opt)   # meritOrder_optimal
        worst = max(worst, abs(val - opt))
    elif h["c1"] <= h["cb"]:
        n_unord += 1
        if val < opt - 1e-7:
            n_bad_unord += 1
    # conditions (15)-(16)
    if d["m"] > 0: assert h["cv"] < h["nu"]
    if d["x"] > 0: assert h["cv"] < h["p"] - h["tx"]
    # structural property of the merit order (a feasible plan): nuclear only
    assert (d["g"] == d["b1"] == d["b"] == 0) or (d["m"] == d["x"] == 0)
    # monotonicity in mining capacity
    if ordered(h):
        h2 = dict(h); h2["M"] = h["M"] + F(rng.randint(0, 8), 4)
        assert margin(h2, merit(h2)) >= margin(h, d)
print(f"{N} random hours: merit order feasible in all; optimal in all {n_ord} hours with Ordered "
      f"(largest |margin - LP optimum| = {worst:.2e})")
print(f"hours with c1 <= cb but tier-1 dearer than available imports: {n_unord}; merit order suboptimal in {n_bad_unord}")

# random feasible plans never beat the merit order (exact arithmetic), and satisfy the structural lemmas
cnt = 0
for _ in range(40000):
    h = rnd_hour(rng)
    if not ordered(h): continue
    s = shortfall(h)
    q = lambda hi: F(rng.randint(0, int(hi * 4)), 4) if hi > 0 else F(0)
    m, x, g, b1 = q(h["M"]), q(h["X"]), q(h["Gi"]), q(h["B1"])
    for b in (F(0), s - g - b1, q(max(s, 0))):
        d = dict(m=m, x=x, g=g, b1=b1, b=b); d["G"] = h["L"] + m + x - g - b1 - b
        if feasible(h, d):
            cnt += 1
            assert margin(h, d) <= margin(h, merit(h)), ("a feasible plan beats the merit order", h, d)
            assert (d["g"] == d["b1"] == d["b"] == 0) or (d["m"] == d["x"] == 0)
            assert d["m"] + d["x"] <= surplus(h)
print(f"{cnt} random feasible plans compared exactly with the merit order: none earns more")

# the arithmetic lemmas
def chk_greedy(rng, n=200000):
    for _ in range(n):
        q = lambda lo, hi: F(rng.randint(lo * 3, hi * 3), 3)
        a, b, U, V, S = q(-4, 6), q(-4, 6), q(0, 5), q(0, 5), q(0, 8)
        u, v = q(0, 5), q(0, 5)
        if not (u <= U and v <= V and u + v <= S): continue
        if 0 <= b <= a:
            assert a * u + b * v <= a * min(S, U) + b * min(S - min(S, U), V)
        if a >= 0 and b <= 0:
            assert a * u + b * v <= a * min(S, U)
        if a <= 0 and b <= 0:
            assert a * u + b * v <= 0
chk_greedy(rng); print("greedy_both / greedy_first / greedy_none hold on 200000 random points")

# the counterexample of `ordering_condition_needed`
h = dict(P=F(0), L=F(1), M=F(0), X=F(0), Gi=F(1), B1=F(1), nu=F(0), p=F(10), tx=F(0), tg=F(0), cv=F(0), c1=F(50), cb=F(100))
d = dict(G=F(0), m=F(0), x=F(0), g=F(1), b1=F(0), b=F(0))
print("counterexample: valid", valid(h), "| c1<=cb", h["c1"] <= h["cb"], "| plan feasible", feasible(h, d),
      "| margin(merit) =", margin(h, merit(h)), "< margin(plan) =", margin(h, d), "| Ordered:", ordered(h))
