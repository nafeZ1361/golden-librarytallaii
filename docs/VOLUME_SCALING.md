# افزایش پلکانی حجم با کنترل ریسک

این فرآیند هیچ افزایش حجمی را خودکار اجرا نمی‌کند. ابتدا حجم بر اساس درصد ریسک، سرمایه، فاصلهٔ Entry تا SL و مشخصات Tick محاسبه می‌شود؛ سپس اپراتور فقط پس از دورهٔ مشاهده و بازبینی گزارش، افزایش را به‌صورت دستی تأیید می‌کند.

## تنظیمات

```bash
export MAX_VOLUME_TARGET=0.01
export MIN_OBSERVATION_DAYS=3
export VOLUME_STATE_PATH=volume_state.json
export VOLUME_CHANGE_LOG=logs/volume_changes.log
```

`MAX_VOLUME_TARGET` سقف سخت است و حتی اگر محاسبهٔ ریسک حجم بزرگ‌تری پیشنهاد کند، اجازهٔ عبور نمی‌دهد. برای افزایش سقف، تغییر دستی و آگاهانهٔ Environment و بازبینی مجدد لازم است.

## محاسبه حجم

فرمول risk_corrector پروژه با نسخهٔ مستقل و بدون نیاز به MT5 در `module/volume_control.py` پیاده‌سازی شده است. سپس مقدار ریسک به حجم تبدیل می‌شود:

```text
risk_money = balance × risk_percent / 100
loss_per_lot = abs(entry - SL) / tick_size × tick_value
raw_volume = risk_money / loss_per_lot
final_volume = min(raw_volume, RISK_MAX_VOLUME, MAX_VOLUME_TARGET)
```

محاسبهٔ پیشنهادی:

```bash
python3 scripts/volume_step.py size \
  --balance 1000 \
  --entry 2000 \
  --sl 1990 \
  --tick-size 0.01 \
  --tick-value 1 \
  --trades 20 \
  --profit 30 \
  --base-risk 1 \
  --rr 2 \
  --max-risk 2
```

## دورهٔ مشاهده

بعد از هر تغییر، حداقل ۳ تا ۵ روز معاملاتی باید بگذرد. مقدار را با Environment تعیین کنید:

```bash
MIN_OBSERVATION_DAYS=5
```

در این دوره باید بررسی شود:

- تعداد معاملات
- Net PnL
- Max Drawdown
- تعداد ERRORها
- `REJECTED`ها و علت آن‌ها
- رفتار SL/TP و Spread
- Stateهای `SENT` و `ACCEPTED`

## تأیید افزایش

```bash
python3 scripts/volume_step.py status
python3 scripts/volume_step.py approve \
  --volume 0.02 \
  --risk-percent 1.0 \
  --reason "پنج روز PAPER پایدار، بدون ERROR بحرانی" \
  --approved-by operator
```

اگر دورهٔ مشاهده کامل نشده باشد، دستور با `NO-GO` متوقف می‌شود. هر تغییر در این فایل ثبت می‌شود:

```text
logs/volume_changes.log
```

## Rollback

در صورت افت عملکرد یا افزایش Drawdown:

```bash
python3 scripts/volume_step.py rollback \
  --volume 0.01 \
  --reason "افزایش Drawdown و افت Profit Factor" \
  --approved-by operator
```

Rollback فقط به حجم پایین‌تر اجازه دارد و به‌صورت جداگانه با وضعیت `ROLLBACK` ثبت می‌شود.

## قاعده ایمنی

این ابزار فقط تنظیم حجم کنترل‌شده را نگه می‌دارد. برای اعمال واقعی، `main.py` باید حجم محاسبه‌شده را به `managed_create_order` بدهد و `ExecutionEngine` همچنان سقف `RiskLimits` را اعمال کند. فعال‌کردن LIVE یا افزایش `MAX_VOLUME_TARGET` بدون شواهد PAPER و بازبینی انسانی مجاز نیست.
