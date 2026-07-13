# 通过环境变量自定义模型的设计方案

## 背景

当前 `file_directory_predictor.py` 没有独立的模型配置文件，也没有在代码中显式指定模型名。所有模型请求都集中在两个函数里：

- `_run_zai_chat()`：调用 `z-ai chat`，用于文本语义分析和编目候选精选。
- `_run_zai_vision()`：调用 `z-ai vision`，用于图片/PDF 渲染页的视觉分析和 OCR。

因此，如果 `z-ai` CLI 支持通过命令行参数选择模型，那么只修改这两个函数即可让整个程序通过环境变量自定义文本模型和视觉模型。

当前环境尚未安装 `z-ai`，无法确认它实际支持的模型参数名。下面方案以 `--model` 作为默认设计假设，并把该外部契约列为实施前确认项。

## 目标

1. 支持通过环境变量分别配置文本模型和视觉模型。
2. 未配置环境变量时保持现有行为不变。
3. 只在两个模型调用封装函数中处理模型参数，避免把模型选择逻辑扩散到 `LLMAnalyzer`、`VLMAnalyzer` 或 `DirectoryPredictor`。
4. 对短 prompt 分支和长 prompt 分支保持一致行为。
5. 让配置方式易于排查，避免静默使用错误参数。

## 非目标

1. 不更换 `z-ai` CLI 为其他 SDK。
2. 不重构整体调用流程。
3. 不在本次设计中引入 `.env` 文件自动加载。
4. 不改变 prompt、JSON 解析、编目匹配逻辑。

## 推荐环境变量

| 环境变量 | 用途 | 示例 |
| --- | --- | --- |
| `ZAI_CHAT_MODEL` | `z-ai chat` 使用的模型名 | `glm-4.5` |
| `ZAI_VISION_MODEL` | `z-ai vision` 使用的模型名 | `glm-4.5v` |
| `ZAI_MODEL_ARG` | 模型参数名，默认 `--model` | `--model` |

可选扩展：

| 环境变量 | 用途 | 示例 |
| --- | --- | --- |
| `ZAI_CHAT_MODEL_ARG` | 覆盖文本模型参数名 | `--model` |
| `ZAI_VISION_MODEL_ARG` | 覆盖视觉模型参数名 | `--model` |

推荐优先实现前三个变量。只有在确认 `z-ai chat` 和 `z-ai vision` 使用不同参数名时，再实现两个细分覆盖变量。

## 预期命令形态

未配置环境变量时保持当前命令：

```bash
z-ai chat -p "<prompt>" -o "<output.json>"
z-ai vision -p "<prompt>" -o "<output.json>" -i "<image.png>"
```

配置后追加模型参数：

```bash
z-ai chat --model "$ZAI_CHAT_MODEL" -p "<prompt>" -o "<output.json>"
z-ai vision --model "$ZAI_VISION_MODEL" -p "<prompt>" -o "<output.json>" -i "<image.png>"
```

参数顺序建议放在子命令之后、业务参数之前，便于阅读和排查：

```python
cmd = ["z-ai", "chat"]
if chat_model:
    cmd += [model_arg, chat_model]
cmd += ["-p", prompt, "-o", str(out_file)]
```

## 实现位置

建议增加一个小的内部辅助函数：

```python
def _append_model_arg(cmd: list, model_env: str, default_arg_env: str = "ZAI_MODEL_ARG") -> list:
    model = os.getenv(model_env, "").strip()
    if not model:
        return cmd
    arg = os.getenv(default_arg_env, "--model").strip() or "--model"
    return cmd + [arg, model]
```

然后在 `_run_zai_chat()` 中读取：

```python
cmd = ["z-ai", "chat"]
cmd = _append_model_arg(cmd, "ZAI_CHAT_MODEL")
cmd += ["-p", prompt, "-o", str(out_file)]
```

在 `_run_zai_vision()` 中读取：

```python
cmd = ["z-ai", "vision"]
cmd = _append_model_arg(cmd, "ZAI_VISION_MODEL")
cmd += ["-p", prompt, "-o", str(out_file)]
```

## 长 prompt 分支

`_run_zai_chat()` 对长 prompt 使用 `bash -c` 拼接字符串：

```python
shell_cmd = f'z-ai chat -p "$(cat {prompt_file})" -o {out_file}'
```

如果增加模型参数，这个分支也必须同步追加，否则同一个函数会出现短文本使用自定义模型、长文本仍使用默认模型的问题。

建议长 prompt 分支不要继续手写一整段 shell 字符串。更稳妥的方向是：

1. 仍然写临时 prompt/system 文件。
2. 使用 Python 读取文件内容并走 `subprocess.run(cmd_list, ...)`。
3. 避免 `bash -c`，也避免 shell quoting 问题。

如果本轮只做最小改动，也可以在 shell 字符串里追加：

```bash
z-ai chat --model "$ZAI_CHAT_MODEL" -p "$(cat prompt.txt)" -o output.json
```

但这会引入额外转义风险，尤其是在 Windows 环境下。后续实现时建议顺手消除 `bash -c` 分支。

## 边界行为

1. `ZAI_CHAT_MODEL` 为空或只包含空白：不追加模型参数。
2. `ZAI_VISION_MODEL` 为空或只包含空白：不追加模型参数。
3. `ZAI_MODEL_ARG` 为空：回退为 `--model`。
4. 模型名不做白名单校验，由 `z-ai` CLI 返回错误。
5. 当前代码没有检查 `subprocess.run()` 的退出码，后续实现时建议至少在输出文件不存在时保留现有返回空字符串行为，并可选择把 stderr 写入调试日志。

## 示例用法

PowerShell：

```powershell
$env:ZAI_CHAT_MODEL = "glm-4.5"
$env:ZAI_VISION_MODEL = "glm-4.5v"
python .\file_directory_predictor.py .\sample.pdf --catalog .\catalog-mapping.xlsx
```

Bash：

```bash
ZAI_CHAT_MODEL=glm-4.5 \
ZAI_VISION_MODEL=glm-4.5v \
python3 file_directory_predictor.py ./sample.pdf --catalog ./catalog-mapping.xlsx
```

如果 `z-ai` 使用的参数不是 `--model`：

```powershell
$env:ZAI_MODEL_ARG = "-m"
$env:ZAI_CHAT_MODEL = "glm-4.5"
$env:ZAI_VISION_MODEL = "glm-4.5v"
```

## 测试建议

在未安装 `z-ai` 的情况下，可以先做命令构造层测试：

1. 未设置环境变量时，构造命令不包含 `--model`。
2. 设置 `ZAI_CHAT_MODEL` 后，`z-ai chat` 命令包含 `--model <value>`。
3. 设置 `ZAI_VISION_MODEL` 后，`z-ai vision` 命令包含 `--model <value>`。
4. 设置 `ZAI_MODEL_ARG=-m` 后，命令包含 `-m <value>`。
5. 长 prompt 和短 prompt 行为一致。

安装 `z-ai` 后，再做端到端验证：

```bash
z-ai chat --model <chat-model> -p "测试" -o /tmp/zai-chat-test.json
z-ai vision --model <vision-model> -p "描述图片" -i <image> -o /tmp/zai-vision-test.json
```

## 审阅决策点

实施前需要确认：

1. `z-ai chat` 和 `z-ai vision` 是否都使用 `--model` 指定模型。
2. 是否接受同时提供 `ZAI_MODEL_ARG` 作为参数名逃生口。
3. 是否在同一次修改中移除 `_run_zai_chat()` 的 `bash -c` 长 prompt 分支。
4. 是否需要在使用说明文档中同步补充环境变量配置示例。

推荐决策：

1. 先确认 `z-ai` 的真实模型参数名。
2. 实现 `ZAI_CHAT_MODEL`、`ZAI_VISION_MODEL`、`ZAI_MODEL_ARG`。
3. 同步消除 `_run_zai_chat()` 的 `bash -c` 分支，确保 Windows 和 Linux 行为一致。
4. 更新使用说明并增加命令构造测试。
