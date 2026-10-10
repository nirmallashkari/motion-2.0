"""Registered multi-actor story plan: source evidence, roles and action limits."""
import copy
import json
from pathlib import Path
import re
from jsonschema import Draft202012Validator

import contract
from character_design import design, digest, validate_profile

REVISION='multi-cast-1.0'
ROLES=('king','queen','minister','boy','girl','parent','teacher','student','merchant','noble','adult')
LOCATIONS=('court','market','room','street','garden')
ACTIONS={
 'stand':'Stand with restrained breathing and gaze.',
 'sit':'Sit on the registered court throne.',
 'rise':'Rise from the registered court throne to address the listener.',
 'speak':'Turn toward the listener, gesture and animate the mouth.',
 'offer_coins':'Present a visible gold and silver coin choice.',
 'choose_silver':'Reach for silver, transfer it to the chooser hand, and retract.',
 'laugh':'Raise the head, move the shoulders and smile broadly.',
 'worry':'Lower the head and bring a hand inward.',
 'tremble':'Hold both hands near the waist with visible anxious shaking.',
 'ask':'Question a listener with an open palm and concerned brows.',
 'nod':'Nod and give a restrained reply.',
 'open_chest':'Lift a hinged chest lid, revealing silver savings.',
 'show_savings':'Present the open chest of silver coins to another actor.',
 'accuse':'Point toward an accused actor with a tense expression.',
 'defend':'Raise a stopping palm, then address the group.',
 'depart':'Walk a short distance together without changing identities.',
 'think':'Hold a thoughtful pose, with gaze and hand progression.',
 'smile':'Look toward the viewer or listener and form a restrained smile.',
 'wait':'Wait while another actor responds.',
}
PROPS=('none','coins','chest','throne','scroll','hourglass')


def should_route(workspace,cues):
    path=Path(workspace)/'_SYSTEM/multi_cast.json'
    if not path.is_file() or contract.read_json(path)!=dict(enabled=True,mode='auto'):
        return False
    text=' '.join(c['text'] for c in cues).casefold()
    roles={role for role in ROLES[:-1] if re.search(r'\b'+role+r'\b',text)}
    return len(roles)>=2


def schema(cues):
    actor=dict(type='object',additionalProperties=False,required=['id','role','age','evidence','face_style','hair_style','costume'],properties=dict(
        id=dict(type='string',pattern='^[a-z][a-z0-9_]{0,23}$'),role=dict(enum=list(ROLES)),
        age=dict(enum=['child','adult','mature']),evidence=dict(type='string',minLength=3,maxLength=120),
        face_style=dict(enum=['oval','round','angular']),hair_style=dict(enum=['side_part','textured_crop','soft_curls','swept_wave','long_bob']),
        costume=dict(enum=['royal','formal','scholar','casual','merchant'])))
    beat=dict(type='object',additionalProperties=False,required=['actor','action'],properties=dict(
        actor=dict(type='string'),action=dict(enum=list(ACTIONS))))
    scene=dict(type='object',additionalProperties=False,required=['cue_id','location','actors','speaker','listener','prop','camera','emotion','intent','evidence','beats'],properties=dict(
        cue_id=dict(type='integer'),location=dict(enum=list(LOCATIONS)),
        actors=dict(type='array',minItems=1,maxItems=3,uniqueItems=True,items=dict(type='string')),
        speaker=dict(type='string'),listener=dict(type='string'),prop=dict(enum=list(PROPS)),
        camera=dict(enum=['wide','medium','two_shot']),emotion=dict(enum=['neutral','warm','tense','concerned','confident']),
        intent=dict(type='string',minLength=20,maxLength=500),evidence=dict(type='string',minLength=3,maxLength=500),
        beats=dict(type='array',minItems=3,maxItems=3,items=beat)))
    return dict(type='object',additionalProperties=False,required=['cast','scenes'],properties=dict(
        cast=dict(type='array',minItems=2,maxItems=6,items=actor),
        scenes=dict(type='array',minItems=len(cues),maxItems=len(cues),items=scene)))


def validate_cast(cast,cues):
    Draft202012Validator(schema(cues)['properties']['cast']).validate(cast)
    source=' '.join(c['text'] for c in cues)
    ids=[c['id'] for c in cast]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate cast identity')
    required={role for role in ROLES if role not in {'parent','adult'} and re.search(r'\b'+role+r's?\b',source,re.I)}
    if required-{a['role'] for a in cast}:raise ValueError('Cast omits explicitly named story roles: '+', '.join(sorted(required-{a['role'] for a in cast})))
    for actor in cast:
        if actor['evidence'] not in source:raise ValueError('Cast evidence absent from source')
        if actor['age']=='child' and not re.search(r'\bboy\b|\bgirl\b|\bchild\b|\bson\b|\bdaughter\b',source,re.I):
            raise ValueError('Child character lacks source support')
    return cast


def validate_plan(plan,cues,cast_source=None):
    Draft202012Validator(schema(cues)).validate(plan)
    validate_cast(plan['cast'],cast_source or cues)
    ids=[c['id'] for c in plan['cast']]
    if [s['cue_id'] for s in plan['scenes']]!=[c['id'] for c in cues]:raise ValueError('Source line order changed')
    signatures=set();previous=None
    for scene,cue in zip(plan['scenes'],cues):
        visible=scene['actors']
        if any(a not in ids for a in visible):raise ValueError('Unknown on-screen actor')
        if scene['speaker'] not in visible or scene['listener'] not in visible+['none']:
            raise ValueError('Speaker/listener is not visible')
        if scene['evidence'] not in cue['text']:raise ValueError('Scene lacks a verbatim source anchor')
        if previous and scene['location']==previous['location'] and set(visible)==set(previous['actors']) and visible!=previous['actors']:
            raise ValueError('Continuing scene flipped left-to-right stage positions')
        for beat in scene['beats']:
            if beat['actor'] not in visible:raise ValueError('Action actor is not visible')
            if beat['action'] in {'offer_coins','choose_silver'} and scene['prop']!='coins':raise ValueError('Coin action requires coins')
            if beat['action'] in {'open_chest','show_savings'} and scene['prop']!='chest':raise ValueError('Chest action requires a chest')
            if beat['action'] in {'sit','rise'} and (scene['location']!='court' or scene['prop']!='throne'):
                raise ValueError('Seated court action requires the court throne')
        actions=[b['action'] for b in scene['beats']]
        occupants={b['actor'] for b in scene['beats'] if b['action'] in {'sit','rise'}}
        if len(occupants)>1:raise ValueError('A throne has only one seated occupant')
        if actions.count('rise')>1 or ('rise' in actions and 'sit' in actions):
            raise ValueError('A rise scene starts seated and rises once; do not also schedule sit')
        if 'choose_silver' in actions and len(visible)<2:raise ValueError('Coin selection needs giver and receiver')
        if not any(a not in {'stand','wait'} for a in actions):raise ValueError('Entire scene has no meaningful action')
        signature=json.dumps(dict(location=scene['location'],actors=visible,prop=scene['prop'],beats=scene['beats']),sort_keys=True)
        if signature in signatures:raise ValueError('Repeated complete action staging; choose a source-supported action variant')
        signatures.add(signature)
        previous=scene
    return plan


def cast_profiles(plan,cues):
    source=' '.join(c['text'] for c in cues)
    result=[]
    used_shirts=set()
    for actor in plan['cast']:
        profile=design([dict(text=source+' Character identity: '+actor['id']+' '+actor['role'])])
        appearance=profile['appearance']
        appearance['hairstyle']=actor['hair_style']
        appearance['shape'].update({'oval':dict(width=.318,height=.41),'round':dict(width=.348,height=.37),
            'angular':dict(width=.335,height=.421)}[actor['face_style']])
        if actor['costume']=='royal':
            appearance['palette']['shirt']=[.28,.025,.045,1]
        elif actor['costume'] in {'formal','scholar'}:
            appearance['palette']['shirt']=[.035,.12,.19,1]
        elif actor['age']=='child':
            appearance['palette']['shirt']=[.10,.31,.24,1]
            appearance['shape'].update(height=.37,eye_size=.076,nose_width=.048)
        shirt=tuple(appearance['palette']['shirt'])
        if shirt in used_shirts:
            alternatives=([.25,.035,.28,1],[.48,.27,.06,1],[.025,.29,.30,1],[.60,.52,.36,1],[.22,.27,.40,1])
            offset=int(digest(dict(source=source,actor=actor['id']))[:8],16)%len(alternatives)
            for index in range(len(alternatives)):
                candidate=alternatives[(offset+index)%len(alternatives)]
                if tuple(candidate) not in used_shirts:
                    appearance['palette']['shirt']=candidate;shirt=tuple(candidate);break
        used_shirts.add(shirt)
        profile['identity_id']=digest(dict(source=profile['source_sha256'],appearance=appearance,revision=profile['revision']))
        validate_profile(profile)
        result.append(dict(actor,profile=profile,scale=.78 if actor['age']=='child' else 1.0))
    if len({a['profile']['identity_id'] for a in result})!=len(result):raise ValueError('Cast appearances collide')
    return result
