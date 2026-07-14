# Smart Case Filing

[中文](README.md)

Smart Case Filing is an intelligent directory prediction tool for court e-filing materials. It reads PDFs, Word documents, images, spreadsheets, and text files, combines local catalog rules with text and vision model analysis, and predicts the case type, volume, second-level directory, and material category.

The current project is centered on a single Python script. It is suitable for local batch processing, catalog-rule validation, model integration testing, and prototyping before integration with a larger case-filing system.

## Key Features

- Supports PDFs, Word documents, images, spreadsheets, plain text, and common structured text files.
- Extracts text from PDFs and can render the first pages for vision-model analysis.
- Sends images to the vision model for layout recognition and OCR clues.
- Sends extracted text to the language model for document type, case clues, keywords, and summaries.
- Retrieves candidate catalog rules from `catalog-mapping.xlsx`, then asks the model to select the best candidate.
- Supports OpenAI-compatible HTTP APIs through environment variables for `base_url`, `api_key`, and `model`.
- Falls back to the legacy `z-ai` CLI when the HTTP model configuration is incomplete.
- Can save stdout and stderr to separate files for auditing and review.
- The operational batch agent mode supports execution traces, run manifests, low-confidence review, partial resume, retry CLI options, model preflight, and review decision records.

## Workflow

```text
Input file
  -> ContentExtractor extracts text and images
  -> VLMAnalyzer analyzes visual materials and OCR clues
  -> LLMAnalyzer builds a text semantic profile
  -> CatalogIndex retrieves candidate catalog rules
  -> DirectoryPredictor asks the model to select a candidate
  -> Predicted directory and analysis result
```

The predicted directory is composed from:

```text
case type / volume / second-level directory / material category
```

## Supported File Types

| Type | Extensions | Processing |
| --- | --- | --- |
| PDF | `.pdf` | Extract text with PyMuPDF and render the first N pages for vision analysis |
| Word | `.docx` | Extract paragraphs and table text with `python-docx` |
| Legacy Word | `.doc` | Convert to `.docx` with LibreOffice, then extract text |
| Image | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` | Send to the vision model for layout recognition and OCR |
| Spreadsheet | `.xlsx` `.xlsm` `.xls` | Read the first 200 rows of all sheets with pandas |
| Text | `.txt` `.csv` `.tsv` `.md` `.json` `.log` `.xml` `.html` `.htm` | Try multiple encodings |
| Other | any extension | Fallback to text extraction |

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

For runtime-only usage, this minimal dependency set is usually enough:

```bash
pip install pandas openpyxl pymupdf python-docx requests
```

Install LibreOffice if `.doc` support is required:

```bash
libreoffice --version
```

Configure an OpenAI-compatible model service:

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

Run single-file prediction:

```bash
python file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx --json
```

Run batch prediction:

```bash
python file_directory_predictor.py --batch ./input-files --catalog ./catalog-mapping.xlsx --json
```

Save output and logs to explicit files:

```bash
python file_directory_predictor.py ./sample.pdf \
  --catalog ./catalog-mapping.xlsx \
  --json \
  --output ./logs/result.json \
  --log ./logs/run.log
```

If `--output` and `--log` are omitted, the script writes these files under the script directory:

- `file_directory_predictor_output.txt`: original stdout content.
- `file_directory_predictor.log`: original stderr content.

## Model Configuration

Generic variables:

| Variable | Meaning |
| --- | --- |
| `AI_BASE_URL` | OpenAI-compatible API base URL, for example `https://api.openai.com/v1` |
| `AI_API_KEY` | API key |
| `AI_MODEL` | Default model name |

Chat-model overrides:

| Variable | Meaning |
| --- | --- |
| `AI_CHAT_BASE_URL` | Chat-model API base URL |
| `AI_CHAT_API_KEY` | Chat-model API key |
| `AI_CHAT_MODEL` | Chat-model name |

Vision-model overrides:

| Variable | Meaning |
| --- | --- |
| `AI_VISION_BASE_URL` | Vision-model API base URL |
| `AI_VISION_API_KEY` | Vision-model API key |
| `AI_VISION_MODEL` | Vision-model name |

Priority:

```text
chat   : AI_CHAT_*   -> AI_*
vision : AI_VISION_* -> AI_*
```

Enable model-call debugging with:

```bash
export AI_DEBUG=1
```

If `base_url`, `api_key`, and `model` are not all configured, the script falls back to:

```bash
z-ai chat
z-ai vision
```

## Catalog Rules

`catalog-mapping.xlsx` must contain at least these columns:

```text
case_type
volume
second_level_directory
constraint
material_category
catalog_name_example
```

The program retrieves candidates from the catalog first, then asks the model to choose only from those candidate IDs. The final result prioritizes `selected_index` and writes back the exact fields from the selected catalog entry to reduce hallucinated catalog values.

## Paths and Runtime Output

The current defaults are defined near the top of `file_directory_predictor.py`:

```python
PROJECT_ROOT = Path("/Users/mooye/python project/smart-case-filing")
PROGRAM_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG = PROJECT_ROOT / "catalog-mapping.xlsx"
TMP_DIR = PROJECT_ROOT / "scripts" / "_tmp_predict"
```

For better portability, pass `--catalog`, `--output`, and `--log` explicitly in command-line runs. For deployment on another machine, prefer deriving these paths from the script directory or external configuration.

## Repository Layout

```text
.
├── file_directory_predictor.py           # Main script
├── catalog-mapping.xlsx                  # Catalog rules
├── README.md                             # Chinese README
├── README.en.md                          # English README
├── docs/
│   ├── 卷宗智能推理编目使用说明.md              # Chinese usage guide
│   ├── Smart_Case_Filing_Usage.en.md     # English usage guide
│   └── 处理结果字段解释.md                 # Prediction result field reference
├── logs/                                 # Runtime logs and output samples
├── offline_pkgs/                         # Offline dependency packages
├── test-reports/                         # End-to-end validation reports
└── tests/                                # Unit tests
```

## Result Fields

The main JSON output fields include:

- `file_path`, `file_type`: input path and detected type.
- `predicted_case_type`, `predicted_volume`, `predicted_second_level_directory`, `predicted_material_category`: final predicted directory fields.
- `predicted_catalog_example`: catalog-name example from the selected rule.
- `confidence`, `reasoning`: confidence level and selection rationale.
- `vlm_analysis`: vision-model analysis result.
- `llm_analysis`: text-model analysis result.
- `matched_entries`: selected catalog rule entries.

See [docs/处理结果字段解释.md](docs/处理结果字段解释.md) for the detailed field reference.

See [docs/Smart_Case_Filing_Usage.en.md](docs/Smart_Case_Filing_Usage.en.md) for the full command-line usage guide.

## Verification and Tests

Run unit tests:

```bash
python -m unittest discover -s tests
```

Run syntax checks:

```bash
python -m py_compile file_directory_predictor.py tests/test_catalog_index.py tests/test_cli_output.py
```

The repository includes an end-to-end OpenAI-compatible model validation record:

- [test-reports/full-chain-report.md](test-reports/full-chain-report.md)
- [test-reports/full-chain-report.json](test-reports/full-chain-report.json)
- [test-reports/full-chain-run.json](test-reports/full-chain-run.json)

## Security Notes

- Do not write real API keys into code, documentation, or commit history.
- Before sharing logs or reports, check for unmasked keys, Authorization headers, and sensitive case materials.
- Authorization values in test reports should remain masked.

## Known Limitations

- Candidate retrieval depends on keyword matching and catalog quality.
- Text analysis uses only the first `MAX_TEXT_CHARS` characters by default.
- PDF vision analysis renders only the first `MAX_PDF_PAGES_FOR_VLM` pages by default.
- OpenAI-compatible vision requests use `image_url` data URI payloads, which must be supported by the target service.
- `.doc` support depends on system LibreOffice.
- The current default paths still contain a machine-specific project path; use explicit CLI arguments or dynamic configuration when moving across machines.

## License

This project is distributed under a non-commercial license. Unless separately authorized in writing by the project rights holder, the code, documentation, catalog rules, and sample materials may be used only for learning, research, evaluation, internal validation, and non-commercial prototyping. They may not be used in revenue-generating products, commercial delivery, commercial SaaS services, or other commercial scenarios.

See [LICENSE.md](LICENSE.md) for the full terms. For commercial use, redistribution, or integration into a commercial system, obtain prior written authorization from the project rights holder.
