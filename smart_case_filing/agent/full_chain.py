from __future__ import annotations

import json
import shutil
from pathlib import Path

from smart_case_filing.agent.audit import audit_run, build_run_report
from smart_case_filing.agent.review import ReviewPackageWriter, build_review_payload
from smart_case_filing.agent.run_manager import AgentRunManager
from smart_case_filing.agent.runner import AgentRunner
from smart_case_filing.agent.state import AgentState, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


def _fake_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()

    def file_name(payload):
        return Path(payload["file_path"]).name

    registry.register("extract_content", lambda payload: ToolResult(ok=True, data={
        "file_path": payload["file_path"],
        "file_type": "text",
        "text_length": 24,
        "text_preview": "fake full chain content",
        "image_count": 0,
    }))
    registry.register("analyze_visual", lambda payload: ToolResult(ok=True, data={
        "vlm_analysis": {"available": False, "skipped": True}
    }))
    registry.register("analyze_text", lambda payload: ToolResult(ok=True, data={
        "llm_analysis": {
            "available": True,
            "doc_type_guess": "complaint",
            "confidence": "high",
        }
    }))

    def retrieve_candidates(payload):
        if "failed" in file_name(payload):
            return ToolResult(ok=False, error="no catalog candidates")
        return ToolResult(ok=True, data={
            "candidate_count": 1,
            "candidate_summaries": [{"material_category": "complaint"}],
        })

    registry.register("retrieve_candidates", retrieve_candidates)

    def select_catalog(payload):
        confidence = "low" if "review" in file_name(payload) else "high"
        return ToolResult(ok=True, data={
            "match": {
                "case_type": "civil",
                "volume": "main",
                "second_level_directory": "complaints",
                "material_category": "complaint",
                "catalog_name_example": "complaint",
                "confidence": confidence,
                "reasoning": "fake full-chain selection",
            },
            "candidate_summaries": [{"material_category": "complaint"}],
        })

    registry.register("select_catalog", select_catalog)
    registry.register("finalize_prediction", lambda payload: ToolResult(ok=True, data={
        "file_path": payload["file_path"],
        "file_type": "text",
        "predicted_case_type": payload["match"]["case_type"],
        "predicted_volume": payload["match"]["volume"],
        "predicted_second_level_directory": payload["match"]["second_level_directory"],
        "predicted_material_category": payload["match"]["material_category"],
        "predicted_catalog_example": payload["match"]["catalog_name_example"],
        "confidence": payload["match"]["confidence"],
        "reasoning": payload["match"]["reasoning"],
        "vlm_analysis": payload.get("vlm_analysis", {}),
        "llm_analysis": payload.get("llm_analysis", {}),
        "matched_entries": [],
        "candidate_summaries": payload.get("candidate_summaries", []),
    }))
    return registry


def _output_from_result(result: dict, trace_path: Path, review_path: Path) -> dict:
    state = result.get("state", AgentState.FAILED)
    state_value = state.value if hasattr(state, "value") else str(state)
    output = dict(result.get("prediction") or {})
    output.update({
        "agent_state": state_value,
        "state": state_value,
        "trace": str(trace_path),
        "review_output": str(review_path),
        "resume": "",
    })
    if result.get("error"):
        output["error"] = result["error"]
    return output


def run_fake_full_chain(output_dir) -> dict:
    output_dir = Path(output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_dir = output_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    for name in ("completed.txt", "review.txt", "failed.txt"):
        (input_dir / name).write_text(name, encoding="utf-8")

    run_dir = output_dir / "run"
    reviews_dir = output_dir / "reviews"
    manager = AgentRunManager(run_dir, run_id="run", reviews_dir=reviews_dir)
    manager.ensure()
    registry = _fake_registry()

    for file_path in sorted(input_dir.iterdir()):
        paths = manager.paths_for(str(file_path))
        result = AgentRunner(registry, AgentTraceStore(paths["trace"])).run(
            run_id=manager.run_id,
            file_path=str(file_path),
        )
        output = _output_from_result(result, paths["trace"], paths["review"])
        paths["output"].parent.mkdir(parents=True, exist_ok=True)
        paths["output"].write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if output["agent_state"] in {AgentState.NEEDS_REVIEW.value, AgentState.FAILED.value}:
            ReviewPackageWriter(paths["review"]).write(build_review_payload(output, str(paths["trace"])))
        manager.record_file(str(file_path), output, paths)

    review_index = manager.write_review_index()
    manifest = manager.load_manifest()
    review_item = next(item for item in manifest["files"] if item["agent_state"] == AgentState.NEEDS_REVIEW.value)
    decision = manager.record_decision({
        "file_id": review_item["file_id"],
        "file_path": review_item["file_path"],
        "decision": "approved",
        "reviewer": "fake-reviewer",
        "notes": "fake full-chain approval",
    })

    audit = audit_run(manager.manifest_path)
    audit_md = output_dir / "audit.md"
    audit_json = output_dir / "audit.json"
    audit_md.write_text(build_run_report(audit, format="md"), encoding="utf-8")
    audit_json.write_text(build_run_report(audit, format="json"), encoding="utf-8")

    return {
        "agent_state": "FULL_CHAIN_TEST_COMPLETED",
        "output_dir": str(output_dir),
        "input_dir": str(input_dir),
        "run_dir": str(manager.run_dir),
        "manifest": str(manager.manifest_path),
        "review_index": str(review_index),
        "decision_path": decision["decision_path"],
        "audit_report_md": str(audit_md),
        "audit_report_json": str(audit_json),
        "audit": audit,
    }
