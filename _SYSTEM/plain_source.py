"""Build an estimated local timeline for plain text without changing the input."""
from difflib import SequenceMatcher
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

import contract

REVISION='plain-source-2.0'


def sections(text,line_mode=True):
    """Keep source words and punctuation in order, with bounded shot length."""
    if line_mode:
        return [line.strip() for line in text.splitlines() if line.strip()]
    output=[]
    for sentence in re.split(r'(?<=[.!?।])\s+|\n\s*\n',text.strip()):
        words=sentence.split()
        count=max(1,math.ceil(len(words)/18))
        for number in range(count):
            start=round(len(words)*number/count);end=round(len(words)*(number+1)/count)
            output.append(' '.join(words[start:end]))
    return [part for part in output if part]


def key(word):
    if any('\u0900'<=c<='\u097f' for c in word):
        from indic_transliteration import sanscript
        word=sanscript.transliterate(word,sanscript.DEVANAGARI,sanscript.ITRANS)
    word=unicodedata.normalize('NFKC',word).lower()
    word=re.sub(r'[^a-z0-9]','',word)
    for old,new in (('sh','s'),('ch','c'),('ph','f'),('bh','b'),('th','t'),('dh','d'),('kh','k'),('gh','g')):
        word=word.replace(old,new)
    # Roman Hindi spelling and ASR Devanagari differ in vowels and schwa.
    consonants=re.sub(r'[aeiou]','',word)
    return consonants or word


def estimated_cues(text,seconds,words,line_mode=True):
    parts=sections(text,line_mode=line_mode)
    if not parts or len(parts)>300:raise ValueError('Plain source must contain 1-300 narration sections.')
    source=[];owners=[]
    for number,part in enumerate(parts):
        for word in part.split():source.append(key(word));owners.append(number)
    recognized=[];times=[]
    for word in words:
        for token in word['word'].split():
            recognized.append(key(token));times.append(float(word['start']))
    matches={}
    for block in SequenceMatcher(None,source,recognized,autojunk=False).get_matching_blocks():
        for offset in range(block.size):matches[block.a+offset]=block.b+offset
    coverage=len(matches)/max(1,len(source))
    # A sparse match cannot justify moving the complete script to a short ASR
    # fragment. Retain a clearly labelled proportional estimate in that case.
    anchors={0:0.0,len(source):seconds}
    if coverage>=.35:
        for index,recognized_index in matches.items():
            position=times[recognized_index]
            if index and 0<position<seconds:anchors[index]=position
    points=sorted(anchors)
    boundaries=[0];offset=0
    for part in parts[:-1]:
        offset+=len(part.split())
        left=max(p for p in points if p<=offset);right=min(p for p in points if p>=offset)
        position=anchors[left] if left==right else anchors[left]+(anchors[right]-anchors[left])*(offset-left)/(right-left)
        boundaries.append(round(position*1000))
    boundaries.append(round(seconds*1000))
    if any(b-a<100 for a,b in zip(boundaries,boundaries[1:])):
        # Degenerate word timestamps cannot produce zero-duration source cues.
        total=sum(len(part.split()) for part in parts);offset=0;boundaries=[0]
        for part in parts:
            offset+=len(part.split());boundaries.append(round(seconds*1000*offset/total))
        coverage=0.0
    cues=[dict(id=i+1,start=boundaries[i],end=boundaries[i+1],text=part) for i,part in enumerate(parts)]
    return cues,dict(method='phonetic_asr_anchors' if coverage>=.35 else 'proportional_estimate',
        matched_word_fraction=round(coverage,3),exact_sync_verified=False,source_unit='nonempty_authored_line' if line_mode else 'estimated_section',
        source_line_count=len(parts),
        limitations=['Plain-text timing is estimated. Phonetic Roman Hindi matching is heuristic; original script and audio are unchanged.'])


def timestamp(ms):
    hours,rest=divmod(ms,3600000);minutes,rest=divmod(rest,60000);seconds,milli=divmod(rest,1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{milli:03}'


def prepare(workspace,source,voice):
    if voice is None:raise ValueError('Plain script needs one voiceover file to estimate its timeline.')
    import motion
    from voice_alignment import align
    text=source.read_text(encoding='utf-8-sig').strip()
    tools=motion.tools_for(dict(scenes=[dict(engine='python')]))
    seconds=float(motion.probe(voice,tools)['format']['duration'])
    if not .1<=seconds<=4500:raise ValueError('Voice duration is outside the supported range.')
    identity=hashlib.sha256((REVISION+contract.sha(Path(__file__))+contract.sha(source)+contract.sha(voice)).encode()).hexdigest()
    reviewed=None
    audit_path=Path(workspace)/'OUTPUT/AUDIO_SCAN/audio_scan.json'
    words_path=Path(workspace)/'OUTPUT/AUDIO_SCAN/word_timing.json'
    if audit_path.is_file() and words_path.is_file():
        audit=contract.read_json(audit_path)
        if audit.get('files',{}).get('script_sha256')==contract.sha(source) and audit.get('files',{}).get('voice_sha256')==contract.sha(voice):
            reviewed=contract.read_json(words_path).get('words',[])
            if len(reviewed)>10000 or any(not 0<=w['start']<=w['end']<=seconds+.1 for w in reviewed):
                raise ValueError('Reviewed word timing is invalid for this voice')
            identity=hashlib.sha256((identity+contract.sha(words_path)).encode()).hexdigest()
    folder=Path(workspace)/'_SYSTEM/work/plain_source'/identity
    timed=folder/'source.srt';report=folder/'timing_report.json'
    if timed.is_file() and report.is_file() and contract.read_json(report).get('timed_source_sha256')==contract.sha(timed):
        contract.write_json(Path(workspace)/'OUTPUT/SOURCE_TIMING.json',contract.read_json(report))
        return timed,contract.parse_srt(timed)
    print('SOURCE: plain text detected; estimating narration sections using local speech timing.',flush=True)
    result=(dict(status='hash_bound_reviewed_asr_reused') if reviewed is not None else
        align(workspace,voice,[dict(id=1,start=0,end=round(seconds*1000),text=text)]))
    cues,evidence=estimated_cues(text,seconds,reviewed if reviewed is not None else result.get('recognized_words',[]))
    evidence['reviewed_asr_reused']=reviewed is not None
    folder.mkdir(parents=True,exist_ok=True)
    timed.write_text('\n\n'.join(f"{cue['id']}\n{timestamp(cue['start'])} --> {timestamp(cue['end'])}\n{cue['text']}" for cue in cues)+'\n',encoding='utf-8')
    evidence.update(revision=REVISION,input_source_path=str(source.resolve()),input_source_sha256=contract.sha(source),
        voice_sha256=contract.sha(voice),voice_seconds=seconds,timed_source_sha256=contract.sha(timed),
        sections=len(cues),speech_status=result['status'])
    contract.write_json(report,evidence)
    contract.write_json(Path(workspace)/'OUTPUT/SOURCE_TIMING.json',evidence)
    print(f"SOURCE: {len(cues)} sections, {seconds:.3f}s, {evidence['method']}; exact sync is not certified.",flush=True)
    return timed,cues
