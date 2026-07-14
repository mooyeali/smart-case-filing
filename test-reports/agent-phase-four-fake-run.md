# Agent Phase Four Fake Operations Report

## Preflight

```bash
python file_directory_predictor.py --agent --agent-preflight --json
```

Expected shape:

```json
{
  "http": {
    "configured": false,
    "base_url": "",
    "api_key_configured": false,
    "model": ""
  },
  "legacy_z_ai": {
    "available": false,
    "path": ""
  },
  "selected_mode": "unconfigured"
}
```

Preflight does not call network APIs.

## Batch Run

```bash
python file_directory_predictor.py \
  --batch ./test-reports/agent-phase-four-input \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./agent-runs/phase-four-fake \
  --review-output ./agent-runs/phase-four-fake-reviews \
  --agent-retry-attempts 2 \
  --agent-retry-errors "temporary,unavailable" \
  --json
```

The fake batch run covers:

- one `COMPLETED` file
- one `NEEDS_REVIEW` file
- one `FAILED` file
- per-file trace and output JSON
- review packages in the explicit review output directory
- `reviews/index.json` in the explicit review output directory

## Batch Resume

```bash
python file_directory_predictor.py \
  --agent \
  --resume ./agent-runs/phase-four-fake/manifest.json \
  --catalog ./catalog-mapping.xlsx \
  --json
```

Batch resume persists updated outputs, manifest entries, review packages, and review index. Terminal files are skipped.

## Review Decision

Decision input:

```json
{
  "file_id": "review-123",
  "file_path": "input/review.txt",
  "decision": "approved",
  "final_prediction": {},
  "reviewer": "reviewer-a",
  "notes": "confirmed"
}
```

Command:

```bash
python file_directory_predictor.py \
  --agent \
  --resume ./agent-runs/phase-four-fake/manifest.json \
  --review-decision ./decision.json \
  --json
```

The decision is written to:

```text
agent-runs/phase-four-fake/decisions/<file_id>.decision.json
```

The run manifest records `decision`, `decision_path`, and `reviewed_at`.

## Verification

```bash
python -m unittest discover -s tests
python file_directory_predictor.py --help
```
