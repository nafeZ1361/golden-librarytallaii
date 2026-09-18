# cp2_backtester_integrity_test.py
# CHECKPOINT CP2 - BACKTESTER INTEGRITY (synthetic controlled scenarios + baseline replay)
# READ-ONLY for project source. No orders. No live trading. No installs.
# Synthetic scenarios craft exact signal lists + prices to prove engine semantics.

import os, sys, json
import pandas as pd
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CACHE = os.path.join(ROOT, "project_audit")
os.makedirs(CACHE, exist_ok=True)

import MetaTrader5 as mt5
import backtest.hashem_backtest as hb

if not mt5.initialize():
    print("[error] MT5 unavailable (needed for symbol digits)")
    sys.exit(3)
info = mt5.symbol_info('XAUUSD.')
DIGITS = info.digits if info else None
PIP = (10 ** -DIGITS) * 10 if DIGITS else None
print("[env] digits=%s pip=%s" % (DIGITS, PIP))

PARAMS = dict(backtest_days=30, use_risk_free=False, risk_free_distance_pips=50.0,
              use_sl=True, sl_pips=100.0, use_tp=True, tp_pips=200.0,
              close_opposite_position=False, initial_balance=5000.0,
              position_size_mode='risk_percent', fixed_lot_size=0.01,
              risk_percent=2, risk_based_on='initial', analyze_weekdays=False,
              analyze_time_sessions=False, session_duration_hours=4.0)

results = []
def record(name, ok, detail=""):
    results.append({"test": name, "status": "PASS" if ok else "FAIL", "detail": detail})
    print("[%s] %s %s" % ("PASS" if ok else "FAIL", name, detail))

def flat_df(n=80, base=4400.0):
    t0 = datetime(2026, 1, 5, 0, 0)   # Monday
    times = [(t0 + timedelta(minutes=3 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(n)]
    return pd.DataFrame({"time": times, "open": [base] * n, "high": [base] * n,
                         "low": [base] * n, "close": [base] * n, "volume": [100] * n})

def signals(n, buy_at=(), sell_at=()):
    trig = ["hold"] * n
    conf = ["hold"] * n
    for i in buy_at:
        trig[i] = "buy"; conf[i] = "buy"
    for i in sell_at:
        trig[i] = "sell"; conf[i] = "sell"
    return trig, conf

def run(df, trig, conf):
    buf = io.StringIO() if False else None
    import io as _io
    from contextlib import redirect_stdout
    buf = _io.StringIO()
    with redirect_stdout(buf):
        rep = hb.backtest(df.copy(), list(trig), list(conf), symbol='XAUUSD.', tf='3m', **PARAMS)
    out = buf.getvalue()
    no_trades = "No trades executed" in out
    stats = {"no_trades": no_trades}
    for line in out.splitlines():
        for k in ("Total Trades Executed", "Winning Trades", "Losing Trades",
                  "Win Rate", "Total Profit", "Final Balance", "ROI"):
            if line.strip().startswith(k + ":"):
                v = line.split(":", 1)[1].strip().replace("$", "").replace("%", "").strip()
                try:
                    stats[k] = float(v)
                except ValueError:
                    stats[k] = v
    return stats

ENTRY = 4400.0
SL = ENTRY - 100 * PIP      # 4390
TP = ENTRY + 200 * PIP      # 4420
N = 80

# ---------- S1: BUY entry at close[i], TP hit ----------
df = flat_df(N)
df.loc[20, "high"] = 4425.0; df.loc[20, "low"] = 4419.0   # touches TP only
trig, conf = signals(N, buy_at=(10,))
s1 = run(df, trig, conf)
record("S1 entry@close + TP hit -> single winning trade",
       s1.get("Total Trades Executed") == 1 and s1.get("Win Rate") == 100.0 and s1.get("Total Profit", 0) > 0,
       str({k: s1.get(k) for k in ("Total Trades Executed", "Win Rate", "Total Profit")}))

# ---------- S2: SL hit ----------
df = flat_df(N)
df.loc[20, "low"] = 4385.0; df.loc[20, "high"] = 4391.0   # touches SL only
trig, conf = signals(N, buy_at=(10,))
s2 = run(df, trig, conf)
record("S2 SL hit -> single losing trade",
       s2.get("Total Trades Executed") == 1 and s2.get("Win Rate") == 0.0 and s2.get("Total Profit", 0) < 0,
       str({k: s2.get(k) for k in ("Total Trades Executed", "Win Rate", "Total Profit")}))

# ---------- risk invariant: |S1| / |S2| == TP/SL distance ratio == 2.0 ----------
p1 = s1.get("Total Profit", 0); p2 = s2.get("Total Profit", 0)
ratio_ok = p2 != 0 and abs(abs(p1 / p2) - 2.0) < 1e-9
record("S-risk invariant |profit_TP| / |profit_SL| == 2.0 (2:1 RR exact)", ratio_ok,
       "S1=%s S2=%s ratio=%s" % (p1, p2, (abs(p1 / p2) if p2 else None)))

# ---------- CP2.3: same-candle TP&SL -> engine picks TP (optimistic) ----------
df = flat_df(N)
df.loc[20, "high"] = 4425.0; df.loc[20, "low"] = 4385.0   # BOTH touched in one candle
trig, conf = signals(N, buy_at=(10,))
s3 = run(df, trig, conf)
record("CP2.3 same-candle TP&SL -> engine resolves as TP (optimistic)",
       s3.get("Total Profit") == p1 and s3.get("Win Rate") == 100.0,
       "S3 profit=%s == S1(TP)=%s ; conservative(SL) would be %s ; optimistic delta=%s"
       % (s3.get("Total Profit"), p1, p2, (p1 - p2) if (p1 is not None and p2 is not None) else None))

# ---------- CP2.4: gap handling ----------
df = flat_df(N)
df.loc[11, "open"] = 4430.0; df.loc[11, "high"] = 4430.0; df.loc[11, "low"] = 4429.0
trig, conf = signals(N, buy_at=(10,))
s4 = run(df, trig, conf)
record("CP2.4 gap-up through TP -> exits at TP price (not open) [optimistic]",
       s4.get("Total Profit") == p1,
       "S4 profit=%s == S1(TP@4420)=%s ; realistic open-fill would be %s"
       % (s4.get("Total Profit"), p1, (4430 - ENTRY) / PIP * (p1 / 200.0) if p1 else None))

df = flat_df(N)
df.loc[11, "open"] = 4370.0; df.loc[11, "low"] = 4365.0; df.loc[11, "high"] = 4371.0
trig, conf = signals(N, buy_at=(10,))
s5 = run(df, trig, conf)
record("CP2.4 gap-down through SL -> exits at SL price (not open) [optimistic]",
       s5.get("Total Profit") == p2,
       "S5 profit=%s == S2(SL@4390)=%s ; realistic open-fill loss would be larger" % (s5.get("Total Profit"), p2))

# ---------- CP2.1: second signal while position open must NOT open 2nd position ----------
df = flat_df(N)
df.loc[20, "high"] = 4425.0; df.loc[20, "low"] = 4419.0
trig, conf = signals(N, buy_at=(10, 30))   # second signal at bar 30 while still in trade
s6 = run(df, trig, conf)
record("CP2.1 single-position engine: 2nd signal while open -> ignored",
       s6.get("Total Trades Executed") == 1,
       "trades=%s (must be 1)" % s6.get("Total Trades Executed"))

# ---------- CP2.5: end-of-data open position silently dropped ----------
df = flat_df(40)
trig, conf = signals(40, buy_at=(36,))     # open near the end, never exits
s7 = run(df, trig, conf)
record("CP2.5 end-of-data open position -> silently dropped (0 trades recorded)",
       s7.get("no_trades") is True or s7.get("Total Trades Executed", 0) == 0,
       "result shows no trades; open-trade P/L excluded from statistics (CONFIRMED behavior)")

# ---------- CP2.8: BUY/SELL symmetry ----------
df = flat_df(N)
df.loc[20, "low"] = 4375.0; df.loc[20, "high"] = 4381.0   # sell TP=4380 touched
trig, conf = signals(N, sell_at=(10,))
s8a = run(df, trig, conf)
df = flat_df(N)
df.loc[20, "high"] = 4412.0; df.loc[20, "low"] = 4411.0   # sell SL=4410 touched
trig, conf = signals(N, sell_at=(10,))
s8b = run(df, trig, conf)
sym_ok = (s8a.get("Total Profit") == p1) and (s8b.get("Total Profit") == p2)
record("CP2.8 BUY/SELL symmetry (entry/SL/TP/profit mirrored)", sym_ok,
       "sell-TP=%s (==buy-TP %s) | sell-SL=%s (==buy-SL %s)"
       % (s8a.get("Total Profit"), p1, s8b.get("Total Profit"), p2))

# ---------- invariant: no signal -> no trades ----------
df = flat_df(60)
trig, conf = signals(60)
s9 = run(df, trig, conf)
record("invariant: no signal -> no position/trades",
       s9.get("no_trades") is True or s9.get("Total Trades Executed", 0) == 0)

# ---------- CP2.9: determinism on synthetic scenario ----------
df_r = flat_df(N)
df_r.loc[20, "high"] = 4425.0; df_r.loc[20, "low"] = 4419.0
s1b = run(df_r, *signals(N, buy_at=(10,)))
det_ok = (s1b.get("Total Profit") == p1) and (s1b.get("Total Trades Executed") == s1.get("Total Trades Executed"))
record("CP2.9 determinism (synthetic re-run identical)", det_ok,
       "re-run profit=%s" % s1b.get("Total Profit"))

# ---------- CP2.11: baseline replay on frozen determinism cache ----------
cache_df = os.path.join(CACHE, "determinism_cache", "df.csv")
cache_sig = os.path.join(CACHE, "determinism_cache", "signal.csv")
cache_conf = os.path.join(CACHE, "determinism_cache", "confirmation.csv")
try:
    rdf = pd.read_csv(cache_df); rdf["time"] = pd.to_datetime(rdf["time"])
    rsig = pd.read_csv(cache_sig)["signal"].tolist()
    rconf = pd.read_csv(cache_conf)["confirmation"].tolist()
    if len(rsig) > len(rdf): rsig = rsig[-len(rdf):]
    if len(rconf) > len(rdf): rconf = rconf[-len(rdf):]
    if len(rsig) < len(rdf): rsig += ["hold"] * (len(rdf) - len(rsig))
    if len(rconf) < len(rdf): rconf += ["hold"] * (len(rdf) - len(rconf))
    s11 = run(rdf, rsig, rconf)
    locked = {"Total Trades Executed": 75.0, "Win Rate": 42.67, "Total Profit": 2100.0,
              "Final Balance": 7100.0, "ROI": 42.0}
    match = all(s11.get(k) == v for k, v in locked.items())
    record("CP2.11 baseline replay reproduces locked artifact exactly", match,
           "replay=%s" % {k: s11.get(k) for k in locked})
except FileNotFoundError as exc:
    record("CP2.11 baseline replay", False, "NOT FOUND: %r" % exc)

# ---------- summary ----------
all_pass = all(r["status"] == "PASS" for r in results)
print("\n" + "=" * 70)
print("CP2 VERIFICATION SUMMARY - %s" % ("ALL PASS" if all_pass else "FAILURES PRESENT"))
for r in results:
    print("  [%s] %s" % (r["status"], r["test"]))
print("=" * 70)
with open(os.path.join(CACHE, "cp2_verification.json"), "w", encoding="utf-8") as f:
    json.dump({"checkpoint": "CP2", "status": "PASS" if all_pass else "FAIL",
               "created": datetime.now().isoformat(), "digits": DIGITS, "pip": PIP,
               "tests": results}, f, indent=2, ensure_ascii=False)
print("[saved] project_audit/cp2_verification.json")
sys.exit(0 if all_pass else 1)
