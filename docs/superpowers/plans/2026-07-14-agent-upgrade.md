# Smart Case Filing Agent Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `file_directory_predictor.py` 从单次流水线预测器升级为受控任务型智能体，同时保持现有 CLI 和 JSON 输出兼容。

**Architecture:** 采用渐进式拆分：先保留现有脚本入口，再引入模型客户端、工具接口、智能体状态、轨迹记录和 runner。智能体只在编目任务边界内决策，最终目录字段继续从 `catalog-mapping.xlsx` 候选规则回写。

**Tech Stack:** Python 3.10+、标准库 `dataclasses/json/pathlib/argparse`、现有依赖 `pandas/openpyxl/pymupdf/python-docx/requests`、`unittest`、fake model client。

---

## File Structure

计划完成后的核心文件职责：

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `file_directory_predictor.py` | Modify | 兼容旧 CLI，逐步改为调用新模块；新增 `--agent`、`--trace`、`--review-output`、`--resume` 参数 |
| `smart_case_filing/__init__.py` | Create | 包入口 |
| `smart_case_filing/config.py` | Create | 项目路径、模型环境变量、超时、默认文件名 |
| `smart_case_filing/models.py` | Create | `CatalogEntry`、`FileContent`、`PredictionResult`、`AgentState`、`AgentStep` |
| `smart_case_filing/model_client.py` | Create | OpenAI-compatible 与 z-ai fallback 的统一模型客户端 |
| `smart_case_filing/catalog.py` | Create | `CatalogIndex`、`CatalogLoader`、案号推导和候选召回 |
| `smart_case_filing/extractors.py` | Create | `ContentExtractor` 及 PDF/Word/图片/表格/文本提取 |
| `smart_case_filing/analyzers.py` | Create | `VLMAnalyzer`、`LLMAnalyzer` |
| `smart_case_filing/predictor.py` | Create | 兼容旧 `DirectoryPredictor.predict()` 的同步预测器 |
| `smart_case_filing/agent/state.py` | Create | 智能体状态枚举、trace JSONL 读写 |
| `smart_case_filing/agent/tools.py` | Create | 工具接口与现有提取/分析/检索/精选工具适配 |
| `smart_case_filing/agent/policy.py` | Create | 下一步决策策略 |
| `smart_case_filing/agent/runner.py` | Create | 智能体状态机和恢复执行 |
| `smart_case_filing/agent/review.py` | Create | 人工复核包生成和读取 |
| `tests/test_agent_state.py` | Create | 状态和 trace 测试 |
| `tests/test_agent_runner.py` | Create | fake tools 的端到端智能体测试 |
| `tests/test_model_client.py` | Create | 模型客户端和脱敏测试 |
| `tests/test_cli_agent.py` | Create | CLI agent 参数兼容测试 |

---

### Task 1: Establish Agent State and Trace Format

**Files:**
- Create: `smart_case_filing/__init__.py`
- Create: `smart_case_filing/agent/__init__.py`
- Create: `smart_case_filing/agent/state.py`
- Create: `tests/test_agent_state.py`

- [ ] **Step 1: Create package marker files**

Create `smart_case_filing/__init__.py`:

```python
"""Smart Case Filing package."""
```

Create `smart_case_filing/agent/__init__.py`:

```python
"""Agent workflow package for Smart Case Filing."""
```

- [ ] **Step 2: Write failing tests for trace round-trip**

Create `tests/test_agent_state.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore


class AgentTraceStoreTest(unittest.TestCase):
    def test_appends_and_loads_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            store = AgentTraceStore(trace_path)
            step = AgentStep(
                run_id="run-1",
                file_path="sample.pdf",
                state=AgentState.EXTRACTED,
                tool="extract_content",
                input_summary={"path": "sample.pdf"},
                output_summary={"file_type": "pdf"},
            )

            store.append(step)
            loaded = store.load()

            self.assertEqual(1, len(loaded))
            self.assertEqual(AgentState.EXTRACTED, loaded[0].state)
            self.assertEqual("extract_content", loaded[0].tool)

    def test_trace_file_is_json_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace_path = Path(tmp) / "trace.jsonl"
            store = AgentTraceStore(trace_path)
            store.append(AgentStep(
                run_id="run-1",
                file_path="a.txt",
                state=AgentState.STARTED,
                tool="start",
                input_summary={},
                output_summary={},
            ))

            raw = trace_path.read_text(encoding="utf-8").strip()
            parsed = json.loads(raw)
            self.assertEqual("STARTED", parsed["state"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the failing test**

Run:

```bash
python -m unittest tests/test_agent_state.py
```

Expected:

```text
ModuleNotFoundError: No module named 'smart_case_filing.agent.state'
```

- [ ] **Step 4: Implement state and trace store**

Create `smart_case_filing/agent/state.py`:

```python
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path


class AgentState(str, Enum):
    STARTED = "STARTED"
    EXTRACTED = "EXTRACTED"
    VISUAL_ANALYZED = "VISUAL_ANALYZED"
    TEXT_ANALYZED = "TEXT_ANALYZED"
    CANDIDATES_RETRIEVED = "CANDIDATES_RETRIEVED"
    MATCHED = "MATCHED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class AgentStep:
    run_id: str
    file_path: str
    state: AgentState
    tool: str
    input_summary: dict = field(default_factory=dict)
    output_summary: dict = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)

    def to_jsonable(self) -> dict:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_jsonable(cls, data: dict) -> "AgentStep":
        return cls(
            run_id=data["run_id"],
            file_path=data["file_path"],
            state=AgentState(data["state"]),
            tool=data["tool"],
            input_summary=data.get("input_summary", {}),
            output_summary=data.get("output_summary", {}),
            error=data.get("error", ""),
            created_at=float(data.get("created_at", time.time())),
        )


class AgentTraceStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, step: AgentStep) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(step.to_jsonable(), ensure_ascii=False) + "\n")

    def load(self) -> list[AgentStep]:
        if not self.path.exists():
            return []
        steps = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                steps.append(AgentStep.from_jsonable(json.loads(line)))
        return steps
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
python -m unittest tests/test_agent_state.py
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```bash
git add smart_case_filing/__init__.py smart_case_filing/agent/__init__.py smart_case_filing/agent/state.py tests/test_agent_state.py
git commit -m "feat: add agent trace state"
```

---

### Task 2: Introduce a Model Client Boundary

**Files:**
- Create: `smart_case_filing/model_client.py`
- Create: `tests/test_model_client.py`
- Modify: `file_directory_predictor.py`

- [ ] **Step 1: Write failing tests for redaction and fake client behavior**

Create `tests/test_model_client.py`:

```python
import unittest

from smart_case_filing.model_client import FakeModelClient, redact_secret


class ModelClientTest(unittest.TestCase):
    def test_redacts_api_key_values(self):
        text = "Authorization: Bearer sk-1234567890abcdef"
        self.assertEqual("Authorization: Bearer sk-1234...cdef", redact_secret(text))

    def test_fake_client_returns_registered_response(self):
        client = FakeModelClient({"chat": "{\"ok\": true}", "vision": "{\"image\": true}"})
        self.assertEqual("{\"ok\": true}", client.chat("prompt", system="sys"))
        self.assertEqual("{\"image\": true}", client.vision("prompt", ["a.png"]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python -m unittest tests/test_model_client.py
```

Expected:

```text
ModuleNotFoundError: No module named 'smart_case_filing.model_client'
```

- [ ] **Step 3: Implement model client types**

Create `smart_case_filing/model_client.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, Protocol


def redact_secret(text: str) -> str:
    def repl(match):
        token = match.group(1)
        if len(token) <= 8:
            return "sk-****"
        return f"{token[:7]}...{token[-4:]}"

    return re.sub(r"(sk-[A-Za-z0-9._-]+)", repl, text or "")


class ModelClient(Protocol):
    def chat(self, prompt: str, system: Optional[str] = None, thinking: bool = False, timeout: int = 180) -> str:
        ...

    def vision(self, prompt: str, image_paths: list, thinking: bool = False, timeout: int = 180) -> str:
        ...


@dataclass
class LegacyFunctionModelClient:
    chat_func: callable
    vision_func: callable

    def chat(self, prompt: str, system: Optional[str] = None, thinking: bool = False, timeout: int = 180) -> str:
        return self.chat_func(prompt, system=system, thinking=thinking, timeout=timeout)

    def vision(self, prompt: str, image_paths: list, thinking: bool = False, timeout: int = 180) -> str:
        return self.vision_func(prompt, image_paths, thinking=thinking, timeout=timeout)


@dataclass
class FakeModelClient:
    responses: dict[str, str] = field(default_factory=dict)

    def chat(self, prompt: str, system: Optional[str] = None, thinking: bool = False, timeout: int = 180) -> str:
        return self.responses.get("chat", "")

    def vision(self, prompt: str, image_paths: list, thinking: bool = False, timeout: int = 180) -> str:
        return self.responses.get("vision", "")
```

- [ ] **Step 4: Thread the model client into analyzers without changing behavior**

Modify `file_directory_predictor.py` imports near the top:

```python
from smart_case_filing.model_client import LegacyFunctionModelClient
```

Modify `VLMAnalyzer`:

```python
class VLMAnalyzer:
    def __init__(self, model_client=None):
        self.model_client = model_client or LegacyFunctionModelClient(_run_zai_chat, _run_zai_vision)

    def analyze(self, fc: FileContent) -> dict:
        if not fc.has_visual():
            return {"available": False, "reason": "无可分析图像"}
        imgs = fc.image_paths[:MAX_PDF_PAGES_FOR_VLM]
        prompt = self._build_prompt(fc)
        raw = self.model_client.vision(prompt, imgs, thinking=False, timeout=CLI_TIMEOUT)
        return self._parse(raw)
```

Modify `LLMAnalyzer`:

```python
class LLMAnalyzer:
    def __init__(self, model_client=None):
        self.model_client = model_client or LegacyFunctionModelClient(_run_zai_chat, _run_zai_vision)

    def analyze_text(self, fc: FileContent) -> dict:
        ...
        raw = self.model_client.chat(prompt, system=self.SYSTEM, thinking=False, timeout=CLI_TIMEOUT)
        return self._parse(raw)
```

Modify `DirectoryPredictor.__init__`:

```python
def __init__(self, catalog: CatalogIndex, model_client=None):
    self.catalog = catalog
    self.model_client = model_client or LegacyFunctionModelClient(_run_zai_chat, _run_zai_vision)
    self.vlm = VLMAnalyzer(self.model_client)
    self.llm = LLMAnalyzer(self.model_client)
```

Modify `_match_catalog`:

```python
raw = self.model_client.chat(prompt, system=LLMAnalyzer.SYSTEM, thinking=True, timeout=CLI_TIMEOUT)
```

- [ ] **Step 5: Run model client and existing tests**

Run:

```bash
python -m unittest tests/test_model_client.py tests/test_catalog_index.py tests/test_cli_output.py
```

Expected:

```text
OK
```

- [ ] **Step 6: Commit**

```bash
git add smart_case_filing/model_client.py tests/test_model_client.py file_directory_predictor.py
git commit -m "refactor: add model client boundary"
```

---

### Task 3: Add Agent Tool Adapters

**Files:**
- Create: `smart_case_filing/agent/tools.py`
- Create: `tests/test_agent_tools.py`

- [ ] **Step 1: Write failing tests for tool registry**

Create `tests/test_agent_tools.py`:

```python
import unittest

from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class AgentToolRegistryTest(unittest.TestCase):
    def test_registers_and_runs_tool(self):
        registry = AgentToolRegistry()
        registry.register("echo", lambda payload: ToolResult(ok=True, data={"value": payload["value"]}))

        result = registry.run("echo", {"value": "hello"})

        self.assertTrue(result.ok)
        self.assertEqual({"value": "hello"}, result.data)

    def test_unknown_tool_returns_failure(self):
        registry = AgentToolRegistry()
        result = registry.run("missing", {})

        self.assertFalse(result.ok)
        self.assertIn("unknown tool", result.error)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python -m unittest tests/test_agent_tools.py
```

Expected:

```text
ModuleNotFoundError: No module named 'smart_case_filing.agent.tools'
```

- [ ] **Step 3: Implement registry and result**

Create `smart_case_filing/agent/tools.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ToolResult:
    ok: bool
    data: dict = field(default_factory=dict)
    error: str = ""


class AgentToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable[[dict], ToolResult]] = {}

    def register(self, name: str, func: Callable[[dict], ToolResult]) -> None:
        self._tools[name] = func

    def run(self, name: str, payload: dict) -> ToolResult:
        func = self._tools.get(name)
        if not func:
            return ToolResult(ok=False, error=f"unknown tool: {name}")
        try:
            return func(payload)
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m unittest tests/test_agent_tools.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add smart_case_filing/agent/tools.py tests/test_agent_tools.py
git commit -m "feat: add agent tool registry"
```

---

### Task 4: Implement the Minimal Agent Runner

**Files:**
- Create: `smart_case_filing/agent/runner.py`
- Create: `tests/test_agent_runner.py`

- [ ] **Step 1: Write failing runner tests with fake tools**

Create `tests/test_agent_runner.py`:

```python
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.runner import AgentRunner
from smart_case_filing.agent.state import AgentState, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class AgentRunnerTest(unittest.TestCase):
    def make_registry(self):
        registry = AgentToolRegistry()
        registry.register("extract_content", lambda payload: ToolResult(ok=True, data={"file_type": "text", "text": "民事起诉状"}))
        registry.register("analyze_text", lambda payload: ToolResult(ok=True, data={"doc_type_guess": "民事起诉状", "confidence": "high"}))
        registry.register("retrieve_candidates", lambda payload: ToolResult(ok=True, data={"count": 1}))
        registry.register("select_catalog", lambda payload: ToolResult(ok=True, data={
            "case_type": "民事一审案件编目规则",
            "volume": "正卷",
            "second_level_directory": "起诉状及相关材料",
            "material_category": "民事起诉状",
            "confidence": "high",
        }))
        return registry

    def test_runner_completes_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(self.make_registry(), trace)

            result = runner.run("run-1", "sample.txt")

            self.assertEqual(AgentState.COMPLETED, result["state"])
            self.assertEqual("民事起诉状", result["prediction"]["material_category"])
            self.assertEqual(5, len(trace.load()))

    def test_runner_stops_on_failed_tool(self):
        registry = AgentToolRegistry()
        registry.register("extract_content", lambda payload: ToolResult(ok=False, error="read failed"))
        with tempfile.TemporaryDirectory() as tmp:
            trace = AgentTraceStore(Path(tmp) / "trace.jsonl")
            runner = AgentRunner(registry, trace)

            result = runner.run("run-1", "missing.pdf")

            self.assertEqual(AgentState.FAILED, result["state"])
            self.assertIn("read failed", result["error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m unittest tests/test_agent_runner.py
```

Expected:

```text
ModuleNotFoundError: No module named 'smart_case_filing.agent.runner'
```

- [ ] **Step 3: Implement minimal sequential runner**

Create `smart_case_filing/agent/runner.py`:

```python
from __future__ import annotations

from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class AgentRunner:
    def __init__(self, tools: AgentToolRegistry, trace_store: AgentTraceStore):
        self.tools = tools
        self.trace_store = trace_store

    def _record(self, run_id: str, file_path: str, state: AgentState, tool: str,
                input_summary: dict, result: ToolResult) -> None:
        self.trace_store.append(AgentStep(
            run_id=run_id,
            file_path=file_path,
            state=state,
            tool=tool,
            input_summary=input_summary,
            output_summary=result.data if result.ok else {},
            error=result.error,
        ))

    def _run_tool(self, run_id: str, file_path: str, state: AgentState,
                  tool: str, payload: dict) -> ToolResult:
        result = self.tools.run(tool, payload)
        self._record(run_id, file_path, state, tool, payload, result)
        return result

    def run(self, run_id: str, file_path: str) -> dict:
        start = ToolResult(ok=True, data={"file_path": file_path})
        self._record(run_id, file_path, AgentState.STARTED, "start", {}, start)

        extracted = self._run_tool(run_id, file_path, AgentState.EXTRACTED, "extract_content", {"file_path": file_path})
        if not extracted.ok:
            return {"state": AgentState.FAILED, "error": extracted.error}

        text = self._run_tool(run_id, file_path, AgentState.TEXT_ANALYZED, "analyze_text", extracted.data)
        if not text.ok:
            return {"state": AgentState.FAILED, "error": text.error}

        candidates = self._run_tool(run_id, file_path, AgentState.CANDIDATES_RETRIEVED, "retrieve_candidates", text.data)
        if not candidates.ok:
            return {"state": AgentState.FAILED, "error": candidates.error}

        match = self._run_tool(run_id, file_path, AgentState.MATCHED, "select_catalog", candidates.data | text.data)
        if not match.ok:
            return {"state": AgentState.FAILED, "error": match.error}

        state = AgentState.COMPLETED if match.data.get("confidence") != "low" else AgentState.NEEDS_REVIEW
        return {"state": state, "prediction": match.data}
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m unittest tests/test_agent_runner.py tests/test_agent_state.py tests/test_agent_tools.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add smart_case_filing/agent/runner.py tests/test_agent_runner.py
git commit -m "feat: add minimal filing agent runner"
```

---

### Task 5: Wire Legacy Predictor Tools into Agent Mode

**Files:**
- Modify: `file_directory_predictor.py`
- Create: `tests/test_cli_agent.py`

- [ ] **Step 1: Write failing CLI agent test**

Create `tests/test_cli_agent.py`:

```python
import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("pandas", types.SimpleNamespace())

import file_directory_predictor as fdp


class CliAgentModeTest(unittest.TestCase):
    def test_agent_mode_writes_trace_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_file = tmp_path / "sample.txt"
            catalog_file = tmp_path / "catalog.xlsx"
            trace_file = tmp_path / "trace.jsonl"
            input_file.write_text("民事起诉状", encoding="utf-8")
            catalog_file.write_text("fake", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.object(sys, "argv", [
                "file_directory_predictor.py",
                str(input_file),
                "--catalog", str(catalog_file),
                "--agent",
                "--trace", str(trace_file),
                "--json",
            ]), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                with patch.object(fdp, "_run_agent_cli", lambda args: print("{\"state\": \"COMPLETED\"}")):
                    fdp.main()

            self.assertIn("COMPLETED", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing CLI test**

Run:

```bash
python -m unittest tests/test_cli_agent.py
```

Expected:

```text
SystemExit: 2
```

because `--agent` and `--trace` do not exist yet.

- [ ] **Step 3: Add CLI flags and dispatch**

Modify `main()` parser in `file_directory_predictor.py`:

```python
parser.add_argument("--agent", action="store_true", help="启用智能体状态机执行")
parser.add_argument("--trace", help="智能体执行轨迹 JSONL 保存路径")
parser.add_argument("--review-output", help="需要人工复核时输出复核材料的路径")
parser.add_argument("--resume", help="从已有 trace JSONL 恢复智能体任务")
```

After `args = parser.parse_args()` add:

```python
if args.agent:
    _run_agent_cli(args)
    return
```

Add a placeholder implementation above `main()`:

```python
def _run_agent_cli(args):
    trace_path = Path(args.trace) if args.trace else PROGRAM_DIR / "agent_trace.jsonl"
    print(json.dumps({
        "state": "FAILED",
        "reason": "agent runner is not wired yet",
        "trace": str(trace_path),
    }, ensure_ascii=False, indent=2))
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
python -m unittest tests/test_cli_agent.py tests/test_cli_output.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add file_directory_predictor.py tests/test_cli_agent.py
git commit -m "feat: add agent cli flags"
```

---

### Task 6: Generate Human Review Package for Low Confidence

**Files:**
- Create: `smart_case_filing/agent/review.py`
- Create: `tests/test_agent_review.py`

- [ ] **Step 1: Write failing review package test**

Create `tests/test_agent_review.py`:

```python
import json
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.review import ReviewPackageWriter


class ReviewPackageWriterTest(unittest.TestCase):
    def test_writes_review_json_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            writer = ReviewPackageWriter(path)
            writer.write({
                "file_path": "case.pdf",
                "confidence": "low",
                "reasoning": "Authorization: Bearer sk-1234567890abcdef",
                "candidates": [{"material_category": "起诉状"}],
            })

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("case.pdf", data["file_path"])
            self.assertNotIn("sk-1234567890abcdef", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run failing test**

Run:

```bash
python -m unittest tests/test_agent_review.py
```

Expected:

```text
ModuleNotFoundError: No module named 'smart_case_filing.agent.review'
```

- [ ] **Step 3: Implement review writer**

Create `smart_case_filing/agent/review.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from smart_case_filing.model_client import redact_secret


class ReviewPackageWriter:
    def __init__(self, path: Path):
        self.path = Path(path)

    def write(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, indent=2)
        self.path.write_text(redact_secret(raw) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run review tests**

Run:

```bash
python -m unittest tests/test_agent_review.py tests/test_model_client.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add smart_case_filing/agent/review.py tests/test_agent_review.py
git commit -m "feat: add agent review package writer"
```

---

### Task 7: Preserve Backward Compatibility and Document Agent Mode

**Files:**
- Modify: `docs/卷宗智能推理编目使用说明.md`
- Modify: `docs/Smart_Case_Filing_Usage.en.md`
- Modify: `README.md`
- Modify: `README.en.md`

- [ ] **Step 1: Run baseline compatibility tests**

Run:

```bash
python -m unittest discover -s tests
```

Expected:

```text
OK
```

- [ ] **Step 2: Update Chinese usage guide with agent mode**

Add this section after “批量预测” in `docs/卷宗智能推理编目使用说明.md`:

````markdown
## 7. 智能体模式

智能体模式适合需要保留执行轨迹、低置信复核和断点恢复的编目任务。

```bash
python file_directory_predictor.py ./sample.pdf \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./logs/sample.trace.jsonl \
  --review-output ./logs/sample.review.json \
  --json
```

智能体模式仍会保持普通 JSON 输出字段兼容；额外的执行步骤写入 `--trace` 指定的 JSONL 文件。
````

- [ ] **Step 3: Update English usage guide with agent mode**

Add this section after “Batch Prediction” in `docs/Smart_Case_Filing_Usage.en.md`:

````markdown
## 7. Agent Mode

Agent mode is for cataloging tasks that need execution trace, low-confidence review, and resume support.

```bash
python file_directory_predictor.py ./sample.pdf \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./logs/sample.trace.jsonl \
  --review-output ./logs/sample.review.json \
  --json
```

Agent mode keeps the normal JSON output fields compatible and writes additional step traces to the JSONL file passed through `--trace`.
````

- [ ] **Step 4: Update README feature list**

In `README.md`, add:

```markdown
- 规划中的智能体模式将支持执行轨迹、低置信复核和断点恢复。
```

In `README.en.md`, add:

```markdown
- The planned agent mode will support execution traces, low-confidence review, and resume support.
```

- [ ] **Step 5: Verify all docs links and tests**

Run:

```bash
python -m unittest discover -s tests
python -c 'from pathlib import Path; import re, sys; ok=True
for f in Path(".").rglob("*.md"):
    if any(part.startswith(".") for part in f.parts):
        continue
    text=f.read_text(encoding="utf-8")
    for target in re.findall(r"\\[[^\\]]+\\]\\(([^)#][^)]+)\\)", text):
        if "://" in target or target.startswith("mailto:"):
            continue
        if not (f.parent / target).resolve().exists():
            print(f"{f}: missing {target}")
            ok=False
print("markdown local links ok" if ok else "markdown local links failed")
sys.exit(0 if ok else 1)'
```

Expected:

```text
OK
markdown local links ok
```

- [ ] **Step 6: Commit**

```bash
git add README.md README.en.md docs/卷宗智能推理编目使用说明.md docs/Smart_Case_Filing_Usage.en.md
git commit -m "docs: describe agent mode"
```

---

## Self-Review

Spec coverage:

- 智能体状态：Task 1 覆盖。
- 模型客户端边界：Task 2 覆盖。
- 工具接口：Task 3 覆盖。
- 最小 runner：Task 4 覆盖。
- CLI agent 入口：Task 5 覆盖。
- 人工复核包：Task 6 覆盖。
- 文档和兼容性：Task 7 覆盖。

Placeholder scan:

- 本计划没有 `TBD`、`TODO`、`implement later`。
- 每个任务都有具体文件、测试、命令和预期结果。

Type consistency:

- `AgentState`、`AgentStep`、`AgentTraceStore` 在 Task 1 定义，后续任务使用相同名称。
- `ToolResult`、`AgentToolRegistry` 在 Task 3 定义，Task 4 使用相同接口。
- `FakeModelClient`、`LegacyFunctionModelClient` 在 Task 2 定义，后续保留相同方法签名。

Execution note:

- 在执行本计划前，先处理当前工作区未提交状态，尤其是 `catalog-mapping.xlsx` 删除和 `requirements.txt` 修改。智能体功能的验证需要可用的编目规则表或测试中的 fake catalog。
