"""Network-enabled Kaggle broker isolated from network-denied render workers."""
import argparse,base64,json,re,time
from pathlib import Path
from cloud_contract import digest,validate_return,strict_json


def execute(folder,timeout):
    from kaggle.api.kaggle_api_extended import KaggleApi
    root=Path(folder).resolve();request=json.loads((root/'request.json').read_text(encoding='utf-8'))
    api=KaggleApi();api.authenticate();owner=api.get_config_value('username')
    if not owner or not re.fullmatch(r'[a-zA-Z0-9_-]+',owner):raise ValueError('Invalid authenticated Kaggle owner.')
    suffix=digest(request)[:12]
    ref=f'{owner}/motion-20-planner-{suffix}'
    kernel=root/'kernel';kernel.mkdir(exist_ok=True)
    system=Path(__file__).parent
    payload=base64.b64encode(json.dumps(request,ensure_ascii=False).encode()).decode()
    sources={name:base64.b64encode((system/name).read_bytes()).decode() for name in ('cloud_contract.py','cloud_runtime.py')}
    code='''import base64,json,subprocess,sys
from pathlib import Path
subprocess.run([sys.executable,'-m','pip','install','--quiet','transformers==4.57.1','accelerate==1.11.0','bitsandbytes==0.48.1','jsonschema==4.25.1'],check=True)
'''+f'SOURCES={sources!r}\nREQUEST={payload!r}\n'+'''root=Path('/kaggle/working/motion_worker');root.mkdir(exist_ok=True)
for name,data in SOURCES.items():(root/name).write_bytes(base64.b64decode(data))
sys.path.insert(0,str(root))
from cloud_runtime import run
run(json.loads(base64.b64decode(REQUEST)), '/kaggle/working')
'''
    (kernel/'planner.py').write_text(code,encoding='utf-8')
    meta=dict(id=ref,title=f'Motion 20 Planner {suffix}',code_file='planner.py',language='python',kernel_type='script',is_private=True,
        enable_gpu=True,enable_tpu=False,enable_internet=True,machine_shape='NvidiaTeslaT4',dataset_sources=[],kernel_sources=[],competition_sources=[],model_sources=[])
    (kernel/'kernel-metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    state_path=root/'submission.json'
    if state_path.is_file():
        state=json.loads(state_path.read_text());assert state['request_id']==digest(request)
    else:
        result=api.kernels_push(str(kernel),timeout=timeout,acc='NvidiaTeslaT4')
        if getattr(result,'error',None):raise RuntimeError('Kaggle submission rejected: '+str(result.error))
        state=dict(request_id=digest(request),ref=ref,url=result.url,version=getattr(result,'version_number',None),submitted_at=time.time())
        state_path.write_text(json.dumps(state,indent=2),encoding='utf-8')
    print('CLOUD: '+state['url'],flush=True)
    deadline=time.monotonic()+timeout;prior=None
    while time.monotonic()<deadline:
        status=api.kernels_status(ref);name=str(status.status).rsplit('.',1)[-1].upper()
        if name!=prior:print('CLOUD: '+name,flush=True);prior=name
        (root/'status.json').write_text(json.dumps(dict(status=name,request_id=state['request_id'])),encoding='utf-8')
        if name in {'COMPLETE','ERROR','CANCELLED'}:
            api.kernels_output(ref,str(root/'download'),file_pattern=r'^plan\.json$',force=True,quiet=True)
            path=root/'download/plan.json'
            if name!='COMPLETE' or not path.is_file():raise RuntimeError('Kaggle job ended without a complete plan: '+name)
            response=strict_json(path.read_text(encoding='utf-8'));validate_return(request,response)
            (root/'validated_plan.json').write_text(json.dumps(response,indent=2,ensure_ascii=False),encoding='utf-8')
            return
        time.sleep(20)
    raise TimeoutError('Kaggle planning exceeded its time allowance; the remote job may still be running. Rerun to resume status checking.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--timeout',type=int,default=1800)
    args=parser.parse_args();execute(args.folder,args.timeout)
