"""Offline production routing, semantics, catalog integrity, and source preservation."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
import local_pipeline
import motion
import self_pipeline as self_mode
from asset_store import AssetStore


class SelfModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = AssetStore()

    def test_self_route_does_not_require_ollama_enabled(self):
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root = Path(directory)
            for name in ("INPUT","OUTPUT","_SYSTEM/work","_SYSTEM/reports"):
                (root/name).mkdir(parents=True)
            contract.write_json(root/"_SYSTEM/installation.json",dict(format=contract.VERSION))
            contract.write_json(root/"_SYSTEM/local_ai.json",dict(local_pipeline.DEFAULTS,enabled=False,authoring_mode="self",vision_checks=False))
            with patch.object(self_mode,"run_self",return_value=0) as run,patch("ollama_client.LocalOllama",side_effect=AssertionError("No model may be constructed")):
                self.assertEqual(motion.main(["run","--workspace",str(root)]),0)
            run.assert_called_once()

    def test_unknown_subject_requires_choice_instead_of_unrelated_movie(self):
        cues=[dict(id=1,start=0,end=3000,text="An unknown abstract narrative with no registered subject.")]
        selected,missing=self_mode.select(cues,self.store)
        self.assertEqual(selected,[None])
        self.assertEqual(missing[0]["cue_id"],1)

    def test_user_selection_can_resolve_unfamiliar_content_without_code(self):
        cues=[dict(id=1,start=0,end=3000,text="An unfamiliar narrative.")]
        selected,missing=self_mode.select(cues,self.store,{"1":{"icon":"volcano","action":"cutaway"}})
        self.assertFalse(missing)
        self.assertEqual(selected[0]["origin"],"user_choice")
        with self.assertRaises(ValueError):
            self_mode.select(cues,self.store,{"1":{"icon":"../bad","action":"cutaway"}})

    def test_negated_transport_is_not_depicted_as_moving(self):
        selected,missing=self_mode.select([dict(id=1,text="यह ट्रेन नहीं चलती है।")],self.store)
        self.assertFalse(missing)
        self.assertEqual(selected[0]["action"],"cutaway")

    def test_broad_subjects_and_continuation(self):
        cues=[dict(id=1,text="ट्रेन बाजार से गुजरती है।"),dict(id=2,text="फिर यह आगे बढ़ती है।"),dict(id=3,text="रुपये की बचत करो।")]
        selected,missing=self_mode.select(cues,self.store)
        self.assertFalse(missing)
        self.assertEqual(selected[0]["icon"],"train")
        self.assertEqual(selected[1]["origin"],"continuation_rule")
        self.assertEqual(selected[2]["icon"],"currency-rupee")

    def test_socket_guard_blocks_model_and_internet_connections(self):
        for event in ("socket.__new__","socket.connect","socket.getaddrinfo"):
            with self.assertRaises(PermissionError):
                self_mode.no_network(event,())
        self_mode.no_network("open",())

    def test_catalog_and_selected_media_detect_tampering(self):
        self.assertEqual(len(self.store.names()),6238)
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root=Path(directory)
            for name in ("source.json","tabler.json","animated_manifest.json"):
                shutil.copy2(self.store.root/name,root/name)
            with (root/"tabler.json").open("ab") as handle:
                handle.write(b" ")
            with self.assertRaisesRegex(ValueError,"checksum"):
                AssetStore(root)

    def test_long_input_is_split_and_source_kept_exact(self):
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root=Path(directory)
            source=root/"source.srt"
            raw=b"1\r\n00:00:00,000 --> 00:10:00,000\r\nThe train travels through the market.\r\n"
            source.write_bytes(raw)
            cues=contract.parse_srt(source)
            selected,missing=self_mode.select(cues,self.store)
            self.assertFalse(missing)
            project,_=self_mode.build_package(root/"package",source,cues,selected,self.store)
            self.assertEqual(project["total_frames"],14400)
            self.assertEqual(len(project["scenes"]),75)
            self.assertEqual((root/"package/source.srt").read_bytes(),raw)
            self.assertTrue(all(s["end_frame"]-s["start_frame"]<=192 for s in project["scenes"]))

    def test_habit_interactions_take_precedence_over_generic_icons(self):
        selected,missing=self_mode.select([dict(id=1,text="फोन को दूसरे कमरे में रखो।")],self.store)
        self.assertFalse(missing)
        self.assertEqual(selected[0]["family"],"phone_away")

    def test_astronomy_subject_relationship_is_not_reversed(self):
        selected,missing=self_mode.select([dict(id=1,text="Earth revolves in orbit around the sun.")],self.store)
        self.assertFalse(missing)
        self.assertEqual(selected[0]["icon"],"sun")
        self.assertEqual(selected[0]["secondary"],"world")

    def test_subject_position_matters_more_than_dictionary_order(self):
        selected,missing=self_mode.select([dict(id=1,text="The atom is the subject of this science illustration.")],self.store)
        self.assertFalse(missing)
        self.assertEqual(selected[0]["icon"],"atom")

    def test_invalid_configuration_reports_the_original_error(self):
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root=Path(directory)
            for name in ("INPUT","OUTPUT","_SYSTEM/work","_SYSTEM/reports"):
                (root/name).mkdir(parents=True)
            contract.write_json(root/"_SYSTEM/installation.json",dict(format=contract.VERSION))
            contract.write_json(root/"_SYSTEM/local_ai.json",[])
            self.assertEqual(motion.main(["run","--workspace",str(root)]),1)
            error=contract.read_json(root/"OUTPUT/ERROR.json")
            self.assertIn("mapping",error["error"])
            self.assertNotIn("Unbound",error["error"])

    def test_build_preset_starts_with_a_visible_subject(self):
        import importlib.util
        from motion_sdk import Context
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root=Path(directory)
            source=root/"source.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:04,000\nThe plant is the subject.\n",encoding="utf-8")
            cues=contract.parse_srt(source)
            chosen,missing=self_mode.select(cues,self.store)
            self.assertFalse(missing)
            project,_=self_mode.build_package(root/"package",source,cues,chosen,self.store)
            module_spec=importlib.util.spec_from_file_location("subject_visibility_test",root/"package/scenes.py")
            module=importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            scene=project["scenes"][0]
            ctx=Context(1280,720,24,0,0,4,scene["id"],root/"package/assets")
            frame=module.render(0,ctx)
            # The source object is the only teal item in this initial frame.
            self.assertGreater(sum(pixel==(104,222,209) for pixel in frame.getdata()),100)

    def test_registered_habit_routes_to_film_not_the_retired_stage(self):
        import importlib.util
        from motion_sdk import Context
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as directory:
            root=Path(directory)
            source=root/"source.srt"
            source.write_text("1\n00:00:00,000 --> 00:00:05,000\nThe alarm stops with snooze.\n",encoding="utf-8")
            cues=contract.parse_srt(source)
            chosen,missing=self_mode.select(cues,self.store)
            self.assertFalse(missing)
            project,_=self_mode.build_package(root/"package",source,cues,chosen,self.store)
            module_spec=importlib.util.spec_from_file_location("film_routing_test",root/"package/scenes.py")
            module=importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            scene=project["scenes"][0]
            ctx=Context(1280,720,24,2,0,5,scene["id"],root/"package/assets")
            with patch.object(module,"render_habit",side_effect=AssertionError("Retired renderer must not run")):
                frame=module.render(2,ctx)
            self.assertEqual(frame.size,(1280,720))
            # The alarm insert is visibly staged in a daylight room, rather than
            # merely renaming or recoloring the former navy illustration stage.
            self.assertGreater(sum(min(pixel)>110 for pixel in frame.getdata()),200000)
            self.assertEqual(module.SCENE_SPECS[scene['id']]['renderer'],"illustrated_film_3.0")


if __name__=="__main__":
    unittest.main()
