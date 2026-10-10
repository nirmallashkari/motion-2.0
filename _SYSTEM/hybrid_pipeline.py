"""Reusable Blender/Python production with bounded local-model choices."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import contract
from asset_store import AssetStore
from character_catalog import ACTIONS, REVISION as CHARACTER_REVISION
from story_director import direct, merge_continuous, evaluate
from voice_alignment import align, apply_timing
from human_policy import enforce, validate, REVISION as HUMAN_REVISION
from editorial_gate import enforce as enforce_editorial
from hybrid_planner import offline_loopback, plan
from narrative_catalog import choose as choose_narrative, CONCEPTS
from library_pipeline import tail_frames
from story_planner import plan_story
from self_pipeline import select, build_package

REVISION = "local-hybrid-6.0"


def upgrade_package_scenes(scenes,plans,choices):
    choices={item["cue_id"]:item for item in choices}
    for scene,creative in zip(scenes,plans):
        # The cue that owns the scene is encoded in the host-generated identity;
        # source_cues may also include a neighbor due to frame quantization.
        cue_id=int(scene["id"].split("__")[1].split("_")[0])
        choice=choices[cue_id]
        action=choice["action"]
        if action=="python":
            scene['params']['semantic_cues']=[cue_id]
            if choice.get('theme') in CONCEPTS:scene['params']['theme']=choice['theme']
            continue
        if action not in ACTIONS:raise ValueError("Unregistered 3D action")
        item=ACTIONS[action]
        scene.update(engine="blender",script="scripts/character.py",entry="build",
            params=dict(action=action,environment=item["environment"],camera=choice["camera"],
                        library_revision=CHARACTER_REVISION,
                        emotion=choice.get("emotion","neutral"),camera_move=choice.get("camera_move","push"),
                        story_role=choice.get("story_role","development"),semantic_cues=[cue_id]))
        if choice.get('theme') in CONCEPTS:
            scene['params']['theme']=choice['theme']
        for key in ('shot_profile','content_key','line_mode','action_plan','character_profile'):
            if key in choice:scene['params'][key]=choice[key]
        goal=f"An articulated stylized person performs the registered {action} action in a {item['environment']} setting, with soft lighting and a moving camera."
        if choice.get('theme') in CONCEPTS:
            goal=CONCEPTS[choice['theme']]['goal']
            item=dict(item,objects=CONCEPTS[choice['theme']]['objects'])
        scene["description"]=goal
        creative["visual_goal"]=goal;creative["main_objects"]=item["objects"]
        for beat in creative["beats"]:beat.update(action=goal,on_screen_text=[])
        creative["claims"][0].update(text=goal,evidence="Source-anchored registered visual illustration or metaphor, not a literal factual assertion.")
    merge_continuous(scenes,plans)


def run_hybrid(workspace,config):
    import motion
    from local_pipeline import local_inputs
    workspace=Path(workspace)
    from cloud_planner import configuration as cloud_configuration
    cloud=cloud_configuration(workspace)
    sys.addaudithook(offline_loopback)
    source,cues,voice=local_inputs(workspace)
    if cues[0]["start"]!=0 or any(a["end"]!=b["start"] for a,b in zip(cues,cues[1:])):
        raise ValueError("Hybrid mode requires contiguous SRT timestamps starting at zero.")
    from cast_contract import should_route
    if should_route(workspace,cues):
        if not cloud['enabled'] or cloud.get('provider')!='deepseek':
            raise ValueError('Multi-character direction requires the enabled DeepSeek provider.')
        from cast_pipeline import run as run_cast
        return run_cast(workspace,source,cues,voice,cloud)
    initial=dict(mode="hybrid",runtime_ai_calls=0,external_network_disabled=not cloud['enabled'],planner_provider=cloud.get('provider','local') if cloud['enabled'] else 'local')
    contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",dict(initial,status="planning"))
    from character_design import ensure_character,bind_choices,enforce_project
    character_profile,character_record=ensure_character(workspace,cues)
    config=dict(config,locked_character=dict(identity_id=character_profile['identity_id'],
        brief=character_profile['brief'],appearance=character_profile['appearance']))
    store=AssetStore()
    choices_file=workspace/"INPUT/visual_choices.json"
    choices=contract.read_json(choices_file) if choices_file.is_file() else {}
    selected,missing=plan_story(cues,store,select,choices,config["unmatched_policy"])
    if missing:raise ValueError("Unsupported passages need abstract policy or declared visual choices.")
    print(f"HYBRID: {initial['planner_provider']} planner selects registered scenes; model never authors code or paths.",flush=True)
    if cloud['enabled']:
        from cloud_planner import plan as cloud_plan
        narrative,ai=cloud_plan(workspace,cues,selected,config,cloud,store)
    else:
        narrative,ai=choose_narrative(cues,selected,config,workspace)
    selected=[item[0] for item in narrative];character_choices=[item[1] for item in narrative]
    selected,character_choices,human_routing=enforce(cues,selected,character_choices)
    validate(cues,selected,character_choices)
    character_choices=direct(cues,character_choices)
    from action_direction import compile_direction,enforce as enforce_direction
    character_choices,action_direction=compile_direction(cues,selected,character_choices)
    from shot_policy import assign,enforce as enforce_shots
    character_choices=assign(cues,selected,character_choices)
    character_choices=bind_choices(character_choices,character_profile)
    python_tools=motion.tools_for(dict(scenes=[dict(engine="python")]))
    voice_seconds=float(motion.probe(voice,python_tools)["format"]["duration"]) if voice else None
    alignment=align(workspace,voice,cues)
    tail=tail_frames(cues[-1]["end"]/1000,voice_seconds)
    render_files=("blender_character.py","character_catalog.py","self_pipeline.py","habit_renderer.py",
                  "self_renderer.py","film_renderer.py","general_renderer.py","story_planner.py","story_director.py","human_policy.py","editorial_gate.py","narrative_catalog.py","narrative_renderer.py","visual_registry.py","shot_policy.py","shot_camera.py","cloud_planner.py","cloud_contract.py","action_direction.py","story_motion.py","preview_gate.py","character_design.py")
    identity=hashlib.sha256((REVISION+contract.sha(source)+str(voice_seconds)+
        json.dumps(character_choices,sort_keys=True)+json.dumps(selected,sort_keys=True)+
        "".join(contract.sha(Path(__file__).with_name(name)) for name in render_files)).encode()).hexdigest()
    evidence=workspace/"_SYSTEM/work/hybrid"/identity;evidence.mkdir(parents=True,exist_ok=True)
    project,assets=build_package(evidence/"package",source,cues,selected,store,tail,character_choices)
    apply_timing(project['scenes'],alignment,cues)
    enforce_project(project,character_profile)
    contract.write_json(evidence/'package/project.json',project)
    editorial_gate=enforce_editorial(workspace,project,evidence)
    line_policy=enforce_shots(project,cues)
    enforce_direction(project,cues)
    for root in (evidence,workspace/'OUTPUT'):contract.write_json(root/'ACTION_DIRECTION.json',action_direction)
    for root in (evidence,workspace/'OUTPUT'):contract.write_json(root/'LINE_VISUAL_POLICY.json',line_policy)
    blender_count=sum(s["engine"]=="blender" for s in project["scenes"])
    motion.tools_for(project)  # Check Blender availability before any clip work.
    editorial=evaluate(cues,project['scenes'])
    abstract=editorial['abstract_cues']
    provenance=dict(revision=REVISION,mode="hybrid",runtime_ai_calls=ai["runtime_ai_calls"],
        successful_ai_calls=ai["successful_ai_calls"],external_network_disabled=not cloud['enabled'],
        ollama_endpoint=None if cloud['enabled'] else "127.0.0.1:11434",external_ai=cloud['enabled'],model=ai.get('model',config["model"]),planner_provider=ai.get('provider','local'),
        per_project_scene_authoring=False,source_sha256=contract.sha(source),
        voice_sha256=contract.sha(voice) if voice else None,voice_seconds=voice_seconds,
        blender_scenes=blender_count,python_scenes=len(project["scenes"])-blender_count,
        abstract_cues=abstract,assets=assets,ai_plan=ai,character_library=CHARACTER_REVISION,
        unrecognized_2d_cues=[cue['id'] for cue,item in zip(cues,selected) if item['kind']=='abstract'],
        character_identity_id=character_profile['identity_id'],character_design=character_record,
        human_routing=human_routing,line_visual_policy=line_policy,editorial_gate=editorial_gate,editorial_review=editorial,voice_alignment_status=alignment['status'],
        cue_level_audio_sync_verified=alignment.get('cue_level_timing_verified',False))
    contract.write_json(evidence/"provenance.json",provenance)
    contract.write_json(evidence/"scene_choices.json",dict(choices=character_choices))
    contract.write_json(evidence/"editorial_review.json",editorial)
    contract.write_json(evidence/"voice_alignment.json",alignment)
    (evidence/"package/storyboard.md").write_text(f"# Hybrid storyboard\n\nHost-registered Blender/Python code. Source-bound {ai.get('provider','local')} choices. No generated scene code. Captions off. Voice and rendering remain local.\n\n"+
        "\n\n".join(f"{s['start_frame']/24:.3f}-{s['end_frame']/24:.3f}s [{s['engine']}]: {s['description']}" for s in project["scenes"]),encoding="utf-8")
    status=dict(initial,status="rendering",runtime_ai_calls=ai["runtime_ai_calls"],
                blender_scenes=blender_count,python_scenes=len(project["scenes"])-blender_count)
    contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",status)
    print(f"HYBRID: {blender_count} Blender / {len(project['scenes'])-blender_count} Python scenes; {ai.get('provider','local')} AI calls: {ai['runtime_ai_calls']}; fallback errors: {len(ai['failures'])}.",flush=True)
    from preview_gate import run as run_preview
    preview=run_preview(workspace,evidence/'package',project,cues)
    result=motion.execute(workspace,selection=(evidence/"package",source,voice),self_mode=True)
    qa=contract.read_json(workspace/"OUTPUT/qa_report.json")
    delivery=workspace/"OUTPUT/deliveries"/qa["job_id"][:16]
    contract.write_json(delivery/'CHARACTER_DESIGN.json',character_record)
    shutil.copy2(workspace/'OUTPUT/character_face.png',delivery/'character_face.png')
    shutil.copy2(evidence/"provenance.json",delivery/"system_provenance.json")
    shutil.copy2(evidence/"scene_choices.json",delivery/"scene_choices.json")
    for root in (workspace/'OUTPUT',delivery):
        contract.write_json(root/'ACTION_DIRECTION.json',action_direction)
        contract.write_json(root/'PREVIEW_QA.json',preview)
    (delivery/'licenses').mkdir(exist_ok=True)
    for notice in ('microsoft_LICENSE','tabler_LICENSE'):
        shutil.copy2(contract.SYSTEM/'assets/github'/notice,delivery/'licenses'/notice)
    for root in (workspace/"OUTPUT",delivery):contract.write_json(root/"EDITORIAL_REVIEW.json",editorial)
    for root in (workspace/"OUTPUT",delivery):contract.write_json(root/"VOICE_ALIGNMENT.json",alignment)
    for root in (workspace/"OUTPUT",delivery):contract.write_json(root/"HUMAN_ROUTING.json",human_routing)
    for root in (workspace/"OUTPUT",delivery):contract.write_json(root/"LINE_VISUAL_POLICY.json",line_policy)
    contract.write_json(workspace/"OUTPUT/LOCAL_AI_STATUS.json",ai)
    if cloud['enabled']:
        for root in (workspace/'OUTPUT',delivery):contract.write_json(root/'CLOUD_PLANNER_STATUS.json',ai)
    summary=(f"READY: {len(project['scenes'])} scenes; {project['total_frames']/24:.3f}s; subtitles OFF.\n"
        f"Source lines: {len(cues)}; one visual per source line; decoded repeat check: {qa['storytelling_checks']['no_repeat']['status']}.\n"
        f"Action direction: setup/action/result; camera-only idea reuse is blocked. Preview gate: {preview['status']}.\n"
        f"Character: story-designed identity locked before planning; {character_profile['identity_id'][:16]}.\n"
        f"Expandable visual library: {ai['visual_library']['recipes']} registered recipes; no fixed twenty-concept ceiling.\n"
        f"Blender: {blender_count}; Python: {len(project['scenes'])-blender_count}; {ai.get('provider','local')} model calls this run: {ai['runtime_ai_calls']}.\n"
        f"Planner: {ai['status'] if not ai['cache_used'] else 'validated cached plan'}; fallback errors: {len(ai['failures'])}.\n"
        f"Abstract source cues: {abstract or 'none'}. Unknown meaning is not verified.\n"
        f"Voice alignment: {alignment['status']}; exact synchronization is not guaranteed.\n"
        "Registered animation code only; no per-project scene authoring. Review subject suitability and artistic quality.\n")
    for root in (workspace/"OUTPUT",delivery):(root/"RUN_SUMMARY.txt").write_text(summary,encoding="utf-8")
    contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",dict(status,status="ready",delivery=str(delivery),
        visual_review="awaiting_user_review",cue_level_audio_sync_verified=alignment.get('cue_level_timing_verified',False)))
    return result
