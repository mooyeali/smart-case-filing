# Agent Phase Seven Filing Plan Report

Date: 2026-07-16

## Scope

第七阶段补齐“预测结果到归档动作”的最后一公里：从单个 agent 输出 JSON 或批量 run manifest 生成可审计归档计划。默认 dry-run，不复制或移动文件；显式 `--agent-filing-apply` 后才执行 `copy` 或 `move`。

## Commands

Focused tests:

```bash
python -m unittest tests/test_agent_filing.py
```

Full regression:

```bash
python -m unittest discover -s tests
```

CLI help:

```bash
python file_directory_predictor.py --help
```

Dry-run filing plan:

```bash
python file_directory_predictor.py \
  --agent \
  --agent-filing-plan ./agent-runs/demo/manifest.json \
  --agent-filing-root ./filed-cases \
  --agent-filing-output ./agent-runs/demo/filing-plan.json \
  --json
```

Apply copy:

```bash
python file_directory_predictor.py \
  --agent \
  --agent-filing-plan ./agent-runs/demo/manifest.json \
  --agent-filing-root ./filed-cases \
  --agent-filing-action copy \
  --agent-filing-apply \
  --agent-filing-output ./agent-runs/demo/filing-plan.applied.json \
  --json
```

## Plan Shape

```json
{
  "agent_state": "FILING_PLAN_CREATED",
  "source": "./agent-runs/demo/manifest.json",
  "filing_root": "./filed-cases",
  "action": "copy",
  "apply": false,
  "item_count": 3,
  "status_counts": {
    "ready": 1,
    "blocked": 2
  },
  "items": [
    {
      "source": "input/complaint.txt",
      "target": "filed-cases/civil/main/complaints/complaint/complaint.txt",
      "action": "copy",
      "status": "ready",
      "reason": "",
      "agent_state": "COMPLETED",
      "confidence": "high"
    }
  ]
}
```

## Safety Rules

- `COMPLETED` and non-`low` confidence are required for `ready`.
- `NEEDS_REVIEW`, `FAILED`, low confidence, missing source files, incomplete prediction fields, and existing target files are `blocked`.
- Target path parts are sanitized before filesystem paths are built.
- Dry-run is the default and does not create target files.
- Apply mode never overwrites an existing target file.

## Verification Result

Focused tests added in `tests/test_agent_filing.py` cover:

- path sanitization;
- single output dry-run plan;
- manifest plan with review, failed, and low-confidence blocks;
- apply copy;
- apply move;
- CLI output and plan file writing.

