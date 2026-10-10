"""Tests for enforceable storytelling rules, distinct from artistic judgment."""
import copy
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import contract
from quality_policy import TextGuard, validate_plan, check_labels, words


class StorytellingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=contract.SYSTEM / "reports",prefix="rules_test_")
        self.package = Path(self.temporary.name) / "return"
        shutil.copytree(contract.SYSTEM / "framework/example_return",self.package)
        self.project,self.cues,_ = contract.validate_package(self.package)
        self.plan = contract.read_json(self.package / "creative_plan.json")

    def tearDown(self):
        self.temporary.cleanup()

    def test_missing_plan_rejected(self):
        (self.package / "creative_plan.json").unlink()
        with self.assertRaisesRegex(ValueError,"creative_plan"):
            contract.validate_package(self.package)

    def test_wrong_rule_version_rejected(self):
        self.plan["rulebook_version"] = "relaxed"
        with self.assertRaises(Exception):
            validate_plan(self.plan,self.project,self.cues)

    def test_label_paragraph_rejected(self):
        self.plan["scenes"][0]["beats"][0]["on_screen_text"] = ["This is a full sentence with too many words"]
        with self.assertRaisesRegex(ValueError,"R05"):
            validate_plan(self.plan,self.project,self.cues)

    def test_frame_word_budget_rejected(self):
        with self.assertRaisesRegex(ValueError,"12 visible|12 words"):
            check_labels(["one two three four five", "six seven eight nine ten", "eleven twelve thirteen"])

    def test_hindi_combining_marks_do_not_split_words(self):
        label = "हर सुबह नेगोशिएट करते हैं"
        self.assertEqual(len(words(label)), 5)
        check_labels([label])

    def test_hindi_actual_long_label_still_rejected(self):
        with self.assertRaisesRegex(ValueError, "R05"):
            check_labels(["आज ही अपनी नई आदत शुरू करो"])

    def test_too_many_labels_rejected(self):
        with self.assertRaises(ValueError):
            check_labels(["one","two","three","four"])

    def test_long_beat_rejected(self):
        self.project["scenes"][0]["end_frame"] = 96
        self.plan["scenes"][0]["beats"][0]["end_frame"] = 96
        with self.assertRaisesRegex(ValueError,"R04"):
            validate_plan(self.plan,self.project,self.cues)

    def test_plan_scene_order_rejected(self):
        self.plan["scenes"].reverse()
        with self.assertRaisesRegex(ValueError,"R02"):
            validate_plan(self.plan,self.project,self.cues)

    def test_text_cards_as_only_objects_rejected(self):
        self.plan["scenes"][0]["main_objects"] = ["cards","heading"]
        with self.assertRaisesRegex(ValueError,"R01"):
            validate_plan(self.plan,self.project,self.cues)

    def test_scene_with_no_action_rejected(self):
        self.plan["scenes"][0]["beats"][0]["kind"] = "hold"
        with self.assertRaisesRegex(ValueError,"R01/R02"):
            validate_plan(self.plan,self.project,self.cues)

    def test_plan_gap_rejected(self):
        self.plan["scenes"][0]["beats"][0]["start_frame"] = 1
        with self.assertRaisesRegex(ValueError,"R02"):
            validate_plan(self.plan,self.project,self.cues)

    def test_percentage_absent_from_source_rejected(self):
        self.plan["scenes"][0]["claims"] = [dict(text="99% success",basis="source_only",
            source_cues=[1],evidence="Start small.")]
        with self.assertRaisesRegex(ValueError,"R06"):
            validate_plan(self.plan,self.project,self.cues)

    def test_unsourced_percentage_label_rejected(self):
        self.plan["scenes"][0]["beats"][0]["on_screen_text"] = ["SUCCESS 99%"]
        with self.assertRaisesRegex(ValueError,"R06"):
            validate_plan(self.plan,self.project,self.cues)

    def test_wrong_source_quote_rejected(self):
        self.plan["scenes"][0]["claims"] = [dict(text="Start small",basis="source_only",
            source_cues=[1],evidence="Something the user did not say")]
        with self.assertRaisesRegex(ValueError,"R06"):
            validate_plan(self.plan,self.project,self.cues)

    def test_missing_reference_rejected(self):
        self.plan["scenes"][0]["claims"] = [dict(text="99% success",basis="verified_reference",
            source_cues=[],evidence="nonexistent")]
        with self.assertRaisesRegex(ValueError,"R06"):
            validate_plan(self.plan,self.project,self.cues)

    def test_false_reference_verification_rejected(self):
        self.plan["references"] = [dict(id="source",url="https://example.com",title="Example",
            excerpt="An excerpt",verified_by_ai=False)]
        with self.assertRaises(Exception):
            validate_plan(self.plan,self.project,self.cues)

    def guard(self,labels):
        planned = dict(beats=[dict(start_frame=0,end_frame=24,on_screen_text=labels)],claims=[])
        guard = TextGuard(planned,"Start small.",(640,360))
        guard.install()
        guard.reset(0)
        return guard,ImageDraw.Draw(Image.new("RGB",(640,360)))

    def restore(self,guard):
        ImageDraw.ImageDraw.text = guard.original

    def test_live_text_overlap_rejected(self):
        guard,draw = self.guard(["FIRST","SECOND"])
        try:
            draw.text((100,100),"FIRST",font=ImageFont.load_default(size=30))
            draw.text((110,100),"SECOND",font=ImageFont.load_default(size=30))
            with self.assertRaisesRegex(ValueError,"overlap"):
                guard.finish()
        finally:
            self.restore(guard)

    def test_live_off_canvas_text_rejected(self):
        guard,draw = self.guard(["FIRST"])
        try:
            draw.text((-20,100),"FIRST",font=ImageFont.load_default(size=30))
            with self.assertRaisesRegex(ValueError,"outside"):
                guard.finish()
        finally:
            self.restore(guard)

    def test_live_good_labels_pass(self):
        guard,draw = self.guard(["START SMALL"])
        try:
            draw.text((100,100),"START SMALL",font=ImageFont.load_default(size=30))
            guard.finish()
        finally:
            self.restore(guard)

    def test_live_long_label_rejected(self):
        guard,draw = self.guard(["SHORT LABEL"])
        try:
            draw.text((100,100),"This sentence contains far too many words")
            with self.assertRaisesRegex(ValueError,"R05"):
                guard.finish()
        finally:
            self.restore(guard)


if __name__ == "__main__":
    unittest.main()
