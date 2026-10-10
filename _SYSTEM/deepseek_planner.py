"""API broker adapter for source-bound registered scene plans, with no local fallback."""
import json
from pathlib import Path
import subprocess
import sys
import time

import contract
from cloud_contract import digest, strict_json, validate_choice
from deepseek_client import MODELS
from narrative_catalog import choose

REVISION = 'motion-deepseek-planner-1.0'


def configuration(workspace):
    path = contract.no_links(Path(workspace)/'_SYSTEM/deepseek_planner.json', workspace)
    if not path.is_file():
        return dict(enabled=False)
    config = contract.read_json(path)
    if set(config) != {'enabled', 'provider', 'model', 'timeout_seconds', 'reasoning_effort', 'max_output_tokens', 'failure_policy'}:
        raise ValueError('Invalid DeepSeek planner settings.')
    if type(config['enabled']) is not bool or config['provider'] != 'deepseek' or config['model'] not in MODELS:
        raise ValueError('Unregistered DeepSeek provider/model.')
    if type(config['timeout_seconds']) is not int or not 30 <= config['timeout_seconds'] <= 300:
        raise ValueError('Invalid DeepSeek request timeout.')
    if config['reasoning_effort'] not in {'none', 'low', 'high'} or type(config['max_output_tokens']) is not int or not 1024 <= config['max_output_tokens'] <= 16384 or config['failure_policy'] != 'stop':
        raise ValueError('Invalid DeepSeek bounded request policy.')
    return config


def make_request(workspace, cues, selected, local_config, config, store=None):
    data = choose(cues, selected, local_config, workspace, store=store, request_only=True)
    return dict(revision=REVISION, provider='deepseek', model=config['model'],
        timeout_seconds=config['timeout_seconds'], reasoning_effort=config['reasoning_effort'],
        max_output_tokens=config['max_output_tokens'], jobs=data['jobs'], library_hash=data['library']['library_hash'],
        worker_hashes={name: contract.sha(contract.SYSTEM/name) for name in
            ('deepseek_planner.py', 'deepseek_broker.py', 'deepseek_client.py', 'cloud_contract.py', 'action_direction.py', 'narrative_catalog.py')})


def validate_return(request, response):
    if set(response) != {'revision', 'request_id', 'provider', 'model', 'status', 'results', 'runtime_ai_calls', 'elapsed_seconds'}:
        raise ValueError('Invalid DeepSeek return fields.')
    if response['revision'] != REVISION or response['request_id'] != digest(request) or response['provider'] != 'deepseek' or response['model'] != request['model'] or response['status'] != 'completed':
        raise ValueError('DeepSeek return is stale or bound to another request/model.')
    results = response['results']
    if len(results) != len(request['jobs']) or type(response['runtime_ai_calls']) is not int:
        raise ValueError('Incomplete DeepSeek scene plan.')
    calls = 0
    for job, result in zip(request['jobs'], results):
        if set(result) != {'output', 'attempts', 'evidence'} or type(result['attempts']) is not int or result['attempts'] not in (1, 2):
            raise ValueError('Invalid DeepSeek attempt accounting.')
        evidence = result['evidence']
        if set(evidence) != {'provider', 'model', 'reasoning_effort', 'usage'} or evidence['provider'] != 'deepseek' or evidence['model'] != request['model'] or evidence['reasoning_effort'] != request['reasoning_effort']:
            raise ValueError('DeepSeek evidence does not match the request.')
        if set(evidence['usage']) != {'prompt_tokens', 'completion_tokens', 'total_tokens'} or any(type(v) is not int or v < 0 for v in evidence['usage'].values()):
            raise ValueError('Invalid DeepSeek token usage.')
        calls += result['attempts']
        validate_choice(job, result['output'])
    if calls != response['runtime_ai_calls'] or type(response['elapsed_seconds']) not in (int, float) or not 0 <= response['elapsed_seconds'] <= len(results)*(request['timeout_seconds']*2+30)+60:
        raise ValueError('Invalid DeepSeek call count or timing.')
    return response


class Replay:
    def __init__(self, request, response):
        validate_return(request, response)
        self.request, self.response, self.index = request, response, 0
        self.provider_identity = 'deepseek:'+digest(request)

    def inventory(self):
        return dict(provider='deepseek')

    def generate(self, messages, schema, tokens):
        job = self.request['jobs'][self.index]
        expected, actual = json.loads(job['messages'][1]['content']), json.loads(messages[1]['content'])
        keys = ('source', 'allowed_choices', 'catalog', 'action_capabilities', 'locked_character')
        if schema != job['schema'] or any(expected.get(key) != actual.get(key) for key in keys):
            raise ValueError('DeepSeek replay no longer matches source/capabilities/identity.')
        result = self.response['results'][self.index]
        self.index += 1
        return result['output'], dict(result['evidence'], remote_attempts=result['attempts'])

    def unload(self):
        pass


def plan(workspace, cues, selected, local_config, config, store=None):
    workspace = Path(workspace)
    request = make_request(workspace, cues, selected, local_config, config, store)
    folder = contract.no_links(workspace/'_SYSTEM/work/deepseek_planner'/digest(request), workspace)
    folder.mkdir(parents=True, exist_ok=True)
    contract.write_json(folder/'request.json', request)
    result_file = folder/'validated_plan.json'
    cached = result_file.is_file()
    if not cached:
        print('API: DeepSeek planning registered scenes; voice stays local.', flush=True)
        with (folder/'broker.log').open('wb') as log:
            process = subprocess.Popen([sys.executable, str(contract.SYSTEM/'deepseek_broker.py'), str(folder)], stdout=log, stderr=log)
            started = last = time.monotonic()
            deadline = started+max(60, len(request['jobs'])*(config['timeout_seconds']*2+30)+60)
            try:
                while process.poll() is None:
                    now = time.monotonic()
                    if now > deadline:
                        raise TimeoutError('DeepSeek planner deadline exceeded; prior movie preserved.')
                    if now-last >= 15:
                        state = contract.read_json(folder/'status.json') if (folder/'status.json').is_file() else {}
                        print(f"API: {state.get('status', 'connecting')}; {int(now-started)}s elapsed.", flush=True)
                        last = now
                    time.sleep(.25)
                if process.returncode:
                    raise RuntimeError('DeepSeek planning failed; inspect '+str(folder/'broker.log')+'. No silent local fallback.')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=20)
    response = strict_json(result_file.read_text(encoding='utf-8'))
    validate_return(request, response)
    replay = Replay(request, response)
    planned, metrics = choose(cues, selected, dict(local_config, enabled=True), workspace, client=replay, store=store)
    if metrics['failures'] or (not metrics['cache_used'] and replay.index != len(request['jobs'])):
        raise ValueError('DeepSeek result failed host narrative acceptance.')
    metrics.update(status='ai_planned', provider='deepseek', model=config['model'], external_network_disabled=False,
        cloud_network_used_this_run=not cached, cloud_plan_cache_used=cached,
        runtime_ai_calls=0 if cached else response['runtime_ai_calls'],
        successful_ai_calls=0 if cached else len(response['results']), request_id=digest(request),
        remote_generation=dict(model=config['model'], runtime_ai_calls=response['runtime_ai_calls'],
            elapsed_seconds=response['elapsed_seconds'], reasoning_effort=config['reasoning_effort'],
            usage=[result['evidence']['usage'] for result in response['results']]),
        voice_uploaded=False, per_project_scene_authoring=False)
    contract.write_json(folder/'host_acceptance.json', metrics)
    contract.write_json(workspace/'OUTPUT/CLOUD_PLANNER_STATUS.json', metrics)
    contract.write_json(workspace/'OUTPUT/DEEPSEEK_API_STATUS.json', metrics)
    return planned, metrics
