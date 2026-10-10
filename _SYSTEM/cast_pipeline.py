"""Reusable API director: cast references, source-bound choreography and delivery."""
import base64
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from PIL import Image,ImageDraw

import contract
from cloud_contract import digest
from cast_contract import REVISION,ACTIONS,schema,validate_plan,validate_cast,cast_profiles


def builder_source():
    base=(contract.SYSTEM/'blender_character.py').read_text(encoding='utf-8')
    return base.replace('def build(ctx,spec):','def build_legacy(ctx,spec):')+'\n'+(contract.SYSTEM/'cast_renderer.py').read_text()


def request_plan(workspace,cues,settings,phase,cast=None,feedback=None):
    request=dict(revision=REVISION,phase=phase,source=cues,settings={key:settings[key] for key in ('provider','model')},
        capabilities=ACTIONS,cast=cast,feedback=feedback,workers={name:contract.sha(contract.SYSTEM/name) for name in ('cast_contract.py','cast_broker.py','deepseek_client.py','credential_store.py')})
    folder=contract.no_links(Path(workspace)/'_SYSTEM/work/cast_director'/digest(request),workspace)
    folder.mkdir(parents=True,exist_ok=True);contract.write_json(folder/'request.json',request)
    response_file=folder/'validated_plan.json';cached=response_file.is_file()
    if not cached:
        print(f'DIRECTOR: API {phase}; script determines identities and actions.',flush=True)
        with (folder/'broker.log').open('wb') as log:
            process=subprocess.Popen([sys.executable,str(contract.SYSTEM/'cast_broker.py'),str(folder)],stdout=log,stderr=log)
            start=last=time.monotonic();timeout=660*max(1,(len(cues)+5)//6)
            try:
                while process.poll() is None:
                    now=time.monotonic()
                    if now-start>timeout:raise TimeoutError('AI Director exceeded its bounded deadline')
                    if now-last>=15:
                        state=contract.read_json(folder/'status.json') if (folder/'status.json').is_file() else {}
                        print(f"DIRECTOR: {phase} {state.get('status','connecting')}; {now-start:.0f}s elapsed.",flush=True);last=now
                    time.sleep(.25)
                if process.returncode:raise ValueError('AI Director failed; inspect '+str(folder/'broker.log'))
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=20)
    response=contract.read_json(response_file)
    if response['request_id']!=digest(request) or response['revision']!=REVISION or response['status']!='completed':
        raise ValueError('AI Director response is stale')
    if phase=='scenes':
        validate_plan(response['plan'],cues)
        if response['plan']['cast']!=cast:raise ValueError('Director changed the locked cast')
    else:
        from jsonschema import Draft202012Validator
        Draft202012Validator(schema(cues)['properties']['cast']).validate(response['plan']['cast'])
        validate_cast(response['plan']['cast'],cues)
    response['cache_used']=cached
    return response,folder


def cached_preview(folder):
    saved=folder/'preview_integrity.json'
    if not saved.is_file():return False
    record=contract.read_json(saved)
    names=['geometry_qa.json','build_report.json']+[f'preview_{i:02}.png' for i in (1,2,3)]
    return set(record)==set(names) and all((folder/name).is_file() and contract.sha(folder/name)==record[name] for name in names)


def task_preview(workspace,package,project,scene,creative,folder):
    import motion
    folder.mkdir(parents=True,exist_ok=True)
    tools=motion.tools_for(project)
    task=dict(project=project,scene=scene,package=str(package),output=str(folder),preview=True,
        sdk_root=str(contract.SYSTEM/'framework'),creative_scene=creative,source_text='')
    contract.write_json(folder/'task.json',task)
    motion.run_worker([tools['blender'],'--background','--factory-startup','--disable-autoexec','--python-exit-code','1',
        '--python',str(contract.SYSTEM/'blender_worker.py'),'--',str(folder/'task.json')],folder/'progress.json',folder/'render.log',scene['id'],1200,180)
    geometry=contract.read_json(folder/'geometry_qa.json')
    if geometry['status']!='passed' or geometry['checked_frames']!=3:raise ValueError('Cast geometry preview failed')
    build=contract.read_json(folder/'build_report.json')
    expected=[a['profile']['identity_id'] for a in scene['params']['cast'] if a['id'] in scene['params']['direction']['actors']]
    if build['actor_identity_ids']!=expected:raise ValueError('Actual Blender cast identities differ from the locked cast')
    contract.write_json(folder/'preview_integrity.json',{name:contract.sha(folder/name) for name in
        ['geometry_qa.json','build_report.json']+[f'preview_{i:02}.png' for i in (1,2,3)]})
    return geometry


def render_cast(workspace,cast):
    identity=digest(dict(cast=cast,builder=builder_source(),worker=contract.sha(contract.SYSTEM/'blender_worker.py')))
    root=Path(workspace)/'_SYSTEM/work/cast_references'/identity;package=root/'package';(package/'scripts').mkdir(parents=True,exist_ok=True)
    (package/'scripts/cast.py').write_text(builder_source(),encoding='utf-8');contract.blender_code(builder_source())
    gallery=Image.new('RGB',(320*len(cast),210),'#101b2b');draw=ImageDraw.Draw(gallery)
    for index,actor in enumerate(cast):
        folder=root/actor['id'];saved=folder/'geometry_qa.json'
        direction=dict(actors=[actor['id']],location='room',prop='none',camera='wide',beats=[dict(actor=actor['id'],action='stand')]*3)
        scene=dict(id='cast_'+actor['id'],engine='blender',script='scripts/cast.py',start_frame=0,end_frame=12,source_cues=[1],
            params=dict(cast=[actor],direction=direction,cast_portrait=True))
        project=dict(canvas=dict(width=1280,height=720,fps=24),seed=91,assets=[],scenes=[scene])
        if not cached_preview(folder):
            print('CAST: actual Blender identity reference '+actor['id'],flush=True)
            task_preview(workspace,package,project,scene,dict(beats=[dict(start_frame=0,end_frame=12,on_screen_text=[])],claims=[]),folder)
        else:
            if contract.read_json(saved)['status']!='passed':raise ValueError('Cached cast geometry failed')
        with Image.open(folder/'preview_02.png') as picture:gallery.paste(picture.resize((320,180)),(index*320,0))
        draw.text((index*320+8,185),actor['id']+' / '+actor['role']+' / '+actor['age'],fill='white')
    gallery.save(root/'cast_reference.jpg',quality=94)
    output=Path(workspace)/'OUTPUT';output.mkdir(exist_ok=True)
    shutil.copy2(root/'cast_reference.jpg',output/'cast_reference.jpg')
    contract.write_json(output/'CAST_DESIGN.json',dict(revision=REVISION,cast=cast,status='references_rendered'))
    return root


def make_package(root,source,cues,plan,cast):
    package=root/'package';(package/'scripts').mkdir(parents=True,exist_ok=True)
    (package/'scripts/cast.py').write_text(builder_source(),encoding='utf-8')
    shutil.copy2(source,package/'source.srt');fps=24;scenes=[];creative=[];position=0
    previous_direction=None;coin_owner=None
    for cue,direction in zip(cues,plan['scenes']):
        end=round(cue['end']*fps/1000)
        if end<=position:raise ValueError('Source cue has no renderable frames')
        identity=f"cast_scene_{cue['id']:03}"
        overlap=[c['id'] for c in cues if c['start']<end/fps*1000-1e-7 and c['end']>position/fps*1000+1e-7]
        scenes.append(dict(id=identity,engine='blender',start_frame=position,end_frame=end,source_cues=overlap,
            script='scripts/cast.py',entry='build',description=direction['intent'],params=dict(cast=cast,direction=direction,semantic_cues=[cue['id']],line_mode=True)))
        continuing=previous_direction is not None and previous_direction['location']==direction['location'] and previous_direction['actors']==direction['actors'] and previous_direction['prop']=='coins' and direction['prop']=='coins'
        offering=any(b['action']=='offer_coins' for b in direction['beats'])
        if continuing and coin_owner in direction['actors'] and not offering:
            scenes[-1]['params']['initial_coin_owner']=coin_owner
        else:coin_owner=None
        for beat in direction['beats']:
            if beat['action']=='choose_silver':coin_owner=beat['actor']
        previous_direction=direction
        beats=[]
        for index,beat in enumerate(direction['beats']):
            a=position+round((end-position)*index/3);b=position+round((end-position)*(index+1)/3)
            for start in range(a,b,72):beats.append(dict(start_frame=start,end_frame=min(b,start+72),kind='object_action',
                action=beat['actor']+' performs '+beat['action']+' using the locked cast and registered props.',on_screen_text=[]))
        creative.append(dict(id=identity,visual_goal=direction['intent'],main_objects=direction['actors']+[direction['prop']],beats=beats,
            claims=[dict(text=cue['text'],basis='source_only',source_cues=[cue['id']],evidence=cue['text'])]))
        position=end
    project=dict(format=contract.VERSION,rulebook_version='1.0',title='AI Directed Story',canvas=dict(width=1280,height=720,fps=24),
        total_frames=position,caption_mode='off',seed=91,scenes=scenes,assets=[])
    contract.write_json(package/'project.json',project)
    contract.write_json(package/'creative_plan.json',dict(rulebook_version='1.0',scenes=creative,references=[]))
    contract.write_json(package/'qa_report.json',dict(status='authored_unverified',capabilities=dict(python=True,blender=True,
        image_inspection=False,video_inspection=False,audio_inspection=False),checks=['API source/cast/capability validation'],blocking_issues=[],
        limitations=['Stylized registered actions; no artistic score or exact lip synchronization claimed.']))
    (package/'storyboard.md').write_text('# API-directed story\n\n'+ '\n\n'.join(f"{s['start_frame']/24:.3f}-{s['end_frame']/24:.3f}s: {s['description']}" for s in scenes),encoding='utf-8')
    contract.validate_package(package,source)
    return package,project,creative


def render_previews(workspace,package,project,creative):
    from preview_gate import inspect_frames
    import copy
    render_project=copy.deepcopy(project)
    # line_mode controls decoded movie QA, not any registered Blender pixels.
    for scene in render_project['scenes']:scene['params'].pop('line_mode',None)
    identity=digest(dict(project=render_project,builder=builder_source(),worker=contract.sha(contract.SYSTEM/'blender_worker.py')))
    root=Path(workspace)/'_SYSTEM/work/cast_previews'/identity;root.mkdir(parents=True,exist_ok=True)
    report_file=root/'preview_report.json'
    for index,(scene,planned) in enumerate(zip(project['scenes'],creative),1):
        folder=root/scene['id'];saved=folder/'geometry_qa.json'
        if not cached_preview(folder):
            print(f'STORY PREVIEW: {index}/{len(project["scenes"])} actors={len(scene["params"]["direction"]["actors"])}',flush=True)
            task_preview(workspace,package,project,scene,planned,folder)
    report=inspect_frames(project,root)
    if report['status']!='passed':raise ValueError('Multi-cast preview failed: '+'; '.join(report['failures']))
    sheet=Image.new('RGB',(960,len(project['scenes'])*210),'#101b2b');draw=ImageDraw.Draw(sheet)
    for row,scene in enumerate(project['scenes']):
        row_image=Image.new('RGB',(960,210),'#101b2b');row_draw=ImageDraw.Draw(row_image)
        for col in range(3):
            with Image.open(root/scene['id']/f'preview_{col+1:02}.png') as picture:
                thumbnail=picture.resize((320,180))
                sheet.paste(thumbnail,(col*320,row*210));row_image.paste(thumbnail,(col*320,0))
        draw.text((8,row*210+184),scene['id']+' / '+scene['params']['direction']['location'],fill='white')
        row_draw.text((8,184),scene['id']+' / '+scene['params']['direction']['location'],fill='white')
        row_image.save(root/scene['id']/'review_samples.jpg',quality=94)
    sheet.save(root/'contact_sheet.jpg',quality=94);contract.write_json(report_file,report)
    shutil.copy2(root/'contact_sheet.jpg',Path(workspace)/'OUTPUT/story_preview.jpg')
    contract.write_json(Path(workspace)/'OUTPUT/PREVIEW_QA.json',report)
    return root,report


def run(workspace,source,cues,voice,settings):
    import motion
    workspace=Path(workspace)
    contract.write_json(workspace/'OUTPUT/SYSTEM_STATUS.json',dict(status='planning',mode='cast_director',planner_provider='deepseek'))
    cast_response,_=request_plan(workspace,cues,settings,'cast')
    cast=cast_profiles(cast_response['plan'],cues)
    render_cast(workspace,cast)
    # Physical identities are now fixed before the API directs the scenes.
    scene_response,_=request_plan(workspace,cues,settings,'scenes',cast=cast_response['plan']['cast'])
    plan=scene_response['plan'];validate_plan(plan,cues);review_history=[];director_requests=[cast_response,scene_response]
    for attempt in range(3):
        root=workspace/'_SYSTEM/work/cast_packages'/digest(dict(plan=plan,cast=cast,builder=builder_source()))
        package,project,creative=make_package(root,source,cues,plan,cast)
        previews,preview=render_previews(workspace,package,project,creative)
        review=review_visuals(workspace,cues,plan,previews,settings);review_history.append(review)
        if not review['blocking_issues']:break
        if attempt==2:raise ValueError('Visual defects remain after two bounded AI repair attempts; previous movie preserved.')
        print('DIRECTOR: repairing sampled visual defects with locked cast and unchanged source.',flush=True)
        scene_response,_=request_plan(workspace,cues,settings,'scenes',cast=cast_response['plan']['cast'],
            feedback=dict(previous_plan=plan,visual_defects=review['blocking_issues']))
        director_requests.append(scene_response)
        plan=scene_response['plan']
    contract.write_json(workspace/'OUTPUT/DIRECTOR_PLAN.json',dict(revision=REVISION,cast=cast,scenes=plan['scenes'],
        cast_api_calls=0 if cast_response['cache_used'] else cast_response['calls'],
        scene_api_calls=sum(0 if r['cache_used'] else r['calls'] for r in director_requests[1:]),
        requests=[{key:r[key] for key in ('request_id','cache_used','calls','evidence','elapsed_seconds')} for r in director_requests],
        visual_review_history=review_history))
    contract.write_json(workspace/'OUTPUT/SYSTEM_STATUS.json',dict(status='rendering',mode='cast_director',planner_provider='deepseek',blender_scenes=len(cues),python_scenes=0))
    motion.execute(workspace,selection=(package,source,voice),self_mode=True)
    qa=contract.read_json(workspace/'OUTPUT/qa_report.json');delivery=workspace/'OUTPUT/deliveries'/qa['job_id'][:16]
    for name in ('CAST_DESIGN.json','DIRECTOR_PLAN.json','PREVIEW_QA.json','AI_VISUAL_REVIEW.json'):
        shutil.copy2(workspace/'OUTPUT'/name,delivery/name)
    for name in ('cast_reference.jpg','story_preview.jpg'):shutil.copy2(workspace/'OUTPUT'/name,delivery/name)
    summary=f"READY: AI-directed multi-character story; {len(cast)} identities, {len(cues)} authored scenes, {project['total_frames']/24:.3f}s.\nAll humans and interactions use Blender. Voice unchanged; subtitles OFF.\nCast design and choreography are API choices; registered local renderer executes them.\nVisual API review passed on sampled previews; exact lip/word sync and artistic score are not certified.\n"
    for output in (workspace/'OUTPUT',delivery):(output/'RUN_SUMMARY.txt').write_text(summary,encoding='utf-8')
    contract.write_json(workspace/'OUTPUT/SYSTEM_STATUS.json',dict(status='ready',mode='cast_director',planner_provider='deepseek',delivery=str(delivery),
        blender_scenes=len(cues),python_scenes=0,visual_review='sampled_api_review',cue_level_audio_sync_verified=False))
    contract.write_json(workspace/'OUTPUT/ERROR.json',dict(status='none',job_id=qa['job_id'],message='No active error; current movie passed publication checks.'))
    return 0


def review_visuals(workspace,cues,plan,previews,settings):
    images=[previews/f"cast_scene_{c['id']:03}"/'review_samples.jpg' for c in cues]
    actual=[[previews/f"cast_scene_{c['id']:03}"/f'preview_{i:02}.png' for i in (1,2,3)] for c in cues]
    request=dict(source=cues,plan=plan,settings={key:settings[key] for key in ('provider','model')},images=[str(p) for p in images],
        image_hashes=[contract.sha(p) for p in images],reviewer_sha256=contract.sha(contract.SYSTEM/'cast_review.py'),
        actual_images=[[str(p) for p in scene] for scene in actual],actual_image_hashes=[[contract.sha(p) for p in scene] for scene in actual],
        cast_image=str(Path(workspace)/'OUTPUT/cast_reference.jpg'),cast_image_sha256=contract.sha(Path(workspace)/'OUTPUT/cast_reference.jpg'))
    folder=Path(workspace)/'_SYSTEM/work/cast_reviews'/digest(request);folder.mkdir(parents=True,exist_ok=True)
    contract.write_json(folder/'request.json',request)
    cached=(folder/'review.json').is_file()
    if not cached:
        contract.write_json(Path(workspace)/'OUTPUT/AI_VISUAL_REVIEW.json',dict(status='reviewing',request_id=digest(request),model='deepseek-flash',scenes=[],blocking_issues=[]))
        print('DIRECTOR REVIEW: image-capable API inspects actual preview frames.',flush=True)
        with (folder/'review.log').open('wb') as log:
            process=subprocess.Popen([sys.executable,str(contract.SYSTEM/'cast_review.py'),str(folder)],stdout=log,stderr=log)
            start=last=time.monotonic()
            try:
                while process.poll() is None:
                    now=time.monotonic()
                    if now-start>660*max(1,len(cues)):raise TimeoutError('Visual review timed out')
                    if now-last>=15:print(f'DIRECTOR REVIEW: {now-start:.0f}s elapsed.',flush=True);last=now
                    time.sleep(.25)
                if process.returncode:
                    contract.write_json(Path(workspace)/'OUTPUT/AI_VISUAL_REVIEW.json',dict(status='failed',request_id=digest(request),model='deepseek-flash',scenes=[],blocking_issues=[],review_log=str(folder/'review.log')))
                    raise ValueError('AI visual review failed; inspect '+str(folder/'review.log'))
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=20)
    review=contract.read_json(folder/'review.json')
    if review['request_id']!=digest(request) or [s['cue_id'] for s in review['scenes']]!=[c['id'] for c in cues]:
        raise ValueError('Visual review response is stale or incomplete')
    blocking=[s for s in review['scenes'] if s['status']=='repair_required']
    if blocking!=review['blocking_issues'] or review['status']!=('repair_required' if blocking else 'passed'):
        raise ValueError('Visual review verdict contradicts its scene findings')
    if any((s['status']=='passed')!=(not s['issues']) for s in review['scenes']):raise ValueError('Visual review scene verdict is inconsistent')
    review.update(cache_used=cached,runtime_api_calls=0 if cached else review['calls'])
    contract.write_json(Path(workspace)/'OUTPUT/AI_VISUAL_REVIEW.json',review)
    return review
