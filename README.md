# Smart Case Filing

> 中文为默认文档语言。English version follows the Chinese version.

## 中文版

Smart Case Filing 是一个面向法院卷宗材料的智能目录推测工具。它读取待归档文件内容，结合文本模型、视觉模型和 `catalog-mapping.xlsx` 编目规则表，推测文件应归属的案件类型、卷宗、二级目录和材料类别。

当前实现以单文件 Python 脚本为核心，适合本地批处理、规则验证、模型接入验证和后续系统集成前的原型验证。

### 核心能力

- 支持 PDF、Word、图片、表格和纯文本文件。
- PDF 会提取文本，并把前几页渲染为图片供视觉模型分析。
- 图片文件会交给视觉模型进行版式识别和 OCR。
- 文本内容会交给语义模型判断文书类型、案件线索和关键短语。
- 本地从编目规则表中召回候选目录，再由模型精选最匹配条目。
- 支持 OpenAI-compatible HTTP API，可通过环境变量自定义 `base_url`、`api_key` 和 `model`。
- 未配置 HTTP 模型三件套时，保留旧的 `z-ai` CLI fallback。

### 工作流程

```text
输入文件
  -> ContentExtractor 提取文本/图片
  -> VLMAnalyzer 分析视觉材料和 OCR
  -> LLMAnalyzer 分析文本语义画像
  -> CatalogIndex 本地召回候选编目规则
  -> DirectoryPredictor 调用模型精选候选
  -> 输出预测目录和分析结果
```

最终目录由以下字段拼接：

```text
案件类型 / 卷宗 / 二级目录 / 材料类别
```

### 支持的文件类型

| 类型 | 扩展名 | 处理方式 |
| --- | --- | --- |
| PDF | `.pdf` | PyMuPDF 提取文本，并渲染前 N 页供视觉模型分析 |
| Word 新格式 | `.docx` | `python-docx` 提取段落和表格文本 |
| Word 老格式 | `.doc` | 通过 LibreOffice 转换为 `.docx` 后提取 |
| 图片 | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` | 交给视觉模型识别和 OCR |
| 表格 | `.xlsx` `.xlsm` `.xls` | pandas 读取所有 sheet 的前 200 行 |
| 文本 | `.txt` `.csv` `.tsv` `.md` `.json` `.log` `.xml` `.html` `.htm` | 尝试多编码读取 |
| 其他 | 任意扩展名 | 兜底按文本读取 |

### 快速开始

安装 Python 依赖：

```bash
pip install pandas openpyxl pymupdf python-docx requests
```

如果需要处理 `.doc` 文件，还需要安装 LibreOffice，并确认命令可用：

```bash
libreoffice --version
```

配置模型服务。推荐使用 OpenAI-compatible HTTP API：

```bash
export AI_BASE_URL="https://api.openai.com/v1"
export AI_API_KEY="sk-..."
export AI_MODEL="gpt-4.1"
```

PowerShell：

```powershell
$env:AI_BASE_URL = "https://api.openai.com/v1"
$env:AI_API_KEY = "sk-..."
$env:AI_MODEL = "gpt-4.1"
```

运行单文件预测：

```bash
python file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx --json
```

批量处理目录：

```bash
python file_directory_predictor.py --batch ./input-files --catalog ./catalog-mapping.xlsx --json
```

### 模型配置

通用环境变量：

| 环境变量 | 含义 |
| --- | --- |
| `AI_BASE_URL` | OpenAI-compatible API 地址，例如 `https://api.openai.com/v1` |
| `AI_API_KEY` | API key |
| `AI_MODEL` | 默认模型名 |

文本模型覆盖：

| 环境变量 | 含义 |
| --- | --- |
| `AI_CHAT_BASE_URL` | 文本模型专用 API 地址 |
| `AI_CHAT_API_KEY` | 文本模型专用 API key |
| `AI_CHAT_MODEL` | 文本模型名 |

视觉模型覆盖：

| 环境变量 | 含义 |
| --- | --- |
| `AI_VISION_BASE_URL` | 视觉模型专用 API 地址 |
| `AI_VISION_API_KEY` | 视觉模型专用 API key |
| `AI_VISION_MODEL` | 视觉模型名 |

读取优先级：

```text
chat   : AI_CHAT_*   -> AI_*
vision : AI_VISION_* -> AI_*
```

如果没有配置完整的 `base_url`、`api_key`、`model` 三件套，脚本会回退到旧的 `z-ai` CLI：

```bash
z-ai chat
z-ai vision
```

### 编目规则表

`catalog-mapping.xlsx` 至少需要包含以下列：

```text
case_type
volume
second_level_directory
constraint
material_category
catalog_name_example
```

当前仓库中的规则表用于本地候选召回。模型最终只能从召回出的候选编号中选择；代码会优先用 `selected_index` 反写规则表字段，避免模型自由编造不存在的目录字段。

### 重要路径配置

当前脚本顶部仍保留原始默认路径：

```python
PROJECT_ROOT = Path("/home/z/my-project")
DEFAULT_CATALOG = PROJECT_ROOT / "upload" / "6a54a3afc78fec0fe9e6aa28_catalog-mapping.xlsx"
TMP_DIR = PROJECT_ROOT / "scripts" / "_tmp_predict"
```

在本仓库目录使用时，建议运行命令时显式传入：

```bash
--catalog ./catalog-mapping.xlsx
```

如需长期使用，建议后续把 `PROJECT_ROOT` 调整为基于脚本所在目录的动态路径。

### 仓库结构

```text
.
├── file_directory_predictor.py          # 主程序
├── catalog-mapping.xlsx                 # 编目规则表
├── file_directory_predictor_usage.md    # 使用文档，中英双语
├── docs/
│   └── model-env-config-design.md       # 模型环境变量配置设计文档
└── test-reports/
    ├── full-chain-input.txt             # 全链路测试输入
    ├── full-chain-run.json              # 原始运行记录
    ├── full-chain-report.json           # JSON 测试报告
    └── full-chain-report.md             # Markdown 测试报告
```

### 验证记录

本项目已完成一次 OpenAI-compatible 模型配置全链路测试，报告位于：

- `test-reports/full-chain-report.md`
- `test-reports/full-chain-report.json`
- `test-reports/full-chain-run.json`

测试覆盖：

- 环境变量模型配置。
- 文件内容提取。
- 文本语义分析。
- 本地候选召回。
- 模型精选候选。
- JSON 输出。

### 安全说明

- 不要把真实 API key 写入代码、文档或提交记录。
- 测试报告中展示的 Authorization 已脱敏。
- 如果需要共享运行记录，请先确认没有包含未脱敏密钥或敏感案件材料。

### 已知限制

- 候选召回依赖关键词匹配，召回质量会影响最终目录。
- 文本分析默认只取前 `MAX_TEXT_CHARS` 个字符。
- PDF 视觉分析默认只渲染前 `MAX_PDF_PAGES_FOR_VLM` 页。
- OpenAI-compatible 视觉请求采用 `image_url` data URI 格式，目标服务需要支持该格式。
- `.doc` 文件依赖系统 LibreOffice。

### 许可证

当前仓库未声明开源许可证。发布或商用前应补充明确许可证。

---

## English Version

Smart Case Filing is an intelligent directory prediction tool for court case filing materials. It reads an input document, combines text-model analysis, vision-model analysis, and the `catalog-mapping.xlsx` catalog rules, then predicts the case type, volume, second-level directory, and material category.

The current implementation is a single-file Python tool suitable for local batch processing, catalog-rule validation, model-integration testing, and prototyping before system integration.

### Key Features

- Supports PDF, Word, images, spreadsheets, and text files.
- Extracts text from PDFs and renders the first pages for vision-model analysis.
- Sends image files to the vision model for layout recognition and OCR.
- Sends extracted text to the language model for document-type and case-clue analysis.
- Retrieves local candidate catalog rules, then asks the model to select the best candidate.
- Supports OpenAI-compatible HTTP APIs through environment variables for `base_url`, `api_key`, and `model`.
- Falls back to the legacy `z-ai` CLI when the HTTP model configuration is incomplete.

### Workflow

```text
Input file
  -> ContentExtractor extracts text/images
  -> VLMAnalyzer analyzes visual materials and OCR
  -> LLMAnalyzer builds a text semantic profile
  -> CatalogIndex retrieves candidate catalog rules locally
  -> DirectoryPredictor asks the model to select the best candidate
  -> Predicted directory and analysis result
```

The final predicted path is:

```text
case type / volume / second-level directory / material category
```

### Supported File Types

| Type | Extensions | Processing |
| --- | --- | --- |
| PDF | `.pdf` | Extract text with PyMuPDF and render the first N pages for vision analysis |
| Word | `.docx` | Extract paragraphs and table text with `python-docx` |
| Legacy Word | `.doc` | Convert to `.docx` with LibreOffice, then extract text |
| Image | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` | Send to the vision model for recognition and OCR |
| Spreadsheet | `.xlsx` `.xlsm` `.xls` | Read the first 200 rows of all sheets with pandas |
| Text | `.txt` `.csv` `.tsv` `.md` `.json` `.log` `.xml` `.html` `.htm` | Try multiple encodings |
| Other | any extension | Fallback to text extraction |

### Quick Start

Install Python dependencies:

```bash
pip install pandas openpyxl pymupdf python-docx requests
```

Install LibreOffice if you need `.doc` support:

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

### Model Configuration

Generic variables:

| Variable | Meaning |
| --- | --- |
| `AI_BASE_URL` | OpenAI-compatible API base URL |
| `AI_API_KEY` | API key |
| `AI_MODEL` | Default model name |

Chat overrides:

| Variable | Meaning |
| --- | --- |
| `AI_CHAT_BASE_URL` | Chat-model base URL |
| `AI_CHAT_API_KEY` | Chat-model API key |
| `AI_CHAT_MODEL` | Chat-model name |

Vision overrides:

| Variable | Meaning |
| --- | --- |
| `AI_VISION_BASE_URL` | Vision-model base URL |
| `AI_VISION_API_KEY` | Vision-model API key |
| `AI_VISION_MODEL` | Vision-model name |

Priority:

```text
chat   : AI_CHAT_*   -> AI_*
vision : AI_VISION_* -> AI_*
```

If `base_url`, `api_key`, and `model` are not fully configured, the script falls back to:

```bash
z-ai chat
z-ai vision
```

### Catalog Rules

`catalog-mapping.xlsx` must contain at least:

```text
case_type
volume
second_level_directory
constraint
material_category
catalog_name_example
```

The model is expected to select from locally retrieved candidate rules. The code trusts `selected_index` first and writes back the exact fields from the selected catalog entry to reduce hallucinated catalog fields.

### Important Path Note

The script still contains the original default paths:

```python
PROJECT_ROOT = Path("/home/z/my-project")
DEFAULT_CATALOG = PROJECT_ROOT / "upload" / "6a54a3afc78fec0fe9e6aa28_catalog-mapping.xlsx"
TMP_DIR = PROJECT_ROOT / "scripts" / "_tmp_predict"
```

When running from this repository, pass the catalog explicitly:

```bash
--catalog ./catalog-mapping.xlsx
```

For long-term use, consider changing `PROJECT_ROOT` to a dynamic path based on the script location.

### Repository Layout

```text
.
├── file_directory_predictor.py
├── catalog-mapping.xlsx
├── file_directory_predictor_usage.md
├── docs/
│   └── model-env-config-design.md
└── test-reports/
    ├── full-chain-input.txt
    ├── full-chain-run.json
    ├── full-chain-report.json
    └── full-chain-report.md
```

### Verification

An end-to-end OpenAI-compatible model test has been completed. Reports are available in `test-reports/`.

### Security Notes

- Do not commit real API keys.
- Authorization headers in test reports are masked.
- Review run records before sharing them externally.

### Known Limitations

- Candidate retrieval quality depends on keyword matching.
- Text analysis uses only the first `MAX_TEXT_CHARS` characters.
- PDF vision analysis renders only the first `MAX_PDF_PAGES_FOR_VLM` pages.
- Vision requests use `image_url` data URI payloads, which must be supported by the target service.
- `.doc` support requires LibreOffice.

### License

No open-source license has been declared yet. Add a license before public release or commercial use.
