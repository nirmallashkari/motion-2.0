"""Regression for camera overflow between the former six-frame samples."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class CameraData:
    type = "ORTHO"

    def __init__(self):
        self.ortho_scale = 10.0
        self.keys = {}

    def keyframe_insert(self, data_path):
        self.keys[self.scene.frame] = self.ortho_scale


class CameraPreflightTests(unittest.TestCase):
    def run_preflight(self, extent):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "blender_worker.py").read_text())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare_character_qa")
        data = CameraData()
        scene = SimpleNamespace(camera=SimpleNamespace(data=data), frame=1)
        data.scene = scene
        evaluated = []

        def frame_set(frame):
            scene.frame = frame
            data.ortho_scale = data.keys.get(frame, 10.0)

        scene.frame_set = frame_set

        def geometry(current):
            evaluated.append(current.frame)
            return {"extent": extent if current.frame == 131 else .8,
                    "visible_fraction": .976 if current.frame == 131 else 1.0}

        namespace = {"bpy": SimpleNamespace(data=SimpleNamespace(objects={"Character_Rig": object()})),
                     "character_geometry": geometry}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "camera_preflight", "exec"), namespace)
        report = namespace["prepare_character_qa"](scene, 152)
        return report, evaluated, data.keys

    def test_between_sample_overflow_repairs_all_camera_frames(self):
        report, evaluated, keys = self.run_preflight(1.067134)
        self.assertEqual(evaluated, list(range(1, 153)))
        self.assertEqual(report["preflight_frames"], 152)
        self.assertEqual(report["repair"]["attempts"], 1)
        self.assertEqual(len(keys), 152)
        self.assertTrue(all(abs(scale - 10 * 1.067134 / .96) < 1e-6 for scale in keys.values()))

    def test_overflow_above_repair_allowance_still_fails(self):
        with self.assertRaisesRegex(ValueError, "bounded repair allowance"):
            self.run_preflight(1.3)


if __name__ == "__main__":
    unittest.main()
