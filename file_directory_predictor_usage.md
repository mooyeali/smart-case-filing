# file_directory_predictor.py 使用文档

> 中文为默认文档语言。English version follows the Chinese version.

## 中文版

本文档说明如何安装、配置和运行 `file_directory_predictor.py`，以及如何理解输出结果和排查常见问题。

`file_directory_predictor.py` 是一个法院卷宗材料目录推测工具。它读取输入文件内容，调用文本模型和视觉模型生成文档画像，再结合 `catalog-mapping.xlsx` 编目规则表，推测文件应归属的目录。

最终目录格式：

```text
案件类型 / 卷宗 / 二级目录 / 材料类别
```

## 1. 环境要求

### 1.1 Python

建议使用 Python 3.10 或更高版本。

检查版本：

```bash
python --version
```

### 1.2 Python 依赖

安装基础依赖：

```bash
pip install pandas openpyxl pymupdf python-docx requests
```

依赖用途：

| 依赖 | 用途 |
| --- | --- |
| `pandas` | 读取 Excel 编目规则和表格文件 |
| `openpyxl` | 支持 `.xlsx` 文件读取 |
| `pymupdf` | PDF 文本提取和页面渲染 |
| `python-docx` | `.docx` 文档内容提取 |
| `requests` | 调用 OpenAI-compatible HTTP 模型服务 |

### 1.3 LibreOffice（可选）

只有处理 `.doc` 老 Word 文件时才需要。

```bash
libreoffice --version
```

如果不处理 `.doc` 文件，可以不安装 LibreOffice。

## 2. 模型服务配置

脚本优先使用 OpenAI-compatible HTTP API。最少需要配置：

- `base_url`
- `api_key`
- `model`

### 2.1 通用配置

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

### 2.2 分别配置文本模型和视觉模型

如果文本和视觉使用不同服务或不同模型，可以使用专用变量。

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

### 2.3 环境变量优先级

```text
chat:
  AI_CHAT_BASE_URL / AI_CHAT_API_KEY / AI_CHAT_MODEL
  -> AI_BASE_URL / AI_API_KEY / AI_MODEL

vision:
  AI_VISION_BASE_URL / AI_VISION_API_KEY / AI_VISION_MODEL
  -> AI_BASE_URL / AI_API_KEY / AI_MODEL
```

### 2.4 z-ai fallback

如果没有配置完整的 HTTP 三件套，脚本会回退到旧的 `z-ai` CLI：

```bash
z-ai chat
z-ai vision
```

使用 fallback 前，请确认：

```bash
z-ai chat -p "测试"
z-ai vision -p "描述图片内容" -i /path/to/image.png
```

## 3. 编目规则表

默认使用 `catalog-mapping.xlsx`。该文件至少需要包含以下列：

```text
case_type
volume
second_level_directory
constraint
material_category
catalog_name_example
```

运行时建议显式传入：

```bash
--catalog ./catalog-mapping.xlsx
```

## 4. 支持的输入文件

| 文件类型 | 扩展名 | 处理方式 |
| --- | --- | --- |
| PDF | `.pdf` | 提取文本，并把前 N 页渲染为图片交给视觉模型 |
| Word 新格式 | `.docx` | 提取段落和表格文本 |
| Word 老格式 | `.doc` | 先用 LibreOffice 转为 `.docx` |
| 图片 | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` | 交给视觉模型做识别和 OCR |
| 表格 | `.xlsx` `.xlsm` `.xls` | 读取所有 sheet 的前 200 行 |
| 文本 | `.txt` `.csv` `.tsv` `.md` `.json` `.log` `.xml` `.html` `.htm` | 尝试多编码读取 |
| 其他 | 任意扩展名 | 兜底按文本读取 |

## 5. 单文件预测

基本命令：

```bash
python file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx
```

JSON 输出：

```bash
python file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx --json
```

输出内容包括：

- 文件路径
- 文件类型
- 推测目录
- 编目名称示例
- 置信度
- 匹配理由
- VLM 视觉分析结果
- LLM 文本分析结果
- 命中的编目规则

## 6. 批量预测

处理目录下所有一级文件：

```bash
python file_directory_predictor.py --batch ./input-files --catalog ./catalog-mapping.xlsx
```

批量 JSON 输出：

```bash
python file_directory_predictor.py --batch ./input-files --catalog ./catalog-mapping.xlsx --json
```

注意：当前批量模式只处理指定目录下的直接文件，不递归处理子目录。

## 7. 输出字段说明

JSON 输出示例结构：

```json
{
  "file_path": "sample.pdf",
  "file_type": "pdf",
  "predicted_case_type": "民事一审案件编目规则",
  "predicted_volume": "正卷",
  "predicted_second_level_directory": "起诉状及相关材料",
  "predicted_material_category": "民事起诉状",
  "predicted_catalog_example": "民事起诉状",
  "confidence": "high",
  "reasoning": "匹配理由",
  "vlm_analysis": {},
  "llm_analysis": {},
  "matched_entries": []
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `file_path` | 输入文件路径 |
| `file_type` | 提取器识别出的文件类型 |
| `predicted_case_type` | 推测案件类型 |
| `predicted_volume` | 推测卷宗 |
| `predicted_second_level_directory` | 推测二级目录 |
| `predicted_material_category` | 推测材料类别 |
| `predicted_catalog_example` | 编目名称示例 |
| `confidence` | `high` / `medium` / `low` |
| `reasoning` | 模型给出的匹配理由 |
| `vlm_analysis` | 视觉模型分析结果 |
| `llm_analysis` | 文本模型分析结果 |
| `matched_entries` | 最终命中的编目规则 |

## 8. 内部处理流程

### 8.1 内容提取

`ContentExtractor.extract()` 根据扩展名提取：

```text
file_path
file_type
text
image_paths
page_count
extract_error
```

### 8.2 视觉分析

`VLMAnalyzer.analyze()` 对图片或 PDF 渲染页调用 `_run_zai_vision()`。

HTTP 模型路径使用：

```text
POST {AI_VISION_BASE_URL or AI_BASE_URL}/chat/completions
```

视觉请求使用 `image_url` data URI 形式，因此目标模型服务需要支持 OpenAI-compatible vision payload。

### 8.3 文本分析

`LLMAnalyzer.analyze_text()` 对提取文本调用 `_run_zai_chat()`，要求模型返回 JSON：

```json
{
  "doc_type_guess": "文书类型",
  "volume_guess": "正卷/副卷/未知",
  "case_clues": "案件类型线索",
  "key_phrases": "关键短语",
  "summary": "一句话摘要",
  "confidence": "high/medium/low"
}
```

### 8.4 候选召回

`DirectoryPredictor._extract_keywords()` 从文书类型、案件线索、摘要、关键短语和文件名中提取关键词。

`CatalogIndex.search_candidates()` 使用关键词在编目规则表中召回最多 25 条候选。

### 8.5 候选精选

模型从候选编号中选择最匹配条目。解析时优先使用 `selected_index`，并用候选规则表反写字段，以减少模型自由生成不存在的目录。

## 9. 常用调参

在 `file_directory_predictor.py` 顶部可以调整：

```python
MAX_PDF_PAGES_FOR_VLM = 3
MAX_TEXT_CHARS = 6000
CLI_TIMEOUT = 180
```

| 参数 | 含义 |
| --- | --- |
| `MAX_PDF_PAGES_FOR_VLM` | PDF 前多少页送入视觉模型 |
| `MAX_TEXT_CHARS` | 文本模型最多接收的字符数 |
| `CLI_TIMEOUT` | 单次模型调用超时时间，单位秒 |

## 10. 常见问题

### 10.1 一启动就报 `/home/z` 相关错误

脚本顶部保留了原始默认路径：

```python
PROJECT_ROOT = Path("/home/z/my-project")
```

建议运行时显式传入：

```bash
--catalog ./catalog-mapping.xlsx
```

如需长期使用，可把 `PROJECT_ROOT` 改为脚本所在目录。

### 10.2 提示编目规则不存在

确认文件存在：

```bash
ls catalog-mapping.xlsx
```

并显式传入：

```bash
python file_directory_predictor.py sample.pdf --catalog ./catalog-mapping.xlsx
```

### 10.3 LLM 或 VLM 无返回

检查 HTTP 环境变量是否完整：

```bash
AI_BASE_URL
AI_API_KEY
AI_MODEL
```

或检查专用变量：

```bash
AI_CHAT_BASE_URL / AI_CHAT_API_KEY / AI_CHAT_MODEL
AI_VISION_BASE_URL / AI_VISION_API_KEY / AI_VISION_MODEL
```

开启调试输出：

```bash
export AI_DEBUG=1
```

PowerShell:

```powershell
$env:AI_DEBUG = "1"
```

### 10.4 PDF 识别不准

扫描 PDF 可能没有可提取文本，脚本会把前几页交给视觉模型。可以调大：

```python
MAX_PDF_PAGES_FOR_VLM = 5
```

### 10.5 长文档关键信息不在开头

脚本默认只取前 `MAX_TEXT_CHARS` 个字符。可以调大：

```python
MAX_TEXT_CHARS = 12000
```

## 11. 测试报告

仓库包含一次全链路测试记录：

```text
test-reports/full-chain-input.txt
test-reports/full-chain-run.json
test-reports/full-chain-report.json
test-reports/full-chain-report.md
```

报告覆盖：

- 环境变量模型配置。
- 真实 HTTP 模型请求和响应。
- 文件内容提取。
- LLM 文本分析。
- 候选召回。
- 最终 JSON 输出。

## 12. 安全注意事项

- 不要提交真实 API key。
- 分享日志或报告前，确认 Authorization 已脱敏。
- 不要把敏感案件材料提交到公开仓库。

---

## English Version

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

The current batch mode does not recurse into subdirectories.

## 7. Output Fields

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

## 8. Internal Flow

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

`DirectoryPredictor._extract_keywords()` extracts keywords, and `CatalogIndex.search_candidates()` retrieves up to 25 candidates.

### 8.5 Candidate Selection

The model selects one candidate index. The code trusts `selected_index` first and writes back exact fields from the selected catalog row.

## 9. Tuning

Common constants:

```python
MAX_PDF_PAGES_FOR_VLM = 3
MAX_TEXT_CHARS = 6000
CLI_TIMEOUT = 180
```

| Constant | Meaning |
| --- | --- |
| `MAX_PDF_PAGES_FOR_VLM` | Number of PDF pages sent to the vision model |
| `MAX_TEXT_CHARS` | Maximum text characters sent to the LLM |
| `CLI_TIMEOUT` | Model-call timeout in seconds |

## 10. Troubleshooting

### 10.1 `/home/z` path error on startup

The script keeps the original default path:

```python
PROJECT_ROOT = Path("/home/z/my-project")
```

Pass the catalog explicitly:

```bash
--catalog ./catalog-mapping.xlsx
```

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

## 11. Test Reports

The repository includes an end-to-end run:

```text
test-reports/full-chain-input.txt
test-reports/full-chain-run.json
test-reports/full-chain-report.json
test-reports/full-chain-report.md
```

The report covers environment-based model configuration, real HTTP request/response records, text extraction, LLM analysis, candidate retrieval, and final JSON output.

## 12. Security Notes

- Do not commit real API keys.
- Mask Authorization headers before sharing logs.
- Do not commit sensitive case materials to a public repository.
