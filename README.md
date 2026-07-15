# 卷宗智能推理编目

[English](README.en.md)

Smart Case Filing 是一个面向法院电子卷宗材料的智能目录推测工具。它读取 PDF、Word、图片、表格和文本文件，结合本地编目规则表、文本模型与视觉模型，推测材料应归入的案件类型、卷宗、二级目录和材料类别。

当前项目以单文件 Python 脚本为核心，适合本地批处理、编目规则验证、模型接入验证，以及接入业务系统前的原型验证。

## 核心能力

- 支持 PDF、Word、图片、表格、纯文本和常见结构化文本文件。
- PDF 会提取文本，并可渲染前若干页供视觉模型分析。
- 图片会发送给视觉模型进行版式识别和 OCR 线索提取。
- 文本内容会发送给语义模型，生成文书类型、案件线索、关键词和摘要。
- 本地基于 `catalog-mapping.xlsx` 召回候选编目规则，再由模型从候选中选择最终条目。
- 支持 OpenAI-compatible HTTP API，通过环境变量配置 `base_url`、`api_key` 和 `model`。
- 未配置完整 HTTP 模型参数时，保留 `z-ai` CLI fallback。
- 支持把标准输出和日志分别保存到文件，便于归档和复核。
- 可验收批量智能体模式支持执行轨迹、run manifest、低置信复核、partial resume、retry CLI、模型配置预检、人工复核决定记录和 run 审计报告。

## 工作流程

```text
输入文件
  -> ContentExtractor 提取文本和图片
  -> VLMAnalyzer 分析视觉材料和 OCR 线索
  -> LLMAnalyzer 分析文本语义画像
  -> CatalogIndex 召回候选编目规则
  -> DirectoryPredictor 调用模型精选候选
  -> 输出预测目录和分析结果
```

预测目录由以下字段组成：

```text
案件类型 / 卷宗 / 二级目录 / 材料类别
```

## 支持的文件类型

| 类型 | 扩展名 | 处理方式 |
| --- | --- | --- |
| PDF | `.pdf` | 使用 PyMuPDF 提取文本，并渲染前 N 页供视觉模型分析 |
| Word 新格式 | `.docx` | 使用 `python-docx` 提取段落和表格文本 |
| Word 老格式 | `.doc` | 通过 LibreOffice 转换为 `.docx` 后提取 |
| 图片 | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` | 发送给视觉模型识别版式和 OCR |
| 表格 | `.xlsx` `.xlsm` `.xls` | 使用 pandas 读取所有 sheet 的前 200 行 |
| 文本 | `.txt` `.csv` `.tsv` `.md` `.json` `.log` `.xml` `.html` `.htm` | 尝试多编码读取 |
| 其他 | 任意扩展名 | 兜底按文本读取 |

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
```

如果只安装运行所需依赖，也可以使用：

```bash
pip install pandas openpyxl pymupdf python-docx requests
```

如需处理 `.doc` 文件，还需要安装 LibreOffice，并确认命令可用：

```bash
libreoffice --version
```

配置 OpenAI-compatible 模型服务：

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

保存结果和日志到指定文件：

```bash
python file_directory_predictor.py ./sample.pdf \
  --catalog ./catalog-mapping.xlsx \
  --json \
  --output ./logs/result.json \
  --log ./logs/run.log
```

未显式指定 `--output` 和 `--log` 时，程序会在脚本所在目录写入：

- `file_directory_predictor_output.txt`：原 stdout 内容。
- `file_directory_predictor.log`：原 stderr 内容。

## 模型配置

通用环境变量：

| 环境变量 | 含义 |
| --- | --- |
| `AI_BASE_URL` | OpenAI-compatible API 地址，例如 `https://api.openai.com/v1` |
| `AI_API_KEY` | API key |
| `AI_MODEL` | 默认模型名 |

文本模型专用覆盖：

| 环境变量 | 含义 |
| --- | --- |
| `AI_CHAT_BASE_URL` | 文本模型 API 地址 |
| `AI_CHAT_API_KEY` | 文本模型 API key |
| `AI_CHAT_MODEL` | 文本模型名 |

视觉模型专用覆盖：

| 环境变量 | 含义 |
| --- | --- |
| `AI_VISION_BASE_URL` | 视觉模型 API 地址 |
| `AI_VISION_API_KEY` | 视觉模型 API key |
| `AI_VISION_MODEL` | 视觉模型名 |

读取优先级：

```text
chat   : AI_CHAT_*   -> AI_*
vision : AI_VISION_* -> AI_*
```

调试模型调用失败原因时，可开启：

```bash
export AI_DEBUG=1
```

如果没有配置完整的 `base_url`、`api_key`、`model` 三件套，脚本会回退到：

```bash
z-ai chat
z-ai vision
```

## 编目规则表

`catalog-mapping.xlsx` 至少需要包含以下列：

```text
case_type
volume
second_level_directory
constraint
material_category
catalog_name_example
```

程序先从规则表中召回候选，再要求模型只能从候选编号中选择。最终结果优先根据 `selected_index` 回写规则表字段，减少模型自由编造目录的风险。

## 路径和运行输出

当前脚本默认配置位于 `file_directory_predictor.py` 顶部：

```python
PROJECT_ROOT = Path("/Users/mooye/python project/smart-case-filing")
PROGRAM_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG = PROJECT_ROOT / "catalog-mapping.xlsx"
TMP_DIR = PROJECT_ROOT / "scripts" / "_tmp_predict"
```

为了提升跨环境可移植性，建议在命令行显式传入 `--catalog`、`--output` 和 `--log`。如果要部署到其他机器，优先把这些路径改为基于脚本目录或部署配置生成。

## 仓库结构

```text
.
├── file_directory_predictor.py           # 主程序
├── catalog-mapping.xlsx                  # 编目规则表
├── README.md                             # 中文说明
├── README.en.md                          # English README
├── docs/
│   ├── 卷宗智能推理编目使用说明.md              # 中文使用说明
│   ├── Smart_Case_Filing_Usage.en.md     # English usage guide
│   └── 处理结果字段解释.md                 # 预测结果字段说明
├── logs/                                 # 运行日志和输出样例
├── offline_pkgs/                         # 离线依赖包
├── test-reports/                         # 全链路验证报告
└── tests/                                # 单元测试
```

## 结果字段说明

JSON 输出的主要字段包括：

- `file_path`、`file_type`：输入文件路径和识别类型。
- `predicted_case_type`、`predicted_volume`、`predicted_second_level_directory`、`predicted_material_category`：最终预测目录字段。
- `predicted_catalog_example`：命中规则中的编目名称示例。
- `confidence`、`reasoning`：置信度和选择理由。
- `vlm_analysis`：视觉模型分析结果。
- `llm_analysis`：文本模型分析结果。
- `matched_entries`：最终命中的编目规则。

更完整的字段解释见 [docs/处理结果字段解释.md](docs/处理结果字段解释.md)。

完整命令行使用说明见 [docs/卷宗智能推理编目使用说明.md](docs/卷宗智能推理编目使用说明.md)。

## 验证和测试

运行单元测试：

```bash
python -m unittest discover -s tests
```

运行语法检查：

```bash
python -m py_compile file_directory_predictor.py tests/test_catalog_index.py tests/test_cli_output.py
```

项目包含一次 OpenAI-compatible 模型配置全链路验证记录：

- [test-reports/full-chain-report.md](test-reports/full-chain-report.md)
- [test-reports/full-chain-report.json](test-reports/full-chain-report.json)
- [test-reports/full-chain-run.json](test-reports/full-chain-run.json)

## 安全说明

- 不要把真实 API key 写入代码、文档或提交记录。
- 共享日志和报告前，检查是否包含未脱敏密钥、Authorization header 或敏感案件材料。
- 测试报告中出现的 Authorization 信息应保持脱敏。

## 已知限制

- 候选召回依赖关键词和规则表质量，召回不足会影响最终预测。
- 文本分析默认只截取前 `MAX_TEXT_CHARS` 个字符。
- PDF 视觉分析默认只渲染前 `MAX_PDF_PAGES_FOR_VLM` 页。
- OpenAI-compatible 视觉请求使用 `image_url` data URI，目标服务需要支持该格式。
- `.doc` 文件依赖系统 LibreOffice。
- 当前默认路径仍带有本机项目路径，跨机器运行建议显式传参或改为动态配置。

## 许可证

本项目采用非商业许可。未经项目权利人另行书面授权，代码、文档、规则表和示例材料仅可用于学习、研究、评估、内部验证和非商业原型开发，不得用于营利性产品、商业交付、商业 SaaS 服务或其他商业场景。

完整条款见 [LICENSE.md](LICENSE.md)。如需商业使用、二次分发或集成到商业系统，请先取得项目权利人的书面授权。
