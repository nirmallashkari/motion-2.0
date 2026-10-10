"""A rotating cube with a real camera and studio lighting."""
import math
import bpy
import blender_sdk as sdk

def build(ctx, spec):
    sdk.studio(ctx)
    cube = sdk.box("Habit cube", (0, 0, 1.1), (1.5, 1.5, 1.5), "cyan", .10)
    sdk.camera(ctx, (5, -7, 4), (0, 0, 1), ortho=5)
    sdk.key(cube, "rotation_euler", [(spec["start_ms"], 0), (spec["end_ms"], math.pi)], ctx, index=2, linear=True)
    bpy.context.scene.view_settings.view_transform = "Standard"
