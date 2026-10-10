"""Grounded catalog, bounded local-AI choices and hybrid package routing."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from asset_store import AssetStore
from character_catalog import candidates
from hybrid_planner import offline_loopback, plan, validate_choices
from hybrid_pipeline import upgrade_package_scenes
from ollama_client import OllamaError
from self_pipeline import build_package,select
from story_planner import plan_story
import local_pipeline


class HybridTests(unittest.TestCase):
    def test_grounded_hindi_and_english_actions(self):
        for text,name in (("किताब पढ़ते हैं","read"),("व्यायाम करते हैं","lift"),
                          ("He is walking","walk"),("Move the phone to another room","carry_phone")):
            self.assertIn(name,candidates(dict(text=text),{}))
        self.assertEqual(candidates(dict(text="DNA and atoms are science concepts"),{}),[])

    def test_duplicate_cue_ids_rejected(self):
        batch=[dict(cue_id=1,choices=["read"]),dict(cue_id=2,choices=["walk"])]
        output=dict(scenes=[dict(cue_id=1,action="read",camera="wide")]*2)
        with self.assertRaises(ValueError):validate_choices(output,batch)

    def test_invented_actions_and_paths_rejected(self):
        batch=[dict(cue_id=1,choices=["read"])]
        for extra in (dict(action="execute_code"),dict(path="C:/unsafe.py")):
            item=dict(cue_id=1,action="read",camera="wide");item.update(extra)
            with self.assertRaises(Exception):validate_choices(dict(scenes=[item]),batch)

    def test_only_ollama_loopback_connections_allowed(self):
        offline_loopback("socket.connect",(None,("127.0.0.1",11434)))
        for address in (("8.8.8.8",11434),("127.0.0.1",80),("::1",11434)):
            with self.assertRaises(PermissionError):offline_loopback("socket.connect",(None,address))
        with self.assertRaises(PermissionError):offline_loopback("socket.getaddrinfo",("example.com",80))

    def test_unavailable_model_retains_catalog_and_reports_fallback(self):
        cues=[dict(id=1,start=0,end=2000,text="Read a book")]
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            client=unittest.mock.Mock();client.inventory.side_effect=OllamaError("Unavailable")
            choices,evidence=plan(Path(directory),cues,[{}],dict(local_pipeline.DEFAULTS,enabled=True),client)
            self.assertEqual(choices[0]["action"],"read")
            self.assertEqual(evidence["status"],"registered_fallback")
            self.assertEqual(evidence["runtime_ai_calls"],0)
            self.assertTrue(evidence["failures"])
            client.generate.assert_not_called()

    def test_valid_plan_is_source_bound_cached_data(self):
        cues=[dict(id=1,start=0,end=2000,text="Read a book")]
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            client=unittest.mock.Mock()
            client.generate.return_value=(dict(scenes=[dict(cue_id=1,action="read",camera="detail")]),{})
            config=dict(local_pipeline.DEFAULTS,enabled=True)
            first,evidence=plan(Path(directory),cues,[{}],config,client)
            second,cached=plan(Path(directory),cues,[{}],config,client)
            self.assertEqual(first,second);self.assertEqual(evidence["runtime_ai_calls"],1)
            self.assertTrue(cached["cache_used"]);self.assertEqual(cached["runtime_ai_calls"],0)
            client.generate.assert_called_once()

    def test_hybrid_package_uses_identical_registered_builder(self):
        store=AssetStore()
        cues=[dict(id=1,start=0,end=2000,text="Read a book"),
              dict(id=2,start=2000,end=4000,text="Earth orbits the sun")]
        selected,_=plan_story(cues,store,select)
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root=Path(directory);source=root/"source.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:02,000\nRead a book\n\n2\n00:00:02,000 --> 00:00:04,000\nEarth orbits the sun\n",encoding="utf-8")
            choices=[dict(cue_id=1,action="read",camera="medium"),dict(cue_id=2,action="python",camera="wide")]
            project,_=build_package(root/"package",source,cues,selected,store,character_choices=choices)
            self.assertEqual([s["engine"] for s in project["scenes"]],["blender","python"])
            self.assertEqual((root/"package/scripts/character.py").read_bytes(),(contract.SYSTEM/"blender_character.py").read_bytes())
            self.assertEqual((root/"package/source.srt").read_bytes(),source.read_bytes())

    def test_model_disabled_hybrid_still_routes(self):
        import motion
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root=Path(directory)
            for name in ("INPUT","OUTPUT","_SYSTEM/work","_SYSTEM/reports"):(root/name).mkdir(parents=True)
            contract.write_json(root/"_SYSTEM/installation.json",dict(format=contract.VERSION))
            contract.write_json(root/"_SYSTEM/local_ai.json",dict(local_pipeline.DEFAULTS,enabled=False,authoring_mode="hybrid"))
            with patch("hybrid_pipeline.run_hybrid",return_value=0) as run:
                self.assertEqual(motion.main(["run","--workspace",str(root)]),0)
            run.assert_called_once()

    def test_all_blender_package_has_no_undeclared_python_code(self):
        store=AssetStore();cues=[dict(id=1,start=0,end=2000,text='Write a note')]
        selected,_=plan_story(cues,store,select)
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as directory:
            root=Path(directory);source=root/'source.srt'
            source.write_text('1\n00:00:00,000 --> 00:00:02,000\nWrite a note\n',encoding='utf-8')
            package=root/'package'
            project,_=build_package(package,source,cues,selected,store,
                character_choices=[dict(cue_id=1,action='write',camera='wide')])
            self.assertEqual(project['scenes'][0]['engine'],'blender')
            self.assertFalse((package/'scenes.py').exists())
            contract.validate_package(package,source)


if __name__=="__main__":unittest.main()
