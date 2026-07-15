# Smart Case Filing Agent Phase Six Implementation Plan

**Goal:** 提供一个可执行、无模型依赖、可重复的 agent 全链路验收入口，生成完整 fake run 产物并自动 audit/export report。

**Source:** `docs/agent/智能体升级第六阶段圆桌会议纪要.md`

**Architecture:** 不改变真实预测流程。新增 `smart_case_filing/agent/full_chain.py`，用 fake tools 驱动现有 `AgentRunner`、`AgentRunManager`、review decision、audit/report 能力，作为本地验收 harness。CLI 新增 `--agent-full-chain-test <output-dir>`。

---

## Task 1: Add Fake Full-chain Runner

**Files:**

- Create: `smart_case_filing/agent/full_chain.py`
- Create: `tests/test_agent_full_chain_cli.py`

**Requirements:**

1. `run_fake_full_chain(output_dir)` creates:
   - input files
   - run directory
   - manifest
   - traces
   - outputs
   - review packages
   - review index
   - review decision
   - audit Markdown report
   - audit JSON report
2. The fake run includes one `COMPLETED`, one `NEEDS_REVIEW`, and one `FAILED` file.
3. Return summary with paths and audit result.

**Acceptance:**

```bash
python -m unittest tests/test_agent_full_chain_cli.py
```

**Commit:**

```bash
git add smart_case_filing/agent/full_chain.py tests/test_agent_full_chain_cli.py
git commit -m "feat: add fake agent full chain runner"
```

---

## Task 2: Add Full-chain CLI

**Files:**

- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_full_chain_cli.py`

**Requirements:**

1. Add `--agent-full-chain-test <output-dir>`.
2. Command runs without input files.
3. Prints JSON summary.
4. Works through existing `--output` and `--log`.

**Acceptance:**

```bash
python -m unittest tests/test_agent_full_chain_cli.py
python file_directory_predictor.py --agent --agent-full-chain-test ./test-reports/agent-full-chain-smoke --json
```

**Commit:**

```bash
git add file_directory_predictor.py tests/test_agent_full_chain_cli.py
git commit -m "feat: add agent full chain test cli"
```

---

## Task 3: Documentation and Report

**Files:**

- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/卷宗智能推理编目使用说明.md`
- Modify: `docs/Smart_Case_Filing_Usage.en.md`
- Create: `test-reports/agent-phase-six-full-chain.md`
- Create: `test-reports/agent-phase-six-full-chain.json`

**Requirements:**

1. Document `--agent-full-chain-test`.
2. Report includes command, generated paths, audit result shape, and test commands.
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
git add README.md README.en.md docs/卷宗智能推理编目使用说明.md docs/Smart_Case_Filing_Usage.en.md test-reports/agent-phase-six-full-chain.md test-reports/agent-phase-six-full-chain.json
git commit -m "docs: document phase six full chain test"
```

---

## Completion Criteria

- [ ] `run_fake_full_chain()` generates a valid full run.
- [ ] CLI `--agent-full-chain-test` runs without input files.
- [ ] Generated run passes `audit_run()`.
- [ ] Markdown and JSON reports are generated.
- [ ] Existing tests pass.
- [ ] Help output includes the new flag.
- [ ] Markdown local link check passes.
- [ ] All changes are committed and pushed.
