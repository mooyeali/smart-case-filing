# Agent Phase Five Fake Audit Report

## Validate a Complete Run

```bash
python file_directory_predictor.py \
  --agent \
  --agent-validate-run ./agent-runs/phase-five-fake/manifest.json \
  --agent-export-report ./agent-runs/phase-five-fake/audit.md \
  --json
```

Expected JSON shape:

```json
{
  "valid": true,
  "run_id": "phase-five-fake",
  "file_count": 3,
  "review_count": 2,
  "decision_count": 1,
  "issues": [],
  "report": "./agent-runs/phase-five-fake/audit.md"
}
```

The Markdown report includes run id, manifest path, status counts, issues, and per-file summaries.

## Validate a Run with Missing Artifacts

If a trace file is missing or the review index does not include every `NEEDS_REVIEW` / `FAILED` file, validation returns:

```json
{
  "valid": false,
  "issues": [
    {
      "message": "trace path does not exist: ..."
    },
    {
      "message": "review index does not include reviewable file"
    }
  ]
}
```

## Export JSON Report

```bash
python file_directory_predictor.py \
  --agent \
  --agent-validate-run ./agent-runs/phase-five-fake/manifest.json \
  --agent-export-report ./agent-runs/phase-five-fake/audit.json \
  --json
```

`.json` suffix exports the full audit result as structured JSON. Other suffixes export Markdown.

## Verification

```bash
python -m unittest tests/test_agent_audit.py
python -m unittest discover -s tests
python file_directory_predictor.py --help
```
