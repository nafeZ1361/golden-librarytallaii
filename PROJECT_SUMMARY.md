# خلاصه جامع پروژه XAUUSD ML / Golden Library — وضعیت، مشکلات، راه‌حل‌ها و شواهد

**تاریخ:** 2026-10-03 | **نویسنده:** بررسی read-only چندمرحله‌ای (Qwen) | **حالت مخزن رسمی:** `nafeZ1361/golden-librarytallaii` @ main

> این سند فقط «خلاصه» است و مجوز merge/LIVE نمی‌دهد. همه وضعیت‌های گیت‌شده در انتها بدون تغییر باقی‌اند.

---

## بخش ۱ — نمای کلی و وضعیت فعلی

| مورد | مقدار / وضعیت |
|---|---|
| کامیت بازیابی مورد انتظار | `bba24476ca474952a1c69296ca9a3e4c60e660fc` (merge PR #8 stage-7-clean-recovery) ✅ تأیید شد |
| HEAD رسمی بررسی‌شده (Windows baseline) | `674e781bdcf15617849583aad0cc79badbf07478` |
| مدل Stage 7.1 | بازنده: Net PnL = -$49,197 ، PF = 0.86 ، Holdout Acc = 51% |
| Governance Cross-Validation | **BLOCKED** (Constitution v0.9 FROZEN در هیچ ref گیت وجود ندارد) |
| PaperBroker Balance/Equity | **P0 باز** (قرارداد حسابداری نقض است) |
| Safety Gates در PAPER عادی | **غیرفعال عملاً** (mark-to-market در run cycle صدا زده نمی‌شود) |
| PR #4 | Request changes |
| LIVE | NO-GO / DENIED |
| Stage 7.1 | BLOCKED (منتظر Human Confirmation + رفع P0ها) |

**ریشه مشکل کلان:** چند سیستم موازی (main.py / bot.ipynb legacy / Phase 5 / Stage 7 / research_harness) با قرارداد واحد کنترل‌نشده در یک repo. «چند سیستم قابل‌باور در یک مخزن، در حالی که حاکمیت آن‌ها را یک سیستم فرض می‌کند.»

---

## بخش ۲ — جدول کامل مشکلات و نحوه رفع

### P0 — بلاکرهای الزامی قبل از هر پیشرفتی

| # | مشکل | محل دقیق | راه‌حل تأییدشده |
|---|---|---|---|
| P0-1 | نقض قرارداد Balance/Equity: equity باید Balance + Unrealized باشد؛ فرمول mark با close ناسازگار (double-counting هزینه)؛ legacy state بدون balance سود بسته‌شده را از دست می‌دهد | `module/paper.py` (equity ~198-205، mark ~161-183، load ~290+) | تفکیک رسمی: `Balance = Initial + Σ NetPnL(بسته‌ها)`، `Equity = Balance + Σ Unrealized(بازها)`؛ یکسان‌سازی فرمول profit در mark و close (هر دو net از commission/spread)؛ مهاجرت legacy با بازیابی از تاریخچه trades بسته‌شده؛ ۴ تست رگرسیون (Open/Close/LegacyLoad/Chronology) |
| P0-2 | Drawdown Gate در PAPER عادی غیرفعال: `equity_history` فقط در replay پر می‌شود؛ `run_once()` هرگز mark نمی‌زند ⇒ drawdown≈0 و گیت هرگز trigger نمی‌شود | `main.py`, `module/paper.py:203-205,227-241` | افزودن mark-to-market به چرخه، **پیش از** ریسک‌گیت. ترتیب اجباری: tick → mark → update equity/drawdown → risk gate → order → checkpoint |
| P0-3 | Spread Gate مرده: `RISK_MAX_SPREAD` هیچ‌وقت چک نمی‌شود چون spread وارد request نمی‌شود | `module/execution.py` / `managed_create_order` | خواندن bid/ask از snapshot واحد `symbol_info_tick()`؛ ثبت واحد (points/pips)؛ نبود tick یا bid/ask نامعتبر ⇒ Reject fail-closed؛ لاگ spread در request؛ تست از مسیر واقعی که ثابت کند سفارش reject به broker نمی‌رسد |
| P0-4 | Trade ID شکننده: وابستگی به `tick.time`/`time.time()` ⇒ نقض idempotency | `main.py` signal path | `trade_id = sha256(canonical_json{symbol, timeframe, closed_candle_time, signal_type, strategy_id, strategy_version})`؛ نبود candle time ⇒ Fail closed (بدون fallback به wall-clock) |
| P0-5 | مسیر legacy قابل اجرا: `bot.ipynb` شامل mt5.initialize ×3، create_order ×20، positions_get ×10 — دور زدن گیت‌های main | `bot.ipynb`, `module/mt5.py` | به ترتیب: static guard → انتقال referenceها به main.py → import-side-effect test → سپس archive/legacy_unsafe/ (read-only). حذف Singletonهای global و lazy-init؛ خروج import مستقیم MT5 و wrapperهای سفارش از مسیر رسمی |
| P0-6 | Recovery اثبات‌نشده: سناریوهای SENT/ACCEPTED/timeout/restart بدون تست matrix (منطق timeout پیاده شده ولی تست نشده) | `module/recovery.py`, `RECOVERY_AUDIT.md` | Matrix کامل ۷ سناریو (SENT±order/position/timeout، ACCEPTED±evidence/timeout، OPEN با position ناپدید) با injectable clock و تطبیق magic/ticket/comment/trade_id |
| P0-7 | Leakage split: `guard = max(horizon, purge)` در Phase 5 ممکن است label-width را پوشش ندهد؛ تست‌ها فقط مرز row چک می‌کنند؛ منطق split Phase5 ≠ Stage7 | `time_series_validation.py:159,245` | purge بر اساس بازه واقعی label interval؛ تست prefix-invariance: تغییر داده آینده نباید prediction گذشته را عوض کند |
| P0-8 | Baseline Freeze نامعتبر (خروجی Windows): ~۱۵۰ فایل untracked آلوده، لاگ تست قطع‌شده، FAIL آشکار `test_grid_and_best_are_deterministic`، بدون provenance binding | محیط Windows `ketabtallaee-backup` | STEP B-1..B-5: clone تمیز از origin → manifest جدا برای untrackedها → ثبت remote/log/status صفر → اجرای کامل تست با log کامل+sha256 → baseline_manifest.json (commit/tree/env/test hashes) |

### P1 — مهم (بعد از P0)

| # | مشکل | محل | راه‌حل |
|---|---|---|---|
| P1-1 | سه قرارداد داده موازی (M1-resample canonical ≠ copy_rates_from_pos در main ≠ harness) | `main.py:170-174`, `DATA_FLOW.md`, `research_harness.py` | MarketDataGateway مشترک؛ مقایسه قبل از SHA باید شامل: timestamp/timezone، تعداد ردیف، OHLCV نرمال‌شده، duplicate policy، chronology، رفتار candle ناقص |
| P1-2 | چند source of truth برای feature/target/split (drift بین Phase5 و Stage7) | `feature_engineering.py`, `target_generation.py`, `time_series_validation.py`, `stage7/pipeline.py` | یکی‌سازی یا version-bind کردن ماژول مشترک |
| P1-3 | مالکان متعدد state (trade_state/paper_state/events/volume/results/evidence) | root json files | ایزولاسیون `runs/<run_id>/{state,evidence,logs}` + manifest مستقل هر run |
| P1-4 | run1/run2 اجرای مستقل نیستند (predictions/signals/equity/trades/split md5 یکسان) — فقط deterministic rerun | `stage7/evidence/run1,run2` | تفکیک deterministic rerun از robustness experiment (seed/window مستقل) |
| P1-5 | model cost متفاوت بین Stage7/Paper/legacy backtest (spread/commission/PnL) | چند فایل | یکسان‌سازی CostContract؛ تعریف دقیق جای commission/spread/swap/fee تا double-count نشود |
| P1-6 | import-time side effects (MT5 init، Telegram print) | `module/mt5.py`, `backtest/backtester.py` | lazy init؛ تست import بدون MT5/Telegram |
| P1-7 | state_io قدیمی: persist اتمیک ندارد؛ خطا→state خالی | `module/state_io.py` (+BOM U+FEFF) | atomic write (temp+fsync+rename) + versioned schema + رفع BOM |
| P1-8 | indicatorهای look-ahead (rolling center=True، shift(-n)) | `module/indicators.py:403-406,1037` | reachability test؛ اگر وارد feature می‌شوند حذف/isolation؛ وگرنه visualization-only علامت‌گذاری |
| P1-9 | Reconciliation per-trade API call (فشار MT5) | recovery path | batch reconciliation |
| P1-10 | CI/Branch Protection اجباری نیست | GitHub settings | workflow شامل compileall، pytest، import tests، leakage/prefix-invariance، static legacy checks، artifact hygiene + required status checks روی main |
| P1-11 | GO_LIVE_CHECKLIST بدون evidence | `GO_LIVE_CHECKLIST.md` | پابرجا NO-GO تا PAPER واقعی کامل |

### P2 — بهداشت

- حذف `.pyc/__pycache__` از PR (۸۹ فایل باینری)؛ در clone تمیز چک شود: `git ls-files '*.pyc'`=0، `ls-files|grep __pycache__`=0، `git diff --check` PASS، `status --short` خالی (نه فقط git status محلی).
- تعیین تکلیف `skll/` (۸۸۱ فایل tracked vendored).
- اصلاح `.gitignore` ضعیف‌شده در نسخه مقابل.
- README/نقشه معماری؛ هم‌ترازی PR با main (Ahead 5 / Behind 7).
- **ثبت Constitution در ref رسمی**: فقط با تصمیم L3 Human Owner (push تحت change record یا اعلام منبع حقیقت). ساخت/کپی توسط agent ممنوع.

---

## بخش ۳ — آنچه همین حالا رفع و TEST شده (شاهد اجرایی، تکرارپذیر)

محیط: Linux `/workspace/golden-clone` @ `bba2447` + اصلاحات working-tree (commit نشده، منتظر review).

| اقدام | قبل | بعد (اجراشده و تأییدشده) |
|---|---|---|
| رفع شکست H3 در grid (بازگردانی برش قطعی first-N با itertools.islice زیر سقف ۵۰ + اصلاح ۲ تست معیوب) | Ran 146 → 2 failures + 8 errors | — |
| افزودن `scikit-learn==1.6.1` و `pytest==8.3.5` به requirements.txt و نصب | ModuleNotFoundError ×8 | — |
| اجرای مجدد unittest discover | — | **Ran 145 tests ... OK** (صفر failure/error) ✅ |
| اجرای pytest stage7 pipeline | — | **13 passed** ✅ |
| بازتولید library.md | ۶۳ بلوک قدیمی/خراب، fence دو-بک‌تیک، ۱۵ DIFF، ۱۲ فایل فاقدپوشش | **۷۸ بلوک verbatim مطابق HEAD، ۷۸/۷۸ تطبیق، صفر mismatch** ✅ |

**نکته مهم درباره خطای ظاهری جدید:** در شروع این نشست، ۸ ERROR دوباره ظاهر شد چون کلاژ Linux ریست شده و sklearn/pytest دوباره نصب نبودند (requirements.txt اصلاح‌شده track-but-uncommitted است و pip install خودکار انجام نمی‌شود). پس از `pip install -r` معادل، تست‌ها مجدداً OK شدند. ⇒ این یک نقص کد نیست؛ نقص **process** است: baseline باید environment.lock + دستور نصب صریح داشته باشد (در STEP B-2 roadmap لحاظ شده).

فایل‌های تغییریافته در این working tree (بدون commit): `agent/manager.py` (51±)، `library.md` (4178±)، `requirements.txt` (+2)، `tests/test_agent_manager.py` (52±). main نسبت به origin/main سه کامیت governance عقب است.

---

## بخش ۴ — نقشه‌راه تأییدشده (با amendments)

```text
Phase 0  Baseline Freeze (STEP B-1..B-5)          ← الان REJECTED؛ باید در clone تمیز redo شود
Phase 1  AT-P0-03 TradeID(SHA-256) → AT-P0-02 Spread(snapshot,fail-closed) → AT-P0-01 MtM(پیش از ریسک‌گیت)
Phase 2  AT-P1-01 DataGateway (contracts برابر قبل از hash) → AT-P1-02 Legacy isolation (guard→refs→import-test→archive)
Phase 3  AT-P1-03 Balance/Equity contract + ۴ تست → AT-P1-04 Recovery matrix (clock injectable)
Phase 4  AT-P2-01 Hygiene (چک‌های ۴گانه ls-files) → AT-P2-02 CI واقعی (required checks)
Gate     Kilo review → Qwen second opinion → Evidence validation → Human Confirmation
```

ترتیب P0 شما صحیح بود؛ amendmentها پذیرفته و در جدول بالا ادغام شدند (MtM قبل از gate، spread از snapshot، trade-id پایدار، baseline freeze، comparison fields قبل از SHA، ترتیب notebook، formula رسمی، recovery matrix، hygiene checks کامل، CI واقعی).

---

## بخش ۵ — موفقیت نهایی (Definition of Done)

Stage 7.1 تنها وقتی به Human Confirmation می‌رود که **همه** PASS شوند:
Execution Causality / Accounting Model / Regression Tests (با شمارش دقیق و log کامل) / Kilo Review / Qwen Review / Evidence Validated — و مدل همچنان edge اثبات‌شده داشته باشد (PnL منفی فعلی یعنی حتی پس از PASS فنی، تصمیم تحقیقاتی با Human Owner است؛ جعل یا مهندسی نتایج ممنوع).

```text
وضعیت نهایی سند:
Repository Audit: COMPLETE
Fixes Verified:   H3 tests + deps + library.md (145 OK / 13 passed)
Governance:       BLOCKED (منتظر تصمیم L3)
PaperBroker P0s:  باز — طبق Phase 1-3 roadmap
Baseline Freeze:  REJECTED — redo در clone تمیز
LIVE:             DENIED
```
