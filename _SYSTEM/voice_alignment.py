"""Offline speech timing with source matching; original SRT is never rewritten."""
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata

import contract

REVISION='voice-alignment-1.2'
MODEL=contract.SYSTEM/'assets/models/faster-whisper-small'


def tokens(text):
    text=unicodedata.normalize('NFKC',text).lower()
    return re.findall(r'[^\W_]+(?:[\u0900-\u097f]+)?',text,re.UNICODE)


def match_words(cues,words):
    source=[];owners=[]
    for cue in cues:
        for token in tokens(cue['text']):source.append(token);owners.append(cue['id'])
    recognized=[];times=[]
    for word in words:
        for token in tokens(word['word']):
            recognized.append(token);times.append((float(word['start']),float(word['end'])))
    matcher=SequenceMatcher(None,source,recognized,autojunk=False)
    matched={}
    for block in matcher.get_matching_blocks():
        for offset in range(block.size):matched[block.a+offset]=block.b+offset
    results=[]
    for cue in cues:
        indices=[i for i,owner in enumerate(owners) if owner==cue['id']]
        samples=[times[matched[i]] for i in indices if i in matched]
        fraction=len(samples)/max(1,len(indices))
        within=all(cue['start']/1000-.8<=a<=b<=cue['end']/1000+.8 for a,b in samples)
        reliable=fraction>=.60 and within and bool(samples)
        beats=sorted(set(round(a-cue['start']/1000,3) for a,b in samples if cue['start']/1000<=a<cue['end']/1000)) if reliable else []
        results.append(dict(cue_id=cue['id'],matched_fraction=round(fraction,3),
            timing_verified=reliable,action_beats=beats[:12],
            speech_start_seconds=samples[0][0] if reliable else None,
            reason='Matched source words within timing tolerance.' if reliable else 'Insufficient matching words or timing drift; original SRT retained.'))
    coverage=len(matched)/max(1,len(source))
    return dict(status='matched' if coverage>=.65 and all(c['timing_verified'] for c in results) else 'partial',
        matched_word_fraction=round(coverage,3),cues=results,
        cue_level_timing_verified=all(c['timing_verified'] for c in results))


def align(workspace,voice,cues):
    if voice is None:return dict(status='unavailable',reason='No narration supplied.',cues=[])
    manifest_path=MODEL/'manifest.json'
    if not manifest_path.is_file():return dict(status='unavailable',reason='Local speech weights absent; SRT timing retained.',cues=[])
    manifest=contract.read_json(manifest_path)
    for filename,digest in manifest['files'].items():
        if filename not in {'model.bin','config.json','tokenizer.json','vocabulary.txt'} or contract.sha(MODEL/filename)!=digest:
            raise ValueError('Pinned local speech model checksum mismatch')
    identity=hashlib.sha256((REVISION+contract.sha(Path(__file__))+contract.sha(contract.SYSTEM/'speech_worker.py')+contract.sha(voice)+json.dumps(cues,sort_keys=True,ensure_ascii=False)+json.dumps(manifest,sort_keys=True)).encode()).hexdigest()
    cache=Path(workspace)/'_SYSTEM/work/voice_alignment'/(identity+'.json')
    if cache.is_file():
        saved=contract.read_json(cache);saved['cache_used']=True
        return saved
    started=time.monotonic()
    print('VOICE: matching narration against source using installed offline speech weights.',flush=True)
    try:
        source_text=' '.join(cue['text'] for cue in cues)
        roman_hindi=len(re.findall(r'\b(?:hai|hain|tum|tumhe|khud|nahi|kyunki|karo|hoga|zindagi)\b',source_text,re.I))>=3
        language='hi' if roman_hindi or any('\u0900'<=char<='\u097f' for char in source_text) else None
        recognition_key=hashlib.sha256((contract.sha(voice)+contract.sha(contract.SYSTEM/'speech_worker.py')+
            json.dumps(manifest,sort_keys=True)+str(language)).encode()).hexdigest()
        recognition_cache=cache.parent/'recognized'/(recognition_key+'.json')
        if recognition_cache.is_file():
            recognized=contract.read_json(recognition_cache)
            result=match_words(cues,recognized['words'])
            result.update(language=recognized['language'],recognized_words=recognized['words'],
                model_revision=manifest['revision'],elapsed_seconds=round(time.monotonic()-started,3),
                cache_used=True,external_network_used=False,source_timestamps_unchanged=True,
                limitations=['ASR word timestamps are estimates, not forced alignment or guaranteed exact synchronization.'])
            contract.write_json(cache,result)
            return result
        directory=cache.parent/identity;directory.mkdir(parents=True,exist_ok=True)
        result_file=directory/'recognized.json';progress=directory/'progress.json';request=directory/'request.json'
        contract.write_json(request,dict(model=str(MODEL),voice=str(Path(voice).resolve()),language=language,result=str(result_file),progress=str(progress)))
        deadline=started+min(1800,max(120,cues[-1]['end']/1000*4+90))
        with (directory/'inference.log').open('wb') as stream:
            process=subprocess.Popen([sys.executable,str(contract.SYSTEM/'speech_worker.py'),str(request)],stdout=stream,stderr=stream)
            last_print=started
            try:
                while process.poll() is None:
                    now=time.monotonic()
                    if now>deadline:raise TimeoutError('Offline speech inference exceeded its bounded time allowance; SRT retained.')
                    if now-last_print>=15:
                        state=contract.read_json(progress) if progress.is_file() else {}
                        print(f"VOICE: {state.get('seconds_decoded',0):.1f}/{cues[-1]['end']/1000:.1f}s examined; {now-started:.0f}s elapsed.",flush=True)
                        last_print=now
                    time.sleep(.2)
                if process.returncode:raise RuntimeError(f'Offline speech worker exited {process.returncode}; inspect {directory / "inference.log"}')
            finally:
                if process.poll() is None:
                    if sys.platform=='win32':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=20)
                    process.kill();process.wait(timeout=20)
        recognized=contract.read_json(result_file);words=recognized['words']
        contract.write_json(recognition_cache,recognized)
        result=match_words(cues,words)
        result.update(language=recognized['language'],recognized_words=words,model_revision=manifest['revision'],
            elapsed_seconds=round(time.monotonic()-started,3),cache_used=False,external_network_used=False,
            source_timestamps_unchanged=True,limitations=['ASR word timestamps are estimates, not forced alignment or guaranteed exact synchronization.'])
    except (ImportError,RuntimeError,OSError,ValueError) as exc:
        result=dict(status='unavailable',reason=str(exc)[:1000],cues=[],external_network_used=False,
            source_timestamps_unchanged=True,cue_level_timing_verified=False)
        print('VOICE: speech timing unavailable; original SRT timing retained.',flush=True)
    contract.write_json(cache,result)
    return result


def apply_timing(scenes,alignment,cues,fps=24):
    by_id={item['cue_id']:item for item in alignment.get('cues',[])}
    source={cue['id']:cue for cue in cues}
    for scene in scenes:
        if scene['engine']!='blender':continue
        beats=[]
        for cue_id in scene['params'].get('semantic_cues',scene['source_cues']):
            cue=source[cue_id];record=by_id.get(cue_id,{})
            for offset in record.get('action_beats',[]):
                position=cue['start']/1000+offset-scene['start_frame']/fps
                if 0<=position<(scene['end_frame']-scene['start_frame'])/fps:beats.append(round(position,3))
        scene['params']['speech_beats']=sorted(set(beats))[:32]
