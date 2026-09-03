# -*- coding: utf-8 -*-
"""
optimizer_walkforward.py
=========================
نسخه‌ی اصلاح‌شده‌ی optimizer.py با اضافه شدن Walk-Forward Validation.

مشکلی که در optimizer.py اصلی حل شده:
---------------------------------------
optimizer() اصلی بهترین پارامتر را فقط بر اساس بالاترین ROI روی یک بازه‌ی
واحد انتخاب می‌کرد. این یعنی هر ترکیبی که "شانسی" روی همان ۳۰ روز خوب کار
کرده باشد، به عنوان برنده انتخاب می‌شود -- حتی اگر هیچ الگوی معنادار و
تکرارپذیری پشتش نباشد (Overfitting کلاسیک).

راه‌حل:
-------
داده‌ی تاریخی به دو بخش تقسیم می‌شود:
  - IN-SAMPLE   (پیش‌فرض ۷۰٪ قدیمی‌تر داده)  -> برای انتخاب بهترین پارامتر
  - OUT-OF-SAMPLE (پیش‌فرض ۳۰٪ جدیدتر داده) -> فقط برای اعتبارسنجی، هرگز
                                                برای انتخاب پارامتر استفاده نمی‌شود

نکته‌ی فنی مهم:
---------------
توابع backtest_ema/backtest_supertrend/... هرکدام مستقیماً از MT5 آخرین
`limit` کندل را می‌گیرند (copy_rates_from_pos از موقعیت ۰ = الان). یعنی
نمی‌شود جداگانه برای هر بخش (IS/OOS) این توابع را با limit متفاوت صدا زد،
چون هر بار داده‌ی متفاوتی (از "الان") برمی‌گردد، نه از بازه‌ی تاریخی موردنظر.

به همین دلیل در این نسخه: سیگنال‌ها یک‌بار روی کل بازه محاسبه می‌شوند
(دقیقاً مثل نسخه‌ی اصلی)، و فقط آرایه‌ی نتیجه (df + سیگنال‌ها) به دو تکه
IS/OOS برش زده می‌شود. این کار داده‌ها را هم‌تراز نگه می‌دارد و از فراخوانی
مجدد و ناهم‌خوان جلوگیری می‌کند.

نحوه‌ی استفاده:
---------------
همان فراخوانی optimizer() قبلی را با optimizer_walkforward() جایگزین کنید:

    from optimizer_walkforward import optimizer_walkforward

    result = optimizer_walkforward(
        symbol='XAUUSD.',
        tf='3m',
        backtest_days=30,
        entry_indicator='kalman_trend',
        conf_indicator='trend_ali',
        in_sample_ratio=0.7,   # جدید
    )

⚠️ این فایل با کد اصلی شما (backtest/optimizer.py و backtest/hashem_backtest.py)
هم‌خوان نوشته شده، اما چون این محیط به MT5 زنده وصل نیست، امکان اجرای
واقعی/تست آن اینجا وجود ندارد. لطفاً قبل از اعتماد به نتایج، آن را روی
سیستم خودتان (با اتصال واقعی MT5) اجرا و خروجی را بررسی کنید.
"""

import itertools
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tqdm import tqdm
except ImportError:  # پیشرفت‌نما اختیاری است
    def tqdm(iterable=None, total=None, desc=None, ncols=None):
        class _Dummy:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def update(self, n=1): pass
            def set_postfix(self, *a, **kw): pass
        return _Dummy()

# این‌ها باید از کدبیس خودتان import شوند (همان چیزی که optimizer.py اصلی
# import می‌کند). این خط‌ها را متناسب با ساختار پروژه‌ی خودتان تنظیم کنید:
from .hashem_backtest import *   # noqa: F401,F403  (backtest_candle, extract_number, ...)
from .indicators import *        # noqa: F401,F403  (backtest_ema, backtest_supertrend, ...)
from .optimizer import (          # noqa: F401
    DEFAULT_PARAMS,
    get_indicator_signals,
    backtest_opt,
)


# ---------------------------------------------------------------------------
# آستانه‌های هشدار Overfitting -- قابل تنظیم
# ---------------------------------------------------------------------------
OOS_MIN_TRADES = 5          # اگر تعداد معاملات OOS کمتر از این باشد، نتیجه غیرقابل اتکاست
OOS_ROI_DROP_WARN = 0.5     # اگر ROI خارج از نمونه کمتر از ۵۰٪ ROI داخل نمونه شد -> هشدار
OOS_WINRATE_DROP_WARN = 15  # اگر Win Rate بیش از ۱۵ واحد درصد افت کرد -> هشدار


def _split_signals(df, entry_signals, confirmation, in_sample_ratio):
    """سیگنال‌ها و df را هم‌طول کرده و به دو بخش IS/OOS برش می‌زند."""
    min_len = min(len(entry_signals), len(confirmation), len(df))
    entry_signals = entry_signals[-min_len:]
    confirmation = confirmation[-min_len:]
    df_aligned = df.iloc[-min_len:].reset_index(drop=True)

    split_idx = int(min_len * in_sample_ratio)
    # حداقل چند کندل برای هر دو بخش لازم است
    split_idx = max(1, min(split_idx, min_len - 1))

    is_slice = {
        'df': df_aligned.iloc[:split_idx].reset_index(drop=True),
        'signals': entry_signals[:split_idx],
        'confirmation': confirmation[:split_idx],
    }
    oos_slice = {
        'df': df_aligned.iloc[split_idx:].reset_index(drop=True),
        'signals': entry_signals[split_idx:],
        'confirmation': confirmation[split_idx:],
    }
    return is_slice, oos_slice


def _run_backtest_on_slice(slice_data, symbol, tf, backtest_params, backtest_days_slice):
    if len(slice_data['df']) < 10:
        return None
    params = dict(backtest_params)
    params['backtest_days'] = backtest_days_slice
    result = backtest_opt(
        slice_data['df'], slice_data['signals'], slice_data['confirmation'],
        symbol=symbol, tf=tf, **params
    )
    return result


def test_single_combination_wfo(args):
    """مثل test_single_combination اصلی، ولی فقط روی بخش IN-SAMPLE امتیاز می‌دهد."""
    (df, symbol, tf, entry_indicator, entry_combo, entry_param_names,
     conf_indicator, fixed_conf_params, backtest_params,
     in_sample_ratio, is_days, oos_days) = args

    entry_params_dict = dict(zip(entry_param_names, entry_combo))

    try:
        entry_signals, _ = get_indicator_signals(df, symbol, tf, entry_indicator, entry_params_dict)
        if entry_signals is None:
            return None

        if conf_indicator and fixed_conf_params:
            _, confirmation = get_indicator_signals(df, symbol, tf, conf_indicator, fixed_conf_params)
        else:
            confirmation = entry_signals

        if confirmation is None:
            return None

        is_slice, _ = _split_signals(df, entry_signals, confirmation, in_sample_ratio)

        is_result = _run_backtest_on_slice(is_slice, symbol, tf, backtest_params, is_days)
        if is_result is None:
            return None

        return {
            'params': entry_params_dict,
            'is_win_rate': is_result['win_rate'],
            'is_roi': is_result['capital_increase_percent'],
            'is_total_trades': is_result['total_trades'],
            'is_max_drawdown': is_result['max_drawdown_percent'],
            'is_final_balance': is_result['final_balance'],
        }

    except Exception:
        return None


def optimizer_walkforward(symbol, tf, backtest_days, entry_indicator,
                           entry_params=None, conf_indicator=None,
                           fixed_conf_params=None, max_workers=4,
                           in_sample_ratio=0.7):
    """
    نسخه‌ی Walk-Forward optimizer(). بهترین پارامتر را فقط روی بخش
    IN-SAMPLE انتخاب می‌کند، سپس همان پارامتر را روی بخش OUT-OF-SAMPLE
    (که در انتخاب هیچ نقشی نداشته) اعتبارسنجی می‌کند.
    """
    print("\n" + "=" * 80)
    print("🚀 WALK-FORWARD OPTIMIZER STARTED")
    print("=" * 80)
    print(f"Symbol: {symbol} | Timeframe: {tf} | Total Days: {backtest_days}")
    print(f"In-Sample: {in_sample_ratio*100:.0f}% | Out-of-Sample: {(1-in_sample_ratio)*100:.0f}%")
    print(f"Entry Indicator: {entry_indicator}")
    if conf_indicator:
        print(f"Confirmation Indicator: {conf_indicator}")
    print("=" * 80 + "\n")

    minutes = extract_number(tf)
    limit = backtest_days * 1440 / minutes

    print("📊 Loading market data (once, full range)...")
    df = backtest_candle(symbol, tf, int(limit))
    print(f"✅ Loaded {len(df)} candles\n")

    is_days = round(backtest_days * in_sample_ratio, 1)
    oos_days = round(backtest_days * (1 - in_sample_ratio), 1)

    if entry_params is None:
        entry_params = DEFAULT_PARAMS.get(entry_indicator, {})

    entry_param_names = list(entry_params.keys())
    entry_param_values = list(entry_params.values())
    entry_combinations = list(itertools.product(*entry_param_values))
    total_combinations = len(entry_combinations)
    print(f"🔍 Total combinations to test (IN-SAMPLE only): {total_combinations}\n")

    backtest_params = {
        'use_risk_free': False,
        'risk_free_distance_pips': 50,
        'use_sl': True,
        'sl_pips': 500,
        'use_tp': True,
        'tp_pips': 1000,
        'close_opposite_position': False,
        'initial_balance': 5000,
        'position_size_mode': 'risk_percent',
        'fixed_lot_size': 0.01,
        'risk_percent': 2,
        'risk_based_on': 'initial',
        'analyze_weekdays': False,
        'analyze_time_sessions': False,
        'session_duration_hours': 4.0,
    }

    best_result = {'params': None, 'is_roi': -float('inf'), 'is_win_rate': -1}
    valid_results = 0

    args_list = [
        (df, symbol, tf, entry_indicator, combo, entry_param_names,
         conf_indicator, fixed_conf_params, backtest_params,
         in_sample_ratio, is_days, oos_days)
        for combo in entry_combinations
    ]

    print(f"⚡ Starting IN-SAMPLE search with {max_workers} workers...\n")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single_combination_wfo, args): args for args in args_list}
        with tqdm(total=total_combinations, desc="Testing (in-sample)", ncols=100) as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    valid_results += 1
                    if result['is_roi'] > best_result['is_roi'] or \
                       (result['is_roi'] == best_result['is_roi'] and result['is_win_rate'] > best_result['is_win_rate']):
                        best_result = result
                        pbar.set_postfix({
                            'Best IS ROI': f"{best_result['is_roi']:.2f}%",
                            'IS Win Rate': f"{best_result['is_win_rate']:.1f}%",
                            'Valid': valid_results
                        })
                pbar.update(1)

    print("\n" + "=" * 80)
    if best_result['params'] is None:
        print("❌ No valid results found in IN-SAMPLE search!")
        print("=" * 80 + "\n")
        return {'error': 'هیچ نتیجه معتبری یافت نشد'}

    # -----------------------------------------------------------------
    # اعتبارسنجی نهایی: همان بهترین پارامتر IS را روی OUT-OF-SAMPLE اجرا کن
    # -----------------------------------------------------------------
    print("🔬 Validating best in-sample params on OUT-OF-SAMPLE data (never seen during selection)...\n")

    entry_signals, _ = get_indicator_signals(df, symbol, tf, entry_indicator, best_result['params'])
    if conf_indicator and fixed_conf_params:
        _, confirmation = get_indicator_signals(df, symbol, tf, conf_indicator, fixed_conf_params)
    else:
        confirmation = entry_signals

    _, oos_slice = _split_signals(df, entry_signals, confirmation, in_sample_ratio)
    oos_result = _run_backtest_on_slice(oos_slice, symbol, tf, backtest_params, oos_days)

    if oos_result is None or oos_result['total_trades'] < OOS_MIN_TRADES:
        oos_summary = {
            'oos_win_rate': None, 'oos_roi': None, 'oos_total_trades':
                0 if oos_result is None else oos_result['total_trades'],
            'oos_max_drawdown': None, 'oos_final_balance': None,
        }
        warning = (f"⚠️ تعداد معاملات Out-of-Sample خیلی کم است "
                   f"({oos_summary['oos_total_trades']} < {OOS_MIN_TRADES}) — "
                   f"نتیجه از نظر آماری غیرقابل اتکاست، بازه‌ی داده را بزرگ‌تر کنید.")
    else:
        oos_summary = {
            'oos_win_rate': oos_result['win_rate'],
            'oos_roi': oos_result['capital_increase_percent'],
            'oos_total_trades': oos_result['total_trades'],
            'oos_max_drawdown': oos_result['max_drawdown_percent'],
            'oos_final_balance': oos_result['final_balance'],
        }
        warning = None
        is_roi = best_result['is_roi']
        oos_roi = oos_summary['oos_roi']
        is_wr = best_result['is_win_rate']
        oos_wr = oos_summary['oos_win_rate']

        if is_roi > 0 and oos_roi <= 0:
            warning = "⚠️ احتمال بالای OVERFITTING: سود در IN-SAMPLE مثبت بود ولی در OUT-OF-SAMPLE منفی/صفر شد."
        elif is_roi > 0 and oos_roi < is_roi * OOS_ROI_DROP_WARN:
            warning = (f"⚠️ احتمال OVERFITTING: ROI خارج از نمونه ({oos_roi:.2f}%) کمتر از "
                       f"{OOS_ROI_DROP_WARN*100:.0f}٪ ROI داخل نمونه ({is_roi:.2f}%) است.")
        elif (is_wr - oos_wr) > OOS_WINRATE_DROP_WARN:
            warning = (f"⚠️ احتمال OVERFITTING: نرخ برد خارج از نمونه {oos_wr:.1f}٪ نسبت به "
                       f"{is_wr:.1f}٪ داخل نمونه، بیش از {OOS_WINRATE_DROP_WARN} واحد افت کرده.")

    result_data = {
        'symbol': symbol,
        'timeframe': tf,
        'total_backtest_days': backtest_days,
        'in_sample_days': is_days,
        'out_of_sample_days': oos_days,
        'entry_indicator': entry_indicator,
        'confirmation_indicator': conf_indicator,
        'best_parameters': best_result['params'],
        'in_sample': {
            'win_rate': best_result['is_win_rate'],
            'roi': best_result['is_roi'],
            'total_trades': best_result['is_total_trades'],
            'max_drawdown': best_result['is_max_drawdown'],
            'final_balance': best_result['is_final_balance'],
        },
        'out_of_sample': oos_summary,
        'overfitting_warning': warning,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_combinations_tested': total_combinations,
        'valid_results': valid_results,
    }

    os.makedirs('optimizer_results', exist_ok=True)
    filename = f"optimizer_results/wfo_{symbol}_{tf}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=4, ensure_ascii=False)

    print("=" * 80)
    print("✅ WALK-FORWARD OPTIMIZATION COMPLETED!")
    print("=" * 80)
    print(f"🏆 Best Parameters (selected on IN-SAMPLE only):")
    for k, v in best_result['params'].items():
        print(f"   {k}: {v}")
    print(f"\n📈 IN-SAMPLE ({is_days} days):")
    print(f"   Win Rate: {best_result['is_win_rate']:.2f}% | ROI: {best_result['is_roi']:.2f}% | "
          f"Trades: {best_result['is_total_trades']} | Max DD: {best_result['is_max_drawdown']:.2f}%")
    print(f"\n📉 OUT-OF-SAMPLE ({oos_days} days, never used for selection):")
    if oos_summary['oos_roi'] is None:
        print(f"   Trades: {oos_summary['oos_total_trades']} (too few to evaluate)")
    else:
        print(f"   Win Rate: {oos_summary['oos_win_rate']:.2f}% | ROI: {oos_summary['oos_roi']:.2f}% | "
              f"Trades: {oos_summary['oos_total_trades']} | Max DD: {oos_summary['oos_max_drawdown']:.2f}%")
    if warning:
        print(f"\n{warning}")
    else:
        print("\n✅ عملکرد Out-of-Sample نسبتاً همخوان با In-Sample است — نشونه‌ی خوبی از پایداری.")
    print(f"\n💾 Results saved to: {filename}")
    print("=" * 80 + "\n")

    return result_data


if __name__ == "__main__":
    symbol = 'XAUUSD.'
    tf = '3m'
    BACKTEST_DAYS = 60  # برای WFO حداقل دو برابر قبل پیشنهاد می‌شود (IS+OOS)

    result = optimizer_walkforward(
        symbol=symbol,
        tf=tf,
        backtest_days=BACKTEST_DAYS,
        entry_indicator='kalman_trend',
        conf_indicator='trend_ali',
        in_sample_ratio=0.7,
    )

    print("🎯 Final Output:")
    print(json.dumps(result, indent=2, ensure_ascii=False))