"""Regression checks for human routing and plain narration timing."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from asset_store import AssetStore
from human_policy import enforce, validate
from plain_source import estimated_cues, key, sections
from self_pipeline import build_package, select
from story_planner import plan_story


class HumanPolicyTests(unittest.TestCase):
    def test_model_cannot_keep_supported_human_template_in_python(self):
        cue=dict(id=1,text='Read a book')
        selected,choices,report=enforce([cue],[dict(kind='habit',family='small_start')],
            [dict(cue_id=1,action='python',camera='wide')])
        self.assertEqual(choices[0]['action'],'read')
        self.assertTrue(report['changes'])
        validate([cue],selected,choices)

    def test_unsupported_human_and_unknown_silhouette_become_human_free(self):
        for preset in (dict(kind='habit',family='unknown'),dict(kind='asset',icon='user',action='cutaway')):
            cue=dict(id=1,text='An indefinable possibility unfolds.')
            selected,choices,_=enforce([cue],[preset],[dict(cue_id=1,action='python',camera='wide')])
            self.assertEqual(selected[0]['kind'],'abstract')
            validate([cue],selected,choices)

    def test_bypass_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'Human routing violation'):
            validate([dict(id=1)],[dict(kind='asset',icon='walk')],[dict(cue_id=1,action='python')])

    def test_real_mixed_package_routes_walk_to_blender_and_preserves_python_objects(self):
        store=AssetStore()
        cues=[dict(id=1,start=0,end=2000,text='He walks along the path.'),
              dict(id=2,start=2000,end=4000,text='Earth revolves around the sun.'),
              dict(id=3,start=4000,end=6000,text='An indefinable possibility unfolds.')]
        selected,_=plan_story(cues,store,select)
        choices=[dict(cue_id=i,action='python',camera='wide') for i in range(1,4)]
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as directory:
            root=Path(directory);source=root/'source.srt'
            source.write_text('1\n00:00:00,000 --> 00:00:02,000\nHe walks along the path.\n\n2\n00:00:02,000 --> 00:00:04,000\nEarth revolves around the sun.\n\n3\n00:00:04,000 --> 00:00:06,000\nAn indefinable possibility unfolds.\n',encoding='utf-8')
            project,_=build_package(root/'package',source,cues,selected,store,character_choices=choices)
            self.assertEqual([s['engine'] for s in project['scenes']],['blender','python','python'])
            general=(contract.SYSTEM/'general_renderer.py').read_text()
            self.assertNotIn('film_actor(',general)
            contract.validate_package(root/'package',source)


class PlainTimingTests(unittest.TestCase):
    def test_long_sentence_does_not_leave_a_one_word_scene(self):
        parts=sections(' '.join(['word']*19)+'.',line_mode=False)
        self.assertEqual([len(part.split()) for part in parts],[10,9])
    def test_no_recognition_is_explicit_estimate_not_claimed_alignment(self):
        cues,evidence=estimated_cues('First sentence. Another sentence!',10,[],line_mode=False)
        self.assertEqual(evidence['method'],'proportional_estimate')
        self.assertFalse(evidence['exact_sync_verified'])
        self.assertEqual(cues[0]['start'],0);self.assertEqual(cues[-1]['end'],10000)
        self.assertEqual(cues[0]['end'],cues[1]['start'])
        self.assertEqual(' '.join(c['text'] for c in cues),'First sentence. Another sentence!')

    def test_roman_hindi_can_match_devanagari_words(self):
        self.assertEqual(key('tum'),key('तुम'))
        self.assertEqual(key('dekha'),key('देखा'))
        text='Kabhi aaina dekha hai? Khud par yakeen rakho.'
        words=[dict(word=w,start=i*.5,end=i*.5+.4) for i,w in enumerate(['कभी','आईना','देखा','है','खुद','पर','यकीन','रखो'])]
        cues,evidence=estimated_cues(text,5,words,line_mode=False)
        self.assertEqual(evidence['method'],'phonetic_asr_anchors')
        self.assertGreaterEqual(evidence['matched_word_fraction'],.7)
        self.assertEqual(cues[0]['end'],2000)
        self.assertEqual(cues[-1]['end'],5000)

    def test_degenerate_speech_times_never_make_zero_length_cues(self):
        words=[dict(word=w,start=1,end=1.1) for w in ['one','two','three','four']]
        cues,_=estimated_cues('One. Two. Three. Four.',5,words)
        self.assertTrue(all(c['end']>c['start'] for c in cues))


if __name__=='__main__':unittest.main()
