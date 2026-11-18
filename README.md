# Missing Telemetry: Actor and Monitor Pilot

A small, reproducible prototype for studying whether language-model monitors catch unsupported inferences and unsafe troubleshooting advice in a synthetic telecom billing incident. LangGraph runs one actor and passes its complete response to two monitors. LangChain integrations call Groq and Google Gemini.

## What this repository demonstrates

- A controlled synthetic case about an enterprise customer's missing invoice.
- An actor prompt that requests evidence-based diagnosis and read-only first checks.
- Two independently prompted monitors that review the same actor response.
- Saved prompts, responses, model labels, and token usage for each completed run.
- A standalone HTML report and a reviewer-entered rubric score.

The checked-in result is one A2 example run, not the complete earlier manual pilot. See [the experiment summary](docs/experiment-summary.md) for what this run does and does not establish. The hidden answer key is intentionally not included.

## Models in the included example

1. Actor: Groq `openai/gpt-oss-20b`
2. Monitor 1: Google Gemini `gemini-3.5-flash-lite`
3. Monitor 2: Groq `openai/gpt-oss-120b`

These match the included example metadata. They are also the script defaults. Model availability, API quotas, and free-tier terms can change; check each provider's current settings before running. Groq serves both the actor and Monitor 2, so the monitors are not fully provider-independent.

## Setup on Windows

Use Python 3.11 or newer. From this folder, create a virtual environment and install the pinned dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .venv\.env
```

Open `.venv\.env` locally and fill in `GROQ_API_KEY` and `GOOGLE_API_KEY`. Keep that file private; `.env` files and `.venv/` are ignored by Git. Never paste key values into an issue, chat, report, or commit. If a key is missing, the script prompts for it without echoing the value.

Run the experiment:

```powershell
python run_eval.py
```

The run makes live API calls and is subject to provider quotas and terms. It saves prompts, outputs, and metadata in a timestamped folder under `runs/`. Those raw run folders are ignored by default.

## Create or view a report

The repository includes a curated report for the checked-in example run at `results/example-run/report.html`. To regenerate it from the included response files:

```powershell
python make_report.py results/example-run
```

For a newly generated run, pass its folder instead:

```powershell
python make_report.py runs\<run-id>
```

The HTML is self-contained. It displays model names, token usage when provided, actor and monitor responses, and the score from `actor-score.json` if present. It does not include API keys or prompts. The raw prompt and response files remain available alongside the example report for audit.

## Scoring and interpretation

The example's 11/12 actor score is a **provisional reviewer assessment**, not an automated model score or validated ground truth. It applies six criteria from the actor prompt, each scored 0–2, and records the rationale and safety flags in `results/example-run/actor-score.json`. The two monitors disagreed: one judged the response sound and the other mixed. The summary explains the issue that needs human adjudication.

Use the same rubric across runs, keep actor and monitor scores separate, and have a human review any score before using it as an application claim. This prototype does not calculate a score automatically.

## Limitations

- The checked-in evidence is a single A2 run; it does not establish general model performance or compare against the baseline condition.
- Model outputs can vary between calls. No repeated-run statistics or inter-rater reliability study is included.
- The script does not resume at a failed graph step. Restarting after a partial failure may repeat earlier API calls.
- The rubric score is provisional and needs human validation.
- The scenario and identifiers are synthetic; no production telemetry or customer data was used.

## Privacy and publishing

The checked-in example uses synthetic data. Do not add customer, employer, or other confidential information. Before publishing, inspect the Git changes and verify that `.env`, `.venv/`, and unreviewed `runs/` contents are not staged. Only move a run into `results/` after checking it for sensitive data and confirming that its prompts, outputs, and score are suitable to share.
