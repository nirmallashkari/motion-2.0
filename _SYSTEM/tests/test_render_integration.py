"""Real FFmpeg/Pillow flow checks in disposable, isolated workspaces."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import contract
import motion


class RenderIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=contract.SYSTEM / "reports", prefix="render_test_")
        self.root = Path(self.temporary.name)
        for folder in ("INPUT", "OUTPUT", "_SYSTEM/work", "_SYSTEM/reports"):
            (self.root / folder).mkdir(parents=True)
        contract.write_json(self.root / "_SYSTEM/installation.json", {"format": contract.VERSION})
        self.package = self.root / "authoring"
        shutil.copytree(contract.SYSTEM / "framework/example_return", self.package)
        project = contract.read_json(self.package / "project.json")
        project["scenes"][1].update(engine="python", script="scenes.py", entry="intro")
        contract.write_json(self.package / "project.json", project)
        plan = contract.read_json(self.package / "creative_plan.json")
        plan["scenes"][1]["main_objects"] = ["moving circle"]
        plan["scenes"][1]["beats"][0]["on_screen_text"] = ["SMALL STARTS"]
        contract.write_json(self.package / "creative_plan.json", plan)
        (self.package / "scripts/cube.py").unlink()
        shutil.copy2(self.package / "source.srt", self.root / "INPUT/source.srt")
        with zipfile.ZipFile(self.root / "INPUT/return.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in contract.package_files(self.package):
                bundle.write(path, path.relative_to(self.package).as_posix())

    def tearDown(self):
        self.temporary.cleanup()

    def audio(self, duration):
        with wave.open(str(self.root / "INPUT/voice.wav"), "wb") as stream:
            stream.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
            stream.writeframes(b"\0\0" * int(duration*48000))

    def run_host(self):
        return subprocess.run([sys.executable, str(contract.SYSTEM / "motion.py"), "run",
                               "--workspace", str(self.root)], capture_output=True, text=True, timeout=120)

    def test_silent_preview_and_verified_cache_resume(self):
        (self.root / "OUTPUT/final.mp4").write_bytes(b"old narrated movie")
        first = self.run_host()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertFalse((self.root / "OUTPUT/final.mp4").exists())
        self.assertTrue((self.root / "OUTPUT/silent_preview.mp4").is_file())
        self.assertTrue(list((self.root / "OUTPUT/history").glob("previous_final_*.mp4")))
        report = contract.read_json(self.root / "OUTPUT/qa_report.json")
        self.assertEqual(report["technical"]["frames"], 72)
        self.assertFalse(report["audio"]["present"])
        second = self.run_host()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(second.stdout.count("Reusing verified scene"), 3)

    def test_fractional_scene_durations_keep_exact_assembled_fps(self):
        tools = motion.tools_for({"scenes": []})
        counts = (58, 68, 66)
        scenes = []
        start = 0
        for index, count in enumerate(counts):
            scene = dict(id=f"clip_{index}", start_frame=start, end_frame=start + count)
            scenes.append(scene)
            start += count
            motion.encode([tools["ffmpeg"], "-v", "error", "-y", "-f", "lavfi", "-i",
                           "color=c=blue:s=128x72:r=24", "-frames:v", str(count),
                           "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           str(self.root / f"clip_{index}.mp4")], self.root / "encode.log")
        manifest = self.root / "concat.txt"
        motion.write_concat_manifest(manifest, scenes, 24)
        movie = self.root / "assembled.mp4"
        motion.encode([tools["ffmpeg"], "-v", "error", "-y", "-f", "concat", "-safe", "1",
                       "-i", str(manifest), "-an", "-c:v", "copy", str(movie)], self.root / "encode.log")
        result = motion.verify_movie(movie, dict(width=128, height=72, fps=24),
                                     sum(counts), tools, False, self.root / "verify.log")
        self.assertEqual(result["duration_seconds"], 8)

    def test_voice_duration_mismatch_stops_before_render(self):
        self.audio(2)
        result = self.run_host()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Supply aligned audio", result.stderr)
        self.assertFalse((self.root / "OUTPUT/final.mp4").exists())
        self.assertTrue((self.root / "OUTPUT/ERROR.json").exists())
        self.assertFalse(list((self.root / "_SYSTEM/work").glob("*/clips/*.mp4")))

    def test_narration_mux_and_snapshot_tampering_rejected(self):
        self.audio(3)
        first = self.run_host()
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        qa = contract.read_json(self.root / "OUTPUT/qa_report.json")
        self.assertEqual(qa["technical"]["audio_codec"], "aac")
        self.assertEqual(qa["technical"]["duration_seconds"], 3)
        self.assertFalse(qa["cue_level_voice_sync_verified"])
        snapshot = self.root / "_SYSTEM/work" / qa["job_id"] / "source/scenes.py"
        snapshot.write_text(snapshot.read_text() + "\n# Changed after validation\n")
        second = self.run_host()
        self.assertEqual(second.returncode, 1)
        self.assertIn("snapshot changed", second.stderr)

    def test_undeclared_text_stops_worker_and_preserves_previous_movie(self):
        path = self.package / "scenes.py"
        path.write_text(path.read_text().replace("SMALL STARTS", "UNDECLARED LABEL"))
        with zipfile.ZipFile(self.root / "INPUT/return.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
            for entry in contract.package_files(self.package):
                bundle.write(entry, entry.relative_to(self.package).as_posix())
        old = self.root / "OUTPUT/final.mp4"
        old.write_bytes(b"previous valid delivery")
        result = self.run_host()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Rendered text is absent", result.stderr)
        self.assertEqual(old.read_bytes(), b"previous valid delivery")

    def test_claimed_action_with_static_code_fails_quality_gate(self):
        project = contract.read_json(self.package / "project.json")
        project["scenes"] = [project["scenes"][0]]
        project["scenes"][0].update(start_frame=0,end_frame=96,source_cues=[1])
        project["total_frames"] = 96
        contract.write_json(self.package / "project.json", project)
        (self.package / "source.srt").write_text("1\n00:00:00,000 --> 00:00:04,000\nStart small.\n")
        shutil.copy2(self.package / "source.srt", self.root / "INPUT/source.srt")
        (self.package / "scenes.py").write_text("def intro(t, ctx):\n    return ctx.canvas()\n")
        plan = contract.read_json(self.package / "creative_plan.json")
        plan["scenes"] = [plan["scenes"][0]]
        plan["scenes"][0]["beats"] = [dict(start_frame=a,end_frame=b,kind="object_action",
            action="A circle is claimed to move across the screen.",on_screen_text=[]) for a,b in [(0,48),(48,96)]]
        contract.write_json(self.package / "creative_plan.json",plan)
        with zipfile.ZipFile(self.root / "INPUT/return.zip", "w", zipfile.ZIP_DEFLATED) as bundle:
            for entry in contract.package_files(self.package):
                bundle.write(entry, entry.relative_to(self.package).as_posix())
        result = self.run_host()
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn("near-static hold",result.stderr)
        self.assertFalse((self.root / "OUTPUT/final.mp4").exists())
        self.assertTrue((self.root / "OUTPUT/REPAIR_REQUEST.json").exists())


if __name__ == "__main__":
    unittest.main()
