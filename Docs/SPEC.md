# ریکوارمنت‌های فاز ۲ مستقل Trace2 (نسخه ۱)

> این سند همان نسخه‌ی فعلی ریکوارمنت‌هاست که برای پیاده‌سازی Analyzer (CLI/CI) و Viewer (Web UI) استفاده می‌شود.

## 0) هدف
ساخت یک ابزار مستقل برای **Traceability-Drift** در سطح **ماژول** که بتواند برای هر **Project × Snapshot** مشخص کند:
- آیا ماژول به یکی از **Baseline**‌ها نزدیک است؟
- اگر اختلاف دارد، آیا این اختلاف با **Requirement**‌های فعال قابل توضیح است؟

> فرض مهم در نسخه ۱: **اثر سوئیچ‌های کامایلر و شرطی‌سازی‌های preprocessor (مثل #ifdef) در تحلیل لحاظ نمی‌شود**. تحلیل صرفاً بر اساس متن/توکن‌های موجود در snapshot است.

---

## 1) اصطلاحات
- **Project**: یک منبع کد (git repo یا مسیر فایل) + یک Snapshot
- **Snapshot**: tag/commit/branch یا یک فولدر ثابت
- **Module**: مجموعه‌ای از فایل‌ها (include/exclude با glob) + critical_files
- **Baseline**: snapshot مرجع برای مقایسه
- **Requirement**: یک قابلیت/تغییر مورد انتظار که روی پروژه فعال می‌شود
- **Expectation Rule**: قانون: اگر requirementهای خاص فعال بود، انتظار داریم Module به یک Target نزدیک باشد
- **Fingerprint**: امضای کد برای سنجش برابری/شباهت
- **Similarity score**: نزدیکی دو fingerprint

---

## 2) محدوده
### In Scope
- تعریف ماژول با YAML
- تعریف baselineها
- تعریف requirementها و ماتریس Project×Requirement
- تولید expectation از روی ruleها
- محاسبه similarity و تشخیص drift
- خروجی استاندارد JSON + CLI

### Out of Scope (در نسخه ۱)
- تحلیل build variants، سوئیچ‌های کامپایلر، شاخه‌های شرطی preprocessor
- تحلیل باینری/IR
- اتصال مستقیم به Jira/Spec (صرفاً با adapter در نسخه‌های بعد)

---

## 3) ورودی‌ها و قرارداد فایل‌ها (Config Contracts)

### FR-001: پشتیبانی از Config Folder
سیستم باید یک پوشهٔ config بگیرد و این فایل‌ها را بخواند:
- `projects.yml`
- `modules.yml`
- `baselines.yml`
- `requirements.yml`
- `matrix.yml`
- `expectations.yml`

**Acceptance Criteria**
- اگر فایل/فیلدی وجود نداشت یا نادرست بود، پیام خطای خوانا بدهد (کدام فایل، کدام فیلد).
- فیلد `version: 1` را بررسی کند.

### FR-002: تعریف Project و Snapshot
هر project باید یکی از این sourceها را پشتیبانی کند:
- `git`: repo + (tag/commit/branch)
- `fs`: path (فولدر)

**Acceptance Criteria**
- برای git: قادر به checkout snapshot در workspace/cache باشد.
- برای fs: snapshot همان وضعیت فعلی فولدر است.

### FR-003: تعریف Module با include/exclude
Moduleها با glob تعریف می‌شوند.

**Acceptance Criteria**
- لیست فایل‌های resolve‌شده برای هر module در حالت debug قابل مشاهده باشد.
- اگر module هیچ فایل پیدا نکرد: status = `MISSING` یا `EMPTY_MODULE` (یکی ثابت انتخاب شود؛ پیشنهاد: `MISSING`).

---

## 4) Fingerprint و Similarity

### FR-010: Normalization حداقلی
برای هر فایل قبل از fingerprint:
- حذف commentها
- نرمال‌سازی whitespace
- (اختیاری در MVP) نرمال‌سازی literalها

**Acceptance Criteria**
- تغییر صرفاً comment/space باعث ایجاد Drift شدید نشود.

### FR-011: Fingerprint فایل
برای هر فایل در module:
- `sha256_normalized`
- `simhash64`

**Acceptance Criteria**
- خروجی fingerprint فایل‌ها در `evidence.json` ذخیره شود.

### FR-012: Fingerprint ماژول
برای هر module یک fingerprint تجمیعی ساخته شود.

**Acceptance Criteria**
- ترتیب فایل‌ها نباید نتیجه را تغییر دهد (قبل از concat، فایل‌ها sort شوند).

### FR-013: Similarity Score
محاسبه شباهت بر اساس فاصله هَمینگ بین simhashها:
- `score = 1 - (hamming_distance/64)`
- اگر sha برابر بود: `score = 1.0`

**Acceptance Criteria**
- score در بازه [0..1] باشد.

---

## 5) Requirement و Expectation Engine

### FR-020: استخراج Requirementهای فعال پروژه
از `matrix.yml` requirementهای فعال هر project استخراج شود.

**Acceptance Criteria**
- در `report.json` لیست requirementهای فعال ثبت شود.

### FR-021: Rule Matching با Priority
Ruleها باید بر اساس `when` و priority انتخاب شوند.

**Acceptance Criteria**
- اگر چند rule match شد، rule با priority بالاتر اعمال شود.
- اگر برای یک module هیچ expectation تولید نشد → status = `UNMAPPED`.

### FR-022: Target Types
Target حداقل دو نوع داشته باشد:
- `type: baseline` (baseline_id)
- `type: signature` (امضای مستقیم)

**Acceptance Criteria**
- baseline_id نامعتبر → خطای واضح.
- signature مستقیم → بدون baseline قابل مقایسه باشد.

---

## 6) Drift Classification (تصمیم نهایی)

### FR-030: وضعیت‌های استاندارد
برای هر Project×Module یکی از statusهای زیر تولید شود:
- `OK_BASELINE`
- `OK_EXPECTED`
- `WARN`
- `DRIFT_UNEXPECTED`
- `UNMAPPED`
- `MISSING`

**Acceptance Criteria**
- status + score + expected_rule_id + target در report ثبت شود.
- thresholds از defaults یا override rule خوانده شود.

---

## 7) خروجی‌ها (Analyzer/CLI Outputs)

> نکته مهم: در این معماری، **Analyzer (CLI/CI)** مرحلهٔ سنگین را انجام می‌دهد (fingerprint + ارزیابی) و خروجی‌های JSON را به شکل یک **Run Folder** تولید می‌کند. **UI/Viewer** صرفاً این خروجی‌ها را می‌خواند و نمایش/مقایسه را انجام می‌دهد.

### FR-040: report.json (خلاصه)
خروجی استاندارد و پایدار.

### FR-041: evidence.json (شواهد)
شامل فایل‌های هر module و fingerprint فایل‌ها و module و critical_files.

### FR-042: actions.json (پیشنهاد اقدام)
خروجی اقدام‌ها باید به صورت JSON تولید شود. فرمت پایدار.

### FR-043: run_manifest.json (متادیتای Run)
هر Run Folder باید یک فایل `run_manifest.json` داشته باشد.

---

## 8) CLI و Exit Codes

### FR-050: دستور اصلی `trace2 analyze`
ورودی: مسیر config
خروجی: پوشه output
Exit codes: 2/1/0 طبق سند.

---

## 9.1) Caching Strategy (نسخه ۱)
FR-CACHE-001..007 و NFR-CACHE-001 طبق سند canvas.

---

## 12) UI (Viewer) و 13) Compare
UI فقط Viewer است و براساس `run_manifest.json`، پروژه/نسخه انتخاب می‌کند و compare انجام می‌دهد.
