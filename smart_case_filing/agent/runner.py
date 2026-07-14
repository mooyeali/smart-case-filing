from __future__ import annotations

from copy import deepcopy

from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult
from smart_case_filing.model_client import redact_secret


def _safe_summary(value):
    if isinstance(value, dict):
        return {
            key: _safe_summary(inner)
            for key, inner in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, list):
        return [_safe_summary(item) for item in value[:20]]
    if isinstance(value, tuple):
        return [_safe_summary(item) for item in value[:20]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, str) and len(value) > 500:
            return value[:500] + "...[truncated]"
        return value
    return repr(value)


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
            input_summary=_safe_summary(input_summary),
            output_summary=_safe_summary(result.data if result.ok else {}),
            error=redact_secret(result.error),
        ))

    def _run_tool(self, run_id: str, file_path: str, state: AgentState,
                  tool: str, payload: dict) -> ToolResult:
        result = self.tools.run(tool, payload)
        self._record(run_id, file_path, state, tool, payload, result)
        return result

    def run(self, run_id: str, file_path: str) -> dict:
        start = ToolResult(ok=True, data={"file_path": file_path})
        self._record(run_id, file_path, AgentState.STARTED, "start", {}, start)

        context = {"file_path": file_path}
        extracted = self._run_tool(
            run_id, file_path, AgentState.EXTRACTED, "extract_content", context
        )
        if not extracted.ok:
            return {"state": AgentState.FAILED, "error": extracted.error}
        context.update(extracted.data)

        if context.get("image_count", 0) or getattr(context.get("_fc"), "has_visual", lambda: False)():
            visual = self._run_tool(run_id, file_path, AgentState.VISUAL_ANALYZED, "analyze_visual", context)
        else:
            visual = ToolResult(ok=True, data={
                "vlm_analysis": {"available": False, "skipped": True, "reason": "no visual input"}
            })
            self._record(run_id, file_path, AgentState.VISUAL_ANALYZED, "analyze_visual", context, visual)
        if not visual.ok:
            return {"state": AgentState.FAILED, "error": visual.error}
        context.update(visual.data)

        if context.get("text_length", 0):
            text = self._run_tool(run_id, file_path, AgentState.TEXT_ANALYZED, "analyze_text", context)
        else:
            text = ToolResult(ok=True, data={
                "llm_analysis": {"available": False, "skipped": True, "reason": "no text input"}
            })
            self._record(run_id, file_path, AgentState.TEXT_ANALYZED, "analyze_text", context, text)
        if not text.ok:
            return {"state": AgentState.FAILED, "error": text.error}
        context.update(text.data)

        candidates = self._run_tool(
            run_id, file_path, AgentState.CANDIDATES_RETRIEVED, "retrieve_candidates", context
        )
        if not candidates.ok:
            return {"state": AgentState.FAILED, "error": candidates.error}
        context.update(candidates.data)

        match = self._run_tool(run_id, file_path, AgentState.MATCHED, "select_catalog", context)
        if not match.ok:
            return {"state": AgentState.FAILED, "error": match.error}
        context.update(match.data)

        final = self._run_tool(run_id, file_path, AgentState.COMPLETED, "finalize_prediction", context)
        if not final.ok:
            return {"state": AgentState.FAILED, "error": final.error}
        context.update(final.data)

        state = AgentState.COMPLETED if final.data.get("confidence") != "low" else AgentState.NEEDS_REVIEW
        if state == AgentState.NEEDS_REVIEW:
            review_result = ToolResult(ok=True, data={"agent_state": state.value, "prediction": final.data})
            self._record(run_id, file_path, AgentState.NEEDS_REVIEW, "needs_review", context, review_result)
        return {"state": state, "prediction": final.data}
