from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote


INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Trace2 Viewer</title>
<style>
body { font-family: Arial, sans-serif; margin: 1.5rem; }
select, button { margin: 0.5rem 0.5rem 0.5rem 0; }
.table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
.table th, .table td { border: 1px solid #ddd; padding: 0.5rem; }
.table th { background: #f3f3f3; }
.badge { padding: 0.2rem 0.5rem; border-radius: 0.3rem; color: #fff; }
.OK_BASELINE, .OK_EXPECTED { background: #2e7d32; }
.WARN { background: #ed6c02; }
.DRIFT_UNEXPECTED { background: #c62828; }
.UNMAPPED { background: #546e7a; }
.MISSING { background: #6d4c41; }
</style>
</head>
<body>
<h1>Trace2 Viewer</h1>
<section>
  <h2>Run Selection</h2>
  <label>Run A</label>
  <select id="runA"></select>
  <label>Run B</label>
  <select id="runB"></select>
  <button id="compareBtn">Compare</button>
</section>
<section>
  <h2>Report</h2>
  <div id="report"></div>
</section>
<section>
  <h2>Compare Summary</h2>
  <div id="compare"></div>
</section>
<script>
async function fetchRuns() {
  const response = await fetch('/api/runs');
  return response.json();
}

function renderReport(report, container) {
  container.innerHTML = '';
  report.projects.forEach(project => {
    const header = document.createElement('h3');
    header.textContent = `${project.title} (${project.snapshot_ref})`;
    container.appendChild(header);
    const table = document.createElement('table');
    table.className = 'table';
    table.innerHTML = `
      <thead><tr><th>Module</th><th>Status</th><th>Score</th><th>Expectation</th></tr></thead>
      <tbody></tbody>`;
    const tbody = table.querySelector('tbody');
    project.modules.forEach(module => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${module.module_id}</td>
        <td><span class="badge ${module.status}">${module.status}</span></td>
        <td>${module.score ?? ''}</td>
        <td>${module.expected_rule_id ?? ''}</td>`;
      tbody.appendChild(row);
    });
    container.appendChild(table);
  });
}

function renderCompare(a, b, container) {
  container.innerHTML = '';
  if (!a || !b) {
    container.textContent = 'Select two runs to compare.';
    return;
  }
  const summary = document.createElement('div');
  const diffs = [];
  a.projects.forEach(projectA => {
    const projectB = b.projects.find(p => p.id === projectA.id);
    if (!projectB) return;
    projectA.modules.forEach(moduleA => {
      const moduleB = projectB.modules.find(m => m.module_id === moduleA.module_id);
      if (!moduleB) return;
      if (moduleA.status !== moduleB.status || moduleA.score !== moduleB.score) {
        diffs.push({ project: projectA.id, module: moduleA.module_id, a: moduleA, b: moduleB });
      }
    });
  });
  summary.textContent = `Differences found: ${diffs.length}`;
  container.appendChild(summary);
  if (diffs.length === 0) return;
  const table = document.createElement('table');
  table.className = 'table';
  table.innerHTML = `
    <thead><tr><th>Project</th><th>Module</th><th>Status A</th><th>Status B</th><th>Score A</th><th>Score B</th></tr></thead>
    <tbody></tbody>`;
  const tbody = table.querySelector('tbody');
  diffs.forEach(diff => {
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${diff.project}</td>
      <td>${diff.module}</td>
      <td>${diff.a.status}</td>
      <td>${diff.b.status}</td>
      <td>${diff.a.score ?? ''}</td>
      <td>${diff.b.score ?? ''}</td>`;
    tbody.appendChild(row);
  });
  container.appendChild(table);
}

async function init() {
  const runs = await fetchRuns();
  const runASelect = document.getElementById('runA');
  const runBSelect = document.getElementById('runB');
  runs.forEach(run => {
    const optionA = document.createElement('option');
    optionA.value = run.run_id;
    optionA.textContent = `${run.run_id} (${run.generated_at})`;
    runASelect.appendChild(optionA);
    const optionB = optionA.cloneNode(true);
    runBSelect.appendChild(optionB);
  });
  async function loadReport(runId, target) {
    if (!runId) return null;
    const response = await fetch(`/api/run/${runId}/report`);
    const report = await response.json();
    if (target) renderReport(report, target);
    return report;
  }
  const reportContainer = document.getElementById('report');
  const compareContainer = document.getElementById('compare');
  runASelect.addEventListener('change', async () => {
    const reportA = await loadReport(runASelect.value, reportContainer);
    const reportB = await loadReport(runBSelect.value);
    renderCompare(reportA, reportB, compareContainer);
  });
  runBSelect.addEventListener('change', async () => {
    const reportA = await loadReport(runASelect.value);
    const reportB = await loadReport(runBSelect.value);
    renderCompare(reportA, reportB, compareContainer);
  });
  document.getElementById('compareBtn').addEventListener('click', async () => {
    const reportA = await loadReport(runASelect.value, reportContainer);
    const reportB = await loadReport(runBSelect.value);
    renderCompare(reportA, reportB, compareContainer);
  });
  if (runs.length > 0) {
    runASelect.value = runs[0].run_id;
    const reportA = await loadReport(runASelect.value, reportContainer);
    renderCompare(reportA, null, compareContainer);
  }
}

init();
</script>
</body>
</html>
"""


class ViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        if path == "/":
            self._send_html(INDEX_HTML)
            return
        if path == "/api/runs":
            self._send_json(self.server.viewer.list_runs())
            return
        if path.startswith("/api/run/"):
            parts = path.split("/")
            if len(parts) >= 5:
                run_id = parts[3]
                item = parts[4]
                data = self.server.viewer.read_run_file(run_id, item)
                if data is None:
                    self.send_error(404, "Run not found")
                    return
                self._send_json(data)
                return
        self.send_error(404, "Not found")

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _send_html(self, content: str) -> None:
        data = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: object) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ViewerApp:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    def list_runs(self) -> list[dict[str, object]]:
        runs = []
        if not self.reports_dir.exists():
            return runs
        for run_dir in sorted(self.reports_dir.iterdir()):
            manifest = run_dir / "run_manifest.json"
            if manifest.exists():
                data = json.loads(manifest.read_text(encoding="utf-8"))
                runs.append(data)
        return runs

    def read_run_file(self, run_id: str, item: str) -> object | None:
        file_map = {
            "report": "report.json",
            "evidence": "evidence.json",
            "actions": "actions.json",
        }
        filename = file_map.get(item)
        if not filename:
            return None
        path = self.reports_dir / run_id / filename
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(prog="trace2-viewer")
    parser.add_argument("--reports", required=True, help="Reports directory")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    reports_dir = Path(args.reports).expanduser().resolve()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), ViewerHandler)
    server.viewer = ViewerApp(reports_dir)
    print(f"Trace2 Viewer running at http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
