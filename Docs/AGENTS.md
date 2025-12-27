# AGENTS.md (برای Codex)

## هدف
پیاده‌سازی Trace2 نسخه ۱ مطابق SPEC.md با دو جزء:
1) Analyzer/CLI: `trace2 analyze --config <dir> --out <run_folder> --cache-dir <dir>`
2) Viewer/Web: فقط خواندن Run Folderها و نمایش + Compare (بدون اجرای تحلیل)

## پیشنهاد زبان/پشته
- Python 3.11+
- pydantic برای validation schema (اختیاری)
- typer یا argparse برای CLI
- nicegui یا streamlit برای Viewer (فقط reader)

## تقسیم کار پیشنهادی (به ترتیب)
1) مدل‌های داده (Config + Outputs) + validation
2) Resolver فایل‌های module (glob include/exclude)
3) Normalization ساده (حذف comment + whitespace normalize)
4) Fingerprint فایل (sha256_normalized + simhash64)
5) Cache فایل: content-based key (برای git: blob-id یا محتوای نرمال‌شده)
6) Aggregation ماژول (deterministic) + cache ماژول
7) Expectation engine (priority rules)
8) Drift classification + report/evidence/actions
9) run_manifest + cache_stats
10) تست‌های E2E روی demo zlib
11) Viewer: لیست runs از reports/ و نمایش report + details + compare

## اصول
- خروجی‌ها فقط JSON (بدون Markdown)
- Deterministic: sort و stable serialization
- لاگ واضح
