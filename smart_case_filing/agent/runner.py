from __future__ import annotations

from smart_case_filing.agent.state import AgentState, AgentStep, AgentTraceStore
from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


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
            input_summary=input_summary,
            output_summary=result.data if result.ok else {},
            error=result.error,
        ))

    def _run_tool(self, run_id: str, file_path: str, state: AgentState,
                  tool: str, payload: dict) -> ToolResult:
        result = self.tools.run(tool, payload)
        self._record(run_id, file_path, state, tool, payload, result)
        return result

    def run(self, run_id: str, file_path: str) -> dict:
        start = ToolResult(ok=True, data={"file_path": file_path})
        self._record(run_id, file_path, AgentState.STARTED, "start", {}, start)

        extracted = self._run_tool(
            run_id, file_path, AgentState.EXTRACTED, "extract_content", {"file_path": file_path}
        )
        if not extracted.ok:
            return {"state": AgentState.FAILED, "error": extracted.error}

        text = self._run_tool(run_id, file_path, AgentState.TEXT_ANALYZED, "analyze_text", extracted.data)
        if not text.ok:
            return {"state": AgentState.FAILED, "error": text.error}

        candidates = self._run_tool(
            run_id, file_path, AgentState.CANDIDATES_RETRIEVED, "retrieve_candidates", text.data
        )
        if not candidates.ok:
            return {"state": AgentState.FAILED, "error": candidates.error}

        match_payload = dict(candidates.data)
        match_payload.update(text.data)
        match = self._run_tool(run_id, file_path, AgentState.MATCHED, "select_catalog", match_payload)
        if not match.ok:
            return {"state": AgentState.FAILED, "error": match.error}

        state = AgentState.COMPLETED if match.data.get("confidence") != "low" else AgentState.NEEDS_REVIEW
        return {"state": state, "prediction": match.data}
