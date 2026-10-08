"""
Simulation benchmark for the JIDS paper:
"Benchmarking Attribution Recovery: Can Simple Marketing Mix Models Find the Truth in a Saudi Market?"

A five-year weekly market is simulated with known ("true") channel effects, including
carryover (adstock), diminishing returns, Ramadan/Eid/National Day demand, and higher
spend during those events. Four OLS specifications are then estimated and compared
against the truth.

    M1  linear OLS on raw spend
    M2  OLS on spend^0.8 (the fixed-exponent specification of the original manuscript)
    M3  OLS on adstocked, power-transformed spend, with channel-specific decay and
        curvature chosen by grid search on a validation window
    M4  M3 without the cultural controls

All four include an intercept, linear trend and month indicators; M1-M3 also include
the Ramadan, Eid and National Day controls.

Run:  .venv/bin/python simulate_mmm.py            (full run, ~ several minutes)
      .venv/bin/python simulate_mmm.py --reps 20  (quick check)
Outputs go to ./sim_results/.
"""

import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_breuschpagan, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import durbin_watson

# ---------------------------------------------------------------- design (the "truth")

START = "2021-01-03"          # first Sunday of 2021
N_WEEKS = 261                 # 1,827 days, five years of weekly data
CHANNELS = ["google_search", "snapchat", "tiktok", "meta"]
TOTAL_SPEND = {"google_search": 1_210_000, "snapchat": 2_125_000, "tiktok": 1_885_000, "meta": 3_139_400}
TRUE_CPA = {"google_search": 73.00, "snapchat": 102.11, "tiktok": 120.02, "meta": 122.63}
TRUE_LAMBDA = {"google_search": 0.10, "snapchat": 0.30, "tiktok": 0.30, "meta": 0.50}
TRUE_ALPHA = {"google_search": 0.95, "snapchat": 0.80, "tiktok": 0.75, "meta": 0.70}

# Cultural demand, in extra sign-ups per week (scaled by the share of the week covered)
TRUE_RAMADAN = 1200
TRUE_EID_FITR = 900
TRUE_EID_ADHA = 600
TRUE_NATIONAL_DAY = 2000
# Firms spend more in these windows: the source of confounding
SPEND_UPLIFT_RAMADAN = 1.5
SPEND_UPLIFT_NATIONAL_DAY = 1.4

BASE_START, BASE_END = 7500, 10500   # baseline weekly sign-ups, trending upward
SEASON_AMPLITUDE = 500               # annual cycle in baseline demand
AR_RHO = 0.3                         # autocorrelation in the weekly noise
NOISE_LEVELS = [150, 300, 600]       # weekly noise SD (roughly 1.5%, 3%, 7% of baseline)
MAIN_NOISE = 300
# Media effectiveness multiplier. 1 = the calibrated market (paid media ~3% of sign-ups);
# 5 = media five times as effective (paid media ~15% of sign-ups, CPAs divided by 5).
SIGNAL_LEVELS = [1, 5]

# Saudi (Umm al-Qura) dates
RAMADAN = [("2021-04-13", "2021-05-12"), ("2022-04-02", "2022-05-01"), ("2023-03-23", "2023-04-20"),
           ("2024-03-11", "2024-04-09"), ("2025-03-01", "2025-03-29")]
EID_FITR = ["2021-05-13", "2022-05-02", "2023-04-21", "2024-04-10", "2025-03-30"]
EID_ADHA = ["2021-07-20", "2022-07-09", "2023-06-28", "2024-06-16", "2025-06-06"]
EID_DAYS = 4

HOLDOUT = 26
VALIDATION = 26
LAMBDA_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
ALPHA_GRID = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


# ---------------------------------------------------------------- helpers

def week_share(weeks, start, end):
    """Share of each week (Sunday-Saturday) that falls between start and end inclusive."""
    days = pd.date_range(start, end)
    s = np.zeros(len(weeks))
    for i, w in enumerate(weeks):
        wk = pd.date_range(w, periods=7)
        s[i] = wk.isin(days).sum() / 7
    return s


def calendar(weeks):
    cal = pd.DataFrame(index=weeks)
    cal["ramadan"] = sum(week_share(weeks, s, e) for s, e in RAMADAN)
    cal["eid_fitr"] = sum(week_share(weeks, d, pd.Timestamp(d) + pd.Timedelta(days=EID_DAYS - 1)) for d in EID_FITR)
    cal["eid_adha"] = sum(week_share(weeks, d, pd.Timestamp(d) + pd.Timedelta(days=EID_DAYS - 1)) for d in EID_ADHA)
    nd = [f"{y}-09-23" for y in range(2021, 2026)]
    cal["national_day"] = sum(week_share(weeks, d, d) for d in nd) * 7  # 1 in the week containing 23 Sept
    return cal


def controls(weeks, cal, cultural=True):
    X = pd.DataFrame(index=weeks)
    X["trend"] = np.arange(len(weeks)) / 52
    for m in range(2, 13):
        X[f"month_{m}"] = (weeks.month == m).astype(float)
    if cultural:
        X = X.join(cal)
    return X


def adstock(x, lam):
    out = np.empty(len(x))
    c = 0.0
    for i, v in enumerate(x):
        c = v + lam * c
        out[i] = c
    return out


def transform(spend, params):
    return pd.DataFrame({ch: adstock(spend[ch].to_numpy(), lam) ** a for ch, (lam, a) in params.items()},
                        index=spend.index)


def mape(a, p):
    a, p = np.asarray(a), np.asarray(p)
    return float(np.mean(np.abs((a - p) / a)) * 100)


# ---------------------------------------------------------------- simulate one market

def make_spend(weeks, cal, rng):
    sp = {}
    burst = rng.random(len(weeks)) < 0.12        # campaign flights
    for ch in CHANNELS:
        x = rng.lognormal(0, 0.35, len(weeks))
        if ch != "google_search":
            x *= np.where(burst & (rng.random(len(weeks)) < 0.7), 1.8, 1.0)
            x *= 1 + (SPEND_UPLIFT_RAMADAN - 1) * cal["ramadan"].to_numpy()
            x *= 1 + (SPEND_UPLIFT_NATIONAL_DAY - 1) * cal["national_day"].to_numpy()
        else:
            x *= 1 + 0.2 * cal["ramadan"].to_numpy()   # search follows demand a little
        sp[ch] = x / x.sum() * TOTAL_SPEND[ch]
    return pd.DataFrame(sp, index=weeks)


def true_media(spend, signal=1):
    """Paid sign-ups per channel per week under the true parameters; betas are set so
    that each channel's total contribution equals spend / (true CPA / signal)."""
    S = transform(spend, {ch: (TRUE_LAMBDA[ch], TRUE_ALPHA[ch]) for ch in CHANNELS})
    beta = {ch: (TOTAL_SPEND[ch] / (TRUE_CPA[ch] / signal)) / S[ch].sum() for ch in CHANNELS}
    return S * pd.Series(beta)


def baseline(weeks, cal):
    t = np.arange(len(weeks))
    base = BASE_START + (BASE_END - BASE_START) * t / (len(weeks) - 1)
    base += SEASON_AMPLITUDE * np.sin(2 * np.pi * (weeks.dayofyear.to_numpy() - 80) / 365.25)
    culture = (TRUE_RAMADAN * cal["ramadan"] + TRUE_EID_FITR * cal["eid_fitr"]
               + TRUE_EID_ADHA * cal["eid_adha"] + TRUE_NATIONAL_DAY * cal["national_day"]).to_numpy()
    return base, culture


def ar1_noise(n, sd, rng):
    e = rng.normal(0, sd * np.sqrt(1 - AR_RHO ** 2), n)
    u = np.empty(n)
    u[0] = rng.normal(0, sd)
    for i in range(1, n):
        u[i] = AR_RHO * u[i - 1] + e[i]
    return u


# ---------------------------------------------------------------- estimation

def fit(y, media, C):
    X = sm.add_constant(pd.concat([media, C], axis=1), has_constant="add")
    return sm.OLS(y, X).fit(), X


def contributions(model, media):
    return {ch: float(model.params[ch] * media[ch].sum()) for ch in media.columns}


_CACHE = {}


def _column(spend, ch, lam, a):
    key = (len(spend), float(spend[ch].sum()), ch, lam, a)
    if key not in _CACHE:
        _CACHE[key] = adstock(spend[ch].to_numpy(), lam) ** a
    return _CACHE[key]


def select_params(y, spend, C, n_train, passes=2):
    """Coordinate-wise grid search over (λ, α) per channel, minimising validation MAPE."""
    params = {ch: (0.3, 0.8) for ch in CHANNELS}
    yv = y.to_numpy()
    Cv = np.column_stack([np.ones(len(y)), C.to_numpy()])

    def score(p):
        X = np.column_stack([Cv] + [_column(spend, ch, *p[ch]) for ch in CHANNELS])
        b = np.linalg.lstsq(X[:n_train], yv[:n_train], rcond=None)[0]
        return mape(yv[n_train:], X[n_train:] @ b)

    best = score(params)
    for _ in range(passes):
        for ch in CHANNELS:
            for lam, a in itertools.product(LAMBDA_GRID, ALPHA_GRID):
                trial = dict(params, **{ch: (lam, a)})
                s = score(trial)
                if s < best:
                    best, params = s, trial
    return params


def estimate_all(y, spend, cal, weeks):
    """Returns, for each model: full-sample fit, media design, holdout MAPE, chosen params."""
    n = len(y)
    n_fit = n - HOLDOUT
    C_full = controls(weeks, cal, cultural=True)
    C_nocult = controls(weeks, cal, cultural=False)
    specs = {}

    lin = {ch: (0.0, 1.0) for ch in CHANNELS}
    p08 = {ch: (0.0, 0.8) for ch in CHANNELS}
    p_m3 = select_params(y.iloc[:n_fit], spend.iloc[:n_fit], C_full.iloc[:n_fit], n_fit - VALIDATION)
    p_m4 = select_params(y.iloc[:n_fit], spend.iloc[:n_fit], C_nocult.iloc[:n_fit], n_fit - VALIDATION)

    for name, p, C in [("M1 Linear", lin, C_full), ("M2 Power 0.8", p08, C_full),
                       ("M3 Adstock + power", p_m3, C_full), ("M4 M3 without culture", p_m4, C_nocult)]:
        media = transform(spend, p)
        m_tr, _ = fit(y.iloc[:n_fit], media.iloc[:n_fit], C.iloc[:n_fit])
        Xh = sm.add_constant(pd.concat([media, C], axis=1), has_constant="add").iloc[n_fit:]
        hold = mape(y.iloc[n_fit:], m_tr.predict(Xh))
        m, X = fit(y, media, C)
        specs[name] = dict(model=m, X=X, media=media, holdout_mape=hold, params=p)
    return specs


# ---------------------------------------------------------------- Monte Carlo workers

_W = {}


def _init_worker(seed):
    weeks = pd.date_range(START, periods=N_WEEKS, freq="W-SUN")
    cal = calendar(weeks)
    spend = make_spend(weeks, cal, np.random.default_rng(seed))   # same first draw as main()
    _W.update(weeks=weeks, cal=cal, spend=spend)


def _run_job(job):
    signal, sd, r, yv = job
    weeks, cal, spend = _W["weeks"], _W["cal"], _W["spend"]
    true_contrib = true_media(spend, signal).sum()
    true_paid = true_contrib.sum()
    true_cpa = pd.Series({ch: TRUE_CPA[ch] / signal for ch in CHANNELS})
    true_rank = list(true_cpa.sort_values().index)
    sp = estimate_all(pd.Series(yv, index=weeks), spend, cal, weeks)
    rows = []
    for name, s in sp.items():
        est = pd.Series(contributions(s["model"], s["media"]))
        cpa = pd.Series({ch: TOTAL_SPEND[ch] / v if v > 0 else np.inf for ch, v in est.items()})
        rec = dict(signal=signal, noise=sd, rep=r, model=name,
                   paid_bias_pct=(est.sum() - true_paid) / true_paid * 100,
                   channel_abs_err_pct=float(np.mean(np.abs(est - true_contrib) / true_contrib) * 100),
                   best_channel_correct=int(cpa.idxmin() == true_rank[0]),
                   full_rank_correct=int(list(cpa.sort_values().index) == true_rank),
                   any_negative=int((est <= 0).any()),
                   holdout_mape=s["holdout_mape"],
                   adj_r2=s["model"].rsquared_adj)
        if "ramadan" in s["model"].params:
            rec["ramadan_est"] = s["model"].params["ramadan"]
        rows.append(rec)
    return rows


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default="sim_results")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)

    weeks = pd.date_range(START, periods=N_WEEKS, freq="W-SUN")
    cal = calendar(weeks)
    rng = np.random.default_rng(a.seed)
    spend = make_spend(weeks, cal, rng)          # fixed design: one spend history for all replications
    media_true = true_media(spend)
    base, culture = baseline(weeks, cal)
    true_contrib = media_true.sum()
    true_paid = true_contrib.sum()

    # ---------- illustrative dataset (main noise level) ----------
    y = pd.Series(base + culture + media_true.sum(axis=1).to_numpy() + ar1_noise(N_WEEKS, MAIN_NOISE, rng),
                  index=weeks)
    pd.concat([y.rename("signups"), spend.add_prefix("spend_"), cal], axis=1).to_csv(out / "illustrative_dataset.csv")
    specs = estimate_all(y, spend, cal, weeks)

    L = []
    w = L.append
    w("# Simulation results\n")
    w(f"Weeks: {N_WEEKS} ({weeks[0].date()} to {(weeks[-1] + pd.Timedelta(days=6)).date()}); total spend {spend.values.sum():,.0f} SAR")
    w(f"Illustrative dataset: weekly sign-ups mean {y.mean():,.0f}, min {y.min():,.0f}, max {y.max():,.0f}; "
      f"true paid sign-ups {true_paid:,.0f} ({true_paid / y.sum() * 100:.1f}% of all sign-ups)")
    ram_w = cal["ramadan"] > 0.5
    w(f"Social spend in Ramadan weeks vs other weeks: "
      f"{spend.loc[ram_w, ['snapchat', 'tiktok', 'meta']].sum(axis=1).mean():,.0f} vs "
      f"{spend.loc[~ram_w, ['snapchat', 'tiktok', 'meta']].sum(axis=1).mean():,.0f} SAR/week")

    w("\n## Table A. True parameters\n")
    w("| Channel | Spend (SAR) | True λ | True α | True paid sign-ups | True CPA (SAR) |\n|---|---|---|---|---|---|")
    for ch in CHANNELS:
        w(f"| {ch} | {TOTAL_SPEND[ch]:,.0f} | {TRUE_LAMBDA[ch]:.2f} | {TRUE_ALPHA[ch]:.2f} | {true_contrib[ch]:,.0f} | {TRUE_CPA[ch]:.2f} |")

    w("\n## Table B. Diagnostics on the illustrative dataset (noise SD = 300)\n")
    w("| Model | Adj. R² | Holdout MAPE | Max VIF (media) | Durbin–Watson | Breusch–Godfrey p (4 lags) | Breusch–Pagan p | RESET p |")
    w("|---|---|---|---|---|---|---|---|")
    for name, s in specs.items():
        m, X = s["model"], s["X"]
        Xc = X.drop(columns="const")
        vifs = [variance_inflation_factor(Xc.values, Xc.columns.get_loc(ch)) for ch in CHANNELS]
        w(f"| {name} | {m.rsquared_adj:.3f} | {s['holdout_mape']:.2f}% | {max(vifs):.2f} | {durbin_watson(m.resid):.2f} | "
          f"{acorr_breusch_godfrey(m, nlags=4)[1]:.3f} | {het_breuschpagan(m.resid, m.model.exog)[1]:.3f} | "
          f"{linear_reset(m, power=2, use_f=True).pvalue:.3f} |")

    w("\n## Table C. Recovered vs true CPA, illustrative dataset\n")
    w("| Channel | True CPA | " + " | ".join(specs) + " |")
    w("|---|---|" + "---|" * len(specs))
    for ch in CHANNELS:
        row = []
        for s in specs.values():
            c = contributions(s["model"], s["media"])[ch]
            row.append(f"{TOTAL_SPEND[ch] / c:,.2f}" if c > 0 else "negative")
        w(f"| {ch} | {TRUE_CPA[ch]:.2f} | " + " | ".join(row) + " |")
    w("\n| Total paid sign-ups | " + f"{true_paid:,.0f} | " +
      " | ".join(f"{sum(contributions(s['model'], s['media']).values()):,.0f}" for s in specs.values()) + " |")
    m3 = specs["M3 Adstock + power"]
    w("\nM3 selected parameters (λ, α): " + ", ".join(f"{ch} ({p[0]:.1f}, {p[1]:.1f})" for ch, p in m3["params"].items()))
    rm = m3["model"]
    w(f"M3 Ramadan coefficient: {rm.params['ramadan']:,.0f} per full week (true {TRUE_RAMADAN}); "
      f"National Day: {rm.params['national_day']:,.0f} (true {TRUE_NATIONAL_DAY})")

    # ---------- Monte Carlo ----------
    # Noise is drawn here, in order, so results are reproducible regardless of worker count.
    jobs = []
    for signal in SIGNAL_LEVELS:
        mt = true_media(spend, signal).sum(axis=1).to_numpy()
        for sd in NOISE_LEVELS:
            for r in range(a.reps):
                jobs.append((signal, sd, r, base + culture + mt + ar1_noise(N_WEEKS, sd, rng)))
    from concurrent.futures import ProcessPoolExecutor
    rows = []
    with ProcessPoolExecutor(initializer=_init_worker, initargs=(a.seed,)) as ex:
        for i, res in enumerate(ex.map(_run_job, jobs, chunksize=4)):
            rows.extend(res)
            print(f"  dataset {i + 1}/{len(jobs)}", end="\r")
    print()
    mc = pd.DataFrame(rows)
    mc.to_csv(out / "monte_carlo.csv", index=False)

    w(f"\n## Table D. Monte Carlo summary ({a.reps} replications per cell)\n")
    w("| Media signal | Noise SD | Model | Mean adj. R² | Mean holdout MAPE | Bias in total paid sign-ups | Mean abs. error per channel | Cheapest channel identified | Full CPA ranking correct | Any negative channel |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    g = mc.groupby(["signal", "noise", "model"], sort=False)
    summ = g.agg(adj_r2=("adj_r2", "mean"), hold=("holdout_mape", "mean"), bias=("paid_bias_pct", "mean"),
                 err=("channel_abs_err_pct", "mean"), best=("best_channel_correct", "mean"),
                 rank=("full_rank_correct", "mean"), neg=("any_negative", "mean"))
    for (sig, sd, name), r in summ.iterrows():
        w(f"| ×{sig} | {sd} | {name} | {r.adj_r2:.3f} | {r.hold:.2f}% | {r.bias:+.1f}% | {r.err:.1f}% | "
          f"{r.best * 100:.0f}% | {r['rank'] * 100:.0f}% | {r.neg * 100:.0f}% |")
    for sig in SIGNAL_LEVELS:
        share = true_media(spend, sig).values.sum() / (base.sum() + culture.sum() + true_media(spend, sig).values.sum())
        w(f"\nSignal ×{sig}: paid media = {share * 100:.1f}% of expected sign-ups")
    ram = mc.dropna(subset=["ramadan_est"]).groupby(["signal", "noise", "model"], sort=False)["ramadan_est"].agg(["mean", "std"])
    w(f"\nRamadan coefficient (true {TRUE_RAMADAN}):")
    for (sig, sd, name), r in ram.iterrows():
        w(f"- signal ×{sig}, noise {sd}, {name}: mean {r['mean']:,.0f} (SD {r['std']:,.0f})")
    sub = mc[(mc.signal == 1) & (mc.noise == MAIN_NOISE)]

    # ---------- figures ----------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "font.family": "sans-serif"})

    fig, ax1 = plt.subplots(figsize=(8, 3.4))
    ax1.plot(weeks, y, color="#1f4e79", lw=1, label="Weekly sign-ups")
    ax2 = ax1.twinx()
    ax2.plot(weeks, spend.sum(axis=1), color="#c55a11", lw=0.8, alpha=0.7, label="Total spend (SAR)")
    for s, e in RAMADAN:
        ax1.axvspan(pd.Timestamp(s), pd.Timestamp(e), color="grey", alpha=0.18, lw=0)
    ax1.set_ylabel("Sign-ups per week")
    ax2.set_ylabel("Spend per week (SAR)")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False)
    fig.tight_layout()
    fig.savefig(out / "fig1_simulated_market.png", dpi=220)
    plt.close(fig)

    names = list(specs)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=False)
    for ax, sig in zip(axes, SIGNAL_LEVELS):
        s2 = mc[(mc.signal == sig) & (mc.noise == MAIN_NOISE)]
        ax.boxplot([s2.loc[s2.model == n, "paid_bias_pct"] for n in names], showfliers=False)
        ax.set_xticks(range(1, len(names) + 1), ["M1", "M2", "M3", "M4"])
        ax.axhline(0, color="black", lw=0.8)
        ax.set_title(f"Media signal ×{sig}", fontsize=9)
    axes[0].set_ylabel("Error in total paid sign-ups (%)")
    fig.tight_layout()
    fig.savefig(out / "fig2_paid_bias.png", dpi=220)
    plt.close(fig)

    (out / "results.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
