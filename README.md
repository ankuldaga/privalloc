# PrivAlloc — private-asset allocation engine + dashboard

A self-contained package that solves a two-wealth (passive / active) allocation problem
under a **toggleable utility formulation**, runs the full case set, and renders it as one
offline HTML dashboard. numpy + scipy only — no JAX, no data downloads, no internet.

```
privalloc/
├── engine.py                 ← the optimiser. Edit CONFIG, run it. Writes results/*.json
├── dashboard.py              ← reads results/*.json, writes PrivAlloc_Dashboard.html
├── mathjax.js                ← vendored MathJax (so the dashboard renders equations offline)
├── results/                  ← generated JSON (+ faj_v26_results.json, a static paper reference)
├── PrivAlloc_Dashboard.html  ← the pre-built dashboard — open this directly, no run needed
└── README.md
```

Five things to email: the three source files, `results/`, and the pre-built HTML. Just want to *look*
at it? Open `PrivAlloc_Dashboard.html` — it is self-contained. Want to *change* something? Edit
`engine.py`'s `CONFIG`, re-run the two commands below.

## Run it (two commands)

```bash
python3 engine.py        # full run: calibrates, solves every case, writes results/
python3 dashboard.py     # ~2 s: builds PrivAlloc_Dashboard.html  (open in any browser)
```

Requirements: Python 3.9+, `numpy`, `scipy`. Nothing else.

**Runtime.** A full `engine.py` run (3 utilities + stability battery + 7-persona ladder, each solved
from multiple starts over `NS` Monte-Carlo paths) takes roughly **~15 min** on a laptop at the shipped
`NS=2000`. Raising `NS` to `4000`–`6000` sharpens the numbers by ~1-2% but is much slower — the high-risk-
aversion VAAM solves in the stability battery scale badly, so a 6000 run can take well over an hour.
`dashboard.py` itself is ~2 s. The shipped `results/*.json` and `PrivAlloc_Dashboard.html` are already
built — you only need to re-run if you change `CONFIG`.

## Toggle the utility formulation

Everything is driven by the `CONFIG` dict at the top of `engine.py`.

```python
utilities       = ['overlay', 'vaam', 'cobb']   # which formulations to compare in Stream 1
persona_utility = 'overlay'                      # which one drives the personas (Stream 2)
```

The four formulations (all over passive wealth `W_p` and active wealth `W_a`):

| key       | name                | objective |
|-----------|---------------------|-----------|
| `overlay` | Modified VAAM (v33) | single CRRA on total wealth at γ_P **plus** a Jensen-gap risk penalty on active total wealth at γ_A |
| `vaam`    | VAAM (JPM 2020)     | additive CRRA: `E[u(W_p;γ_P)] + E[u(W_a;γ_A)]`, W_p = systematic β·r, W_a = factor-adjusted alpha |
| `cobb`    | Cobb-Douglas        | certainty-equivalent bundle `CE_P^θ · CE_A^(1-θ)` (θ = `THETA`) |
| `wam`     | WAM (excess)        | additive CRRA on active **excess** wealth with passive-only W_P (baseline; degenerate → ~0% active) |

Set `persona_utility` to any of these and re-run — the persona ladder, tax sleeves and the
Stream-2 tabs all rebuild under that formulation.

## Give it the inputs

Also in `CONFIG`:

- **`factors`** — annual arithmetic mean / vol for each systematic factor, plus `factor_corr`.
- **`active`** — manager `alpha` / tracking-error `te` per active public fund, and the factor it tracks.
  Ships with `us_eq_act`, **`intl_eq_act`** (β=1 vs international equity, same α/TE as US active), `us_bd_act`.
- **`privates`** — illiquidity `premium`, `te`, gating `gate`, and the systematic `beta` replica per private sleeve (BO / PRE / PI / PCDL).
- **`gate`** — the conditional liquidity-penalty (onset-charged) parameters.
- **`personas`** — `(name, ARA multiplier, policy equity, liquidity-aversion λ)` per case.
- **`caps`**, **`home_bias`**, **`tax`**, **`income_yield`** — sleeve caps, the 60/40 US home-bias tie, and the tax ladder.

## Calibration (automatic)

Two risk-aversion anchors are calibrated by bisection each run:

- **γ_P** → the passive book hits the equity/bond target (`eqbd_target`, default 60/40).
- **γ_A** → the public book hits the active/passive target (`active_target`, default 70/30).

The personas then re-anchor **γ_P per policy-equity** and set **γ_A** so the central case lands at ~20% privates.

## Asset universe (14)

6 passive (`us_eq, intl_eq, us_agg, intl_bd, us_hy, us_muni`) · 3 active
(`us_eq_act, intl_eq_act, us_bd_act`) · 4 private (`pe, pre, pi, pcdl`) · `cash`.
International equity is tied to US equity by a 60/40 home-bias rule, so US equity is always
≥ 60% of total equity.

## Optimiser

scipy **SLSQP multi-start** over the reduced free-weight vector (disallowed sleeves are dropped
from the problem, not pinned at zero, so the QP stays well-posed). Each book runs several restarts
plus a homotopy warm-start carried from the previous solve; the sweeps and the persona ladder warm-start
off the base book. `NS` Monte-Carlo paths × `NQ` quarters, pooled over the persona seeds.
This reproduces the capped-vertex optima of the original JAX/CMA-ES research build without the
heavy dependencies.

## Output

`PrivAlloc_Dashboard.html` is fully self-contained (MathJax inlined, no external requests) — email it,
open it offline, it just works. Two streams: **Stream 1** compares the three utility formulations and
stress-tests their stability; **Stream 2** is the persona ladder under the production formulation, with a
before/after-tax toggle, the portfolio ladder, and the tax sleeves.
