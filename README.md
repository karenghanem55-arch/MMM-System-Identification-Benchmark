# MMM System Identification Benchmark

Code for Ghanem, K. (2026), *Benchmarking Attribution Recovery: Can Simple Marketing Mix Models Find the Truth in a Saudi Market?* (submitted to the Journal of International DBA Studies).

**All data in this repository are simulated.** No real customer, company or platform data are used.

## What the code does

`simulate_mmm.py` simulates five years (261 weeks) of customer acquisition for a Saudi subscription business with an 8,359,400 SAR budget across Google Search, Snapchat, TikTok and Meta. The true effect of every channel is set in advance, including carryover (adstock), diminishing returns, and the actual dates of Ramadan, Eid al-Fitr, Eid al-Adha and Saudi National Day. It then estimates four OLS marketing mix models on 3,000 simulated datasets and measures how closely each recovers the truth.

| Model | Specification |
|---|---|
| M1 | Linear OLS on raw spend |
| M2 | OLS on spend^0.8 |
| M3 | OLS on adstocked, power-transformed spend (grid-searched per channel) |
| M4 | M3 without cultural controls |

## Reproduce the results

```bash
pip install numpy pandas statsmodels matplotlib
python simulate_mmm.py --reps 500
```

This takes a few minutes and writes every table and figure in the paper to `sim_results/` (fixed seed 2026). Use `--reps 20` for a quick check.

## Files

- `simulate_mmm.py`: simulation, estimation and reporting
- `sim_results/results.md`: all tables reported in the paper
- `sim_results/illustrative_dataset.csv`: the illustrative simulated dataset (Figure 1)
- `sim_results/fig1_simulated_market.png`, `fig2_paid_bias.png`: figures in the paper

## License

See `LICENSE`.
