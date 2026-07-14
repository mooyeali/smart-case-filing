# Agent Phase Three Fake Full-chain Report

## Command

```bash
python file_directory_predictor.py \
  --batch ./test-reports/agent-phase-three-input \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./agent-runs/phase-three-fake \
  --json
```

## Input Files

```text
completed.txt
review.txt
failed.txt
```

The fake registry returns one completed file, one low-confidence file, and one deterministic candidate-retrieval failure.

## Fake Model Behavior

- `completed.txt`: candidate selection returns `confidence=high`, final state `COMPLETED`.
- `review.txt`: candidate selection returns `confidence=low`, final state `NEEDS_REVIEW`.
- `failed.txt`: candidate retrieval returns `no catalog candidates`, final state `FAILED`.

## Run Directory

```text
agent-runs/phase-three-fake/
  manifest.json
  traces/<file_id>.trace.jsonl
  reviews/<file_id>.review.json
  reviews/index.json
  outputs/<file_id>.json
```

## Manifest Summary

```json
{
  "status_counts": {
    "COMPLETED": 1,
    "NEEDS_REVIEW": 1,
    "FAILED": 1
  },
  "file_count": 3
}
```

## Review Index

`reviews/index.json` contains the `review.txt` and `failed.txt` entries with trace paths, review paths, confidence, reasoning, and error summaries.

## Resume Command

```bash
python file_directory_predictor.py \
  --agent \
  --resume ./agent-runs/phase-three-fake/manifest.json \
  --catalog ./catalog-mapping.xlsx \
  --json
```

For a completed manifest, the resume command skips all terminal files and reports `BATCH_RESUMED` with `resumed_count=0`.

## Verification

```bash
python -m unittest tests/test_agent_full_chain.py
python -m unittest discover -s tests
```
