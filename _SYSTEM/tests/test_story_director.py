"""Narration grounding, cross-caption continuity and honest speech confidence."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from character_catalog import ACTIONS,candidates
from story_director import direct,merge_continuous,evaluate
from voice_alignment import match_words,apply_timing


class DirectorTests(unittest.TestCase):
    def test_negation_and_metaphors_do_not_create_literal_actions(self):
        for text in ('He does not run.','Do not drink water.','वह किताब नहीं पढ़ता।','Run a business.','Jump to conclusions.','इस बात पर ध्यान देना।'):
            self.assertEqual(candidates(dict(text=text),{}),[],text)
        self.assertIn('read',candidates(dict(text='He does not run. He reads a book.'),{}))
        self.assertEqual(candidates(dict(text='Go to another room.'),{}),[])

    def test_catalog_includes_distinct_physical_actions(self):
        self.assertEqual(len(ACTIONS),32)
        for text,action in [('He is typing on a laptop.','type'),('वह खाना बना रहा है।','cook'),
                            ('She waters a plant.','water_plant'),('She is cycling.','cycle'),
                            ('He does pushups.','pushup'),('वह नोट्स लिख रहा है।','write')]:
            self.assertEqual(candidates(dict(text=text),{})[0],action)
        self.assertEqual(candidates(dict(text='Woh kitab padh raha hai.'),{})[0],'read')
        self.assertEqual(candidates(dict(text='Kitab mat padhna.'),{}),[])
        self.assertEqual(candidates(dict(text='A robot is reading a book.'),{}),[])

    def test_director_protects_full_body_and_changes_repeated_shots(self):
        cues=[dict(id=i+1,text='He runs on a treadmill.') for i in range(4)]
        choices=[dict(cue_id=i+1,action='run',camera='detail') for i in range(4)]
        output=direct(cues,choices)
        self.assertEqual(output[0]['story_role'],'hook')
        self.assertEqual(output[-1]['story_role'],'closing')
        self.assertTrue(all(x['camera']!='detail' for x in output))
        self.assertEqual(len(set(x['camera'] for x in output)),2)

    def test_continuous_captions_merge_and_keep_all_claims(self):
        scenes=[];plans=[]
        for i in range(3):
            scenes.append(dict(id=str(i),engine='blender',start_frame=i*48,end_frame=(i+1)*48,
                source_cues=[i+1],params=dict(action='read',environment='study',emotion='focused')))
            plans.append(dict(beats=[dict(start_frame=i*48,end_frame=(i+1)*48)],claims=[dict(text='illustration'),dict(text=f'source {i}')]))
        merge_continuous(scenes,plans,max_seconds=4)
        self.assertEqual(len(scenes),2)
        self.assertEqual(scenes[0]['source_cues'],[1,2])
        self.assertEqual(len(plans[0]['claims']),3)
        self.assertEqual(scenes[0]['end_frame'],scenes[1]['start_frame'])

    def test_emotion_change_prevents_merging(self):
        scenes=[dict(id=str(i),engine='blender',start_frame=i*24,end_frame=(i+1)*24,source_cues=[i+1],
            params=dict(action='talk',environment='living',emotion=emotion)) for i,emotion in enumerate(('happy','concerned'))]
        plans=[dict(beats=[],claims=[{}]) for _ in scenes]
        merge_continuous(scenes,plans);self.assertEqual(len(scenes),2)

    def test_graphic_continuity_keeps_source_beats_without_merging_different_themes(self):
        scenes=[dict(id=str(i),engine='python',start_frame=i*48,end_frame=(i+1)*48,source_cues=[i+1],
            params=dict(theme=theme,semantic_cues=[i+1])) for i,theme in enumerate(('fire','fire','pressure'))]
        plans=[dict(beats=[dict(start_frame=s['start_frame'],end_frame=s['end_frame'])],
                    claims=[dict(text='metaphor'),dict(text=str(i))]) for i,s in enumerate(scenes)]
        merge_continuous(scenes,plans)
        self.assertEqual(len(scenes),2)
        self.assertEqual(scenes[0]['params']['semantic_cues'],[1,2])
        self.assertEqual(len(plans[0]['beats']),2)
        self.assertEqual(scenes[0]['end_frame'],96)
        self.assertEqual(scenes[1]['params']['theme'],'pressure')

    def test_asr_matching_rejects_wrong_words_and_timing_drift(self):
        cues=[dict(id=1,start=0,end=2000,text='Read a book')]
        correct=[dict(word=word,start=.1+i*.3,end=.3+i*.3) for i,word in enumerate(('Read','a','book'))]
        self.assertTrue(match_words(cues,correct)['cue_level_timing_verified'])
        for bad in ([dict(word='Some unrelated speech',start=.1,end=.9)],
                    [dict(word='Read a book',start=10,end=11)]):
            report=match_words(cues,bad)
            self.assertFalse(report['cue_level_timing_verified'])
            self.assertEqual(report['cues'][0]['action_beats'],[])
        hindi=[dict(id=1,start=0,end=2000,text='वह किताब पढ़ता है।')]
        words=[dict(word=word,start=.1+i*.3,end=.3+i*.3) for i,word in enumerate(('वह','किताब','पढ़ता','है'))]
        self.assertTrue(match_words(hindi,words)['cue_level_timing_verified'])

    def test_speech_beats_use_group_local_time_without_source_edits(self):
        cues=[dict(id=2,start=2000,end=4000,text='Read a book')]
        scene=dict(engine='blender',start_frame=24,end_frame=96,source_cues=[2],params={})
        apply_timing([scene],dict(cues=[dict(cue_id=2,action_beats=[.2,.6])]),cues)
        self.assertEqual(scene['params']['speech_beats'],[1.2,1.6])
        self.assertEqual(cues[0]['start'],2000)

    def test_registered_blender_code_remains_policy_valid(self):
        contract.blender_code((contract.SYSTEM/'blender_character.py').read_text(encoding='utf-8'))

    def test_frame_rounding_overlap_does_not_hide_abstract_meaning(self):
        cues=[dict(id=1),dict(id=2)]
        scenes=[dict(id='abstract_story__001_01__wide',engine='python',source_cues=[1],params=dict(semantic_cues=[1])),
                dict(id='physical__002_01__wide',engine='blender',source_cues=[1,2],params=dict(action='walk',camera='wide',semantic_cues=[2]))]
        review=evaluate(cues,scenes)
        self.assertEqual(review['abstract_cues'],[1])
        self.assertEqual(review['literal_cue_fraction'],.5)


if __name__=='__main__':unittest.main()
