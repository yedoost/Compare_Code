from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class SnapshotRef:
    type: str
    ref: str


@dataclass(frozen=True)
class Source:
    type: str
    repo: Optional[str] = None
    snapshot: Optional[SnapshotRef] = None
    path: Optional[str] = None


@dataclass(frozen=True)
class Project:
    id: str
    title: str
    source: Source


@dataclass(frozen=True)
class Module:
    id: str
    title: str
    language: str
    include: List[str]
    exclude: List[str]
    critical_files: List[str]


@dataclass(frozen=True)
class Baseline:
    id: str
    title: str
    source: Source


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    description: str
    impacts: Dict[str, Any]


@dataclass(frozen=True)
class MatrixEntry:
    id: str
    requires: List[Dict[str, Any]]


@dataclass(frozen=True)
class ExpectationTarget:
    type: str
    baseline_id: Optional[str] = None
    signature: Optional[str] = None
    sha256: Optional[str] = None


@dataclass(frozen=True)
class Expectation:
    module: str
    expected_level: str
    target: ExpectationTarget


@dataclass(frozen=True)
class ExpectationRule:
    id: str
    priority: int
    when: Dict[str, Any]
    expect: List[Expectation]


@dataclass(frozen=True)
class ExpectationsConfig:
    defaults: Dict[str, Any]
    rules: List[ExpectationRule]


@dataclass(frozen=True)
class ConfigBundle:
    projects: List[Project]
    modules: List[Module]
    baselines: List[Baseline]
    requirements: List[Requirement]
    matrix: List[MatrixEntry]
    expectations: ExpectationsConfig


EXPECTED_FILES = {
    "projects": "projects.yml",
    "modules": "modules.yml",
    "baselines": "baselines.yml",
    "requirements": "requirements.yml",
    "matrix": "matrix.yml",
    "expectations": "expectations.yml",
}


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing config file: {path.name}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError(f"Invalid YAML structure in {path.name}")
    version = data.get("version")
    if version != 1:
        raise ConfigError(f"{path.name}: unsupported version {version}")
    return data


def _parse_snapshot(snapshot: Dict[str, Any]) -> SnapshotRef:
    if not isinstance(snapshot, dict):
        raise ConfigError("snapshot must be a mapping")
    return SnapshotRef(type=str(snapshot.get("type")), ref=str(snapshot.get("ref")))


def _parse_source(source: Dict[str, Any]) -> Source:
    if not isinstance(source, dict):
        raise ConfigError("source must be a mapping")
    source_type = source.get("type")
    if source_type == "git":
        snapshot = _parse_snapshot(source.get("snapshot", {}))
        repo = source.get("repo")
        if not repo:
            raise ConfigError("git source requires repo")
        return Source(type="git", repo=str(repo), snapshot=snapshot)
    if source_type == "fs":
        path = source.get("path")
        if not path:
            raise ConfigError("fs source requires path")
        return Source(type="fs", path=str(path))
    raise ConfigError(f"Unknown source type: {source_type}")


def _parse_projects(data: Dict[str, Any]) -> List[Project]:
    items = data.get("projects")
    if not isinstance(items, list):
        raise ConfigError("projects.yml: projects must be a list")
    projects: List[Project] = []
    for item in items:
        if not isinstance(item, dict):
            raise ConfigError("projects.yml: project must be a mapping")
        projects.append(
            Project(
                id=str(item.get("id")),
                title=str(item.get("title")),
                source=_parse_source(item.get("source", {})),
            )
        )
    return projects


def _parse_modules(data: Dict[str, Any]) -> List[Module]:
    items = data.get("modules")
    if not isinstance(items, list):
        raise ConfigError("modules.yml: modules must be a list")
    modules: List[Module] = []
    for item in items:
        if not isinstance(item, dict):
            raise ConfigError("modules.yml: module must be a mapping")
        modules.append(
            Module(
                id=str(item.get("id")),
                title=str(item.get("title")),
                language=str(item.get("language")),
                include=list(item.get("include", [])),
                exclude=list(item.get("exclude", [])),
                critical_files=list(item.get("critical_files", [])),
            )
        )
    return modules


def _parse_baselines(data: Dict[str, Any]) -> List[Baseline]:
    items = data.get("baselines")
    if not isinstance(items, list):
        raise ConfigError("baselines.yml: baselines must be a list")
    baselines: List[Baseline] = []
    for item in items:
        if not isinstance(item, dict):
            raise ConfigError("baselines.yml: baseline must be a mapping")
        baselines.append(
            Baseline(
                id=str(item.get("id")),
                title=str(item.get("title")),
                source=_parse_source(item.get("source", {})),
            )
        )
    return baselines


def _parse_requirements(data: Dict[str, Any]) -> List[Requirement]:
    items = data.get("requirements")
    if not isinstance(items, list):
        raise ConfigError("requirements.yml: requirements must be a list")
    requirements: List[Requirement] = []
    for item in items:
        if not isinstance(item, dict):
            raise ConfigError("requirements.yml: requirement must be a mapping")
        requirements.append(
            Requirement(
                id=str(item.get("id")),
                title=str(item.get("title")),
                description=str(item.get("description", "")),
                impacts=item.get("impacts", {}),
            )
        )
    return requirements


def _parse_matrix(data: Dict[str, Any]) -> List[MatrixEntry]:
    items = data.get("projects")
    if not isinstance(items, list):
        raise ConfigError("matrix.yml: projects must be a list")
    matrix: List[MatrixEntry] = []
    for item in items:
        if not isinstance(item, dict):
            raise ConfigError("matrix.yml: project entry must be a mapping")
        matrix.append(
            MatrixEntry(
                id=str(item.get("id")),
                requires=list(item.get("requires", [])),
            )
        )
    return matrix


def _parse_expectations(data: Dict[str, Any]) -> ExpectationsConfig:
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        raise ConfigError("expectations.yml: defaults must be a mapping")
    rules_raw = data.get("rules")
    if not isinstance(rules_raw, list):
        raise ConfigError("expectations.yml: rules must be a list")
    rules: List[ExpectationRule] = []
    for item in rules_raw:
        if not isinstance(item, dict):
            raise ConfigError("expectations.yml: rule must be a mapping")
        expect_entries: List[Expectation] = []
        for exp in item.get("expect", []):
            target = exp.get("target", {})
            if not isinstance(target, dict):
                raise ConfigError("expectations.yml: target must be a mapping")
            expect_entries.append(
                Expectation(
                    module=str(exp.get("module")),
                    expected_level=str(exp.get("expected_level")),
                    target=ExpectationTarget(
                        type=str(target.get("type")),
                        baseline_id=target.get("baseline_id"),
                        signature=target.get("signature"),
                        sha256=target.get("sha256"),
                    ),
                )
            )
        rules.append(
            ExpectationRule(
                id=str(item.get("id")),
                priority=int(item.get("priority", 0)),
                when=item.get("when", {}),
                expect=expect_entries,
            )
        )
    return ExpectationsConfig(defaults=defaults, rules=rules)


def load_config_bundle(config_dir: Path) -> ConfigBundle:
    if not config_dir.exists():
        raise ConfigError(f"Config directory not found: {config_dir}")
    data_projects = _read_yaml(config_dir / EXPECTED_FILES["projects"])
    data_modules = _read_yaml(config_dir / EXPECTED_FILES["modules"])
    data_baselines = _read_yaml(config_dir / EXPECTED_FILES["baselines"])
    data_requirements = _read_yaml(config_dir / EXPECTED_FILES["requirements"])
    data_matrix = _read_yaml(config_dir / EXPECTED_FILES["matrix"])
    data_expectations = _read_yaml(config_dir / EXPECTED_FILES["expectations"])

    return ConfigBundle(
        projects=_parse_projects(data_projects),
        modules=_parse_modules(data_modules),
        baselines=_parse_baselines(data_baselines),
        requirements=_parse_requirements(data_requirements),
        matrix=_parse_matrix(data_matrix),
        expectations=_parse_expectations(data_expectations),
    )
