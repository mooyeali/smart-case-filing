import json
import tempfile
import unittest
from pathlib import Path

from smart_case_filing.agent.review import ReviewPackageWriter


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


if __name__ == "__main__":
    unittest.main()
