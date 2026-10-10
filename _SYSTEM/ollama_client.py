"""Loopback-only Ollama client with independent response/schema validation."""
from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    """A local-model failure that must not be interpreted as approval."""


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise OllamaError(f"Duplicate model JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise OllamaError(f"Non-finite model JSON value: {value}")

    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, TypeError) as exc:
        raise OllamaError(f"Invalid model JSON: {exc}") from exc


class LocalOllama:
    def __init__(self, model="qwen3:4b", timeout=240, transport=None, context=8192,
                 sampling=None, thinking=False, ground_schema=False):
        self.model = model
        self.timeout = timeout
        self.transport = transport or self._http
        self.context = context
        self.thinking = thinking
        self.ground_schema = ground_schema
        self.sampling = dict(sampling or {})
        allowed = {"temperature", "top_p", "top_k", "min_p", "presence_penalty", "repeat_penalty"}
        if set(self.sampling) - allowed:
            raise OllamaError("Sampling overrides may not change model, context, output limits or transport")

    def _http(self, route, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request("http://127.0.0.1:11434" + route, data=data,
                          headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise OllamaError("Local model response exceeded 16 MiB")
            result = strict_json(raw.decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read(4096).decode('utf-8', errors='replace')
            try:
                detail = json.loads(detail).get('error', detail)
            except (ValueError, AttributeError):
                pass
            raise OllamaError(f"Local Ollama request failed for {self.model}: HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError, UnicodeError) as exc:
            raise OllamaError(f"Local Ollama request failed: {exc}") from exc
        if not isinstance(result, dict) or result.get("error"):
            raise OllamaError(f"Local Ollama error: {result.get('error') if isinstance(result, dict) else 'invalid response'}")
        return result

    def inventory(self):
        tags = self.transport("/api/tags", None)
        if self.model not in [m.get("name") for m in tags.get("models", [])]:
            raise OllamaError(f"Required installed model is missing: {self.model}")
        return tags

    def generate(self, messages, schema, tokens=3300):
        started = time.monotonic()
        if self.ground_schema:
            messages = list(messages) + [{"role": "user", "content":
                "Output JSON only. The exact required fields and validation contract are:\n"
                + json.dumps(schema, ensure_ascii=False)
                + "\nFollow this structure and the preceding source/host rules. Keep prose concise."}]
        result = self.transport("/api/chat", {
            "model": self.model, "messages": messages, "stream": False,
            "think": self.thinking, "format": schema, "keep_alive": "5m",
            "options": {"temperature": 0, "seed": 91, **self.sampling,
                        "num_ctx": self.context, "num_predict": tokens},
        })
        def failure(message):
            error = OllamaError(message)
            # Preserve generated content for diagnosis, never accept it as complete code.
            error.response_details = {key: result.get(key) for key in (
                "done", "done_reason", "eval_count", "prompt_eval_count", "total_duration", "eval_duration")}
            error.response_details["content"] = result.get("message", {}).get("content", "")[:16000]
            return error
        if result.get("done") is not True or result.get("done_reason") not in (None, "stop"):
            raise failure(f"Incomplete model response: {result.get('done_reason', 'not done')}")
        try:
            output = strict_json(result.get("message", {}).get("content", ""))
        except OllamaError as exc:
            raise failure(str(exc)) from exc
        from jsonschema import Draft202012Validator
        try:
            Draft202012Validator(schema).validate(output)
        except Exception as exc:
            raise failure(f"Model response failed requested schema: {exc}") from exc
        seconds = result.get("eval_duration", 0) / 1e9
        metrics = {"wall_seconds": round(time.monotonic() - started, 3),
                   "server_seconds": round(result.get("total_duration", 0) / 1e9, 3),
                   "load_seconds": round(result.get("load_duration", 0) / 1e9, 3),
                   "prompt_tokens": result.get("prompt_eval_count"),
                   "output_tokens": result.get("eval_count"),
                   "tokens_per_second": round(result.get("eval_count", 0) / seconds, 2) if seconds else None,
                   "thinking": self.thinking, "sampling": self.sampling,
                   "schema_grounded_in_prompt": self.ground_schema,
                   "thinking_characters": len(result.get("message", {}).get("thinking", ""))}
        return output, metrics

    def unload(self):
        return self.transport("/api/generate", {"model": self.model, "keep_alive": 0})
