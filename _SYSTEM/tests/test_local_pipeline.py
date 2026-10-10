"""Local workflow acceptance and preservation checks without paid/network inference."""
import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contract
import local_pipeline as local
import motion


class FakeModel:
    def __init__(self):
        self.calls = 0
        self.unloads = 0

    def inventory(self):
        return {"models": [{"name": "test-model", "digest": "a"*64}]}

    def unload(self):
        self.unloads += 1

    def generate(self, messages, schema, tokens):
        self.calls += 1
        if "matches_source" in schema["properties"]:
            return dict(matches_source=True, blocking_issues=[]), {}
        if "engine" in schema["properties"]:
            return dict(engine="python", engine_reason="A flat illustrated phone moving across a desk needs 2D animation.",
                        visual_goal="Show an illustrated phone moving away from an open book.", main_objects=["phone", "book"],
                        beats=[dict(kind="object_action", action="An illustrated phone slides away while the book stays on the desk.")]), {}
        return {"function_body": "image=ctx.canvas()\nd=ImageDraw.Draw(image)\nx=round(300+t*100)\nd.rounded_rectangle((x,200,x+140,460),radius=20,fill=(240,240,240))\nd.rectangle((x+12,235,x+128,425),fill=(30,60,120))\nd.ellipse((x+60,435,x+80,455),fill=(0,0,0))\nd.polygon([(700,280),(820,250),(820,460),(700,490)],fill=(230,210,180))\nd.polygon([(820,250),(940,280),(940,490),(820,460)],fill=(250,230,200))\nreturn image\n"}, {}


class LocalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=contract.SYSTEM / "reports", prefix="local_test_")
        self.root = Path(self.temp.name)
        for name in ("INPUT", "OUTPUT", "_SYSTEM/work", "_SYSTEM/reports"):
            (self.root/name).mkdir(parents=True)
        contract.write_json(self.root/"_SYSTEM/installation.json", {"format": contract.VERSION})
        self.source = self.root/"INPUT/Script.txt"
        self.source.write_text("1\n00:00:00,000 --> 00:00:03,000\nMove the phone away from the open book.\n", encoding="utf-8")
        self.config = dict(local.DEFAULTS, enabled=True, model="test-model")
        contract.write_json(self.root/"_SYSTEM/local_ai.json", self.config)

    def tearDown(self):
        self.temp.cleanup()

    def author(self, client=None):
        return local.Author(self.root, self.config, self.source, contract.parse_srt(self.source), None, client or FakeModel())

    def test_local_inputs_need_no_zip_and_accept_case_and_filename(self):
        source, cues, voice = local.local_inputs(self.root)
        self.assertEqual(source, self.source)
        self.assertEqual(len(cues), 1)
        self.assertIsNone(voice)
        self.source.rename(self.root/"INPUT/Another Script.srt")
        self.assertEqual(local.local_inputs(self.root)[0].name, "Another Script.srt")

    def test_ambiguous_scripts_rejected(self):
        shutil.copy2(self.source, self.root/"INPUT/copy.srt")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            local.local_inputs(self.root)

    def test_canonical_duplicate_sources_must_match(self):
        second = self.root/"INPUT/source.srt"
        shutil.copy2(self.source, second)
        self.assertEqual(local.local_inputs(self.root)[0], second)
        second.write_text(second.read_text().replace("Move", "Keep"))
        with self.assertRaisesRegex(ValueError, "disagree"):
            local.local_inputs(self.root)

    def test_return_zip_selects_existing_external_workflow(self):
        (self.root/"INPUT/return.zip").write_bytes(b"placeholder")
        with patch.object(motion, "execute", return_value=0) as external, patch.object(local, "run_local") as internal:
            self.assertEqual(motion.main(["run", "--workspace", str(self.root)]), 0)
        external.assert_called_once()
        internal.assert_not_called()

    def test_launcher_routes_script_only_to_local(self):
        with patch.object(local, "run_local", return_value=0) as internal, patch.object(motion, "execute") as external:
            self.assertEqual(motion.main(["run", "--workspace", str(self.root)]), 0)
        internal.assert_called_once()
        external.assert_not_called()

    def test_audio_mismatch_rejects_before_inference_and_keeps_movie(self):
        with wave.open(str(self.root/"INPUT/voice.wav"), "wb") as stream:
            stream.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            stream.writeframes(b"\0\0"*48000)
        prior = self.root/"OUTPUT/final.mp4"
        prior.write_bytes(b"previous delivery")
        with patch.object(local, "Author") as author:
            self.assertEqual(motion.main(["run", "--workspace", str(self.root)]), 1)
        author.assert_not_called()
        self.assertEqual(prior.read_bytes(), b"previous delivery")
        self.assertIn("Supply aligned audio", contract.read_json(self.root/"OUTPUT/ERROR.json")["error"])

    def test_long_cue_splits_visuals_preserves_source_ids_and_duration(self):
        cues = [{"id": 10, "start": 0, "end": 20100, "text": "Read the book."}]
        project = local.project_for(cues, self.source, 8)
        self.assertEqual(project["total_frames"], 482)
        self.assertEqual([(s["start_frame"],s["end_frame"]) for s in project["scenes"]], [(0,192),(192,384),(384,482)])
        self.assertTrue(all(s["source_cues"] == [10] for s in project["scenes"]))
        self.assertEqual(cues[0]["end"], 20100)

    def test_packaging_preserves_source_and_reuses_checked_authoring(self):
        client = FakeModel()
        author = self.author(client)
        original = self.source.read_bytes()
        author.build()
        project, cues, qa = contract.validate_package(author.package, self.source)
        self.assertEqual(qa["status"], "authored_unverified")
        self.assertEqual(qa["capabilities"]["image_inspection"], False)
        self.assertEqual(author.package.joinpath("source.srt").read_bytes(), original)
        self.assertEqual(client.calls, 3)
        self.author(client).build()
        self.assertEqual(client.calls, 3)
        self.assertEqual(self.source.read_bytes(), original)

    def test_forbidden_code_does_not_execute_and_attempts_are_bounded(self):
        author = self.author()
        bad = FakeModel()
        bad.generate = lambda *args: ({"function_body": "import os\nreturn ctx.canvas()\n"}, {})
        author.client = bad
        scene = author.project["scenes"][0]
        with self.assertRaisesRegex(ValueError, "could not complete"):
            author.retry("bad", [{"role":"system","content":"test"}], local.CODE_SCHEMA, 100,
                         lambda r: local.body_module(r["function_body"], scene))
        self.assertEqual(author.state["calls"]["bad"], 3)
        with self.assertRaisesRegex(ValueError, "could not complete"):
            author.retry("bad", [], local.CODE_SCHEMA, 100, lambda r: None)
        self.assertEqual(author.state["calls"]["bad"], 3)

    def test_body_profile_rejects_main_demo_and_wraps_valid_drawing(self):
        scene = self.author().project["scenes"][0]
        with self.assertRaisesRegex(ValueError, "main block"):
            local.body_module("if __name__ == '__main__':\n    return ctx.canvas()", scene)
        with self.assertRaisesRegex(ValueError, "entry function"):
            local.body_module("def scene_001(t, ctx):\n    return ctx.canvas()", scene)
        self.assertIn("def scene_001(t, ctx):", local.body_module("return ctx.canvas()", scene))

    def test_malformed_and_repeated_planner_actions_rejected(self):
        with self.assertRaisesRegex(ValueError, "natural English"):
            local.check_action_prose(dict(visual_goal="Illustrate the requested object action clearly.",
                beats=[{"action":"hand_place_phone_on_desk_"*5}]))
        with self.assertRaisesRegex(ValueError, "Repeated action"):
            local.check_action_prose(dict(visual_goal="Illustrate the requested object action clearly.",
                beats=[{"action":"The hand moves the phone away. "*4}]))
    def test_scene_helpers_cannot_replace_other_scenes(self):
        author = self.author()
        source = "def scene_001(t, ctx):\n    return ctx.canvas()\ndef scene_002(t, ctx):\n    return ctx.canvas()\n"
        with self.assertRaisesRegex(ValueError, "Prefix helper"):
            local.audit_code(source, author.project["scenes"][0])

    def test_blender_authoring_gets_its_own_script_and_host_entry(self):
        client = FakeModel()
        original_generate = client.generate
        def generate(messages, schema, tokens):
            if "engine" in schema["properties"]:
                result, metrics = original_generate(messages,schema,tokens)
                result.update(engine="blender", engine_reason="Depth and a perspective camera explain the spatial object movement.")
                return result, metrics
            if "function_body" in schema["properties"]:
                return dict(function_body="studio(ctx)\nobj=box('phone',(0,0,1),(1,2,.2),'blue')\ncamera(ctx,(4,-6,5),(0,0,1),ortho=8)\nkey(obj,'location',[(spec['start_frame']/24*1000,(0,0,1)),(spec['end_frame']/24*1000,(3,0,1))],ctx)\n"), {}
            return original_generate(messages,schema,tokens)
        client.generate = generate
        author = self.author(client)
        # This tests package authoring, not an installed Blender executable.
        # Verify that tool preflight is requested; production keeps the real gate.
        with patch('motion.tools_for', return_value={}) as tools:
            author.build()
        tools.assert_called_once_with(author.project)
        project, _, _ = contract.validate_package(author.package, self.source)
        self.assertEqual(project["scenes"][0]["engine"], "blender")
        self.assertTrue((author.package/"scripts/scene_001.py").is_file())
        self.assertFalse((author.package/"scenes.py").exists())

    def test_source_meaning_rejection_stops_before_code(self):
        client = FakeModel()
        original_generate = client.generate
        def generate(messages,schema,tokens):
            if "matches_source" in schema["properties"]:
                return dict(matches_source=False, blocking_issues=["Moving the phone closer reverses the narration."]), {}
            return original_generate(messages,schema,tokens)
        client.generate = generate
        author = self.author(client)
        with self.assertRaisesRegex(ValueError, "Source-meaning diagnostic rejected"):
            author.build()
        self.assertFalse((author.package/"scenes.py").exists())
        self.assertEqual(author.state["calls"]["plan_scene_001"], 3)

    def test_render_failure_repaired_only_within_bound(self):
        author = self.author()
        author.build()
        failure = local.SceneFailure(["scene_001"], "Phone is outside the canvas")
        author.repair(failure)
        author.repair(failure)
        with self.assertRaisesRegex(ValueError, "repair limit"):
            author.repair(failure)
        self.assertEqual(author.state["render_repairs"]["scene_001"], 2)

    def test_reviewer_failure_prevents_publication(self):
        author = self.author()
        author.build()
        prior = self.root/"OUTPUT/final.mp4"
        prior.write_bytes(b"previous delivery")
        with self.assertRaises(local.SceneFailure):
            motion.execute(self.root, selection=(author.package,self.source,None),
                           reviewer=lambda *args: (_ for _ in ()).throw(local.SceneFailure(["scene_001"], "Blank scene")))
        self.assertEqual(prior.read_bytes(), b"previous delivery")

    def test_blank_local_sample_review_blocks_publication_without_false_approval(self):
        author = self.author()
        author.build()
        author.client.generate = lambda *args: (dict(visible_objects=[], mostly_blank=True, blocking_defects=[],
                                                    limitations=["Static samples only."]), {})
        prior = self.root/"OUTPUT/final.mp4"
        prior.write_bytes(b"previous delivery")
        with self.assertRaises(local.SceneFailure):
            motion.execute(self.root, selection=(author.package,self.source,None), reviewer=author.review)
        self.assertEqual(prior.read_bytes(), b"previous delivery")
        report = contract.read_json(author.root/"latest_visual_review.json")
        self.assertEqual(report["status"], "changes_required")
        self.assertFalse(report["artistic_approval"])
        self.assertFalse(report["complete_video_inspected"])


if __name__ == "__main__":
    unittest.main()
