"""Deterministic story-first character design, rendered before scene planning."""
import copy
import hashlib
import json
import math
from pathlib import Path
import random
import re
import shutil
import sys
import unicodedata

import contract

REVISION = 'story-character-1.0'
SHAPE_LIMITS = {
    'width': (.305, .355), 'height': (.365, .425), 'depth': (.275, .310),
    'eye_spacing': (.104, .130), 'eye_size': (.062, .078),
    'nose_width': (.047, .075), 'nose_length': (.068, .096),
    'brow_radius': (.013, .022), 'mouth_width': (.067, .093),
}
HAIR = ('side_part', 'textured_crop', 'soft_curls', 'swept_wave', 'long_bob')
ROLES = (
    ('student', r'\bstudent\b|\bschool\b|\bcollege\b|छात्र|विद्यार्थी'),
    ('athlete', r'\bathlete\b|\btraining\b|\bsport\b|खिलाड़ी'),
    ('explorer', r'\bexplorer\b|\bjourney\b|\btravel\b|यात्री'),
    ('creator', r'\bwriter\b|\bartist\b|\bcreate\b|\bwork\b|\bkaam\b|लेखक'),
)


def canonical_story(cues):
    text = ' '.join(c['text'] for c in cues)
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def story_brief(cues):
    text = canonical_story(cues)
    role = next((name for name, pattern in ROLES if re.search(pattern, text)), 'narrator')
    reflective = bool(re.search(r'\bfear\b|\bdarr\b|\bkhud\b|\bregret\b|\bmirror\b|\baaina\b|डर|आईना', text))
    hints = {}
    for name, pattern in (
        ('glasses', r'\bwear(?:s|ing)? glasses\b|\bwith glasses\b|\bchashma\b|चश्मा'),
        ('silver_hair', r'\bgray hair\b|\bgrey hair\b|\bsilver hair\b|सफेद बाल'),
        ('long_hair', r'\blong hair\b|\blambe baal\b|लंबे बाल'),
        ('curly_hair', r'\bcurly hair\b|घुंघराले'),
        ('short_hair', r'\bshort hair\b|\bchhote baal\b|छोटे बाल'),
    ):
        match = re.search(pattern, text)
        if match:
            hints[name] = match.group()
    return dict(role=role, tone='reflective' if reflective else 'active', explicit_hints=hints)


def harmony(shape, palette):
    """Mechanical design ranking, not a claimed artistic quality rating."""
    ratio = shape['width'] / shape['height']
    spacing = shape['eye_spacing'] / shape['width']
    hair, skin = palette['hair'], palette['skin']
    contrast = math.sqrt(sum((a-b)**2 for a, b in zip(hair[:3], skin[:3])))
    return round(1 - abs(ratio-.84)*1.2 - abs(spacing-.35) + min(contrast, .8)*.1, 6)


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {'revision', 'identity_id', 'source_sha256', 'brief', 'appearance', 'design'}:
        raise ValueError('Character profile fields are invalid.')
    if profile['revision'] != REVISION or not re.fullmatch(r'[0-9a-f]{64}', profile['source_sha256']):
        raise ValueError('Character revision or source hash is invalid.')
    appearance = profile['appearance']
    if set(appearance) != {'shape', 'palette', 'hairstyle', 'glasses'} or appearance['hairstyle'] not in HAIR or type(appearance['glasses']) is not bool:
        raise ValueError('Unregistered character appearance.')
    if set(appearance['shape']) != set(SHAPE_LIMITS):
        raise ValueError('Face shape fields changed.')
    for key, (low, high) in SHAPE_LIMITS.items():
        value = appearance['shape'][key]
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('Face proportions exceed registered limits: '+key)
    if set(appearance['palette']) != {'skin', 'hair', 'shirt', 'pants'}:
        raise ValueError('Character palette fields changed.')
    for color in appearance['palette'].values():
        if not isinstance(color, list) or len(color) != 4 or color[3] != 1 or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in color):
            raise ValueError('Invalid character material color.')
    if profile['identity_id'] != digest(dict(source=profile['source_sha256'], appearance=appearance, revision=REVISION)):
        raise ValueError('Locked character identity does not match its appearance.')
    return profile


def design(cues):
    source_hash = hashlib.sha256(canonical_story(cues).encode()).hexdigest()
    brief = story_brief(cues)
    rng = random.Random(int(source_hash, 16))
    candidates = []
    for index in range(12):
        shape = {key: round(rng.uniform(low, high), 6) for key, (low, high) in SHAPE_LIMITS.items()}
        # Palette variation is independent of role, morality, emotion or ethnicity.
        skin_light = rng.uniform(.38, .74)
        skin = [round(skin_light, 6), round(skin_light*rng.uniform(.53, .73), 6), round(skin_light*rng.uniform(.32, .52), 6), 1]
        hair_light = rng.uniform(.022, .105)
        hair = [round(hair_light, 6), round(hair_light*.77, 6), round(hair_light*.56, 6), 1]
        shirt = [round(rng.uniform(.07, .31), 6), round(rng.uniform(.15, .38), 6), round(rng.uniform(.22, .45), 6), 1]
        hairstyle = rng.choice(HAIR[:-1])
        hints = brief['explicit_hints']
        if 'long_hair' in hints:
            hairstyle = 'long_bob'
        elif 'curly_hair' in hints:
            hairstyle = 'soft_curls'
        elif 'short_hair' in hints:
            hairstyle = 'textured_crop'
        if 'silver_hair' in hints:
            hair = [.37, .40, .43, 1]
        palette = dict(skin=skin, hair=hair, shirt=shirt, pants=[.05, .075, .10, 1])
        score = harmony(shape, palette)
        if brief['tone'] == 'reflective':
            score -= abs(shape['brow_radius']-.016)*2
        if brief['role'] == 'athlete':
            score -= abs(shape['width']-.34)*2
        appearance = dict(shape=shape, palette=palette, hairstyle=hairstyle, glasses='glasses' in hints)
        candidates.append(dict(index=index, score=round(score, 6), appearance=appearance))
    winner = max(candidates, key=lambda c: c['score'])
    appearance = winner['appearance']
    profile = dict(revision=REVISION, source_sha256=source_hash, brief=brief, appearance=appearance,
        identity_id=digest(dict(source=source_hash, appearance=appearance, revision=REVISION)),
        design=dict(candidates=12, selected_candidate=winner['index'], mechanical_score=winner['score'],
                    ranking='Bounded proportions, feature spacing and material contrast; not an artistic score.',
                    limitations=['One stylized lead character; no arbitrary photorealistic face generation.',
                                 'Role/tone and appearance hints use bounded keyword rules.',
                                 'Finite procedural parameters cannot guarantee every pair looks perceptually distinct.']))
    return validate_profile(profile)


def bind_choices(choices, profile):
    validate_profile(profile)
    return [dict(choice, character_profile=copy.deepcopy(profile)) for choice in choices]


def enforce_project(project, profile):
    validate_profile(profile)
    for scene in project['scenes']:
        if scene['engine'] == 'blender' and scene['params'].get('character_profile') != profile:
            raise ValueError('Scene changed the locked story character: '+scene['id'])


def ensure_character(workspace, cues):
    """Build and validate the actual lead before the cloud/local scene planner."""
    import motion
    workspace = Path(workspace)
    profile = design(cues)
    key = digest(dict(profile=profile, workers={name: contract.sha(contract.SYSTEM/name)
        for name in ('character_design.py', 'blender_character.py', 'blender_worker.py')}))
    folder = contract.no_links(workspace/'_SYSTEM/work/character_design'/key, workspace)
    folder.mkdir(parents=True, exist_ok=True)
    saved = folder/'validated_character.json'
    if saved.is_file():
        record = contract.read_json(saved)
        good = record['profile'] == profile and all((folder/name).is_file() and contract.sha(folder/name) == checksum for name, checksum in record['files'].items())
        if good:
            print('CHARACTER: validated story identity reused before scene planning.', flush=True)
            return publish(workspace, folder, profile, record)
    print('CHARACTER: designing and rendering the lead before scene planning.', flush=True)
    package = folder/'package'
    (package/'scripts').mkdir(parents=True, exist_ok=True)
    shutil.copy2(contract.SYSTEM/'blender_character.py', package/'scripts/character.py')
    render = folder/'render'
    render.mkdir(exist_ok=True)
    scene = dict(id='character_reference', engine='blender', start_frame=0, end_frame=12,
        script='scripts/character.py', params=dict(action='stand', environment='living', camera='detail',
        emotion='neutral', camera_move='locked', character_profile=profile, character_portrait=True))
    project = dict(canvas=dict(width=1280, height=720, fps=24), seed=91, scenes=[scene], assets=[])
    tools = motion.tools_for(project)
    task = dict(project=project, scene=scene, package=str(package), output=str(render),
        sdk_root=str(contract.SYSTEM/'framework'), preview=True, source_text='',
        creative_scene=dict(beats=[dict(start_frame=0, end_frame=12, on_screen_text=[])], claims=[]))
    contract.write_json(folder/'task.json', task)
    command = [tools['blender'], '--background', '--factory-startup', '--disable-autoexec',
        '--python-exit-code', '1', '--python', str(contract.SYSTEM/'blender_worker.py'), '--', str(folder/'task.json')]
    motion.run_worker(command, render/'progress.json', folder/'render.log', 'character reference', 600, 120)
    geometry = contract.read_json(render/'geometry_qa.json')
    if geometry['status'] != 'passed' or geometry['checked_frames'] != 3:
        raise ValueError('Character design failed its actual Blender geometry check.')
    build = contract.read_json(render/'build_report.json')
    if build.get('character_identity_id') != profile['identity_id']:
        raise ValueError('Rendered character did not match its locked design.')
    from PIL import Image
    for index in (1, 2, 3):
        with Image.open(render/f'preview_{index:02}.png') as frame:
            if frame.size != (320, 180):
                raise ValueError('Character portrait dimensions changed.')
            frame.verify()
    shutil.copy2(render/'preview_02.png', folder/'character_face.png')
    record = dict(status='validated_character', profile=profile, geometry=geometry,
        files={'character_face.png': contract.sha(folder/'character_face.png')},
        builder_sha256=contract.sha(package/'scripts/character.py'),
        method='Actual Blender portrait execution, locked profile and sampled geometry; no artistic approval.')
    contract.write_json(saved, record)
    return publish(workspace, folder, profile, record)


def publish(workspace, folder, profile, record):
    output = workspace/'OUTPUT'
    output.mkdir(exist_ok=True)
    shutil.copy2(folder/'character_face.png', output/'character_face.png')
    contract.write_json(output/'CHARACTER_DESIGN.json', record)
    return profile, record
