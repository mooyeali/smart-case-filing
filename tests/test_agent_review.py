import json
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.review import (
    ReviewPackageWriter,
    build_review_decision_payload,
    build_review_index_payload,
    build_review_payload,
)


class ReviewPackageWriterTest(unittest.TestCase):
    def test_writes_review_json_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.json"
            writer = ReviewPackageWriter(path)
            writer.write({
                "file_path": "case.pdf",
                "confidence": "low",
                "reasoning": "Authorization: Bearer sk-1234567890abcdef",
                "candidates": [{"material_category": "起诉状"}],
            })

            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.assertEqual("case.pdf", data["file_path"])
            self.assertNotIn("sk-1234567890abcdef", raw)

    def test_builds_structured_review_payload(self):
        payload = build_review_payload({
            "agent_state": "NEEDS_REVIEW",
            "file_path": "case.pdf",
            "confidence": "low",
            "reasoning": "ambiguous material",
            "candidate_summaries": [{"material_category": "complaint"}],
            "llm_analysis": {"available": True, "summary": "short"},
            "vlm_analysis": {"available": False},
        }, "trace.jsonl")

        self.assertEqual("case.pdf", payload["file_path"])
        self.assertEqual("NEEDS_REVIEW", payload["agent_state"])
        self.assertEqual("low", payload["confidence"])
        self.assertEqual("ambiguous material", payload["reasoning"])
        self.assertEqual("trace.jsonl", payload["trace"])
        self.assertEqual([{"material_category": "complaint"}], payload["candidate_summaries"])
        self.assertEqual({"available": True, "summary": "short"}, payload["llm_analysis"])
        self.assertEqual({"available": False}, payload["vlm_analysis"])
        self.assertIn("error", payload)
        self.assertIsInstance(payload["created_at"], float)

    def test_builds_review_payload_from_runner_result(self):
        payload = build_review_payload({
            "state": "NEEDS_REVIEW",
            "prediction": {
                "file_path": "case.pdf",
                "confidence": "low",
                "reasoning": "needs human judgment",
                "candidate_summaries": [{"material_category": "appeal"}],
                "llm_analysis": {"available": True},
                "vlm_analysis": {"available": True},
            },
        }, "trace.jsonl")

        self.assertEqual("case.pdf", payload["file_path"])
        self.assertEqual("NEEDS_REVIEW", payload["agent_state"])
        self.assertEqual([{"material_category": "appeal"}], payload["candidate_summaries"])

    def test_writer_creates_parent_directory_for_structured_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "review.json"
            ReviewPackageWriter(path).write(build_review_payload({
                "agent_state": "FAILED",
                "file_path": "case.pdf",
                "error": "Authorization: Bearer sk-abcdef1234567890",
            }, "trace.jsonl"))

            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            self.assertEqual("FAILED", data["agent_state"])
            self.assertEqual("case.pdf", data["file_path"])
            self.assertNotIn("sk-abcdef1234567890", raw)

    def test_builds_review_index_payload(self):
        payload = build_review_index_payload({
            "run_id": "run-1",
            "files": [
                {
                    "file_id": "ok",
                    "file_path": "ok.txt",
                    "agent_state": "COMPLETED",
                },
                {
                    "file_id": "review",
                    "file_path": "review.txt",
                    "agent_state": "NEEDS_REVIEW",
                    "confidence": "low",
                    "reasoning": "ambiguous",
                    "trace": "trace.jsonl",
                    "review": "review.json",
                },
                {
                    "file_id": "failed",
                    "file_path": "failed.txt",
                    "agent_state": "FAILED",
                    "error": "model unavailable",
                },
            ],
        })

        self.assertEqual("run-1", payload["run_id"])
        self.assertEqual(2, payload["review_count"])
        self.assertEqual(["review", "failed"], [item["file_id"] for item in payload["items"]])

    def test_builds_review_decision_payload(self):
        payload = build_review_decision_payload({
            "file_id": "file-1",
            "file_path": "case.pdf",
            "decision": "corrected",
            "final_prediction": {"predicted_material_category": "complaint"},
            "reviewer": "reviewer-a",
            "notes": "Authorization: Bearer sk-abcdef1234567890",
        })

        self.assertEqual("file-1", payload["file_id"])
        self.assertEqual("corrected", payload["decision"])
        self.assertEqual("complaint", payload["final_prediction"]["predicted_material_category"])
        self.assertIn("created_at", payload)


if __name__ == "__main__":
    unittest.main()
