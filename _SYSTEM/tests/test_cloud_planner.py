"""Cloud request binding, strict returns and isolation from local plan caches."""
from pathlib import Path
import copy,json,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from local_pipeline import DEFAULTS
from narrative_catalog import choose
from cloud_contract import REVISION,digest,strict_json,validate_return
from cloud_planner import configuration,Replay,plan,make_request


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.cues=[dict(id=1,start=0,end=1000,text='Build a budget.')]
        self.selected=[dict(kind='abstract')]
        data=choose(self.cues,self.selected,dict(DEFAULTS,enabled=True),self.root,request_only=True)
        self.request=dict(revision=REVISION,model='Qwen/Qwen3-8B',jobs=data['jobs'])
        self.response=dict(revision=REVISION,model='Qwen/Qwen3-8B',request_id=digest(self.request),status='completed',
            results=[dict(output=dict(scenes=[dict(cue_id=1,concept='money-saving',camera='wide',evidence='budget')]),attempts=1,output_tokens=30)],
            runtime_ai_calls=1,gpu=['Tesla T4'],elapsed_seconds=10)
    def tearDown(self):self.temporary.cleanup()
    def test_request_preparation_does_not_call_a_model_or_write_a_fake_ai_cache(self):
        self.assertFalse(list(self.root.rglob('*.json')))
    def test_stale_or_wrong_model_return_fails(self):
        for key,value in (('request_id','other'),('model','other'),('status','failed')):
            response=copy.deepcopy(self.response);response[key]=value
            with self.assertRaises(ValueError):validate_return(self.request,response)
    def test_extra_fields_and_wrong_cue_order_are_rejected(self):
        response=copy.deepcopy(self.response);response['results'][0]['output']['scenes'][0]['path']='bad.py'
        with self.assertRaises(Exception):validate_return(self.request,response)
        response=copy.deepcopy(self.response);response['results'][0]['output']['scenes'][0]['cue_id']=2
        with self.assertRaisesRegex(ValueError,'order'):validate_return(self.request,response)
    def test_unsupported_concept_and_fabricated_source_anchor_are_rejected(self):
        for key,value in (('concept','physical:execute'),('evidence','invented source')):
            response=copy.deepcopy(self.response);response['results'][0]['output']['scenes'][0][key]=value
            with self.assertRaises(Exception):validate_return(self.request,response)
    def test_duplicate_json_keys_do_not_pass(self):
        with self.assertRaises(ValueError):strict_json('{"status":"failed","status":"completed"}')
    def test_gpu_and_call_accounting_are_required(self):
        for key,value in (('gpu',[]),('runtime_ai_calls',True),('elapsed_seconds',-1)):
            response=copy.deepcopy(self.response);response[key]=value
            with self.assertRaises(ValueError):validate_return(self.request,response)
    def test_cloud_and_local_caches_cannot_collide(self):
        config=dict(DEFAULTS,enabled=True);replay=Replay(self.request,self.response)
        cloud,report=choose(self.cues,self.selected,config,self.root,client=replay)
        self.assertEqual(report['successful_ai_calls'],1)
        data=choose(self.cues,self.selected,config,self.root,request_only=True)
        self.assertEqual(data['jobs'],self.request['jobs'])
        from unittest.mock import Mock
        local=Mock();local.provider_identity='local';local.generate.return_value=(self.response['results'][0]['output'],{})
        _,report=choose(self.cues,self.selected,config,self.root,client=local)
        self.assertFalse(report['cache_used']);local.generate.assert_called_once()
    def test_replay_does_not_accept_changed_registered_choices(self):
        replay=Replay(self.request,self.response);job=self.request['jobs'][0]
        schema=copy.deepcopy(job['schema']);schema['extra']='invalid'
        with self.assertRaisesRegex(ValueError,'matches'):replay.generate(job['messages'],schema,1400)
    def test_cloud_absent_defaults_to_local_and_invalid_config_stops(self):
        self.assertFalse(configuration(self.root)['enabled'])
        contract.write_json(self.root/'_SYSTEM/cloud_planner.json',dict(enabled=True,endpoint='bad'))
        with self.assertRaises(ValueError):configuration(self.root)

    def test_cloud_failure_keeps_the_previous_movie_and_reports_failure(self):
        from unittest.mock import patch,Mock
        import motion
        for folder in ('INPUT','OUTPUT','_SYSTEM/work','_SYSTEM/reports'):(self.root/folder).mkdir(parents=True,exist_ok=True)
        contract.write_json(self.root/'_SYSTEM/installation.json',dict(format=contract.VERSION))
        contract.write_json(self.root/'_SYSTEM/local_ai.json',dict(DEFAULTS,enabled=True,authoring_mode='hybrid'))
        cloud=contract.read_json(contract.SYSTEM/'cloud_planner.json');cloud['enabled']=True
        contract.write_json(self.root/'_SYSTEM/cloud_planner.json',cloud)
        (self.root/'INPUT/source.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nBuild a budget.\n')
        old=self.root/'OUTPUT/final.mp4';old.write_bytes(b'previous delivery')
        process=Mock();process.poll.return_value=1;process.returncode=1
        with patch('hybrid_pipeline.sys.addaudithook'),patch('cloud_planner.subprocess.Popen',return_value=process):
            self.assertEqual(motion.main(['run','--workspace',str(self.root)]),1)
        self.assertEqual(old.read_bytes(),b'previous delivery')
        self.assertEqual(contract.read_json(self.root/'OUTPUT/SYSTEM_STATUS.json')['status'],'failed')

    def test_validated_cloud_cache_requires_no_broker_or_new_model_calls(self):
        from unittest.mock import patch
        cloud=contract.read_json(contract.SYSTEM/'cloud_planner.json')
        local=dict(DEFAULTS,enabled=True)
        request=make_request(self.root,self.cues,self.selected,local,cloud)
        response=copy.deepcopy(self.response);response['request_id']=digest(request)
        path=self.root/'_SYSTEM/work/cloud_planner'/digest(request)/'validated_plan.json'
        contract.write_json(path,response)
        with patch('cloud_planner.subprocess.Popen') as broker:
            scenes,metrics=plan(self.root,self.cues,self.selected,local,cloud)
        broker.assert_not_called()
        self.assertEqual(metrics['runtime_ai_calls'],0)
        self.assertTrue(metrics['cloud_plan_cache_used'])
        self.assertFalse(metrics['cloud_network_used_this_run'])
        self.assertEqual(scenes[0][0]['recipe_id'],'money-saving')


if __name__=='__main__':unittest.main()
