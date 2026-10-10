"""Behavior and boundary tests for the combined Motion workflow."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contract
import motion


class UnifiedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=contract.SYSTEM / "reports", prefix="unit_")
        self.root = Path(self.temporary.name)
        self.package = self.root / "return"
        shutil.copytree(contract.SYSTEM / "framework/example_return", self.package)
        self.original = contract.read_json(self.package / "project.json")

    def tearDown(self):
        self.temporary.cleanup()

    def edit(self, change):
        value = copy.deepcopy(self.original)
        change(value)
        contract.write_json(self.package / "project.json", value)

    def workspace(self):
        root = self.root / "workspace"
        for folder in ("INPUT", "OUTPUT", "_SYSTEM/work", "_SYSTEM/reports", "_SYSTEM/engines"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        contract.write_json(root / "_SYSTEM/installation.json", {"format": contract.VERSION})
        for folder in ("INPUT", "OUTPUT"):
            (root / folder / "README.txt").write_text("Keep this document")
        (root / "_SYSTEM/engines/protected.txt").write_text("engine")
        return root

    def test_mixed_contract_valid(self):
        project, cues, qa = contract.validate_package(self.package)
        self.assertEqual([s["engine"] for s in project["scenes"]], ["python", "blender", "python"])
        self.assertEqual(len(cues), 3)

    def test_python_only_contract_valid(self):
        def change(project):
            project["scenes"][1].update(engine="python", script="scenes.py", entry="intro")
        self.edit(change)
        (self.package / "scripts/cube.py").unlink()
        self.assertTrue(all(s["engine"] == "python" for s in contract.validate_package(self.package)[0]["scenes"]))

    def test_blender_only_contract_valid(self):
        def change(project):
            for scene in project["scenes"]:
                scene.update(engine="blender", script="scripts/cube.py", entry="build")
        self.edit(change)
        (self.package / "scenes.py").unlink()
        self.assertTrue(all(s["engine"] == "blender" for s in contract.validate_package(self.package)[0]["scenes"]))

    def test_relative_package_path_valid(self):
        relative = self.package.relative_to(Path.cwd())
        self.assertEqual(contract.validate_package(relative)[0]["total_frames"], 72)

    def test_unsupported_canvas_rejected(self):
        self.edit(lambda p: p["canvas"].update(width=1280, height=1920))
        with self.assertRaisesRegex(ValueError, "canvas"):
            contract.validate_package(self.package)

    def test_corrupt_asset_rejected(self):
        (self.package / "assets").mkdir()
        (self.package / "assets/bad.png").write_bytes(b"not an image")
        self.edit(lambda p: p["assets"].append(dict(path="assets/bad.png", sha256=None, provenance="test")))
        with self.assertRaises(Exception):
            contract.validate_package(self.package)

    def test_asset_hash_mismatch_rejected(self):
        (self.package / "assets").mkdir()
        (self.package / "assets/test.ttf").write_bytes(b"test bytes")
        self.edit(lambda p: p["assets"].append(dict(path="assets/test.ttf", sha256="0"*64, provenance="test")))
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            contract.validate_package(self.package)

    def test_timeline_gap_rejected(self):
        self.edit(lambda p: p["scenes"][1].update(start_frame=25))
        with self.assertRaisesRegex(ValueError, "contiguously"):
            contract.validate_package(self.package)

    def test_timeline_overlap_rejected(self):
        self.edit(lambda p: p["scenes"][1].update(start_frame=23))
        with self.assertRaises(ValueError):
            contract.validate_package(self.package)

    def test_wrong_total_duration_rejected(self):
        self.edit(lambda p: p.update(total_frames=73))
        with self.assertRaisesRegex(ValueError, "total_frames"):
            contract.validate_package(self.package)

    def test_duplicate_scene_rejected(self):
        self.edit(lambda p: p["scenes"][1].update(id="scene_001"))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            contract.validate_package(self.package)

    def test_wrong_cue_mapping_rejected(self):
        self.edit(lambda p: p["scenes"][1].update(source_cues=[1]))
        with self.assertRaisesRegex(ValueError, "source_cues"):
            contract.validate_package(self.package)

    def test_subtitle_mode_rejected(self):
        self.edit(lambda p: p.update(caption_mode="burn_in"))
        with self.assertRaises(Exception):
            contract.validate_package(self.package)

    def test_unknown_setting_rejected(self):
        self.edit(lambda p: p.update(upload_to_drive=True))
        with self.assertRaises(Exception):
            contract.validate_package(self.package)

    def test_missing_scene_code_rejected(self):
        (self.package / "scripts/cube.py").unlink()
        with self.assertRaisesRegex(ValueError, "Missing scene code"):
            contract.validate_package(self.package)

    def test_source_changed_rejected(self):
        original = self.root / "original.srt"
        original.write_text((self.package / "source.srt").read_text().replace("Start small.", "Original script"))
        with self.assertRaisesRegex(ValueError, "changes"):
            contract.validate_package(self.package, original)

    def test_undeclared_file_rejected(self):
        (self.package / "extra.py").write_text("print('extra')")
        with self.assertRaisesRegex(ValueError, "Undeclared"):
            contract.validate_package(self.package)

    def test_python_process_import_rejected(self):
        path = self.package / "scenes.py"
        path.write_text("import subprocess\n" + path.read_text())
        with self.assertRaisesRegex(ValueError, "unsupported import"):
            contract.validate_package(self.package)

    def test_blender_save_operation_rejected(self):
        path = self.package / "scripts/cube.py"
        path.write_text(path.read_text() + '\n    bpy.ops.wm.save_as_mainfile(filepath="outside.blend")\n')
        with self.assertRaisesRegex(ValueError, "Unsupported Blender"):
            contract.validate_package(self.package)

    def test_wrong_python_signature_rejected(self):
        path = self.package / "scenes.py"
        path.write_text(path.read_text().replace("def intro(t, ctx)", "def intro(t, ctx, extra)"))
        with self.assertRaisesRegex(ValueError, "signature"):
            contract.validate_package(self.package)

    def test_reserved_windows_filename_rejected(self):
        self.edit(lambda p: p["scenes"][0].update(id="CON"))
        with self.assertRaisesRegex(ValueError, "Windows filename"):
            contract.validate_package(self.package)

    def test_blocking_qa_rejected(self):
        qa = contract.read_json(self.package / "qa_report.json")
        qa["blocking_issues"] = ["Missing visual"]
        contract.write_json(self.package / "qa_report.json", qa)
        with self.assertRaisesRegex(ValueError, "blocking"):
            contract.validate_package(self.package)

    def test_false_video_capability_rejected(self):
        qa = contract.read_json(self.package / "qa_report.json")
        qa["status"] = "video_checked"
        contract.write_json(self.package / "qa_report.json", qa)
        with self.assertRaisesRegex(ValueError, "video_inspection"):
            contract.validate_package(self.package)

    def test_zip_traversal_rejected_before_write(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("safe.txt", "safe")
            bundle.writestr("../outside.txt", "unsafe")
        target = self.root / "extract"
        target.mkdir()
        with self.assertRaises(ValueError):
            contract.extract_zip(archive, target)
        self.assertEqual(list(target.iterdir()), [])

    def test_zip_case_collision_rejected(self):
        archive = self.root / "bad.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("project.json", "{}")
            bundle.writestr("PROJECT.json", "{}")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            contract.extract_zip(archive, self.root / "extract")

    def test_duplicate_json_keys_rejected(self):
        path = self.root / "duplicate.json"
        path.write_text('{"x": 1, "x": 2}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
            contract.read_json(path)

    def test_ambiguous_inputs_rejected(self):
        workspace = self.workspace()
        for name in ("one.zip", "two.zip"):
            (workspace / "INPUT" / name).write_bytes(b"zip")
        with self.assertRaisesRegex(ValueError, "exactly ONE"):
            motion.select_inputs(workspace / "INPUT")

    def test_any_audio_filename_accepted(self):
        workspace = self.workspace()
        (workspace / "INPUT/package.zip").write_bytes(b"zip")
        (workspace / "INPUT/my_recording.wav").write_bytes(b"wav")
        returned, source, audio = motion.select_inputs(workspace / "INPUT")
        self.assertEqual(audio.name, "my_recording.wav")

    def test_two_audio_files_rejected(self):
        workspace = self.workspace()
        (workspace / "INPUT/package.zip").write_bytes(b"zip")
        for name in ("voice.mp3", "voice.wav"):
            (workspace / "INPUT" / name).write_bytes(b"audio")
        with self.assertRaisesRegex(ValueError, "only ONE"):
            motion.select_inputs(workspace / "INPUT")

    def test_timed_script_txt_is_used_as_original_source(self):
        workspace = self.workspace()
        (workspace / "INPUT/package.zip").write_bytes(b"zip")
        shutil.copy2(self.package / "source.srt",workspace / "INPUT/SCRIPT.txt")
        _,source,_ = motion.select_inputs(workspace / "INPUT")
        self.assertEqual(source.name,"SCRIPT.txt")

    def test_conflicting_independent_sources_rejected(self):
        workspace = self.workspace()
        (workspace / "INPUT/package.zip").write_bytes(b"zip")
        text = (self.package / "source.srt").read_text()
        (workspace / "INPUT/source.srt").write_text(text)
        (workspace / "INPUT/SCRIPT.txt").write_text(text.replace("Start small.","Changed source"))
        with self.assertRaisesRegex(ValueError,"R03"):
            motion.select_inputs(workspace / "INPUT")

    def test_reset_dry_run_preserves_data(self):
        workspace = self.workspace()
        path = workspace / "INPUT/user.txt"
        path.write_text("user")
        self.assertEqual(motion.main(["reset", "--workspace", str(workspace), "--dry-run"]), 0)
        self.assertTrue(path.exists())

    def test_reset_cancel_preserves_data(self):
        workspace = self.workspace()
        path = workspace / "INPUT/user.txt"
        path.write_text("user")
        self.assertEqual(motion.main(["reset", "--workspace", str(workspace), "--confirmation", "CANCEL"]), 0)
        self.assertTrue(path.exists())

    def test_reset_clears_data_preserves_framework_and_engines(self):
        workspace = self.workspace()
        (workspace / "INPUT/voice.mp3").write_bytes(b"voice")
        (workspace / "OUTPUT/final.mp4").write_bytes(b"movie")
        (workspace / "_SYSTEM/work/job").mkdir()
        (workspace / "_SYSTEM/work/job/cache.bin").write_bytes(b"cache")
        self.assertEqual(motion.main(["reset", "--workspace", str(workspace), "--confirmation", "RESET"]), 0)
        self.assertFalse((workspace / "INPUT/voice.mp3").exists())
        self.assertFalse((workspace / "OUTPUT/final.mp4").exists())
        self.assertTrue((workspace / "_SYSTEM/engines/protected.txt").exists())
        self.assertTrue((workspace / "INPUT/README.txt").exists())

    def test_reset_missing_marker_refuses(self):
        workspace = self.workspace()
        (workspace / "_SYSTEM/installation.json").unlink()
        (workspace / "INPUT/user.txt").write_text("keep")
        self.assertEqual(motion.main(["reset", "--workspace", str(workspace), "--confirmation", "RESET"]), 1)
        self.assertTrue((workspace / "INPUT/user.txt").exists())

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_nested_junction_reset_refuses_before_deletion(self):
        workspace = self.workspace()
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep")
        link = workspace / "INPUT/link"
        result = subprocess.run(["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors="replace"))
        try:
            self.assertEqual(motion.main(["reset", "--workspace", str(workspace), "--confirmation", "RESET"]), 1)
            self.assertTrue((outside / "keep.txt").exists())
        finally:
            link.rmdir()

    def test_workspace_lock_prevents_second_operation(self):
        workspace = self.workspace()
        with motion.workspace_lock(workspace):
            self.assertEqual(motion.main(["reset", "--workspace", str(workspace), "--dry-run"]), 1)

    def test_stalled_worker_is_stopped(self):
        log = self.root / "worker.log"
        with self.assertRaises(TimeoutError):
            motion.run_worker([sys.executable, "-c", "import time; time.sleep(30)"], self.root / "progress.json",
                              log, "test", timeout=1, stall=.3)


if __name__ == "__main__":
    unittest.main()
