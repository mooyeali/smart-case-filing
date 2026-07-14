# Smart Case Filing Agent Phase Two Implementation Plan

**Goal:** 将第一阶段已建立的智能体骨架接入真实编目工具链，使 `--agent` 模式具备单文件端到端预测能力，同时保持旧 CLI 和 JSON 输出兼容。

**Source:** `docs/agent/智能体升级第二阶段圆桌会议纪要.md`

**Architecture:** 第二阶段采用“旧能力薄适配 + 顺序状态机增强”的路线。新增 `legacy_tools.py` 将 `file_directory_predictor.py` 中已有的提取、分析、候选召回、候选精选能力包装为 Agent tools；扩展 `AgentRunner` 支持真实工具链步骤、低置信复核、失败状态、最终输出组装和最小 resume。暂不做开放式聊天、多 Agent、SQLite、Web UI 或完整批量恢复。

**Tech Stack:** Python 3.10+、标准库 `dataclasses/json/pathlib/argparse/tempfile/unittest`、现有依赖 `pandas/openpyxl/pymupdf/python-docx/requests`、fake model client。

---

## File Structure

第二阶段计划涉及文件：

| 文件 | 操作 | 职责 |
| --- | --- | --- |
| `smart_case_filing/agent/legacy_tools.py` | Create | 将旧 `ContentExtractor`、`LLMAnalyzer`、`VLMAnalyzer`、`CatalogIndex`、候选精选逻辑包装为 agent tools |
| `smart_case_filing/agent/runner.py` | Modify | 从最小 runner 扩展为单文件编目 runner，支持视觉步骤、最终输出、低置信复核 |
| `smart_case_filing/agent/review.py` | Modify | 支持写入第二阶段 review package 结构 |
| `file_directory_predictor.py` | Modify | `_run_agent_cli(args)` 从占位实现改为真实执行 |
| `tests/test_agent_legacy_tools.py` | Create | 验证旧能力 adapter 的工具输出、候选摘要和字段约束 |
| `tests/test_agent_runner_v2.py` | Create | 验证真实步骤序列、trace、low confidence、failure |
| `tests/test_agent_cli_integration.py` | Create | 验证 CLI agent 模式输出、trace、review 文件 |
| `tests/test_agent_resume.py` | Create | 验证最小 resume 语义 |
| `docs/卷宗智能推理编目使用说明.md` | Modify | 描述真实 agent mode 行为和限制 |
| `docs/Smart_Case_Filing_Usage.en.md` | Modify | 英文同步说明 |
| `README.md` / `README.en.md` | Modify | 更新 agent mode 状态，从“规划中”调整为“可用的单文件 agent mode” |
| `test-reports/agent-phase-two-fake-run.md` | Create | fake model 的 agent mode 测试报告 |

---

## Task 1: Add Legacy Agent Tool Adapters

**Files:**
- Create: `smart_case_filing/agent/legacy_tools.py`
- Create: `tests/test_agent_legacy_tools.py`

- [ ] **Step 1: Write failing tests for adapter registry**

Create tests covering:

1. `build_legacy_tool_registry(...)` registers:
   - `extract_content`
   - `analyze_visual`
   - `analyze_text`
   - `retrieve_candidates`
   - `select_catalog`
   - `finalize_prediction`
2. `extract_content` returns summary, not full text by default.
3. `analyze_text` can use `FakeModelClient`.
4. `retrieve_candidates` returns candidate count and compact candidate summaries.
5. `select_catalog` keeps final fields from the selected candidate, not from model-invented fields.

Suggested test fixture:

```python
from pathlib import Path
from smart_case_filing.agent.legacy_tools import build_legacy_tool_registry
from smart_case_filing.model_client import FakeModelClient
from file_directory_predictor import CatalogEntry, CatalogIndex
```

- [ ] **Step 2: Run failing tests**

```bash
python -m unittest tests/test_agent_legacy_tools.py
```

Expected:

```text
ModuleNotFoundError: No module named 'smart_case_filing.agent.legacy_tools'
```

- [ ] **Step 3: Implement `legacy_tools.py`**

Required public API:

```python
def build_legacy_tool_registry(catalog, model_client=None):
    ...

def summarize_file_content(fc) -> dict:
    ...

def summarize_candidates(candidates: list, limit: int = 5) -> list[dict]:
    ...
```

Tool contract:

```text
extract_content input:
  {"file_path": "..."}
extract_content output:
  {
    "file_path": "...",
    "file_type": "...",
    "text_length": 123,
    "text_preview": "...",
    "image_count": 0,
    "page_count": 1,
    "_fc": FileContent
  }
```

Internal `_fc` may be passed between tools but must not be recorded directly in trace summaries.

`retrieve_candidates` output:

```text
{
  "keywords": [...],
  "candidate_count": 25,
  "candidate_summaries": [...],
  "_candidates": [...]
}
```

`select_catalog` output:

```text
{
  "match": {...},
  "candidate_count": 25
}
```

`finalize_prediction` output should include legacy-compatible fields:

```text
file_path
file_type
predicted_case_type
predicted_volume
predicted_second_level_directory
predicted_material_category
predicted_catalog_example
confidence
reasoning
vlm_analysis
llm_analysis
matched_entries
```

- [ ] **Step 4: Run tests**

```bash
python -m unittest tests/test_agent_legacy_tools.py tests/test_model_client.py tests/test_catalog_index.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add smart_case_filing/agent/legacy_tools.py tests/test_agent_legacy_tools.py
git commit -m "feat: add legacy agent tool adapters"
```

---

## Task 2: Extend AgentRunner for Real Filing Flow

**Files:**
- Modify: `smart_case_filing/agent/runner.py`
- Create: `tests/test_agent_runner_v2.py`

- [ ] **Step 1: Write failing tests for full step sequence**

Test cases:

1. Happy path:
   - records `STARTED`
   - records `EXTRACTED`
   - records `VISUAL_ANALYZED` with skipped summary when no images
   - records `TEXT_ANALYZED`
   - records `CANDIDATES_RETRIEVED`
   - records `MATCHED`
   - records `COMPLETED`
2. Low confidence:
   - final state is `NEEDS_REVIEW`
   - prediction is still present
3. Failed tool:
   - final state is `FAILED`
   - trace includes error
4. Trace summaries:
   - no `_fc`
   - no `_candidates`
   - no raw full text

- [ ] **Step 2: Run failing tests**

```bash
python -m unittest tests/test_agent_runner_v2.py
```

Expected: failures because current runner lacks visual/finalize/review-aware sequence.

- [ ] **Step 3: Implement runner v2**

Keep public constructor compatible:

```python
AgentRunner(tools, trace_store)
```

Add optional behavior:

```python
def run(self, run_id: str, file_path: str) -> dict:
    ...
```

Required tool order:

```text
start
extract_content
analyze_visual
analyze_text
retrieve_candidates
select_catalog
finalize_prediction
completed / needs_review / failed
```

Skip behavior:

- If no visual input, still record `VISUAL_ANALYZED` with `{"skipped": True, "reason": "no visual input"}`.
- If no text, still record `TEXT_ANALYZED` with skipped summary.

Trace sanitization:

- Before appending `AgentStep`, remove internal keys beginning with `_`.
- Truncate previews.
- Redact secrets from error strings.

- [ ] **Step 4: Run runner tests**

```bash
python -m unittest tests/test_agent_runner.py tests/test_agent_runner_v2.py tests/test_agent_state.py tests/test_agent_tools.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add smart_case_filing/agent/runner.py tests/test_agent_runner_v2.py
git commit -m "feat: extend agent runner for filing flow"
```

---

## Task 3: Wire `_run_agent_cli` to Real Agent Execution

**Files:**
- Modify: `file_directory_predictor.py`
- Create: `tests/test_agent_cli_integration.py`

- [ ] **Step 1: Write failing CLI integration tests**

Test cases:

1. `--agent --json` writes JSON output containing legacy fields and `agent_state`.
2. `--trace <path>` creates JSONL trace.
3. Low confidence writes `--review-output`.
4. Non-agent CLI tests continue to pass.

Use fake dependencies:

- Patch `CatalogLoader`.
- Patch `build_legacy_tool_registry` or model client.
- Use temporary input file and catalog file.

- [ ] **Step 2: Run failing tests**

```bash
python -m unittest tests/test_agent_cli_integration.py
```

Expected: failures because `_run_agent_cli` is still placeholder.

- [ ] **Step 3: Implement CLI agent execution**

Suggested helper:

```python
def _run_agent_cli(args):
    catalog_path = Path(args.catalog)
    catalog = CatalogLoader(catalog_path).load()
    trace_path = Path(args.trace) if args.trace else PROGRAM_DIR / "agent_trace.jsonl"
    trace_store = AgentTraceStore(trace_path)
    registry = build_legacy_tool_registry(catalog)
    runner = AgentRunner(registry, trace_store)
    result = runner.run(run_id=..., file_path=args.file)
    ...
```

Output shape:

```json
{
  "agent_state": "COMPLETED",
  "trace": "...",
  "review_output": "",
  "file_path": "...",
  "file_type": "...",
  "predicted_case_type": "...",
  "predicted_volume": "...",
  "predicted_second_level_directory": "...",
  "predicted_material_category": "...",
  "predicted_catalog_example": "...",
  "confidence": "...",
  "reasoning": "...",
  "vlm_analysis": {},
  "llm_analysis": {},
  "matched_entries": []
}
```

Compatibility rule:

- Do not remove legacy top-level fields.
- Add agent fields only as additive fields.

Review output:

- If state is `NEEDS_REVIEW` or `FAILED` and `args.review_output` is set, call `ReviewPackageWriter`.

- [ ] **Step 4: Run CLI tests**

```bash
python -m unittest tests/test_agent_cli_integration.py tests/test_cli_agent.py tests/test_cli_output.py
```

Expected:

```text
OK
```

- [ ] **Step 5: Commit**

```bash
git add file_directory_predictor.py tests/test_agent_cli_integration.py
git commit -m "feat: wire agent cli to filing runner"
```

---

## Task 4: Implement Minimal Resume Semantics

**Files:**
- Modify: `file_directory_predictor.py`
- Modify: `smart_case_filing/agent/runner.py` if needed
- Create: `tests/test_agent_resume.py`

- [ ] **Step 1: Write failing resume tests**

Test cases:

1. Resume from trace whose last state is `COMPLETED` returns completed summary and does not execute tools.
2. Resume from trace whose last state is `FAILED` returns failed summary and does not execute tools.
3. Resume from missing trace returns a clear `FAILED` response.
4. Resume from partial trace returns explicit unsupported/interrupted state, not silent success.

- [ ] **Step 2: Implement resume helper**

Suggested helper:

```python
def _run_agent_resume(args):
    trace_store = AgentTraceStore(Path(args.resume))
    steps = trace_store.load()
    ...
```

Minimal semantics:

- `COMPLETED`: return `{"agent_state": "COMPLETED", "trace": "...", "resume": True}`
- `FAILED`: return `{"agent_state": "FAILED", "trace": "...", "resume": True, "error": "..."}`
- `NEEDS_REVIEW`: return `{"agent_state": "NEEDS_REVIEW", ...}`
- other last states: return `{"agent_state": "FAILED", "reason": "partial resume is not supported in phase two"}`

- [ ] **Step 3: Run resume tests**

```bash
python -m unittest tests/test_agent_resume.py tests/test_agent_state.py
```

Expected:

```text
OK
```

- [ ] **Step 4: Commit**

```bash
git add file_directory_predictor.py smart_case_filing/agent/runner.py tests/test_agent_resume.py
git commit -m "feat: add minimal agent resume"
```

---

## Task 5: Strengthen Review Package Content

**Files:**
- Modify: `smart_case_filing/agent/review.py`
- Modify: `tests/test_agent_review.py`

- [ ] **Step 1: Extend review tests**

Review package must contain:

```text
file_path
agent_state
confidence
reasoning
trace
candidate_summaries
llm_analysis
vlm_analysis
error
created_at
```

Tests:

- API keys are redacted.
- File parent directory is created.
- Candidate summaries are retained.
- Full extracted text is not required.

- [ ] **Step 2: Implement structured review package**

Add helper:

```python
def build_review_payload(agent_result: dict, trace_path: str) -> dict:
    ...
```

Keep `ReviewPackageWriter.write(payload)` compatible.

- [ ] **Step 3: Run tests**

```bash
python -m unittest tests/test_agent_review.py tests/test_agent_cli_integration.py
```

Expected:

```text
OK
```

- [ ] **Step 4: Commit**

```bash
git add smart_case_filing/agent/review.py tests/test_agent_review.py
git commit -m "feat: structure agent review packages"
```

---

## Task 6: Document Real Agent Mode and Add Fake Run Report

**Files:**
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/卷宗智能推理编目使用说明.md`
- Modify: `docs/Smart_Case_Filing_Usage.en.md`
- Create: `test-reports/agent-phase-two-fake-run.md`
- Create: `test-reports/agent-phase-two-fake-run.json`

- [ ] **Step 1: Update docs**

Change wording from “规划中的智能体模式” to “单文件智能体模式”.

Document:

- `--agent`
- `--trace`
- `--review-output`
- `--resume`
- trace JSONL format
- review package behavior
- phase two limitations:
  - no batch agent
  - no partial resume
  - no retry policy yet

- [ ] **Step 2: Create fake run report**

Report should include:

```text
command
input file
fake model behavior
trace excerpt
JSON output
review output if applicable
test command
```

- [ ] **Step 3: Validate docs and tests**

```bash
python -m unittest discover -s tests
python -c "from pathlib import Path; import re, sys; ok=True
for f in Path('.').rglob('*.md'):
    if any(part.startswith('.') for part in f.parts):
        continue
    text=f.read_text(encoding='utf-8')
    for target in re.findall(r'\\[[^\\]]+\\]\\(([^)#][^)]+)\\)', text):
        if '://' in target or target.startswith('mailto:'):
            continue
        if not (f.parent / target).resolve().exists():
            print(f'{f}: missing {target}')
            ok=False
print('markdown local links ok' if ok else 'markdown local links failed')
sys.exit(0 if ok else 1)"
```

Expected:

```text
OK
markdown local links ok
```

- [ ] **Step 4: Commit**

```bash
git add README.md README.en.md docs/卷宗智能推理编目使用说明.md docs/Smart_Case_Filing_Usage.en.md test-reports/agent-phase-two-fake-run.md test-reports/agent-phase-two-fake-run.json
git commit -m "docs: document real agent mode"
```

---

## Final Verification

Before declaring phase two complete, run:

```bash
python -m unittest discover -s tests
python file_directory_predictor.py --help
```

Manual smoke test with fake or local input:

```bash
python file_directory_predictor.py ./test-reports/full-chain-input.txt \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./test-reports/agent-smoke.trace.jsonl \
  --review-output ./test-reports/agent-smoke.review.json \
  --json
```

Expected:

- command exits with code 0
- JSON output contains legacy prediction fields
- JSON output contains `agent_state`
- trace JSONL exists
- review JSON exists when state is `NEEDS_REVIEW` or `FAILED`

---

## Completion Criteria

Phase two is complete only when:

- [ ] `--agent` no longer returns placeholder output.
- [ ] Single-file agent mode completes end-to-end with real legacy tools.
- [ ] Trace JSONL records the full step chain.
- [ ] Low confidence or failure writes review package.
- [ ] Minimal `--resume` behavior is implemented and tested.
- [ ] Final catalog fields are still copied from candidate rules.
- [ ] Existing non-agent CLI behavior remains compatible.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] Documentation describes actual phase-two behavior.
- [ ] A fake run report is committed.

---

## Out of Scope for Phase Two

- Batch agent mode.
- True partial step resume.
- Retry/backoff policy.
- SQLite persistence.
- Web UI.
- Model routing.
- Full extraction of `file_directory_predictor.py` into package modules.

These are candidates for phase three.
