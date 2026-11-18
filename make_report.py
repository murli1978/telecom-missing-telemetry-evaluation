"""Build a self-contained HTML report from a saved evaluation run."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNS_ROOT = (HERE / "runs").resolve()
RESPONSE_FILES = {
    "actor": ("Actor", "actor-response.md"),
    "monitor_1": ("Monitor 1", "monitor-1-response.md"),
    "monitor_2": ("Monitor 2", "monitor-2-response.md"),
}


def scoring_html(run_dir: Path) -> str:
    score_path = run_dir / "actor-score.json"
    if not score_path.exists():
        return """<section class="card" id="scoring"><h2>Actor rubric score</h2>
<p class="model">Not scored. Add an actor-score.json file and regenerate the report to display a rubric review.</p></section>"""
    scoring = json.loads(score_path.read_text(encoding="utf-8"))
    criteria = scoring.get("criteria", [])
    max_score = sum(int(item.get("max_score", 2)) for item in criteria)
    total = sum(int(item.get("score", 0)) for item in criteria)
    rows = "".join(
        "<tr><th scope=\"row\">{}</th><td>{}/{}</td><td>{}</td></tr>".format(
            html.escape(str(item.get("name", "Criterion"))),
            html.escape(str(item.get("score", "—"))),
            html.escape(str(item.get("max_score", 2))),
            html.escape(str(item.get("rationale", ""))),
        )
        for item in criteria
    )
    flags = scoring.get("flags", [])
    flag_html = "".join(f"<li>{html.escape(str(flag))}</li>" for flag in flags) or "<li>No separate flags recorded.</li>"
    label = html.escape(str(scoring.get("label", "Provisional reviewer assessment")))
    caveat = html.escape(str(scoring.get("caveat", "")))
    return f"""<section class="card" id="scoring">
<h2>Actor rubric score: {total}/{max_score}</h2>
<p class="model">{label} · Each criterion is scored 0–2. The rubric follows the actor prompt.</p>
<div class="table-wrap"><table><thead><tr><th>Criterion</th><th>Score</th><th>Evidence-based rationale</th></tr></thead><tbody>{rows}</tbody></table></div>
<h3>Flags and interpretation</h3><ul>{flag_html}</ul>
<p class="caveat">{caveat}</p>
</section>"""


def latest_run() -> Path:
    candidates = [path for path in RUNS_ROOT.iterdir() if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No run folders found under {RUNS_ROOT}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def safe_text(path: Path) -> str:
    if not path.exists():
        return "No saved response found."
    raw = path.read_text(encoding="utf-8").strip()
    # Some integrations save text blocks wrapped with provider metadata.
    # Render only their text in the HTML while preserving the raw file as-is.
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        text_blocks = [item["text"] for item in payload if item.get("type") == "text" and isinstance(item.get("text"), str)]
        if text_blocks:
            return "\n\n".join(text_blocks).strip()
    return raw


def model_info(metadata: dict, key: str) -> str:
    role = metadata.get(key, {})
    if not isinstance(role, dict):
        return "Model details unavailable"
    provider = role.get("mode", "unknown mode")
    model = role.get("returned_model_label") or role.get("label", "unknown model")
    return f"{provider} · {model}"


def token_info(metadata: dict, key: str) -> str:
    role = metadata.get(key, {})
    usage = role.get("usage", {}) if isinstance(role, dict) else {}
    if not isinstance(usage, dict) or not usage:
        return "Token usage not reported"
    total = usage.get("total_tokens")
    incoming = usage.get("input_tokens")
    outgoing = usage.get("output_tokens")
    if total is None:
        return "Token usage reported"
    return f"{total:,} tokens total · {incoming or 0:,} in · {outgoing or 0:,} out"


def build_report(run_dir: Path, output: Path) -> Path:
    run_dir = run_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run folder not found: {run_dir}")

    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    run_id = str(metadata.get("run_id") or run_dir.name)
    condition = str(metadata.get("condition") or "Not recorded")
    created_at = str(metadata.get("created_at_utc") or "Not recorded")
    complete = bool(metadata.get("complete"))

    cards = []
    for key, (title, filename) in RESPONSE_FILES.items():
        response = safe_text(run_dir / filename)
        cards.append(
            f"""<section class="card" id="{key}">
  <div class="card-head"><div><h2>{html.escape(title)}</h2>
  <p class="model">{html.escape(model_info(metadata, key))}</p></div>
  <span class="usage">{html.escape(token_info(metadata, key))}</span></div>
  <pre>{html.escape(response)}</pre>
</section>"""
        )

    status_class = "complete" if complete else "incomplete"
    status = "Complete" if complete else "Incomplete or status unavailable"
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Model actor and monitor responses from a synthetic telecom missing-telemetry evaluation.">
<title>Evaluation report · {html.escape(run_id)}</title>
<style>
:root {{ color-scheme: light; --ink:#182230; --muted:#596579; --line:#dce3eb; --panel:#fff; --bg:#f3f6fa; --accent:#2457a7; }}
* {{ box-sizing:border-box; }} body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1050px; margin:0 auto; padding:36px 22px 60px; }}
header {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:26px; margin-bottom:20px; }}
h1 {{ margin:0 0 8px; font-size:clamp(1.6rem,4vw,2.2rem); }} .subtitle {{ color:var(--muted); margin:0 0 18px; }}
.facts {{ display:flex; flex-wrap:wrap; gap:9px; }} .fact {{ background:#edf2f8; border-radius:999px; padding:5px 11px; font-size:.88rem; }}
.status {{ font-weight:700; }} .status.complete {{ color:#14734a; }} .status.incomplete {{ color:#9b5b00; }}
nav {{ display:flex; flex-wrap:wrap; gap:10px; margin:18px 0; }} nav a {{ color:var(--accent); text-decoration:none; background:#e7eef9; border-radius:8px; padding:8px 12px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:22px; margin:16px 0; scroll-margin-top:14px; }}
.card-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; }} h2 {{ margin:0; font-size:1.3rem; }} .model,.usage {{ color:var(--muted); margin:3px 0 12px; font-size:.9rem; }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; margin:10px 0 0; }} footer {{ color:var(--muted); font-size:.88rem; padding:12px 4px; }}
.table-wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; margin-top:12px; }} th,td {{ border-bottom:1px solid var(--line); padding:10px; text-align:left; vertical-align:top; }} th {{ background:#f7f9fc; }} .caveat {{ color:var(--muted); font-size:.9rem; }}
@media print {{ body {{ background:white; }} main {{ max-width:none; padding:0; }} header,.card {{ break-inside:avoid; border-color:#bbb; }} nav {{ display:none; }} }}
</style>
</head>
<body><main>
<header>
  <h1>Missing telemetry evaluation</h1>
  <p class="subtitle">Synthetic telecom billing case · actor response reviewed independently by two monitors</p>
  <div class="facts">
    <span class="fact">Run: {html.escape(run_id)}</span>
    <span class="fact">Condition: {html.escape(condition)}</span>
    <span class="fact">Created (UTC): {html.escape(created_at)}</span>
    <span class="fact status {status_class}">{html.escape(status)}</span>
  </div>
</header>
<nav aria-label="Report sections"><a href="#scoring">Actor score</a><a href="#actor">Actor response</a><a href="#monitor_1">Monitor 1</a><a href="#monitor_2">Monitor 2</a></nav>
{scoring_html(run_dir)}
{''.join(cards)}
<footer>Generated from saved run artifacts. Responses are shown verbatim. Any rubric score is a provisional reviewer assessment, not a model-generated ground truth. Review before sharing.</footer>
</main></body></html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a shareable, self-contained HTML report for a saved run.")
    parser.add_argument("run_dir", nargs="?", help="Run folder; defaults to the most recently modified folder in runs/")
    parser.add_argument("--output", help="Output HTML path; defaults to report.html inside the run folder")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve() if args.run_dir else latest_run()
    output = Path(args.output).resolve() if args.output else run_dir / "report.html"
    report = build_report(run_dir, output)
    print(f"HTML report created: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
