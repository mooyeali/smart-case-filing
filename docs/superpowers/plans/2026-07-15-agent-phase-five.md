# Smart Case Filing Agent Phase Five Implementation Plan

**Goal:** 将第四阶段的可运营批量 agent 增强为“可验收、可归档的批量 agent 运行产物”，提供 run manifest 机器校验、缺失产物诊断、Markdown/JSON 报告导出和最终验收门禁。

**Source:** `docs/agent/智能体升级第五阶段圆桌会议纪要.md`

**Architecture:** 第五阶段只新增只读 audit/report 能力，不改变核心预测流程。`smart_case_filing/agent/audit.py` 读取 manifest、trace/output/review/decision 文件和 review index，返回结构化校验结果；CLI 负责打印或导出报告。

---

## Task 1: Add Run Audit Helper

**Files:**

- Create: `smart_case_filing/agent/audit.py`
- Create: `tests/test_agent_audit.py`

**Requirements:**

1. `audit_run(manifest_or_run_dir)` accepts a manifest path or run directory.
2. Validate:
   - manifest exists and parses as JSON
   - manifest has `files`
   - status counts match file entries
   - each file has trace and output paths that exist
   - `NEEDS_REVIEW` and `FAILED` files have review paths that exist
   - review index exists and covers all reviewable files
   - decision paths exist when recorded
3. Return:

```json
{
  "valid": true,
  "manifest": "...",
  "run_id": "...",
  "status_counts": {},
  "file_count": 0,
  "review_count": 0,
  "decision_count": 0,
  "issues": [],
  "files": []
}
```

**Acceptance:**

```bash
python -m unittest tests/test_agent_audit.py
```

**Commit:**

```bash
git add smart_case_filing/agent/audit.py tests/test_agent_audit.py
git commit -m "feat: add agent run audit"
```

---

## Task 2: Add Validate Run CLI

**Files:**

- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_audit.py`

**Requirements:**

1. Add `--agent-validate-run <manifest-or-run-dir>`.
2. Validation runs without input file or batch.
3. Print JSON audit result.
4. Exit through existing output/log capture.

**Acceptance:**

```bash
python -m unittest tests/test_agent_audit.py
python file_directory_predictor.py --agent --agent-validate-run ./missing --json
```

**Commit:**

```bash
git add file_directory_predictor.py tests/test_agent_audit.py
git commit -m "feat: add agent validate run cli"
```

---

## Task 3: Add Report Export

**Files:**

- Modify: `smart_case_filing/agent/audit.py`
- Modify: `file_directory_predictor.py`
- Modify: `tests/test_agent_audit.py`

**Requirements:**

1. Add `build_run_report(audit_result, format="md|json")`.
2. Add CLI `--agent-export-report <path>`.
3. When used with `--agent-validate-run`, write the report to path.
4. `.json` suffix writes JSON; other suffixes write Markdown.
5. Report includes run id, manifest path, status counts, issue list, review count, decision count, and per-file summary.

**Acceptance:**

```bash
python -m unittest tests/test_agent_audit.py
```

**Commit:**

```bash
git add smart_case_filing/agent/audit.py file_directory_predictor.py tests/test_agent_audit.py
git commit -m "feat: export agent run audit reports"
```

---

## Task 4: Documentation and Fake Report

**Files:**

- Modify: `README.md`
- Modify: `README.en.md`
- Modify: `docs/卷宗智能推理编目使用说明.md`
- Modify: `docs/Smart_Case_Filing_Usage.en.md`
- Create: `test-reports/agent-phase-five-fake-run.md`
- Create: `test-reports/agent-phase-five-fake-run.json`

**Requirements:**

1. Document:
   - `--agent-validate-run`
   - `--agent-export-report`
   - audit checks
   - report formats
2. Fake report demonstrates:
   - valid run audit
   - missing artifact audit issue
   - Markdown report export
   - JSON report export

**Acceptance:**

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
git add README.md README.en.md docs/卷宗智能推理编目使用说明.md docs/Smart_Case_Filing_Usage.en.md test-reports/agent-phase-five-fake-run.md test-reports/agent-phase-five-fake-run.json
git commit -m "docs: document phase five agent audit"
```

---

## Completion Criteria

- [ ] `audit_run()` validates complete run directories.
- [ ] Missing trace/output/review/decision artifacts produce explicit issues.
- [ ] Review index coverage is checked.
- [ ] `--agent-validate-run` works without input files.
- [ ] `--agent-export-report` writes Markdown and JSON reports.
- [ ] Existing agent prediction flows remain compatible.
- [ ] `python -m unittest discover -s tests` passes.
- [ ] `python file_directory_predictor.py --help` passes.
- [ ] Markdown local link check passes.
- [ ] All changes are committed and pushed.

---

## Out of Scope for Phase Five

- Web UI.
- Database persistence.
- Automatic artifact repair.
- Recursive directory traversal.
- Online review approval workflow.
