"""Decode a movie and detect long near-static holds before publication."""
from pathlib import Path
import subprocess
import time

from PIL import Image, ImageChops, ImageStat
import numpy as np

from quality_policy import MAX_HOLD_SECONDS, RULEBOOK_VERSION


def check_repeats(samples):
    """Compare decoded pictures at five equal relative positions in each shot."""
    duplicates=[];closest=None
    for index,(identity,frames) in enumerate(samples):
        current=np.stack([np.asarray(frame,dtype=np.float32) for frame in frames])
        for other,prior in samples[:index]:
            previous=np.stack([np.asarray(frame,dtype=np.float32) for frame in prior])
            distances=np.abs(current-previous).mean(axis=(1,2))
            distance=float(distances.mean())
            if closest is None or distance<closest['mean_difference']:
                closest=dict(first=other,second=identity,mean_difference=round(distance,4))
            # Require every sampled position to match, not one transition frame.
            if float(distances.max())<=.65:
                duplicates.append(dict(first=other,second=identity,mean_difference=round(distance,4)))
    return dict(status='failed' if duplicates else 'passed',duplicates=duplicates,closest_pair=closest,
        sampled_shots=len(samples),samples_per_shot=5,
        method='Five normalized-time decoded grayscale frames; each mean pixel difference <=0.65/255 marks a repeat.',
        limitations=['Heuristic detects identical or very close pictures, not every semantic repetition.',
                     'Camera or composition changes may pass; character identity can remain consistent.'])


def check_motion(path, project, tools, log):
    command = [tools["ffmpeg"], "-v", "error", "-i", str(path), "-an",
               "-vf", "scale=160:90:flags=area,format=gray", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    scene_reports, failures, samples = [], [], []
    line_mode=any(scene.get('params',{}).get('line_mode') for scene in project['scenes'])
    started = last_print = time.monotonic()
    with Path(log).open("ab") as stream:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=stream)
        try:
            for scene in project["scenes"]:
                previous = None
                longest = current = 0
                count=scene['end_frame']-scene['start_frame']
                positions=[scene['start_frame']+min(count-1,int(count*q)) for q in (.1,.3,.5,.7,.9)]
                sampled={}
                for frame in range(scene["start_frame"], scene["end_frame"]):
                    data = process.stdout.read(160*90)
                    if len(data) != 160*90:
                        raise ValueError("R04: Incomplete decode during motion quality check")
                    image = Image.frombytes("L", (160,90), data)
                    if line_mode and frame in positions:sampled[frame]=image
                    mean = ImageStat.Stat(ImageChops.difference(image, previous)).mean[0] if previous else 255
                    current = current+1 if mean <= .08 else 0
                    longest = max(current, longest)
                    previous = image
                    now = time.monotonic()
                    if now-last_print > 5:
                        print(f"Checking visual motion: frame {frame+1}/{project['total_frames']}", flush=True)
                        last_print = now
                seconds = longest / project["canvas"]["fps"]
                if line_mode:samples.append((scene['id'],[sampled[position] for position in positions]))
                scene_reports.append(dict(id=scene["id"], longest_near_static_seconds=round(seconds,3)))
                if seconds > MAX_HOLD_SECONDS:
                    failures.append(f"R04: {scene['id']} has a {seconds:.2f}s near-static hold; limit {MAX_HOLD_SECONDS:g}s")
            process.stdout.close()
            if process.wait(timeout=60):
                raise ValueError("Motion quality decoder failed")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=20)
    repeat=check_repeats(samples) if line_mode else dict(status='not_applicable',reason='Legacy package without line-mode policy.')
    failures.extend(f"R17: {pair['second']} visually repeats {pair['first']}; create a different source-related shot."
                    for pair in repeat.get('duplicates',[]))
    return dict(rulebook_version=RULEBOOK_VERSION, status="failed" if failures else "passed",no_repeat=repeat,
                method="160x90 grayscale, adjacent-frame mean difference <=0.08/255",
                limitations=["Heuristic: subtle purposeful movement can be flagged; decorative movement can evade detection.",
                             "Passing does not prove visual storytelling, citation truth or word-level audio sync."],
                failures=failures, scenes=scene_reports, elapsed_seconds=round(time.monotonic()-started,3))
