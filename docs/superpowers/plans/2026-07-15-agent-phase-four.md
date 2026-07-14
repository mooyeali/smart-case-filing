# Smart Case Filing Agent Phase Four Implementation Plan

**Goal:** 将第三阶段的批量可恢复 agent 增强为“可运营的批量编目 agent 闭环”，补齐 batch review 目录语义、batch resume 持久化、CLI retry 配置、模型配置 preflight、review decision 记录和文档化全链路报告。

**Source:** `docs/agent/智能体升级第四阶段圆桌会议纪要.md`

**Architecture:** 不引入 Web UI、数据库或多 Agent 框架。继续使用 JSONL trace、JSON manifest、review package 和 CLI。增强点集中在 `AgentRunManager`、`ReviewPackageWriter`、`AgentRunner` 参数装配和 `file_directory_predictor.py` 的 agent CLI 边界。

---

## Task 1: Honor Batch Review Output Directory

**Files:**

- Modify: `smart_case_filing/agent/run_manager.py`
- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_batch_cli.py`

**Requirements:**

1. In batch agent mode, `--review-output <dir>` controls where per-file review packages and `index.json` are written.
2. If `--review-output` is not provided, keep the current default: `<run_dir>/reviews`.
3. Manifest `review` fields point to the actual review directory.
4. Existing single-file `--review-output <file>` behavior remains compatible.

**Acceptance:**

```bash
python -m unittest tests/test_agent_batch_cli.py tests/test_agent_run_manager.py
```

**Commit:**

```bash
git add smart_case_filing/agent/run_manager.py file_directory_predictor.py tests/test_agent_batch_cli.py
git commit -m "feat: honor batch review output directory"
```

---

## Task 2: Persist Batch Resume Results

**Files:**

- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_partial_resume.py`
- Modify: `tests/test_agent_full_chain.py`

**Requirements:**

1. Batch resume updates manifest entries for resumed files.
2. Batch resume writes per-file output JSON for resumed files.
3. Batch resume writes review packages for resumed `NEEDS_REVIEW` or `FAILED` files.
4. Batch resume rebuilds `reviews/index.json`.
5. Terminal files remain skipped and are not rerun.

**Acceptance:**

```bash
python -m unittest tests/test_agent_partial_resume.py tests/test_agent_full_chain.py
```

**Commit:**

```bash
git add file_directory_predictor.py tests/test_agent_partial_resume.py tests/test_agent_full_chain.py
git commit -m "feat: persist batch resume results"
```

---

## Task 3: Expose Retry Policy in CLI

**Files:**

- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_retry.py`

**Requirements:**

1. Add CLI flags:
   - `--agent-retry-attempts`
   - `--agent-retry-delay`
   - `--agent-retry-backoff`
   - `--agent-retry-errors`
2. Defaults preserve existing behavior: one attempt and no delay.
3. Single-file, batch, and resume agent runners use the configured retry policy.
4. `--agent-retry-errors` accepts comma-separated substrings.

**Acceptance:**

```bash
python -m unittest tests/test_agent_retry.py tests/test_agent_cli_integration.py tests/test_agent_batch_cli.py
```

**Commit:**

```bash
git add file_directory_predictor.py tests/test_agent_retry.py
git commit -m "feat: expose agent retry cli options"
```

---

## Task 4: Add Model Configuration Preflight

**Files:**

- Create: `smart_case_filing/agent/preflight.py`
- Modify: `file_directory_predictor.py`
- Create: `tests/test_agent_preflight.py`

**Requirements:**

1. Add CLI flag `--agent-preflight`.
2. Preflight returns JSON with:
   - HTTP model configured: `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`
   - legacy `z-ai` availability from PATH
   - selected mode: `http`, `legacy-z-ai`, or `unconfigured`
3. Preflight does not call network APIs.
4. Preflight can run without file or batch input.

**Acceptance:**

```bash
python -m unittest tests/test_agent_preflight.py
python file_directory_predictor.py --agent --agent-preflight --json
```

**Commit:**

```bash
git add smart_case_filing/agent/preflight.py file_directory_predictor.py tests/test_agent_preflight.py
git commit -m "feat: add agent model preflight"
```

---

## Task 5: Add Review Decision Records

**Files:**

- Modify: `smart_case_filing/agent/review.py`
- Modify: `smart_case_filing/agent/run_manager.py`
- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_review.py`
- Modify: `tests/test_agent_run_manager.py`

**Requirements:**

1. Add CLI flag `--review-decision <json>`.
2. Decision JSON supports:

```json
{
  "file_id": "...",
  "file_path": "...",
  "decision": "approved|corrected|rejected",
  "final_prediction": {},
  "reviewer": "",
  "notes": ""
}
```

3. Decision files are written under `<run_dir>/decisions/<file_id>.decision.json`.
4. Manifest records `decision`, `decision_path`, and `reviewed_at`.
5. API keys are redacted.

**Acceptance:**

```bash
python -m unittest tests/test_agent_review.py tests/test_agent_run_manager.py
```

**Commit:**

```bash
git add smart_case_filing/agent/review.py smart_case_filing/agent/run_manager.py file_directory_predictor.py tests/test_agent_review.py tests/test_agent_run_manager.py
git commit -m "feat: add review decision records"
```

---

## Task 6: Documentation and Full Verification

**Files:**

- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/卷宗智能推理编目使用说明.md`
- Modify: `docs/Smart_Case_Filing_Usage.en.md`
- Create: `test-reports/agent-phase-four-fake-run.md`
- Create: `test-reports/agent-phase-four-fake-run.json`

**Requirements:**

1. Document:
   - batch `--review-output` directory semantics
   - persistent batch resume
   - retry CLI flags
   - `--agent-preflight`
   - `--review-decision`
2. Fake run report covers:
   - preflight
   - batch run
   - batch resume persistence
   - review decision record
3. Run final verification:

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

**Commit:**

```bash
git add README.md README.en.md docs/卷宗智能推理编目使用说明.md docs/Smart_Case_Filing_Usage.en.md test-reports/agent-phase-four-fake-run.md test-reports/agent-phase-four-fake-run.json
git commit -m "docs: document phase four agent operations"
```

---

## Completion Criteria

- [ ] Batch `--review-output` directory is honored.
- [ ] Batch resume persists outputs, manifest, review packages, and review index.
- [ ] Retry policy is configurable from CLI.
- [ ] `--agent-preflight` works without input files and does not call network APIs.
- [ ] Review decision files are written and indexed in manifest.
- [ ] Existing single-file and non-agent CLI behavior remains compatible.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] `python file_directory_predictor.py --help` passes.
- [ ] Markdown local link check passes.
- [ ] All changes are committed and pushed.

---

## Out of Scope for Phase Four

- Web UI.
- SQLite or server database persistence.
- Recursive directory traversal.
- Online human approval system.
- Multi-agent framework.
