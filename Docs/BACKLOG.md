# BACKLOG.md (ریز کارهای پیشنهادی برای Codex)

## Analyzer/CLI
- [ ] parse config YAML + validation
- [ ] git fetch/checkout (cache worktree)
- [ ] file discovery per module
- [ ] normalization v1
- [ ] sha256_normalized
- [ ] simhash64 (token-based ساده)
- [ ] content-based cache key (git blob یا content-hash)
- [ ] module aggregation + module cache
- [ ] expectations rule matching (priority)
- [ ] scoring + classification
- [ ] outputs: report.json/evidence.json/actions.json/run_manifest.json/cache_stats.json
- [ ] exit codes + logs
- [ ] tests: unit + e2e zlib

## Viewer
- [ ] index runs from reports/ via run_manifest.json
- [ ] report table + filters
- [ ] module details (evidence)
- [ ] actions viewer
- [ ] compare: select project/snapshot for side A/B + diff summary/table
- [ ] export CSV/JSON
