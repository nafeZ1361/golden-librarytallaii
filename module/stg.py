from .mt5 import *
from .indicators import *

def supertrend_stg(symbol , tf, atr_period=10, multiplier=3.0 , candle_type = 'ha' ,lot = 0.01 , rr = 2 , comment = 'hashem'):
    trend = supertrend(symbol , tf, atr_period, multiplier , candle_type)
    signal = Trend_change_signal(trend['position'])
    price = mt5.symbol_info_tick(symbol)

    if signal == 'buy' :
        sl = trend['value'][-1]
        tp = price.ask + ((price.ask - sl )* rr)
        create_order(symbol , lot , buy , sl , tp , comment)

    if signal == 'sell' :
        sl = trend['value'][-1]
        tp = price.bid - ((sl - price.bid)* rr)
        create_order(symbol , lot , sell , sl , tp , comment)
        
        
        
# module/stg.py
from module.mt5 import *
from module.indicators import *
import MetaTrader5 as mt5
import datetime
import numpy as np
import math
import time
import pandas as pd


# ----------------------------- Utilities: safety & math ----------------------------- #

def _is_finite_number(x) -> bool:
    """بررسی اینکه x عدد معتبر (نه NaN/inf/None) است."""
    try:
        return x is not None and np.isfinite(float(x))
    except Exception:
        return False


def _sorted_by_index(swings: list) -> list:
    """مرتب‌سازی سوئینگ‌ها فقط بر اساس index (بدون اعتماد به ترتیب خروجی zigzag)."""
    return sorted(swings or [], key=lambda s: int(s.get("index", -10**18)))


def _safe_swings(swings: list, last_bar_index: int, confirm_bars: int) -> list:
    """
    حذف سوئینگ‌های مشکوک به repaint (نزدیک به انتهای دیتا).
    فقط سوئینگ‌هایی نگه داشته می‌شوند که:
    1) index آن‌ها کمتر یا مساوی last_bar_index باشد
    2) حداقل confirm_bars کندل از آخر فاصله داشته باشند
    """
    out = []
    for s in swings or []:
        if "index" not in s:
            continue
        idx = int(s["index"])
        # چک کردن اینکه index در محدوده معتبر باشد
        if idx <= last_bar_index and (last_bar_index - idx) >= int(confirm_bars):
            out.append(s)
    return out


def _get_higher_tf(tf_str: str) -> str:
    """تبدیل TF پایین به TF بالاتر برای تأیید روند/OB."""
    tf_l = str(tf_str).lower().strip()
    mapping = {"1m": "5m", "3m": "15m", "5m": "15m"}
    return mapping.get(tf_l, "15m")


def _tf_to_minutes(tf_str: str) -> int:
    """تبدیل رشته تایم‌فریم به دقیقه."""
    tf_l = str(tf_str).lower().strip()
    if tf_l.endswith("m"):
        return int(tf_l[:-1])
    if tf_l.endswith("h"):
        return int(tf_l[:-1]) * 60
    if tf_l.endswith("d"):
        return int(tf_l[:-1]) * 1440
    return 15


def lot_calculator_universal(symbol: str, risk_percent: float, entry: float, sl: float) -> float:
    """
    محاسبه حجم به روش عمومی MT5:
    loss_per_1lot = (|entry-sl| / tick_size) * tick_value
    lot = risk_amount / loss_per_1lot
    
    این فرمول برای Gold, Forex, BTC و همه نمادها کار می‌کند.
    """
    # دریافت اطلاعات نماد و حساب
    info = mt5.symbol_info(symbol)
    acc = mt5.account_info()
    if info is None or acc is None:
        return 0.01

    # محاسبه فاصله ورود تا SL
    dist = abs(float(entry) - float(sl))
    if dist <= 0:
        return float(info.volume_min) if info else 0.01

    # محاسبه مقدار ریسک به دلار
    balance = float(acc.balance)
    risk_amount = balance * (float(risk_percent) / 100.0)

    # دریافت tick_size و tick_value
    tick_size = float(info.trade_tick_size)
    tick_value = float(info.trade_tick_value)

    # بررسی معتبر بودن
    if tick_size <= 0 or tick_value <= 0:
        return float(info.volume_min)

    # محاسبه ضرر به ازای 1 لات
    loss_per_1lot = (dist / tick_size) * tick_value
    if loss_per_1lot <= 0:
        return float(info.volume_min)

    # محاسبه حجم خام
    raw = risk_amount / loss_per_1lot

    # دریافت محدودیت‌های حجم
    vol_min = float(info.volume_min)
    vol_max = float(info.volume_max)
    vol_step = float(info.volume_step)

    if vol_step <= 0:
        vol_step = 0.01

    # گرد کردن به پایین بر اساس vol_step
    lot = math.floor(raw / vol_step) * vol_step
    
    # محدود کردن به بازه مجاز
    lot = max(vol_min, min(vol_max, lot))

    # رُند نهایی برای نمایش
    lot = round(lot, 2)
    
    # اطمینان از اینکه کمتر از حداقل نشود
    if lot < vol_min:
        lot = vol_min
        
    return lot


def consecutive_loss_since_last_win(comment: str, lookback_days: int = 30) -> int:
    """
    شمارش ضررهای متوالی از آخرین معامله سودده (تا سقف lookback_days).
    این تابع تمام معاملات با comment مشخص را می‌گیرد و از جدیدترین شروع به شمارش می‌کند
    تا به اولین معامله سودده برسد.
    """
    # محاسبه بازه زمانی
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(days=int(lookback_days))
    
    # دریافت تاریخچه معاملات
    deals = mt5.history_deals_get(start, now)
    if not deals:
        return 0

    # فیلتر معاملات مربوط به این استراتژی (فقط خروجی‌ها)
    my_deals = [d for d in deals if d.comment == comment and d.entry == mt5.DEAL_ENTRY_OUT]
    
    # مرتب‌سازی از جدید به قدیم
    my_deals.sort(key=lambda x: x.time, reverse=True)

    # شمارش ضررهای متوالی
    cnt = 0
    for d in my_deals:
        if d.profit < 0:
            cnt += 1
        elif d.profit > 0:
            break  # به اولین معامله سودده رسیدیم، زنجیره قطع می‌شود
            
    return cnt


# ----------------------------- ABCD: pattern picking (robust) ----------------------------- #

def pick_abcd_points_bullish(highs: list, lows: list):
    """
    انتخاب نقاط A,B,C برای AB=CD صعودی، فقط بر اساس index:
    - C: آخرین high (بالاترین index در زمان)
    - A: high قبل از C (دومین high از آخر)
    - B: آخرین low بین A و C (در بازه زمانی A < B < C)
    
    شرایط:
    1) A و C باید بالای B باشند
    2) نسبت BC/AB باید در بازه 0.55 تا 0.85 باشد
    3) D محاسبه می‌شود: D = C - AB
    """
    # مرتب‌سازی بر اساس index (از قدیم به جدید)
    highs = _sorted_by_index(highs)
    lows = _sorted_by_index(lows)
    
    # حداقل دو high لازم است
    if len(highs) < 2:
        return None

    # انتخاب C و A
    C = highs[-1]  # آخرین high (جدیدترین)
    A = highs[-2]  # high قبلی (قدیمی‌تر)

    # پیدا کردن B: آخرین low که بین A و C قرار دارد
    b_candidates = [x for x in lows if int(A["index"]) < int(x["index"]) < int(C["index"])]
    if not b_candidates:
        return None
    B = b_candidates[-1]  # آخرین low در این بازه

    # بررسی شرایط قیمتی: A و C باید بالای B باشند
    if not (A["price"] > B["price"] and C["price"] > B["price"]):
        return None

    # محاسبه طول پاها
    leg_AB = float(A["price"]) - float(B["price"])
    leg_BC = float(C["price"]) - float(B["price"])
    
    # بررسی معتبر بودن اعداد
    if not (_is_finite_number(leg_AB) and _is_finite_number(leg_BC)) or leg_AB <= 0:
        return None

    # محاسبه نسبت BC/AB
    ratio = leg_BC / leg_AB
    
    # بررسی بازه قابل قبول نسبت (محدوده تقریبی 0.618)
    if ratio < 0.55 or ratio > 0.85:
        return None

    # محاسبه قیمت D
    D_price = float(C["price"]) - leg_AB
    
    return {
        "type": "bullish",
        "A": A,
        "B": B,
        "C": C,
        "D_price": D_price,
        "ratio": ratio
    }


def pick_abcd_points_bearish(lows: list, highs: list):
    """
    انتخاب نقاط A,B,C برای AB=CD نزولی:
    - C: آخرین low (پایین‌ترین index در زمان)
    - A: low قبل از C
    - B: آخرین high بین A و C
    
    شرایط:
    1) A و C باید پایین‌تر از B باشند
    2) نسبت BC/AB باید در بازه 0.55 تا 0.85 باشد
    3) D محاسبه می‌شود: D = C + AB
    """
    # مرتب‌سازی بر اساس index
    highs = _sorted_by_index(highs)
    lows = _sorted_by_index(lows)
    
    # حداقل دو low لازم است
    if len(lows) < 2:
        return None

    # انتخاب C و A
    C = lows[-1]  # آخرین low (جدیدترین)
    A = lows[-2]  # low قبلی (قدیمی‌تر)

    # پیدا کردن B: آخرین high که بین A و C قرار دارد
    b_candidates = [x for x in highs if int(A["index"]) < int(x["index"]) < int(C["index"])]
    if not b_candidates:
        return None
    B = b_candidates[-1]  # آخرین high در این بازه

    # بررسی شرایط قیمتی: A و C باید پایین‌تر از B باشند
    if not (A["price"] < B["price"] and C["price"] < B["price"]):
        return None

    # محاسبه طول پاها
    leg_AB = float(B["price"]) - float(A["price"])
    leg_BC = float(B["price"]) - float(C["price"])
    
    # بررسی معتبر بودن اعداد
    if not (_is_finite_number(leg_AB) and _is_finite_number(leg_BC)) or leg_AB <= 0:
        return None

    # محاسبه نسبت BC/AB
    ratio = leg_BC / leg_AB
    
    # بررسی بازه قابل قبول
    if ratio < 0.55 or ratio > 0.85:
        return None

    # محاسبه قیمت D
    D_price = float(C["price"]) + leg_AB
    
    return {
        "type": "bearish",
        "A": A,
        "B": B,
        "C": C,
        "D_price": D_price,
        "ratio": ratio
    }


# ----------------------------- ABCD Strategy (fixed) ----------------------------- #

# -----------------------------------------------------------------------
# QUARANTINED (CP19 LOOP-4 / D9): abcd_strategy has NO production caller
# (caller-graph verified in CP19). It is kept for research/reference only.
# Do NOT wire it into any live path without a new pre-registered validation
# cycle. Note: Gartley_Stg / Butterfly_Stg referenced by bot_state.json are
# MISSING DEPENDENCIES (source file never recovered) - registered in CP19.
# -----------------------------------------------------------------------
def abcd_strategy(symbol: str,
                  tf: str,
                  risk: float,
                  state: dict,
                  comment: str = "ABCD_Stg",
                  depth: int = 12,
                  confirm_bars_mult: float = 1.5,
                  lookback_days: int = 30) -> dict:
    """
    استراتژی AB=CD با ویژگی‌های:
    - Swing selection بر اساس index (بدون وابستگی به ترتیب خروجی zigzag)
    - ضد-repaint با confirm_bars (فقط سوئینگ‌های تأیید‌شده)
    - consecutive_loss از آخرین سود (تا سقف 30 روز)
    - lot_calculator_universal (برای همه نمادها)
    - StopLevel + NaN checks
    - ذخیره metadata برای invalidation pending در state
    
    پارامترها:
        symbol: نماد (مثل 'XAUUSD')
        tf: تایم‌فریم (مثل '3m')
        risk: درصد ریسک پایه
        state: دیکشنری state (برای ذخیره اطلاعات بین فراخوانی‌ها)
        comment: شناسه استراتژی (برای فیلتر معاملات)
        depth: عمق zigzag (پیش‌فرض 12)
        confirm_bars_mult: ضریب تأیید سوئینگ (پیش‌فرض 1.5 * depth)
        lookback_days: بازه محاسبه ضررهای متوالی (پیش‌فرض 30)
    
    خروجی:
        state به‌روز شده
    """
    # تضمین وجود state
    if state is None:
        state = {}

    # --- 1) محاسبه ضررهای متوالی و تنظیم سخت‌گیری/ریسک ---
    consecutive_loss = consecutive_loss_since_last_win(comment, lookback_days=lookback_days)

    # فعال‌سازی فیلترهای اضافی بر اساس تعداد ضررها
    use_rsi = consecutive_loss >= 1
    use_macd = consecutive_loss >= 2

    # تنظیم حداقل امتیاز قابل قبول
    min_score = 70
    if consecutive_loss == 1:
        min_score = 75
    elif consecutive_loss >= 2:
        min_score = 80

    # تنظیم ریسک مؤثر (نصف بعد از ضرر)
    risk_effective = float(risk) * (0.5 if consecutive_loss > 0 else 1.0)
    if risk_effective <= 0:
        return state

    # --- 2) دریافت داده کندلی ---
    raw = candle(symbol, tf, 500)
    try:
        df = raw.obj.copy()
    except Exception:
        df = pd.DataFrame(raw[:])

    if df is None or df.empty:
        return state

    # تضمین وجود ستون time
    df = _ensure_time_column(df)
    
    # بررسی ستون‌های ضروری
    if not {"high", "low", "close"}.issubset(df.columns):
        return state

    n = len(df)
    if n < 100:  # حداقل داده لازم
        return state

    # --- 3) ZigZag + Anti-Repaint ---
    zz = zigzag(df, depth=depth)
    highs = zz.get("high", [])
    lows = zz.get("low", [])

    # محاسبه تعداد کندل‌های لازم برای تأیید
    confirm_bars = int(math.ceil(depth * float(confirm_bars_mult)))  # مثلاً 18 برای depth=12
    
    # حذف سوئینگ‌های نزدیک به انتهای دیتا (مشکوک به repaint)
    highs = _safe_swings(highs, last_bar_index=n - 1, confirm_bars=confirm_bars)
    lows = _safe_swings(lows, last_bar_index=n - 1, confirm_bars=confirm_bars)

    # بررسی وجود سوئینگ کافی
    if len(highs) < 2 or len(lows) < 2:
        return state

    # --- 4) محاسبه ATR/ADX با چک NaN ---
    try:
        # دریافت سری ATR
        atr_series = Atr(symbol, tf, 14)
        if atr_series is None or len(atr_series) < 20:
            return state
            
        # استفاده از کندل بسته‌شده قبلی
        atr_current = float(atr_series[-2])
        
        # بررسی معتبر بودن ATR
        if not _is_finite_number(atr_current) or atr_current <= 0:
            return state
            
        # محاسبه میانگین ATR (فقط اعداد معتبر)
        valid_atrs = [x for x in atr_series[-20:] if _is_finite_number(x)]
        atr_avg = float(np.mean(valid_atrs))
        
        # محاسبه نسبت نوسان
        vol_ratio = (atr_current / atr_avg) if (atr_avg and _is_finite_number(atr_avg) and atr_avg > 0) else 1.0
        
    except Exception:
        return state

    try:
        # دریافت سری ADX
        adx_series = adx(symbol, tf)
        if adx_series is None or len(adx_series) == 0:
            return state
            
        adx_val = float(adx_series[-1])
        
        # بررسی معتبر بودن ADX
        if not _is_finite_number(adx_val):
            return state
            
    except Exception:
        return state

    # فیلتر بازار رنج (ADX < 20)
    if adx_val < 20:
        return state

    # --- 5) محاسبه RSI/MACD (فقط در صورت فعال بودن) ---
    rsi_val = 50.0  # مقدار پیش‌فرض خنثی
    if use_rsi:
        try:
            rsi_series = rsi(symbol, tf)
            rsi_val = float(rsi_series[-2])
            if not _is_finite_number(rsi_val):
                return state
        except Exception:
            return state

    macd_hist_curr = macd_hist_prev = 0.0
    if use_macd:
        try:
            m = macd(symbol, tf, 12, 26, 9)
            hist = m.get("histogram", [])
            macd_hist_curr = float(hist[-2])
            macd_hist_prev = float(hist[-3])
            if not (_is_finite_number(macd_hist_curr) and _is_finite_number(macd_hist_prev)):
                return state
        except Exception:
            return state

    # --- 6) تأیید HTF (تایم‌فریم بالاتر) + Order Block ---
    higher_tf = _get_higher_tf(tf)

    # دریافت روند HTF
    try:
        htf_trend_data = trend_ali(symbol, higher_tf)
        htf_trend = str(htf_trend_data["trend"][-1]).lower()
    except Exception:
        htf_trend = "neutral"

    # دریافت Order Blocks
    try:
        ob_data = detect_ob(symbol, higher_tf)
        supply_zones = ob_data.get("supply_zones", [])
        demand_zones = ob_data.get("demand_zones", [])
    except Exception:
        supply_zones, demand_zones = [], []

    # تنظیم حدود RSI بر اساس تایم‌فریم
    tf_mins = _tf_to_minutes(tf)
    rsi_lower, rsi_upper = (20, 80) if tf_mins < 15 else (30, 70)

    # --- 7) تشخیص الگو (robust) ---
    bull_pattern = pick_abcd_points_bullish(highs, lows)
    bear_pattern = pick_abcd_points_bearish(lows, highs)

    # اگر هیچ الگوی معتبر نیافتیم
    if bull_pattern is None and bear_pattern is None:
        return state

    # --- 8) سیستم امتیازدهی (0-100) ---
    def score_pattern(pattern: dict, direction: str) -> float:
        """محاسبه امتیاز الگو بر اساس چند معیار."""
        score = 0.0

        # 1) کیفیت هندسی الگو (حداکثر 25 امتیاز)
        # نزدیکی نسبت BC/AB به 0.7 (ایده‌آل)
        target_ratio = 0.7
        max_diff = 0.15
        diff = abs(float(pattern["ratio"]) - target_ratio)
        geo_factor = max(0.0, 1.0 - diff / max_diff)
        score += geo_factor * 25.0

        # 2) تأیید HTF (حداکثر 20 امتیاز)
        if direction == "bullish":
            score += 20.0 if htf_trend == "long" else (5.0 if htf_trend == "neutral" else 0.0)
        else:
            score += 20.0 if htf_trend == "short" else (5.0 if htf_trend == "neutral" else 0.0)

        # 3) تأیید Order Block (حداکثر 20 امتیاز)
        D_price = float(pattern["D_price"])
        margin = atr_current * 0.5  # حاشیه نصف ATR
        ob_score = 0.0

        if direction == "bullish":
            # چک کردن Demand Zones
            for ob in demand_zones:
                if ob.get("status") != "active":
                    continue
                top = ob.get("top")
                bottom = ob.get("bottom")
                if top is None or bottom is None:
                    continue
                # بررسی هم‌پوشانی D با OB
                if (float(bottom) - margin) <= D_price <= (float(top) + margin):
                    ob_score = 20.0
                    break
        else:
            # چک کردن Supply Zones
            for ob in supply_zones:
                if ob.get("status") != "active":
                    continue
                top = ob.get("top")
                bottom = ob.get("bottom")
                if top is None or bottom is None:
                    continue
                if (float(bottom) - margin) <= D_price <= (float(top) + margin):
                    ob_score = 20.0
                    break

        score += ob_score

        # 4) مومنتوم (RSI/MACD) (حداکثر 15 امتیاز)
        mom_score = 0.0
        
        if use_rsi:
            if direction == "bullish":
                # برای خرید، RSI پایین‌تر بهتر است
                if rsi_val < 50:
                    mom_score += 8.0
                if rsi_val < (rsi_lower + 5):
                    mom_score += 4.0
            else:
                # برای فروش، RSI بالاتر بهتر است
                if rsi_val > 50:
                    mom_score += 8.0
                if rsi_val > (rsi_upper - 5):
                    mom_score += 4.0

        if use_macd:
            # بررسی جهت هیستوگرام MACD
            if direction == "bullish" and macd_hist_curr > macd_hist_prev:
                mom_score += 3.0
            if direction == "bearish" and macd_hist_curr < macd_hist_prev:
                mom_score += 3.0

        score += min(mom_score, 15.0)

        # 5) نوسان‌پذیری (حداکثر 10 امتیاز)
        # بازه مطلوب نوسان
        if 0.7 <= vol_ratio <= 1.8:
            vol_score = 10.0
        elif 0.5 <= vol_ratio < 0.7 or 1.8 < vol_ratio <= 2.5:
            vol_score = 5.0
        else:
            vol_score = 0.0
            
        score += vol_score

        # محدود کردن امتیاز نهایی به بازه [0, 100]
        return float(max(0.0, min(100.0, score)))

    # محاسبه امتیاز الگوها
    bull_score = score_pattern(bull_pattern, "bullish") if bull_pattern else None
    bear_score = score_pattern(bear_pattern, "bearish") if bear_pattern else None

    # --- 9) انتخاب بهترین الگو ---
    best = None
    best_dir = None
    best_score = -1.0

    # بررسی الگوی صعودی
    if bull_score is not None and bull_score >= min_score:
        best = bull_pattern
        best_dir = "bullish"
        best_score = bull_score

    # بررسی الگوی نزولی (اگر امتیازش بیشتر است)
    if bear_score is not None and bear_score >= min_score and bear_score > best_score:
        best = bear_pattern
        best_dir = "bearish"
        best_score = bear_score

    # اگر هیچ الگویی به حداقل امتیاز نرسید
    if best is None:
        return state

    # --- 10) ساخت سفارش Pending با چک StopLevel ---
    # دریافت اطلاعات نماد و قیمت فعلی
    tick = mt5.symbol_info_tick(symbol)
    info = mt5.symbol_info(symbol)
    if tick is None or info is None:
        return state

    # محاسبه حداقل فاصله SL از قیمت
    point = float(info.point)
    broker_min_stop = float(info.trade_stops_level) * point
    min_stop_distance = max(point * 10.0, broker_min_stop)

    # استخراج اطلاعات الگو
    D_price = float(best["D_price"])
    C_price = float(best["C"]["price"])
    C_index = int(best["C"]["index"])

    # جلوگیری از تکرار سیگنال روی همان C
    if best_dir == "bullish":
        if state.get(f"{comment}_bull_idx") == C_index:
            return state
    else:
        if state.get(f"{comment}_bear_idx") == C_index:
            return state

    # --- 11) محاسبه SL/TP و ثبت سفارش ---
    if best_dir == "bullish":
        # بررسی اینکه قیمت فعلی بالاتر از D است (شرط Buy Limit)
        if tick.ask <= D_price:
            return state

        # محاسبه SL (زیر D به اندازه 1.5 * ATR)
        sl = D_price - (atr_current * 1.5)
        
        # اعمال حداقل فاصله بروکر
        if (D_price - sl) < min_stop_distance:
            sl = D_price - min_stop_distance

        # TP در نقطه C
        tp = C_price

        # بررسی نهایی معتبر بودن اعداد
        if not (_is_finite_number(sl) and _is_finite_number(tp)):
            return state

        # محاسبه حجم
        lot = lot_calculator_universal(symbol, risk_effective, D_price, sl)
        if lot <= 0:
            return state

        # ثبت سفارش Buy Limit
        res = pending_order(symbol, lot, mt5.ORDER_TYPE_BUY_LIMIT, D_price, sl, tp, comment)

        # اگر سفارش با موفقیت ثبت شد
        if res is not None and getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
            # ذخیره index برای جلوگیری از تکرار
            state[f"{comment}_bull_idx"] = C_index

            # ذخیره اطلاعات برای مدیریت invalidation
            state[f"{comment}_last_setup"] = {
                "direction": "buy",
                "C_index": C_index,
                "C_price": C_price,
                "D_price": D_price,
                "time_setup": time.time(),
                "tf": tf,
                "score": float(best_score),
            }

    else:  # bearish
        # بررسی اینکه قیمت فعلی پایین‌تر از D است (شرط Sell Limit)
        if tick.bid >= D_price:
            return state

        # محاسبه SL (بالای D به اندازه 1.5 * ATR)
        sl = D_price + (atr_current * 1.5)
        
        # اعمال حداقل فاصله بروکر
        if (sl - D_price) < min_stop_distance:
            sl = D_price + min_stop_distance

        # TP در نقطه C
        tp = C_price

        # بررسی نهایی معتبر بودن اعداد
        if not (_is_finite_number(sl) and _is_finite_number(tp)):
            return state

        # محاسبه حجم
        lot = lot_calculator_universal(symbol, risk_effective, D_price, sl)
        if lot <= 0:
            return state

        # ثبت سفارش Sell Limit
        res = pending_order(symbol, lot, mt5.ORDER_TYPE_SELL_LIMIT, D_price, sl, tp, comment)

        # اگر سفارش با موفقیت ثبت شد
        if res is not None and getattr(res, "retcode", None) == mt5.TRADE_RETCODE_DONE:
            # ذخیره index برای جلوگیری از تکرار
            state[f"{comment}_bear_idx"] = C_index
            
            # ذخیره اطلاعات برای مدیریت invalidation
            state[f"{comment}_last_setup"] = {
                "direction": "sell",
                "C_index": C_index,
                "C_price": C_price,
                "D_price": D_price,
                "time_setup": time.time(),
                "tf": tf,
                "score": float(best_score),
            }

    return state


# ----------------------------- Pending Orders Manager (TTL + Invalidation) ----------------------------- #

def manage_pending_orders(symbol: str,
                          state: dict,
                          comment: str = "ABCD_Stg") -> dict:
    """
    مدیریت سفارشات Pending این استراتژی:
    - TTL (Time To Live) بر اساس تایم‌فریم
    - Invalidation: اگر قیمت از C عبور کند، سفارش کنسل می‌شود
    
    منطق TTL:
    - 1m → 30 دقیقه
    - 3m → 1 ساعت
    - 5m → 2 ساعت
    - 15m → 4 ساعت
    - بیشتر → 6 ساعت
    
    منطق Invalidation:
    - برای Buy Limit: اگر قیمت (bid) بالاتر از C برود
    - برای Sell Limit: اگر قیمت (ask) پایین‌تر از C برود
    """
    # بررسی وجود state
    if state is None:
        return {}

    # دریافت سفارشات باز این نماد
    orders = mt5.orders_get(symbol=symbol)
    if not orders:
        return state

    # دریافت قیمت فعلی
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return state

    # دریافت اطلاعات آخرین setup
    last_setup = state.get(f"{comment}_last_setup")
    if not last_setup:
        return state

    # استخراج تایم‌فریم و محاسبه TTL
    tf = str(last_setup.get("tf", "3m"))
    tf_m = _tf_to_minutes(tf)

    # تعیین TTL بر اساس تایم‌فریم
    if tf_m <= 1:
        ttl = 30 * 60  # 30 دقیقه
    elif tf_m <= 3:
        ttl = 60 * 60  # 1 ساعت
    elif tf_m <= 5:
        ttl = 2 * 60 * 60  # 2 ساعت
    elif tf_m <= 15:
        ttl = 4 * 60 * 60  # 4 ساعت
    else:
        ttl = 6 * 60 * 60  # 6 ساعت

    # زمان فعلی
    now = time.time()
    
    # استخراج اطلاعات برای invalidation
    c_price = last_setup.get("C_price")
    direction = last_setup.get("direction")

    # پردازش هر سفارش
    for o in orders:
        # فقط سفارشات این استراتژی
        if o.comment != comment:
            continue

        # 1) بررسی TTL (زمان انقضا)
        order_age = now - float(o.time_setup)
        if order_age > ttl:
            remove_order(o.ticket)
            continue

        # 2) بررسی Invalidation (عبور قیمت از C)
        if _is_finite_number(c_price):
            c_price = float(c_price)

            # برای Buy Limit: اگر قیمت بالای C رفت، الگو invalidate شده
            if direction == "buy" and tick.bid > c_price:
                remove_order(o.ticket)
                continue

            # برای Sell Limit: اگر قیمت پایین‌تر از C رفت، الگو invalidate شده
            if direction == "sell" and tick.ask < c_price:
                remove_order(o.ticket)
                continue

    return state        