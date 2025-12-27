from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from nicegui import ui


@dataclass(frozen=True)
class ProjectRun:
    project_id: str
    title: str
    snapshot_ref: str
    run_id: str
    generated_at: str


class RunIndex:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir
        self.project_runs: List[ProjectRun] = []
        self._index_runs()

    def _index_runs(self) -> None:
        if not self.reports_dir.exists():
            return
        for run_dir in sorted(self.reports_dir.iterdir()):
            manifest = run_dir / "run_manifest.json"
            if not manifest.exists():
                continue
            data = json.loads(manifest.read_text(encoding="utf-8"))
            generated_at = data.get("generated_at", "")
            run_id = data.get("run_id", run_dir.name)
            for project in data.get("projects", []):
                self.project_runs.append(
                    ProjectRun(
                        project_id=project.get("id", ""),
                        title=project.get("title", ""),
                        snapshot_ref=project.get("snapshot_ref", ""),
                        run_id=run_id,
                        generated_at=generated_at,
                    )
                )

    def unique_projects(self) -> List[ProjectRun]:
        latest: Dict[str, ProjectRun] = {}
        for project in self.project_runs:
            key = f"{project.project_id}::{project.snapshot_ref}"
            existing = latest.get(key)
            if existing is None or project.generated_at > existing.generated_at:
                latest[key] = project
        return sorted(latest.values(), key=lambda item: (item.project_id, item.snapshot_ref))

    def read_report(self, run_id: str) -> Optional[Dict[str, Any]]:
        path = self.reports_dir / run_id / "report.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


class ViewerState:
    def __init__(self, index: RunIndex) -> None:
        self.index = index
        self.run_map = {self._label(run): run for run in index.unique_projects()}
        self.selected_a: Optional[ProjectRun] = None
        self.selected_b: Optional[ProjectRun] = None

    @staticmethod
    def _label(run: ProjectRun) -> str:
        return f"{run.title} ({run.snapshot_ref})"

    def labels(self) -> List[str]:
        return list(self.run_map.keys())

    def select_a(self, label: Optional[str]) -> None:
        self.selected_a = self.run_map.get(label) if label else None

    def select_b(self, label: Optional[str]) -> None:
        self.selected_b = self.run_map.get(label) if label else None


def build_report_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for project in report.get("projects", []):
        for module in project.get("modules", []):
            rows.append(
                {
                    "project": project.get("id"),
                    "snapshot": project.get("snapshot_ref"),
                    "module": module.get("module_id"),
                    "status": module.get("status"),
                    "score": module.get("score"),
                    "expectation": module.get("expected_rule_id"),
                }
            )
    return rows


def build_compare_rows(report_a: Dict[str, Any], report_b: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    index_b: Dict[str, Dict[str, Any]] = {}
    for project in report_b.get("projects", []):
        for module in project.get("modules", []):
            key = f"{project.get('id')}::{module.get('module_id')}"
            index_b[key] = module
    for project in report_a.get("projects", []):
        for module in project.get("modules", []):
            key = f"{project.get('id')}::{module.get('module_id')}"
            other = index_b.get(key)
            if not other:
                continue
            if module.get("status") == other.get("status") and module.get("score") == other.get("score"):
                continue
            rows.append(
                {
                    "project": project.get("id"),
                    "module": module.get("module_id"),
                    "status_a": module.get("status"),
                    "status_b": other.get("status"),
                    "score_a": module.get("score"),
                    "score_b": other.get("score"),
                }
            )
    return rows


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(prog="trace2-viewer")
    parser.add_argument("--reports", required=True, help="Reports directory")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    reports_dir = Path(args.reports).expanduser().resolve()
    index = RunIndex(reports_dir)
    state = ViewerState(index)

    ui.add_head_html(
        """
        <style>
        body { background: #f7f8fa; }
        .summary-card { background: white; border-radius: 12px; padding: 16px; box-shadow: 0 6px 16px rgba(0,0,0,0.08); }
        </style>
        """
    )

    with ui.row().classes("w-full items-center justify-between").style("padding: 16px 24px;"):
        ui.label("Trace2 Viewer").classes("text-2xl font-bold")
        ui.label("Compare snapshots by version/commit").classes("text-sm text-gray-500")

    with ui.row().classes("w-full gap-6").style("padding: 0 24px 24px 24px;"):
        with ui.column().classes("w-1/2"):
            ui.label("Snapshot A").classes("text-sm font-medium text-gray-600")
            select_a = ui.select(options=state.labels(), value=None).classes("w-full")
        with ui.column().classes("w-1/2"):
            ui.label("Snapshot B").classes("text-sm font-medium text-gray-600")
            select_b = ui.select(options=state.labels(), value=None).classes("w-full")

    with ui.row().classes("w-full gap-6").style("padding: 0 24px;"):
        report_card = ui.card().classes("summary-card w-full")
        compare_card = ui.card().classes("summary-card w-full")

    report_table = ui.table(
        columns=[
            {"name": "project", "label": "Project", "field": "project"},
            {"name": "snapshot", "label": "Snapshot", "field": "snapshot"},
            {"name": "module", "label": "Module", "field": "module"},
            {"name": "status", "label": "Status", "field": "status"},
            {"name": "score", "label": "Score", "field": "score"},
            {"name": "expectation", "label": "Expectation", "field": "expectation"},
        ],
        rows=[],
        row_key="module",
    ).classes("w-full")

    compare_table = ui.table(
        columns=[
            {"name": "project", "label": "Project", "field": "project"},
            {"name": "module", "label": "Module", "field": "module"},
            {"name": "status_a", "label": "Status A", "field": "status_a"},
            {"name": "status_b", "label": "Status B", "field": "status_b"},
            {"name": "score_a", "label": "Score A", "field": "score_a"},
            {"name": "score_b", "label": "Score B", "field": "score_b"},
        ],
        rows=[],
        row_key="module",
    ).classes("w-full")

    with report_card:
        ui.label("Report Overview").classes("text-lg font-semibold mb-2")
        ui.label("Select snapshot A to view its report.").classes("text-sm text-gray-500")
        report_card.add(report_table)

    with compare_card:
        ui.label("Comparison").classes("text-lg font-semibold mb-2")
        ui.label("Select both snapshots to compare drift.").classes("text-sm text-gray-500")
        compare_card.add(compare_table)

    def refresh() -> None:
        report_table.rows = []
        compare_table.rows = []
        if state.selected_a:
            report_a = index.read_report(state.selected_a.run_id)
            if report_a:
                report_table.rows = build_report_rows(report_a)
        if state.selected_a and state.selected_b:
            report_a = index.read_report(state.selected_a.run_id) or {}
            report_b = index.read_report(state.selected_b.run_id) or {}
            compare_table.rows = build_compare_rows(report_a, report_b)
        report_table.update()
        compare_table.update()

    select_a.on("update:model-value", lambda e: (state.select_a(e.value), refresh()))
    select_b.on("update:model-value", lambda e: (state.select_b(e.value), refresh()))

    ui.run(port=args.port)


if __name__ == "__main__":
    main()
