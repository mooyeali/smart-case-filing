# Smart Case Filing Agent Phase Three Implementation Plan

**Goal:** 将第二阶段的单文件受控编目 agent 扩展为“批量可恢复的编目任务 agent”，支持稳定运行目录、run manifest、批量执行、partial resume、retry/backoff、复核索引和可重复全链路测试门禁。

**Source:** `docs/agent/智能体升级第三阶段圆桌会议纪要.md`

**Architecture:** 第三阶段不引入通用多 Agent 框架，继续沿用 `AgentRunner`、`AgentTraceStore`、`legacy_tools.py` 和 OpenAI-compatible HTTP API。新增轻量 run 管理层负责 `run_id`、路径规划、manifest、批量任务汇总和 resume 策略；新增 retry policy 包装工具调用；CLI 只负责参数解析和结果输出。

**Tech Stack:** Python 3.10+、标准库 `json/pathlib/time/uuid/dataclasses/unittest/tempfile`、现有依赖 `requests/pandas/openpyxl/pymupdf/python-docx`、fake model client。

---

## File Structure

| File | Action | Responsibility |
| --- | --- | --- |
| `smart_case_filing/agent/run_manager.py` | Create | 管理 run_id、运行目录、manifest、批量文件状态和结果汇总 |
| `smart_case_filing/agent/retry.py` | Create | 定义 retry/backoff policy 和可重试错误包装 |
| `smart_case_filing/agent/runner.py` | Modify | 支持从指定状态上下文继续执行；工具调用接入 retry policy |
| `smart_case_filing/agent/state.py` | Modify | 如需要，增加 manifest 读写辅助或稳定 step 查询 |
| `smart_case_filing/agent/review.py` | Modify | 支持批量 review index payload |
| `file_directory_predictor.py` | Modify | 接入 batch agent、run directory、partial resume CLI |
| `tests/test_agent_run_manager.py` | Create | 验证运行目录、manifest、路径规划和汇总 |
| `tests/test_agent_batch_cli.py` | Create | 验证 `--agent --batch` 批量执行和兼容输出 |
| `tests/test_agent_partial_resume.py` | Create | 验证从中间 trace 恢复继续执行 |
| `tests/test_agent_retry.py` | Create | 验证 retry/backoff 策略 |
| `tests/test_agent_full_chain.py` | Create | fake model 的任务级全链路测试 |
| `docs/卷宗智能推理编目使用说明.md` | Modify | 更新第三阶段 agent 行为 |
| `docs/Smart_Case_Filing_Usage.en.md` | Modify | 英文同步说明 |
| `README.md` / `README.en.md` | Modify | 更新 agent 状态为批量可恢复 |
| `test-reports/agent-phase-three-fake-run.md` | Create | 第三阶段 fake full-chain 报告 |
| `test-reports/agent-phase-three-fake-run.json` | Create | 第三阶段 fake full-chain 结构化报告 |

---

## Task 1: Add Run Directory and Manifest Manager

**Files:**

- Create: `smart_case_filing/agent/run_manager.py`
- Create: `tests/test_agent_run_manager.py`

### Requirements

1. Generate a stable `run_id` for each agent invocation unless one is supplied.
2. Create a run directory:

```text
agent-runs/<run_id>/
  manifest.json
  traces/
  reviews/
  outputs/
```

3. Allocate per-file paths from a stable file id:

```text
traces/<file_id>.trace.jsonl
reviews/<file_id>.review.json
outputs/<file_id>.json
```

4. Manifest records:

```json
{
  "run_id": "...",
  "created_at": 1784126400.0,
  "updated_at": 1784126401.0,
  "status_counts": {
    "COMPLETED": 0,
    "NEEDS_REVIEW": 0,
    "FAILED": 0
  },
  "files": [
    {
      "file_id": "...",
      "file_path": "...",
      "agent_state": "COMPLETED",
      "confidence": "high",
      "trace": "...",
      "review": "",
      "output": "...",
      "error": ""
    }
  ]
}
```

### Acceptance

```bash
python -m unittest tests/test_agent_run_manager.py
```

Expected: `OK`

### Commit

```bash
git add smart_case_filing/agent/run_manager.py tests/test_agent_run_manager.py
git commit -m "feat: add agent run manifest manager"
```

---

## Task 2: Add Batch Agent Mode

**Files:**

- Modify: `file_directory_predictor.py`
- Modify: `smart_case_filing/agent/run_manager.py`
- Create: `tests/test_agent_batch_cli.py`

### Requirements

1. Support:

```bash
python file_directory_predictor.py \
  --batch ./input-files \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./agent-runs/demo \
  --review-output ./agent-runs/demo/reviews \
  --json
```

2. In batch agent mode, `--trace` is treated as a run directory if it points to a directory or has no `.jsonl` suffix.
3. Process only direct files, matching current non-agent batch semantics.
4. Each file gets independent trace, output, and optional review package.
5. CLI JSON output returns a batch summary with status counts and manifest path.
6. Non-agent `--batch` remains unchanged.

### Acceptance

```bash
python -m unittest tests/test_agent_batch_cli.py tests/test_cli_output.py
python -m unittest discover -s tests
```

Expected: `OK`

### Commit

```bash
git add file_directory_predictor.py smart_case_filing/agent/run_manager.py tests/test_agent_batch_cli.py
git commit -m "feat: add batch agent mode"
```

---

## Task 3: Implement Partial Resume

**Files:**

- Modify: `smart_case_filing/agent/runner.py`
- Modify: `file_directory_predictor.py`
- Create: `tests/test_agent_partial_resume.py`

### Requirements

1. Resume a partial single-file trace from the next incomplete step.
2. Reconstruct minimal context from trace summaries where possible.
3. If context is insufficient to continue safely, return `FAILED` with a clear reason.
4. Completed, failed, and needs-review traces still return summaries without re-running tools.
5. Batch resume reads manifest and resumes only unfinished files.

### State Mapping

| Last state | Resume behavior |
| --- | --- |
| `STARTED` | Run from `extract_content` |
| `EXTRACTED` | Continue from visual/text analysis if `_fc` can be rebuilt; otherwise fail clearly |
| `VISUAL_ANALYZED` | Continue from text analysis |
| `TEXT_ANALYZED` | Continue from candidate retrieval |
| `CANDIDATES_RETRIEVED` | Continue from catalog selection if candidates can be rebuilt; otherwise fail clearly |
| `MATCHED` | Continue from finalize prediction |
| `COMPLETED` | Return completed summary |
| `NEEDS_REVIEW` | Return needs-review summary |
| `FAILED` | Return failed summary |

### Acceptance

```bash
python -m unittest tests/test_agent_partial_resume.py tests/test_agent_resume.py
python -m unittest discover -s tests
```

Expected: `OK`

### Commit

```bash
git add smart_case_filing/agent/runner.py file_directory_predictor.py tests/test_agent_partial_resume.py
git commit -m "feat: support partial agent resume"
```

---

## Task 4: Add Retry and Backoff Policy

**Files:**

- Create: `smart_case_filing/agent/retry.py`
- Modify: `smart_case_filing/agent/runner.py`
- Create: `tests/test_agent_retry.py`

### Requirements

1. Define retry settings:

```text
max_attempts
initial_delay_seconds
backoff_factor
retryable_errors
```

2. Retry transient model/tool failures.
3. Do not retry deterministic validation failures, such as no candidates or invalid selected index.
4. Record attempt count and final error in trace summary.
5. Keep unit tests fast by allowing zero delay in tests.

### Acceptance

```bash
python -m unittest tests/test_agent_retry.py tests/test_agent_runner_v2.py
```

Expected: `OK`

### Commit

```bash
git add smart_case_filing/agent/retry.py smart_case_filing/agent/runner.py tests/test_agent_retry.py
git commit -m "feat: add agent retry policy"
```

---

## Task 5: Add Batch Review Index and Reports

**Files:**

- Modify: `smart_case_filing/agent/review.py`
- Modify: `smart_case_filing/agent/run_manager.py`
- Create or modify tests as needed

### Requirements

1. Create a review index for batch runs:

```text
agent-runs/<run_id>/reviews/index.json
```

2. Include every `NEEDS_REVIEW` and `FAILED` file.
3. Include trace path, review path, confidence, reasoning, and error.
4. Redact secrets.

### Acceptance

```bash
python -m unittest tests/test_agent_run_manager.py tests/test_agent_review.py
```

Expected: `OK`

### Commit

```bash
git add smart_case_filing/agent/review.py smart_case_filing/agent/run_manager.py tests
git commit -m "feat: add batch review index"
```

---

## Task 6: Full-chain Fake Test and Documentation

**Files:**

- Create: `tests/test_agent_full_chain.py`
- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/卷宗智能推理编目使用说明.md`
- Modify: `docs/Smart_Case_Filing_Usage.en.md`
- Create: `test-reports/agent-phase-three-fake-run.md`
- Create: `test-reports/agent-phase-three-fake-run.json`

### Requirements

1. Fake full-chain test covers:
   - batch agent command
   - one completed file
   - one needs-review file
   - one failed file
   - manifest
   - trace files
   - review index
   - resume command
2. Docs describe:
   - run directory
   - manifest
   - batch agent
   - partial resume
   - retry policy
   - real model smoke test prerequisites
3. Smoke test docs must state that real model smoke requires `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL` or available legacy `z-ai` CLI.

### Acceptance

```bash
python -m unittest discover -s tests
python file_directory_predictor.py --help
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

### Commit

```bash
git add tests/test_agent_full_chain.py README.md README.en.md docs/卷宗智能推理编目使用说明.md docs/Smart_Case_Filing_Usage.en.md test-reports/agent-phase-three-fake-run.md test-reports/agent-phase-three-fake-run.json
git commit -m "docs: document phase three agent mode"
```

---

## Final Verification

Run:

```bash
python -m unittest discover -s tests
python file_directory_predictor.py --help
```

Optional real model smoke, only when model configuration is available:

```bash
python file_directory_predictor.py \
  --batch ./test-reports \
  --catalog ./catalog-mapping.xlsx \
  --agent \
  --trace ./agent-runs/smoke \
  --review-output ./agent-runs/smoke/reviews \
  --json
```

---

## Completion Criteria

Phase three is complete only when:

- [ ] Batch agent mode works with direct files in a directory.
- [ ] Each file has independent trace, output, and optional review package.
- [ ] Run manifest records every file and status counts.
- [ ] Partial resume can continue supported interrupted traces or fail with a precise reason.
- [ ] Completed, failed, and needs-review traces do not rerun tools on resume.
- [ ] Retry/backoff policy is implemented and tested.
- [ ] Review index is generated for batch runs.
- [ ] Fake full-chain test covers completed, needs-review, failed, and resume paths.
- [ ] Existing non-agent CLI behavior remains compatible.
- [ ] Documentation describes actual third-stage behavior.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] Markdown local link check passes.

---

## Out of Scope for Phase Three

- Open-ended chat agent.
- Multi-agent framework.
- Web UI.
- SQLite or server database persistence.
- Model routing and cost optimization.
- Recursive directory traversal.
- Human approval UI.
