"""Bounded official DeepSeek client; credentials never enter jobs or reports."""
import json
from pathlib import Path
import ssl
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPSHandler, HTTPRedirectHandler, build_opener

from cloud_contract import strict_json

MODELS = {'deepseek-v4-pro', 'deepseek-flash'}
BASE_URL = 'https://api.deepseek.com'


class DeepSeekError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DeepSeekError('DeepSeek redirects are disabled.')


class DeepSeekClient:
    def __init__(self, key_file, model='deepseek-v4-pro', timeout=180, reasoning_effort='high', max_tokens=8192):
        if model not in MODELS or reasoning_effort not in {'none', 'low', 'high'}:
            raise DeepSeekError('Unregistered DeepSeek model/settings.')
        if type(timeout) is not int or not 30 <= timeout <= 300 or type(max_tokens) is not int or not 1024 <= max_tokens <= 16384:
            raise DeepSeekError('DeepSeek request limits are invalid.')
        try:
            from credential_store import load
            key = load(key_file)
        except (OSError,ValueError):
            raise DeepSeekError('DeepSeek key file is missing or unreadable.') from None
        if not key or len(key) > 512 or any(c.isspace() for c in key) or key.startswith('DEEPSEEK_API_KEY='):
            raise DeepSeekError('Paste only the API key on one line in the local key file.')
        self._key = key
        self.model = model
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        self.max_tokens = max_tokens
        self._opener = build_opener(HTTPSHandler(context=ssl.create_default_context()), NoRedirect())

    def __repr__(self):
        return 'DeepSeekClient(model='+self.model+', credential=<redacted>)'

    def request(self, endpoint, payload=None):
        if endpoint not in {'/models', '/chat/completions'}:
            raise DeepSeekError('Unregistered DeepSeek endpoint.')
        body = json.dumps(payload, allow_nan=False).encode() if payload is not None else None
        request = Request(BASE_URL+endpoint, data=body, method='POST' if body else 'GET', headers={
            'Authorization': 'Bearer '+self._key, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                data = response.read(4*1024*1024+1)
            if len(data) > 4*1024*1024:
                raise DeepSeekError('DeepSeek response exceeded the size limit.')
            return strict_json(data.decode('utf-8'))
        except HTTPError as error:
            explanations = {401: 'Key rejected.', 402: 'Insufficient API balance.', 429: 'Rate limit reached.'}
            raise DeepSeekError('DeepSeek HTTP '+str(error.code)+': '+explanations.get(error.code, 'Request failed.')) from None
        except (URLError, TimeoutError, OSError):
            raise DeepSeekError('DeepSeek network connection failed or timed out.') from None
        except (UnicodeError, ValueError):
            raise DeepSeekError('DeepSeek returned invalid JSON.') from None

    def inventory(self):
        result = self.request('/models')
        ids = [item.get('id') for item in result.get('data', [])]
        if self.model not in ids:
            raise DeepSeekError('Configured DeepSeek model is unavailable for this account.')
        return dict(provider='deepseek', model=self.model, available_models=ids)

    def generate(self, messages, schema):
        prompt = list(messages)+[dict(role='user', content='Return only valid JSON matching this exact schema: '+json.dumps(schema))]
        result = self.request('/chat/completions', dict(model=self.model, messages=prompt,
            reasoning_effort=self.reasoning_effort, max_tokens=self.max_tokens,
            response_format=dict(type='json_object'), stream=False))
        if result.get('model') != self.model:
            raise DeepSeekError('DeepSeek response model does not match the requested model.')
        choices = result.get('choices', [])
        if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
            raise DeepSeekError('DeepSeek result is incomplete or truncated.')
        content = choices[0].get('message', {}).get('content')
        if not isinstance(content, str) or not content.strip():
            raise DeepSeekError('DeepSeek returned no final JSON content.')
        try:
            output = strict_json(content)
        except ValueError:
            raise DeepSeekError('DeepSeek final content is invalid JSON.') from None
        usage = result.get('usage', {})
        evidence = dict(provider='deepseek', model=self.model, reasoning_effort=self.reasoning_effort,
            usage={name: usage.get(name, 0) for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')})
        return output, evidence
