"""One source unit per shot, real renderer variation and explicit repeat failure."""
import json

REVISION='line-shots-1.0'
# Each profile changes rendered camera position and its motion, not just an ID.
PROFILES=[dict(name=f'{angle_name}_{move}',yaw=yaw,move=move) for angle_name,yaw in
    (('left',-.42),('left_center',-.21),('front',0.),('right_center',.21),('right',.42))
    for move in ('push','pull','orbit')]


def content_key(preset,choice):
    if choice['action']!='python':
        content=dict(engine='blender',theme=choice.get('theme'),action=choice['action'])
    else:
        content=dict(engine='python',theme=choice.get('theme'),kind=preset['kind'],
            action=preset.get('action') if preset['kind']=='asset' else None,
            icon=preset.get('icon'),secondary=preset.get('secondary'),domain=preset.get('domain'))
    return json.dumps(content,sort_keys=True)


def assign(cues,selected,choices):
    """Assign visibly different registered camera profiles for recurring content."""
    if len(cues)!=len(selected) or len(cues)!=len(choices):raise ValueError('One visual choice is required per source line.')
    seen={};output=[]
    for cue,preset,choice in zip(cues,selected,choices):
        if choice['cue_id']!=cue['id']:raise ValueError('Visual line order changed.')
        item=dict(choice);key=content_key(preset,item);count=seen.get(key,0)
        if count>=len(PROFILES):
            raise ValueError(f"Unique visual alternatives exhausted at source line {cue['id']}. Add a source-related recipe; do not recycle a shot.")
        # Alternate visibly different camera sides before smaller nearby changes.
        order=(2*3,0*3,4*3,1*3,3*3,2*3+1,0*3+1,4*3+1,1*3+1,3*3+1,
               2*3+2,0*3+2,4*3+2,1*3+2,3*3+2)
        item['shot_profile']=dict(PROFILES[order[count]])
        item['content_key']=key;item['line_mode']=True
        seen[key]=count+1;output.append(item)
    return output


def inspect(project,cues):
    """IDs and source text never count as visual uniqueness."""
    failures=[];seen={};owned=[]
    for scene in project['scenes']:
        params=scene['params'];owners=params.get('semantic_cues',[]);owned+=owners
        if len(owners)!=1:failures.append(f"{scene['id']}: exactly one semantic source line is required.")
        profile=params.get('shot_profile') or {}
        camera=dict(yaw=profile.get('yaw'),move=profile.get('move'))
        if not any(camera==dict(yaw=p['yaw'],move=p['move']) for p in PROFILES):
            failures.append(f"{scene['id']}: unregistered rendered camera profile.")
        signature=json.dumps(dict(content=params.get('content_key'),profile=camera),sort_keys=True)
        if not params.get('content_key') or not params.get('shot_profile'):
            failures.append(f"{scene['id']}: renderer-backed uniqueness data is missing.")
        elif signature in seen:failures.append(f"{scene['id']}: visual repeats {seen[signature]}.")
        seen[signature]=scene['id']
    if owned!=[cue['id'] for cue in cues]:failures.append('Every source line must own exactly one visual shot in order.')
    if len(project['scenes'])!=len(cues):failures.append('Visual shot count differs from source line count.')
    return dict(revision=REVISION,status='failed' if failures else 'plan_passed',
        source_lines=len(cues),visual_shots=len(project['scenes']),failures=failures,
        repeat_scope='Exact shot content plus rendered camera profile; character identity may recur.',
        limitations=['Plan uniqueness is not independent perceptual approval. A decoded similarity check runs before publication.'])


def enforce(project,cues):
    report=inspect(project,cues)
    if report['failures']:raise ValueError('Line visual policy failed: '+'; '.join(report['failures']))
    return report
