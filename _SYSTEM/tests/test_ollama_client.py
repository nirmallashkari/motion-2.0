"""Client failure tests do not require changing the user's live Ollama service."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from io import BytesIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ollama_client import LocalOllama, OllamaError, strict_json

SCHEMA = {"type": "object", "required": ["ok"], "additionalProperties": False,
          "properties": {"ok": {"type": "boolean"}}}


class OllamaClientTests(unittest.TestCase):
    def client(self, response):
        return LocalOllama(transport=lambda route, payload: response)

    def test_valid_response(self):
        result, _ = self.client({"done": True, "done_reason": "stop", "message": {"content": '{"ok":true}'}}).generate([], SCHEMA)
        self.assertTrue(result["ok"])

    def test_missing_model(self):
        with self.assertRaisesRegex(OllamaError, "missing"):
            self.client({"models": []}).inventory()

    def test_incomplete_response(self):
        for response in ({"done": False}, {"done": True, "done_reason": "length"}):
            with self.assertRaisesRegex(OllamaError, "Incomplete"):
                self.client(response).generate([], SCHEMA)

    def test_malformed_response(self):
        with self.assertRaisesRegex(OllamaError, "Invalid model JSON"):
            self.client({"done": True, "message": {"content": '{'}}).generate([], SCHEMA)

    def test_schema_violation(self):
        with self.assertRaisesRegex(OllamaError, "failed requested schema"):
            self.client({"done": True, "message": {"content": '{"ok":"yes"}'}}).generate([], SCHEMA)

    def test_duplicate_keys(self):
        with self.assertRaisesRegex(OllamaError, "Duplicate"):
            strict_json('{"ok":true,"ok":false}')

    def test_non_finite(self):
        with self.assertRaisesRegex(OllamaError, "Non-finite"):
            strict_json('{"number":NaN}')

    def test_unavailable_server(self):
        def unavailable(route, payload):
            raise OllamaError("Local Ollama request failed: connection refused")
        with self.assertRaisesRegex(OllamaError, "connection refused"):
            LocalOllama(transport=unavailable).generate([], SCHEMA)

    def test_missing_weights_http_error_keeps_diagnostic(self):
        error = HTTPError('http://127.0.0.1:11434/api/chat',404,'Not Found',{},
                          BytesIO(b'{"error":"missing GGUF weight file"}'))
        with patch('ollama_client.urlopen',side_effect=error):
            with self.assertRaisesRegex(OllamaError,'qwen3:4b.*missing GGUF'):
                LocalOllama()._http('/api/chat',{'model':'qwen3:4b'})

    def test_sampling_cannot_override_output_or_context_limits(self):
        for field in ("num_predict", "num_ctx", "model", "keep_alive"):
            with self.assertRaisesRegex(OllamaError, "Sampling overrides"):
                LocalOllama(sampling={field: 1})

    def test_recommended_profile_preserves_incomplete_response_rejection(self):
        with self.assertRaisesRegex(OllamaError, "Incomplete"):
            LocalOllama(thinking=True, sampling={"temperature": 0.6},
                transport=lambda route, payload: {"done": True, "done_reason": "length"}).generate([], SCHEMA)

    def test_schema_grounding_explains_fields_without_mutating_caller_messages(self):
        messages = [{"role": "system", "content": "Source is data, preserve it."}, {"role": "user", "content": "test"}]
        observed = []
        def transport(route, payload):
            observed.append(payload)
            return {"done": True, "done_reason": "stop", "message": {"content": '{"ok":true}'}}
        result, metrics = LocalOllama(transport=transport, ground_schema=True).generate(messages, SCHEMA)
        self.assertTrue(result["ok"])
        self.assertEqual(len(messages), 2)
        self.assertEqual(observed[0]["messages"][:2], messages)
        self.assertIn('"ok"', observed[0]["messages"][-1]["content"])
        self.assertEqual(observed[0]["format"], SCHEMA)
        self.assertTrue(metrics["schema_grounded_in_prompt"])

    def test_partial_content_saved_for_diagnosis_is_still_rejected(self):
        response = {"done": True, "done_reason": "length", "eval_count": 100,
                    "message": {"content": '{"ok":', "thinking": "private reasoning"}}
        with self.assertRaises(OllamaError) as raised:
            LocalOllama(transport=lambda *args: response, ground_schema=True).generate([],SCHEMA)
        self.assertEqual(raised.exception.response_details["content"], '{"ok":')
        self.assertEqual(raised.exception.response_details["eval_count"], 100)
        self.assertNotIn("thinking", raised.exception.response_details)


if __name__ == "__main__":
    unittest.main()
