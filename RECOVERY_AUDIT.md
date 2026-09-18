# Core Stabilization & Recovery Audit

## نتیجهٔ ممیزی

Repository واقعی بررسی شد. State Machine در `module/state_machine.py` قرار دارد و wrapperهای تولید سیگنال و حلقه‌های مانیتورینگ در `bot.ipynb` به آن متصل شده‌اند. اجرای فعلی برای PAPER مناسب است، اما Recovery کامل هنوز آماده نیست.

## نقشهٔ وضعیت فعلی

```text
SIGNAL → VALIDATED → APPROVED → SENT → ACCEPTED → OPEN → MANAGED → CLOSED
                    ↘ REJECTED
```

انتقال‌های قانونی در `module/state_machine.py` متمرکز شده‌اند و ذخیره‌سازی JSON اتمیک است.

## نقاط قوت تأییدشده

| موضوع | وضعیت |
|---|---|
| جلوگیری از انتقال غیرمجاز | PASS |
| ذخیره‌سازی اتمیک State Machine | PASS |
| جلوگیری اولیه از `trade_id` تکراری در همان پردازش | PASS |
| PAPER/BACKTEST بدون `order_send` | PASS |
| اتصال تولید سیگنال به State Machine | PASS |
| تطبیق OPEN/MANAGED/CLOSED با پوزیشن مشاهده‌شده | PARTIAL |

## شکاف‌های بحرانی Recovery

| شدت | شکاف | اثر |
|---|---|---|
| CRITICAL | `SENT` در `reconcile_all_trade_states` عمداً skip می‌شود | سفارش ارسال‌شده پس از Restart قابل بازیابی نیست |
| CRITICAL | `ACCEPTED` بدون پوزیشن متناظر timeout/recovery ندارد | معامله ممکن است برای همیشه در وضعیت ACCEPTED بماند |
| HIGH | جست‌وجوی پوزیشن با comment، بدون Magic Number یکتا | احتمال تطبیق پوزیشن متعلق به استراتژی/ربات دیگر |
| HIGH | وضعیت‌های حافظه‌ای `trade_states.records` پس از Restart فقط از JSON می‌آیند و با تاریخچه MT5 بازسازی نمی‌شوند | شکاف بین State و واقعیت بروکر |
| HIGH | `SENT` و `ACCEPTED` فاقد timestamp/timeout هستند | تشخیص معاملهٔ گیرکرده ممکن نیست |
| MEDIUM | `trade_id` فعلی برای بعضی wrapperها timeframe=`unknown` دارد | شناسه برای چند استراتژی هم‌زمان به‌اندازهٔ کافی توصیفی نیست |
| MEDIUM | تست Mock برای positions/orders/history MT5 وجود ندارد | Reconciliation واقعی هنوز اثبات نشده است |

## Magic Number

در کد فعلی مقدارهای `magic: 0` در مسیر بستن معامله دیده می‌شود و Magic Number مرکزی و یکتا برای ورودها تعریف نشده است. پیش از PAPER/دمو باید یک `MAGIC_NUMBER` ثابت در تنظیمات تعریف شود و تمام ورودها، بستن‌ها، Pendingها و reconciliation با آن فیلتر شوند.

## تست‌های لازم در گام بعد

1. State transition و رد انتقال غیرمجاز.
2. Restart در وضعیت `SENT` با order موجود.
3. Restart در وضعیت `SENT` بدون order.
4. Restart در وضعیت `ACCEPTED` با position موجود.
5. Restart در وضعیت `ACCEPTED` بدون position.
6. تطبیق فقط با Magic Number صحیح.
7. جلوگیری از duplicate execution پس از Restart.
8. قطع MT5 و retry/recovery.
9. بازیابی Paper Position و Journal.
10. regression برای رفتار ML خاموش/بدون تغییر استراتژی.

## تصمیم اجرایی

تا PASSشدن تست‌های Recovery و Magic Number، ML اضافه نشود و LIVE فعال نشود. گام بعدی باید ساخت یک reconciler مستقل برای `SENT` و `ACCEPTED` با timeout، Magic Number و mockهای MT5 باشد؛ سپس سناریوهای Restart در `tests/` اجرا شوند.
