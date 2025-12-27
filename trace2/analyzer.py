from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .cache import CacheStore
from .config import Baseline, ConfigBundle, Module, Project
from .fingerprint import ModuleFingerprint, FileFingerprint, similarity_score, sha256_hex, simhash64
from .git_utils import checkout_git_source
from .normalization import normalize_content


@dataclass
class ModuleAnalysis:
    module_id: str
    title: str
    status: str
    score: Optional[float]
    expected_rule_id: Optional[str]
    expected_level: Optional[str]
    target: Optional[Dict[str, str]]


@dataclass
class ProjectAnalysis:
    project_id: str
    title: str
    snapshot_ref: str
    requirements: List[str]
    modules: List[ModuleAnalysis]


class Analyzer:
    def __init__(self, config: ConfigBundle, cache_dir: Path) -> None:
        self.config = config
        self.cache = CacheStore(cache_dir)
        self._baseline_cache: Dict[str, Dict[str, ModuleFingerprint]] = {}

    def analyze(self, out_dir: Path) -> Dict[str, object]:
        out_dir.mkdir(parents=True, exist_ok=True)
        generated_at = datetime.now(timezone.utc).isoformat()
        report_projects: List[Dict[str, object]] = []
        evidence_projects: Dict[str, object] = {}

        for project in sorted(self.config.projects, key=lambda p: p.id):
            project_result, evidence = self._analyze_project(project)
            report_projects.append(project_result)
            evidence_projects[project.id] = evidence

        report = {
            "run_id": out_dir.name,
            "generated_at": generated_at,
            "projects": report_projects,
        }
        evidence = {
            "run_id": out_dir.name,
            "generated_at": generated_at,
            "projects": evidence_projects,
        }
        actions = self._build_actions(report_projects)
        manifest = {
            "run_id": out_dir.name,
            "generated_at": generated_at,
            "reports": {
                "report": "report.json",
                "evidence": "evidence.json",
                "actions": "actions.json",
                "cache_stats": "cache_stats.json",
            },
            "projects": [
                {
                    "id": project["id"],
                    "title": project["title"],
                    "snapshot_ref": project["snapshot_ref"],
                }
                for project in report_projects
            ],
        }

        (out_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        (out_dir / "evidence.json").write_text(
            json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        (out_dir / "actions.json").write_text(
            json.dumps(actions, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        (out_dir / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        (out_dir / "cache_stats.json").write_text(
            json.dumps(self.cache.stats.__dict__, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        return report

    def _analyze_project(self, project: Project) -> Tuple[Dict[str, object], Dict[str, object]]:
        project_path = self._resolve_project_path(project)
        active_requirements = self._active_requirements(project.id)
        rules = self._matching_rules(project.id, active_requirements)
        report_modules: List[Dict[str, object]] = []
        evidence_modules: Dict[str, object] = {}

        for module in sorted(self.config.modules, key=lambda m: m.id):
            module_files = self._resolve_module_files(project_path, module)
            module_fingerprint, files_evidence = self._fingerprint_module(
                project_path, module_files
            )
            module_evidence = {
                "module_id": module.id,
                "files": files_evidence,
                "module_fingerprint": module_fingerprint.__dict__ if module_fingerprint else None,
                "critical_files": module.critical_files,
                "missing_critical_files": [
                    path for path in module.critical_files if path not in module_files
                ],
            }
            evidence_modules[module.id] = module_evidence

            if not module_files:
                report_modules.append(
                    {
                        "module_id": module.id,
                        "title": module.title,
                        "status": "MISSING",
                        "score": None,
                        "expected_rule_id": None,
                        "expected_level": None,
                        "target": None,
                    }
                )
                continue

            expectation = self._select_expectation(rules, module.id)
            if expectation is None:
                report_modules.append(
                    {
                        "module_id": module.id,
                        "title": module.title,
                        "status": "UNMAPPED",
                        "score": None,
                        "expected_rule_id": None,
                        "expected_level": None,
                        "target": None,
                    }
                )
                continue

            target_fingerprint = self._resolve_target_fingerprint(expectation, module)
            if target_fingerprint is None or module_fingerprint is None:
                report_modules.append(
                    {
                        "module_id": module.id,
                        "title": module.title,
                        "status": "MISSING",
                        "score": None,
                        "expected_rule_id": expectation["rule_id"],
                        "expected_level": expectation["expected_level"],
                        "target": expectation["target"],
                    }
                )
                continue

            score = similarity_score(
                module_fingerprint.sha256_normalized,
                target_fingerprint.sha256_normalized,
                module_fingerprint.simhash64,
                target_fingerprint.simhash64,
            )
            thresholds = self._resolve_thresholds(expectation)
            status = self._classify_status(score, thresholds, expectation["target"]["type"])
            report_modules.append(
                {
                    "module_id": module.id,
                    "title": module.title,
                    "status": status,
                    "score": round(score, 4),
                    "expected_rule_id": expectation["rule_id"],
                    "expected_level": expectation["expected_level"],
                    "target": expectation["target"],
                }
            )

        snapshot_ref = ""
        if project.source.type == "git" and project.source.snapshot:
            snapshot_ref = project.source.snapshot.ref
        elif project.source.type == "fs":
            snapshot_ref = project.source.path or ""

        report = {
            "id": project.id,
            "title": project.title,
            "snapshot_ref": snapshot_ref,
            "requirements": sorted(active_requirements),
            "modules": report_modules,
        }
        evidence = {
            "id": project.id,
            "title": project.title,
            "snapshot_ref": snapshot_ref,
            "modules": evidence_modules,
        }
        return report, evidence

    def _resolve_project_path(self, project: Project) -> Path:
        if project.source.type == "git":
            if not project.source.snapshot:
                raise ValueError("git project missing snapshot")
            return checkout_git_source(
                project.source.repo or "",
                project.source.snapshot.ref,
                self.cache.root,
            )
        return Path(project.source.path or "").expanduser().resolve()

    def _resolve_module_files(self, project_path: Path, module: Module) -> List[str]:
        matched: set[str] = set()
        for pattern in module.include:
            for path in project_path.glob(pattern):
                if path.is_file():
                    matched.add(path.relative_to(project_path).as_posix())
        for pattern in module.exclude:
            for path in project_path.glob(pattern):
                if path.is_file():
                    matched.discard(path.relative_to(project_path).as_posix())
        return sorted(matched)

    def _fingerprint_module(
        self, project_path: Path, module_files: List[str]
    ) -> Tuple[Optional[ModuleFingerprint], List[Dict[str, str]]]:
        if not module_files:
            return None, []
        file_evidence: List[Dict[str, str]] = []
        module_hasher = hashlib.sha256()
        tokens: List[str] = []
        for file_path in module_files:
            file_fp = self._fingerprint_file(project_path, file_path)
            if file_fp is None:
                continue
            file_evidence.append({
                "path": file_path,
                "sha256_normalized": file_fp.sha256_normalized,
                "simhash64": file_fp.simhash64,
            })
            module_hasher.update(file_fp.sha256_normalized.encode("utf-8"))
            tokens.append(file_fp.simhash64)
        module_sha = module_hasher.hexdigest()
        cached_module = self.cache.get_module(module_sha)
        if cached_module:
            module_fp = ModuleFingerprint(
                sha256_normalized=cached_module["sha256_normalized"],
                simhash64=cached_module["simhash64"],
            )
            return module_fp, file_evidence
        module_simhash = simhash64(tokens)
        module_fp = ModuleFingerprint(sha256_normalized=module_sha, simhash64=module_simhash)
        self.cache.set_module(
            module_sha,
            {"sha256_normalized": module_sha, "simhash64": module_simhash},
        )
        return module_fp, file_evidence

    def _fingerprint_file(self, project_path: Path, relative_path: str) -> Optional[FileFingerprint]:
        path = project_path / relative_path
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="ignore")
        raw_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        cached = self.cache.get_file(raw_hash)
        if cached:
            return FileFingerprint(
                sha256_normalized=cached["sha256_normalized"],
                simhash64=cached["simhash64"],
            )
        normalized = normalize_content(text)
        sha = sha256_hex(normalized)
        simhash_value = simhash64(normalized.split())
        fp = FileFingerprint(sha256_normalized=sha, simhash64=simhash_value)
        self.cache.set_file(raw_hash, {"sha256_normalized": sha, "simhash64": simhash_value})
        return fp

    def _active_requirements(self, project_id: str) -> List[str]:
        entry = next((item for item in self.config.matrix if item.id == project_id), None)
        if entry is None:
            return []
        requirements: List[str] = []
        for req in entry.requires:
            if req.get("must_have"):
                requirements.append(str(req.get("id")))
        return requirements

    def _matching_rules(self, project_id: str, requirements: List[str]) -> List[Dict[str, object]]:
        matched: List[Dict[str, object]] = []
        for rule in self.config.expectations.rules:
            when = rule.when
            projects = when.get("projects")
            requires_all = when.get("requires_all")
            if projects:
                if "*" not in projects and project_id not in projects:
                    continue
            if requires_all:
                if not all(req in requirements for req in requires_all):
                    continue
            matched.append(
                {
                    "rule_id": rule.id,
                    "priority": rule.priority,
                    "expect": rule.expect,
                }
            )
        return sorted(matched, key=lambda r: r["priority"], reverse=True)

    def _select_expectation(self, rules: List[Dict[str, object]], module_id: str) -> Optional[Dict[str, object]]:
        for rule in rules:
            for exp in rule["expect"]:
                if exp.module == module_id:
                    return {
                        "rule_id": rule["rule_id"],
                        "expected_level": exp.expected_level,
                        "target": {
                            "type": exp.target.type,
                            "baseline_id": exp.target.baseline_id,
                            "signature": exp.target.signature,
                            "sha256": exp.target.sha256,
                        },
                    }
        return None

    def _resolve_target_fingerprint(
        self, expectation: Dict[str, object], module: Module
    ) -> Optional[ModuleFingerprint]:
        target = expectation["target"]
        target_type = target["type"]
        if target_type == "baseline":
            baseline_id = target.get("baseline_id")
            if not baseline_id:
                return None
            return self._baseline_module_fingerprint(baseline_id, module)
        if target_type == "signature":
            signature = target.get("signature")
            sha256 = target.get("sha256")
            if signature is None or sha256 is None:
                return None
            return ModuleFingerprint(sha256_normalized=sha256, simhash64=signature)
        return None

    def _baseline_module_fingerprint(self, baseline_id: str, module: Module) -> Optional[ModuleFingerprint]:
        if baseline_id not in self._baseline_cache:
            baseline = next((b for b in self.config.baselines if b.id == baseline_id), None)
            if baseline is None:
                raise ValueError(f"Unknown baseline id: {baseline_id}")
            baseline_path = self._resolve_baseline_path(baseline)
            module_fps: Dict[str, ModuleFingerprint] = {}
            for mod in self.config.modules:
                module_files = self._resolve_module_files(baseline_path, mod)
                module_fp, _ = self._fingerprint_module(baseline_path, module_files)
                if module_fp:
                    module_fps[mod.id] = module_fp
            self._baseline_cache[baseline_id] = module_fps
        return self._baseline_cache[baseline_id].get(module.id)

    def _resolve_baseline_path(self, baseline: Baseline) -> Path:
        if baseline.source.type == "git":
            if not baseline.source.snapshot:
                raise ValueError("baseline git source missing snapshot")
            return checkout_git_source(
                baseline.source.repo or "",
                baseline.source.snapshot.ref,
                self.cache.root,
            )
        return Path(baseline.source.path or "").expanduser().resolve()

    def _resolve_thresholds(self, expectation: Dict[str, object]) -> Dict[str, float]:
        defaults = self.config.expectations.defaults
        thresholds = defaults.get("thresholds", {})
        expected_level = expectation["expected_level"]
        return thresholds.get(expected_level, {"ok": 1.0, "warn": 0.0})

    def _classify_status(
        self, score: float, thresholds: Dict[str, float], target_type: str
    ) -> str:
        ok_threshold = float(thresholds.get("ok", 1.0))
        warn_threshold = float(thresholds.get("warn", 0.0))
        if score >= ok_threshold:
            return "OK_BASELINE" if target_type == "baseline" else "OK_EXPECTED"
        if score >= warn_threshold:
            return "WARN"
        return "DRIFT_UNEXPECTED"

    def _build_actions(self, report_projects: List[Dict[str, object]]) -> Dict[str, object]:
        actions: List[Dict[str, object]] = []
        for project in report_projects:
            for module in project["modules"]:
                if module["status"] in {"WARN", "DRIFT_UNEXPECTED"}:
                    actions.append(
                        {
                            "project_id": project["id"],
                            "module_id": module["module_id"],
                            "status": module["status"],
                            "message": "Review drift and update expectation or baseline.",
                        }
                    )
        return {"actions": actions}
