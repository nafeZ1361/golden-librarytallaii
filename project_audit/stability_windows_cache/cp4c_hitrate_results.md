CP4c DIRECTIONAL HIT-RATE DIAGNOSTIC - 2026-09-04 12:53:20.467698
method: Supertrend state flips (baseline params, HA) vs close[i+h] vs close[i]
horizons: 5 and 20 bars | windows: 6 (each 14,400 M3 bars) | metric: hit rate %

Win    Indicator      H   Flips    Hits     Rate%   ExclEnd
-----------------------------------------------------------
1      supertrend     5     254     115     45.28         0
1      supertrend    20     254     115     45.28         0
1      trend_ali      5     170      77     45.29         0
1      trend_ali     20     170      71     41.76         0
2      supertrend     5     257     107     41.63         0
2      supertrend    20     257     101     39.30         0
2      trend_ali      5     157      67     42.68         0
2      trend_ali     20     157      73     46.50         0
3      supertrend     5     241     113     46.89         0
3      supertrend    20     241     129     53.53         0
3      trend_ali      5     157      84     53.50         0
3      trend_ali     20     157      71     45.22         0
4      supertrend     5     235     117     49.79         0
4      supertrend    20     235     115     48.94         0
4      trend_ali      5     176      82     46.59         1
4      trend_ali     20     175      88     50.29         2
5      supertrend     5     262     133     50.76         1
5      supertrend    20     262     135     51.53         1
5      trend_ali      5     141      75     53.19         0
5      trend_ali     20     141      84     59.57         0
6      supertrend     5     266     132     49.62         1
6      supertrend    20     266     136     51.13         1
6      trend_ali      5     142      77     54.23         0
6      trend_ali     20     142      81     57.04         0

AGGREGATE (sum over 6 windows):
  supertrend_h5    flips= 1515 hits=  717 rate=47.33% | Wald95=[44.81% - 49.84%]
  supertrend_h20   flips= 1515 hits=  731 rate=48.25% | Wald95=[45.73% - 50.77%]
  trend_ali_h5     flips=  943 hits=  462 rate=48.99% | Wald95=[45.80% - 52.18%]
  trend_ali_h20    flips=  942 hits=  468 rate=49.68% | Wald95=[46.49% - 52.87%]

reading rule (user-defined): rate ~= 50% -> indicators give no directional edge;
rate clearly >50% -> direction OK, problem is entry timing / trade management.