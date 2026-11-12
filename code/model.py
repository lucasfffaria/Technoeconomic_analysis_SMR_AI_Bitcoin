"""
model.py - techno-economic model of a co-located SMR / AI data-centre / Bitcoin-mining energy hub.

Units: MW, MWh, USD (constant 2025), hours. One 'representative operating year' is simulated at
hourly resolution (possibly several concatenated years, to average over outage realisations and
price years) and embedded in a discounted cash-flow model over the plant's economic life.
"""
from dataclasses import dataclass, replace, asdict
import numpy as np
from scipy.signal import lfilter

H = 8760


# ----------------------------------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------------------------------
@dataclass
class Tech:
    name: str
    occ: float            # overnight capital cost, $/kWe
    fom: float            # fixed O&M, $/kW-yr
    vom: float            # variable O&M, $/MWh
    fuel: float           # fuel, $/MWh
    t_con: float          # construction time, years
    for_: float           # forced outage rate (fraction of time)
    planned_days: float   # planned outage per module, days per cycle
    eff: float            # net thermal efficiency
    cycle_months: int = 24
    mttr: float = 120.0   # mean time to repair, h
    n_mod: int = 4
    cap_mod: float = 75.0  # MWe net per module
    life: int = 40        # economic life, years
    decom_frac: float = 0.10
    kappa: float = 1.0    # share of the fuel cost that is avoided when output is reduced

    @property
    def cap(self):
        return self.n_mod * self.cap_mod

    @property
    def c_var(self):
        """Marginal (avoidable) cost of an extra MWh, $/MWh."""
        return self.vom + self.kappa * self.fuel


@dataclass
class Econ:
    wacc: float = 0.07
    ai_price: float = 100.0      # reference AI PPA price, $/MWh
    tau_x: float = 2.0           # export fee/loss, $/MWh
    tau_g: float = 10.0          # import network adder, $/MWh
    c_backup: float = 250.0      # on-site backup generation (diesel), $/MWh
    voll: float = 5000.0         # unserved AI energy, $/MWh (not reached in practice)
    standby: float = 50.0        # grid standby charge, $/kW-yr on contracted backup capacity
    k_ic: float = 150.0          # grid interconnection capex, $/kW
    price_scale: float = 1.0     # multiplier on wholesale prices
    itc: float = 0.0             # investment tax credit on nuclear capex (fraction)


@dataclass
class Mining:
    rbar: float = 150.0          # long-run median gross revenue of a frontier ASIC, $/MWh
    sigma: float = 0.40          # stationary sd of log frontier netback (annual)
    rho: float = 0.5             # annual autocorrelation
    g: float = 0.20              # efficiency-progress rate = decay of a machine's netback, 1/yr
    L: int = 5                   # ASIC replacement interval, years
    cls_ratio: float = 0.95      # netback of the purchased class relative to the frontier
    k_asic: float = 1.30e6       # ASIC capex, $/MW (frontier-value class)
    k_infra: float = 0.70e6      # site infrastructure, $/MW
    theta: float = 0.5           # elasticity of ASIC price to the frontier netback at purchase
    fom: float = 25.0            # mining fixed O&M, $/kW-yr
    pool_fee: float = 0.015
    pue: float = 1.04            # mining auxiliary/cooling overhead
    uptime: float = 0.97
    infra_life: int = 20
    intra_sd: float = 0.25       # sd of within-year daily hashprice variation (log)
    r_thr: float = 100.0         # reinvestment threshold on the frontier netback, $/MWh


def ipwr():
    return Tech("iPWR", occ=8800, fom=150, vom=2.9, fuel=12.1, t_con=55 / 12, for_=0.03,
                planned_days=14, eff=0.31)


def fhr():
    return Tech("FHR", occ=8800, fom=165, vom=2.9, fuel=18.0, t_con=60 / 12, for_=0.04,
                planned_days=10, eff=0.42)


# ----------------------------------------------------------------------------------------------
# Hourly building blocks
# ----------------------------------------------------------------------------------------------
def availability(tech, rng, years=1):
    """Available capacity (MW) per hour: staggered planned outages (half of the modules per year
    for a 24-month cycle) plus forced outages (two-state Markov process per module)."""
    n = tech.n_mod
    T = H * years
    up = np.ones((n, T), dtype=bool)
    # planned outages
    per_year = n * 12.0 / tech.cycle_months          # modules in planned outage each year
    dur = int(round(tech.planned_days * 24))
    k = 0
    for y in range(years):
        cnt = int(round(per_year * (y + 1))) - int(round(per_year * y))
        for j in range(cnt):
            # alternate spring (day ~80) and autumn (day ~285) windows, staggered back-to-back
            season = j % 2
            slot = j // 2
            start = y * H + (80 if season == 0 else 285) * 24 + slot * dur
            mod = k % n
            up[mod, start:start + dur] = False
            k += 1
    # forced outages
    if tech.for_ > 0:
        mttf = tech.mttr * (1 - tech.for_) / tech.for_
        for i in range(n):
            t = rng.exponential(mttf) * rng.random()   # random phase
            while t < T:
                d = rng.exponential(tech.mttr)
                a, b = int(t), int(min(T, t + d))
                up[i, a:b] = False
                t += d + rng.exponential(mttf)
    return up.sum(axis=0) * tech.cap_mod


def ai_profile(rng, lf=0.80, diurnal=0.05, seasonal=0.03, sigma=0.05, rho=0.97, years=1):
    """AI campus load as a fraction of contracted peak (mean = lf, capped at 1)."""
    T = H * years
    h = np.arange(T)
    hod, doy = h % 24, (h // 24) % 365
    base = diurnal * np.sin(2 * np.pi * (hod - 9) / 24) - seasonal * np.cos(2 * np.pi * (doy - 15) / 365)
    e = rng.normal(size=T) * sigma * np.sqrt(1 - rho ** 2)
    e[0] = rng.normal() * sigma
    ar = lfilter([1.0], [1.0, -rho], e)
    x = base + ar
    shift = lf
    for _ in range(40):
        y = np.clip(shift + x, 0.30, 1.0)
        shift += lf - y.mean()
    return np.clip(shift + x, 0.30, 1.0)


def intra_year_profile(rng, sd=0.25, years=1):
    """Daily multiplicative hashprice profile within a year (mean 1), expanded to hours."""
    nd = 365 * years
    e = rng.normal(size=nd) * np.sqrt(1 - 0.98 ** 2)
    e[0] = rng.normal()
    x = lfilter([1.0], [1.0, -0.98], e)
    f = np.exp(sd * x)
    f /= f.mean()
    return np.repeat(f, 24)


def dispatch(avail, load, price, nu, M, X, G, c_var, econ, b1_cap=0.0, b1_cost=0.0, series=False):
    """Closed-form optimal hourly dispatch (see SI for the equivalent LP).
    avail, load, price, nu: arrays (MW, MW, $/MWh, $/MWh); M: mining capacity (MW, effective);
    X: export limit (MW); G: import limit for AI shortfalls (MW).
    b1_cap/b1_cost: optional tier-1 firming resource used before grid imports and emergency
    diesel (on-site gas backup, or curtailment of flexible AI load).
    Returns dict of energy totals (MWh) and money totals ($) over the simulated horizon."""
    short = np.maximum(load - avail, 0.0)
    b1 = np.minimum(short, b1_cap)
    rest = short - b1
    g = np.minimum(rest, G)
    g = np.where(price + econ.tau_g <= econ.c_backup, g, 0.0)
    b = rest - g
    gen_ai = load - short
    S = avail - gen_ai
    px = price - econ.tau_x
    mine_ok = nu > c_var
    exp_ok = px > c_var
    mine_first = nu >= px
    m1 = np.where(mine_ok, np.minimum(S, M), 0.0)          # mining first
    x1 = np.where(exp_ok, np.minimum(S - m1, X), 0.0)
    x2 = np.where(exp_ok, np.minimum(S, X), 0.0)           # export first
    m2 = np.where(mine_ok, np.minimum(S - x2, M), 0.0)
    m = np.where(mine_first, m1, m2)
    x = np.where(mine_first, x1, x2)
    gen = gen_ai + m + x
    if series:
        return dict(gen_ai=gen_ai, mine=m, export=x, imp=g, backup=b, b1=b1, curtailed=avail - gen)
    return dict(E_ai=load.sum(), E_ai_nuc=gen_ai.sum(), E_imp=g.sum(), E_bak=b.sum(), E_b1=b1.sum(),
                E_mine=m.sum(), E_exp=x.sum(), E_gen=gen.sum(), E_avail=avail.sum(),
                R_mine=(m * nu).sum(), R_exp=(x * px).sum(),
                C_imp=(g * (price + econ.tau_g)).sum(), C_bak=b.sum() * econ.c_backup,
                C_b1=b1.sum() * b1_cost, C_var=gen.sum() * c_var, hours=len(avail))


# ----------------------------------------------------------------------------------------------
# Mining netback paths
# ----------------------------------------------------------------------------------------------
def frontier_path(rng, T, mining, deterministic=False):
    """Annual frontier gross netback R^F_y ($/MWh), y = 0..T (stationary log-AR(1))."""
    if deterministic:
        return np.full(T + 1, mining.rbar * np.exp(0.5 * mining.sigma ** 2 * 0))
    x = np.empty(T + 1)
    x[0] = rng.normal() * mining.sigma
    for y in range(1, T + 1):
        x[y] = mining.rho * x[y - 1] + np.sqrt(1 - mining.rho ** 2) * mining.sigma * rng.normal()
    return mining.rbar * np.exp(x)


def machine_netback(RF, mining, T):
    """Net revenue per MWh at the meter for the installed fleet in project years 1..T, the years
    in which a new ASIC vintage is bought and the ASIC price multiplier at each purchase.
    Reinvestment rule: a new vintage is bought when the fleet is at least L years old (or absent)
    and the frontier netback observed at that date is at least r_thr; otherwise the old fleet
    keeps running (its netback keeps decaying at rate g) and the decision is revisited yearly."""
    nu = np.zeros(T)
    vint, cur = [], None
    for y in range(1, T + 1):
        d = y - 1
        if (cur is None or d - cur >= mining.L) and RF[d] >= mining.r_thr:
            cur = d
            vint.append(d)
        if cur is not None:
            age = (y - 0.5) - cur
            nu[y - 1] = RF[y] * mining.cls_ratio * np.exp(-mining.g * age) * (1 - mining.pool_fee) / mining.pue
    vint = np.array(vint, dtype=int)
    kmult = (RF[vint] / mining.rbar) ** mining.theta if len(vint) else np.array([])
    return nu, vint, kmult


# ----------------------------------------------------------------------------------------------
# Life-cycle evaluation
# ----------------------------------------------------------------------------------------------
def capex_pv_factor(t_con, r):
    """PV (at COD) of 1 $ of overnight cost spent uniformly over the construction period."""
    n = max(int(round(t_con * 12)), 1)
    j = np.arange(n)
    return np.mean((1 + r) ** ((n - j - 0.5) / 12.0))


@dataclass
class Config:
    name: str
    p_ai: float               # contracted AI peak (MW); 0 = none
    M: float                  # installed mining capacity (MW)
    X: float                  # export limit (MW)
    G: float                  # import limit for AI shortfalls (MW)
    g_contract: float = 0.0   # contracted grid backup capacity (MW) charged at 'standby'
    b1_cap: float = 0.0       # tier-1 firming resource (MW): gas backup or flexible-AI curtailment
    b1_cost: float = 0.0      # its variable cost ($/MWh)
    b1_delivers: bool = True  # True: energy is delivered to AI (gas); False: AI is curtailed
    b1_capex: float = 0.0     # $/kW
    b1_fom: float = 0.0       # $/kW-yr


NU_GRID = np.concatenate([[0.0], np.geomspace(4.0, 3000.0, 72)])
FLOW_KEYS = ("E_ai", "E_ai_nuc", "E_imp", "E_bak", "E_b1", "E_mine", "E_exp", "E_gen", "E_avail",
             "R_mine", "R_exp", "C_imp", "C_bak", "C_b1", "C_var")


def flow_table(tech, cfg, econ, mining, hourly, intra=None):
    """Annual operating flows as a function of the fleet's mean annual mining netback (NU_GRID).
    R_mine is stored divided by the netback level so that it interpolates smoothly."""
    avail = hourly["avail"]
    load = cfg.p_ai * hourly["ell"]
    price = hourly["price"] * econ.price_scale
    yrs = len(avail) / H
    if intra is None:
        intra = hourly.get("intra", np.ones(len(avail)))
    Meff = cfg.M * mining.uptime
    grid = NU_GRID if cfg.M > 0 else np.array([0.0])
    tab = {k: np.empty(len(grid)) for k in FLOW_KEYS}
    for i, nu in enumerate(grid):
        f = dispatch(avail, load, price, nu * intra, Meff, cfg.X, cfg.G, tech.c_var, econ,
                     cfg.b1_cap, cfg.b1_cost)
        for k in FLOW_KEYS:
            tab[k][i] = f[k] / yrs
        tab["R_mine"][i] = f["R_mine"] / yrs / nu if nu > 0 else 0.0
    tab["grid"] = grid
    return tab


def _interp(tab, key, nu):
    if len(tab["grid"]) == 1:
        return tab[key][0]
    return np.interp(nu, tab["grid"], tab[key])


def evaluate(tech, cfg, econ, mining, hourly=None, RF=None, intra=None, table=None,
             tables_by_year=None, M_by_year=None):
    """Life-cycle indicators for one configuration and one frontier-netback path RF (len life+1).
    Either 'hourly' (dict of arrays avail/ell/price) or a precomputed 'table' must be given.
    tables_by_year / M_by_year allow year-specific operating regimes (AI ramp-up)."""
    T, r = tech.life, econ.wacc
    if tables_by_year is None:
        if table is None:
            table = flow_table(tech, cfg, econ, mining, hourly, intra)
        tables_by_year = [table] * T
    if M_by_year is None:
        M_by_year = np.full(T, cfg.M)
    disc = (1 + r) ** -(np.arange(1, T + 1) - 0.5)
    A = disc.sum()
    has_mining = M_by_year.max() > 0
    if has_mining:
        nu_y, vint, kmult = machine_netback(RF, mining, T)
    else:
        nu_y, vint, kmult = np.zeros(T), np.array([], dtype=int), np.array([])
    if all(t is tables_by_year[0] for t in tables_by_year):          # fast path: one operating regime
        t0 = tables_by_year[0]
        ann = {k: (np.full(T, t0[k][0]) if len(t0["grid"]) == 1 else np.interp(nu_y, t0["grid"], t0[k]))
               for k in FLOW_KEYS}
    else:
        ann = {k: np.array([_interp(tables_by_year[y], k, nu_y[y]) for y in range(T)]) for k in FLOW_KEYS}
    ann["R_mine"] = ann["R_mine"] * nu_y

    # --- present values (at COD)
    P_kw = tech.cap * 1000.0
    pv_capex = tech.occ * P_kw * capex_pv_factor(tech.t_con, r) * (1 - econ.itc)
    pv_fom = tech.fom * P_kw * A
    pv_fuel_sunk = (1 - tech.kappa) * tech.fuel * (ann["E_avail"] * disc).sum()
    pv_var = (ann["C_var"] * disc).sum() + pv_fuel_sunk
    pv_decom = tech.decom_frac * tech.occ * P_kw * (1 + r) ** -T
    pv_nuc = pv_capex + pv_fom + pv_var + pv_decom

    pv_min_capex = pv_min_om = 0.0
    if has_mining:
        Mv = M_by_year[vint]                               # capacity purchased at each vintage
        pv_min_capex += (Mv * mining.k_asic * kmult * (1 + r) ** -vint.astype(float)).sum()
        Minfra = M_by_year.max()
        pv_min_capex += Minfra * mining.k_infra * (1 + 0.5 * sum((1 + r) ** -float(k)
                                                                for k in range(mining.infra_life, T, mining.infra_life)))
        pv_min_om = (M_by_year * 1000.0 * mining.fom * disc).sum()
    pv_min_rev = (ann["R_mine"] * disc).sum()

    grid_cap = max(cfg.X, cfg.G)
    pv_grid_fix = econ.k_ic * grid_cap * 1000.0 + econ.standby * cfg.g_contract * 1000.0 * A
    pv_b1_fix = cfg.b1_cap * 1000.0 * (cfg.b1_capex * (1 + 0.5 * (1 + r) ** -20.0) + cfg.b1_fom * A)
    pv_imp = ((ann["C_imp"] + ann["C_bak"] + ann["C_b1"]) * disc).sum()
    pv_exp = (ann["R_exp"] * disc).sum()

    E_del = ann["E_ai"] - (0.0 if cfg.b1_delivers else ann["E_b1"])     # AI energy actually delivered
    pv_E_ai = (E_del * disc).sum()
    pv_E_avail = (ann["E_avail"] * disc).sum()
    pv_E_mine = (ann["E_mine"] * disc).sum()

    pv_cost_total = pv_nuc + pv_min_capex + pv_min_om + pv_grid_fix + pv_b1_fix + pv_imp
    pv_coprod = pv_min_rev + pv_exp
    lcoe = (pv_capex + pv_fom + pv_decom + (tech.vom + tech.fuel) * pv_E_avail) / pv_E_avail
    out = dict(config=cfg.name, tech=tech.name, lcoe=lcoe,
               pv_nuc=pv_nuc, pv_capex=pv_capex, pv_fom=pv_fom, pv_var=pv_var,
               pv_cost_total=pv_cost_total, pv_coprod=pv_coprod,
               pv_min_net=pv_min_rev - pv_min_capex - pv_min_om,
               pv_min_rev=pv_min_rev, pv_min_capex=pv_min_capex, pv_min_om=pv_min_om,
               pv_exp=pv_exp, pv_imp=pv_imp, pv_grid_fix=pv_grid_fix, pv_b1_fix=pv_b1_fix,
               pv_E_ai=pv_E_ai, pv_E_avail=pv_E_avail, pv_E_mine=pv_E_mine, annuity=A)
    if cfg.p_ai > 0:
        out["lcai"] = (pv_cost_total - pv_coprod) / pv_E_ai          # break-even AI price
        out["npv"] = econ.ai_price * pv_E_ai - (pv_cost_total - pv_coprod)
    else:
        out["lcai"] = np.nan
        out["npv"] = pv_coprod - pv_cost_total
    out["npv_per_kw"] = out["npv"] / P_kw
    for k in ("E_ai", "E_ai_nuc", "E_imp", "E_bak", "E_b1", "E_mine", "E_exp", "E_gen", "E_avail"):
        out[k] = ann[k].mean()
    out["E_del"] = E_del.mean()
    out["util"] = out["E_gen"] / out["E_avail"]
    out["mine_cf"] = out["E_mine"] / (M_by_year.mean() * H) if has_mining else 0.0
    out["ai_nuc_share"] = out["E_ai_nuc"] / out["E_ai"] if cfg.p_ai > 0 else np.nan
    out["nu_mean"] = nu_y.mean()
    return out


def make_hourly(tech, market_years, rng, lf=0.80, n_real=1):
    """Concatenate (price year x outage realisation) blocks into one long hourly record."""
    av, el, pr = [], [], []
    for p in market_years:
        for _ in range(n_real):
            av.append(availability(tech, rng))
            el.append(ai_profile(rng, lf=lf))
            pr.append(p)
    return dict(avail=np.concatenate(av), ell=np.concatenate(el), price=np.concatenate(pr))


def std_configs(tech, M=None):
    """Scenario set for one technology.
    Grid regimes:  I = islanded;  X = export-only (non-firm) interconnection;  G = full grid
    connection (export + firm backup). AI is sized to N-1 firm capacity whenever firmness must be
    provided on site (I, X) and to the full plant when the grid provides backup (G).
    M: dict regime -> mining capacity for the shared (AI+BTC) scenarios."""
    M = M or {}
    C, c = tech.cap, tech.cap_mod
    firm = C - c
    return {
        "AI-I": Config("AI-I", firm, 0.0, 0.0, 0.0),
        "AI-X": Config("AI-X", firm, 0.0, C, 0.0),
        "AI-G": Config("AI-G", C, 0.0, C, C, g_contract=c),
        "BTC-I": Config("BTC-I", 0.0, C, 0.0, 0.0),
        "BTC-G": Config("BTC-G", 0.0, C, C, 0.0),
        "AI+BTC-I": Config("AI+BTC-I", firm, M.get("I", 0.0), 0.0, 0.0),
        "AI+BTC-X": Config("AI+BTC-X", firm, M.get("X", 0.0), C, 0.0),
        "AI+BTC-G": Config("AI+BTC-G", C, M.get("G", 0.0), C, C, g_contract=c),
        "GRID": Config("GRID", 0.0, 0.0, C, 0.0),
    }
