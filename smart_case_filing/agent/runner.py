from __future__ import annotations

from copy import deepcopy

from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult
from smart_case_filing.agent.retry import NO_RETRY, RetryPolicy
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
    def __init__(self, tools: AgentToolRegistry, trace_store: AgentTraceStore,
                 retry_policy: RetryPolicy | None = None):
        self.tools = tools
        self.trace_store = trace_store
        self.retry_policy = retry_policy or NO_RETRY

    def _record(self, run_id: str, file_path: str, state: AgentState, tool: str,
                input_summary: dict, result: ToolResult) -> None:
        self.trace_store.append(AgentStep(
            run_id=run_id,
            file_path=file_path,
            state=state,
            tool=tool,
            input_summary=_safe_summary(input_summary),
            output_summary=_safe_summary(result.data or {}),
            error=redact_secret(result.error),
        ))

    def _run_tool(self, run_id: str, file_path: str, state: AgentState,
                  tool: str, payload: dict) -> ToolResult:
        result = self.retry_policy.run(lambda: self.tools.run(tool, payload))
        self._record(run_id, file_path, state, tool, payload, result)
        return result

    def run(self, run_id: str, file_path: str) -> dict:
        return self._run_flow(run_id, file_path, start_after=None, context={"file_path": file_path})

    def resume(self, run_id: str, file_path: str, steps: list[AgentStep]) -> dict:
        if not steps:
            return self.run(run_id, file_path)

        last = steps[-1]
        if last.state in {AgentState.COMPLETED, AgentState.NEEDS_REVIEW}:
            return {"state": last.state, "prediction": dict(last.output_summary or {})}
        if last.state == AgentState.FAILED:
            return {"state": AgentState.FAILED, "error": last.error or "agent run failed"}

        context = {"file_path": file_path}
        for step in steps:
            context.update(step.output_summary or {})
        return self._run_flow(run_id, file_path, start_after=last.state, context=context)

    def _run_flow(self, run_id: str, file_path: str, start_after: AgentState | None, context: dict) -> dict:
        if start_after is None:
            start = ToolResult(ok=True, data={"file_path": file_path})
            self._record(run_id, file_path, AgentState.STARTED, "start", {}, start)

        if start_after is None or start_after == AgentState.STARTED:
            extracted = self._run_tool(
                run_id, file_path, AgentState.EXTRACTED, "extract_content", context
            )
            if not extracted.ok:
                return {"state": AgentState.FAILED, "error": extracted.error}
            context.update(extracted.data)
        elif start_after in {
            AgentState.EXTRACTED,
            AgentState.VISUAL_ANALYZED,
            AgentState.TEXT_ANALYZED,
            AgentState.CANDIDATES_RETRIEVED,
            AgentState.MATCHED,
        }:
            pass
        else:
            return {"state": AgentState.FAILED, "error": f"cannot resume from state: {start_after.value}"}

        if start_after not in {AgentState.VISUAL_ANALYZED, AgentState.TEXT_ANALYZED,
                               AgentState.CANDIDATES_RETRIEVED, AgentState.MATCHED}:
            if start_after == AgentState.EXTRACTED and not context.get("_fc"):
                return {
                    "state": AgentState.FAILED,
                    "error": "cannot resume after EXTRACTED: extracted file content is not available in trace",
                }
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

        if start_after in {AgentState.TEXT_ANALYZED, AgentState.CANDIDATES_RETRIEVED, AgentState.MATCHED}:
            pass
        else:
            if start_after == AgentState.VISUAL_ANALYZED and context.get("text_length", 0) and not context.get("_fc"):
                return {
                    "state": AgentState.FAILED,
                    "error": "cannot resume after VISUAL_ANALYZED: extracted file content is not available in trace",
                }
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

        if start_after in {AgentState.CANDIDATES_RETRIEVED, AgentState.MATCHED}:
            pass
        else:
            candidates = self._run_tool(
                run_id, file_path, AgentState.CANDIDATES_RETRIEVED, "retrieve_candidates", context
            )
            if not candidates.ok:
                return {"state": AgentState.FAILED, "error": candidates.error}
            context.update(candidates.data)

        if start_after == AgentState.MATCHED:
            pass
        else:
            if start_after == AgentState.CANDIDATES_RETRIEVED and not context.get("_candidates"):
                return {
                    "state": AgentState.FAILED,
                    "error": "cannot resume after CANDIDATES_RETRIEVED: candidate objects are not available in trace",
                }
            match = self._run_tool(run_id, file_path, AgentState.MATCHED, "select_catalog", context)
            if not match.ok:
                return {"state": AgentState.FAILED, "error": match.error}
            context.update(match.data)

        if start_after == AgentState.MATCHED and not context.get("match"):
            return {
                "state": AgentState.FAILED,
                "error": "cannot resume after MATCHED: match payload is not available in trace",
            }
        final = self._run_tool(run_id, file_path, AgentState.COMPLETED, "finalize_prediction", context)
        if not final.ok:
            return {"state": AgentState.FAILED, "error": final.error}
        context.update(final.data)

        state = AgentState.COMPLETED if final.data.get("confidence") != "low" else AgentState.NEEDS_REVIEW
        if state == AgentState.NEEDS_REVIEW:
            review_result = ToolResult(ok=True, data={"agent_state": state.value, "prediction": final.data})
            self._record(run_id, file_path, AgentState.NEEDS_REVIEW, "needs_review", context, review_result)
        return {"state": state, "prediction": final.data}
