"""Source-unit preservation, expandable recipes and renderer-backed repeat gates."""
from pathlib import Path
import sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from asset_store import AssetStore
from local_pipeline import DEFAULTS
from plain_source import sections,estimated_cues
from narrative_catalog import CONCEPTS,choose
from visual_registry import recipes,relevant
from shot_policy import assign,enforce,inspect
from quality_check import check_repeats
from self_pipeline import build_package
from PIL import Image
from unittest.mock import Mock
from quality_check import check_motion
import motion


class LineVisualTests(unittest.TestCase):
    def test_authored_lines_survive_sentence_and_word_boundaries(self):
        text='First sentence. Another sentence!\n\n'+('word '*50).strip()+'\nLast line?'
        self.assertEqual(len(sections(text)),3)
        cues,evidence=estimated_cues(text,60,[])
        self.assertEqual([c['text'] for c in cues],sections(text))
        self.assertEqual(evidence['source_line_count'],3)
        self.assertEqual(cues[-1]['end'],60000)

    def test_registry_exceeds_twenty_and_reads_new_data_without_code_changes(self):
        store=AssetStore()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);catalog,before=recipes(store,CONCEPTS,root)
            self.assertGreater(len(catalog),20)
            item=dict(id='custom-money',keywords=['budget'],icon='coin',secondary='wallet',motion='transfer',goal='Transfer coins into a wallet to illustrate saving money.')
            contract.write_json(root/'new.json',dict(revision='visual-registry-1.0',recipes=[item]))
            catalog,after=recipes(store,CONCEPTS,root)
            self.assertNotEqual(before['library_hash'],after['library_hash'])
            self.assertIn('custom-money',relevant(dict(text='Build a budget.'),{},catalog))
            scenes,_=choose([dict(id=1,start=0,end=20000,text='Build a budget.')],[dict(kind='abstract')],dict(DEFAULTS,enabled=False),root,store=store,library_root=root)
            self.assertEqual(scenes[0][0]['recipe_id'],'custom-money')
            choices=assign([dict(id=1)], [scenes[0][0]], [scenes[0][1]])
            source=root/'source.srt';source.write_text('1\n00:00:00,000 --> 00:00:20,000\nBuild a budget.\n')
            project,_=build_package(root/'package',source,[dict(id=1,start=0,end=20000,text='Build a budget.')],[scenes[0][0]],store,character_choices=choices)
            self.assertEqual(len(project['scenes']),1)
            self.assertEqual(project['scenes'][0]['end_frame'],480)
            enforce(project,[dict(id=1)])

    def test_unsafe_recipe_cannot_introduce_humans_or_code(self):
        store=AssetStore()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            item=dict(id='bad',keywords=['test'],icon='user',secondary=None,motion='travel',goal='A source-related object moves across the scene.')
            contract.write_json(root/'bad.json',dict(revision='visual-registry-1.0',recipes=[item]))
            with self.assertRaisesRegex(ValueError,'nonhuman'):recipes(store,CONCEPTS,root)
            item.update(icon='coin',code='print(1)')
            contract.write_json(root/'bad.json',dict(revision='visual-registry-1.0',recipes=[item]))
            with self.assertRaisesRegex(ValueError,'data only'):recipes(store,CONCEPTS,root)

    def test_ids_alone_do_not_make_a_shot_unique(self):
        cues=[dict(id=i) for i in (1,2)]
        preset=dict(kind='narrative',theme='pressure')
        choices=assign(cues,[preset,preset],[dict(cue_id=i,action='python',theme='pressure') for i in (1,2)])
        self.assertNotEqual(choices[0]['shot_profile'],choices[1]['shot_profile'])
        scenes=[dict(id=str(i),params=dict(choice,semantic_cues=[i])) for i,choice in zip((1,2),choices)]
        enforce(dict(scenes=scenes),cues)
        scenes[1]['params']['shot_profile']=scenes[0]['params']['shot_profile']
        self.assertEqual(inspect(dict(scenes=scenes),cues)['status'],'failed')
        scenes[1]['params']['shot_profile']=dict(scenes[0]['params']['shot_profile'],name='invented-name')
        self.assertEqual(inspect(dict(scenes=scenes),cues)['status'],'failed')

    def test_model_extra_fields_are_rejected_and_reported(self):
        cues=[dict(id=1,start=0,end=1000,text='Build a budget.')]
        client=Mock();client.generate.return_value=(dict(scenes=[dict(cue_id=1,concept='money-saving',camera='wide',evidence='budget',command='bad')]),{})
        with tempfile.TemporaryDirectory() as temporary:
            scenes,report=choose(cues,[dict(kind='abstract')],dict(DEFAULTS,enabled=True,attempts=1),Path(temporary),client=client)
            self.assertEqual(report['successful_ai_calls'],0)
            self.assertTrue(report['failures'])
            self.assertEqual(scenes[0][0]['recipe_id'],'money-saving')
            client.unload.assert_called_once()

    def test_exhaustion_fails_instead_of_relabeling_a_repeat(self):
        cues=[dict(id=i) for i in range(16)]
        with self.assertRaisesRegex(ValueError,'exhausted'):
            assign(cues,[dict(kind='narrative')]*16,[dict(cue_id=i,action='python',theme='pressure') for i in range(16)])

    def test_decoded_picture_comparison_ignores_scene_names(self):
        frames=[Image.new('L',(160,90),v) for v in (20,30,40,50,60)]
        report=check_repeats([('different-id-1',frames),('different-id-2',[f.copy() for f in frames])])
        self.assertEqual(report['status'],'failed')
        self.assertEqual(check_repeats([('first',frames),('other',[Image.new('L',(160,90),180)]*5)])['status'],'passed')

    def test_actual_encoded_duplicate_sequence_fails_before_publication(self):
        tools=motion.tools_for(dict(scenes=[]))
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);movie=root/'duplicate.mp4';log=root/'decode.log'
            motion.encode([tools['ffmpeg'],'-v','error','-y','-f','lavfi','-i','testsrc2=size=160x90:rate=24:duration=1',
                '-vf','loop=loop=1:size=24:start=0','-frames:v','48','-c:v','libx264','-crf','0','-pix_fmt','yuv420p',str(movie)],log)
            project=dict(total_frames=48,canvas=dict(fps=24),scenes=[dict(id=str(i),start_frame=i*24,end_frame=(i+1)*24,params=dict(line_mode=True)) for i in range(2)])
            result=check_motion(movie,project,tools,log)
            self.assertEqual(result['no_repeat']['status'],'failed')
            self.assertTrue(any('R17' in failure for failure in result['failures']))


if __name__=='__main__':unittest.main()
