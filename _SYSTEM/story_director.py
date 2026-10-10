"""Source-grounded shot sequencing, continuity grouping and editorial diagnostics."""
import re

REVISION = 'director-1.1'
CAMERAS = ('wide', 'medium', 'detail')
MOVES = ('push', 'orbit', 'locked', 'tracking')
EMOTIONS = ('neutral', 'focused', 'happy', 'concerned')
FULL_BODY = {'walk','run','cycle','jump','pushup','squat','stretch','carry_phone','carry_box'}


def source_emotion(text):
    if re.search(r'\bsad\b|\bworr|\bdisappoint|उदास|निराश|परेशान|\bdarr\b|taane|waqt kharab|nazron mein gir',text,re.I):
        return 'concerned'
    if re.search(r'\bcelebrat|\bhappy\b|\bjoy\b|जश्न|खुशी|जीत',text,re.I):
        return 'happy'
    return 'neutral'


def direct(cues, choices):
    """Keep model choices; bound optional styling and vary repeated shots."""
    output=[]
    for index,(cue,choice) in enumerate(zip(cues,choices)):
        item=dict(choice)
        role='hook' if index==0 else 'closing' if index==len(cues)-1 else 'development'
        if re.search(r'लेकिन|however|but\b|instead|बजाय',cue['text'],re.I):role='turn'
        item['story_role']=role
        item['emotion']=source_emotion(cue['text'])
        if item['action'] in {'read','write','type','paint','cook'} and item['emotion']=='neutral':item['emotion']='focused'
        # Camera choices cannot crop whole-body interactions into hand-only shots.
        if item['action'] in FULL_BODY and item['camera']=='detail':item['camera']='medium'
        if index==0 or (output and item['action']!=output[-1]['action']):item['camera']='wide'
        if item.get('theme') in {'fear','criticism','exhaustion','selfworth','resolve','confidence'}:
            item['camera']='detail' if item['theme']=='fear' else 'medium'
        if len(output)>=2 and item['camera']==output[-1]['camera']==output[-2]['camera']:
            item['camera']='medium' if item['camera']=='wide' else 'wide'
        item['camera_move']='tracking' if item['action'] in {'walk','carry_phone','carry_box'} else 'orbit' if role=='turn' else 'push'
        output.append(item)
    return output


def merge_continuous(scenes,plans,fps=24,max_seconds=8):
    """Continue matching adjacent registered shots without restarting animation."""
    merged=[];creative=[];groups=[]
    for scene,plan in zip(scenes,plans):
        params=scene['params']
        prior=merged[-1] if merged else None
        same_3d=prior is not None and scene['engine']==prior['engine']=='blender' and all(
            params.get(key)==prior['params'].get(key) for key in ('action','environment','emotion','theme'))
        same_graphic=prior is not None and scene['engine']==prior['engine']=='python' and params.get('theme') and (
            params.get('theme')==prior['params'].get('theme'))
        same=(same_3d or same_graphic) and not params.get('line_mode') and not (prior and prior['params'].get('line_mode'))
        if same and scene['end_frame']-prior['start_frame']<=fps*max_seconds:
            prior['end_frame']=scene['end_frame']
            prior['source_cues']=list(dict.fromkeys(prior['source_cues']+scene['source_cues']))
            prior['params']['semantic_cues']=list(dict.fromkeys(prior['params'].get('semantic_cues',[])+params.get('semantic_cues',[])))
            creative[-1]['beats']+=plan['beats']
            creative[-1]['claims']+=plan['claims'][1:]
            groups[-1]['source_cues']=prior['source_cues']
        else:
            merged.append(scene);creative.append(plan)
            groups.append(dict(scene_id=scene['id'],source_cues=list(scene['source_cues']),role=params.get('story_role','development')))
    scenes[:]=merged;plans[:]=creative
    return groups


def evaluate(cues,scenes):
    literal=set();abstract=set();warnings=[];runs=1
    for i,scene in enumerate(scenes):
        owned=scene['params'].get('semantic_cues',scene['source_cues'])
        if scene['engine']=='python' and scene['id'].startswith('abstract_story__'):
            abstract.update(owned)
        else:literal.update(owned)
        signature=(scene['engine'],scene['params'].get('action'),scene['params'].get('camera'))
        old=(scenes[i-1]['engine'],scenes[i-1]['params'].get('action'),scenes[i-1]['params'].get('camera')) if i else None
        runs=runs+1 if i and signature==old else 1
        if runs==4:warnings.append(dict(scene=scene['id'],reason='Four consecutive shots repeat an engine/action/camera combination.'))
    unknown=sorted(abstract-literal)
    if unknown:warnings.append(dict(source_cues=unknown,reason='Source meaning has no literal supported scene; abstract illustration requires review.'))
    return dict(revision=REVISION,status='review_required' if warnings else 'checks_passed',
        literal_cue_fraction=round(len(literal)/max(1,len(cues)),3),abstract_cues=unknown,
        source_cues=len(cues),shots=len(scenes),warnings=warnings,
        limitations=['Catalog coverage and repetition checks are not independent semantic or artistic approval.'])
