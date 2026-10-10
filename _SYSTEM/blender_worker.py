"""Trusted Blender builder/render worker; source code only builds the scene."""
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import sys
import time

sys.dont_write_bytecode = True

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def no_network(event, args):
    if event.startswith("socket."):
        raise PermissionError("Blender frame workers cannot use network or model connections.")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    for attempt in range(20):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.02)


def character_geometry(scene):
    """Inspect actual evaluated rig geometry; ignore environment/background."""
    rig=bpy.data.objects.get('Character_Rig')
    if not rig:return None
    rigs=[obj for obj in scene.objects if obj.type=='ARMATURE' and obj.name.startswith('Character_Rig')]
    points=[];all_points=[];length_errors=[]
    focus=scene.camera.data.get('shot_focus','full_body')
    for actor in rigs:
        for bone in actor.pose.bones:
            if bone.name.endswith(('_thigh','_shin','_upperarm','_forearm')) and abs(bone.length-actor.data.bones[bone.name].length)>.008:
                length_errors.append(actor.name+':'+bone.name)
    graph=bpy.context.evaluated_depsgraph_get()
    for obj in scene.objects:
        if obj.type=='MESH' and obj.parent in rigs and not obj.hide_render:
            evaluated=obj.evaluated_get(graph)
            corners=[evaluated.matrix_world@Vector(corner) for corner in evaluated.bound_box]
            all_points.extend(corners)
            names={group.name for group in obj.vertex_groups}
            upper_groups={'head','torso','L_upperarm','R_upperarm','L_forearm','R_forearm','L_hand','R_hand'}
            if focus=='full_body' or 'head' in names or (focus=='upper_body' and names.intersection(upper_groups)):
                points.extend(corners)
    projected=[world_to_camera_view(scene,scene.camera,point) for point in points]
    visible=sum(-.02<=point.x<=1.02 and -.02<=point.y<=1.02 and point.z>0 for point in projected)/max(1,len(projected))
    extent=max([max(abs(point.x-.5)*2,abs(point.y-.5)*2) for point in projected] or [1])
    return dict(visible_fraction=visible,extent=extent,minimum_z=min([point.z for point in all_points] or [0]),limb_length_errors=length_errors,shot_focus=focus,actors_checked=len(rigs))


def prepare_character_qa(scene,count):
    """Inspect every animation frame before one bounded camera repair."""
    if not bpy.data.objects.get('Character_Rig'):return dict(status='not_applicable')
    if scene.camera.data.type!='ORTHO':return dict(status='not_applicable',reason='Registered orthographic repair requires an orthographic camera.')
    snapshots=[]
    # A between-sample limb pose can overflow even when neighboring frames fit.
    # Evaluate geometry at every frame without rendering pixels first.
    for frame in range(1,count+1):
        scene.frame_set(frame);record=character_geometry(scene);snapshots.append(record)
    factor=max(record['extent'] for record in snapshots)/.96
    repair=None
    if factor>1 and any(record['visible_fraction']<.98 for record in snapshots):
        if factor>1.20:raise ValueError('Character camera overflow exceeds bounded repair allowance')
        # Save original animation values before inserting any replacement keys.
        scales=[]
        for frame in range(1,count+1):scene.frame_set(frame);scales.append(scene.camera.data.ortho_scale)
        for frame,scale in enumerate(scales,1):
            scene.frame_set(frame);scene.camera.data.ortho_scale=scale*factor;scene.camera.data.keyframe_insert(data_path='ortho_scale')
        repair=dict(kind='widen_registered_camera',factor=round(factor,4),attempts=1)
    scene.frame_set(1)
    return dict(status='checking',repair=repair,preflight_frames=count,
                checked_frames=0,minimum_visible_fraction=1,lowest_character_z=100,failures=[])


def main():
    if bpy.app.version_string != "5.1.1":
        raise ValueError("The unified SDK requires Blender 5.1.1")
    task = json.loads(Path(sys.argv[sys.argv.index("--")+1]).read_text(encoding="utf-8"))
    sys.addaudithook(no_network)
    project, spec = task["project"], dict(task["scene"])
    canvas = project["canvas"]
    package, output = Path(task["package"]), Path(task["output"])
    fps, count = canvas["fps"], spec["end_frame"] - spec["start_frame"]
    spec["start_ms"] = spec["start_frame"] / fps * 1000
    spec["end_ms"] = spec["end_frame"] / fps * 1000
    sys.path.insert(0, task["sdk_root"])
    import blender_sdk as sdk
    from quality_policy import check_blender_text
    bpy.ops.wm.read_factory_settings(use_empty=True)
    random.seed(project["seed"])
    declared = {a["path"] for a in project["assets"]}

    def asset(relative):
        name = "assets/" + relative
        path = (package / name).resolve()
        if name not in declared or not path.is_relative_to((package / "assets").resolve()) or not path.is_file():
            raise ValueError("Blender asset must be a declared file inside package assets/")
        return str(path)

    ctx = dict(fps=fps, width=canvas["width"], height=canvas["height"], seed=project["seed"],
               shot=spec, orientation="landscape" if canvas["width"] > canvas["height"] else "portrait",
               sdk=sdk, asset=asset)
    module_spec = importlib.util.spec_from_file_location("external_blender_scene", package / spec["script"])
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    module.build(ctx, spec)
    scene = bpy.context.scene
    if not scene.camera:
        raise ValueError("Blender scene did not create a camera")
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 32
    scene.render.resolution_x = canvas["width"]
    scene.render.resolution_y = canvas["height"]
    scene.render.resolution_percentage = 100
    if task.get('preview') is True:
        scene.render.resolution_percentage=50 if spec.get('params',{}).get('cast') else 25
        scene.eevee.taa_render_samples=16
    scene.render.fps = fps
    scene.render.fps_base = 1
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.frame_start, scene.frame_end = 1, count
    scene.frame_set(1)
    geometry=prepare_character_qa(scene,count)
    previous_head=None
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "scene.blend"))
    hashes_path = output / "frame_hashes.json"
    hashes = json.loads(hashes_path.read_text()) if hashes_path.exists() else {}
    indices=[round((count-1)*q) for q in (.08,.50,.94)] if task.get('preview') is True else list(range(count))
    write(output / "progress.json", dict(completed=0, total=len(indices)))
    for number,index in enumerate(indices,1):
        scene.frame_set(index+1)
        if geometry['status']!='not_applicable':
            record=character_geometry(scene)
            head=bpy.data.objects['Character_Rig'].pose.bones['head'].matrix.to_quaternion()
            if task.get('preview') is not True and previous_head and previous_head.rotation_difference(head).angle>.25:record['limb_length_errors'].append('head_rotation_discontinuity')
            previous_head=head.copy()
            geometry['checked_frames']+=1
            geometry['minimum_visible_fraction']=min(geometry['minimum_visible_fraction'],record['visible_fraction'])
            geometry['lowest_character_z']=min(geometry['lowest_character_z'],record['minimum_z'])
            if record['visible_fraction']<.98 or record['minimum_z']<-.05 or record['limb_length_errors']:
                geometry['failures'].append(dict(frame=index,**record))
                geometry['status']='failed';write(output/'geometry_qa.json',geometry)
                raise ValueError(f'Character geometry check failed at frame {index}: {record}')
        check_blender_text(task["creative_scene"], task["source_text"], scene.objects, spec["start_frame"]+index)
        frame = output / (f'preview_{number:02}.png' if task.get('preview') is True else f"frame_{index:06d}.png")
        known = hashes.get(str(index))
        if not frame.is_file() or not known or sha(frame) != known:
            scene.frame_set(index+1)
            scene.render.filepath = str(frame)
            bpy.ops.render.render(write_still=True)
            hashes[str(index)] = sha(frame)
            write(hashes_path, hashes)
        write(output / "progress.json", dict(completed=number, total=len(indices)))
    if geometry['status']!='not_applicable':geometry['status']='passed'
    write(output/'geometry_qa.json',geometry)
    write(output / "build_report.json", dict(blender=bpy.app.version_string, engine=scene.render.engine,
          frames=len(indices), preview=task.get('preview') is True, objects=len(scene.objects), view_transform=scene.view_settings.view_transform,
          character_geometry=geometry,
          character_identity_id=bpy.data.objects['Character_Rig'].get('character_identity_id') if bpy.data.objects.get('Character_Rig') else None,
          actor_identity_ids=[obj.get('character_identity_id') for obj in scene.objects if obj.type=='ARMATURE' and obj.name.startswith('Character_Rig')],
          cast_ids=scene.get('cast_ids',''),silver_owner=scene.get('silver_owner',''),
          interaction_contact_max=scene.get('interaction_contact_max',None)))


if __name__ == "__main__":
    main()
