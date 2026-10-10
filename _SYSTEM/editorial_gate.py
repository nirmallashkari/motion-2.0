"""Block observed unsupported-coverage failures before expensive rendering."""
from pathlib import Path
import contract

REVISION='editorial-coverage-1.0'
MAX_ABSTRACT_FRACTION=.15
MAX_ABSTRACT_RUN_SECONDS=3.0


def inspect(project):
    fps=project['canvas']['fps']
    abstract_frames=0;run=0;longest=0;unknown=[]
    for scene in project['scenes']:
        count=scene['end_frame']-scene['start_frame']
        abstract=scene['engine']=='python' and scene['id'].startswith('abstract_story__')
        if abstract:
            abstract_frames+=count;run+=count;longest=max(longest,run)
            unknown.extend(scene['params'].get('semantic_cues',scene['source_cues']))
        else:run=0
    fraction=abstract_frames/max(1,project['total_frames'])
    failures=[]
    if fraction>MAX_ABSTRACT_FRACTION:
        failures.append('Unsupported abstract scenes exceed 15 percent of video duration.')
    if longest/fps>MAX_ABSTRACT_RUN_SECONDS:
        failures.append('Consecutive unsupported abstract coverage exceeds three seconds.')
    return dict(revision=REVISION,status='blocked' if failures else 'coverage_passed',
        abstract_duration_fraction=round(fraction,4),longest_abstract_run_seconds=round(longest/fps,3),
        unsupported_cues=sorted(set(unknown)),failures=failures,
        limits=dict(max_abstract_fraction=MAX_ABSTRACT_FRACTION,max_abstract_run_seconds=MAX_ABSTRACT_RUN_SECONDS),
        limitations=['Coverage checks do not certify narrative understanding, natural acting or artistic quality.'])


def enforce(workspace,project,evidence):
    review=inspect(project)
    contract.write_json(Path(evidence)/'editorial_gate.json',review)
    contract.write_json(Path(workspace)/'OUTPUT/EDITORIAL_GATE.json',review)
    if review['failures']:
        raise ValueError('Editorial coverage failed before rendering: '+ '; '.join(review['failures'])+
            ' Extend source-related visual coverage; do not publish a repeated generic fallback movie.')
    return review
