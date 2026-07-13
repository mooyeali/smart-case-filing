# 通过环境变量自定义模型服务的设计方案

## 背景

当前 `file_directory_predictor.py` 的模型调用集中在两个函数：

- `_run_zai_chat()`：调用 `z-ai chat`，用于文本语义分析和编目候选精选。
- `_run_zai_vision()`：调用 `z-ai vision`，用于图片/PDF 渲染页的视觉分析和 OCR。

旧方案只考虑给 `z-ai` CLI 增加模型名参数。这不满足实际目标，因为它仍然被 `z-ai` 的供应商和模型集合限制，不能自由指定 `base_url`、`api_key`、`model`。

新的目标是把这两个函数改造成模型调用适配层：通过环境变量读取 OpenAI-compatible API 的 `base_url`、`api_key` 和 `model`，从而可以接入 OpenAI、智谱、DeepSeek、通义、硅基流动、本地 vLLM/Ollama 兼容网关等服务。

## 目标

1. 支持通过环境变量配置 `base_url`、`api_key`、`model` 三个核心参数。
2. 文本模型和视觉模型可以分别配置，避免把同一个模型强行用于不同任务。
3. 不再依赖 `z-ai` CLI 的模型选择能力。
4. 保持调用入口集中在 `_run_zai_chat()` 和 `_run_zai_vision()`，不把 provider 细节扩散到 `LLMAnalyzer`、`VLMAnalyzer`、`DirectoryPredictor`。
5. 尽量保持现有返回格式不变：两个函数仍返回模型回复的文本内容，调用方无需感知底层改造。
6. 设计上允许保留 `z-ai` 作为 fallback，但自定义模型路径应优先使用 OpenAI-compatible HTTP API。

## 非目标

1. 不在本次设计中重写文件提取、编目匹配、prompt 或 JSON 解析逻辑。
2. 不强绑定某一家厂商 SDK。
3. 不把 API key 写入代码或配置文件。
4. 不在代码里维护模型白名单。

## 推荐环境变量

通用默认值：

| 环境变量 | 用途 | 示例 |
| --- | --- | --- |
| `AI_BASE_URL` | 默认 OpenAI-compatible API base URL | `https://api.openai.com/v1` |
| `AI_API_KEY` | 默认 API key | `sk-...` |
| `AI_MODEL` | 默认模型名 | `gpt-4.1` |

文本模型覆盖：

| 环境变量 | 用途 | 示例 |
| --- | --- | --- |
| `AI_CHAT_BASE_URL` | 文本模型专用 base URL | `https://api.deepseek.com/v1` |
| `AI_CHAT_API_KEY` | 文本模型专用 API key | `sk-...` |
| `AI_CHAT_MODEL` | 文本模型名 | `deepseek-chat` |

视觉模型覆盖：

| 环境变量 | 用途 | 示例 |
| --- | --- | --- |
| `AI_VISION_BASE_URL` | 视觉模型专用 base URL | `https://api.openai.com/v1` |
| `AI_VISION_API_KEY` | 视觉模型专用 API key | `sk-...` |
| `AI_VISION_MODEL` | 视觉模型名 | `gpt-4.1` |

读取优先级：

```text
chat base_url = AI_CHAT_BASE_URL or AI_BASE_URL
chat api_key  = AI_CHAT_API_KEY  or AI_API_KEY
chat model    = AI_CHAT_MODEL    or AI_MODEL

vision base_url = AI_VISION_BASE_URL or AI_BASE_URL
vision api_key  = AI_VISION_API_KEY  or AI_API_KEY
vision model    = AI_VISION_MODEL    or AI_MODEL
```

## API 约定

采用 OpenAI-compatible Chat Completions 接口：

```text
POST {base_url}/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json
```

文本请求 body：

```json
{
  "model": "模型名",
  "messages": [
    {"role": "system", "content": "system prompt"},
    {"role": "user", "content": "user prompt"}
  ]
}
```

视觉请求 body：

```json
{
  "model": "视觉模型名",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "prompt"},
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,..."
          }
        }
      ]
    }
  ]
}
```

返回解析沿用 OpenAI-compatible 格式：

```text
choices[0].message.content
```

## 实现方案

建议新增两个内部辅助函数：

```python
def _get_model_config(kind: str) -> dict:
    ...
```

职责：

1. `kind == "chat"` 时读取 `AI_CHAT_*`，再回退到 `AI_*`。
2. `kind == "vision"` 时读取 `AI_VISION_*`，再回退到 `AI_*`。
3. 返回 `{base_url, api_key, model}`。
4. 去掉末尾 `/`，避免拼接 URL 时出现双斜杠。

```python
def _run_openai_compatible_chat(prompt: str, system: str | None, config: dict, timeout: int) -> str:
    ...
```

职责：

1. 构造 `/chat/completions` 请求。
2. 发送 HTTP 请求。
3. 解析 `choices[0].message.content`。
4. 失败时返回空字符串，保持现有调用方行为。

视觉可以复用同一 HTTP helper，只是 messages content 构造不同。

## 对 `_run_zai_chat()` 的改造

推荐保留函数名，降低调用方改动：

```python
def _run_zai_chat(prompt: str, system: Optional[str] = None,
                  thinking: bool = False, timeout: int = CLI_TIMEOUT) -> str:
    config = _get_model_config("chat")
    if config["base_url"] and config["api_key"] and config["model"]:
        return _run_openai_compatible_chat(prompt, system, config, timeout)
    return _run_zai_chat_cli(prompt, system, thinking, timeout)
```

说明：

1. 函数名可以暂时不改，因为外部调用方只依赖其返回文本。
2. 当三件套完整时，优先走自定义 HTTP 模型。
3. 当三件套不完整时，是否 fallback 到旧 `z-ai` CLI 作为兼容路径，由审阅决定。

## 对 `_run_zai_vision()` 的改造

推荐同样保留函数名：

```python
def _run_zai_vision(prompt: str, image_paths: list, thinking: bool = False,
                    timeout: int = CLI_TIMEOUT) -> str:
    config = _get_model_config("vision")
    if config["base_url"] and config["api_key"] and config["model"]:
        return _run_openai_compatible_vision(prompt, image_paths, config, timeout)
    return _run_zai_vision_cli(prompt, image_paths, thinking, timeout)
```

视觉请求应复用现有 `_image_to_base64()` 或直接把图片编码为 data URI。当前文件已有 `_image_to_base64(path: Path) -> str`，适合直接复用。

## 依赖选择

有两个可选方向：

### 方案 A：使用标准库 `urllib.request`

优点：

1. 不新增 pip 依赖。
2. 适合当前单文件脚本。
3. 便于在受限环境中运行。

缺点：

1. 代码略啰嗦。
2. 错误处理和超时写法不如 `requests` 直观。

### 方案 B：使用 `requests`

优点：

1. 代码更短，更容易读。
2. HTTP 错误处理更自然。

缺点：

1. 需要新增依赖。
2. 使用说明需要补充安装命令。

推荐方案 A：当前脚本已经是单文件工具，优先不增加依赖。

## `thinking` 参数处理

当前 `thinking=True` 只对 `z-ai` CLI 有意义。OpenAI-compatible API 不存在统一的 `thinking` 参数。

推荐行为：

1. HTTP 自定义模型路径忽略 `thinking` 参数。
2. 不把 `thinking` 自动转换成厂商私有字段。
3. 如后续需要支持 reasoning，可另行设计 `AI_EXTRA_BODY_JSON` 或特定 provider adapter。

## 错误处理

为了保持兼容，HTTP 调用失败时仍返回空字符串，调用方会得到现有的“LLM 无返回”或“VLM 无返回”结果。

建议同时加一个可选调试开关：

| 环境变量 | 用途 |
| --- | --- |
| `AI_DEBUG` | 设置为 `1` 时，把 HTTP 状态码和错误摘要输出到 stderr |

不要输出 `api_key`。

## 示例配置

PowerShell：

```powershell
$env:AI_BASE_URL = "https://api.openai.com/v1"
$env:AI_API_KEY = "sk-..."
$env:AI_CHAT_MODEL = "gpt-4.1"
$env:AI_VISION_MODEL = "gpt-4.1"
python .\file_directory_predictor.py .\sample.pdf --catalog .\catalog-mapping.xlsx
```

DeepSeek 文本 + OpenAI 视觉：

```powershell
$env:AI_CHAT_BASE_URL = "https://api.deepseek.com/v1"
$env:AI_CHAT_API_KEY = "sk-..."
$env:AI_CHAT_MODEL = "deepseek-chat"

$env:AI_VISION_BASE_URL = "https://api.openai.com/v1"
$env:AI_VISION_API_KEY = "sk-..."
$env:AI_VISION_MODEL = "gpt-4.1"
```

本地兼容服务：

```powershell
$env:AI_BASE_URL = "http://localhost:8000/v1"
$env:AI_API_KEY = "local-key"
$env:AI_MODEL = "qwen2.5-vl"
```

## 测试建议

不需要真实 API key 的测试：

1. `_get_model_config("chat")` 能正确读取 `AI_CHAT_*` 并回退到 `AI_*`。
2. `_get_model_config("vision")` 能正确读取 `AI_VISION_*` 并回退到 `AI_*`。
3. base URL 末尾 `/` 会被规范化。
4. 未配置三件套时走旧 `z-ai` CLI fallback，或按审阅决定直接返回空字符串。

需要 mock HTTP 的测试：

1. 文本请求 body 符合 `/chat/completions` 格式。
2. 视觉请求 body 包含 text 和 image_url data URI。
3. 成功响应能解析 `choices[0].message.content`。
4. HTTP 失败、JSON 格式异常、缺少 choices 时返回空字符串。

端到端验证：

```powershell
$env:AI_BASE_URL = "..."
$env:AI_API_KEY = "..."
$env:AI_CHAT_MODEL = "..."
$env:AI_VISION_MODEL = "..."
python .\file_directory_predictor.py .\sample.pdf --catalog .\catalog-mapping.xlsx --json
```

## 审阅决策点

实施前需要确认：

1. 是否接受 OpenAI-compatible `/chat/completions` 作为统一接入协议。
2. 是否保留旧 `z-ai` CLI 作为未配置环境变量时的 fallback。
3. 是否采用标准库 `urllib.request`，避免新增依赖。
4. 是否同步更新 `file_directory_predictor_usage.md` 中的模型配置说明。
5. 是否保留 `_run_zai_chat()` / `_run_zai_vision()` 函数名，还是重命名为更中性的 `_run_chat_model()` / `_run_vision_model()`。

推荐决策：

1. 采用 OpenAI-compatible HTTP API。
2. 保留旧 `z-ai` fallback，避免破坏已有用法。
3. 使用标准库 `urllib.request` 实现，不新增依赖。
4. 本轮只改两个模型调用封装及必要 helper，不触碰上层业务流程。
5. 同步更新使用说明。
