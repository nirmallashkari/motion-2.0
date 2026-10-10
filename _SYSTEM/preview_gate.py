"""Render real setup/action/result samples before expensive hybrid production.

This gate checks execution, sampled character geometry and visible state change.
It is not an AI vision review or artistic approval.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys

from PIL import Image,ImageChops,ImageStat,ImageDraw
import contract
from action_direction import enforce
from quality_check import check_repeats

REVISION='action-preview-1.0'


def inspect_frames(project, folder):
    scenes=[]; pictures=[]; failures=[]
    for scene in project['scenes']:
        paths=sorted((folder/scene['id']).glob('preview_*.png'))
        if len(paths)!=3:raise ValueError(scene['id']+': exactly three preview samples are required.')
        images=[]
        for path in paths:
            with Image.open(path) as frame:
                expected=(640,360) if scene.get('params',{}).get('cast') else (320,180)
                if frame.size!=expected:raise ValueError('Preview sample dimensions changed.')
                images.append(frame.convert('L').resize((160,90)))
        # Exclude the outer frame; background movement still makes this heuristic.
        delta=max(ImageStat.Stat(ImageChops.difference(images[0].crop((24,9,136,81)),im.crop((24,9,136,81)))).mean[0] for im in images[1:])
        if delta<=.50:failures.append(scene['id']+': no visible setup/action/result change in sampled subject region.')
        geometry=None
        if scene['engine']=='blender':
            geometry=contract.read_json(folder/scene['id']/'geometry_qa.json')
            if geometry['status']!='passed' or geometry['checked_frames']!=3:failures.append(scene['id']+': sampled character geometry did not pass.')
        scenes.append(dict(id=scene['id'],engine=scene['engine'],subject_region_change=round(delta,4),sampled_frames=3,
            geometry=geometry,frame_hashes={p.name:contract.sha(p) for p in paths}))
        pictures.append((scene['id'],images))
    repeats=check_repeats(pictures)
    repeats.update(samples_per_shot=3,method='Three setup/action/result grayscale samples; every sampled picture must differ from a repeated shot.')
    if repeats['status']=='failed':failures.append('Preview pictures repeat an earlier shot.')
    return dict(revision=REVISION,status='failed' if failures else 'passed',scenes=scenes,failures=failures,no_repeat=repeats,
        repair_policy='One bounded registered Blender camera repair; other failures stop before full render.',
        limitations=['Three still samples per shot do not verify every frame, word-level sync or artistic quality.',
            'Subject-region differences can include camera or background motion; this is not unrestricted semantic vision QA.'])


def run(workspace,package,project,cues):
    import motion
    workspace=Path(workspace);package=Path(package)
    contract.validate_package(package);enforce(project,cues)
    tools=motion.tools_for(project)
    identity=hashlib.sha256((REVISION+json.dumps(project,sort_keys=True)+
        ''.join(contract.sha(p) for p in contract.package_files(package))+
        ''.join(contract.sha(contract.SYSTEM/name) for name in ('preview_gate.py','python_worker.py','blender_worker.py'))).encode()).hexdigest()
    root=contract.no_links(workspace/'_SYSTEM/work/action_previews'/identity,workspace);root.mkdir(parents=True,exist_ok=True)
    report_path=root/'report.json';cached=False
    if report_path.is_file():
        saved=contract.read_json(report_path)
        cached=saved['status']=='passed' and all((root/item['id']/name).is_file() and contract.sha(root/item['id']/name)==sha
            for item in saved['scenes'] for name,sha in item['frame_hashes'].items())
    if not cached:
        creative=contract.read_json(package/'creative_plan.json');plans={item['id']:item for item in creative['scenes']}
        for number,scene in enumerate(project['scenes'],1):
            print(f"PREVIEW: setup/action/result {number}/{len(project['scenes'])} [{scene['engine']}].",flush=True)
            output=root/scene['id'];output.mkdir(exist_ok=True)
            task=dict(project=project,scene=scene,package=str(package),output=str(output),clip=str(output/'unused.mp4'),
                ffmpeg=tools['ffmpeg'],sdk_root=str(contract.SYSTEM/'framework'),creative_scene=plans[scene['id']],
                source_text=' '.join(c['text'] for c in cues if c['id'] in scene['source_cues']),preview=True)
            path=root/(scene['id']+'.json');contract.write_json(path,task)
            command=([sys.executable,'-u',str(contract.SYSTEM/'python_worker.py'),str(path)] if scene['engine']=='python' else
                [tools['blender'],'--background','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(contract.SYSTEM/'blender_worker.py'),'--',str(path)])
            motion.run_worker(command,output/'progress.json',root/(scene['id']+'.log'),'preview '+str(number),600,180)
    report=inspect_frames(project,root);report.update(cache_used=cached,preview_folder=str(root),identity=identity)
    contract.write_json(report_path,report);contract.write_json(workspace/'OUTPUT/PREVIEW_QA.json',report)
    if report['failures']:raise ValueError('Preview gate failed before full render: '+'; '.join(report['failures']))
    sheet=Image.new('RGB',(960,210*len(project['scenes'])),'#101c2b');draw=ImageDraw.Draw(sheet)
    for row,scene in enumerate(project['scenes']):
        for col,path in enumerate(sorted((root/scene['id']).glob('preview_*.png'))):
            with Image.open(path) as frame:sheet.paste(frame,(320*col,210*row))
        draw.text((8,210*row+185),f"Shot {row+1}: setup / action / result",fill='white')
    sheet.save(root/'contact_sheet.jpg')
    public=workspace/'OUTPUT/preview_contact_sheet.jpg';shutil.copy2(root/'contact_sheet.jpg',public)
    print('PREVIEW: sampled motion and geometry checks passed; full rendering may start.',flush=True)
    return report
