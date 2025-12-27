# Trace2 – بسته ورودی پیشنهادی برای Codex

این پوشه شامل هر چیزی است که برای شروع توسعه با Codex پیشنهاد می‌شود:

## محتویات
- `SPEC.md` ریکوارمنت‌های نسخه ۱ (Analyzer CLI + Viewer Web UI)
- `demo/config/` کانفیگ آماده برای تست با zlib
- `TEST_SCENARIOS.md` سناریوهای تست E2E و معیارهای قابل چک
- `AGENTS.md` راهنمای اجرا برای Codex (تقسیم کار و قواعد)
- `scripts/` اسکریپت‌های کمکی (اختیاری)

## Repo تست پیشنهادی
- Repo: https://github.com/madler/zlib.git
- Snapshots (Tags): `v1.2.12`, `v1.2.13`, `v1.3.1`
  - (اختیاری) `v1.3.1.2` اگر خواستی یک نقطه جدیدتر هم داشته باشی.

نکته: UI آفلاین است، اما برای گرفتن ریپو/تگ‌ها یک بار نیاز به clone دارید. در محیط‌های air-gapped می‌توانید repo را mirror کنید و در `projects.yml` آدرس داخلی بدهید.

## هدف دمو
- تولید چند Run Folder در `reports/`
- Viewer بتواند از روی `run_manifest.json` پروژه/نسخه را انتخاب و نمایش/compare کند
