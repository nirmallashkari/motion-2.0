"""Trusted speech inference worker with no networking and progress checkpoints."""
import os
from pathlib import Path
import sys
import time
import contract


def no_network(event,args):
    if event.startswith('socket.'):raise PermissionError('Speech inference is offline only.')


def main():
    task=contract.read_json(Path(sys.argv[1]))
    sys.addaudithook(no_network)
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    from faster_whisper import WhisperModel
    model=WhisperModel(task['model'],device='cpu',compute_type='int8',cpu_threads=6,num_workers=1,local_files_only=True)
    segments,info=model.transcribe(task['voice'],language=task['language'],beam_size=3,word_timestamps=True,
        vad_filter=True,condition_on_previous_text=False)
    words=[];started=time.monotonic()
    for segment in segments:
        words.extend(dict(word=word.word,start=word.start,end=word.end,probability=word.probability) for word in segment.words or [])
        contract.write_json(Path(task['progress']),dict(seconds_decoded=segment.end,words=len(words),elapsed_seconds=round(time.monotonic()-started,1)))
    contract.write_json(Path(task['result']),dict(words=words,language=info.language))


if __name__=='__main__':main()
