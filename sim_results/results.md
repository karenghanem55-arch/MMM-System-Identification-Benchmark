# Simulation results

Weeks: 261 (2021-01-03 to 2026-01-03); total spend 8,359,400 SAR
Illustrative dataset: weekly sign-ups mean 9,446, min 7,005, max 12,745; true paid sign-ups 78,693 (3.2% of all sign-ups)
Social spend in Ramadan weeks vs other weeks: 36,682 vs 26,579 SAR/week

## Table A. True parameters

| Channel | Spend (SAR) | True λ | True α | True paid sign-ups | True CPA (SAR) |
|---|---|---|---|---|---|
| google_search | 1,210,000 | 0.10 | 0.95 | 16,575 | 73.00 |
| snapchat | 2,125,000 | 0.30 | 0.80 | 20,811 | 102.11 |
| tiktok | 1,885,000 | 0.30 | 0.75 | 15,706 | 120.02 |
| meta | 3,139,400 | 0.50 | 0.70 | 25,601 | 122.63 |

## Table B. Diagnostics on the illustrative dataset (noise SD = 300)

| Model | Adj. R² | Holdout MAPE | Max VIF (media) | Durbin–Watson | Breusch–Godfrey p (4 lags) | Breusch–Pagan p | RESET p |
|---|---|---|---|---|---|---|---|
| M1 Linear | 0.913 | 2.10% | 1.24 | 1.54 | 0.003 | 0.376 | 0.740 |
| M2 Power 0.8 | 0.913 | 2.10% | 1.24 | 1.54 | 0.003 | 0.381 | 0.751 |
| M3 Adstock + power | 0.913 | 2.16% | 1.79 | 1.56 | 0.005 | 0.450 | 0.733 |
| M4 M3 without culture | 0.823 | 3.18% | 1.34 | 1.75 | 0.156 | 0.000 | 0.770 |

## Table C. Recovered vs true CPA, illustrative dataset

| Channel | True CPA | M1 Linear | M2 Power 0.8 | M3 Adstock + power | M4 M3 without culture |
|---|---|---|---|---|---|
| google_search | 73.00 | 167.24 | 113.70 | 33.12 | 37.75 |
| snapchat | 102.11 | 548.25 | 401.32 | negative | 27.35 |
| tiktok | 120.02 | 104.52 | 86.31 | 23.49 | 31.96 |
| meta | 122.63 | negative | negative | negative | 29.43 |

| Total paid sign-ups | 78,693 | 14,150 | 17,942 | 102,387 | 275,402 |

M3 selected parameters (λ, α): google_search (0.3, 0.5), snapchat (0.7, 1.0), tiktok (0.7, 0.5), meta (0.0, 1.0)
M3 Ramadan coefficient: 1,133 per full week (true 1200); National Day: 1,833 (true 2000)

## Table D. Monte Carlo summary (500 replications per cell)

| Media signal | Noise SD | Model | Mean adj. R² | Mean holdout MAPE | Bias in total paid sign-ups | Mean abs. error per channel | Cheapest channel identified | Full CPA ranking correct | Any negative channel |
|---|---|---|---|---|---|---|---|---|---|
| ×1 | 150 | M1 Linear | 0.977 | 1.29% | -46.8% | 50.3% | 77% | 25% | 20% |
| ×1 | 150 | M2 Power 0.8 | 0.977 | 1.29% | -32.4% | 47.3% | 76% | 25% | 23% |
| ×1 | 150 | M3 Adstock + power | 0.977 | 1.29% | +48.8% | 108.5% | 52% | 12% | 30% |
| ×1 | 150 | M4 M3 without culture | 0.874 | 2.22% | +301.8% | 333.5% | 6% | 0% | 12% |
| ×1 | 300 | M1 Linear | 0.922 | 2.49% | -48.5% | 68.1% | 57% | 15% | 63% |
| ×1 | 300 | M2 Power 0.8 | 0.922 | 2.49% | -34.6% | 75.7% | 58% | 15% | 63% |
| ×1 | 300 | M3 Adstock + power | 0.923 | 2.53% | +46.6% | 186.5% | 46% | 10% | 69% |
| ×1 | 300 | M4 M3 without culture | 0.823 | 3.29% | +294.8% | 355.0% | 15% | 2% | 26% |
| ×1 | 600 | M1 Linear | 0.753 | 4.93% | -51.7% | 115.8% | 45% | 13% | 85% |
| ×1 | 600 | M2 Power 0.8 | 0.753 | 4.93% | -38.6% | 141.4% | 46% | 13% | 84% |
| ×1 | 600 | M3 Adstock + power | 0.755 | 4.97% | +31.1% | 365.7% | 41% | 13% | 85% |
| ×1 | 600 | M4 M3 without culture | 0.675 | 5.51% | +302.9% | 447.7% | 26% | 4% | 52% |
| ×5 | 150 | M1 Linear | 0.975 | 1.27% | -46.4% | 43.9% | 100% | 87% | 0% |
| ×5 | 150 | M2 Power 0.8 | 0.975 | 1.28% | -32.0% | 34.4% | 100% | 88% | 0% |
| ×5 | 150 | M3 Adstock + power | 0.978 | 1.25% | +29.0% | 52.9% | 74% | 32% | 0% |
| ×5 | 150 | M4 M3 without culture | 0.882 | 2.03% | +70.8% | 79.3% | 72% | 10% | 0% |
| ×5 | 300 | M1 Linear | 0.925 | 2.27% | -46.1% | 44.4% | 100% | 60% | 0% |
| ×5 | 300 | M2 Power 0.8 | 0.925 | 2.28% | -31.5% | 35.9% | 100% | 60% | 0% |
| ×5 | 300 | M3 Adstock + power | 0.928 | 2.30% | +26.6% | 58.7% | 71% | 26% | 0% |
| ×5 | 300 | M4 M3 without culture | 0.837 | 2.91% | +70.5% | 82.5% | 58% | 12% | 0% |
| ×5 | 600 | M1 Linear | 0.769 | 4.41% | -45.8% | 47.6% | 87% | 25% | 13% |
| ×5 | 600 | M2 Power 0.8 | 0.769 | 4.41% | -31.2% | 42.8% | 87% | 27% | 13% |
| ×5 | 600 | M3 Adstock + power | 0.772 | 4.45% | +29.2% | 84.9% | 57% | 14% | 22% |
| ×5 | 600 | M4 M3 without culture | 0.699 | 4.86% | +73.8% | 98.7% | 47% | 14% | 7% |

Signal ×1: paid media = 3.2% of expected sign-ups

Signal ×5: paid media = 14.1% of expected sign-ups

Ramadan coefficient (true 1200):
- signal ×1, noise 150, M1 Linear: mean 1,201 (SD 56)
- signal ×1, noise 150, M2 Power 0.8: mean 1,201 (SD 56)
- signal ×1, noise 150, M3 Adstock + power: mean 1,186 (SD 58)
- signal ×1, noise 300, M1 Linear: mean 1,211 (SD 111)
- signal ×1, noise 300, M2 Power 0.8: mean 1,211 (SD 111)
- signal ×1, noise 300, M3 Adstock + power: mean 1,196 (SD 116)
- signal ×1, noise 600, M1 Linear: mean 1,206 (SD 234)
- signal ×1, noise 600, M2 Power 0.8: mean 1,206 (SD 234)
- signal ×1, noise 600, M3 Adstock + power: mean 1,193 (SD 240)
- signal ×5, noise 150, M1 Linear: mean 1,270 (SD 57)
- signal ×5, noise 150, M2 Power 0.8: mean 1,270 (SD 57)
- signal ×5, noise 150, M3 Adstock + power: mean 1,207 (SD 63)
- signal ×5, noise 300, M1 Linear: mean 1,268 (SD 116)
- signal ×5, noise 300, M2 Power 0.8: mean 1,268 (SD 116)
- signal ×5, noise 300, M3 Adstock + power: mean 1,215 (SD 119)
- signal ×5, noise 600, M1 Linear: mean 1,248 (SD 236)
- signal ×5, noise 600, M2 Power 0.8: mean 1,248 (SD 236)
- signal ×5, noise 600, M3 Adstock + power: mean 1,197 (SD 242)