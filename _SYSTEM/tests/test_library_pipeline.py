"""Bounded narration tails and registered-library source preservation."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
import library_pipeline as library
import motion


class LibraryTests(unittest.TestCase):
    def test_full_narration_rounds_up_without_cutting_source(self):
        self.assertEqual(library.tail_frames(155,155.715875),18)
        self.assertGreaterEqual((3720+18)/24,155.715875)
        self.assertEqual(library.tail_frames(155,155.1),0)
        self.assertEqual(library.tail_frames(155,None),0)

    def test_large_or_earlier_audio_mismatch_rejected(self):
        for duration in (153,156.01):
            with self.assertRaisesRegex(ValueError,"mismatch"):
                library.tail_frames(155,duration)

    def test_unknown_narration_cannot_become_unrelated_slide(self):
        with self.assertRaisesRegex(ValueError,"cannot illustrate"):
            library.recognize(dict(id=1,text="Describe a volcano eruption."))

    def test_actual_source_routes_phone_and_idiom_correctly(self):
        self.assertEqual(library.recognize(dict(id=1,text="उसे दूसरे कमरे में रखो।"))[0],"phone_away")
        self.assertEqual(library.recognize(dict(id=1,text="आगे बढ़ना बच्चों का खेल बन जाता है।"))[0],"momentum")

    def test_package_preserves_bytes_and_tail_requires_audio(self):
        with tempfile.TemporaryDirectory(dir=contract.SYSTEM/"reports") as temporary:
            root=Path(temporary)
            source=root/"input.srt"
            raw="1\r\n00:00:00,000 --> 00:00:03,000\r\nPut the phone in another room.\r\n".encode()
            source.write_bytes(raw)
            cues=contract.parse_srt(source)
            package=root/"package"
            project=library.create_package(package,source,cues,[library.recognize(cues[0])],["wide"],18)
            self.assertEqual((package/"source.srt").read_bytes(),raw)
            self.assertEqual(project["total_frames"],90)
            self.assertEqual(project["caption_mode"],"off")
            workspace=root/"workspace"
            (workspace/"_SYSTEM/work").mkdir(parents=True)
            (workspace/"OUTPUT").mkdir()
            with patch.object(motion,"tools_for",return_value={}):
                with self.assertRaisesRegex(ValueError,"requires.*voiceover"):
                    motion.execute(workspace,selection=(package,source,None))
            project["narration_tail_frames"]=25
            contract.write_json(package/"project.json",project)
            with self.assertRaisesRegex(ValueError,"at most one second"):
                contract.validate_package(package,source)


if __name__=="__main__":
    unittest.main()
