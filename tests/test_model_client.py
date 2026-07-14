import unittest

from smart_case_filing.model_client import FakeModelClient, redact_secret


class ModelClientTest(unittest.TestCase):
    def test_redacts_api_key_values(self):
        text = "Authorization: Bearer sk-1234567890abcdef"
        self.assertEqual("Authorization: Bearer sk-123...cdef", redact_secret(text))

    def test_fake_client_returns_registered_response(self):
        client = FakeModelClient({"chat": "{\"ok\": true}", "vision": "{\"image\": true}"})
        self.assertEqual("{\"ok\": true}", client.chat("prompt", system="sys"))
        self.assertEqual("{\"image\": true}", client.vision("prompt", ["a.png"]))


if __name__ == "__main__":
    unittest.main()
