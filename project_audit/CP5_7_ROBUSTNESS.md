# CP5.7 — ROBUSTNESS
Generated: 2026-09-05T16:33:57 | disk-only, no MT5, frozen dataset be4fa581..., frozen
  sources cp5-source-freeze-v1. Grids + classification rules registered BEFORE evaluation (see module header). Full grids reported; nothing selected.

## Anchor gate (reimplementations must equal frozen strategies byte-identically)
- window 1: A1 anchor=True | A2 anchor=True
- window 2: A1 anchor=True | A2 anchor=True
- window 3: A1 anchor=True | A2 anchor=True
- window 4: A1 anchor=True | A2 anchor=True
- window 5: A1 anchor=True | A2 anchor=True
- window 6: A1 anchor=True | A2 anchor=True
- ANCHOR GATE: PASS

## A1 parameter grid (12 combos x h5/h20) — full report
- {"rsi_len": 10, "thr": [30, 70], "bb": [20, 2.0]}: h5 ev=2358 rate=53.82 CI=[51.80, 55.83] | h20 rate=52.95
- {"rsi_len": 10, "thr": [30, 70], "bb": [15, 3.0]}: h5 ev=2095 rate=54.94 CI=[52.81, 57.07] | h20 rate=52.46
- {"rsi_len": 10, "thr": [25, 75], "bb": [20, 2.0]}: h5 ev=1430 rate=56.50 CI=[53.93, 59.07] | h20 rate=53.99
- {"rsi_len": 10, "thr": [25, 75], "bb": [15, 3.0]}: h5 ev=1216 rate=56.58 CI=[53.79, 59.36] | h20 rate=52.51
- {"rsi_len": 14, "thr": [30, 70], "bb": [20, 2.0]} [BASELINE]: h5 ev=1376 rate=55.60 CI=[52.97, 58.22] | h20 rate=51.97
- {"rsi_len": 14, "thr": [30, 70], "bb": [15, 3.0]}: h5 ev=1187 rate=55.27 CI=[52.44, 58.09] | h20 rate=50.93
- {"rsi_len": 14, "thr": [25, 75], "bb": [20, 2.0]}: h5 ev=659 rate=57.66 CI=[53.89, 61.44] | h20 rate=52.50
- {"rsi_len": 14, "thr": [25, 75], "bb": [15, 3.0]}: h5 ev=562 rate=56.58 CI=[52.49, 60.68] | h20 rate=51.60
- {"rsi_len": 20, "thr": [30, 70], "bb": [20, 2.0]}: h5 ev=639 rate=55.40 CI=[51.54, 59.25] | h20 rate=51.64
- {"rsi_len": 20, "thr": [30, 70], "bb": [15, 3.0]}: h5 ev=552 rate=55.25 CI=[51.11, 59.40] | h20 rate=51.99
- {"rsi_len": 20, "thr": [25, 75], "bb": [20, 2.0]}: h5 ev=245 rate=53.06 CI=[46.81, 59.31] | h20 rate=49.80
- {"rsi_len": 20, "thr": [25, 75], "bb": [15, 3.0]}: h5 ev=217 rate=50.69 CI=[44.04, 57.34] | h20 rate=47.47

## A2 parameter grid (9 combos x h5/h20) — full report
- OR=90min vol=1.2: h5 ev=4116 rate=50.97 CI=[49.44, 52.50] | h20 rate=51.40
- OR=90min vol=1.5: h5 ev=1957 rate=51.71 CI=[49.50, 53.93] | h20 rate=51.92
- OR=90min vol=2.0: h5 ev=1306 rate=54.36 CI=[51.66, 57.07] | h20 rate=54.06
- OR=120min vol=1.2: h5 ev=4098 rate=50.24 CI=[48.71, 51.77] | h20 rate=50.82
- OR=120min vol=1.5 [BASELINE]: h5 ev=1855 rate=52.56 CI=[50.29, 54.83] | h20 rate=51.65
- OR=120min vol=2.0: h5 ev=1169 rate=52.95 CI=[50.09, 55.81] | h20 rate=53.04
- OR=150min vol=1.2: h5 ev=3338 rate=51.05 CI=[49.35, 52.74] | h20 rate=51.45
- OR=150min vol=1.5: h5 ev=1478 rate=53.25 CI=[50.70, 55.79] | h20 rate=51.63
- OR=150min vol=2.0: h5 ev=707 rate=50.78 CI=[47.09, 54.46] | h20 rate=50.50

## SL/TP economic grid (9 combos x 2 strategies, frozen signals/engine) — full report
- A1 SL=75 TP=150: trades=1106 netC0=$9750 expC0=$8.82 expC1=$5.32
- A1 SL=75 TP=200: trades=1037 netC0=$11505 expC0=$11.09 expC1=$7.59
- A1 SL=75 TP=300: trades=908 netC0=$9458 expC0=$10.42 expC1=$6.92
- A1 SL=100 TP=150: trades=1043 netC0=$8450 expC0=$8.10 expC1=$4.60
- A1 SL=100 TP=200 [BASELINE]: trades=970 netC0=$10700 expC0=$11.03 expC1=$7.53
- A1 SL=100 TP=300: trades=829 netC0=$9100 expC0=$10.98 expC1=$7.48
- A1 SL=150 TP=150: trades=945 netC0=$3255 expC0=$3.44 expC1=$-0.06
- A1 SL=150 TP=200: trades=847 netC0=$6125 expC0=$7.23 expC1=$3.73
- A1 SL=150 TP=300: trades=711 netC0=$4410 expC0=$6.20 expC1=$2.70
- A2 SL=75 TP=150: trades=986 netC0=$6825 expC0=$6.92 expC1=$3.42
- A2 SL=75 TP=200: trades=894 netC0=$8287 expC0=$9.27 expC1=$5.77
- A2 SL=75 TP=300: trades=785 netC0=$4388 expC0=$5.59 expC1=$2.09
- A2 SL=100 TP=150: trades=912 netC0=$4550 expC0=$4.99 expC1=$1.49
- A2 SL=100 TP=200 [BASELINE]: trades=816 netC0=$8700 expC0=$10.66 expC1=$7.16
- A2 SL=100 TP=300: trades=693 netC0=$2700 expC0=$3.90 expC1=$0.40
- A2 SL=150 TP=150: trades=789 netC0=$5565 expC0=$7.05 expC1=$3.55
- A2 SL=150 TP=200: trades=704 netC0=$7665 expC0=$10.89 expC1=$7.39
- A2 SL=150 TP=300: trades=585 netC0=$5040 expC0=$8.62 expC1=$5.12

## Robustness classification (pre-registered rules)
- A1 h5: 10/12 variants pass -> ROBUST (>=2/3 of variants keep LB>50)
- A1 h20: 3/12 -> FRAGILE (<1/3 of variants keep LB>50)
- A2 h5: 4/9 -> MIXED
- A2 h20: 2/9 -> FRAGILE (<1/3 of variants keep LB>50)
- A1 SL/TP grid: 9/9 cells expC0>0, 8/9 expC1>0 | baseline expC0=11.03 -> region-positive
- A2 SL/TP grid: 9/9 cells expC0>0, 9/9 expC1>0 | baseline expC0=10.66 -> region-positive

## Interpretation guard
- Grid variants are SENSITIVITY EVIDENCE about the registered points, NOT new hypotheses; no variant is claimed as edge (registered §14 discipline).
- Regression check: frozen CSVs and sources untouched (script writes only its own artifacts); anchor gate already proved frozen outputs unchanged.
