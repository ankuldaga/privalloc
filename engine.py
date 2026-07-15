#!/usr/bin/env python3
"""PrivAlloc — private-asset allocation engine (self-contained, numpy + scipy only).

Toggle the utility formulation, edit the inputs in CONFIG, run:  python3 engine.py
It calibrates gamma_P (->60/40 equity/bond) and gamma_A (->70/30 active/passive), solves the
base books, runs the sensitivity sweeps + stability battery, and solves the 7-persona tax ladder
under the chosen production utility. Writes results/*.json, which dashboard.py turns into a
self-contained HTML dashboard.

Optimiser: scipy SLSQP multi-start (no JAX/CMA-ES) — reproduces the capped-vertex optima closely.
Universe (14 assets): 6 passive + 3 active (US-eq, INTL-eq, US-bond) + 4 private + cash.
"""
import os, json, numpy as np
from scipy.optimize import minimize
HERE = os.path.dirname(os.path.abspath(__file__)); RES = os.path.join(HERE, 'results')
os.makedirs(RES, exist_ok=True)
log = lambda s: print(s, flush=True)

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  CONFIG  —  edit everything here
# ═══════════════════════════════════════════════════════════════════════════════════════════
CFG = dict(
    NS=2000, NQ=40, N_YEARS=10, SEED=20260630, RF=0.035,   # shipped at NS=2000 (fast, ~15 min full run); raise to 4000-6000 for more fidelity (much slower — the high-gamma vaam stability solves dominate)
    # ---- which utilities to analyse in Stream 1, and which drives the personas (Stream 2) ----
    utilities=['overlay', 'vaam', 'cobb'],   # any of: overlay (Modified VAAM/v33), vaam (JPM), cobb, wam
    persona_utility='overlay',               # the production formulation for the personas
    THETA=0.85,                              # Cobb-Douglas passive/active split
    # ---- factor CMAs: annual arithmetic mean / vol ----
    factors=dict(
        US_EQ=(0.096, 0.171), INTL_EQ=(0.102, 0.186), US_BD=(0.048, 0.046), INTL_BD=(0.046, 0.043),
        HY=(0.055, 0.120), MUNI=(0.035, 0.051), REIT=(0.080, 0.200), SMALL=(0.020, 0.11), VALUE=(0.020, 0.11)),
    factor_corr=[[1, .87, -.06, -.05, .65, .10, .65, .30, -.10], [.87, 1, -.03, .10, .60, .10, .60, .28, -.05],
        [-.06, -.03, 1, .55, .35, .70, .30, 0, 0], [-.05, .10, .55, 1, .30, .50, .25, 0, 0],
        [.65, .60, .35, .30, 1, .30, .55, .20, .10], [.10, .10, .70, .50, .30, 1, .25, 0, 0],
        [.65, .60, .30, .25, .55, .25, 1, .25, .10], [.30, .28, 0, 0, .20, 0, .25, 1, .10],
        [-.10, -.05, 0, 0, .10, 0, .10, .10, 1]],
    # ---- active public funds: manager alpha / tracking error (annual) ----
    active=dict(us_eq_act=dict(factor='US_EQ', alpha=0.010, te=0.030),
                intl_eq_act=dict(factor='INTL_EQ', alpha=0.010, te=0.030),   # NEW: intl active = beta1 INTL_EQ, same alpha/TE as US active
                us_bd_act=dict(factor='US_BD', alpha=0.004, te=0.008)),
    # ---- privates: systematic replica (beta) + illiquidity premium + tracking error + gating ----
    privates=dict(
        pe=dict(premium=0.0235, te=0.066, gate=1.00, beta={'GEQ': 0.9, 'RF': 0.1}),
        pre=dict(premium=0.0210, te=0.054, gate=0.85, beta={'REIT': 1.0}),
        pi=dict(premium=0.0280, te=0.0353, gate=0.45, beta={'GEQ': 0.67, 'RF': 0.33}),
        pcdl=dict(premium=0.0320, te=0.0315, gate=0.20, beta={'HY': 0.57, 'RF': 0.43})),
    prem_sigma=dict(pe=0.010, pre=0.010, pi=0.010, pcdl=0.008),   # per-path premium uncertainty
    cash_vol=0.01,
    # gating (liquidity-penalty onset): probability & charge per quarter, in stress vs normal regime
    gate=dict(stress_pctile=10.0, p_stress=0.15, p_normal=0.03, k_stress=0.25, k_normal=0.043, cap=0.25),
    # ---- eps/capacity cost floor (regularises the private sleeve); scan picks moderate ----
    cost_candidates=[('ultra-low', 0.0002, 0.60), ('low', 0.0004, 0.40), ('mid', 0.0007, 0.28), ('base', 0.0010, 0.20)],
    cost_use='base', cpriv=0.003,
    # ---- calibration anchors ----
    eqbd_target=0.60, active_target=70.0,
    # ---- personas: (name, ARA multiplier, policy equity, liquidity-aversion lambda) ----
    personas=[('L0 Legacy Central', 1.0, 0.70, 0.005), ('L1 Legacy - Higher RA', 1.6, 0.50, 0.005),
              ('L2 Legacy - Lower RA', 0.6, 0.85, 0.005), ('L3 Legacy - Higher LA', 1.0, 0.70, 0.015),
              ('L4 Legacy - Lower LA', 1.0, 0.70, 0.0015), ('R5 Retirement', 1.6, 0.50, 0.015),
              ('E6 Education', 1.3, 0.60, 0.03)],
    persona_seeds=[42, 43, 44],
    caps=dict(private=0.08, active=0.20, funding=0.60), home_bias=0.60,
    tax=dict(income=0.37, dividend=0.20, cap_gains=0.20),
    tax_types=dict(us_eq='dividend', intl_eq='dividend', us_agg='income', intl_bd='income', us_hy='income',
                   us_muni='exempt', us_eq_act='dividend', intl_eq_act='dividend', us_bd_act='income',
                   pe='cg_heavy', pre='income', pi='income', pcdl='income', cash='income'),
    income_yield=dict(us_eq=0.016, intl_eq=0.030, us_agg=0.0418, intl_bd=0.026, us_hy=0.047, us_muni=0.033,
                      us_eq_act=0.016, intl_eq_act=0.030, us_bd_act=0.052, pe=0.01, pre=0.03, pi=0.025, pcdl=0.05, cash=0.035),
)
# ═══════════════════════════════════════════════════════════════════════════════════════════

FACT = list(CFG['factors'].keys()); fi = {f: i for i, f in enumerate(FACT)}
FMEAN = np.array([CFG['factors'][f][0] for f in FACT]); FVOL = np.array([CFG['factors'][f][1] for f in FACT])
FCORR = np.array(CFG['factor_corr'])
PRIVS = list(CFG['privates'].keys())
PASSIVE = ['us_eq', 'intl_eq', 'us_agg', 'intl_bd', 'us_hy', 'us_muni', 'cash']
ACT_FUNDS = list(CFG['active'].keys())                       # us_eq_act, intl_eq_act, us_bd_act
ASSETS = ['us_eq', 'intl_eq', 'us_agg', 'intl_bd', 'us_hy', 'us_muni'] + ACT_FUNDS + PRIVS + ['cash']
idx = {a: i for i, a in enumerate(ASSETS)}
ACTIVE = ACT_FUNDS + PRIVS
ACTVEC = np.array([1.0 if a in ACTIVE else 0.0 for a in ASSETS])
RF = CFG['RF']; RFq = RF / 4; NS, NQ = CFG['NS'], CFG['NQ']
CL = np.array([CFG['cpriv'] if a in PRIVS else 0.0 for a in ASSETS])
_FACTOR_OF = {'us_agg': 'US_BD', 'intl_bd': 'INTL_BD', 'us_hy': 'HY', 'us_muni': 'MUNI',
              'us_eq': 'US_EQ', 'intl_eq': 'INTL_EQ'}

def set_cost(eps, wcap):
    return np.array([eps + (CFG['privates'][a]['premium'] / (2 * wcap) if a in PRIVS else 0.0) for a in ASSETS])
_cost = next(c for c in CFG['cost_candidates'] if c[0] == CFG['cost_use'])
ET = set_cost(_cost[1], _cost[2])

def make_scenario(seed):
    F = np.random.default_rng(seed).multivariate_normal(FMEAN / 4, np.outer(FVOL / 2, FVOL / 2) * FCORR, size=(NS, NQ))
    GEQ = 0.6 * F[:, :, fi['US_EQ']] + 0.4 * F[:, :, fi['INTL_EQ']]
    thr = np.percentile(GEQ, CFG['gate']['stress_pctile']); REG = (GEQ < thr).astype(float)
    gu = np.random.default_rng(seed + 1).uniform(0, 1, (NS, NQ)); PEN = np.zeros((NS, NQ)); cum = np.zeros(NS)
    g = CFG['gate']
    for t in range(NQ):
        st = REG[:, t] > 0.5; p = np.where(st, g['p_stress'] / 4, g['p_normal'] / 4); k = np.where(st, g['k_stress'], g['k_normal'])
        on = (gu[:, t] < p); ch = np.minimum(k * on, np.maximum(g['cap'] - cum, 0)); PEN[:, t] = ch; cum += ch
    rng = np.random.default_rng(seed + 2)
    N = {a: rng.normal(0, 1, (NS, NQ)) for a in ACT_FUNDS + PRIVS}       # tracking-error noise per active holding
    CASHN = np.random.default_rng(seed + 30).normal(0, 1, (NS, NQ))
    TH = {a: np.random.default_rng(seed + 10 + i).normal(0, 1, (NS, 1)) * CFG['prem_sigma'][a] for i, a in enumerate(PRIVS)}
    def beta_ret(spec):
        r = np.zeros((NS, NQ))
        for k_, v in spec.items():
            r = r + v * (GEQ if k_ == 'GEQ' else RFq if k_ == 'RF' else F[:, :, fi[k_]])
        return r
    B = {a: beta_ret(CFG['privates'][a]['beta']) for a in PRIVS}
    return dict(F=F, GEQ=GEQ, PEN=PEN, N=N, CASHN=CASHN, TH=TH, B=B)

def build(scn, alpha_scale=1.0, te_scale=1.0, eq_bump=0.0, prem_mult=None):
    pm = prem_mult or {}; F = scn['F']
    SYS = {a: F[:, :, fi[_FACTOR_OF[a]]] for a in ('us_eq', 'intl_eq', 'us_agg', 'intl_bd', 'us_hy', 'us_muni')}
    ACTc = {a: np.zeros((NS, NQ)) for a in ASSETS}
    for a, sp in CFG['active'].items():
        SYS[a] = F[:, :, fi[sp['factor']]]
        bump = eq_bump if a == 'us_eq_act' else 0.0
        ACTc[a] = (alpha_scale * sp['alpha'] + bump) / 4 + te_scale * (sp['te'] / 2) * scn['N'][a]
    for a in PRIVS:
        sp = CFG['privates'][a]
        SYS[a] = scn['B'][a] + (alpha_scale * sp['premium'] * pm.get(a, 1.0) + scn['TH'][a]) / 4 - sp['gate'] * scn['PEN']
        ACTc[a] = te_scale * (sp['te'] / 2) * scn['N'][a]
    SYS['cash'] = np.full((NS, NQ), RFq) + (CFG['cash_vol'] / 2) * scn['CASHN']
    TOT = np.stack([SYS[a] + ACTc[a] for a in ASSETS], 2)
    REP = {a: SYS[a] for a in ASSETS}
    for a in PRIVS: REP[a] = scn['B'][a]                                  # private replica = pure beta
    EXC = np.stack([SYS[a] + ACTc[a] - REP[a] for a in ASSETS], 2)        # factor-adjusted alpha component
    return TOT, EXC

# ---- utilities ---------------------------------------------------------------------------------
def ceq(W, g):
    W = np.maximum(W, 1e-9)
    if abs(g - 1.0) < 1e-9: return float(np.exp(np.mean(np.log(W))))
    m = float(np.mean(W ** (1.0 - g))); return 1e-9 if m <= 0 else m ** (1.0 / (1.0 - g))
def crra(W, g):
    W = np.maximum(W, 1e-9)
    return float(np.mean(np.log(W))) if abs(g - 1.0) < 1e-9 else float(np.mean(W ** (1.0 - g) / (1.0 - g)))
def uref(EW, g):                                                      # CRRA utility evaluated at the mean (Jensen ref)
    EW = max(EW, 1e-9)
    return np.log(EW) if abs(g - 1.0) < 1e-9 else EW ** (1.0 - g) / (1.0 - g)
def negw(mode, w, TOT, EXC, gP, gA, et=None):
    et = ET if et is None else et
    d = (CL @ w + (et * w) @ w) / 4
    Wt = np.prod(1 + TOT @ w - d, 1)
    if mode == 'overlay':                                                 # Modified VAAM (v33): Jensen-gap risk penalty
        WA = np.prod(1 + TOT @ (w * ACTVEC), 1); EWA = WA.mean()
        return -(crra(Wt, gP) + (crra(WA, gA) - uref(EWA, gA)))           # gA=1 -> log branch (no div-by-zero)
    if mode == 'cobb':                                                    # Cobb-Douglas CE-bundle
        WA = np.prod(1 + TOT @ (w * ACTVEC), 1)
        return -(ceq(Wt, gP) ** CFG['THETA'] * ceq(WA, gA) ** (1 - CFG['THETA']))
    if mode == 'wam':                                                     # WAM: additive CRRA on active EXCESS, passive-only W_P
        PM = 1.0 - ACTVEC
        WP = np.prod(1 + TOT @ (w * PM) - d, 1); WAe = np.prod(1 + EXC @ w, 1)
        return -(crra(WP, gP) + crra(WAe, gA))
    Wp = np.prod(1 + (TOT - EXC) @ w - d, 1); Wa = np.prod(1 + EXC @ w, 1)  # vaam: additive systematic + alpha CRRA
    return -(crra(Wp, gP) + crra(Wa, gA))

# ---- home-bias tie + reduced-dimension SLSQP multi-start --------------------------------------
# We optimise ONLY the free (non-zero) assets, deriving intl_eq from the 60/40 US home-bias tie.
# This keeps the QP fully linearly-constrained with no variables pinned at (0,0) — SLSQP is robust
# to that, whereas optimising the full 14-vector with (0,0) bounds makes it report "constraints
# incompatible" and return the seed unchanged.
_R = 0.4 / 0.6                                                     # intl equity total = 40/60 of US equity total
def _intl(x, pos):                                                 # derived passive intl-equity weight
    s = x[pos['us_eq']]
    if 'us_eq_act' in pos: s = s + x[pos['us_eq_act']]
    return _R * s - (x[pos['intl_eq_act']] if 'intl_eq_act' in pos else 0.0)
def _tofull(x, free, pos):
    w = np.zeros(len(ASSETS))
    for k, a in enumerate(free): w[idx[a]] = max(x[k], 0.0)
    w[idx['intl_eq']] = max(_intl(x, pos), 0.0)
    return w
def _msolve(objf, free, hi=None, extra=None, seeds_x=None, maxiter=300):
    """Minimise objf(full_w) over the reduced free-weight vector x>=0. Home-bias-tied intl_eq is
    derived (not a variable); sum(w)=1 and every cap are linear in x. `extra` constraints are given
    on the full w and remapped. Returns the best full 14-vector (or None)."""
    hi = hi or {}; extra = extra or []; pos = {a: k for k, a in enumerate(free)}
    bnds = [(0.0, hi.get(a, 1.0)) for a in free]
    cons = [{'type': 'eq', 'fun': lambda x: x.sum() + _intl(x, pos) - 1.0},
            {'type': 'ineq', 'fun': lambda x: _intl(x, pos)}]                       # intl_eq >= 0
    for c in extra:
        cons.append({'type': c['type'], 'fun': (lambda cc: (lambda x: cc['fun'](_tofull(x, free, pos))))(c)})
    f = lambda x: objf(_tofull(x, free, pos)); best = None
    for x0 in (seeds_x or []):
        x0 = np.clip(np.asarray(x0, float), 0, [b[1] for b in bnds]); s = x0.sum() + max(_intl(x0, pos), 0.0)
        if s > 0: x0 = x0 / s
        r = minimize(f, x0, method='SLSQP', bounds=bnds, constraints=cons, options={'maxiter': maxiter, 'ftol': 1e-10})
        w = _tofull(r.x, free, pos); sm = w.sum()
        if sm <= 0: continue
        w = w / sm; fv = objf(w)
        if best is None or fv < best[0]: best = (fv, w)
    return best[1] if best is not None else None
def solve(mode, TOT, EXC, gP, gA, free, et=None, warm=None, nstarts=4, maxiter=300):
    objf = lambda w: negw(mode, w, TOT, EXC, gP, gA, et)
    defs = [np.full(len(free), 1.0 / len(free)),
            np.array([0.30 if a == 'us_eq' else 0.15 if a in ('us_agg', 'intl_bd') else 0.05 for a in free]),
            np.array([0.30 if a in PRIVS else 0.05 for a in free]),
            np.array([0.30 if a in ACT_FUNDS else 0.05 for a in free])]
    warm_x = [np.array([wf[idx[a]] for a in free]) for wf in (warm or [])]          # project full warm -> free x
    return _msolve(objf, free, seeds_x=warm_x + defs[:nstarts], maxiter=maxiter)

def roll(w):
    g = lambda a: float(w[idx[a]]) * 100
    eq = g('us_eq') + g('intl_eq') + g('us_eq_act') + g('intl_eq_act')
    bd = g('us_agg') + g('intl_bd') + g('us_hy') + g('us_muni') + g('us_bd_act')
    act = sum(g(a) for a in ACT_FUNDS); pr = sum(g(a) for a in PRIVS); ca = g('cash')
    pub = 100 - pr - ca
    return dict(equity=round(eq, 1), bonds=round(bd, 1), active=round(act, 1), privates=round(pr, 1), cash=round(ca, 1),
                acteq_share=round((g('us_eq_act') + g('intl_eq_act')) / max(eq, 1e-9) * 100, 1),
                eq_active=round(g('us_eq_act') + g('intl_eq_act'), 1), bd_active=round(g('us_bd_act'), 1),
                pass_eq=round(g('us_eq') + g('intl_eq'), 1), pub_active_share=round(act / max(pub, 1e-9) * 100, 1))
WD = lambda w: {a: round(float(w[idx[a]]), 4) for a in ASSETS}
PAS = ['us_eq', 'us_agg', 'intl_bd', 'us_hy', 'us_muni', 'cash']; PUB = PAS + ACT_FUNDS; ALL = PUB + PRIVS

# ═══════════════════════════════════════════════════════════════════════════════════════════
#  PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════════════════
UT_NAME = {'overlay': 'Modified VAAM (v33)', 'vaam': 'VAAM', 'cobb': 'Cobb-Douglas', 'wam': 'WAM (excess baseline)'}
UT_FILE = {'overlay': 'v33_overlay_results.json', 'vaam': 'vaam_overlay_results.json',
           'cobb': 'cobb_overlay_results.json', 'wam': 'wam_overlay_results.json'}
GA_CAL = {'overlay': [0.05, 0.1, 0.2, 0.35, 0.6, 1.0, 2.0], 'cobb': [0.02, 0.05, 0.1, 0.2, 0.35, 0.6, 1.0],
          'vaam': [0.5, 1.5, 2.0, 3.0, 5.0, 8.0, 15.0, 30.0], 'wam': [0.05, 0.1, 0.2, 0.5, 1.0, 2.0]}
GA_SWEEP = {'overlay': [0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0], 'cobb': [0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 4.0],
            'vaam': [0.5, 1.5, 2.0, 3.0, 5.0, 9.0, 18.0], 'wam': [0.05, 0.1, 0.2, 0.5, 1.0, 2.0]}
PRAG = [1.5, 2.0, 2.85, 4.0, 6.0, 9.0]; SCG = [0.5, 0.75, 1.0, 1.25, 1.5]
OPTLABEL = 'SLSQP multi-start (scipy)'
def maxjump(rows, keys=('equity', 'active', 'privates')):
    return round(max((sum(abs(rows[i][k] - rows[i - 1][k]) for k in keys) for i in range(1, len(rows))), default=0.0), 1)
def calib_gamP(mode, TOT, EXC):
    grid = [1.5, 2.0, 2.5, 2.85, 3.5, 4.5, 6.0, 8.0]; best = None
    for gp in grid:
        r = roll(solve(mode, TOT, EXC, gp, GA_CAL[mode][2], PAS, nstarts=1, maxiter=90)); sh = r['equity'] / max(r['equity'] + r['bonds'], 1e-9)
        if best is None or abs(sh - CFG['eqbd_target']) < abs(best[1] - CFG['eqbd_target']): best = (gp, sh)
    return best[0]
def calib_gamA(mode, TOT, EXC, gamP):
    cand = [(ga, roll(solve(mode, TOT, EXC, gamP, ga, PUB, nstarts=1, maxiter=90))['pub_active_share']) for ga in GA_CAL[mode]]
    return min(cand, key=lambda x: abs(x[1] - CFG['active_target']))[0]

def run_utility(mode, scn):
    TOT0, EXC0 = build(scn)
    gamP = calib_gamP(mode, TOT0, EXC0); gamA = calib_gamA(mode, TOT0, EXC0, gamP)
    # cost-floor scan (informational; use CFG['cost_use'])
    scan = []; scan_ga = 0.1 if mode in ('overlay', 'cobb', 'wam') else 5.0
    for name, eb, wc in CFG['cost_candidates']:
        et = set_cost(eb, wc)
        w1 = solve(mode, TOT0, EXC0, gamP, scan_ga, ALL, et=et, nstarts=1, maxiter=120)
        r1 = roll(w1); mp = max(w1[idx[a]] * 100 for a in PRIVS)
        stable = (mp < 40 and r1['privates'] < 60)
        scan.append(dict(name=name, eps=eb, wcap=wc, eta_pi=round(eb + CFG['privates']['pi']['premium'] / (2 * wc), 4),
                         maxpriv=round(mp, 1), privates=r1['privates'], uniq_l1=0.0, stable=bool(stable)))
    wbase = solve(mode, TOT0, EXC0, gamP, gamA, ALL, nstarts=3, maxiter=160); rbase = roll(wbase)
    def sweep_g(which, grid):
        out = []; prev = wbase
        for gv in grid:
            gp, ga = (gv, gamA) if which == 'PRA' else (gamP, gv)
            w = solve(mode, TOT0, EXC0, gp, ga, ALL, warm=[prev, wbase], nstarts=0, maxiter=120); out.append(roll(w)); prev = w
        return out
    def sweep_s(kind, grid):
        out = []; prev = wbase
        for f in grid:
            T, E = build(scn, alpha_scale=f) if kind == 'alpha' else build(scn, te_scale=f)
            w = solve(mode, T, E, gamP, gamA, ALL, warm=[prev, wbase], nstarts=0, maxiter=120); out.append(roll(w)); prev = w
        return out
    sw = dict(PRA=(PRAG, sweep_g('PRA', PRAG)), ARA=(GA_SWEEP[mode], sweep_g('ARA', GA_SWEEP[mode])),
              alpha=(SCG, sweep_s('alpha', SCG)), TE=(SCG, sweep_s('TE', SCG)))
    Tn, En = build(scn, eq_bump=0.005); wn = solve(mode, Tn, En, gamP, gamA, ALL, warm=[wbase], nstarts=0, maxiter=120)
    nud = round(float(np.abs(wn - wbase).sum() * 100), 1)
    out = dict(config=dict(utility=mode, utility_label=UT_NAME[mode], gamP=round(gamP, 2), gamA=round(gamA, 3),
        theta=(CFG['THETA'] if mode == 'cobb' else None), eps_base=_cost[1], wcap=_cost[2], cost_label=_cost[0],
        active_target=CFG['active_target'], optimizer=OPTLABEL, n_sims=NS, n_quarters=NQ,
        note='%s; SLSQP multi-start; gamP->60/40 (passive), gamA->70/30 (public); %s cost floor; incl intl_eq_act' % (UT_NAME[mode], _cost[0])),
        cost_scan=scan, base=dict(gamP=round(gamP, 2), gamA=round(gamA, 3), roll=rbase, weights=WD(wbase)),
        sens={k: dict(x=g, rows=r, maxjump=maxjump(r)) for k, (g, r) in sw.items()},
        spike=dict(nudge_50bp_eqalpha=nud, nudge_mix=WD(wn)))
    json.dump(out, open(os.path.join(RES, UT_FILE[mode]), 'w'), indent=1)
    log('  %-9s gamP=%.2f gamA=%.3f  base: eq %.0f active %.0f priv %.0f bonds %.0f  nudge %.1f' % (
        mode, gamP, gamA, rbase['equity'], rbase['active'], rbase['privates'], rbase['bonds'], nud))
    return gamP, gamA

def run_compare_calib(gams):
    scn = make_scenario(CFG['SEED']); TOT, EXC = build(scn); OUT = {}
    g = lambda w, a: float(w[idx[a]]) * 100
    for mode in CFG['utilities']:
        gP, gA = gams[mode]
        wp = solve(mode, TOT, EXC, gP, gA, PAS, nstarts=2, maxiter=200); wu = solve(mode, TOT, EXC, gP, gA, PUB, nstarts=2, maxiter=200)
        eqp = g(wp, 'us_eq') + g(wp, 'intl_eq'); bdp = sum(g(wp, a) for a in ('us_agg', 'intl_bd', 'us_hy', 'us_muni')); cap = g(wp, 'cash')
        equ = sum(g(wu, a) for a in ('us_eq', 'intl_eq', 'us_eq_act', 'intl_eq_act')); bdu = sum(g(wu, a) for a in ('us_agg', 'intl_bd', 'us_hy', 'us_muni', 'us_bd_act'))
        act = sum(g(wu, a) for a in ACT_FUNDS); pasv = 100 - act - g(wu, 'cash')
        OUT[mode] = dict(gamP=gP, gamA=gA,
            passive=dict(equity=round(eqp, 1), bonds=round(bdp, 1), cash=round(cap, 1), eq_share=round(eqp / max(eqp + bdp, 1e-9) * 100, 1)),
            public=dict(equity=round(equ, 1), bonds=round(bdu, 1), active=round(act, 1), passive_idx=round(pasv, 1),
                        eq_share=round(equ / max(equ + bdu, 1e-9) * 100, 1), active_share=round(act / max(act + pasv, 1e-9) * 100, 1),
                        acteq_share=round((g(wu, 'us_eq_act') + g(wu, 'intl_eq_act')) / max(equ, 1e-9) * 100, 1)))
    json.dump(OUT, open(os.path.join(RES, 'compare_calib.json'), 'w'), indent=1); log('  compare_calib written')

def run_stability(gams):
    MODES = CFG['utilities']; sc0 = make_scenario(CFG['SEED']); TOT0, EXC0 = build(sc0)
    GAMP = 2.85; et = set_cost(0.001, 0.20)
    GA = {}; WBASE = {}
    for m in MODES:                                              # re-calibrate gamA on the FULL book (fair, common cost)
        cand = [(ga, roll(solve(m, TOT0, EXC0, GAMP, ga, ALL, et=et, nstarts=2, maxiter=200))['pub_active_share']) for ga in GA_CAL[m]]
        GA[m] = min(cand, key=lambda x: abs(x[1] - 70.0))[0]
        WBASE[m] = solve(m, TOT0, EXC0, GAMP, GA[m], ALL, et=et, nstarts=3, maxiter=250)
    L1 = lambda a, b: float(np.abs(np.asarray(a) - np.asarray(b)).sum() * 100)
    def fm(**kw):                                                # factor-mean multiplier vector (1.0 except the shocked factors)
        v = np.ones(len(FACT))
        for f, x in kw.items(): v[fi[f]] = x
        return v
    A = {m: [] for m in MODES}
    BUILD_SHOCKS = [('alpha/premia +10%', dict(alpha_scale=1.1)), ('alpha/premia -10%', dict(alpha_scale=0.9)),
        ('all TE +10%', dict(te_scale=1.1)), ('all TE -10%', dict(te_scale=0.9)), ('+50bp eq-alpha', dict(eq_bump=0.005)),
        ('PI premium +10%', dict(prem_mult={'pi': 1.1})), ('PI premium -10%', dict(prem_mult={'pi': 0.9})),
        ('PCDL premium +10%', dict(prem_mult={'pcdl': 1.1})), ('PCDL premium -10%', dict(prem_mult={'pcdl': 0.9}))]
    for lbl, kw in BUILD_SHOCKS:
        T, E = build(sc0, **kw)
        for m in MODES: A[m].append((lbl, L1(solve(m, T, E, GAMP, GA[m], ALL, et=et, warm=[WBASE[m]], nstarts=1, maxiter=200), WBASE[m])))
    REGEN = [('eq factor mean +5%', dict(US_EQ=1.05, INTL_EQ=1.05)), ('eq factor mean -5%', dict(US_EQ=0.95, INTL_EQ=0.95)),
             ('bond factor mean +10%', dict(US_BD=1.10)), ('HY factor mean +10%', dict(HY=1.10))]
    for lbl, mm in REGEN:
        global FMEAN; base_fm = FMEAN.copy(); FMEAN = base_fm * fm(**mm); scS = make_scenario(CFG['SEED']); T, E = build(scS); FMEAN = base_fm
        for m in MODES: A[m].append((lbl, L1(solve(m, T, E, GAMP, GA[m], ALL, et=et, warm=[WBASE[m]], nstarts=1, maxiter=200), WBASE[m])))
    Bw = {m: [] for m in MODES}
    for ms in [11, 22, 33, 44, 55, 66]:
        scK = make_scenario(ms); Tk, Ek = build(scK)
        for m in MODES: Bw[m].append(solve(m, Tk, Ek, GAMP, GA[m], ALL, et=et, warm=[WBASE[m]], nstarts=1, maxiter=200))
    Bdisp = {}
    for m in MODES:
        W = np.array(Bw[m]); cen = W.mean(0)
        Bdisp[m] = dict(mean_L1_from_centroid=round(float(np.mean([L1(w, cen) for w in W])), 1),
                        worst_asset_sd=round(float(W.std(0).max() * 100), 1), priv_sd=round(float(W[:, [idx[a] for a in PRIVS]].sum(1).std() * 100), 1))
    STARTS = [WBASE[MODES[0]]] + [np.random.default_rng(s).uniform(0, 1, len(ASSETS)) for s in range(4)]   # full 14-vectors
    Cuniq = {}
    for m in MODES:
        sols = [solve(m, TOT0, EXC0, GAMP, GA[m], ALL, et=et, warm=[s], nstarts=0, maxiter=200) for s in STARTS]
        Cuniq[m] = round(float(max(L1(sols[i], sols[j]) for i in range(len(sols)) for j in range(i + 1, len(sols)))), 1)
    sc_ = {m: dict(A_mean=round(float(np.mean([v for _, v in A[m]])), 1), A_max=round(float(np.max([v for _, v in A[m]])), 1),
                   B_disp=Bdisp[m]['mean_L1_from_centroid'], B_privSD=Bdisp[m]['priv_sd'], C_uniq=Cuniq[m]) for m in MODES}
    out = dict(config=dict(NS=NS, cost='moderate eps=0.001 wcap=0.20', gamP=GAMP, gamA={m: round(GA[m], 3) for m in MODES}, theta=CFG['THETA']),
               names={m: UT_NAME[m] for m in MODES}, A_shocks={m: A[m] for m in MODES}, B_sampling=Bdisp, C_uniqueness=Cuniq, scorecard=sc_)
    json.dump(out, open(os.path.join(RES, 'stability_results.json'), 'w'), indent=1)
    log('  stability written: ' + ' | '.join('%s A=%.1f' % (m, sc_[m]['A_mean']) for m in MODES))

# ---- persona tax ladder (P1 passive / P2 +active / P3 full pre-tax / P4 full after-tax) --------
def _inc_rate(tt):
    return {'income': CFG['tax']['income'], 'dividend': CFG['tax']['dividend'], 'exempt': 0.0, 'cg_heavy': CFG['tax']['dividend']}[tt]
def w0_persona(policy_eq):
    w = np.zeros(len(ASSETS))
    w[idx['us_eq']] = policy_eq * 0.70; w[idx['intl_eq']] = policy_eq * 0.30; b = 1 - policy_eq
    w[idx['us_agg']] = b * 0.50; w[idx['intl_bd']] = b * 0.20; w[idx['us_hy']] = b * 0.15; w[idx['us_muni']] = b * 0.15
    return w
def run_personas():
    mode = CFG['persona_utility']; seeds = CFG['persona_seeds']
    cg = CFG['tax']['cap_gains']; INC = {a: _inc_rate(CFG['tax_types'][a]) for a in ASSETS}
    IY = np.array([CFG['income_yield'].get(a, 0.0) / 4 for a in ASSETS])
    SCN = [make_scenario(s) for s in seeds]
    def seed_returns(tax):
        out = []
        for scn in SCN:
            TOT, EXC = build(scn)
            if tax:
                price = TOT - IY[None, None, :]; R = IY[None, None, :] * (1 - np.array([INC[a] for a in ASSETS]))[None, None, :] + price * (1 - cg)
                Re = EXC * (1 - cg)                                   # excess taxed at cap-gains
            else:
                R, Re = TOT, EXC
            out.append((R, Re))
        return out
    _cache = {}
    def rets(tax):
        if tax not in _cache: _cache[tax] = seed_returns(tax)
        return _cache[tax]
    def pobj(w, gP, gA, tax):
        return float(np.mean([negw(mode, w, R, Re, gP, gA) for R, Re in rets(tax)]))
    def pobj1(w, gP, gA, tax):                                    # single-seed (fast) for calibration
        R, Re = rets(tax)[0]; return negw(mode, w, R, Re, gP, gA)
    C = CFG['caps']; FREE = {'passive': PAS, 'active': PUB, 'full': ALL}
    def psolve(gP, gA, tax, opp, policy_eq, starts=None, objf=None, maxiter=250, nseed=2):
        of = objf or pobj; fobj = lambda w: of(w, gP, gA, tax)
        free = FREE[opp]; hi = {a: C['private'] for a in PRIVS}
        extra = []
        if opp in ('active', 'full'):
            extra.append({'type': 'ineq', 'fun': lambda w: C['active'] - sum(w[idx[a]] for a in ACT_FUNDS)})
        if opp == 'full':
            ce, cb = C['funding'] * policy_eq, C['funding'] * (1 - policy_eq)
            extra.append({'type': 'ineq', 'fun': lambda w: ce - (w[idx['pe']] + w[idx['pre']] + w[idx['pi']])})
            extra.append({'type': 'ineq', 'fun': lambda w: cb - w[idx['pcdl']]})
        w0 = w0_persona(policy_eq); projd = lambda wf: np.array([wf[idx[a]] for a in free])
        defaults = [projd(w0), projd(np.where([a in PRIVS for a in ASSETS], C['private'], w0))]
        seeds_x = [projd(np.asarray(s, float)) for s in (starts or [])] + defaults[:nseed]
        w = _msolve(fobj, free, hi=hi, extra=extra, seeds_x=seeds_x, maxiter=maxiter)
        return w if w is not None else w0
    priv = lambda w: sum(w[idx[a]] for a in PRIVS)
    # homotopy: warm-start each SLSQP from the previous bisection point so it converges in ~5 iters, not ~40
    def calib_PRA(policy_eq):
        lo, hi = 0.3, 30.0; wp = None
        for _ in range(14):
            g = 0.5 * (lo + hi)
            w = psolve(g, 1.0, False, 'passive', policy_eq, starts=([wp] if wp is not None else None),
                       objf=pobj1, maxiter=120, nseed=(0 if wp is not None else 2)); wp = w
            e = w[idx['us_eq']] + w[idx['intl_eq']]
            if abs(e - policy_eq) < 0.005: break
            lo, hi = (g, hi) if e > policy_eq else (lo, g)
        return g
    def calib_ARA(dP):
        lo, hi = 0.005, 5.0; wp = None
        for _ in range(16):
            g = 0.5 * (lo + hi)
            w = psolve(dP, g, False, 'full', 0.70, starts=([wp] if wp is not None else None),
                       objf=pobj1, maxiter=120, nseed=(0 if wp is not None else 2)); wp = w
            if abs(priv(w) - 0.20) < 0.006: break
            lo, hi = (g, hi) if priv(w) > 0.20 else (lo, g)
        return g
    PRA = {eq: calib_PRA(eq) for eq in sorted({p[2] for p in CFG['personas']})}
    for eq in PRA: log('  PRA(eq=%.2f)=%.2f' % (eq, PRA[eq]))
    ARA_C = calib_ARA(PRA[0.70]); log('  ARA_C(L0->20%% priv)=%.3f' % ARA_C)
    def summ(w):
        d = {a: float(w[idx[a]]) for a in ASSETS}
        pub_eq = d['us_eq'] + d['intl_eq'] + d['us_eq_act'] + d['intl_eq_act']
        return dict(weights=d, pub_eq=pub_eq, us_eq_share=((d['us_eq'] + d['us_eq_act']) / pub_eq if pub_eq > 1e-9 else 0),
                    bonds=d['us_agg'] + d['intl_bd'] + d['us_hy'] + d['us_muni'] + d['us_bd_act'], muni=d['us_muni'],
                    active=sum(d[a] for a in ACT_FUNDS), priv=priv(w), BO=d['pe'], PRE=d['pre'], PI=d['pi'], PCDL=d['pcdl'])
    OUT = dict(seeds=seeds, bracket={'income': CFG['tax']['income'], 'div': CFG['tax']['dividend'], 'cg': cg},
               PRA_by_eq={str(k): v for k, v in PRA.items()}, ARA_C=ARA_C, lp_timing='before_tax_capital_bucket',
               tax_types=CFG['tax_types'], optimizer=dict(optimizer=OPTLABEL, n_sims=NS, n_quarters=NQ, seeds=seeds,
                   effective_paths=NS * len(seeds), objective='%s persona ladder' % UT_NAME[mode]),
               income_rate_by_asset={a: INC[a] for a in ASSETS},
               port_order=['P1_passive_pre', 'P1_passive_post', 'P2_active_pre', 'P2_active_post', 'P3_full_pre', 'P4_full_post'], personas={})
    warm = {}                                                     # homotopy warm start per opportunity set
    def book(dP, dA, tax, opp, eq):
        w0 = warm.get(opp)
        w = psolve(dP, dA, tax, opp, eq, starts=([w0] if w0 is not None else None),
                   objf=pobj, maxiter=200, nseed=(0 if w0 is not None else 2))
        warm[opp] = w; return w
    for name, mult, eq, lam in CFG['personas']:
        dP, dA = PRA[eq], ARA_C * mult
        ports = {'P1_passive_pre': book(dP, dA, False, 'passive', eq), 'P1_passive_post': book(dP, dA, True, 'passive', eq),
                 'P2_active_pre': book(dP, dA, False, 'active', eq), 'P2_active_post': book(dP, dA, True, 'active', eq),
                 'P3_full_pre': book(dP, dA, False, 'full', eq), 'P4_full_post': book(dP, dA, True, 'full', eq)}
        OUT['personas'][name] = dict(policy_eq=eq, ara_mult=mult, lam=lam, pmult=lam / 0.005, PRA=dP, ARA=dA,
                                     ports={k: summ(v) for k, v in ports.items()})
        log('  %-24s PRA %.2f ARA %.3f  P3 priv %.0f%% P4 priv %.0f%%' % (name, dP, dA, priv(ports['P3_full_pre']) * 100, priv(ports['P4_full_post']) * 100))
    json.dump(OUT, open(os.path.join(RES, 'persona_4portfolios_v33.json'), 'w'), indent=1)

def run_all():
    log('PrivAlloc — utilities %s; personas under %s (%s)' % (CFG['utilities'], CFG['persona_utility'], UT_NAME[CFG['persona_utility']]))
    scn = make_scenario(CFG['SEED']); gams = {}
    for m in CFG['utilities']: gams[m] = run_utility(m, scn)
    run_compare_calib(gams); run_stability(gams); run_personas()
    log('DONE -> results/   (now run: python3 dashboard.py)')

if __name__ == '__main__':
    run_all()
