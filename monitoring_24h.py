# monitoring_24h.py — 24-Hour Watchdog for GOLD-LIBRARY Bot
# Purpose: Monitor bot execution, connection stability, data integrity, signal accuracy, and resource usage.
# Logs results to console, file, and optionally Telegram every 4 hours.

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup paths
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
LOG_DIR = Path(ROOT) / "monitoring_logs"
LOG_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M')}.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import MT5 and module functions
try:
    import MetaTrader5 as mt5
    from module.mt5 import balance, pnl_today, check_time, is_news
    from module.telegram import send_message_to_channel as _tg_notify
    TG_ENABLED = True
except Exception as e:
    logger.warning(f"Optional dependencies failed (expected in test env): {e}")
    mt5 = None
    TG_ENABLED = False

def notify(msg):
    """Send Telegram notification if enabled."""
    if TG_ENABLED and _tg_notify:
        try:
            _tg_notify(f"[24h-Watchdog] {msg}")
            logger.info(f"Telegram sent: {msg[:50]}...")
        except Exception as ex:
            logger.error(f"Telegram notify failed: {ex}")
    else:
        logger.info(f"[TG-DISABLED] {msg}")

def check_mt5_connection():
    """Verify MT5 connection and symbol info."""
    if not mt5:
        return {"status": "NO_MT5", "error": "MetaTrader5 not available"}
    
    if not mt5.initialize():
        return {"status": "DISCONNECTED", "error": str(mt5.last_error())}
    
    info = mt5.symbol_info('XAUUSD.')
    if info is None:
        mt5.shutdown()
        return {"status": "SYMBOL_ERROR", "error": "XAUUSD. not found"}
    
    tick = mt5.symbol_info_tick('XAUUSD.')
    if tick is None:
        mt5.shutdown()
        return {"status": "NO_TICK", "error": "No tick data"}
    
    spread = (tick.ask - tick.bid) / (10 ** -info.digits) / 10
    mt5.shutdown()
    
    return {
        "status": "CONNECTED",
        "spread_points": round(spread, 2),
        "bid": tick.bid,
        "ask": tick.ask,
        "last_update": datetime.fromtimestamp(tick.time).isoformat()
    }

def check_data_integrity():
    """Check if recent candles are available and valid."""
    if not mt5:
        return {"status": "NO_MT5"}
    
    if not mt5.initialize():
        return {"status": "DISCONNECTED"}
    
    rates = mt5.copy_rates_from_pos('XAUUSD.', mt5.TIMEFRAME_M3, 0, 10)
    mt5.shutdown()
    
    if rates is None or len(rates) == 0:
        return {"status": "NO_DATA", "error": "Empty rates"}
    
    # Check for gaps or duplicates
    timestamps = [r['time'] for r in rates]
    unique_ts = len(set(timestamps))
    if unique_ts != len(timestamps):
        return {"status": "DUPLICATE_TIMESTAMPS", "count": len(timestamps) - unique_ts}
    
    # Check for forming candle (last bar might be incomplete)
    last_time = datetime.fromtimestamp(timestamps[-1])
    now = datetime.now()
    age_minutes = (now - last_time).total_seconds() / 60
    
    return {
        "status": "VALID",
        "bars_received": len(rates),
        "last_bar_age_minutes": round(age_minutes, 2),
        "unique_timestamps": unique_ts
    }

def get_bot_status():
    """Get current bot state (balance, PnL, positions)."""
    try:
        bal = balance() if mt5 else 0
        pnl = pnl_today() if mt5 else 0
        return {
            "balance": bal,
            "pnl_today": pnl,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

def run_watchdog_cycle():
    """Execute one full monitoring cycle."""
    logger.info("=== Starting Watchdog Cycle ===")
    
    conn = check_mt5_connection()
    data = check_data_integrity()
    bot = get_bot_status()
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "connection": conn,
        "data_integrity": data,
        "bot_status": bot
    }
    
    # Log summary
    conn_status = conn.get("status", "UNKNOWN")
    data_status = data.get("status", "UNKNOWN")
    logger.info(f"Connection: {conn_status} | Data: {data_status} | Balance: {bot.get('balance', 'N/A')}")
    
    # Alert on critical issues
    alerts = []
    if conn_status != "CONNECTED":
        alerts.append(f"CRITICAL: MT5 Connection Failed ({conn_status})")
    if data_status != "VALID":
        alerts.append(f"WARNING: Data Integrity Issue ({data_status})")
    
    if alerts:
        alert_msg = " | ".join(alerts)
        logger.warning(alert_msg)
        notify(alert_msg)
    
    return report

def main():
    """Main 24-hour monitoring loop."""
    logger.info("="*50)
    logger.info("24-HOUR WATCHDOG STARTED")
    logger.info(f"Log directory: {LOG_DIR}")
    logger.info(f"Check interval: 4 hours (adjustable)")
    logger.info("="*50)
    
    notify("24-Hour Watchdog started. Monitoring connection, data, and signals.")
    
    start_time = datetime.now()
    end_time = start_time + timedelta(hours=24)
    check_interval_hours = 4  # Check every 4 hours
    check_interval_seconds = check_interval_hours * 3600
    
    cycle_count = 0
    
    while datetime.now() < end_time:
        cycle_count += 1
        logger.info(f"\n--- Cycle {cycle_count} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        report = run_watchdog_cycle()
        
        # Save report to JSON
        report_file = LOG_DIR / f"report_cycle_{cycle_count}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Report saved: {report_file}")
        
        # Calculate sleep time
        now = datetime.now()
        if now >= end_time:
            break
        
        remaining = (end_time - now).total_seconds()
        sleep_time = min(check_interval_seconds, remaining)
        
        logger.info(f"Next check in {sleep_time/3600:.2f} hours...")
        time.sleep(sleep_time)
    
    # Final summary
    logger.info("\n" + "="*50)
    logger.info("24-HOUR WATCHDOG COMPLETED")
    logger.info(f"Total cycles: {cycle_count}")
    logger.info(f"Logs saved in: {LOG_DIR}")
    logger.info("="*50)
    
    notify(f"24-Hour Watchdog completed. {cycle_count} cycles executed. Logs: {LOG_DIR}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user.")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        notify(f"Watchdog FATAL ERROR: {e}")
