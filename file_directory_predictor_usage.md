# file_directory_predictor.py 使用说明

## 1. 脚本用途

`file_directory_predictor.py` 是一个法院卷宗文件目录推测工具。它读取待分类文件内容，结合视觉模型 VLM、文本语义模型 LLM 和 `catalog-mapping.xlsx` 编目规则表，推测文件应归属的目录路径。

最终输出的目录由以下字段拼接：

```text
案件类型 / 卷宗 / 二级目录 / 材料类别
```

例如：

```text
刑事一审案件编目规则 / 正卷 / 案件审判流程管理信息表、案件登记表 / 案件登记表
```

## 2. 支持的输入文件

脚本按扩展名选择内容提取方式：

| 文件类型 | 扩展名 | 处理方式 |
| --- | --- | --- |
| PDF | `.pdf` | 使用 PyMuPDF 提取文本，并把前 3 页渲染为图片交给 VLM |
| Word 新格式 | `.docx` | 使用 `python-docx` 提取段落和表格文本 |
| Word 老格式 | `.doc` | 先调用 `libreoffice --headless` 转为 `.docx`，再提取文本 |
| 图片 | `.png` `.jpg` `.jpeg` `.gif` `.webp` `.bmp` | 直接交给 VLM 做视觉分析和 OCR |
| 表格 | `.xlsx` `.xlsm` `.xls` | 使用 pandas 读取所有 sheet 的前 200 行 |
| 文本 | `.txt` `.csv` `.tsv` `.md` `.json` `.log` `.xml` `.html` `.htm` | 尝试用 `utf-8`、`gbk`、`gb18030`、`latin-1` 读取 |
| 其他 | 任意扩展名 | 兜底按文本读取 |

## 3. 运行前准备

### 3.1 Python 依赖

脚本直接依赖：

```bash
pip install pandas openpyxl pymupdf python-docx
```

如果要处理 `.doc` 文件，还需要系统安装 LibreOffice，并确保命令行可以访问：

```bash
libreoffice --version
```

### 3.2 模型 CLI 依赖

脚本通过外部命令调用模型：

```bash
z-ai chat
z-ai vision
```

运行前需要确认 `z-ai` 已安装、已登录或已配置可用凭据，并且以下命令能正常返回：

```bash
z-ai chat -p "测试"
z-ai vision -p "描述图片内容" -i /path/to/image.png
```

### 3.3 编目规则表

编目规则表必须是 Excel 文件，并至少包含以下列：

```text
case_type
volume
second_level_directory
constraint
material_category
catalog_name_example
```

当前目录下的 `catalog-mapping.xlsx` 已符合要求，共 3860 条规则。

### 3.4 重要：配置项目路径

脚本顶部写死了默认路径：

```python
PROJECT_ROOT = Path("/home/z/my-project")
DEFAULT_CATALOG = PROJECT_ROOT / "upload" / "6a54a3afc78fec0fe9e6aa28_catalog-mapping.xlsx"
TMP_DIR = PROJECT_ROOT / "scripts" / "_tmp_predict"
```

这会带来两个影响：

1. 如果本机没有 `/home/z/my-project` 或没有写权限，脚本导入阶段就会失败。
2. 默认编目表路径不是当前目录的 `catalog-mapping.xlsx`。

在当前目录使用时，建议先把 `PROJECT_ROOT` 改成当前项目路径，或至少保证 `TMP_DIR` 指向一个可写目录。运行命令时也建议显式传入 `--catalog ./catalog-mapping.xlsx`。

## 4. 单文件预测

基本命令：

```bash
python3 file_directory_predictor.py /path/to/待分类文件.pdf --catalog ./catalog-mapping.xlsx
```

输出内容包括：

```text
文件
类型
推测目录
编目示例
置信度
理由
VLM 视觉分析结果
LLM 语义分析结果
```

如果需要 JSON 输出：

```bash
python3 file_directory_predictor.py /path/to/待分类文件.pdf --catalog ./catalog-mapping.xlsx --json
```

JSON 中主要字段：

| 字段 | 含义 |
| --- | --- |
| `file_path` | 输入文件路径 |
| `file_type` | 提取器识别出的类型 |
| `predicted_case_type` | 推测案件类型 |
| `predicted_volume` | 推测卷宗，如正卷、副卷 |
| `predicted_second_level_directory` | 推测二级目录 |
| `predicted_material_category` | 推测材料类别 |
| `predicted_catalog_example` | 对应编目名称示例 |
| `confidence` | `high`、`medium` 或 `low` |
| `reasoning` | LLM 给出的匹配理由 |
| `vlm_analysis` | 视觉分析结果 |
| `llm_analysis` | 文本语义分析结果 |
| `matched_entries` | 命中的候选编目规则 |

## 5. 批量预测

处理某个目录下的所有一级文件：

```bash
python3 file_directory_predictor.py --batch /path/to/files --catalog ./catalog-mapping.xlsx
```

批量模式只遍历该目录下的直接文件，不递归子目录。

JSON 批量输出：

```bash
python3 file_directory_predictor.py --batch /path/to/files --catalog ./catalog-mapping.xlsx --json
```

注意：当前实现中批量 JSON 模式会在处理每个文件时打印单条 JSON，最后再打印汇总 JSON；如果要被其他程序稳定消费，建议后续把单条输出改为只写日志或只保留最终数组。

## 6. 内部工作流程

### 6.1 加载规则

`CatalogLoader` 使用 pandas 读取 Excel，把每行转成 `CatalogEntry`：

```text
case_type + volume + second_level_directory + constraint + material_category + catalog_name_example
```

`CatalogIndex.build()` 会建立：

```text
material_category -> CatalogEntry 列表
案件类型列表
材料类别列表
```

### 6.2 提取文件内容

`ContentExtractor.extract()` 根据扩展名返回 `FileContent`，包含：

```text
file_path
file_type
text
image_paths
page_count
extract_error
```

PDF 会同时产生文本和页面图片；图片文件只产生 `image_paths`，不做本地 OCR。

### 6.3 VLM 视觉分析

`VLMAnalyzer.analyze()` 对图片或 PDF 渲染页调用：

```bash
z-ai vision
```

要求模型返回 JSON：

```json
{
  "doc_type_guess": "文书类型",
  "volume_guess": "正卷/副卷/未知",
  "case_clues": "案件类型线索",
  "visual_features": "视觉特征",
  "ocr_text": "OCR 关键文字",
  "confidence": "high/medium/low"
}
```

没有图片时，VLM 分析会标记为不可用。

### 6.4 LLM 文本分析

`LLMAnalyzer.analyze_text()` 对提取文本调用：

```bash
z-ai chat
```

最多送入前 6000 个字符，要求返回 JSON：

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

没有文本时，LLM 文本分析会标记为不可用。

### 6.5 融合画像

`DirectoryPredictor._fuse()` 合并 VLM 和 LLM 结果，生成统一画像：

```text
doc_type
volume
case_clues
key_info
file_name
file_type
text_preview
confidence
```

如果 VLM 和 LLM 都高置信，融合置信度会更高；如果只有一路可用，置信度通常较低。

### 6.6 两阶段匹配编目

第一阶段：本地关键词检索。

`_extract_keywords()` 从文书类型、案件线索、关键信息和文件名提取最多 40 个关键词。`CatalogIndex.search_candidates()` 在规则表中匹配关键词，返回最多 25 条候选规则。

第二阶段：LLM 精选。

脚本把文件画像和候选规则交给 `z-ai chat -t`，要求模型从候选编号中选择最匹配的一条。解析结果时优先相信 `selected_index`，然后用候选规则反写案件类型、卷宗、二级目录、材料类别和编目示例，避免模型自由生成不存在的规则字段。

## 7. 常见问题

### 7.1 一启动就报 `/home/z` 相关错误

原因是 `PROJECT_ROOT` 写死为 `/home/z/my-project`，脚本会在导入阶段创建 `TMP_DIR`。

处理方式：

```python
PROJECT_ROOT = Path("/Users/mooye/Desktop/AI")
DEFAULT_CATALOG = PROJECT_ROOT / "catalog-mapping.xlsx"
TMP_DIR = PROJECT_ROOT / "_tmp_predict"
```

或改成其他实际存在且可写的目录。

### 7.2 提示编目规则文件不存在

显式传入当前目录的规则表：

```bash
python3 file_directory_predictor.py sample.pdf --catalog ./catalog-mapping.xlsx
```

### 7.3 VLM 或 LLM 显示无返回

检查：

```bash
which z-ai
z-ai chat -p "测试"
z-ai vision -p "描述图片" -i /path/to/image.png
```

也要确认模型 CLI 的鉴权、网络和超时时间是否正常。脚本默认每次 CLI 调用超时为 180 秒。

### 7.4 PDF 没有文本或识别不准

扫描 PDF 可能没有可提取文本。脚本会把前 3 页渲染为图片交给 VLM 做 OCR，但只看前 3 页。如果关键信息在后续页，需要调整：

```python
MAX_PDF_PAGES_FOR_VLM = 3
```

### 7.5 大文件内容太长

LLM 文本分析只取前 6000 个字符：

```python
MAX_TEXT_CHARS = 6000
```

如果文件开头不是关键内容，可以考虑增加该值或在提取阶段做更有针对性的摘要。

## 8. 推荐命令

当前目录下建议先修正 `PROJECT_ROOT`、`DEFAULT_CATALOG` 和 `TMP_DIR`，然后使用：

```bash
python3 file_directory_predictor.py ./待分类文件.pdf --catalog ./catalog-mapping.xlsx
```

机器可读输出：

```bash
python3 file_directory_predictor.py ./待分类文件.pdf --catalog ./catalog-mapping.xlsx --json
```

批量处理：

```bash
python3 file_directory_predictor.py --batch ./待分类目录 --catalog ./catalog-mapping.xlsx --json
```

## 9. 本次检查结论

本次已完成 codegraph 初始化，索引结果为：

```text
Files indexed: 1
Total nodes: 62
Total edges: 113
Language: python
```

同时确认 `catalog-mapping.xlsx` 可读取，列名符合脚本要求，共 3860 条规则。

`python3 -m py_compile file_directory_predictor.py` 语法检查通过。

`python3 file_directory_predictor.py --help` 在当前环境失败，原因不是 argparse，而是脚本导入阶段创建硬编码临时目录 `/home/z/my-project/scripts/_tmp_predict` 失败。修正路径后再运行即可。
