#!/usr/bin/env python3
"""Build the PrivAlloc dashboard from the results/ JSONs that engine.py writes.

Data source (all under results/, written by engine.py):
  - persona_4portfolios_v33.json : per-persona ladder of six portfolios over one
    14-asset opportunity set —
        P1 Passive (pre / after-tax)  -> anchors PRA to the policy eq/bd split
        P2 +Active (pre / after-tax)  -> introduces ARA (active overlay; no privates)
        P3/P4 Full  (pre / after-tax) -> add privates; PRA & ARA FIXED, no recalibration
    Multi-seed (42/43/44 pooled); home-bias floor US >= 60% of public equity on every book;
    liquidity penalty charged BEFORE tax (capital bucket): R = QI(1-inc) + (QP-LP)(1-cg).
  - v33_overlay / cobb_overlay / vaam_overlay / stability / compare_calib / faj_v26 (reference).
Output: PrivAlloc_Dashboard.html (self-contained; MathJax inlined from mathjax.js).
"""
import json, datetime, html, os
HERE=os.path.dirname(os.path.abspath(__file__)); RES=os.path.join(HERE,'results')
J = os.path.join(RES,'persona_4portfolios_v33.json')  # personas under Modified-VAAM (v33), the most-stable formulation
OUT = os.path.join(HERE,'PrivAlloc_Dashboard.html')
def loadj(p):
    try: return json.load(open(p))
    except Exception: return None
D = json.load(open(J)); _br = D['bracket']; PER = D['personas']
OPT = D.get('optimizer', {})                                              # v33 optimiser metadata
V33O = loadj(os.path.join(RES,'v33_overlay_results.json'))  # overlay-results tab
COBB = loadj(os.path.join(RES,'cobb_overlay_results.json')) # Cobb-Douglas (CE-bundle) overlay
VAAM = loadj(os.path.join(RES,'vaam_overlay_results.json')) # VAAM (total-wealth CRRA + excess-active CRRA)
STAB = loadj(os.path.join(RES,'stability_results.json'))    # 3-way stability scorecard + per-shock L1
CALIB = loadj(os.path.join(RES,'compare_calib.json'))       # public-only calibration books (gamP->60/40, gamA->70/30)
FAJ = loadj(os.path.join(RES,'faj_v26_results.json'))       # conditional-liquidity-penalty cases
BR = {'income': _br['income'], 'dividend': _br.get('dividend', _br.get('div')),
      'cap_gains': _br.get('cap_gains', _br.get('cg'))}
ORDER = ['L0 Legacy Central', 'L1 Legacy - Higher RA', 'L2 Legacy - Lower RA', 'L3 Legacy - Higher LA',
         'L4 Legacy - Lower LA', 'R5 Retirement', 'E6 Education']
PORTS = D['port_order']   # 6 keys
# stage groups: (label, [pre_key, post_key])
GROUPS = [('Passive', ['P1_passive_pre', 'P1_passive_post']),
          ('+ Active', ['P2_active_pre', 'P2_active_post']),
          ('Full (+ privates)', ['P3_full_pre', 'P4_full_post'])]
POSTKEYS = {'P1_passive_post', 'P2_active_post', 'P4_full_post'}

META = {
 'L0 Legacy Central': dict(s='L0', m='Family Legacy Pool ($80m)', r='CENTRAL CASE — anchors the calibration',
   d='UHNW family-office legacy pool, ~2% spending. 70/30 policy; privates take half the active sleeve.',
   t='The calibration hub: PRA set on the passive book to 70/30; ARA set so the pre-tax full book holds ~20% privates.'),
 'L1 Legacy - Higher RA': dict(s='L1', m='Conservative Trust ($25m)', r='Spoke — higher risk aversion',
   d='Irrevocable trust, trustee prudence. Risk aversion x1.6 -> 50/50 policy.',
   t='The 50/50 bond sleeve is large enough that muni survives after tax (taxable bonds vacate).'),
 'L2 Legacy - Lower RA': dict(s='L2', m='Growth Pool ($15m)', r='Spoke — lower risk aversion',
   d="Founder's opportunistic sleeve, 85/15 policy, risk aversion x0.6.",
   t='Low ARA -> all three equity-funded privates sit at their 8% caps; the private total is tax-invariant.'),
 'L3 Legacy - Higher LA': dict(s='L3', m='Foundation Reserve ($20m)', r='Spoke — higher liquidity aversion',
   d='Pre-funds dated grants; illiquidity carries a real shadow price (lambda 150 bps).',
   t='Higher liquidity aversion thins PRE; after tax it thins further.'),
 'L4 Legacy - Lower LA': dict(s='L4', m='Perpetual Pool ($30m)', r='Spoke — lower liquidity aversion',
   d='Outside cash flows cover spending; capital effectively untouchable (lambda 15 bps).',
   t='Near-zero liquidity cost -> the largest private sleeve, and the largest after-tax give-back in PRE.'),
 'R5 Retirement': dict(s='R5', m='Gen-1 retirees ($6m)', r='Goal case — retirement decumulation',
   d='Drawing 4%; decumulation raises both aversions (50/50, ARA x1.6, lambda 150 bps).',
   t='Like L1: a real bond sleeve, so muni appears after tax.'),
 'E6 Education': dict(s='E6', m='Education Trust ($3m)', r='Goal case — education funding',
   d='Funds tuition from ~year 6; dated, non-negotiable outflows (lambda 300 bps).',
   t='High liquidity aversion -> the thinnest private sleeve; PRE nearly gone after tax.'),
}
CMA = {'BO': dict(n='Evergreen buyout (PE)', a=4.1, te=5.1, s=1.25, ir=0.64, c='#5aa9e6'),
       'PRE': dict(n='Private real estate', a=2.1, te=3.5, s=1.15, ir=0.39, c='#f0a868'),
       'PI': dict(n='Private infrastructure', a=2.8, te=3.3, s=1.00, ir=0.78, c='#7ed3a2'),
       'PCDL': dict(n='Private credit (direct lending)', a=3.2, te=3.2, s=0.75, ir=1.00, c='#c79be8')}
KEYS = ['BO', 'PRE', 'PI', 'PCDL']
PMAP = {'BO': 'pe', 'PRE': 'pre', 'PI': 'pi', 'PCDL': 'pcdl'}
esc = lambda s: html.escape(str(s))
def _join(xs):
    xs = list(xs)
    if not xs: return ''
    if len(xs) == 1: return xs[0]
    return ' &amp; '.join(xs) if len(xs) == 2 else ', '.join(xs[:-1]) + ' &amp; ' + xs[-1]
_verb = lambda xs: 'stays' if len(list(xs)) == 1 else 'stay'
_sit = lambda xs: 'sits' if len(list(xs)) == 1 else 'sit'

ASSET_ROWS = [
  ('Equities', [('us_eq', 'US equity'), ('intl_eq', 'Intl equity'), ('us_eq_act', 'US active equity'),
                ('intl_eq_act', 'Intl active equity')]),
  ('Bonds', [('us_agg', 'US bonds'), ('intl_bd', 'Intl bonds'), ('us_hy', 'US high yield'),
             ('us_bd_act', 'US active bond'), ('us_muni', 'US muni'), ('cash', 'Cash')]),
  ('Privates', [('pe', 'BO — buyout'), ('pre', 'PRE — real estate'), ('pi', 'PI — infrastructure'),
                ('pcdl', 'PCDL — direct lending')]),
]
def cell(frac, post, b=False, hl=''):
    v = frac * 100
    txt = ('%.1f' % v) if v > 0.05 else '<span style="color:#4a5160">·</span>'
    cls = 'n' + (' s' if post else '') + (' b' if b else '')
    return f'<td class="{cls}"{hl}>{txt}</td>'

def pill(d):
    c = 'up' if d > 0.05 else ('dn' if d < -0.05 else 'fl')
    return f'<span class="pill {c}">{d:+.1f}</span>'

def legend(items):
    return '<div class="legend">' + ''.join(
        f'<span class="lg"><i style="background:{c}"></i>{esc(n)}</span>' for n, c in items) + '</div>'

def stacked(parts, w=300, h=15, mx=40.0):
    x = 0.0; segs = ''
    for v, c in parts:
        ww = max(0.0, v) / mx * w
        if ww > 0.4: segs += f'<rect x="{x:.1f}" y="0" width="{ww:.1f}" height="{h}" fill="{c}" rx="1"/>'
        x += ww
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{segs}</svg>'

# ---- SVG/tile helpers ported from build_stab_dashboard.py (for the v33 overlay tab) ----
def legend2(items):
    return '<div class="lg2">' + ''.join(
        f'<span><i style="background:{c};{"border-bottom:2px dashed #0f1117" if d else ""}"></i>'
        f'{esc(l)}{" (dashed)" if d else ""}</span>' for l, c, d in items) + '</div>'
def multiline(xs, series, ymax=100, w=430, h=205, xlab='', dash=(), xticks=None, markers=True):
    """series: list of (label, ys, color). Markers carry hover tooltips; end labels in ink."""
    s = f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:auto">'
    x0, x1, y0, y1 = 40, w - 64, 12, h - 30; xmin, xmax = min(xs), max(xs)
    sx = lambda x: x0 + (x - xmin) / (xmax - xmin + 1e-9) * (x1 - x0)
    sy = lambda y: y1 - (min(y, ymax) / ymax) * (y1 - y0)
    for gy in [0, ymax * .25, ymax * .5, ymax * .75, ymax]:
        s += f'<line x1="{x0}" y1="{sy(gy):.1f}" x2="{x1}" y2="{sy(gy):.1f}" stroke="#1e222b"/><text x="8" y="{sy(gy)+3:.1f}" fill="#5b6373" font-size="9">{gy:.0f}</text>'
    for xt in (xticks if xticks is not None else xs):
        s += f'<text x="{sx(xt):.1f}" y="{h-16}" fill="#5b6373" font-size="9" text-anchor="middle">{xt:g}</text>'
    laby = [sy(ys[-1]) for _, ys, _ in series]
    for i in sorted(range(len(laby)), key=lambda k: laby[k]):
        for j in sorted(range(len(laby)), key=lambda k: laby[k]):
            if j != i and 0 <= laby[j] - laby[i] < 11: laby[j] = laby[i] + 11
    for si, (lb, ys, c) in enumerate(series):
        dd = ' stroke-dasharray="5,4"' if lb in dash else ''
        pts = ' '.join('%.1f,%.1f' % (sx(x), sy(y)) for x, y in zip(xs, ys))
        s += f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2"{dd}/>'
        if markers:
            for x, y in zip(xs, ys):
                s += f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.2" fill="{c}"><title>{esc(lb)} @ {x:g}: {y:.1f}%</title></circle>'
        s += f'<text x="{sx(xs[-1])+6:.1f}" y="{laby[si]+3:.1f}" fill="#c9cfda" font-size="9">{esc(lb)}</text>'
    s += f'<text x="{(x0+x1)/2:.0f}" y="{h-4}" fill="#8a93a6" font-size="10" text-anchor="middle">{esc(xlab)}</text>'
    return s + '</svg>'
def tiles(items):
    return '<div class="tiles">' + ''.join(
        f'<div class="tile"><div class="v" style="color:{c}">{esc(v)}</div><div class="l">{esc(l)}</div></div>'
        for v, l, c in items) + '</div>'
def groupbars(labels, series, w=680, rowh=30, xlab='L1 weight move on shock (pp)'):
    """Horizontal grouped bars. series: list of (name, color, values[]) aligned to labels."""
    n = len(labels); ns = len(series); pad = 6; barh = (rowh - pad) / max(ns, 1)
    x0, x1, top = 178, w - 42, 6; h = n * rowh + 42
    xmax = (max((max(v) for _, _, v in series), default=1) or 1) * 1.10
    sx = lambda v: x0 + max(v, 0) / xmax * (x1 - x0)
    s = f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:auto">'
    step = 2 if xmax <= 12 else 4; gv = 0.0
    while gv <= xmax:
        s += f'<line x1="{sx(gv):.1f}" y1="{top}" x2="{sx(gv):.1f}" y2="{n*rowh+top}" stroke="#1e222b"/>'
        s += f'<text x="{sx(gv):.1f}" y="{n*rowh+top+14}" fill="#5b6373" font-size="9" text-anchor="middle">{gv:g}</text>'
        gv += step
    for i, lab in enumerate(labels):
        yb = top + i * rowh
        s += f'<text x="{x0-6}" y="{yb+rowh/2+3:.1f}" fill="#aeb6c6" font-size="10" text-anchor="end">{esc(lab)}</text>'
        for si, (nm, c, vals) in enumerate(series):
            y = yb + si * barh; bw = sx(vals[i]) - x0
            s += f'<rect x="{x0}" y="{y:.1f}" width="{bw:.1f}" height="{barh-1:.1f}" fill="{c}" rx="1"><title>{esc(nm)} &middot; {esc(lab)}: {vals[i]:.1f} pp</title></rect>'
            s += f'<text x="{x0+bw+3:.1f}" y="{y+barh/2+2.5:.1f}" fill="#8a93a6" font-size="8">{vals[i]:.1f}</text>'
    s += f'<text x="{(x0+x1)/2:.0f}" y="{h-4}" fill="#8a93a6" font-size="10" text-anchor="middle">{esc(xlab)}</text>'
    return s + '</svg>'

# ---------- Tab: Overview ----------
def t_overview():
    l0p = PER['L0 Legacy Central']['ports']
    pre_t = l0p['P3_full_pre']['priv'] * 100; post_t = l0p['P4_full_post']['priv'] * 100
    post_tots = [PER[k]['ports']['P4_full_post']['priv'] * 100 for k in ORDER]
    kpis = ('<div class="kpis">'
        '<div class="kpi"><div class="kb">6 &times; 7</div><div class="kl">portfolios &times; personas</div><div class="ks">passive / +active / full, each pre &amp; after-tax</div></div>'
        f'<div class="kpi"><div class="kb">{int(BR["income"]*100)}% / {int(BR["cap_gains"]*100)}%</div><div class="kl">tax bracket (all)</div><div class="ks">ordinary income / qual-div &amp; LT cap-gains</div></div>'
        f'<div class="kpi"><div class="kb">{pre_t:.1f}% &rarr; {post_t:.1f}%</div><div class="kl">L0 privates, full book</div><div class="ks">pre-tax &rarr; after-tax (PRA/ARA fixed)</div></div>'
        f'<div class="kpi"><div class="kb">{min(post_tots):.0f}–{max(post_tots):.0f}%</div><div class="kl">after-tax private range</div><div class="ks">across the seven mandates</div></div>'
        '</div>')
    method = ('<div class="banner accent"><b>A like-for-like ladder, holding risk aversion fixed across tax.</b> '
        'For each mandate we build the same portfolio four ways and read the same opportunity set: '
        '<b>(1) Passive</b> alone fixes the passive risk aversion <b>PRA</b> to the policy eq/bd split; '
        '<b>(2) +Active</b> introduces the active overlay and the active-risk aversion <b>ARA</b> (ARA is set once at L0 so the pre-tax full book holds ~20% privates, then scaled by each persona&rsquo;s multiplier); '
        '<b>(3) Full</b> adds the four privates. PRA and ARA are then held <b>fixed</b> between the pre-tax and after-tax solves — no recalibration — so the private total is free to move with tax. '
        'Liquidity penalties are charged <b>before</b> tax; optimisation is pooled over <b>3 seeds</b>; every book carries a <b>US &ge; 60%</b> home-bias floor within public equity.</div>')
    note = ('<div class="banner"><b>The Meridian family — one framework, seven mandates.</b> '
        'Cards show the full-book private sleeve, pre-tax and after-tax. Open <b>Portfolio ladder</b> for the complete '
        'asset-by-asset build of all six portfolios per persona, and <b>Tax &amp; sleeves</b> for the muni and equity story.</div>')
    pc = ''
    for k in ORDER:
        mt = META[k]; pp = PER[k]; pre = pp['ports']['P3_full_pre']; post = pp['ports']['P4_full_post']
        bar = stacked([(post[x] * 100, CMA[x]['c']) for x in KEYS])
        pc += (f'<div class="pcard"><div class="ph"><span class="ptag">{mt["s"]}</span>'
               f'<div><div class="pm">{esc(mt["m"])}</div><div class="pr">{esc(mt["r"])}</div></div>'
               f'<div class="ptot">{post["priv"]*100:.1f}%<span class="psub">priv aft (pre {pre["priv"]*100:.1f}%)</span></div></div>'
               f'<div class="pd">{esc(mt["d"])}</div>{bar}'
               f'<div class="pmix">BO {post["BO"]*100:.1f} &middot; PRE {post["PRE"]*100:.1f} &middot; PI {post["PI"]*100:.1f} &middot; PCDL {post["PCDL"]*100:.1f}</div>'
               f'<div class="pt">{esc(mt["t"])}</div></div>')
    return method + kpis + note + legend([(CMA[x]['n'], CMA[x]['c']) for x in KEYS]) + f'<div class="pgrid">{pc}</div>'

# ---------- Tab: Portfolio ladder (the 6-portfolio full-asset tables) ----------
def ladder_table(k):
    pp = PER[k]; ports = pp['ports']
    # header
    g1 = '<tr><th rowspan="2">Asset %</th>'
    for lab, keys in GROUPS:
        cls = ' s' if keys[0] in POSTKEYS or keys[1] in POSTKEYS else ''
        g1 += f'<th colspan="2" class="grp{cls}">{lab}</th>'
    g1 += '</tr>'
    g2 = '<tr>'
    for lab, keys in GROUPS:
        for pk in keys:
            g2 += f'<th class="n{" s" if pk in POSTKEYS else ""}">{"after" if pk in POSTKEYS else "pre"}</th>'
    g2 += '</tr>'
    body = ''
    for grp, rows in ASSET_ROWS:
        body += f'<tr><td class="grp2" colspan="7">{grp}</td></tr>'
        for aid, alab in rows:
            hl = ' style="color:#e9d8a6;font-weight:600"' if aid == 'us_muni' else ''
            body += f'<tr><td{hl}>{alab}</td>'
            for lab, keys in GROUPS:
                for pk in keys:
                    body += cell(ports[pk]['weights'][aid], pk in POSTKEYS, hl=hl)
            body += '</tr>'
    # summary rows
    def srow(label, field, pct0=False, accent=False):
        st = ' style="color:#e9d8a6"' if accent else ''
        r = f'<tr><td class="b"{st}>{label}</td>'
        for lab, keys in GROUPS:
            for pk in keys:
                v = ports[pk][field]
                r += cell(v, pk in POSTKEYS, b=True, hl=st)
        return r + '</tr>'
    body += '<tr><td class="grp2" colspan="7">Summary</td></tr>'
    body += srow('Total equities', 'pub_eq')
    body += srow('Total bonds (incl muni)', 'bonds')
    body += srow('&mdash; of which muni', 'muni', accent=True)
    body += srow('Total active overlay', 'active')
    body += srow('Total privates', 'priv')
    # US home-bias row (already a share, 0..1) -> show as %
    hb = '<tr><td class="b">US % of public equity</td>'
    for lab, keys in GROUPS:
        for pk in keys:
            hb += f'<td class="n b{" s" if pk in POSTKEYS else ""}">{ports[pk]["us_eq_share"]*100:.0f}</td>'
    hb += '</tr>'
    body += hb
    return (f'<div class="card"><h3>{META[k]["s"]} &middot; {esc(META[k]["m"])} '
            f'<span class="tag">PRA {pp["PRA"]:.2f} &middot; ARA {pp["ARA"]:.2f} &middot; policy {int(pp["policy_eq"]*100)}/{100-int(pp["policy_eq"]*100)} '
            f'&middot; &lambda; {int(pp["lam"]*1e4)} bps</span></h3>'
            '<div class="tw"><table class="dt">'
            f'<thead>{g1}{g2}</thead><tbody>{body}</tbody></table></div></div>')

def t_ladder():
    intro = ('<div class="banner">Each column is a full optimised portfolio over the <b>same 14-asset</b> opportunity set. '
        'Reading left&rarr;right you add <b>active</b>, then <b>privates</b>; within each stage the shaded column is <b>after-tax</b> '
        '(same PRA/ARA as its pre-tax neighbour). The three summary lines — <b>total equities</b>, <b>total active overlay</b>, '
        '<b>total privates</b> — plus the muni line and the US home-bias floor are the quick read.</div>'
        + legend([(CMA[x]['n'], CMA[x]['c']) for x in KEYS]))
    return intro + ''.join(ladder_table(k) for k in ORDER)

# ---------- Tab: Tax & sleeves (privates, muni, equity) ----------
def t_sleeves():
    # 1) privates pre vs post, full book
    pr = ''
    for k in ORDER:
        pp = PER[k]['ports']; a = pp['P3_full_pre']; b = pp['P4_full_post']
        d = (b['priv'] - a['priv']) * 100
        pr += (f'<tr><td><b>{META[k]["s"]}</b></td>'
               f'<td class="n">{a["BO"]*100:.1f}</td><td class="n">{a["PRE"]*100:.1f}</td><td class="n">{a["PI"]*100:.1f}</td><td class="n">{a["PCDL"]*100:.1f}</td><td class="n b">{a["priv"]*100:.1f}</td>'
               f'<td class="n s">{b["BO"]*100:.1f}</td><td class="n s">{b["PRE"]*100:.1f}</td><td class="n s">{b["PI"]*100:.1f}</td><td class="n s">{b["PCDL"]*100:.1f}</td><td class="n b s">{b["priv"]*100:.1f}</td>'
               f'<td class="n">{pill(d)}</td></tr>')
    privtbl = ('<div class="card"><h3>Privates — pre-tax vs after-tax, full book <span class="tag">PRA/ARA fixed; weights %</span></h3>'
        '<div class="tw"><table class="dt"><thead>'
        '<tr><th rowspan="2">Case</th><th colspan="5" class="grp">PRE-TAX</th><th colspan="5" class="grp s">AFTER-TAX</th><th rowspan="2" class="n">&Delta; tot</th></tr>'
        '<tr><th class="n">BO</th><th class="n">PRE</th><th class="n">PI</th><th class="n">PCDL</th><th class="n">Tot</th>'
        '<th class="n s">BO</th><th class="n s">PRE</th><th class="n s">PI</th><th class="n s">PCDL</th><th class="n s">Tot</th></tr></thead>'
        f'<tbody>{pr}</tbody></table></div>'
        '<p class="note">With risk aversion held fixed and the liquidity penalty charged before tax, the private sleeve <b>falls</b> after tax in '
        'every mandate (flat only at L2, where all three equity-funded privates sit at their 8% caps). <b>PRE</b> is the swing line; '
        'BO and PI stay pinned at the cap; PCDL stays at zero at these ARA levels.</p></div>')

    # 2) muni substitution — passive book pre vs post
    mu = ''
    for k in ORDER:
        pp = PER[k]['ports']; a = pp['P1_passive_pre']; b = pp['P1_passive_post']
        taxbd_a = (a['bonds'] - a['muni']) * 100; taxbd_b = (b['bonds'] - b['muni']) * 100
        mu += (f'<tr><td><b>{META[k]["s"]}</b></td><td class="n">{int(PER[k]["policy_eq"]*100)}/{100-int(PER[k]["policy_eq"]*100)}</td>'
               f'<td class="n">{taxbd_a:.1f}</td><td class="n">{a["muni"]*100:.1f}</td>'
               f'<td class="n s">{taxbd_b:.1f}</td><td class="n s">{b["muni"]*100:.1f}</td>'
               f'<td class="n">{pill((b["muni"]-a["muni"])*100)}</td></tr>')
    munitbl = ('<div class="card"><h3>Muni substitution in the bond sleeve — passive book <span class="tag">pre vs after-tax; weights %</span></h3>'
        '<div class="tw"><table class="dt"><thead>'
        '<tr><th rowspan="2">Case</th><th rowspan="2" class="n">eq/bd</th><th colspan="2" class="grp">PRE-TAX</th><th colspan="2" class="grp s">AFTER-TAX</th><th rowspan="2" class="n">&Delta; muni</th></tr>'
        '<tr><th class="n">taxable bd</th><th class="n">muni</th><th class="n s">taxable bd</th><th class="n s">muni</th></tr></thead>'
        f'<tbody>{mu}</tbody></table></div>'
        '<p class="note">Pre-tax, muni is return-dominated and sits at zero everywhere. After tax (taxable bonds &minus;37%, muni exempt) the '
        'passive bond sleeve flips almost entirely to <b>muni</b>. In the full books this mostly disappears because active + privates already '
        'displace the bond sleeve before tax — so muni only survives the full optimisation in the bond-heavy <b>L1 / R5</b> 50/50 mandates.</p></div>')

    # 3) equity behaviour — full book pre vs post
    eq = ''
    for k in ORDER:
        pp = PER[k]['ports']; a = pp['P3_full_pre']; b = pp['P4_full_post']
        eq += (f'<tr><td><b>{META[k]["s"]}</b></td>'
               f'<td class="n">{a["pub_eq"]*100:.1f}</td><td class="n s">{b["pub_eq"]*100:.1f}</td>'
               f'<td class="n">{a["weights"]["intl_eq"]*100:.1f}</td><td class="n s">{b["weights"]["intl_eq"]*100:.1f}</td>'
               f'<td class="n">{a["us_eq_share"]*100:.0f}</td><td class="n s">{b["us_eq_share"]*100:.0f}</td>'
               f'<td class="n">{a["bonds"]*100:.1f}</td><td class="n s">{b["bonds"]*100:.1f}</td></tr>')
    eqtbl = ('<div class="card"><h3>Equity &amp; bonds — full book, pre vs after-tax <span class="tag">public equity = US + Intl + US-active; weights %</span></h3>'
        '<div class="tw"><table class="dt"><thead>'
        '<tr><th rowspan="2">Case</th><th colspan="2" class="grp">Public equity</th><th colspan="2" class="grp">Intl equity</th><th colspan="2" class="grp">US % of pub eq</th><th colspan="2" class="grp">Bonds</th></tr>'
        '<tr><th class="n">pre</th><th class="n s">aft</th><th class="n">pre</th><th class="n s">aft</th><th class="n">pre</th><th class="n s">aft</th><th class="n">pre</th><th class="n s">aft</th></tr></thead>'
        f'<tbody>{eq}</tbody></table></div>'
        '<p class="note">Because PRA is anchored on the <i>passive</i> book, the active overlay and the equity-funded privates stack on top of '
        'equity beta rather than displacing it — so the full books carry more public equity than the policy split and bonds fall to ~0. '
        'After tax, taxable bonds vacate, public equity rises further, the mix tilts toward <b>international equity</b>, and the '
        '<b>US 60% home-bias floor binds</b> in nearly every book.</p></div>')

    head = ('<div class="banner accent"><b>Three things move with tax — and now they move the intuitive way.</b> '
        'Privates give back (income-taxed PRE leads); the passive bond sleeve converts to muni; equity stacks toward the home-bias floor. '
        'The private give-back is genuine here because risk aversion is held fixed and the illiquidity penalty is taxed consistently '
        '(charged before tax), rather than re-anchored.</div>')
    return head + privtbl + munitbl + eqtbl

# ---------- Tab: Key insights (data-driven, per case) ----------
def _priv_state(port):
    """Classify each private (full book) as capped (>=7.9), out (<0.1), or mid."""
    d = {x: port[x] * 100 for x in KEYS}
    capped = [x for x in KEYS if d[x] >= 7.9]
    out = [x for x in KEYS if d[x] < 0.1]
    mid = [x for x in KEYS if 0.1 <= d[x] < 7.9]
    return d, capped, out, mid

def case_insights(k):
    pp = PER[k]; ports = pp['ports']
    pre = ports['P3_full_pre']; post = ports['P4_full_post']
    pas_post = ports['P1_passive_post']
    dpriv = (post['priv'] - pre['priv']) * 100
    d_post, capped, out, mid = _priv_state(post)
    d_pre, _, _, _ = _priv_state(pre)
    ins = []
    # 1. private sleeve headline
    ins.append(f"Private sleeve <b>{pre['priv']*100:.1f}% &rarr; {post['priv']*100:.1f}%</b> after tax "
               f"({'tax-invariant' if abs(dpriv) < 0.15 else f'{dpriv:+.1f}pp'}), risk aversion held fixed.")
    # 2. cap structure / swing line
    if mid:
        swing = max(mid, key=lambda x: abs(d_post[x] - d_pre[x]))
        cap_lead = (f"<b>{_join(capped)}</b> {_sit(capped)} at the 8% cap" if capped else "No private binds its cap")
        ins.append(cap_lead + f"; <b>{swing}</b> is the swing line ({d_pre[swing]:.1f}&rarr;{d_post[swing]:.1f}%)"
                   + (f"; {_join(out)} {_verb(out)} out." if out else "."))
    else:
        eqf = [c for c in capped if c != 'PCDL']
        ins.append(f"All equity-funded privates (<b>{_join(eqf)}</b>) are pinned at the 8% cap"
                   + (f"; {_join(out)} {_verb(out)} out." if out else "."))
    # 3. tax give-back source / invariance
    if dpriv < -0.2:
        worst = min(KEYS, key=lambda x: d_post[x] - d_pre[x])
        ins.append(f"After-tax give-back concentrated in <b>{worst}</b> (income-taxed): "
                   f"{d_pre[worst]:.1f}&rarr;{d_post[worst]:.1f}%.")
    elif abs(dpriv) <= 0.2:
        ins.append("Private total is <b>tax-invariant</b> &mdash; every equity-funded private is already pinned at its cap.")
    # 4. muni
    if pas_post['muni'] * 100 > 0.5:
        ins.append(f"Passive bond sleeve flips to <b>muni {pas_post['muni']*100:.1f}%</b> after tax (taxable bonds vacate).")
    if post['muni'] * 100 > 0.5:
        ins.append(f"Muni even survives the <b>full</b> book ({post['muni']*100:.1f}%) &mdash; the "
                   f"{int(pp['policy_eq']*100)}/{100-int(pp['policy_eq']*100)} bond sleeve is deep enough.")
    # 5. home-bias floor
    if abs(post['us_eq_share'] * 100 - 60) < 1.0:
        ins.append("<b>US home-bias floor binds</b> (US = 60% of public equity) in the after-tax book.")
    # 6. equity stacking
    ins.append(f"Public equity <b>{pre['pub_eq']*100:.0f}% &rarr; {post['pub_eq']*100:.0f}%</b> "
               f"&mdash; stacks above the {int(pp['policy_eq']*100)}% policy as bonds fall toward 0.")
    return pre, post, dpriv, ins

def t_insights():
    falls = 0; invar = []; post_tots = []
    tally = {x: {'cap': 0, 'out': 0, 'mid': 0} for x in KEYS}
    cards = ''
    for k in ORDER:
        pre, post, dpriv, ins = case_insights(k)
        post_tots.append(post['priv'] * 100)
        if dpriv < -0.2: falls += 1
        if abs(dpriv) <= 0.2: invar.append(META[k]['s'])
        _, capped, out, mid = _priv_state(post)
        for x in capped: tally[x]['cap'] += 1
        for x in out: tally[x]['out'] += 1
        for x in mid: tally[x]['mid'] += 1
        FB = [('pub_eq', 'Equity', '#5aa9e6'), ('bonds', 'Bonds', '#6c7486'), ('priv', 'Privates', '#7ed3a2')]
        fullbar = lambda port: stacked([(port[f] * 100, c) for f, _, c in FB], w=300, h=17, mx=100.0)
        macmix = lambda port: ' &middot; '.join(f'{lab} {port[f]*100:.0f}%' for f, lab, _ in FB)
        privmix = lambda port: ' &middot; '.join(f'{x} {port[x]*100:.1f}' for x in KEYS)
        block = lambda port, cls: (f'<div class="taxview {cls}{" hide" if cls=="post" else ""}">{fullbar(port)}'
                                   f'<div class="pmix">{macmix(port)}</div>'
                                   f'<div class="pmix" style="color:#7e889c">private sleeve: {privmix(port)}</div></div>')
        chips = (f'<span class="chip">&gamma;<sub>P</sub> {PER[k]["PRA"]:.2f}</span><span class="chip">&gamma;<sub>A</sub> {PER[k]["ARA"]:.3f}</span>'
                 f'<span class="chip">policy {int(PER[k]["policy_eq"]*100)}/{100-int(PER[k]["policy_eq"]*100)}</span>'
                 f'<span class="chip">&lambda; {int(PER[k]["lam"]*1e4)} bps</span>'
                 f'<span class="chip">&gamma;<sub>A</sub>&times;{PER[k]["ara_mult"]:g}</span>')
        lis = ''.join(f'<li>{b}</li>' for b in ins)
        cards += (f'<div class="card"><div class="ph"><span class="ptag">{META[k]["s"]}</span>'
                  f'<div><div class="pm">{esc(META[k]["m"])}</div><div class="pr">{esc(META[k]["r"])}</div></div>'
                  f'<div class="ptot"><span class="taxview pre">{pre["priv"]*100:.1f}%<span class="psub">privates &middot; before tax</span></span>'
                  f'<span class="taxview post hide">{post["priv"]*100:.1f}%<span class="psub">privates &middot; after tax</span></span></div></div>'
                  f'<div class="chips">{chips}</div>'
                  f'{block(pre, "pre")}{block(post, "post")}'
                  f'<ul class="ins">{lis}</ul></div>')
    # computed cross-case patterns
    def role(x):
        t = tally[x]
        if t['cap'] == 7: return f"<b>{x}</b> binds the 8% cap in all 7"
        if t['out'] == 7: return f"<b>{x}</b> stays out in all 7"
        return f"<b>{x}</b> caps in {t['cap']}, swings in {t['mid']}, out in {t['out']}"
    pat = '; '.join(role(x) for x in KEYS)
    invtxt = (f' (tax-invariant only at <b>{", ".join(invar)}</b>, where the equity-funded privates are already at cap)'
              if invar else '')
    lead = (f'<div class="banner accent"><b>What the optimiser does, case by case.</b> '
            f'Privates give back after tax in <b>{falls} of 7</b> mandates{invtxt}. '
            f'After-tax private totals span <b>{min(post_tots):.0f}&ndash;{max(post_tots):.0f}%</b>. '
            f'Across cases: {pat} &mdash; at these ARA levels and on NewCMA inputs. '
            'PRA is anchored on each passive book; ARA is fixed at L0 then scaled per mandate &mdash; both frozen across tax.</div>')
    toggle = ('<div class="toggle" role="group" aria-label="tax view"><button data-tax="pre" class="on">Before tax</button>'
              '<button data-tax="post">After tax</button></div>'
              '<span class="note" style="margin-left:10px">&larr; toggle the cards between the policy (pre-tax) and realised (after-tax) book</span>')
    maclegend = legend([('Equity', '#5aa9e6'), ('Bonds', '#6c7486'), ('Privates', '#7ed3a2')])
    return lead + toggle + maclegend + f'<div class="pgrid">{cards}</div>'

# ---------- Tab: Inputs / Method ----------
def t_inputs():
    cr = ''
    for x in KEYS:
        c = CMA[x]; cr += (f'<tr><td><span class="dot" style="background:{c["c"]}"></span><b>{x}</b> — {esc(c["n"])}</td>'
            f'<td class="n">{c["a"]:.1f}%</td><td class="n">{c["te"]:.1f}%</td><td class="n">{c["s"]:.2f}</td><td class="n">{c["ir"]:.2f}</td></tr>')
    cma = (f'<div class="card"><h3>Private-asset assumptions <span class="tag">workbook &lsquo;Assumptions&rsquo;; 65th-pct base manager</span></h3>'
        '<table class="dt"><thead><tr><th>Asset</th><th class="n">Excess &alpha; vs public</th><th class="n">TE (FOLB)</th><th class="n">Illiquidity s&#7522;</th><th class="n">Info ratio</th></tr></thead>'
        f'<tbody>{cr}</tbody></table><p class="note">&alpha; = expected excess return vs the public sleeve each private is funded from. '
        'Privates enter a two-wealth additive CRRA over simulated terminal wealth; per-private cap 8%, funding-sleeve cap 60%, active overlay cap 20%.</p></div>')
    # calibration table
    cal = '<tr><th>policy eq/bd</th><th class="n">PRA (passive anchor)</th><th class="n">ARA base &times; mult</th></tr>'
    calrows = ''
    seen = set()
    for k in ORDER:
        pp = PER[k]; key = pp['policy_eq']
        calrows += (f'<tr><td>{META[k]["s"]} — {int(key*100)}/{100-int(key*100)}</td>'
                    f'<td class="n">{pp["PRA"]:.2f}</td><td class="n">{D["ARA_C"]:.2f} &times; {pp["ara_mult"]:g} = {pp["ARA"]:.2f}</td></tr>')
    caltbl = (f'<div class="card"><h3>Calibration <span class="tag">anchored once, then frozen across tax</span></h3>'
        f'<div class="banner">PRA is solved on each <b>passive</b> book to hit the policy equity split. ARA base '
        f'<b>{D["ARA_C"]:.2f}</b> is solved once at L0 so the <b>pre-tax</b> full book holds 20% privates, then scaled by each persona&rsquo;s '
        'multiplier. Both are held fixed for the after-tax solves.</div>'
        '<table class="dt"><thead>' + cal + f'</thead><tbody>{calrows}</tbody></table></div>')
    # tax table
    tt = D['tax_types']; rate = D['income_rate_by_asset']
    LBL = {'us_eq': 'US equity', 'intl_eq': 'Intl equity', 'us_agg': 'US bonds', 'intl_bd': 'Intl bonds',
           'us_hy': 'US high yield', 'us_muni': 'US muni', 'us_eq_act': 'US active equity', 'intl_eq_act': 'Intl active equity',
           'us_bd_act': 'US active bond', 'cash': 'Cash',
           'pe': 'Buyout (BO)', 'pre': 'Real estate (PRE)', 'pi': 'Infrastructure (PI)', 'pcdl': 'Private credit (PCDL)'}
    tr = ''
    for a in ['us_eq', 'intl_eq', 'us_eq_act', 'intl_eq_act', 'pe', 'us_agg', 'intl_bd', 'us_bd_act', 'us_hy', 'pre', 'pi', 'pcdl', 'us_muni', 'cash']:
        tr += f'<tr><td>{LBL[a]}</td><td>{tt[a]}</td><td class="n">{int(round(rate[a]*100))}%</td></tr>'
    tax = (f'<div class="card"><h3>Tax assumptions <span class="tag">single top bracket, all personas</span></h3>'
        f'<div class="banner">Ordinary income <b>{int(BR["income"]*100)}%</b> &middot; qualified dividends <b>{int(BR["dividend"]*100)}%</b> &middot; long-term cap-gains <b>{int(BR["cap_gains"]*100)}%</b>. '
        'Income taxed per asset, price appreciation at LT cap-gains. The v26 conditional liquidity penalty is charged <b>before</b> tax '
        '(capital bucket): <code>R = QI(1-inc) + (QP-LP)(1-cg)</code>. Optimisation pooled over seeds 42/43/44.</div>'
        '<table class="dt"><thead><tr><th>Asset</th><th>Tax character</th><th class="n">Income rate</th></tr></thead>'
        f'<tbody>{tr}</tbody></table></div>')
    # optimiser / method card (v33 engine)
    if OPT:
        optc = (f'<div class="card"><h3>Optimisation engine <span class="tag">packaged v33</span></h3>'
            '<div class="banner accent">The persona books are solved with '
            f'<b>{esc(OPT["optimizer"])}</b> over the selected two-wealth objective, at '
            f'<b>NS={OPT["n_sims"]:,} paths &times; NQ={OPT.get("n_quarters",40)} quarters</b>, '
            f'pooled over <b>{len(OPT.get("seeds",[]))} seeds</b> '
            f'({", ".join(str(s) for s in OPT.get("seeds",[]))}) &rarr; {OPT.get("effective_paths",0):,} effective paths. '
            'Each book runs several SLSQP restarts (default seeds plus a homotopy warm-start carried from the '
            'previous book) under exact linear constraints &mdash; budget, the sleeve caps, and the US home-bias floor. '
            'The PRA and ARA anchors are found by bisection, warm-starting each step from the last solve so the '
            'whole ladder calibrates in a handful of iterations.</div>'
            '<table class="dt"><thead><tr><th>Setting</th><th class="n">Value</th></tr></thead><tbody>'
            f'<tr><td>Optimiser</td><td class="n">{esc(OPT["optimizer"])}</td></tr>'
            f'<tr><td>Simulations (paths)</td><td class="n">{OPT["n_sims"]:,}</td></tr>'
            f'<tr><td>Quarters per path</td><td class="n">{OPT.get("n_quarters",40)}</td></tr>'
            f'<tr><td>Seeds (pooled)</td><td class="n">{", ".join(str(s) for s in OPT.get("seeds",[]))}</td></tr>'
            f'<tr><td>Effective paths</td><td class="n">{OPT.get("effective_paths",0):,}</td></tr>'
            f'<tr><td>Objective</td><td class="n">{esc(OPT.get("objective","two-wealth ladder"))}</td></tr>'
            '</tbody></table><p class="note">Same objective and the same personas as the research build; the packaged '
            'engine swaps the JAX/CMA-ES global stage for a warm-started SLSQP multi-start so it runs anywhere with '
            'just numpy + scipy. The restarts guard against the winner-take-all local optima the capped sleeve is prone to.</p></div>')
    else:
        optc = ''
    return optc + f'<div class="g2">{cma}{caltbl}</div>{tax}'

# ---------- Tab: Conditional liquidity-penalty cases (FAJ v26 paper reproduction) ----------
def t_faj():
    if not FAJ:
        return ('<div class="card"><h3>Conditional-liquidity-penalty cases not yet generated</h3>'
                '<p class="note">Run <code>python3 run_faj_cases_json.py</code> in <code>TaxVAAM/</code> to write '
                '<code>faj_v26_results.json</code>, then rebuild this dashboard.</p></div>')
    M = FAJ['meta']; B = FAJ['baseline']
    IDLBL = {'us_eq': 'US eq', 'us_eq_act': 'US active eq', 'us_tsy': 'US bonds', 'intl_eq': 'Intl eq',
             'intl_bd': 'Intl bd', 'pe': 'Buyout (PE)'}
    heat = lambda v: '#15321f' if v >= 20 else ('#1e2c1c' if v >= 10 else ('#2a281a' if v >= 3 else '#2a1e1e'))
    hcol = lambda v: '#7ed3a2' if v >= 20 else ('#bcd39a' if v >= 10 else ('#e0b877' if v >= 3 else '#d79a9a'))
    banner = ('<div class="banner accent"><b>Conditional Liquidity Penalties in Buyout (FAJ v26) &mdash; the paper&rsquo;s '
        'decision cases, reproduced.</b> The illiquidity discount on a private buyout programme is <b>state-dependent</b>: '
        'a gating episode is charged <b>once at onset</b> (&kappa; per event, suppressed for K quarters) under a rational-exit '
        'cap, and gates fire more often in equity stress. So CRRA prices the penalty&rsquo;s tail and variance, not just its mean. '
        f'Optimiser <b>{esc(M["optimizer"])}</b>, <b>NS={M["n_sims"]:,}</b> paths &times; {M["n_years"]}y; '
        f'&gamma;<sub>s</sub>={M["gamma_s_60"]} (60% equity); active risk aversion empirically remapped so the baseline '
        'penalised buyout reproduces the paper&rsquo;s 17.4%.</div>')
    mt = tiles([(str(M['moderate_ara']), 'moderate ARA (model scale)', '#5aa9e6'),
                (f'{B["frictionless_pe"]:.1f}%', 'frictionless buyout', '#8a93a6'),
                (f'{B["baseline_pe"]:.1f}%', 'baseline buyout (penalised)', '#7ed3a2')])
    # Table 6 - lambda x kappa
    t6 = FAJ['table6']; lams = t6['lams']; kaps = t6['kaps']
    h6 = '<tr><th>&kappa; &darr; / &lambda; &rarr;</th>' + ''.join(f'<th class="n">{l:g}</th>' for l in lams) + '</tr>'
    b6 = ''
    for ki, kap in enumerate(kaps):
        b6 += f'<tr><td class="b">{kap:g}</td>' + ''.join(
            f'<td class="n" style="background:{heat(v)};color:{hcol(v)};font-weight:700">{v:.1f}</td>' for v in t6['pe'][ki]) + '</tr>'
    tab6 = (f'<div class="card"><h3>Table 6 &middot; &lambda;&times;&kappa; decision matrix <span class="tag">optimal buyout %</span></h3>'
        f'<div class="tw"><table class="dt"><thead>{h6}</thead><tbody>{b6}</tbody></table></div>'
        f'<p class="note">{esc(t6["caption"])}</p></div>')
    # Table 7 - manager alpha (model vs paper)
    b7 = ''
    for r in FAJ['table7']['rows']:
        pp = '&mdash;' if r['paper'] is None else f'{r["paper"]:.1f}%'
        b7 += (f'<tr><td>{r["pctile"]}th</td><td class="n">{r["alpha_bps"]}</td>'
               f'<td class="n b" style="color:{hcol(r["pe"])}">{r["pe"]:.1f}%</td><td class="n" style="color:#8a93a6">{pp}</td></tr>')
    tab7 = (f'<div class="card"><h3>Table 7 &middot; manager-skill sensitivity <span class="tag">model vs paper</span></h3>'
        '<table class="dt"><thead><tr><th>Manager pctile</th><th class="n">&alpha; (bps)</th>'
        f'<th class="n">model buyout%</th><th class="n">paper</th></tr></thead><tbody>{b7}</tbody></table>'
        f'<p class="note">{esc(FAJ["table7"]["caption"])}</p></div>')
    # Table 8 - tracking error (model vs paper)
    b8 = ''
    for r in FAJ['table8']['rows']:
        b8 += (f'<tr><td>{r["te_bps"]}</td><td class="n b" style="color:{hcol(r["pe"])}">{r["pe"]:.1f}%</td>'
               f'<td class="n" style="color:#8a93a6">{r["paper"]:.1f}%</td></tr>')
    tab8 = (f'<div class="card"><h3>Table 8 &middot; tracking-error sensitivity <span class="tag">model vs paper</span></h3>'
        '<table class="dt"><thead><tr><th>PE tracking error (bps)</th><th class="n">model buyout%</th>'
        f'<th class="n">paper</th></tr></thead><tbody>{b8}</tbody></table>'
        f'<p class="note">{esc(FAJ["table8"]["caption"])}</p></div>')
    # Table 9 - substitution (weights per percentile)
    t9 = FAJ['table9']; ids9 = t9['ids']; cols9 = t9['rows']
    h9 = '<tr><th>Asset %</th>' + ''.join(f'<th class="n">{r["pctile"]}th</th>' for r in cols9) + '</tr>'
    b9 = ''
    for a in ids9:
        b9 += f'<tr><td>{IDLBL.get(a, a)}</td>' + ''.join(f'<td class="n">{r["weights"].get(a, 0):.1f}</td>' for r in cols9) + '</tr>'
    tab9 = (f'<div class="card"><h3>Table 9 &middot; buyout vs public active equity <span class="tag">substitution by manager skill</span></h3>'
        f'<div class="tw"><table class="dt"><thead>{h9}</thead><tbody>{b9}</tbody></table></div>'
        f'<p class="note">{esc(t9["caption"])}</p></div>')
    # Table E1 - passive RA
    e1 = FAJ['tableE1']; ids1 = e1['ids']; cols1 = e1['rows']
    h1 = '<tr><th>Asset %</th>' + ''.join(f'<th class="n">{r["eq_target"]}% eq<br><span style="color:#5b6373">&gamma;<sub>s</sub>={r["gamma_s"]:g}</span></th>' for r in cols1) + '</tr>'
    bE1 = ''
    for a in ids1:
        bE1 += f'<tr><td>{IDLBL.get(a, a)}</td>' + ''.join(f'<td class="n">{r["weights"].get(a, 0):.1f}</td>' for r in cols1) + '</tr>'
    tabE1 = (f'<div class="card"><h3>Table E1 &middot; passive risk aversion <span class="tag">equity target set by &gamma;<sub>s</sub></span></h3>'
        f'<div class="tw"><table class="dt"><thead>{h1}</thead><tbody>{bE1}</tbody></table></div>'
        f'<p class="note">{esc(e1["caption"])}</p></div>')
    # Table E2 - active RA (model vs paper)
    bE2 = ''
    for r in FAJ['tableE2']['rows']:
        bE2 += (f'<tr><td>{esc(r["level"])}</td><td class="n">{r["ara"]:g}</td>'
                f'<td class="n b" style="color:{hcol(r["pe"])}">{r["pe"]:.1f}%</td>'
                f'<td class="n" style="color:#8a93a6">{r["paper"]:.1f}%</td></tr>')
    tabE2 = (f'<div class="card"><h3>Table E2 &middot; active risk aversion <span class="tag">model vs paper</span></h3>'
        '<table class="dt"><thead><tr><th>Level</th><th class="n">ARA</th><th class="n">model buyout%</th>'
        f'<th class="n">paper</th></tr></thead><tbody>{bE2}</tbody></table>'
        f'<p class="note">{esc(FAJ["tableE2"]["caption"])}</p></div>')
    # RE worked example
    re = FAJ['re_example']
    ret = tiles([(f'{re["kappa_normal_bps"]:g} bps', 'core-RE &kappa; normal', '#5aa9e6'),
                 (f'{re["kappa_stress_bps"]:g} bps', 'core-RE &kappa; stress', '#f0a868'),
                 (f'{re["re_allocation"]:.1f}%', 'optimal core-RE allocation', '#7ed3a2')])
    tabRE = (f'<div class="card"><h3>Open-end core real-estate worked example</h3>{ret}'
        f'<p class="note">{esc(re["caption"])} Per-event onset charge from the model&rsquo;s sell-vs-wait formula '
        f'(paper Table 4: {esc(re["paper_kappa"])} bps). Heavier gating penalties than buyout &rarr; a thinner sleeve '
        'than the ~17% buyout baseline.</p></div>')
    return (banner + mt + tab6 + f'<div class="g2">{tab7}{tab8}</div>' + tab9
            + f'<div class="g2">{tabE1}{tabE2}</div>' + tabRE)

# ---------- Tabs: two-gamma overlay results (Modified VAAM/v33 / Cobb-Douglas / VAAM) — shared renderer ----------
_WLBL = [('us_eq', 'US eq'), ('intl_eq', 'Intl eq'), ('us_agg', 'US agg'), ('intl_bd', 'Intl bd'),
         ('us_hy', 'HY'), ('us_muni', 'muni'), ('us_eq_act', 'eq-act'), ('intl_eq_act', 'intl-eq-act'),
         ('us_bd_act', 'bd-act'),
         ('pe', 'PE'), ('pre', 'PRE'), ('pi', 'PI'), ('pcdl', 'PCDL'), ('cash', 'cash')]
# per-utility banner / objective equations / notes / verdict (values, so no f-string brace escaping)
OVL_META = {
 'v33': dict(
   banner=('<b>Modified VAAM (v33) &mdash; the active-risk overlay.</b> '
     'A single CRRA on TOTAL wealth at \\(\\gamma_P\\) plus a <b>Jensen-gap risk charge</b> on ACTIVE TOTAL wealth '
     'at \\(\\gamma_A\\), \\(\\varphi=1\\). Privates sit in \\(W_A\\); raw alpha; idio removed; cash risky (3.5%/1% vol); '
     'pre-tax. The active term rewards nothing (it is \\(\\le0\\)) &mdash; it only penalises active-wealth risk.'),
   obj=r"$$U(w)=\mathbb E[u(W;\gamma_P)]\;+\;\varphi\big(\mathbb E[u(W_A;\gamma_A)]-u(\mathbb E[W_A];\gamma_A)\big),\qquad u(W;\gamma)=\tfrac{W^{1-\gamma}}{1-\gamma}$$",
   wdef=r"$$W=\prod_{t=1}^{40}\Big(1+\textstyle\sum_i w_i r_{i,t}-\tfrac{\mathrm{drag}}{4}\Big),\qquad W_A=\prod_{t=1}^{40}\Big(1+\textstyle\sum_{i\in\text{active}} w_i r_{i,t}\Big)$$",
   objnote=('\\(W\\) = total wealth on all 13 holdings; \\(W_A\\) = the total-return wealth of the ACTIVE holdings only '
     '(two active funds + four privates). \\(\\gamma_P\\) prices all portfolio risk (60/40 anchor); \\(\\gamma_A\\) the extra '
     'aversion to active-program risk. The second term is a pure Jensen-gap penalty (mean-preserving risk charge).'),
   verdict=('Structurally the overlay works &mdash; two-\\(\\gamma\\) delineation, order-one \\(\\gamma_A\\), no TE cliff. '
     'The Cobb-Douglas and VAAM tabs run the SAME scenario and result set under two alternative aggregators, so the '
     'three are directly comparable. The <b>persona ladder tabs remain the production model</b>; these three overlays are the research diagnostics.')),
 'cobb': dict(
   banner=('<b>Cobb-Douglas of certainty-equivalents &mdash; two-\\(\\gamma\\) alternative to the overlay.</b> '
     'Instead of adding the two buckets, it multiplies their <b>certainty-equivalents</b>: '
     '\\(U=\\mathrm{CE}_P^{\\theta}\\,\\mathrm{CE}_A^{1-\\theta}\\). Same scenario, risk, return and optimiser as v33; '
     '\\(W_P\\) = TOTAL wealth, \\(W_A\\) = ACTIVE total wealth (as in v33); \\(\\theta\\) = passive/active split. A bad '
     'active outcome <b>scales down</b> total utility multiplicatively rather than adding a bounded penalty.'),
   obj=r"$$U(w)=\mathrm{CE}_P(w)^{\theta}\,\mathrm{CE}_A(w)^{1-\theta},\qquad \mathrm{CE}_X=\big(\mathbb E[W_X^{1-\gamma_X}]\big)^{\frac{1}{1-\gamma_X}}$$",
   wdef=r"$$W_P=\prod_{t=1}^{40}\Big(1+\textstyle\sum_i w_i r_{i,t}-\tfrac{\mathrm{drag}}{4}\Big),\qquad W_A=\prod_{t=1}^{40}\Big(1+\textstyle\sum_{i\in\text{active}} w_i r_{i,t}\Big)$$",
   objnote=('\\(\\mathrm{CE}_X\\) is the certainty-equivalent terminal wealth of bucket \\(X\\) at curvature \\(\\gamma_X\\). '
     '\\(\\gamma_P\\) (60/40 anchor) and \\(\\gamma_A\\) (active-equity anchor) are calibrated exactly as in the overlay; '
     '\\(\\theta\\) is the Cobb-Douglas weight on the passive/total bucket. Because the buckets combine multiplicatively, '
     'the marginal value of active wealth depends on the passive-wealth level &mdash; a genuine complementarity the additive forms lack.'),
   verdict=('Because \\(\\mathrm{CE}_A\\) rewards the LEVEL of active-total wealth, the Cobb-Douglas book chases the '
     'highest-return active assets (privates); the passive/active split \\(\\theta\\) is the brake. At \\(\\theta=0.5\\) it '
     'corners into ~94% privates; this run uses \\(\\theta=0.85\\), which restores a balanced book (see the base tiles). '
     'Note the passive aggregate bond stays starved even here &mdash; bond exposure arrives as <b>bond-active</b>, which also '
     'feeds \\(\\mathrm{CE}_A\\); the passive bond feeds only \\(\\mathrm{CE}_P\\) and loses the competition. Contrast the v33 '
     'overlay, whose active term is a risk-only penalty and never chases return.')),
 'vaam': dict(
   banner=('<b>VAAM (Aliaga-Diaz, Renzi-Ricci, Daga &amp; Ahluwalia, JPM 2020) &mdash; the ADDITIVE CRRA.</b> Each holding&rsquo;s return is '
     'decomposed into a systematic (beta) part and a factor-adjusted alpha part; each accumulates into its OWN wealth bucket, priced by its OWN '
     '\\(\\gamma\\) (split by risk COMPONENT, not by holding type). \\(U=\\mathbb E[u(W_p;\\gamma_P)]+\\mathbb E[u(W_a;\\gamma_A)]\\). '
     '\\(W_p\\) = the systematic/beta wealth of ALL holdings (passive + active + private betas); \\(W_a\\) = the factor-adjusted alpha wealth '
     '(active alpha + private premium + \\(\\varepsilon\\)). The active/private beta is risk-priced at \\(\\gamma_P\\); only the alpha is priced at '
     '\\(\\gamma_A\\) &mdash; so there is no blind spot and the 70%-active anchor is reachable. Same scenario/risk/return/optimiser as v33.'),
   obj=r"$$U(w)=\mathbb E[u(W_p;\gamma_P)]+\mathbb E[u(W_a;\gamma_A)],\qquad u(W;\gamma)=\tfrac{W^{1-\gamma}}{1-\gamma}$$",
   wdef=r"$$W_p=\prod_{t=1}^{40}\Big(1+\textstyle\sum_i w_i\,\beta_i r^{M}_{i,t}-\tfrac{\mathrm{drag}}{4}\Big),\qquad W_a=\prod_{t=1}^{40}\Big(1+\textstyle\sum_i w_i(\alpha_i+\varepsilon_{i,t})\Big)$$",
   objnote=('Following the paper (Eq.&nbsp;1, A-4), each holding&rsquo;s return \\(r=\\alpha+\\beta r^M+\\text{factor}+\\varepsilon\\) is split: the systematic '
     '\\(\\beta r^M\\) (+ factor) accumulates into \\(W_p\\), the factor-adjusted alpha \\(\\alpha+\\varepsilon\\) into \\(W_a\\). Passive holdings have '
     '\\(\\alpha=0\\) so they touch only \\(W_p\\); the two active funds contribute their manager alpha, the privates their illiquidity premium. '
     '\\(\\gamma_P\\) prices systematic risk (60/40 anchor), \\(\\gamma_A\\) prices alpha risk (70%-active anchor). Because the active/private beta is priced '
     'in \\(W_p\\) rather than omitted, \\(\\gamma_A\\) dials the active share cleanly &mdash; the tractable additive form is footnote&nbsp;13 / Appendix&nbsp;B.'),
   verdict=('This is the actual VAAM objective (the additive CRRA of footnote&nbsp;13 / Appendix&nbsp;B). Its defining move &mdash; the paper&rsquo;s '
     '&ldquo;removing the ad hoc step&rdquo; &mdash; is to decompose risk by COMPONENT (systematic vs alpha) rather than by holding, giving each its own '
     '\\(\\gamma\\). Compare its base book and sensitivities to the overlay (a Jensen penalty on active TOTAL wealth) and Cobb (a multiplicative CE bundle): '
     'all three now express a two-\\(\\gamma\\) active/passive split, but only VAAM does it by splitting each holding&rsquo;s return into its beta and alpha pieces.')),
}
def _sweep_range(rows, key='privates'):
    return (rows[0][key], rows[-1][key]) if rows else (0, 0)
def _overlay_body(V, kind):
    if not V:
        return ('<div class="card"><h3>Results not found</h3><p class="note">The <code>%s</code> overlay JSON is missing; '
                'run <code>run_altutil_overlay_suite.py</code> / the overlay suite in <code>TaxVAAM/</code>.</p></div>' % kind)
    M = OVL_META[kind]; cfg = V['config']; b = V['base']['roll']; sp = V['spike']; S = V['sens']
    scan = V.get('cost_scan', []); gp = cfg['gamP']; ga = cfg['gamA']; clabel = cfg.get('cost_label', '')
    jcol = lambda v: '#3fa473' if v < 15 else ('#f0a868' if v < 30 else '#f2a3a3')
    PE_ = '#3486c9'; EA = '#a06cc9'; BA = '#c8813b'; PC = '#3fa473'
    wd = V['base']['weights']
    wline = ' &middot; '.join(f'{l} {wd.get(a,0)*100:.1f}' for a, l in _WLBL if wd.get(a, 0) * 100 > 0.05)
    scan_priv = [r['privates'] for r in scan] if scan else [b['privates']]
    def sweepblock(key, xlab, note):
        d = S[key]; xs = d['x']; rows = d['rows']
        ymax = max(60, 10 * (int(max(max(r['pass_eq'], r['bd_active'], r['eq_active'], r['privates']) for r in rows) / 10) + 1))
        ch = multiline(xs, [('passive eq', [r['pass_eq'] for r in rows], PE_), ('eq-active', [r['eq_active'] for r in rows], EA),
                            ('bond-active', [r['bd_active'] for r in rows], BA), ('privates', [r['privates'] for r in rows], PC)],
                       ymax=ymax, xlab=xlab)
        tb = '<table class="mt"><tr><th>' + xlab.split()[0] + '</th><th>pass-eq</th><th>eq-act</th><th>bd-act</th><th>priv</th><th>bonds</th></tr>'
        for x, r in zip(xs, rows):
            tb += f'<tr><td class="n">{x:g}</td><td class="n">{r["pass_eq"]:.0f}</td><td class="n">{r["eq_active"]:.0f}</td><td class="n">{r["bd_active"]:.0f}</td><td class="n">{r["privates"]:.0f}</td><td class="n">{r["bonds"]:.0f}</td></tr>'
        tb += '</table>'
        jump = d['maxjump']; jc = jcol(jump)
        return f"""<div class="card"><h3>{key} sweep &mdash; the active sleeve split into equity-active and bond-active</h3>
{legend2([('passive eq',PE_,False),('eq-active',EA,False),('bond-active',BA,False),('privates',PC,False)])}{ch}
<div class="grid2"><div>{tb}</div><div><p class="note"><b>Max single-step jump:</b> <span style="color:{jc};font-weight:700">{jump:.1f} pts</span> (L1 over eq+act+priv). {note}</p></div></div></div>"""
    pra0, praN = _sweep_range(S['PRA']['rows']); ara0, araN = _sweep_range(S['ARA']['rows'])
    al0, alN = _sweep_range(S['alpha']['rows']); te0, teN = _sweep_range(S['TE']['rows'])
    eaA0, eaAN = _sweep_range(S['ARA']['rows'], 'eq_active')
    return f"""
<div class="banner accent">{M['banner']} \\(\\gamma_P={gp:g}\\) (60/40), \\(\\gamma_A={ga:g}\\) (active anchor){(', \\\\(\\\\theta=%g\\\\)'%cfg['theta']) if cfg.get('theta') is not None else ''}; optimiser {esc(cfg.get('optimizer','CMA-ES (evosax/JAX) + SLSQP polish'))}, NS={cfg.get('n_sims',20000):,}. Cost floor: <b>{esc(clabel)}</b> (&epsilon;={cfg['eps_base']*100:.2f}%, W<sub>cap</sub>={cfg['wcap']*100:.0f}%).</div>
<div class="card"><h3>The objective (what the optimizer maximises)</h3>
{M['obj']}
{M['wdef']}
<p class="note">{M['objnote']} The &epsilon;/capacity drag \\(\\mathrm{{drag}}(w)=\\sum_i(c_i w_i+\\eta_i w_i^2)\\), \\(\\eta_i=\\varepsilon+\\mathrm{{LIQP}}_i/2W_{{cap}}\\) on privates, is the uniform floor that keeps the private sleeve well-posed.</p></div>
<div class="grid2">
<div class="card"><h3>Cost-floor scan &mdash; the lowest &epsilon;/capacity cost that stays stable</h3>
<table class="mt"><tr><th>cost</th><th>&epsilon;</th><th>W<sub>cap</sub></th><th>&eta; on PI</th><th>max single</th><th>total priv</th><th>2-start L1</th><th>stable?</th></tr>
{''.join('<tr%s><td>%s</td><td class="n">%.2f%%</td><td class="n">%.0f%%</td><td class="n">%.1f%%</td><td class="n">%.1f%%</td><td class="n">%.1f%%</td><td class="n">%.1f</td><td style="color:%s">%s</td></tr>'%(' style="background:#171b24"' if r['name']==clabel else '',r['name'],r['eps']*100,r['wcap']*100,r['eta_pi']*100,r['maxpriv'],r['privates'],r['uniq_l1'],'#3fa473' if r['stable'] else '#f2a3a3','yes' if r['stable'] else 'no') for r in scan)}
</table>
<p class="note">Across the scan the private sleeve runs from <b>{min(scan_priv):.1f}% &rarr; {max(scan_priv):.1f}%</b>. The highlighted floor (<b>{esc(clabel)}</b>) is the one used for the headline book. {'This tab deliberately uses the cheapest stable floor to expose that the minimum is a false economy (privates run, sensitivity blows up).' if clabel in ('ultra-low','low') and kind=='v33' else 'We use the <b>moderate</b> floor, not the cheapest &mdash; the minimum floor is a false economy (privates run, input-sensitivity blows up; see the v33 tab). The capacity cost disciplines the private level; uniqueness and input-robustness are different properties.'}</p></div>
<div class="card"><h3>Base book (\\(\\gamma_P={gp:g},\\ \\gamma_A={ga:g}\\), {esc(clabel)} cost)</h3>
{tiles([('%.0f%%'%b['equity'],'equity',PE_),('%.0f%%'%b['active'],'active',BA),('%.0f%%'%b['privates'],'privates',PC),('%.0f%%'%b['bonds'],'bonds','#5b6373')])}
<p class="note">Weights: {wline}. <b>Privates {b['privates']:.0f}%</b>, active {b['active']:.0f}% (public-active {b.get('pub_active_share',0):.0f}% of the public book), bonds {b['bonds']:.0f}%, cash {b['cash']:.0f}%.</p></div>
</div>
<div class="card"><h3>Spike diagnostics &mdash; input sensitivity at the chosen floor</h3>
{tiles([('%.1f pts'%S['TE']['maxjump'],'TE sweep max step',jcol(S['TE']['maxjump'])),('%.1f pts'%sp['nudge_50bp_eqalpha'],'+50bp eq-alpha nudge',jcol(sp['nudge_50bp_eqalpha'])),('%.1f pts'%S['ARA']['maxjump'],'ARA sweep max step',jcol(S['ARA']['maxjump'])),('%.1f pts'%S['alpha']['maxjump'],'alpha sweep max step',jcol(S['alpha']['maxjump']))])}
<p class="note">The active/private sleeve is where the sensitivity lives. The <b>+50bp equity-alpha nudge</b> moves the mix <b>{sp['nudge_50bp_eqalpha']:.1f} pts</b> and the alpha-scale sweep's max single step is <b>{S['alpha']['maxjump']:.1f} pts</b>, vs TE at {S['TE']['maxjump']:.1f} pts. Lower = more input-robust; compare this row across the three utility tabs.</p></div>
{sweepblock('PRA','gamP (passive/total risk aversion)', f'\\(\\gamma_P\\) is the master risk dial: equity gives way to bonds as it rises. Privates move {pra0:.0f}&rarr;{praN:.0f}% across the grid.')}
{sweepblock('ARA','gamA (active-risk aversion)', f'The intended active dial: higher \\(\\gamma_A\\) suppresses the active/excess sleeve. Eq-active {eaA0:.0f}&rarr;{eaAN:.0f}; privates {ara0:.0f}&rarr;{araN:.0f}%. The base sits at \\(\\gamma_A={ga:g}\\).')}
{sweepblock('alpha','x_alpha (alpha & premium scale)', f'Scales BOTH active-fund alphas AND private premia 0.5&rarr;1.5&times;. Privates swing {al0:.0f}&rarr;{alN:.0f}%; a steeper response here means the sleeve tracks its premium more one-for-one (less regularised).')}
{sweepblock('TE','x_TE (tracking-error scale)', f'Scales BOTH active-fund TE AND private TE 0.5&rarr;1.5&times;. Privates ease {te0:.0f}&rarr;{teN:.0f}% as TE rises; publics roughly flat.')}
<div class="card"><h3>Verdict &amp; how it relates to the persona model</h3>
<p class="note">{M['verdict']}</p></div>"""
def t_overlay():      return _overlay_body(V33O, 'v33')
def t_overlay_cobb(): return _overlay_body(COBB, 'cobb')
def t_overlay_vaam(): return _overlay_body(VAAM, 'vaam')

# ---------- Tab: systematic stability test of the 3 utilities ----------
def t_stability():
    if not STAB:
        return ('<div class="card"><h3>Stability results not found</h3><p class="note">Run '
                '<code>python3 stability_test.py</code> in <code>TaxVAAM/</code> to write <code>stability_results.json</code>.</p></div>')
    sc = STAB['scorecard']; names = STAB['names']; cfg = STAB['config']
    MODES = ['overlay', 'cobb', 'vaam']; COL = {'overlay': '#3486c9', 'cobb': '#a06cc9', 'vaam': '#3fa473'}
    SHORT = {'overlay': 'Modified VAAM (v33)', 'cobb': 'Cobb-Douglas', 'vaam': 'VAAM'}
    # composite rank (lower = more stable) on the 3 discriminating axes
    rank = {m: 0 for m in MODES}
    for key in ('A_mean', 'B_disp', 'C_uniq'):
        for i, m in enumerate(sorted(MODES, key=lambda m: sc[m][key])): rank[m] += i
    order = sorted(MODES, key=lambda m: rank[m]); best = order[0]; worst = order[-1]
    ga = cfg.get('gamA', {})
    banner = ('<div class="banner accent"><b>Systematic stability test &mdash; the 3 utilities on equal footing.</b> '
        'Identical scenario, risk/return and optimiser (SLSQP multi-start), <b>same moderate cost floor</b> '
        f'(&epsilon;={cfg.get("cost","")}), \\(\\gamma_P={cfg.get("gamP",2.85)}\\), and \\(\\gamma_A\\) re-calibrated to the '
        'SAME 70%-active anchor on the full book for each '
        f'(overlay \\(\\gamma_A={ga.get("overlay","?")}\\), Cobb {ga.get("cobb","?")}, VAAM {ga.get("vaam","?")}); NS={cfg.get("NS",10000):,}. '
        'Stability = how far the optimal weights move under a perturbation (L1, percentage points; <b>lower = more stable</b>). '
        f'<b>Most stable: {SHORT[best]}; least stable: {SHORT[worst]}.</b> The ranking tracks the size of the active/private sleeve at the '
        'common calibration: the <b>overlay</b> holds the leanest sleeve (17% privates &mdash; its Jensen term penalises active risk without rewarding '
        'level) and moves least; <b>VAAM</b> rewards factor-adjusted alpha, so its 51% private sleeve is maximally exposed to premium/alpha shocks '
        '(worst-case 21.9 pp); Cobb sits between.</div>')
    # scorecard tiles (composite) + table
    kpis = tiles([(SHORT[m] + (' ★' if m == best else ''),
                   'A %.1f · seed %.1f · uniq %.1f' % (sc[m]['A_mean'], sc[m]['B_disp'], sc[m]['C_uniq']),
                   COL[m]) for m in MODES])
    METR = [('A_mean', 'Assumption robustness — mean L1 over 13 input shocks'),
            ('A_max', '— worst-case single shock'),
            ('B_disp', 'Sampling — cross-seed dispersion (8 seeds)'),
            ('B_privSD', '— SD of the private sleeve across seeds'),
            ('C_uniq', 'Uniqueness — worst multi-start disagreement')]
    head = '<tr><th>metric (lower = more stable)</th>' + ''.join(f'<th class="n" style="color:{COL[m]}">{SHORT[m]}</th>' for m in MODES) + '</tr>'
    body = ''
    for k, lbl in METR:
        vals = {m: sc[m][k] for m in MODES}; bestm = min(vals, key=vals.get)
        body += f'<tr><td>{esc(lbl)}</td>' + ''.join(
            f'<td class="n"{" style=\"color:#7ed3a2;font-weight:700\"" if m == bestm else ""}>{vals[m]:.1f}</td>' for m in MODES) + '</tr>'
    scorecard = (f'<div class="card"><h3>Stability scorecard <span class="tag">L1 weight move, pp &middot; green = best in row</span></h3>'
        f'{kpis}<table class="dt"><thead>{head}</thead><tbody>{body}</tbody></table>'
        '<p class="note">All three are <b>unique</b> (multi-start disagreement 0.0) at the moderate floor &mdash; well-posed, no multi-modality. '
        'The ranking tracks the private-sleeve size: the overlay (17% privates) is the most input-robust, VAAM (51% privates, additive alpha reward) the least, Cobb between.</p></div>')
    # per-shock grouped bars (sorted by mean move, descending)
    labels = [l for l, _ in STAB['A_shocks']['overlay']]
    vmap = {m: {l: v for l, v in STAB['A_shocks'][m]} for m in MODES}
    order = sorted(labels, key=lambda l: -sum(vmap[m][l] for m in MODES) / 3.0)
    series = [(SHORT[m], COL[m], [vmap[m][l] for l in order]) for m in MODES]
    leg = legend2([(SHORT[m], COL[m], False) for m in MODES])
    bars = (f'<div class="card"><h3>Per-shock sensitivity &mdash; how far the book moves under each standardized input shock</h3>'
        f'{leg}{groupbars(order, series)}'
        '<p class="note"><b>For the overlay and Cobb the dominant instability is the factor-MEAN estimates</b> (equity / bond return means move the book '
        '11&ndash;16 pp) &mdash; the classic Chopra&ndash;Ziemba result that allocations are far more sensitive to return means than to second moments. '
        '<b>For VAAM the biggest mover is instead the +50bp alpha nudge (21.9 pp):</b> because it rewards factor-adjusted alpha and holds a large alpha/private '
        'sleeve, it is maximally exposed to the alpha estimate. Either way, the highest-leverage robustness fix is shrinking/anchoring the means and premia '
        '(Black&ndash;Litterman priors, wider premium-uncertainty draws) and holding a leaner sleeve &mdash; not simply picking a different utility.</p></div>')
    method = ('<div class="card"><h3>How the test works &mdash; three orthogonal axes</h3>'
        '<table class="dt"><thead><tr><th>axis</th><th>what it perturbs</th><th>metric</th></tr></thead><tbody>'
        '<tr><td class="b">A · Assumption robustness</td><td>13 standardized input shocks: &plusmn;10% premia / all-TE, +50bp alpha, '
        '&plusmn;10% per-private premium, &plusmn;5&ndash;10% factor means</td><td>mean &amp; max \\(\\lVert\\Delta w^\\*\\rVert_1\\)</td></tr>'
        '<tr><td class="b">B · Sampling stability</td><td>re-draw the Monte-Carlo scenario over 6 seeds at fixed preferences (Michaud resampling)</td>'
        '<td>cross-seed dispersion of \\(w^\\*\\)</td></tr>'
        '<tr><td class="b">C · Uniqueness</td><td>5 diverse optimizer starts at fixed inputs</td><td>worst pairwise \\(\\lVert\\Delta w\\rVert_1\\)</td></tr>'
        '</tbody></table><p class="note">Fairness controls (identical scenario, cost floor, \\(\\gamma_P\\), 70%-active calibration, optimiser, NS) '
        'are what make the numbers comparable &mdash; the raw per-tab sweep max-steps were not (different cost floors and grids). '
        'Harness: <code>engine.py</code> (<code>run_stability</code>) &rarr; <code>results/stability_results.json</code>.</p></div>')
    defn = ('<div class="card"><h3>What &ldquo;stability&rdquo; means</h3>'
        '<p class="note" style="font-size:13px;color:#cfd5e0;line-height:1.55">Stability is just how much the portfolio moves when your inputs are a '
        'little off. Our capital-market assumptions are always estimates, so what we want is a model that gives roughly the same book when we nudge '
        'them &mdash; not one that reshuffles 20 points of the allocation because the equity return forecast moved half a percent. We test that by '
        'perturbing the assumptions (premia, alpha, tracking error, return means), re-drawing the simulations, and re-starting the optimizer, then '
        'measuring how far the weights travel &mdash; <b>smaller is better</b>. The takeaway: the formulations that <b>penalise</b> active risk hold a '
        'leaner, steadier sleeve, and the real driver of instability across all of them is the return assumptions themselves &mdash; so better-anchored '
        'CMAs buy you more robustness than a cleverer objective ever will.</p>'
        '<p class="note">Formally, each test below reports \\(\\lVert\\Delta w^\\*\\rVert_1\\) &mdash; the sum of the absolute weight changes, in percentage '
        'points &mdash; between the base book and the book after a perturbation. Lower = more stable = more trustworthy.</p></div>')
    return banner + defn + scorecard + bars + method

# ---------- Tab: Cover / guide ----------
def _go(tab):  # clickable card -> jump to a tab
    return f"onclick=\"document.querySelector('.tab[data-tab=&quot;{tab}&quot;]').click();window.scrollTo(0,0)\""
def t_cover():
    npriv = [PER[k]['ports']['P3_full_pre']['priv'] * 100 for k in ORDER]
    stab_line = ''
    if STAB:
        sc = STAB['scorecard']; MO = ['overlay', 'cobb', 'vaam']
        rk = {m: sum(sorted(MO, key=lambda x: sc[x][kk]).index(m) for kk in ('A_mean', 'B_disp', 'C_uniq')) for m in MO}
        winner = {'overlay': 'Modified VAAM (v33)', 'cobb': 'Cobb-Douglas', 'vaam': 'VAAM'}[min(MO, key=lambda m: rk[m])]
        stab_line = f'The stability test picks <b>{winner}</b> as the most robust of the three.'
    return f"""
<div class="banner accent" style="font-size:14px"><b>How to read this dashboard.</b> It answers two questions, in two streams. First we decide <b>which utility formulation</b> best turns a client&rsquo;s risk preferences into an allocation across passive, active and private assets (Stream 1). Then we apply the winner to build the <b>recommended portfolios</b> for seven family mandates, before and after tax (Stream 2). Use the grouped tabs above, or the two cards below. Full model details are on the <b>Methodology</b> tab.</div>
<div class="g2" style="margin-top:14px">
<div class="pcard" style="cursor:pointer;border-left:3px solid #5aa9e6" {_go('inputs')}>
<div class="ph"><span class="ptag" style="background:#5aa9e6">Stream 1</span><div class="pm" style="font-size:15px">Which utility formulation?</div></div>
<p class="pd" style="font-size:13px">We take the same assets, risk/return and optimiser, and test three ways to combine <b>systematic</b> and <b>active</b> risk aversion into one allocation &mdash; then stress-test how stable each is.</p>
<div class="tw"><table class="mt"><tr><th>step</th><th>tab</th></tr>
<tr><td class="n">1</td><td>Inputs &amp; assumptions</td></tr>
<tr><td class="n">2</td><td>Compare the three formulations</td></tr>
<tr><td class="n">3</td><td>VAAM &middot; Cobb-Douglas &middot; Modified VAAM (v33) &mdash; deep dives</td></tr>
<tr><td class="n">4</td><td>Stability test &rarr; the verdict</td></tr></table></div>
<p class="pt" style="font-size:12px">{stab_line} <span style="color:#5aa9e6;font-weight:700">Enter Stream 1 &rarr;</span></p></div>
<div class="pcard" style="cursor:pointer;border-left:3px solid #7ed3a2" {_go('insights')}>
<div class="ph"><span class="ptag" style="background:#7ed3a2;color:#0f1117">Stream 2</span><div class="pm" style="font-size:15px">The recommended portfolios</div></div>
<p class="pd" style="font-size:13px">Seven Meridian-family mandates (legacy, retirement, education), each built under the winning formulation &mdash; with a <b>before/after-tax toggle</b>, the full portfolio ladder, and the tax-sleeve story.</p>
<div class="tw"><table class="mt"><tr><th>step</th><th>tab</th></tr>
<tr><td class="n">1</td><td>Key insights (before/after-tax toggle)</td></tr>
<tr><td class="n">2</td><td>Portfolio ladder (passive &rarr; +active &rarr; full)</td></tr>
<tr><td class="n">3</td><td>Tax &amp; sleeves</td></tr></table></div>
<p class="pt" style="font-size:12px">7 mandates &middot; private sleeve {min(npriv):.0f}&ndash;{max(npriv):.0f}% pre-tax. <span style="color:#7ed3a2;font-weight:700">Enter Stream 2 &rarr;</span></p></div>
</div>
<div class="banner"><b>The through-line.</b> Stream 1 is model selection; Stream 2 is the application. Everything shares one opportunity set (14 assets), one optimiser (SLSQP multi-start), and the same conditional-liquidity-penalty treatment of privates. If you only have five minutes: read this cover, then <b>Compare</b>, then <b>Key insights</b>.</div>"""

# ---------- Tab: Compare the three utility formulations ----------
def t_compare():
    UT = [('Modified VAAM (v33)', V33O, 'overlay', 'overlay', '#3fa473',
           'single CRRA on <b>total</b> wealth + a Jensen-gap <b>risk penalty</b> on active total wealth'),
          ('VAAM', VAAM, 'overlay_vaam', 'vaam', '#a06cc9',
           'additive CRRA: <b>systematic</b> wealth + <b>factor-adjusted-alpha</b> wealth, each its own \\(\\gamma\\)'),
          ('Cobb-Douglas', COBB, 'overlay_cd', 'cobb', '#c8813b',
           'multiplicative bundle of the two buckets&rsquo; <b>certainty-equivalents</b>, \\(\\mathrm{CE}_P^{\\theta}\\mathrm{CE}_A^{1-\\theta}\\)')]
    sc = STAB['scorecard'] if STAB else {}
    rk = {}
    if sc:
        MO = ['overlay', 'cobb', 'vaam']
        rk = {m: sum(sorted(MO, key=lambda x: sc[x][kk]).index(m) for kk in ('A_mean', 'B_disp', 'C_uniq')) for m in MO}
    CAL = CALIB or {}
    hdr = ('<tr><th>formulation</th><th>active term</th><th class="n">\\(\\gamma_P\\)</th><th class="n">\\(\\gamma_A\\)</th>'
           '<th class="n">passive book<span class="psub">eq / bd &rarr; 60/40</span></th>'
           '<th class="n">public book<span class="psub">active / passive &rarr; 70/30</span></th>'
           '<th class="n">input-sens.<span class="psub">A_mean, pp</span></th><th class="n">stability</th></tr>')
    body = ''
    for nm, J_, tab, key, col, term in UT:
        cal = CAL.get(key)
        gp = ('%.2f' % J_['config']['gamP']) if J_ else '?'; ga = ('%.2f' % J_['config']['gamA']) if J_ else '?'
        if cal:
            pas = cal['passive']; pub = cal['public']
            pas_cell = f'{pas["equity"]:.0f} / {pas["bonds"]:.0f}<span class="psub">{pas["eq_share"]:.0f}% eq</span>'
            pub_cell = f'{pub["active"]:.0f} / {pub["passive_idx"]:.0f}<span class="psub">{pub["active_share"]:.0f}% active</span>'
        else:
            pas_cell = pub_cell = '&mdash;'
        amean = ('%.1f' % sc[key]['A_mean']) if sc else '&mdash;'
        stab = ''
        if rk:
            pos = sorted(['overlay', 'cobb', 'vaam'], key=lambda m: rk[m]).index(key)
            stab = ['<b style="color:#7ed3a2">most stable</b>', 'middle', '<b style="color:#f0a868">least stable</b>'][pos]
        body += (f'<tr><td style="color:{col};font-weight:700;cursor:pointer" {_go(tab)}>{nm} &rsaquo;</td>'
                 f'<td class="wrap" style="white-space:normal;max-width:260px">{term}</td>'
                 f'<td class="n">{gp}</td><td class="n">{ga}</td>'
                 f'<td class="n b" style="color:{col}">{pas_cell}</td><td class="n b" style="color:{col}">{pub_cell}</td>'
                 f'<td class="n">{amean}</td><td class="n">{stab}</td></tr>')
    verdict = ''
    if rk:
        winner = {'overlay': 'Modified VAAM (v33)', 'cobb': 'Cobb-Douglas', 'vaam': 'VAAM'}[min(rk, key=rk.get)]
        verdict = (f'<div class="banner accent"><b>The calibration is the same two-step recipe for all three &mdash; and {winner} is the most stable.</b> '
                   'Each formulation has exactly two preference dials: \\(\\gamma_P\\) (systematic risk aversion) is set on the <b>passive book</b> to hit a '
                   '<b>60/40 equity/bond</b> split; \\(\\gamma_A\\) (active risk aversion) is set on the <b>public book</b> (passive + active, no privates) to hit a '
                   '<b>70/30 active/passive</b> split. The table below shows that base public setting &mdash; privates are then layered on top in the deep-dive '
                   'tabs and in Stream 2. All three calibrate to the same anchors; they differ only in how the active term enters, which is what drives the '
                   'stability difference.</div>')
    note = ('<p class="note"><b>Read the two calibration columns:</b> the <b>passive book</b> confirms \\(\\gamma_P\\) delivers ~60/40 equity/bond (the systematic anchor); '
            'the <b>public book</b> confirms \\(\\gamma_A\\) delivers ~70/30 active/passive (the active anchor). These are the shared, privates-free base settings &mdash; '
            'cost floor is immaterial with no privates, so this is a strictly like-for-like calibration comparison. The <b>input-sensitivity</b> and <b>stability</b> '
            'columns (from the full battery on the Stability tab) show what happens once privates and input shocks enter. Click a formulation to open its deep-dive.</p>')
    return (verdict + '<div class="card"><h3>The base setting on public assets only &mdash; how \\(\\gamma_P\\) and \\(\\gamma_A\\) are calibrated '
            '<span class="tag">same assets, risk/return, optimiser</span></h3>'
            f'<div class="tw"><table class="dt"><thead>{hdr}</thead><tbody>{body}</tbody></table></div>{note}</div>')

# ---------- Tab: Methodology ----------
def t_methodology():
    OB = OVL_META
    eqrow = lambda nm, m, col: (f'<div class="card"><h3 style="color:{col}">{nm}</h3>{OB[m]["obj"]}<p class="note">{OB[m]["objnote"]}</p></div>')
    persona_obj = (r"$$U(w)=\mathbb E[u(W_{\text{total}};\gamma_P)]+\Big(\mathbb E[u(W_A;\gamma_A)]-u(\mathbb E[W_A];\gamma_A)\Big),\qquad u(W;\gamma)=\tfrac{W^{1-\gamma}}{1-\gamma}$$")
    opt = OPT or {}
    intro = ('<div class="banner accent"><b>Methodology &mdash; everything a reviewer needs.</b> One opportunity set, one return model, one '
        'optimiser, four candidate utilities. Stream 1 selects the utility; Stream 2 applies the winner (Modified VAAM / v33) to the seven personas. '
        'This tab collects the objective functions, the return-generating model, the persona engine, the conditional-liquidity-penalty calibration, '
        'and the caveats. Inputs &amp; CMAs are on the <b>Inputs</b> tab.</div>')
    utils = ('<div class="card"><h3>1 &middot; The utility formulations</h3>'
        '<p class="note">Each holding&rsquo;s return decomposes into a systematic (beta) part and a factor-adjusted alpha/excess part. The four candidate '
        'objectives combine the resulting <b>systematic</b> and <b>active</b> wealth in different ways:</p>'
        '<table class="mt"><tr><th>formulation</th><th>active term</th><th>behaviour</th></tr>'
        '<tr><td><b>VAAM &mdash; excess baseline</b></td><td class="wrap">additive CRRA on active <b>excess</b> wealth, passive-only \\(W_P\\)</td><td class="wrap">degenerate: the active/private beta is in a blind spot &rarr; 0% public active. Motivates the decomposition &amp; the overlay.</td></tr>'
        '<tr style="background:#161d1a"><td><b>Modified VAAM (v33)</b></td><td class="wrap">Jensen-gap <b>risk penalty</b> on active <b>total</b> wealth</td><td class="wrap">rewards nothing, only penalises active-risk dispersion &rarr; leanest sleeve, most stable. <b>Used in Stream 2.</b></td></tr>'
        '<tr><td><b>VAAM</b> (JPM 2020)</td><td class="wrap">additive CRRA on <b>alpha</b> wealth (systematic beta priced separately in \\(W_p\\))</td><td class="wrap">rewards factor-adjusted alpha &rarr; privates dominate the alpha bucket; largest sleeve.</td></tr>'
        '<tr><td><b>Cobb-Douglas</b></td><td class="wrap">multiplicative bundle of the buckets&rsquo; certainty-equivalents</td><td class="wrap">rewards active-wealth level &rarr; chases the highest-return bucket; \\(\\theta\\) is the brake.</td></tr>'
        '</table></div>'
        + eqrow('Modified VAAM (v33) &mdash; the production objective', 'v33', '#3fa473')
        + eqrow('VAAM (JPM 2020)', 'vaam', '#a06cc9')
        + eqrow('Cobb-Douglas', 'cobb', '#c8813b'))
    engine = (f'<div class="card"><h3>2 &middot; The persona engine (Stream 2)</h3>'
        '<p class="note">The seven personas are solved under the <b>Modified-VAAM (v33)</b> overlay &mdash; the most stable formulation &mdash; on the same '
        '14-asset opportunity set. For each mandate a ladder of portfolios is built and read consistently:</p>'
        f'{persona_obj}'
        '<table class="mt"><tr><th>rung</th><th>what it fixes</th></tr>'
        '<tr><td><b>P1 Passive</b></td><td class="wrap">anchors \\(\\gamma_P\\) to the persona&rsquo;s policy equity/bond split (60/40, 50/50, 85/15&hellip;)</td></tr>'
        '<tr><td><b>P2 +Active</b></td><td class="wrap">introduces the active overlay; \\(\\gamma_A\\) set once at the central case so the pre-tax full book holds ~20% privates, then scaled per persona</td></tr>'
        '<tr><td><b>P3 Full (pre-tax)</b> / <b>P4 Full (after-tax)</b></td><td class="wrap">add the four privates; \\(\\gamma_P,\\gamma_A\\) held FIXED across tax &mdash; so the private total is free to move with tax</td></tr>'
        '</table>'
        f'<p class="note"><b>Optimiser:</b> {esc(opt.get("optimizer","SLSQP multi-start (scipy)"))} at <b>NS={opt.get("n_sims",0):,} &times; {len(opt.get("seeds",[]))} seeds</b> '
        f'({opt.get("effective_paths",0):,} effective paths). Reduced-dimension SLSQP multi-start with a homotopy warm-start carried down the persona ladder (numpy + scipy only, no JAX). '
        'Per-private cap 8%, active-sleeve cap 20%, funding-sleeve cap 60%, US home-bias floor 60% of public equity. Liquidity penalty charged <b>before</b> tax '
        '(capital bucket): <code>R = QI(1-inc) + (QP-LP)(1-cg)</code>. Pooled over 3 seeds to damp Monte-Carlo corner noise.</p></div>')
    caveats = ('<div class="card"><h3>4 &middot; Caveats &amp; what a reviewer should know</h3><ul class="ins">'
        '<li>Risk-aversion coefficients are <b>ordinal</b>, not cardinal, and are calibrated to allocation anchors (60/40 equity, ~20% privates), not elicited directly.</li>'
        '<li>The largest source of allocation instability across every formulation is the <b>return-mean estimates</b> (Chopra&ndash;Ziemba), not the utility choice &mdash; see the Stability tab. The right robustness lever is shrinking/anchoring the CMAs.</li>'
        '<li>Private &ldquo;premium&rdquo; is modelled as a factor-adjusted excess return net of the state-dependent v26 liquidity penalty; managers are taken at the median (zero idiosyncratic alpha) unless stated.</li>'
        '<li>Single-period, 10-year horizon, pre-specified factor CMAs (NewCMA 2026-06). No transaction costs, no dynamic rebalancing, no APW dynamic illiquidity channel.</li>'
        '<li>Stream-1 base books are each at their own calibration/cost floor; the Stability tab is the only strictly like-for-like comparison.</li></ul>'
        '<p class="note">Regenerate everything from two files: <code>python3 engine.py</code> writes all results/*.json (utilities &middot; stability &middot; calibration &middot; personas), '
        'then <code>python3 dashboard.py</code> rebuilds this page. Edit the <code>CONFIG</code> dict at the top of <code>engine.py</code> to toggle the utility or change any input.</p></div>')
    liq = ('<div class="card" style="border-left:3px solid #f0a868"><h3>3 &middot; Conditional-liquidity-penalty calibration (FAJ v26)</h3>'
        '<p class="note">The private illiquidity discount is <b>state-dependent</b> and charged once at the onset of each gating episode, calibrated to reproduce '
        'the published buyout decision matrices. The cases below validate the penalty model that feeds the private returns used everywhere in this dashboard.</p></div>'
        + t_faj())
    return intro + utils + engine + liq + caveats

GROUPS = [
    (None, None, '', [('cover', 'Cover', t_cover())]),
    ('1', 'Which utility?', 's1', [
        ('inputs', 'Inputs', t_inputs()),
        ('compare', 'Compare', t_compare()),
        ('overlay_vaam', 'VAAM', t_overlay_vaam()),
        ('overlay_cd', 'Cobb-Douglas', t_overlay_cobb()),
        ('overlay', 'Modified VAAM (v33)', t_overlay()),
        ('stability', 'Stability', t_stability()),
    ]),
    ('2', 'The portfolios', 's2', [
        ('insights', 'Key insights', t_insights()),
        ('ladder', 'Portfolio ladder', t_ladder()),
        ('sleeves', 'Tax &amp; sleeves', t_sleeves()),
    ]),
    (None, None, 'sm', [('methodology', 'Methodology', t_methodology())]),
]
_flat = [(t, n, b) for _, _, _, tabs in GROUPS for (t, n, b) in tabs]
def _btn(t, n, sc):
    return f'<button class="tab {sc}{" active" if t=="cover" else ""}" data-tab="{t}">{n}</button>'
def _navgroup(num, label, sc, tabs):
    btns = ''.join(_btn(t, n, sc) for (t, n, _) in tabs)
    return btns if num is None else f'<span class="navg"><span class="navgrp {sc}">{num} &middot; {label}</span>{btns}</span>'
nav = ''.join(_navgroup(num, label, sc, tabs) for (num, label, sc, tabs) in GROUPS)
panels = ''.join(f'<section class="panel{" active" if t=="cover" else ""}" id="{t}">{b}</section>' for (t, n, b) in _flat)
today = datetime.date(2026, 7, 14).strftime('%d %b %Y')
# Inline the MathJax SVG bundle so the dashboard is FULLY self-contained (no CDN; equations render offline).
_mjx_path = os.path.join(HERE, 'mathjax.js')
MJX_BUNDLE = ('<script>' + open(_mjx_path).read() + '</script>') if os.path.exists(_mjx_path) else \
             '<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-svg.js" async></script>'
_opt_sub = (f" &middot; <b>optimiser {esc(OPT['optimizer'])}, NS={OPT['n_sims']:,}&times;{len(OPT.get('seeds',[]))} seeds</b>"
            if OPT else '')

HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>All-Privates &mdash; Utility Selection &amp; Persona Portfolios</title>
<style>
:root{{--bg:#0f1117;--panel:#181b23;--card:#1c2029;--line:#262a35;--txt:#e2e4ea;--mut:#8a93a6;--acc:#5aa9e6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--txt);font-family:Inter,system-ui,sans-serif;font-size:14px;line-height:1.5}}
header{{padding:16px 24px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#141821,#0f1117)}}
header h1{{margin:0;font-size:18px;font-weight:800}} .sub{{color:var(--mut);font-size:12px;margin-top:3px}}
nav{{display:flex;gap:4px;padding:8px 18px;border-bottom:1px solid var(--line);background:#10131a;flex-wrap:wrap}}
.tab{{background:none;border:0;color:var(--mut);padding:8px 14px;border-radius:7px;font:600 13px Inter;cursor:pointer}}
.tab:hover{{color:var(--txt);background:#1a1e27}} .tab.active{{color:#fff;background:var(--acc)}}
main{{max-width:1180px;margin:0 auto;padding:18px 24px 60px}} .panel{{display:none}} .panel.active{{display:block}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:14px 0}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}}
.kb{{font-size:23px;font-weight:800}} .kl{{color:var(--mut);font-size:12px;margin-top:2px}} .ks{{color:#6c7486;font-size:11px;margin-top:3px}}
.banner{{background:#161a22;border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:9px;padding:11px 14px;margin:10px 0;font-size:13px}}
.banner.accent{{border-left-color:#7ed3a2}}
.card{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px 17px;margin:12px 0}}
.card h3{{margin:0 0 10px;font-size:14px}} .tag{{color:var(--mut);font-weight:500;font-size:11px;margin-left:6px}}
.pgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;margin-top:8px}}
.pcard{{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:13px 15px}}
.ph{{display:flex;align-items:center;gap:10px}} .ptag{{background:var(--acc);color:#fff;font-weight:700;border-radius:6px;padding:3px 8px;font-size:12px}}
.pm{{font-weight:700;font-size:13px}} .pr{{color:var(--mut);font-size:11px}} .ptot{{margin-left:auto;text-align:right;font-weight:800;font-size:18px}}
.psub{{display:block;color:var(--mut);font-size:10px;font-weight:500}} .pd{{color:var(--mut);font-size:12px;margin:8px 0 7px}}
.pmix{{font-size:11px;color:#aeb6c6;margin:5px 0 6px;font-variant-numeric:tabular-nums}} .pt{{font-size:12px;color:#cfd5e0;border-top:1px dashed var(--line);padding-top:7px}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 10px}} .lg{{color:var(--mut);font-size:11px;display:flex;align-items:center;gap:5px}} .lg i{{width:11px;height:11px;border-radius:3px;display:inline-block}}
.tw{{overflow-x:auto}} table.dt{{width:100%;border-collapse:collapse;font-size:12.5px}}
.dt th,.dt td{{padding:6px 9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
.dt th{{color:var(--mut);font-weight:600;font-size:10.5px;text-transform:uppercase;letter-spacing:.4px}}
.dt td.n,.dt th.n{{text-align:right;font-variant-numeric:tabular-nums}} .dt td.b{{font-weight:700}}
.dt .grp{{text-align:center;color:#aeb6c6;border-bottom:2px solid var(--acc)}} .dt .grp.s{{border-bottom-color:#7ed3a2}}
.dt td.grp2{{text-align:left;color:#7e889c;text-transform:uppercase;letter-spacing:.5px;font-size:10px;font-weight:700;background:#13161d;border-bottom:1px solid var(--line)}}
.dt td.s,.dt th.s{{background:#161d1a}} .dt tr:last-child td{{border-bottom:0}}
.pill{{border-radius:5px;padding:1px 7px;font-size:11px;font-weight:700}} .pill.up{{background:#15321f;color:#7ed3a2}} .pill.dn{{background:#3a1f1f;color:#f2a3a3}} .pill.fl{{background:#23262f;color:var(--mut)}}
.note{{color:var(--mut);font-size:12px;margin:9px 0 0}} .g2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.chips{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 6px}}
.chip{{background:#11151d;border:1px solid var(--line);color:#aeb6c6;border-radius:6px;padding:2px 8px;font-size:11px;font-variant-numeric:tabular-nums}}
ul.ins{{margin:9px 0 0;padding-left:17px}} ul.ins li{{margin:4px 0;font-size:12.5px;color:#cfd5e0;line-height:1.45}}
.dot{{width:9px;height:9px;border-radius:2px;display:inline-block;margin-right:6px}}
code{{background:#11141b;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:11px}}
footer{{color:#5b6373;font-size:11px;text-align:center;padding:18px;border-top:1px solid var(--line)}}
@media(max-width:820px){{.g2{{grid-template-columns:1fr}}}}
.mt{{width:100%;border-collapse:collapse;font-size:12px;margin:6px 0}}
.mt th,.mt td{{padding:5px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}}
.mt th{{color:var(--mut);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.4px}}
.mt td.n,.mt th.n{{text-align:right;font-variant-numeric:tabular-nums}} .mt td.wrap{{white-space:normal}}
.tiles{{display:flex;gap:10px;flex-wrap:wrap;margin:9px 0}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:120px}}
.tile .v{{font-size:20px;font-weight:800}} .tile .l{{color:var(--mut);font-size:11px;margin-top:2px}}
.lg2{{display:flex;gap:14px;flex-wrap:wrap;margin:4px 0 8px}} .lg2 span{{color:var(--mut);font-size:11px;display:flex;align-items:center;gap:5px}} .lg2 i{{width:11px;height:11px;border-radius:3px;display:inline-block}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}} @media(max-width:820px){{.grid2{{grid-template-columns:1fr}}}}
mjx-container{{overflow-x:auto;overflow-y:hidden;max-width:100%}}
.navg{{display:inline-flex;align-items:center;gap:4px;flex-wrap:wrap}}
.navgrp{{color:#6c7486;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:2px 8px 2px 10px;border-left:2px solid var(--line);margin-left:4px}}
.navgrp.s1{{color:#5aa9e6;border-left-color:#5aa9e6}} .navgrp.s2{{color:#7ed3a2;border-left-color:#7ed3a2}}
.tab.s1.active{{background:#5aa9e6;color:#fff}} .tab.s2.active{{background:#7ed3a2;color:#0f1117}} .tab.sm.active{{background:#8a93a6;color:#0f1117}}
.toggle{{display:inline-flex;background:#11151d;border:1px solid var(--line);border-radius:8px;padding:3px;gap:3px;margin:2px 0 8px}}
.toggle button{{background:none;border:0;color:var(--mut);padding:6px 15px;border-radius:6px;font:600 12px Inter;cursor:pointer}}
.toggle button.on{{background:var(--acc);color:#fff}}
.taxview.hide{{display:none}}
</style>
<script>window.MathJax={{tex:{{inlineMath:[['\\\\(','\\\\)']],displayMath:[['$$','$$']]}},svg:{{fontCache:'local'}}}};</script>
{MJX_BUNDLE}
</head><body>
<header><h1>All-Privates &mdash; Private-Asset Allocation Framework</h1>
<div class="sub"><b>Stream 1</b> selects the utility formulation (VAAM &middot; Cobb-Douglas &middot; Modified VAAM/v33) &middot; <b>Stream 2</b> applies the winner to 7 Meridian-family mandates, before &amp; after tax (top bracket {int(BR['income']*100)}% / {int(BR['cap_gains']*100)}%) &middot; NewCMA 2026-06 inputs{_opt_sub} &middot; built {today} &middot; start on the <b>Cover</b> tab</div></header>
<nav>{nav}</nav>
<main>{panels}</main>
<footer>Fully self-contained &mdash; opens offline, no internet required (MathJax inlined, no CDN). Personas solved under <b>Modified VAAM (v33)</b> &mdash; the most stable of the three tested formulations &mdash; with {esc(OPT.get('optimizer','SLSQP multi-start (scipy)'))} at NS={OPT.get('n_sims',0):,} &times; {len(OPT.get('seeds',[]))} seeds; v26 conditional liquidity penalties (charged before tax); home-bias US&ge;60%. See the <b>Methodology</b> tab for full details. Regenerate: <code>python3 engine.py &amp;&amp; python3 dashboard.py</code>. Internal illustration only.</footer>
<script>
document.querySelectorAll('.tab').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');document.getElementById(b.dataset.tab).classList.add('active');
  if(window.MathJax&&MathJax.typesetPromise)MathJax.typesetPromise();
}});
document.querySelectorAll('.toggle button[data-tax]').forEach(b=>b.onclick=()=>{{
  const v=b.dataset.tax;
  document.querySelectorAll('.toggle button[data-tax]').forEach(x=>x.classList.toggle('on',x.dataset.tax===v));
  document.querySelectorAll('.taxview').forEach(x=>x.classList.toggle('hide',!x.classList.contains(v)));
}});
document.addEventListener('keydown',e=>{{const t=[...document.querySelectorAll('.tab')];const i=t.findIndex(x=>x.classList.contains('active'));
  if(e.key==='ArrowRight'&&i<t.length-1)t[i+1].click();if(e.key==='ArrowLeft'&&i>0)t[i-1].click();}});
</script></body></html>"""
open(OUT, 'w').write(HTML)
print('wrote', OUT, '(%d bytes)' % len(HTML))
