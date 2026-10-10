"""Semantic boundaries, actual state progression and pre-render failure behavior."""
from pathlib import Path
import copy,json,sys,tempfile,unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract,motion
from PIL import Image,ImageDraw
from action_direction import compile_direction,enforce
from asset_store import AssetStore
from local_pipeline import DEFAULTS
from narrative_catalog import choose,grounded
from story_director import direct
from story_planner import plan_story
from self_pipeline import select,build_package
from shot_policy import assign
from preview_gate import inspect_frames,run


class ActionDirectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=AssetStore()
    def tearDown(self):self.tmp.cleanup()
    def make(self,texts):
        cues=[dict(id=i+1,start=i*1000,end=(i+1)*1000,text=text) for i,text in enumerate(texts)]
        selected,_=plan_story(cues,self.store,select)
        pairs,_=choose(cues,selected,dict(DEFAULTS,enabled=False),self.root)
        presets=[pair[0] for pair in pairs];choices=direct(cues,[pair[1] for pair in pairs])
        choices,report=compile_direction(cues,presets,choices);choices=assign(cues,presets,choices)
        source=self.root/'source.srt';source.write_text('\n\n'.join(f'{c["id"]}\n00:00:{i:02},000 --> 00:00:{i+1:02},000\n{c["text"]}' for i,c in enumerate(cues))+'\n',encoding='utf-8')
        project,_=build_package(self.root/'package',source,cues,presets,self.store,character_choices=choices)
        return cues,project,report
    def test_solution_and_exhaustion_outrank_the_criticism_trigger(self):
        self.assertEqual(grounded('Aukat par sawal uthaye, apne kaam se jawab dena!'),'effort')
        self.assertEqual(grounded('Taane sunte-sunte kaan thak gaye hain.'),'exhaustion')
    def test_unrelated_concept_is_not_allowed_despite_a_verbatim_anchor(self):
        cues=[dict(id=1,start=0,end=1000,text='Apne kaam se jawab dena.')]
        client=Mock();client.generate.return_value=(dict(scenes=[dict(cue_id=1,concept='criticism',camera='wide',evidence='kaam')]),{})
        pairs,report=choose(cues,[dict(kind='abstract')],dict(DEFAULTS,enabled=True,attempts=1),self.root,client=client)
        self.assertTrue(report['failures']);self.assertEqual(pairs[0][1]['theme'],'effort')
        request=choose(cues,[dict(kind='abstract')],dict(DEFAULTS,enabled=True),self.root,request_only=True)
        body=json.loads(request['jobs'][0]['messages'][1]['content'])
        self.assertIn('action_capabilities',body);self.assertNotIn('criticism',body['allowed_choices'][0])
    def test_second_criticism_has_a_prop_action_recipe_not_just_another_camera(self):
        cues,project,report=self.make(['People criticize the person.','More criticism reaches the person.'])
        self.assertEqual([s['variant'] for s in report['scenes']],[0,1])
        self.assertIn('gate',report['scenes'][1]['phases'][0]['action'])
        enforce(project,cues)
        project['scenes'][1]['params']['action_plan']=copy.deepcopy(project['scenes'][0]['params']['action_plan'])
        with self.assertRaisesRegex(ValueError,'repeated'):enforce(project,cues)
    def test_third_identical_idea_stops_instead_of_relabeling(self):
        with self.assertRaisesRegex(ValueError,'Camera changes do not count'):
            self.make(['People criticize the person.']*3)
    def test_fake_plan_id_does_not_prove_uniqueness(self):
        cues,project,_=self.make(['People criticize the person.'])
        project['scenes'][0]['params']['action_plan']['plan_id']='invented'
        with self.assertRaisesRegex(ValueError,'unregistered'):enforce(project,cues)
    def test_different_recipe_names_cannot_recycle_identical_object_actions(self):
        cues=[dict(id=i+1,text='Save money.') for i in range(2)]
        presets=[dict(kind='asset',icon='coin',secondary='wallet',action='transfer',domain='finance',recipe_id=name) for name in ('recipe-one','recipe-two')]
        choices=[dict(cue_id=i+1,action='python',theme=None) for i in range(2)]
        with self.assertRaisesRegex(ValueError,'exhausted'):compile_direction(cues,presets,choices)
    def test_phase_beats_cover_the_same_source_timeline_without_subtitles(self):
        cues,project,_=self.make(['Aag jalne lagi.','Heere dabav mein nikharte hain.'])
        plans=contract.read_json(self.root/'package/creative_plan.json')
        for scene,plan in zip(project['scenes'],plans['scenes']):
            self.assertEqual(len(plan['beats']),3)
            self.assertEqual(plan['beats'][0]['start_frame'],scene['start_frame'])
            self.assertEqual(plan['beats'][-1]['end_frame'],scene['end_frame'])
            self.assertTrue(all(not b['on_screen_text'] for b in plan['beats']))
        contract.validate_package(self.root/'package')
    def test_preview_rejects_motionless_subject_samples(self):
        scene=dict(id='fixed',engine='python');folder=self.root/'fixed';folder.mkdir()
        for i in range(1,4):Image.new('RGB',(320,180),'navy').save(folder/f'preview_{i:02}.png')
        report=inspect_frames(dict(scenes=[scene]),self.root)
        self.assertEqual(report['status'],'failed');self.assertIn('visible',report['failures'][0])
    def test_preview_cache_rechecks_frame_hashes(self):
        cues,project,_=self.make(['Aag jalne lagi.'])
        def fake_worker(command,progress,log,label,timeout,stall):
            task=contract.read_json(Path(command[-1]));folder=Path(task['output'])
            for i in range(1,4):
                image=Image.new('RGB',(320,180),'navy');ImageDraw.Draw(image).rectangle((100,80,100+i*30,140),fill='gold');image.save(folder/f'preview_{i:02}.png')
        with patch('motion.run_worker',side_effect=fake_worker) as worker:
            first=run(self.root,self.root/'package',project,cues);self.assertFalse(first['cache_used'])
            second=run(self.root,self.root/'package',project,cues);self.assertTrue(second['cache_used']);self.assertEqual(worker.call_count,1)
            sample=Path(second['preview_folder'])/project['scenes'][0]['id']/'preview_01.png';sample.write_bytes(b'corrupted')
            third=run(self.root,self.root/'package',project,cues);self.assertFalse(third['cache_used']);self.assertEqual(worker.call_count,2)
    def test_preview_failure_retains_the_previous_delivered_video(self):
        for folder in ('INPUT','OUTPUT','_SYSTEM/work','_SYSTEM/reports'):(self.root/folder).mkdir(parents=True,exist_ok=True)
        contract.write_json(self.root/'_SYSTEM/installation.json',dict(format=contract.VERSION))
        contract.write_json(self.root/'_SYSTEM/local_ai.json',dict(DEFAULTS,enabled=False,authoring_mode='hybrid'))
        (self.root/'INPUT/source.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nAag jalne lagi.\n')
        old=self.root/'OUTPUT/final.mp4';old.write_bytes(b'previous narrated delivery')
        with patch('hybrid_pipeline.sys.addaudithook'),patch('preview_gate.run',side_effect=ValueError('Preview motion failed')),patch('motion.execute') as render:
            self.assertEqual(motion.main(['run','--workspace',str(self.root)]),1)
        render.assert_not_called();self.assertEqual(old.read_bytes(),b'previous narrated delivery')


if __name__=='__main__':unittest.main()
