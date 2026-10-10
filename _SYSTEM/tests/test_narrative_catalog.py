"""Source concepts, human routing and registered data-to-render integration."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from asset_store import AssetStore
from local_pipeline import DEFAULTS
from narrative_catalog import CONCEPTS,grounded,choose
from human_policy import enforce,validate,human_free
from self_pipeline import build_package,select
from story_planner import plan_story
from editorial_gate import inspect


class NarrativeTests(unittest.TestCase):
    def test_roman_hindi_sources_get_distinct_meaningful_concepts(self):
        examples=[('Kabhi aaina dekha hai?','reflection'),('Raat ko bistar par lete ho.','night_reflection'),
            ('Log kehte hain tumse nahi hoga.','criticism'),('Aag tabhi lagti hai.','fire'),
            ('Heere dabav mein nikharte hain.','pressure'),('Apni taqdeer apne haath se likho.','destiny'),
            ('Apne andar ke sher ko jagao.','inner_power'),('Baazi palatni hai.','strategy')]
        for text,theme in examples:self.assertEqual(grounded(text),theme)

    def test_narrative_nonhuman_routes_never_accept_human_themes(self):
        for theme,item in CONCEPTS.items():
            self.assertEqual(human_free(dict(kind='narrative',theme=theme)),item['engine']=='python')

    def test_all_registered_concepts_form_valid_packages_without_generated_code(self):
        store=AssetStore()
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as directory:
            root=Path(directory)
            for theme,item in CONCEPTS.items():
                cues=[dict(id=1,start=0,end=3000,text=item['goal'])]
                source=root/'source.srt';source.write_text(f"1\n00:00:00,000 --> 00:00:03,000\n{item['goal']}\n",encoding='utf-8')
                selected=[dict(kind='narrative',theme=theme)]
                choices=[dict(cue_id=1,action=item.get('action','python'),camera='wide',theme=theme)]
                validate(cues,selected,choices)
                package=root/theme;project,_=build_package(package,source,cues,selected,store,character_choices=choices)
                self.assertEqual(project['scenes'][0]['engine'],item['engine'])
                self.assertEqual(project['scenes'][0]['params']['theme'],theme)
                self.assertEqual(inspect(project)['status'],'coverage_passed')
                contract.validate_package(package,source)

    def test_model_off_fallback_is_source_related_and_reports_no_model_calls(self):
        cues=[dict(id=1,start=0,end=3000,text='Kabhi aaina dekha hai?'),dict(id=2,start=3000,end=6000,text='Heere dabav mein nikharte hain.')]
        store=AssetStore();selected,_=plan_story(cues,store,select)
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as directory:
            scenes,evidence=choose(cues,selected,dict(DEFAULTS,enabled=False),Path(directory))
            self.assertEqual([choice['theme'] for _,choice in scenes],['reflection','pressure'])
            self.assertEqual(evidence['runtime_ai_calls'],0)

    def test_unrecognized_narration_still_cannot_claim_supported_coverage(self):
        cues=[dict(id=1,start=0,end=3000,text='An indefinable possibility unfolds.')]
        store=AssetStore();selected,_=plan_story(cues,store,select)
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as directory:
            scenes,_=choose(cues,selected,dict(DEFAULTS,enabled=False),Path(directory))
            self.assertEqual(scenes[0][0]['kind'],'abstract')
            self.assertEqual(scenes[0][1]['action'],'python')

    def test_rhetorical_setup_uses_following_explanation_and_negated_victory_is_not_literal(self):
        cues=[dict(id=1,start=0,end=2000,text='Par sabse bada dard pata hai kya hai?'),
              dict(id=2,start=2000,end=4000,text='Kisi aur ka galat bolna nahi.'),
              dict(id=3,start=4000,end=6000,text='Khud ki nazron mein gir jana!'),
              dict(id=4,start=6000,end=8000,text='Agar tum nahi ladoge toh koi tumhare liye jeetne nahi aayega.')]
        store=AssetStore();selected,_=plan_story(cues,store,select)
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as directory:
            scenes,_=choose(cues,selected,dict(DEFAULTS,enabled=False),Path(directory))
            self.assertEqual([choice['theme'] for _,choice in scenes],['selfworth','selfworth','selfworth','resolve'])


if __name__=='__main__':unittest.main()
