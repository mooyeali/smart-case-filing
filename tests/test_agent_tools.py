import unittest

from smart_case_filing.agent.tools import AgentToolRegistry, ToolResult


class AgentToolRegistryTest(unittest.TestCase):
    def test_registers_and_runs_tool(self):
        registry = AgentToolRegistry()
        registry.register("echo", lambda payload: ToolResult(ok=True, data={"value": payload["value"]}))

        result = registry.run("echo", {"value": "hello"})

        self.assertTrue(result.ok)
        self.assertEqual({"value": "hello"}, result.data)

    def test_unknown_tool_returns_failure(self):
        registry = AgentToolRegistry()
        result = registry.run("missing", {})

        self.assertFalse(result.ok)
        self.assertIn("unknown tool", result.error)


if __name__ == "__main__":
    unittest.main()
