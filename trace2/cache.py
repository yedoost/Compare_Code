from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class CacheStats:
    file_cache_hits: int = 0
    file_cache_misses: int = 0
    module_cache_hits: int = 0
    module_cache_misses: int = 0


class CacheStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.file_cache_dir = root / "file_cache"
        self.module_cache_dir = root / "module_cache"
        self.file_cache_dir.mkdir(parents=True, exist_ok=True)
        self.module_cache_dir.mkdir(parents=True, exist_ok=True)
        self.stats = CacheStats()

    def get_file(self, key: str) -> Optional[Dict[str, Any]]:
        path = self.file_cache_dir / f"{key}.json"
        if path.exists():
            self.stats.file_cache_hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        self.stats.file_cache_misses += 1
        return None

    def set_file(self, key: str, data: Dict[str, Any]) -> None:
        path = self.file_cache_dir / f"{key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    def get_module(self, key: str) -> Optional[Dict[str, Any]]:
        path = self.module_cache_dir / f"{key}.json"
        if path.exists():
            self.stats.module_cache_hits += 1
            return json.loads(path.read_text(encoding="utf-8"))
        self.stats.module_cache_misses += 1
        return None

    def set_module(self, key: str, data: Dict[str, Any]) -> None:
        path = self.module_cache_dir / f"{key}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
