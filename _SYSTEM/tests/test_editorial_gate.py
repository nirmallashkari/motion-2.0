"""Coverage regression tests for the rejected repetitive motivational output."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from editorial_gate import inspect, enforce


def project(parts):
    start=0;scenes=[]
    for number,(kind,seconds) in enumerate(parts,1):
        count=round(seconds*24)
        scenes.append(dict(id=('abstract_story__' if kind=='abstract' else 'asset_motion__')+str(number),
            engine='python',start_frame=start,end_frame=start+count,source_cues=[number],params={}))
        start+=count
    return dict(canvas=dict(fps=24),total_frames=start,scenes=scenes)


class EditorialGateTests(unittest.TestCase):
    def test_short_declared_transition_can_pass(self):
        self.assertEqual(inspect(project([('literal',9),('abstract',1)]))['status'],'coverage_passed')

    def test_low_scene_count_cannot_hide_long_unsupported_duration(self):
        result=inspect(project([('literal',1),('abstract',9)]))
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['abstract_duration_fraction'],.9)

    def test_separate_ids_cannot_hide_consecutive_fallback_run(self):
        result=inspect(project([('literal',60),('abstract',2),('abstract',2)]))
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['longest_abstract_run_seconds'],4)

    def test_block_records_evidence_and_preserves_previous_movie(self):
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/'reports') as folder:
            root=Path(folder);(root/'OUTPUT').mkdir()
            movie=root/'OUTPUT/final.mp4';movie.write_bytes(b'previous movie')
            with self.assertRaisesRegex(ValueError,'before rendering'):
                enforce(root,project([('abstract',10)]),root/'evidence')
            self.assertEqual(movie.read_bytes(),b'previous movie')
            self.assertEqual(contract.read_json(root/'OUTPUT/EDITORIAL_GATE.json')['status'],'blocked')


if __name__=='__main__':unittest.main()
