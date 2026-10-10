"""Host cloud adapter: prepare, resume, validate, then replay data locally."""
import json,re,subprocess,sys,time
from pathlib import Path
import contract
from cloud_contract import REVISION,digest,strict_json,validate_return
from narrative_catalog import choose


def configuration(workspace):
    from deepseek_planner import configuration as api_configuration
    api=api_configuration(workspace)
    if api['enabled']:return api
    path=contract.no_links(Path(workspace)/'_SYSTEM/cloud_planner.json',workspace)
    if not path.is_file():return dict(enabled=False)
    config=contract.read_json(path)
    if set(config)!={'enabled','provider','model','model_revision','timeout_seconds','failure_policy'}:
        raise ValueError('Invalid cloud planner settings.')
    if not isinstance(config['enabled'],bool) or config['provider']!='kaggle' or config['model']!='Qwen/Qwen3-8B' or not isinstance(config['model_revision'],str) or not re.fullmatch('[0-9a-f]{40}',config['model_revision']):
        raise ValueError('Unregistered cloud provider/model revision.')
    if not isinstance(config['timeout_seconds'],int) or not 300<=config['timeout_seconds']<=3600 or config['failure_policy']!='stop':
        raise ValueError('Invalid cloud timeout/failure policy.')
    return config


class Replay:
    def __init__(self,request,response):
        validate_return(request,response)
        self.request=request;self.response=response;self.index=0
        self.provider_identity='kaggle:'+digest(request)
    def inventory(self):return dict(provider='kaggle')
    def generate(self,messages,schema,tokens):
        job=self.request['jobs'][self.index];result=self.response['results'][self.index]
        # Previous source-context choices may change during host protection rules.
        # Cue data, allowed concepts and the exact schema must still match.
        expected=json.loads(job['messages'][1]['content']);actual=json.loads(messages[1]['content'])
        if schema!=job['schema'] or any(expected[key]!=actual[key] for key in ('source','allowed_choices','catalog','action_capabilities')) or expected.get('locked_character')!=actual.get('locked_character'):
            raise ValueError('Cloud replay no longer matches the local source/catalog.')
        self.index+=1
        return result['output'],dict(provider='kaggle',model=self.response['model'],remote_attempts=result['attempts'],output_tokens=result['output_tokens'])
    def unload(self):pass


def make_request(workspace,cues,selected,local_config,cloud_config,store=None):
    data=choose(cues,selected,local_config,workspace,store=store,request_only=True)
    return dict(revision=REVISION,model=cloud_config['model'],model_revision=cloud_config['model_revision'],
        jobs=data['jobs'],library_hash=data['library']['library_hash'],
        worker_hashes={name:contract.sha(contract.SYSTEM/name) for name in ('cloud_contract.py','cloud_runtime.py','cloud_broker.py','action_direction.py')})


def plan(workspace,cues,selected,local_config,cloud_config,store=None):
    if cloud_config.get('provider')=='deepseek':
        from deepseek_planner import plan as api_plan
        return api_plan(workspace,cues,selected,local_config,cloud_config,store)
    workspace=Path(workspace)
    request=make_request(workspace,cues,selected,local_config,cloud_config,store)
    root=contract.no_links(workspace/'_SYSTEM/work/cloud_planner'/digest(request),workspace)
    root.mkdir(parents=True,exist_ok=True);contract.write_json(root/'request.json',request)
    response_file=contract.no_links(root/'validated_plan.json',workspace);cached=response_file.is_file()
    if not cached:
        print('CLOUD: sending timed source and registered choices to private Kaggle planner; voice stays local.',flush=True)
        command=[sys.executable,str(contract.SYSTEM/'cloud_broker.py'),str(root),'--timeout',str(cloud_config['timeout_seconds'])]
        with (root/'broker.log').open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=log)
            started=last=time.monotonic()
            try:
                while process.poll() is None:
                    now=time.monotonic()
                    if now-started>cloud_config['timeout_seconds']+180:raise TimeoutError('Cloud broker deadline exceeded; rerun to resume remote checking.')
                    if now-last>=20:
                        status=contract.read_json(root/'status.json') if (root/'status.json').is_file() else {}
                        print(f"CLOUD: {status.get('status','submitting')}; {int(now-started)}s elapsed.",flush=True);last=now
                    time.sleep(.25)
                if process.returncode:raise RuntimeError(f'Cloud planner failed; see {root / "broker.log"}. Previous video retained; no silent local substitution.')
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=20)
    response=strict_json(response_file.read_text(encoding='utf-8'));validate_return(request,response)
    replay=Replay(request,response)
    planned,metrics=choose(cues,selected,dict(local_config,enabled=True),workspace,client=replay,store=store)
    if metrics['failures'] or (not metrics['cache_used'] and replay.index!=len(request['jobs'])):
        raise ValueError('Cloud result failed host narrative acceptance.')
    metrics.update(provider='kaggle',model=response['model'],external_network_disabled=False,
        cloud_network_used_this_run=not cached,cloud_plan_cache_used=cached,
        runtime_ai_calls=0 if cached else response['runtime_ai_calls'],successful_ai_calls=0 if cached else len(response['results']),
        remote_generation=dict(model_revision=request['model_revision'],runtime_ai_calls=response['runtime_ai_calls'],gpu=response['gpu'],elapsed_seconds=response['elapsed_seconds']),
        request_id=digest(request),voice_uploaded=False,per_project_scene_authoring=False)
    contract.write_json(root/'host_acceptance.json',metrics)
    contract.write_json(workspace/'OUTPUT/CLOUD_PLANNER_STATUS.json',metrics)
    return planned,metrics
