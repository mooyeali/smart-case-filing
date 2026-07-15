# Smart Case Filing Agent Phase Seven Implementation Plan

**Goal:** 新增可审计归档计划与安全演练执行能力，将 agent 预测结果或 run manifest 转换为可执行 copy / move 计划，默认 dry-run。

**Source:** `docs/agent/智能体升级第七阶段圆桌会议纪要.md`

**Architecture:** 不改变现有模型调用、预测、批量、复核、resume、audit 流程。新增 `smart_case_filing/agent/filing.py` 作为归档计划 helper，并在 CLI 中增加归档计划入口。CLI 读取现有 agent 输出 JSON 或 run manifest，生成 plan JSON；默认不改动文件系统，显式 `--agent-filing-apply` 时才执行 copy / move。

---

## Task 1: Add Filing Plan Helper

**Files:**

- Create: `smart_case_filing/agent/filing.py`
- Create: `tests/test_agent_filing.py`

**Requirements:**

1. 从单个 agent 输出 dict 生成归档计划 item。
2. 从 run manifest 读取每个文件 output，生成多文件归档计划。
3. 目标路径由 `predicted_case_type / predicted_volume / predicted_second_level_directory / predicted_material_category / source_name` 组成。
4. 路径片段要做安全清洗，避免空值、路径分隔符和非法字符污染目标目录。
5. 只有 `agent_state == COMPLETED` 且 `confidence != low` 的文件可执行。
6. `NEEDS_REVIEW`、`FAILED`、low confidence 和字段不完整的文件必须标记为 blocked，并写明 reason。

**Acceptance:**

```bash
python -m unittest tests/test_agent_filing.py
```

**Commit:**

```bash
git add smart_case_filing/agent/filing.py tests/test_agent_filing.py
git commit -m "feat: add agent filing plan helper"
```

---

## Task 2: Add Filing Plan CLI

**Files:**

- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_filing.py`

**Requirements:**

1. Add `--agent-filing-plan <agent-output-or-manifest-json>`.
2. Add `--agent-filing-root <dir>` as required output root for filing plans.
3. Add `--agent-filing-action copy|move`, default `copy`.
4. Add `--agent-filing-apply`, default false.
5. Add `--agent-filing-output <plan-json>` for writing plan artifacts.
6. CLI prints JSON summary and respects existing `--output` / `--log` redirection.

**Acceptance:**

```bash
python -m unittest tests/test_agent_filing.py
python file_directory_predictor.py --agent --agent-filing-plan <manifest.json> --agent-filing-root ./filing-out --agent-filing-output ./filing-plan.json
```

**Commit:**

```bash
git add file_directory_predictor.py tests/test_agent_filing.py
git commit -m "feat: add agent filing plan cli"
```

---

## Task 3: Documentation and Report

**Files:**

- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/卷宗智能推理编目使用说明.md`
- Modify: `docs/Smart_Case_Filing_Usage.en.md`
- Create: `test-reports/agent-phase-seven-filing.md`
- Create: `test-reports/agent-phase-seven-filing.json`

**Requirements:**

1. Document the filing plan command and safety rules.
2. Document dry-run vs apply behavior.
3. Report includes command, sample plan shape, blocked item rules, and verification commands.
4. Run final verification:

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
git add README.md README.en.md docs/卷宗智能推理编目使用说明.md docs/Smart_Case_Filing_Usage.en.md test-reports/agent-phase-seven-filing.md test-reports/agent-phase-seven-filing.json
git commit -m "docs: document phase seven filing plan"
```

---

## Completion Criteria

- [ ] Single agent output can produce a filing plan.
- [ ] Run manifest can produce a multi-file filing plan.
- [ ] Blocked files are explicit and explainable.
- [ ] Dry-run does not create target files.
- [ ] Apply copy creates target files.
- [ ] Existing tests pass.
- [ ] Help output includes the new filing flags.
- [ ] Markdown local link check passes.
- [ ] All changes are committed and pushed.
