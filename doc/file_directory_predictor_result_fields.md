# 文件目录推测结果参数对照说明

本文档说明 `file_directory_predictor.py --json` 输出结果中的字段含义。示例来源于程序运行结果，例如：

```json
{
  "file_path": "/Users/mooye/Desktop/test_material/input/(2026)鲁03民终1157号/送达地址确认书-栾志.pdf.pdf",
  "file_type": "pdf",
  "predicted_case_type": "民事二审案件编目规则",
  "predicted_volume": "正卷",
  "predicted_second_level_directory": "送达地址确认书、送达回证或其他送达凭证",
  "predicted_material_category": "送达地址确认书",
  "predicted_catalog_example": "送达地址确认书",
  "confidence": "high",
  "reasoning": "文件名为送达地址确认书，内容确认为当事人送达地址，完全匹配候选条目226的材料类别和二级目录。",
  "vlm_analysis": {
    "available": false,
    "reason": "VLM 无返回"
  },
  "llm_analysis": {
    "doc_type_guess": "送达地址确认书",
    "volume_guess": "正卷",
    "case_clues": "民事, 一审",
    "key_phrases": "送达地址确认书, 受送达人, 栾志, 电子送达方式, 线下送达方式, 后果告知",
    "summary": "当事人栾志向法院确认其电子及线下法律文书送达地址及联系方式的文书。",
    "confidence": "high",
    "available": true
  },
  "matched_entries": [
    {
      "case_type": "民事二审案件编目规则",
      "volume": "正卷",
      "second_level_directory": "送达地址确认书、送达回证或其他送达凭证",
      "constraint": "必选",
      "material_category": "送达地址确认书",
      "catalog_name_example": "送达地址确认书"
    }
  ]
}
```

## 1. 顶层返回字段

| 参数名 | 参数名含义 | 返回值含义 |
| --- | --- | --- |
| `file_path` | 输入文件路径 | 当前被处理文件的完整路径。批量模式下，每个文件都会生成一条对应结果。 |
| `file_type` | 文件类型 | 内容提取器按扩展名识别出的类型。常见值包括 `pdf`、`docx`、`doc`、`image`、`spreadsheet`、`text`、`unknown`。 |
| `predicted_case_type` | 推测案件类型 | 最终匹配到的案件编目规则类型，例如 `民事二审案件编目规则`。为空字符串时表示未能得到可信匹配。 |
| `predicted_volume` | 推测卷宗 | 最终匹配到的卷宗类型，例如 `正卷`、`副卷`。为空字符串时表示未能匹配。 |
| `predicted_second_level_directory` | 推测二级目录 | 最终匹配到的二级目录名称，例如 `送达地址确认书、送达回证或其他送达凭证`。 |
| `predicted_material_category` | 推测材料类别 | 最终匹配到的材料类别，例如 `送达地址确认书`。如果编目规则该字段为空，或未匹配成功，则可能为空字符串。 |
| `predicted_catalog_example` | 编目名称示例 | 编目规则表中对应条目的示例名称，例如 `送达地址确认书`。用于提示最终落目录时可采用的编目名称样式。 |
| `confidence` | 最终匹配置信度 | 模型或解析逻辑给出的匹配置信度。常见值为 `high`、`medium`、`low`。`low` 通常表示匹配弱、模型无返回或解析失败。 |
| `reasoning` | 匹配理由 | 模型选择该编目条目的简要原因。若值为 `LLM 匹配无返回`，表示候选精选阶段没有拿到可用模型返回。 |
| `vlm_analysis` | 视觉模型分析结果 | VLM 对图片或 PDF 渲染页的分析画像。详见“视觉模型分析字段”。 |
| `llm_analysis` | 文本模型分析结果 | LLM 对文件提取文本的语义分析画像。详见“文本模型分析字段”。 |
| `matched_entries` | 命中的编目规则列表 | 程序最终确认命中的编目规则。通常包含 1 条；字段回退匹配时可能包含多条；未匹配时为空数组。 |

## 2. 视觉模型分析字段：`vlm_analysis`

`vlm_analysis` 来自视觉模型，输入通常是图片文件或 PDF 渲染后的页面图片。

| 参数名 | 参数名含义 | 返回值含义 |
| --- | --- | --- |
| `available` | 视觉分析是否可用 | `true` 表示 VLM 返回并解析出结构化结果；`false` 表示未进行视觉分析或模型无可用返回。 |
| `reason` | 视觉分析不可用原因 | 当 `available=false` 时出现。常见值包括 `无可分析图像`、`VLM 无返回`。 |
| `doc_type_guess` | 视觉推测文书类型 | VLM 根据版式、标题、印章、OCR 内容推测的文书类型，例如 `送达回证`、`判决书`、`电子送达确认书`。 |
| `volume_guess` | 视觉推测卷宗 | VLM 根据材料性质推测的卷宗，例如 `正卷`、`副卷`、`未知`。 |
| `case_clues` | 视觉案件线索 | VLM 从图片文字或版式中识别出的案件类型、案由、审级等线索，例如 `民事 / 离婚纠纷`。 |
| `visual_features` | 视觉特征描述 | VLM 识别出的版式与外观特征，例如 `红色公章/表格/印刷体/送达成功记录`。 |
| `ocr_text` | 视觉 OCR 文本 | VLM 从图片或 PDF 渲染页中识别出的关键文字。通常截取为关键内容，不一定是全文。 |
| `confidence` | 视觉分析置信度 | VLM 对自身识别结果的置信度，常见值为 `high`、`medium`、`low`。 |

### `vlm_analysis.available=false` 的常见含义

| 返回值 | 含义 |
| --- | --- |
| `reason="无可分析图像"` | 当前文件没有可供 VLM 分析的图片。例如纯文本、普通 `.doc` 文档、未渲染出图片的文件。 |
| `reason="VLM 无返回"` | 已尝试调用视觉模型，但模型接口没有返回可用内容。可能原因包括接口错误、服务端过载、网络中断、图片格式无法识别等。 |

## 3. 文本模型分析字段：`llm_analysis`

`llm_analysis` 来自文本模型，输入是内容提取器从文件中提取的文本。

| 参数名 | 参数名含义 | 返回值含义 |
| --- | --- | --- |
| `available` | 文本分析是否可用 | `true` 表示 LLM 返回并解析出结构化结果；`false` 表示没有可分析文本或模型无可用返回。 |
| `reason` | 文本分析不可用原因 | 当 `available=false` 时出现。常见值包括 `无文本可分析`、`LLM 无返回`。 |
| `doc_type_guess` | 文本推测文书类型 | LLM 根据提取文本推测的文书类型，例如 `送达地址确认书`、`民事判决书`、`上诉状`。 |
| `volume_guess` | 文本推测卷宗 | LLM 根据文本内容推测的卷宗，例如 `正卷`、`副卷`、`未知`。 |
| `case_clues` | 文本案件线索 | LLM 从文本中提取的案件类型、案由、审级等线索，例如 `民事, 一审`。 |
| `key_phrases` | 关键短语 | LLM 识别出的能够体现文书性质的关键词或短语，例如 `送达地址确认书, 受送达人, 电子送达方式`。 |
| `summary` | 内容摘要 | LLM 对该文件内容的一句话概括。 |
| `confidence` | 文本分析置信度 | LLM 对语义分析结果的置信度，常见值为 `high`、`medium`、`low`。 |

### `llm_analysis.available=false` 的常见含义

| 返回值 | 含义 |
| --- | --- |
| `reason="无文本可分析"` | 内容提取器没有提取到文本。例如图片文件默认不做本地 OCR，或 `.doc` 转换失败导致文本为空。 |
| `reason="LLM 无返回"` | 已尝试调用文本模型，但模型接口没有返回可用内容。可能原因包括接口错误、服务端过载、网络中断或超时。 |

## 4. 命中编目规则字段：`matched_entries[]`

`matched_entries` 是数组，每一项对应一条编目规则表中的规则。

| 参数名 | 参数名含义 | 返回值含义 |
| --- | --- | --- |
| `case_type` | 案件类型 | 编目规则表中的案件类型，例如 `民事二审案件编目规则`。通常与顶层 `predicted_case_type` 一致。 |
| `volume` | 卷宗 | 编目规则表中的卷宗字段，例如 `正卷`、`副卷`。通常与顶层 `predicted_volume` 一致。 |
| `second_level_directory` | 二级目录 | 编目规则表中的二级目录字段，例如 `送达地址确认书、送达回证或其他送达凭证`。 |
| `constraint` | 规则约束 | 编目规则表中的约束字段，例如 `必选`。用于表示该材料在对应目录中的规则属性。 |
| `material_category` | 材料类别 | 编目规则表中的材料类别字段，例如 `送达地址确认书`。通常与顶层 `predicted_material_category` 一致。 |
| `catalog_name_example` | 编目名称示例 | 编目规则表中的示例字段，例如 `送达地址确认书`。通常与顶层 `predicted_catalog_example` 一致。 |

## 5. 顶层字段与命中规则字段的关系

顶层 `predicted_*` 字段是程序最终对外展示的单条预测结果。`matched_entries` 是该预测结果对应的编目规则来源。

通常关系如下：

| 顶层字段 | 对应的命中规则字段 |
| --- | --- |
| `predicted_case_type` | `matched_entries[0].case_type` |
| `predicted_volume` | `matched_entries[0].volume` |
| `predicted_second_level_directory` | `matched_entries[0].second_level_directory` |
| `predicted_material_category` | `matched_entries[0].material_category` |
| `predicted_catalog_example` | `matched_entries[0].catalog_name_example` |

如果 `matched_entries` 为空数组，说明程序没有成功确认可用编目规则；此时顶层预测字段通常为空字符串，`confidence` 多为 `low`。

## 6. 置信度取值说明

| 取值 | 含义 |
| --- | --- |
| `high` | 高置信度。文件名、文本、视觉特征或候选规则匹配较明确。 |
| `medium` | 中等置信度。存在部分有效线索，但仍需人工复核。 |
| `low` | 低置信度。模型无返回、解析失败、候选不匹配或证据不足。 |

## 7. 示例结果解读

对示例中的 `送达地址确认书-栾志.pdf.pdf`：

- `file_type=pdf`：程序按 PDF 文件处理。
- `predicted_case_type=民事二审案件编目规则`：最终认为该文件属于民事二审编目规则。
- `predicted_second_level_directory=送达地址确认书、送达回证或其他送达凭证`：最终归入该二级目录。
- `predicted_material_category=送达地址确认书`：材料类别为送达地址确认书。
- `vlm_analysis.available=false` 且 `reason=VLM 无返回`：视觉模型没有返回可用结果。
- `llm_analysis.available=true`：文本模型成功分析了 PDF 提取文本。
- `matched_entries[0]`：表示最终命中的编目规则表条目，顶层预测字段主要从该条规则回写得到。
