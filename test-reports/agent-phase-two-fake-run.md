# Agent Phase Two Fake Run Report

## Command

```bash
python file_directory_predictor.py ./test-reports/full-chain-input.txt \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./test-reports/agent-phase-two-fake-run.trace.jsonl \
  --review-output ./test-reports/agent-phase-two-fake-run.review.json \
  --json
```

## Input File

- `./test-reports/full-chain-input.txt`
- Plain text legal filing sample used for deterministic agent integration checks.

## Fake Model Behavior

- Text analysis returns a civil complaint profile with high confidence.
- Visual analysis is skipped because the input has no rendered images.
- Candidate retrieval returns one catalog candidate.
- Catalog selection returns the candidate as the final match.

## Trace Excerpt

```json
{"state":"STARTED","tool":"start","file_path":"./test-reports/full-chain-input.txt"}
{"state":"EXTRACTED","tool":"extract_content","output_summary":{"file_type":"text","text_length":32}}
{"state":"TEXT_ANALYZED","tool":"analyze_text","output_summary":{"llm_analysis":{"confidence":"high"}}}
{"state":"CANDIDATES_RETRIEVED","tool":"retrieve_candidates","output_summary":{"candidate_count":1}}
{"state":"MATCHED","tool":"select_catalog","output_summary":{"match":{"confidence":"high"}}}
{"state":"COMPLETED","tool":"finalize_prediction","output_summary":{"confidence":"high"}}
```

## JSON Output

```json
{
  "file_path": "./test-reports/full-chain-input.txt",
  "file_type": "text",
  "predicted_case_type": "Civil First-instance Case Catalog Rules",
  "predicted_volume": "Main volume",
  "predicted_second_level_directory": "Complaint and related materials",
  "predicted_material_category": "Civil complaint",
  "predicted_catalog_example": "Civil complaint",
  "confidence": "high",
  "reasoning": "Fake model selected the only matching candidate.",
  "agent_state": "COMPLETED",
  "trace": "./test-reports/agent-phase-two-fake-run.trace.jsonl",
  "review_output": "./test-reports/agent-phase-two-fake-run.review.json",
  "resume": ""
}
```

## Review Output

No review package is expected for this high-confidence completed fake run. Low-confidence or failed runs write the structured review package to `--review-output`.

## Test Command

```bash
python -m unittest discover -s tests
```
