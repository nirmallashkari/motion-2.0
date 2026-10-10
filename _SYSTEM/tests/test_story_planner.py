"""Reusable planning boundaries and the no-per-project-code contract."""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'framework'))
import contract
from asset_store import AssetStore
from story_planner import plan_story
import self_pipeline
from motion_sdk import Context


class ReusablePlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store=AssetStore()

    def plan(self,texts,policy='abstract'):
        cues=[dict(id=i+1,start=i*4000,end=(i+1)*4000,text=text) for i,text in enumerate(texts)]
        return cues,plan_story(cues,self.store,self_pipeline.select,unmatched_policy=policy)

    def test_unknown_passage_finishes_without_inventing_a_literal_subject(self):
        _,(chosen,missing)=self.plan(['An unnameable possibility unfolds.'])
        self.assertFalse(missing)
        self.assertEqual(chosen[0]['kind'],'abstract')
        self.assertNotIn('icon',chosen[0])
        self.assertIn('not verified',chosen[0]['limitation'])

    def test_opt_in_strict_policy_still_stops(self):
        _,(chosen,missing)=self.plan(['An unnameable possibility unfolds.'],'stop')
        self.assertEqual(chosen,[None])
        self.assertEqual(len(missing),1)

    def test_finance_identity_is_not_turned_into_a_habit_mirror(self):
        _,(chosen,missing)=self.plan(['The coin verifies identity in this finance illustration.'])
        self.assertFalse(missing)
        self.assertEqual(chosen[0]['kind'],'asset')
        self.assertEqual(chosen[0]['icon'],'coin')
        self.assertEqual(chosen[0]['domain'],'finance')

    def test_original_habit_profile_is_still_selected(self):
        _,(chosen,missing)=self.plan(['Discipline begins when the alarm stops with snooze.'])
        self.assertFalse(missing)
        self.assertEqual(chosen[0]['kind'],'habit')

    def test_english_substrings_do_not_add_rain_to_a_train_scene(self):
        matches=self_pipeline.subjects('The train crosses the market.',self.store)
        self.assertNotIn('droplet',[icon for icon,_ in matches])
        self.assertIn('carrot',[icon for icon,_ in self_pipeline.subjects('Vegetables sit in the basket.',self.store)])

    def test_alias_is_not_duplicated_ahead_of_the_destination(self):
        _,(chosen,missing)=self.plan(['Transfer the phone to another room.'])
        self.assertFalse(missing)
        self.assertEqual(chosen[0]['secondary'],'home')

    def test_pronoun_uses_previous_explicit_subject(self):
        _,(chosen,missing)=self.plan(['A train passes through the market.','They continue along the route.'])
        self.assertFalse(missing)
        self.assertEqual(chosen[1]['icon'],'train')
        self.assertEqual(chosen[1]['origin'],'context_rule')
        self.assertEqual(chosen[0]['domain'],'market')

    def test_astronomy_relationship_and_hindi_aliases(self):
        _,(chosen,missing)=self.plan(['पृथ्वी सूर्य की परिक्रमा करती है।','डीएनए को सूक्ष्मदर्शी से देखते हैं।'])
        self.assertFalse(missing)
        self.assertEqual((chosen[0]['icon'],chosen[0]['secondary']),('sun','world'))
        self.assertEqual(chosen[1]['icon'],'dna')

    def test_different_sources_package_identical_registered_logic(self):
        trees=[]
        for text in ('The train travels.','Earth orbits the sun.','An unnameable possibility unfolds.'):
            cues,(chosen,missing)=self.plan([text])
            self.assertFalse(missing)
            with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as directory:
                root=Path(directory)
                source=root/'source.srt'
                source.write_text('1\n00:00:00,000 --> 00:00:04,000\n'+text+'\n',encoding='utf-8')
                project,_=self_pipeline.build_package(root/'package',source,cues,chosen,self.store)
                module_spec=importlib.util.spec_from_file_location('reusable_test',root/'package/scenes.py')
                module=importlib.util.module_from_spec(module_spec)
                module_spec.loader.exec_module(module)
                scene=project['scenes'][0]
                ctx=Context(1280,720,24,1,0,4,scene['id'],root/'package/assets')
                frame=module.render(1,ctx)
                self.assertEqual(frame.size,(1280,720))
                tree=ast.parse((root/'package/scenes.py').read_text(encoding='utf-8'))
                tree.body=[node for node in tree.body if not (isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='SCENE_SPECS' for target in node.targets))]
                trees.append(ast.dump(tree,include_attributes=False))
        self.assertEqual(trees[0],trees[1])
        self.assertEqual(trees[1],trees[2])


if __name__=='__main__':unittest.main()
