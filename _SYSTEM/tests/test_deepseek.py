"""Provider binding, source acceptance, failure preservation and secret handling."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import Mock, patch
import unittest
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contract
from cloud_contract import digest
from deepseek_client import DeepSeekClient, DeepSeekError
from deepseek_planner import configuration, make_request, validate_return, Replay, plan
from local_pipeline import DEFAULTS


class DeepSeekTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key_file = self.root/'key.txt'
        self.key_file.write_text('sk-test-never-log')
        self.cues = [dict(id=1, start=0, end=1000, text='Build a budget.')]
        self.selected = [dict(kind='abstract')]
        self.config = dict(enabled=True, provider='deepseek', model='deepseek-v4-pro', timeout_seconds=180,
            reasoning_effort='high', max_output_tokens=8192, failure_policy='stop')
        self.request = make_request(self.root, self.cues, self.selected, DEFAULTS, self.config)
        self.output = dict(scenes=[dict(cue_id=1, concept='money-saving', camera='wide', evidence='budget')])
        self.response = dict(revision=self.request['revision'], provider='deepseek', model=self.config['model'],
            request_id=digest(self.request), status='completed', runtime_ai_calls=1, elapsed_seconds=1,
            results=[dict(output=self.output, attempts=1, evidence=dict(provider='deepseek', model=self.config['model'],
                reasoning_effort='high', usage=dict(prompt_tokens=100, completion_tokens=100, total_tokens=200)))])

    def tearDown(self):
        self.temp.cleanup()

    def client(self):
        return DeepSeekClient(self.key_file)

    def test_request_contains_no_credential(self):
        text = json.dumps(self.request)
        self.assertNotIn(self.key_file.read_text(), text)
        self.assertNotIn('key_file', text)
        self.assertNotIn('Authorization', text)

    def test_key_format_and_endpoint_restricted(self):
        for text in ['', 'abc\ndef', 'DEEPSEEK_API_KEY=secret']:
            self.key_file.write_text(text)
            with self.assertRaises(DeepSeekError):
                self.client()
        self.key_file.write_text('sk-test-never-log')
        with self.assertRaises(DeepSeekError):
            self.client().request('https://untrusted.example')

    def test_http_error_and_repr_do_not_expose_secret(self):
        client = self.client()
        client._opener = Mock()
        client._opener.open.side_effect = HTTPError('https://api.deepseek.com', 401, 'sk-test-never-log', {}, io.BytesIO(b'sk-test-never-log'))
        with self.assertRaises(DeepSeekError) as error:
            client.inventory()
        self.assertNotIn('sk-test-never-log', str(error.exception))
        self.assertNotIn('sk-test-never-log', repr(client))

    def test_truncated_or_wrong_model_result_rejected(self):
        for field, value in [('finish_reason', 'length'), ('model', 'other')]:
            result = dict(model='deepseek-v4-pro', choices=[dict(finish_reason='stop', message=dict(content=json.dumps(self.output)))])
            if field == 'model': result['model'] = value
            else: result['choices'][0][field] = value
            with patch.object(DeepSeekClient, 'request', return_value=result):
                with self.assertRaises(DeepSeekError):
                    self.client().generate([], {})

    def test_duplicate_json_keys_rejected(self):
        result = dict(model='deepseek-v4-pro', choices=[dict(finish_reason='stop', message=dict(content='{"scenes": [], "scenes": []}'))])
        with patch.object(DeepSeekClient, 'request', return_value=result):
            with self.assertRaises(DeepSeekError):
                self.client().generate([], {})

    def test_invalid_config_rejects_endpoint_or_unbounded_limits(self):
        for change in [dict(endpoint='https://untrusted.example'), dict(max_output_tokens=100000), dict(failure_policy='fallback')]:
            contract.write_json(self.root/'_SYSTEM/deepseek_planner.json', dict(self.config, **change))
            with self.assertRaises(ValueError): configuration(self.root)

    def test_changed_source_order_extra_code_and_identity_rejected(self):
        for changed in [dict(cue_id=2), dict(path='bad.py'), dict(concept='unregistered')]:
            response = copy.deepcopy(self.response)
            response['results'][0]['output']['scenes'][0].update(changed)
            with self.assertRaises(Exception): validate_return(self.request, response)
        replay = Replay(self.request, self.response)
        messages = copy.deepcopy(self.request['jobs'][0]['messages'])
        body = json.loads(messages[1]['content']); body['locked_character'] = {'identity_id':'changed'}
        messages[1]['content'] = json.dumps(body)
        with self.assertRaises(ValueError): replay.generate(messages, self.request['jobs'][0]['schema'], 1400)

    def test_stale_model_call_accounting_and_usage_rejected(self):
        for key, value in [('request_id', 'stale'), ('model', 'wrong'), ('runtime_ai_calls', 2)]:
            response = copy.deepcopy(self.response); response[key] = value
            with self.assertRaises(ValueError): validate_return(self.request, response)
        response = copy.deepcopy(self.response)
        response['results'][0]['evidence']['usage']['prompt_tokens'] = -1
        with self.assertRaises(ValueError): validate_return(self.request, response)

    def test_cache_reuse_makes_no_new_network_calls(self):
        path = self.root/'_SYSTEM/work/deepseek_planner'/digest(self.request)/'validated_plan.json'
        contract.write_json(path, self.response)
        with patch('deepseek_planner.subprocess.Popen') as process:
            scenes, report = plan(self.root, self.cues, self.selected, DEFAULTS, self.config)
        process.assert_not_called()
        self.assertEqual(scenes[0][0]['recipe_id'], 'money-saving')
        self.assertEqual(report['runtime_ai_calls'], 0)
        self.assertTrue(report['cloud_plan_cache_used'])
        self.assertFalse(report['voice_uploaded'])

    def test_api_failure_preserves_prior_video_and_stops(self):
        old = self.root/'OUTPUT/final.mp4'; old.parent.mkdir(); old.write_bytes(b'prior movie')
        process = Mock(); process.poll.return_value = 1; process.returncode = 1
        with patch('deepseek_planner.subprocess.Popen', return_value=process):
            with self.assertRaisesRegex(RuntimeError, 'No silent local fallback'):
                plan(self.root, self.cues, self.selected, DEFAULTS, self.config)
        self.assertEqual(old.read_bytes(), b'prior movie')

    def test_active_api_precedes_kaggle(self):
        import cloud_planner
        contract.write_json(self.root/'_SYSTEM/deepseek_planner.json', self.config)
        self.assertEqual(cloud_planner.configuration(self.root)['provider'], 'deepseek')


if __name__ == '__main__':
    unittest.main()
