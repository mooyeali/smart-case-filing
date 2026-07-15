# Agent Phase Six Full-chain Validation Report

## Command

```bash
python file_directory_predictor.py \
  --agent \
  --agent-full-chain-test ./test-reports/agent-full-chain-smoke \
  --json
```

## What It Generates

```text
agent-full-chain-smoke/
  input/
    completed.txt
    review.txt
    failed.txt
  run/
    manifest.json
    traces/
    outputs/
    decisions/
  reviews/
    *.review.json
    index.json
  audit.md
  audit.json
```

## Expected Summary

```json
{
  "agent_state": "FULL_CHAIN_TEST_COMPLETED",
  "audit": {
    "valid": true,
    "status_counts": {
      "COMPLETED": 1,
      "NEEDS_REVIEW": 1,
      "FAILED": 1
    },
    "review_count": 2,
    "decision_count": 1,
    "issues": []
  }
}
```

## Coverage

- batch-style agent execution
- completed path
- low-confidence review path
- failure review path
- review index
- review decision
- run audit
- Markdown audit report
- JSON audit report

## Verification

```bash
python -m unittest tests/test_agent_full_chain_cli.py
python -m unittest discover -s tests
python file_directory_predictor.py --help
```
