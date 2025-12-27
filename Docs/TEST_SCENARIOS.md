# TEST_SCENARIOS.md

## پیش‌نیاز
- demo config در `demo/config/`
- دسترسی به repo zlib و tagهای مشخص
- اجرای CLI: `trace2 analyze --config demo/config --out reports/<something> --cache-dir .cache/trace2`

## سناریو 1: Smoke
- اجرا بدون خطا
- تولید فایل‌ها در run folder:
  - run_manifest.json
  - report.json
  - evidence.json
  - actions.json (یا قابل تولید توسط viewer از report/evidence)
  - cache_stats.json

## سناریو 2: تنوع وضعیت‌ها
- در report.json حداقل 2 status مختلف وجود داشته باشد (مثلاً OK_* و WARN/DRIFT_UNEXPECTED)

## سناریو 3: Cache gain
- اجرای دوم روی همان Project×Snapshot:
  - file_cache_hits > 0 در cache_stats.json

## سناریو 4: Determinism
- اجرای پشت سر هم (با ورودی ثابت) باید report.json یکسان بدهد.

## سناریو 5: Compare (بدون تحلیل مجدد)
- دو run folder برای دو snapshot مختلف داشته باش
- viewer بتواند Side A (project_id + snapshot_ref) و Side B را انتخاب کند
- خلاصه اختلاف‌ها و جدول delta تولید شود
