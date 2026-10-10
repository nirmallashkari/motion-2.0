"""Self-contained offline authoring from timed narration and registered assets."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys

import contract
from asset_store import AssetStore
from library_pipeline import CATALOG, tail_frames
from story_planner import EXTRA_SUBJECTS, plan_story

REVISION = "self-reusable-4.0"
# These composition defaults were checked on actual rendered object interactions.
CLOSE = {"snooze", "resistance", "convenience", "big_goal", "first_push", "negotiation",
         "choice_battery", "gym", "phone_away", "reward", "treadmill", "calendar", "identity"}

# Words are literal subject cues, not executable instructions. The host retains
# timing, files, animation code, captions, and publication authority.
SUBJECTS = [
    ("train", r"train|ट्रेन|रेलगाड़ी|रेलवे", "travel"),
    ("plane", r"airplane|flight|विमान|हवाई|उड़ान", "travel"),
    ("car", r"\bcar\b|कार|गाड़ी|vehicle", "travel"),
    ("bus", r"\bbus\b|बस में|बस से", "travel"),
    ("ship", r"ship|boat|जहाज|नाव", "travel"),
    ("rocket", r"rocket|रॉकेट|launch|लॉन्च", "travel"),
    ("building-store", r"market|बाज़ार|बाजार|मार्केट|दुकान|shopping", "cutaway"),
    ("carrot", r"vegetable|सब्ज|सब्ज़|सबजी|सब्जी", "build"),
    ("umbrella", r"umbrella|छाता|tent|टेंट", "cutaway"),
    ("brain", r"brain|दिमाग|मस्तिष्क", "cutaway"),
    ("book", r"book|पुस्तक|किताब|पढ़ाई|study|read", "cutaway"),
    ("device-mobile", r"phone|mobile|फ़ोन|फोन|मोबाइल", "cutaway"),
    ("device-laptop", r"computer|laptop|कंप्यूटर|लैपटॉप", "cutaway"),
    ("currency-rupee", r"money|पैस|रुपय|income|कमाई|salary", "build"),
    ("chart-line", r"invest|निवेश|बचत|saving|finance|फाइनेंस", "build"),
    ("coin", r"coin|सिक्क|budget|बजट|cost|कीमत", "build"),
    ("clock", r"clock|time|समय|वक्त|घंट|मिनट", "cutaway"),
    ("calendar", r"calendar|कैलेंडर|schedule|शेड्यूल", "cutaway"),
    ("heart", r"heart|दिल|हृदय|health|स्वास्थ्य", "cutaway"),
    ("stethoscope", r"doctor|डॉक्टर|medical|मेडिकल", "cutaway"),
    ("pill", r"medicine|दवा|दवाई|tablet", "cutaway"),
    ("barbell", r"exercise|gym|व्यायाम|एक्सरसाइज|जिम", "cutaway"),
    ("bike", r"bicycle|cycling|साइकिल", "travel"),
    ("walk", r"walking|walk|पैदल|चलना", "travel"),
    ("run", r"running|jog|दौड़", "travel"),
    ("headphones", r"podcast|music|पॉडकास्ट|संगीत|हेडफोन", "cutaway"),
    ("cup", r"tea|coffee|चाय|कॉफी", "cutaway"),
    ("burger", r"food|खाना|भोजन|hamburger", "cutaway"),
    ("droplet", r"water|पानी|जल|rain|बारिश", "cutaway"),
    ("plant", r"plant|पेड़|पौध|garden|बगीच", "build"),
    ("leaf", r"nature|प्रकृति|environment|पर्यावरण", "cutaway"),
    ("world", r"earth|world|पृथ्वी|दुनिया|थाईलैंड|thailand", "orbit"),
    ("moon", r"moon|चाँद|चांद|space|अंतरिक्ष", "orbit"),
    ("sun", r"sun|सूरज|सूर्य|solar|सौर", "orbit"),
    ("bolt", r"electric|बिजली|power|ऊर्जा|energy", "transfer"),
    ("bulb", r"idea|आइडिया|विचार|innovation", "cutaway"),
    ("flask", r"science|विज्ञान|experiment|प्रयोग", "cutaway"),
    ("atom", r"atom|परमाणु|physics|भौतिक", "orbit"),
    ("robot", r"robot|रोबोट|artificial|आर्टिफिशियल", "cutaway"),
    ("shield", r"security|सुरक्षा|secure|सिक्योर", "cutaway"),
    ("lock", r"password|पासवर्ड|privacy|प्राइवेसी", "cutaway"),
    ("building", r"city|शहर|building|इमारत", "build"),
    ("home", r"house|घर|home|room|कमर", "cutaway"),
    ("school", r"school|education|विद्यालय|स्कूल|शिक्षा", "cutaway"),
    ("briefcase", r"work|office|काम|ऑफिस|job|नौकरी", "cutaway"),
    ("target", r"goal|लक्ष्य|गोल|target|टारगेट", "cutaway"),
    ("trophy", r"success|सफलता|जीत|achievement", "cutaway"),
    ("mountain", r"mountain|पर्वत|पहाड़", "cutaway"),
    ("volcano", r"volcano|ज्वालामुखी", "cutaway"),
    ("camera", r"camera|कैमरा|photo|फोटो", "cutaway"),
    ("movie", r"video|वीडियो|film|फिल्म", "cutaway"),
    ("cloud", r"cloud|बादल|weather|मौसम", "cutaway"),
    ("hand-stop", r"stop|रुक|pause|पॉज", "cutaway"),
]
ANIMATED = {"brain": "Brain", "rocket": "Rocket", "clock": "Alarm clock", "barbell": "Flexed biceps"}
DISCOURSE_WORDS = {"registered", "copyright", "text", "heading", "title", "label", "labels",
    "input", "output", "script", "prompt", "source", "format", "type", "section", "select",
    "code", "function", "copy", "command", "data", "system", "user", "message", "send",
    "return", "print", "sample", "example", "sort", "list", "file", "terminal", "check",
    "clear", "new", "old", "all", "any", "with", "without", "before", "after", "link",
    "route", "path", "way", "scene", "illustration", "detail", "begin", "next", "today",
    "tomorrow", "arrow", "direction", "transition", "journey", "steps", "continue", "different",
    "transfer", "pair", "compare", "build", "grow", "move", "moves", "cross", "crosses",
    "fold", "folds", "reveal", "reveals", "inspect", "inspects", "examine", "examines",
    "enter", "exit", "start", "stop", "turn", "returns", "unfold", "unfolds", "pass",
    "passes", "goes", "stay", "stays", "show", "shows", "choose", "around", "along",
    "between", "near", "beside", "orbit", "orbiting"}


def no_network(event, args):
    if event.startswith("socket."):
        raise PermissionError("Self mode is offline: network and model connections are disabled.")


def subject_pattern(pattern):
    # Plain English keywords are words, not substrings: train is not rain.
    parts=pattern.split('|')
    return '|'.join(r'\b'+part+r'(?:s|es)?\b' if re.fullmatch('[a-z]+',part) else part for part in parts)


def subjects(text, store):
    result = []
    covered_words=set()
    for icon, pattern, action in SUBJECTS + EXTRA_SUBJECTS:
        occurrences=list(re.finditer(subject_pattern(pattern),text,re.I))
        if occurrences:
            try:
                store.resolve(icon)
            except ValueError:
                continue
            if icon not in [item[0] for item in result]:
                result.append((icon, action))
            for occurrence in occurrences:
                covered_words.update(re.findall(r'[a-z]+(?:-[a-z]+)*',occurrence.group().casefold()))
    # English icon names extend the curated bilingual dictionary without inventing
    # semantic equivalence for unfamiliar Hindi terms.
    for token in re.findall(r"[a-z]+(?:-[a-z]+)*", text.casefold()):
        if len(token) > 2 and token not in covered_words and token not in DISCOURSE_WORDS and token in store.data["icons"] and token not in [item[0] for item in result]:
            result.append((token, "cutaway"))
    positions = {icon:min((match.start() for candidate,pattern,_ in SUBJECTS+EXTRA_SUBJECTS if candidate==icon for match in re.finditer(subject_pattern(pattern),text,re.I)),default=text.casefold().find(icon)) for icon,_ in result}
    return sorted(result,key=lambda item:positions[item[0]])


def select(cues, store, choices=None, allow_habits=True):
    choices = choices or {}
    selected = []
    missing = []
    previous = None
    for cue in cues:
        override = choices.get(str(cue["id"]))
        if override:
            if not isinstance(override,dict) or not isinstance(override.get("icon"),str):
                raise ValueError(f"Visual choice {cue['id']} must contain an icon name.")
            icon = override["icon"]
            store.resolve(icon)
            action = override.get("action", "cutaway")
            if action not in {"travel", "transfer", "pair", "compare", "build", "orbit", "cutaway"}:
                raise ValueError(f"Invalid visual choice action: {action}")
            selected.append(dict(kind="asset", icon=icon, action=action, origin="user_choice"))
            previous = selected[-1]
            continue
        habit = next((item for item in CATALOG if re.search(item[1], cue["text"], re.I)), None) if allow_habits else None
        if habit:
            selected.append(dict(kind="habit", family=habit[0], item=habit, origin="registered_action"))
            previous = selected[-1]
            continue
        matches = subjects(cue["text"], store)
        if matches:
            icon, action = matches[0]
            second = matches[1][0] if len(matches) > 1 else None
            mentioned = {item[0] for item in matches}
            if {"sun","world"}.issubset(mentioned) and re.search(r"orbit|revolv|चक्कर|परिक्रमा",cue["text"],re.I):
                icon,second,action = "sun","world","orbit"
            elif {"moon","world"}.issubset(mentioned) and re.search(r"orbit|revolv|चक्कर|परिक्रमा",cue["text"],re.I):
                icon,second,action = "world","moon","orbit"
            if second and re.search(r"pair|combine|साथ|जोड़|मिलाकर", cue["text"], re.I):
                action = "pair"
            elif re.search(r"compare|versus|तुलना|बनाम", cue["text"], re.I):
                action = "compare"
            elif re.search(r"दूसरे|transfer|दूर|हटाओ", cue["text"], re.I):
                action = "transfer"
            if re.search(r"नहीं|\bnot\b|\bnever\b", cue["text"], re.I):
                action = "cutaway"
            selected.append(dict(kind="asset", icon=icon, secondary=second, action=action, origin="subject_rule"))
            previous = selected[-1]
        elif previous and re.match(r"^(और|लेकिन|फिर|ये|यह|इस|वह|वो|and\b|but\b|then\b|it\b|this\b)", cue["text"].strip(), re.I):
            selected.append(dict(previous, origin="continuation_rule"))
        else:
            missing.append(dict(cue_id=cue["id"], text=cue["text"], reason="No supported subject or registered action", choice={"icon": "", "action": "cutaway"}))
            selected.append(None)
            previous = None
    return selected, missing


def renderer_source(specs):
    original = Path(__file__).with_name("habit_renderer.py").read_text(encoding="utf-8")
    original = original.replace("def render(t,ctx):", "def render_habit(t,ctx):")
    original = original.replace("p=Painter(framing)", "p=Painter(framing)\n    p.ctx=ctx\n    p.time=t")
    original = original.replace("def brain(p,x,y,s=1,pressure=0):", "def brain(p,x,y,s=1,pressure=0):\n    if p.ctx.scene_id in SCENE_SPECS and 'brain_asset' in SCENE_SPECS[p.ctx.scene_id]:\n        asset_brain(p,x,y,s,pressure)\n        return")
    helpers = Path(__file__).with_name("self_renderer.py").read_text(encoding="utf-8")
    helpers = helpers.replace("SCENE_SPECS = {}", "SCENE_SPECS = " + repr(specs))
    film = Path(__file__).with_name("film_renderer.py").read_text(encoding="utf-8")
    general = Path(__file__).with_name("general_renderer.py").read_text(encoding="utf-8")
    helpers = helpers.replace("return render_habit(t,ctx)", "return render_film(t,ctx)")
    helpers = helpers.replace("return render_asset(t,ctx,spec)", "return render_story(t,ctx,spec)")
    narrative=Path(__file__).with_name('narrative_renderer.py').read_text(encoding='utf-8')
    camera=Path(__file__).with_name('shot_camera.py').read_text(encoding='utf-8')
    acting=Path(__file__).with_name('story_motion.py').read_text(encoding='utf-8')
    helpers=helpers.replace("return render_story(t,ctx,spec)","return render_narrative(t,ctx,spec) if spec['kind']=='narrative' else render_story(t,ctx,spec)")
    return original + "\n\n" + helpers + "\n\n" + film + "\n\n" + general + "\n\n" + narrative + "\n\n" + camera + "\n\n" + acting


def build_package(package, source, cues, selected, store, tail=0, character_choices=None):
    if character_choices is not None:
        from human_policy import enforce, validate
        selected, character_choices, _ = enforce(cues, selected, character_choices)
        validate(cues, selected, character_choices)
    package.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, package / "source.srt")
    scenes, plans, specs, asset_evidence = [], [], {}, {}
    fps = 24
    position = 0
    for number, (cue, chosen) in enumerate(zip(cues, selected)):
        cue_end = round(cue["end"]*fps/1000) + (tail if number == len(cues)-1 else 0)
        parts = 1 if character_choices is not None else max(1, math.ceil((cue_end-position)/(8*fps)))
        begin = position
        for part in range(parts):
            end = round(begin + (cue_end-begin)*(part+1)/parts)
            family = chosen.get("family", "abstract_story" if chosen["kind"]=="abstract" else "asset_motion")
            framing = "close" if family in CLOSE else "wide"
            identity = f"{family}__{cue['id']:03d}_{part+1:02d}__{framing}"
            spec = dict(kind=chosen["kind"], variation=number+part,
                        domain=chosen.get("domain","work"), shot_variant=(chosen.get("shot_variant",number)+part)%3)
            if chosen['kind']=='narrative':
                from narrative_catalog import CONCEPTS
                item=CONCEPTS[chosen['theme']]
                goal=item['goal'];objects=item['objects'];labels=[]
                spec.update(theme=chosen['theme'],renderer='narrative_1.0')
            elif chosen["kind"] == "habit":
                _,_,goal,objects,labels = chosen["item"]
                spec["renderer"] = "illustrated_film_3.0"
                labels = ["05:00", "TOMORROW"] if family == "night_plan" else []
                goal = "Stage the source-related action in an illustrated physical environment with a consistent character, moving camera, and object interaction: " + goal
                if family == "fixed_anchor":
                    goal = "Connect a wall clock set to six with a prepared study desk and seated reader, illustrating a fixed time and place."
                    objects = ["clock", "study desk", "book", "reader"]
                elif family == "bundle":
                    goal = "Show a headphone-wearing runner on a moving treadmill inside a gym, illustrating the pairing of exercise and listening."
                    objects = ["runner", "headphones", "treadmill", "playback bars"]
                elif family in {"fork", "negotiation"}:
                    goal = "Show a character hesitating at a study desk between the clock, phone and book, illustrating repeated negotiation rather than following a routine."
                    objects = ["person", "clock", "phone", "book", "study desk"]
                elif family == "energy":
                    goal = "Show an actor, a couch and an inset brain with a draining battery metaphor, illustrating the narrated energy explanation without asserting a historical fact."
                    objects = ["person", "couch", "brain illustration", "battery metaphor"]
                if family in {"brain_resist", "resistance", "energy", "choice_battery"}:
                    path, evidence = store.copy_asset(package, "Brain", animated=True)
                    spec["brain_asset"] = path.removeprefix("assets/")
                    asset_evidence[path] = evidence
            elif chosen["kind"] == "abstract":
                goal = "Use a moving light orb and a changing pathway as a human-free abstract transition. No literal subject was recognized; the source meaning is not verified."
                objects = ["light orb", "pathway", "light ribbon"]
                labels = []
                spec.update(action="journey",renderer="general_story_4.0")
            else:
                icon = chosen["icon"]
                secondary = chosen.get("secondary")
                action = chosen["action"]
                goal = chosen.get('visual_goal') or f"Use a stylized {icon.replace('-', ' ')} illustration with the registered {action} camera/object preset to visualize the source-mentioned subject."
                objects = [icon.replace("-", " ")]
                labels = []
                color="ink" if chosen.get("domain") not in (None,"science") else ["teal", "gold", "coral"][number%3]
                animated = icon in ANIMATED and not (character_choices is not None and icon=='barbell')
                path, evidence = store.copy_asset(package, ANIMATED[icon] if animated else icon, animated=animated, color=color)
                asset_evidence[path] = evidence
                spec.update(main_asset=path.removeprefix("assets/"), action=action, labels=[],
                            icon=icon,secondary_icon=secondary,renderer="general_story_4.0")
                if secondary:
                    animated = secondary in ANIMATED and not (character_choices is not None and secondary=='barbell')
                    path, evidence = store.copy_asset(package, ANIMATED[secondary] if animated else secondary, animated=animated, color="gold" if chosen.get("domain")=="science" else "ink")
                    spec["secondary_asset"] = path.removeprefix("assets/")
                    asset_evidence[path] = evidence
                    objects.append(secondary.replace("-", " "))
            involved = [c["id"] for c in cues if c["start"] < end/fps*1000-1e-7 and c["end"] > position/fps*1000+1e-7]
            if character_choices is not None:
                choice=character_choices[number]
                for key in ('shot_profile','content_key','line_mode','action_plan'):
                    if key in choice:spec[key]=choice[key]
            scenes.append(dict(id=identity,engine="python",start_frame=position,end_frame=end,source_cues=involved,script="scenes.py",entry="render",description=goal,params={}))
            beats = [dict(start_frame=start,end_frame=min(end,start+72),kind="object_action" if chosen["kind"]=="habit" or chosen.get("action")!="cutaway" else "camera_move",action=goal,on_screen_text=labels) for start in range(position,end,72)]
            plans.append(dict(id=identity,visual_goal=goal,main_objects=list(dict.fromkeys(objects)),beats=beats,claims=[dict(text=goal,basis="illustrative",source_cues=[cue["id"]],evidence="Source-related stylized illustration; no independently verified fact or numerical measurement is added."),dict(text=cue["text"],basis="source_only",source_cues=[cue["id"]],evidence=cue["text"])]))
            specs[identity] = spec
            position = end
    if character_choices is not None:
        from hybrid_pipeline import upgrade_package_scenes
        upgrade_package_scenes(scenes,plans,character_choices)
        for scene in scenes:
            if scene['engine']=='python':
                for key in ('shot_profile','content_key','line_mode','action_plan'):
                    if key in specs[scene['id']]:scene['params'][key]=specs[scene['id']][key]
    habit_count = sum(item["kind"]=="habit" for item in selected)
    title = "Small Starts, Stronger Habits" if habit_count > len(cues)/2 else "Local Motion Video"
    project = dict(format=contract.VERSION,rulebook_version="1.0",title=title,canvas=dict(width=1280,height=720,fps=fps),total_frames=position,caption_mode="off",seed=91,scenes=scenes,assets=[dict(path=path,sha256=contract.sha(package/path),provenance=json.dumps(evidence,ensure_ascii=True)[:2000]) for path,evidence in asset_evidence.items()])
    if tail:
        project["narration_tail_frames"] = tail
    contract.write_json(package/"project.json",project)
    contract.write_json(package/"creative_plan.json",dict(rulebook_version="1.0",scenes=plans,references=[]))
    if any(scene['engine']=='python' for scene in scenes):
        (package/"scenes.py").write_text(renderer_source(specs),encoding="utf-8")
    elif (package/'scenes.py').is_file():
        (package/'scenes.py').unlink()
    if character_choices is not None and any(scene['engine']=='blender' for scene in scenes):
        (package/"scripts").mkdir(exist_ok=True)
        shutil.copy2(Path(__file__).with_name("blender_character.py"),package/"scripts/character.py")
    elif (package/'scripts/character.py').is_file():
        (package/'scripts/character.py').unlink()
    if character_choices is not None:
        for scene,creative in zip(scenes,plans):
            direction=scene['params'].get('action_plan')
            if direction:
                boundaries=[scene['start_frame']]+[round(scene['start_frame']+(scene['end_frame']-scene['start_frame'])*q) for q in (.20,.78)]+[scene['end_frame']]
                creative['beats']=[dict(start_frame=start,end_frame=min(b,start+72),kind='object_action' if phase['stage']=='action' else 'state_change',action=phase['action'],on_screen_text=[]) for a,b,phase in zip(boundaries,boundaries[1:],direction['phases']) if b>a for start in range(a,b,72)]
        contract.write_json(package/'creative_plan.json',dict(rulebook_version='1.0',scenes=plans,references=[]))
    contract.write_json(package/"qa_report.json",dict(status="authored_unverified",capabilities=dict(python=True,blender=any(s["engine"]=="blender" for s in scenes),image_inspection=False,video_inspection=False,audio_inspection=False),checks=["Registered local scene rules and checksum-verified offline assets; host execution checks run separately."],blocking_issues=[],limitations=["Subject matching and registered presets do not establish arbitrary-script semantic or artistic approval.","No transcript-level audio alignment is claimed."]))
    (package/"storyboard.md").write_text("# Self mode storyboard\n\nLocal registered actions and verified GitHub assets. No runtime model, network, generated code, or external return package. The unchanged source supplies timing; labels are design elements, captions are off.\n\n"+"\n\n".join(f"{s['start_frame']/fps:.3f}-{s['end_frame']/fps:.3f}s: {s['description']}" for s in scenes),encoding="utf-8")
    contract.validate_package(package,source)
    return project, asset_evidence


def run_self(workspace, config):
    import motion
    from local_pipeline import local_inputs
    workspace = Path(workspace)
    sys.addaudithook(no_network)
    contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",dict(status="preparing",mode="self",runtime_ai_calls=0,network_disabled=True))
    source,cues,voice = local_inputs(workspace)
    if cues[0]["start"] != 0 or any(a["end"] != b["start"] for a,b in zip(cues,cues[1:])):
        raise ValueError("Self mode requires contiguous SRT timestamps starting at zero.")
    store = AssetStore()
    choices_file = workspace/"INPUT/visual_choices.json"
    saved_choices = workspace/"_SYSTEM/work/visual_choices"/(contract.sha(source)+".json")
    choices = contract.read_json(choices_file) if choices_file.is_file() else (contract.read_json(saved_choices) if saved_choices.is_file() else {})
    if not isinstance(choices,dict):
        raise ValueError("Visual choices must be an object keyed by cue ID.")
    unknown_ids = set(choices) - {str(cue['id']) for cue in cues}
    if unknown_ids:
        raise ValueError(f"Visual choices refer to absent cue IDs: {sorted(unknown_ids)}")
    policy = config.get("unmatched_policy","abstract")
    selected,missing = plan_story(cues,store,select,choices,policy)
    if missing and policy == "ask" and os.environ.get("MOTION_NONINTERACTIVE") != "1":
        from visual_chooser import choose_visuals
        print(f"{len(missing)} passage(s) need a visual choice. Opening the offline object picker.",flush=True)
        answers = choose_visuals(missing,store)
        if answers:
            choices.update(answers)
            contract.write_json(saved_choices,choices)
            selected,missing = plan_story(cues,store,select,choices,policy)
    if missing:
        contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",dict(status="needs_visual_choices",mode="self",runtime_ai_calls=0,unmatched_cues=len(missing)))
        contract.write_json(workspace/"OUTPUT/NEEDS_VISUAL_CHOICES.json",dict(status="needs_visual_choices",unmatched=missing,available_icons_file=str(store.root/"available_icons.txt"),instructions="Choose an installed icon and action for each unmatched cue. Put a JSON object keyed by cue ID into INPUT/visual_choices.json and rerun. No AI or renderer coding is required.",example={str(missing[0]["cue_id"]):{"icon":"book","action":"cutaway"}}))
        raise ValueError(f"{len(missing)} passage(s) need visual choices. See OUTPUT/NEEDS_VISUAL_CHOICES.json; the previous movie is retained.")
    tools = motion.tools_for(dict(scenes=[dict(engine="python")]))
    voice_seconds = float(motion.probe(voice,tools)["format"]["duration"]) if voice else None
    tail = tail_frames(cues[-1]["end"]/1000,voice_seconds)
    renderer_hash = "".join(contract.sha(Path(__file__).with_name(name)) for name in ("habit_renderer.py", "self_renderer.py", "film_renderer.py", "general_renderer.py", "story_planner.py"))
    identity = hashlib.sha256((REVISION+contract.sha(Path(__file__))+renderer_hash+contract.sha(source)+str(voice_seconds)+json.dumps(selected,sort_keys=True)+store.source["sha256"]).encode()).hexdigest()
    evidence = workspace/"_SYSTEM/work/self"/identity
    evidence.mkdir(parents=True,exist_ok=True)
    package = evidence/"package"
    project,assets = build_package(package,source,cues,selected,store,tail)
    abstract_cues=[cue['id'] for cue,item in zip(cues,selected) if item['kind']=='abstract']
    provenance = dict(revision=REVISION,mode="self",runtime_ai_calls=0,network_disabled=True,external_ai=False,selection_origin="deterministic_local_rules",source_sha256=contract.sha(source),voice_sha256=contract.sha(voice) if voice else None,renderer_sha256=contract.sha(package/"scenes.py"),asset_catalog_size=len(store.names()),asset_evidence=assets,scenes=len(project["scenes"]),total_frames=project["total_frames"],caption_mode="off",voice_seconds=voice_seconds,narration_tail_frames=tail,abstract_cues=abstract_cues,unmatched_policy=policy,per_project_scene_authoring=False)
    contract.write_json(evidence/"provenance.json",provenance)
    contract.write_json(evidence/"selection.json",dict(selections=selected))
    status = dict(status="rendering",mode="self",runtime_ai_calls=0,network_disabled=True,source_sha256=contract.sha(source))
    contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",status)
    print(f"SELF MODE: reusable offline rules, {len(store.names())} installed icons, {len(project['scenes'])} scenes, no model calls; abstract cues: {len(abstract_cues)}.",flush=True)
    try:
        result = motion.execute(workspace,selection=(package,source,voice),self_mode=True)
        report = contract.read_json(workspace/"OUTPUT/qa_report.json")
        delivery = workspace/"OUTPUT/deliveries"/report["job_id"][:16]
        shutil.copy2(evidence/"provenance.json",delivery/"system_provenance.json")
        shutil.copy2(evidence/"selection.json",delivery/"scene_selection.json")
        summary = (f"READY: {len(project['scenes'])} scenes; {project['total_frames']/24:.3f}s; subtitles OFF.\n"
                   "Registered local animation engine; no per-project scene code authoring or runtime AI calls.\n"
                   f"Abstract fallback cues: {abstract_cues or 'none'}. Abstract passages have no verified literal interpretation.\n"
                   "Review the video for subject suitability and artistic quality.\n")
        (workspace/"OUTPUT/RUN_SUMMARY.txt").write_text(summary,encoding="utf-8")
        (delivery/"RUN_SUMMARY.txt").write_text(summary,encoding="utf-8")
        licenses = delivery/"licenses"
        licenses.mkdir(exist_ok=True)
        for name in ("microsoft_LICENSE","tabler_LICENSE"):
            shutil.copy2(store.root/name,licenses/name)
        contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",dict(status,status="ready",delivery=str(delivery),visual_review="awaiting_user_review",cue_level_audio_sync_verified=False))
        contract.write_json(workspace/"OUTPUT/LOCAL_AI_STATUS.json",dict(status="not_used",authoring_mode="self",runtime_ai_calls=0))
        pending = workspace/"OUTPUT/NEEDS_VISUAL_CHOICES.json"
        if pending.exists():
            pending.replace(delivery/"previous_visual_choices_request.json")
        return result
    except Exception as exc:
        contract.write_json(workspace/"OUTPUT/SYSTEM_STATUS.json",dict(status,status="failed",error=str(exc)))
        raise
