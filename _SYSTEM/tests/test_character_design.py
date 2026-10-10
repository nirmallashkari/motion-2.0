"""Story identity stability, appearance variation and character-first order."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from character_design import design, validate_profile, bind_choices, enforce_project
from cloud_planner import make_request
from asset_store import AssetStore
from local_pipeline import DEFAULTS
from self_pipeline import select, build_package
from story_planner import plan_story
from narrative_catalog import choose
from story_director import direct
from action_direction import compile_direction
from shot_policy import assign


def cues(text):
    return [dict(id=1, start=0, end=1000, text=text)]


class StoryCharacterTests(unittest.TestCase):
    def test_same_story_and_different_timing_keep_exact_appearance(self):
        first = design(cues('A writer works hard.'))
        other = [dict(id=9, start=4000, end=7000, text='A writer'), dict(id=10, start=7000, end=10000, text='works hard.')]
        self.assertEqual(first, design(other))

    def test_different_stories_change_actual_shapes_not_only_identity(self):
        appearances = [design(cues(f'A traveler explores mountain {i}.'))['appearance'] for i in range(100)]
        self.assertEqual(len({json.dumps(p, sort_keys=True) for p in appearances}), 100)
        self.assertEqual(len({json.dumps(p['shape'], sort_keys=True) for p in appearances}), 100)

    def test_explicit_hair_and_glasses_hints_are_obeyed(self):
        profile = design(cues('A writer with glasses and curly hair opens a notebook.'))
        self.assertEqual(profile['appearance']['hairstyle'], 'soft_curls')
        self.assertTrue(profile['appearance']['glasses'])
        profile = design(cues('A traveler with long hair and silver hair explores a path.'))
        self.assertEqual(profile['appearance']['hairstyle'], 'long_bob')
        self.assertEqual(profile['appearance']['palette']['hair'], [.37, .40, .43, 1])

    def test_tampered_and_nonfinite_profiles_are_rejected(self):
        for value in [.8, float('nan')]:
            profile = design(cues('Work hard.'))
            profile['appearance']['shape']['width'] = value
            with self.assertRaises(ValueError):
                validate_profile(profile)
        profile = design(cues('Work hard.'))
        profile['identity_id'] = '0'*64
        with self.assertRaises(ValueError):
            validate_profile(profile)

    def test_package_locks_every_blender_scene_and_detects_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'source.srt'
            source.write_text('1\n00:00:00,000 --> 00:00:01,000\nApne kaam se jawab dena.\n')
            source_cues = cues('Apne kaam se jawab dena.')
            store = AssetStore()
            selected, _ = plan_story(source_cues, store, select)
            pairs, _ = choose(source_cues, selected, dict(DEFAULTS, enabled=False), root)
            selected = [p[0] for p in pairs]
            choices = direct(source_cues, [p[1] for p in pairs])
            choices, _ = compile_direction(source_cues, selected, choices)
            choices = assign(source_cues, selected, choices)
            profile = design(source_cues)
            project, _ = build_package(root/'package', source, source_cues, selected, store,
                                       character_choices=bind_choices(choices, profile))
            self.assertEqual(project['scenes'][0]['engine'], 'blender')
            enforce_project(project, profile)
            project['scenes'][0]['params']['character_profile']['appearance']['shape']['width'] = .8
            with self.assertRaises(ValueError):
                enforce_project(project, profile)

    def test_cloud_request_contains_the_locked_identity(self):
        source_cues = cues('Apne kaam se jawab dena.')
        store = AssetStore()
        selected, _ = plan_story(source_cues, store, select)
        profile = design(source_cues)
        locked = dict(identity_id=profile['identity_id'], brief=profile['brief'], appearance=profile['appearance'])
        cloud = dict(model='Qwen/Qwen3-8B', model_revision='b968826d9c46dd6066d109eabc6255188de91218')
        with tempfile.TemporaryDirectory() as tmp:
            request = make_request(Path(tmp), source_cues, selected, dict(DEFAULTS, locked_character=locked), cloud, store)
        self.assertEqual(json.loads(request['jobs'][0]['messages'][1]['content'])['locked_character'], locked)

    def test_failed_character_design_stops_before_planning_or_rendering(self):
        import hybrid_pipeline
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'OUTPUT').mkdir()
            prior = root/'OUTPUT/final.mp4'
            prior.write_bytes(b'prior delivery')
            with patch('hybrid_pipeline.sys.addaudithook'), patch('cloud_planner.configuration', return_value=dict(enabled=False)), \
                 patch('local_pipeline.local_inputs', return_value=(root/'source.srt', cues('Work hard.'), None)), \
                 patch('character_design.ensure_character', side_effect=ValueError('Face geometry failed')), \
                 patch('hybrid_pipeline.choose_narrative') as planner, patch('motion.execute') as renderer:
                with self.assertRaisesRegex(ValueError, 'Face geometry failed'):
                    hybrid_pipeline.run_hybrid(root, dict(DEFAULTS, authoring_mode='hybrid'))
            planner.assert_not_called()
            renderer.assert_not_called()
            self.assertEqual(prior.read_bytes(), b'prior delivery')


if __name__ == '__main__':
    unittest.main()
