# راه‌اندازی مانیتورینگ لاگ و هشدار تلگرام

این پروژه یک مانیتور ساده و مستقل دارد که فایل JSONL لاگ ربات را دنبال می‌کند و برای خطاهای مهم، هشدار Telegram می‌فرستد. مانیتور فقط لاگ را می‌خواند و هیچ سفارش یا تغییری در MT5 ایجاد نمی‌کند.

## رویدادهای هشداردهنده

هشدار برای سطح‌های `ERROR` و `CRITICAL` و همچنین رویدادهای `recovery_timeout`، `recovery_error`، `run_once_error` و `trade_rejected` تولید می‌شود. هشدارهای تکراری بر اساس ترکیب سطح، رویداد و پیام، تا مدت مشخص‌شده سرکوب می‌شوند.

## تنظیمات محیطی

مقادیر واقعی توکن و Chat ID را در فایل `.env` خصوصی یا Secret Manager قرار دهید و آن را وارد Git نکنید.

```bash
export TELEGRAM_ALERTS_ENABLED=YES
export TELEGRAM_BOT_TOKEN='توکن واقعی ربات'
export TELEGRAM_CHAT_ID='شناسه چت'
export TELEGRAM_ALERT_TIMEOUT=10
export TELEGRAM_ALERT_COOLDOWN_SECONDS=300
export LOG_FILE=logs/trading.jsonl
export LOG_POLL_INTERVAL_SECONDS=1
```

برای حالت پیش‌فرض ایمن، هشدار خاموش است:

```bash
export TELEGRAM_ALERTS_ENABLED=NO
```

توکن و Chat ID در خروجی ترمینال چاپ نمی‌شوند. اگر توکن در Git، لاگ یا پیام عمومی افشا شد، آن را در BotFather باطل و توکن جدید تولید کنید.

## اجرای دستی

در ترمینال اول ربات را در حالت PAPER اجرا کنید:

```bash
export TRADING_MODE=PAPER
export ENABLE_LIVE_TRADING=NO
python3 main.py
```

در ترمینال دوم مانیتور را اجرا کنید:

```bash
python3 scripts/monitor_logs.py logs/trading.jsonl
```

برای تست یک‌بارهٔ فایل موجود بدون انتظار دائمی:

```bash
python3 - <<'PY'
from pathlib import Path
from scripts.monitor_logs import monitor
monitor(Path('logs/trading.jsonl'), once=True)
PY
```

## اجرای هم‌زمان با systemd در لینوکس

فایل زیر را با مسیر واقعی پروژه جایگزین کنید و به‌عنوان `golden-log-monitor.service` ذخیره کنید. بهتر است متغیرهای حساس از یک فایل Environment با دسترسی محدود خوانده شوند.

```ini
[Unit]
Description=Golden Library trading log monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/golden-librarytallaii
EnvironmentFile=/opt/golden-librarytallaii/.env.private
ExecStart=/usr/bin/python3 /opt/golden-librarytallaii/scripts/monitor_logs.py /opt/golden-librarytallaii/logs/trading.jsonl
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

سپس:

```bash
sudo chmod 600 /opt/golden-librarytallaii/.env.private
sudo systemctl daemon-reload
sudo systemctl enable --now golden-log-monitor.service
sudo systemctl status golden-log-monitor.service
journalctl -u golden-log-monitor.service -f
```

## بررسی سلامت

```bash
# خطاهای مهم
rg 'ERROR|CRITICAL|recovery_timeout|recovery_error|run_once_error|trade_rejected' logs/trading.jsonl

# وضعیت سرویس
systemctl is-active golden-log-monitor.service

# تست ارسال، فقط پس از تنظیم توکن و Chat ID
printf '{"level":"ERROR","event":"run_once_error","message":"test alert"}\n' >> logs/trading.jsonl
```

در تست ارسال، باید یک پیام آزمایشی دریافت شود. سپس خط آزمایشی را حذف یا فایل لاگ آزمایشی جداگانه استفاده کنید.

## محدودیت‌ها

این ابزار جایگزین Health Check یا سیستم مانیتورینگ چندسروره نیست. اگر خود سیستم، شبکه یا سرویس مانیتورینگ خاموش باشد، هشدار ارسال نمی‌شود. برای اجرای چندروزه، لاگ‌روتیشن، فضای دیسک، دسترسی فایل و زنده‌بودن سرویس را روزانه بررسی کنید.
