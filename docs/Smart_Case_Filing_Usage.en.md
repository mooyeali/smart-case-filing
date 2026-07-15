# file_directory_predictor.py English Usage Guide

[中文使用说明](卷宗智能推理编目使用说明.md)

This document explains how to install, configure, and run `file_directory_predictor.py`, and how to understand its output and troubleshoot common issues.

`file_directory_predictor.py` is a court case filing directory prediction tool. It reads an input file, calls text and vision models to build a document profile, and uses `catalog-mapping.xlsx` catalog rules to predict the destination directory.

Final directory format:

```text
case type / volume / second-level directory / material category
```

## 1. Environment Requirements

### 1.1 Python

Python 3.10 or later is recommended.

```bash
python --version
```

### 1.2 Python Dependencies

Install dependencies:

```bash
pip install pandas openpyxl pymupdf python-docx requests
```

| Dependency | Purpose |
| --- | --- |
| `pandas` | Reads Excel catalog rules and spreadsheet files |
| `openpyxl` | Enables `.xlsx` support |
| `pymupdf` | Extracts PDF text and renders pages |
| `python-docx` | Extracts `.docx` content |
| `requests` | Calls OpenAI-compatible HTTP model services |

### 1.3 LibreOffice Optional

LibreOffice is required only for legacy `.doc` files.

```bash
libreoffice --version
```

## 2. Model Service Configuration

The script prefers OpenAI-compatible HTTP APIs. At minimum, configure:

- `base_url`
- `api_key`
- `model`

### 2.1 Generic Configuration

Bash:

```bash
export AI_BASE_URL="https://api.openai.com/v1"
export AI_API_KEY="sk-..."
export AI_MODEL="gpt-4.1"
```

PowerShell:

```powershell
$env:AI_BASE_URL = "https://api.openai.com/v1"
$env:AI_API_KEY = "sk-..."
$env:AI_MODEL = "gpt-4.1"
```

### 2.2 Separate Chat and Vision Models

Bash:

```bash
export AI_CHAT_BASE_URL="https://api.deepseek.com/v1"
export AI_CHAT_API_KEY="sk-..."
export AI_CHAT_MODEL="deepseek-chat"

export AI_VISION_BASE_URL="https://api.openai.com/v1"
export AI_VISION_API_KEY="sk-..."
export AI_VISION_MODEL="gpt-4.1"
```

PowerShell:

```powershell
$env:AI_CHAT_BASE_URL = "https://api.deepseek.com/v1"
$env:AI_CHAT_API_KEY = "sk-..."
$env:AI_CHAT_MODEL = "deepseek-chat"

$env:AI_VISION_BASE_URL = "https://api.openai.com/v1"
$env:AI_VISION_API_KEY = "sk-..."
$env:AI_VISION_MODEL = "gpt-4.1"
```

### 2.3 Priority

```text
chat:
  AI_CHAT_BASE_URL / AI_CHAT_API_KEY / AI_CHAT_MODEL
  -> AI_BASE_URL / AI_API_KEY / AI_MODEL

vision:
  AI_VISION_BASE_URL / AI_VISION_API_KEY / AI_VISION_MODEL
  -> AI_BASE_URL / AI_API_KEY / AI_MODEL
```

### 2.4 z-ai Fallback

If the HTTP configuration is incomplete, the script falls back to:

```bash
z-ai chat
z-ai vision
```

Check the fallback before use:

```bash
z-ai chat -p "test"
z-ai vision -p "describe image" -i /path/to/image.png
```

## 3. Catalog Rules

`catalog-mapping.xlsx` must contain at least:

```text
case_type
volume
second_level_directory
constraint
material_category
catalog_name_example
```

Pass the catalog explicitly:

```bash
--catalog ./catalog-mapping.xlsx
```

## 4. Supported Inputs

| File type | Extensions | Processing |
| --- | --- | --- |
| PDF | `.pdf` | Extract text and render first N pages for vision analysis |
| Word | `.docx` | Extract paragraphs and table text |
| Legacy Word | `.doc` | Convert with LibreOffice first |
| Image | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` | Send to vision model for recognition and OCR |
| Spreadsheet | `.xlsx` `.xlsm` `.xls` | Read first 200 rows of all sheets |
| Text | `.txt` `.csv` `.tsv` `.md` `.json` `.log` `.xml` `.html` `.htm` | Try multiple encodings |
| Other | any extension | Fallback to text reading |

## 5. Single-file Prediction

Basic command:

```bash
python file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx
```

JSON output:

```bash
python file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx --json
```

The output includes:

- File path
- File type
- Predicted directory
- Catalog name example
- Confidence
- Reasoning
- VLM analysis
- LLM analysis
- Matched catalog entries

## 6. Batch Prediction

Process direct files under a directory:

```bash
python file_directory_predictor.py --batch ./input-files --catalog ./catalog-mapping.xlsx
```

Batch JSON output:

```bash
python file_directory_predictor.py --batch ./input-files --catalog ./catalog-mapping.xlsx --json
```

Save output and logs to explicit files:

```bash
python file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx --json --output ./result.json --log ./run.log
```

If `--output` and `--log` are not provided, the program writes default files under the script directory:

- `file_directory_predictor_output.txt`: runtime output, equivalent to stdout
- `file_directory_predictor.log`: runtime logs, equivalent to stderr

The current batch mode does not recurse into subdirectories.

## 7. Batch-resumable Agent Mode

Agent mode is for cataloging tasks that need execution traces, low-confidence review, batch summaries, and resumable runs. It uses the same OpenAI-compatible HTTP API configuration and legacy `z-ai` fallback as the normal predictor, and reuses the existing extraction, visual analysis, text analysis, and catalog candidate rules.

```bash
python file_directory_predictor.py ./sample.pdf \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./logs/sample.trace.jsonl \
  --review-output ./logs/sample.review.json \
  --json
```

Agent mode keeps the normal JSON output fields compatible and adds `agent_state`, `trace`, `review_output`, `resume`, and related agent fields.

Batch agent example:

```bash
python file_directory_predictor.py \
  --batch ./input-files \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./agent-runs/demo \
  --review-output ./agent-runs/demo/reviews \
  --json
```

Batch mode only processes direct files in the specified directory. In batch agent mode, `--trace` is treated as the run directory. If `--review-output` points to a directory, review packages and `index.json` are written there. The run writes:

```text
agent-runs/<run_id>/
  manifest.json
  traces/<file_id>.trace.jsonl
  reviews/<file_id>.review.json
  reviews/index.json
  outputs/<file_id>.json
```

Arguments:

| Argument | Meaning |
| --- | --- |
| `--agent` | Enables the agent state machine. |
| `--trace <path>` | In single-file mode, writes a JSONL trace; in batch mode, acts as the run directory. |
| `--review-output <path>` | In single-file mode, a review JSON file; in batch mode, a review directory. |
| `--resume <trace-or-manifest>` | Resumes from a single-file trace or batch manifest. Terminal states are not rerun; partial states attempt to continue from the next step. |
| `--agent-retry-attempts <n>` | Maximum tool attempts. Default: `1`. |
| `--agent-retry-delay <seconds>` | Initial retry delay. Default: `0`. |
| `--agent-retry-backoff <factor>` | Retry backoff factor. Default: `2.0`. |
| `--agent-retry-errors <keywords>` | Comma-separated retryable error substrings. |
| `--agent-preflight` | Prints model configuration status without network calls or input files. |
| `--review-decision <json>` | Records a human review decision and updates the run manifest. |
| `--agent-validate-run <manifest-or-run-dir>` | Validates manifest, trace, output, review, decision, and review index artifacts. |
| `--agent-export-report <path>` | With `--agent-validate-run`, exports a Markdown or JSON audit report. |
| `--agent-full-chain-test <output-dir>` | Runs a no-model fake full-chain validation and writes complete run artifacts plus audit reports. |

Each trace JSONL line is one step record:

```json
{
  "run_id": "agent-...",
  "file_path": "sample.pdf",
  "state": "TEXT_ANALYZED",
  "tool": "analyze_text",
  "input_summary": {},
  "output_summary": {},
  "error": "",
  "created_at": 1784040000.0
}
```

The review package contains `file_path`, `agent_state`, `confidence`, `reasoning`, `trace`, `candidate_summaries`, `llm_analysis`, `vlm_analysis`, `error`, and `created_at`. API keys and similar secrets are redacted before the file is written.

For batch runs, `manifest.json` records each file's state, confidence, trace, review, output, and error summary. `reviews/index.json` indexes all `NEEDS_REVIEW` and `FAILED` files for centralized review.

Model configuration preflight:

```bash
python file_directory_predictor.py \
  --agent \
  --agent-preflight \
  --json
```

Preflight checks whether `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL` are complete, and whether a legacy `z-ai` executable exists on PATH. It does not call remote model APIs.

Resume example:

```bash
python file_directory_predictor.py \
  --agent \
  --resume ./logs/sample.trace.jsonl \
  --json
```

Batch resume example:

```bash
python file_directory_predictor.py \
  --agent \
  --resume ./agent-runs/demo/manifest.json \
  --catalog ./catalog-mapping.xlsx \
  --json
```

Batch resume persists resumed file outputs, review packages, manifest updates, and the review index. Terminal files in `COMPLETED`, `NEEDS_REVIEW`, or `FAILED` are not rerun.

Review decision example:

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

Record the decision:

```bash
python file_directory_predictor.py \
  --agent \
  --resume ./agent-runs/demo/manifest.json \
  --review-decision ./decision.json \
  --json
```

Validate run artifacts:

```bash
python file_directory_predictor.py \
  --agent \
  --agent-validate-run ./agent-runs/demo/manifest.json \
  --agent-export-report ./agent-runs/demo/audit.md \
  --json
```

The audit checks:

- `manifest.json` exists and parses.
- manifest status counts match file entries.
- each file has trace and output artifacts.
- `NEEDS_REVIEW` and `FAILED` files have review packages.
- `reviews/index.json` covers every reviewable file.
- recorded review decision files exist.

No-model full-chain validation:

```bash
python file_directory_predictor.py \
  --agent \
  --agent-full-chain-test ./test-reports/agent-full-chain-smoke \
  --json
```

This command generates a deterministic fake run: one `COMPLETED` file, one `NEEDS_REVIEW` file, one `FAILED` file, review index, review decision, Markdown audit report, and JSON audit report. It does not call real models, so it is suitable as a fast local acceptance button before handoff.

Phase-three behavior and limitations:

- Batch agent mode is supported, but still only processes direct files in the target directory.
- Partial resume is supported; if trace summaries are insufficient to resume safely, the command returns a clear failed response.
- Tool calls use a retry policy. The CLI can configure attempts, backoff, and retryable errors.
- Run audit is read-only; it does not update manifest files or rerun tools.
- Real model smoke tests require `AI_BASE_URL`, `AI_API_KEY`, and `AI_MODEL`, or an available legacy `z-ai` CLI fallback.

## 8. Output Fields

Example JSON shape:

```json
{
  "file_path": "sample.pdf",
  "file_type": "pdf",
  "predicted_case_type": "Civil First-instance Case Catalog Rules",
  "predicted_volume": "Main volume",
  "predicted_second_level_directory": "Complaint and related materials",
  "predicted_material_category": "Civil complaint",
  "predicted_catalog_example": "Civil complaint",
  "confidence": "high",
  "reasoning": "Reasoning",
  "vlm_analysis": {},
  "llm_analysis": {},
  "matched_entries": []
}
```

| Field | Meaning |
| --- | --- |
| `file_path` | Input file path |
| `file_type` | Detected file type |
| `predicted_case_type` | Predicted case type |
| `predicted_volume` | Predicted volume |
| `predicted_second_level_directory` | Predicted second-level directory |
| `predicted_material_category` | Predicted material category |
| `predicted_catalog_example` | Catalog name example |
| `confidence` | `high`, `medium`, or `low` |
| `reasoning` | Model reasoning |
| `vlm_analysis` | Vision-model analysis |
| `llm_analysis` | Text-model analysis |
| `matched_entries` | Matched catalog entries |

## 9. Internal Flow

### 8.1 Content Extraction

`ContentExtractor.extract()` returns:

```text
file_path
file_type
text
image_paths
page_count
extract_error
```

### 8.2 Vision Analysis

`VLMAnalyzer.analyze()` calls `_run_zai_vision()`.

HTTP path:

```text
POST {AI_VISION_BASE_URL or AI_BASE_URL}/chat/completions
```

Vision payload uses `image_url` data URIs.

### 8.3 Text Analysis

`LLMAnalyzer.analyze_text()` calls `_run_zai_chat()` and expects JSON containing document type, volume, case clues, key phrases, summary, and confidence.

### 8.4 Candidate Retrieval

`DirectoryPredictor` passes the file parent directory name to `CatalogIndex.search_candidates()` as the case-number clue.

`CatalogIndex.search_candidates()` first tries to infer the case type from the case number, such as `民初`, `民终`, `刑初`, `行再`, or `执`, and loads all catalog rules for that case type. If the case type cannot be inferred from the case number, it falls back to keyword-based candidate retrieval using document type, case clues, summary, key phrases, and file name.

### 8.5 Candidate Selection

The model selects one candidate index. The code trusts `selected_index` first and writes back exact fields from the selected catalog row.

## 10. Tuning

Common constants:

```python
MAX_PDF_PAGES_FOR_VLM = 10
MAX_TEXT_CHARS = 6000
CLI_TIMEOUT = 180
```

| Constant | Meaning |
| --- | --- |
| `MAX_PDF_PAGES_FOR_VLM` | Number of PDF pages sent to the vision model |
| `MAX_TEXT_CHARS` | Maximum text characters sent to the LLM |
| `CLI_TIMEOUT` | Model-call timeout in seconds |

## 11. Troubleshooting

### 10.1 Default path does not match the deployment environment

The script currently defines these default paths near the top of `file_directory_predictor.py`:

```python
PROJECT_ROOT = Path("/Users/mooye/python project/smart-case-filing")
PROGRAM_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG = PROJECT_ROOT / "catalog-mapping.xlsx"
TMP_DIR = PROJECT_ROOT / "scripts" / "_tmp_predict"
```

When deploying to another machine, pass the catalog explicitly:

```bash
--catalog ./catalog-mapping.xlsx
```

For long-term use, derive `PROJECT_ROOT` from the script directory or deployment configuration.

### 10.2 Catalog file not found

Check the file:

```bash
ls catalog-mapping.xlsx
```

Run:

```bash
python file_directory_predictor.py sample.pdf --catalog ./catalog-mapping.xlsx
```

### 10.3 LLM or VLM returns nothing

Check:

```bash
AI_BASE_URL
AI_API_KEY
AI_MODEL
```

Or dedicated variables:

```bash
AI_CHAT_BASE_URL / AI_CHAT_API_KEY / AI_CHAT_MODEL
AI_VISION_BASE_URL / AI_VISION_API_KEY / AI_VISION_MODEL
```

Enable debug:

```bash
export AI_DEBUG=1
```

PowerShell:

```powershell
$env:AI_DEBUG = "1"
```

### 10.4 Poor PDF recognition

Increase:

```python
MAX_PDF_PAGES_FOR_VLM = 5
```

### 10.5 Key content is not at the beginning

Increase:

```python
MAX_TEXT_CHARS = 12000
```

## 12. Test Reports

The repository includes an end-to-end run:

```text
test-reports/full-chain-input.txt
test-reports/full-chain-run.json
test-reports/full-chain-report.json
test-reports/full-chain-report.md
```

The report covers environment-based model configuration, real HTTP request/response records, text extraction, LLM analysis, candidate retrieval, and final JSON output.

## 13. Security Notes

- Do not commit real API keys.
- Mask Authorization headers before sharing logs.
- Do not commit sensitive case materials to a public repository.

