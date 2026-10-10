"""Pinned storytelling rules, package planning checks and live text safeguards."""
from __future__ import annotations

import re
import unicodedata

RULEBOOK_VERSION = "1.0"
MAX_LABEL_WORDS = 5
MAX_FRAME_WORDS = 12
MAX_LABELS = 3
MAX_HOLD_SECONDS = 3.0

QUALITY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object", "additionalProperties": False,
    "required": ["rulebook_version", "scenes", "references"],
    "properties": {
        "rulebook_version": {"const": RULEBOOK_VERSION},
        "references": {"type": "array", "maxItems": 200, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "url", "title", "excerpt", "verified_by_ai"],
            "properties": {"id": {"type": "string", "minLength": 1},
                "url": {"type": "string", "pattern": "^https://"},
                "title": {"type": "string", "minLength": 1}, "excerpt": {"type": "string", "minLength": 1},
                "verified_by_ai": {"const": True}}}},
        "scenes": {"type": "array", "minItems": 1, "maxItems": 300, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["id", "visual_goal", "main_objects", "beats", "claims"],
            "properties": {
                "id": {"type": "string"}, "visual_goal": {"type": "string", "minLength": 20},
                "main_objects": {"type": "array", "minItems": 1, "maxItems": 8,
                    "uniqueItems": True, "items": {"type": "string", "minLength": 1, "maxLength": 100}},
                "beats": {"type": "array", "minItems": 1, "maxItems": 1000, "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["start_frame", "end_frame", "kind", "action", "on_screen_text"],
                    "properties": {"start_frame": {"type": "integer", "minimum": 0},
                        "end_frame": {"type": "integer", "minimum": 1},
                        "kind": {"enum": ["object_action", "object_reveal", "camera_move", "state_change", "visual_comparison", "hold"]},
                        "action": {"type": "string", "minLength": 20, "maxLength": 2000},
                        "on_screen_text": {"type": "array", "maxItems": MAX_LABELS, "uniqueItems": True,
                            "items": {"type": "string", "minLength": 1, "maxLength": 120}}}}},
                "claims": {"type": "array", "maxItems": 100, "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["text", "basis", "source_cues", "evidence"],
                    "properties": {"text": {"type": "string", "minLength": 1},
                        "basis": {"enum": ["source_only", "verified_reference", "illustrative"]},
                        "source_cues": {"type": "array", "uniqueItems": True, "items": {"type": "integer", "minimum": 1}},
                        "evidence": {"type": "string", "minLength": 1}}}}
            }}}
    }
}


def words(text):
    # Python's regex \w excludes combining marks, including Hindi vowel signs.
    # Removing those marks only for counting keeps one written word contiguous.
    counted = "".join(char for char in str(text) if not unicodedata.category(char).startswith("M"))
    return re.findall(r"\b[\w]+(?:['’-][\w]+)*\b", counted, re.UNICODE)


def percentages(text):
    return set(re.findall(r"\d+(?:\.\d+)?\s*%", text))


def normalize(text):
    return " ".join(text.split())


def check_labels(labels, maximum=MAX_FRAME_WORDS):
    if len(labels) > MAX_LABELS:
        raise ValueError(f"R05: At most {MAX_LABELS} visible labels, not a text slide")
    for label in labels:
        if len(words(label)) > MAX_LABEL_WORDS:
            raise ValueError(f"R05: Label exceeds {MAX_LABEL_WORDS} words: {label!r}")
        if len(label.splitlines()) > 2:
            raise ValueError("R05: Labels may occupy at most two lines")
    if sum(len(words(label)) for label in labels) > maximum:
        raise ValueError(f"R05: Visible text exceeds {maximum} words")


def validate_plan(plan, project, cues):
    from jsonschema import Draft202012Validator
    Draft202012Validator(QUALITY_SCHEMA).validate(plan)
    if [s["id"] for s in plan["scenes"]] != [s["id"] for s in project["scenes"]]:
        raise ValueError("R02: creative_plan scenes must match project scenes exactly, in order")
    references = {item["id"]: item for item in plan["references"]}
    if len(references) != len(plan["references"]):
        raise ValueError("R06: Duplicate reference ID")
    by_cue = {c["id"]: c for c in cues}
    label_objects = {"text", "card", "cards", "panel", "panels", "heading", "title", "label", "labels", "badge", "paragraph"}
    for planned, scene in zip(plan["scenes"], project["scenes"]):
        if all(obj.casefold().strip() in label_objects for obj in planned["main_objects"]):
            raise ValueError(f"R01: {scene['id']} must illustrate meaning with an object/action")
        position = scene["start_frame"]
        action_seen = False
        for beat in planned["beats"]:
            if beat["start_frame"] != position or beat["end_frame"] <= position:
                raise ValueError(f"R02: {scene['id']} beats must be contiguous and positive")
            if beat["end_frame"] - position > MAX_HOLD_SECONDS * project["canvas"]["fps"]:
                raise ValueError(f"R04: {scene['id']} needs a meaningful beat at least every {MAX_HOLD_SECONDS:g}s")
            check_labels(beat["on_screen_text"])
            action_seen |= beat["kind"] != "hold"
            position = beat["end_frame"]
        if position != scene["end_frame"] or not action_seen:
            raise ValueError(f"R01/R02: {scene['id']} must cover its whole interval and include visible action")
        for claim in planned["claims"]:
            if any(c not in scene["source_cues"] for c in claim["source_cues"]):
                raise ValueError("R06: Claim source cues must belong to its scene")
            if claim["basis"] == "source_only":
                text = normalize(" ".join(by_cue[c]["text"] for c in claim["source_cues"]))
                if not claim["source_cues"] or normalize(claim["evidence"]) not in text:
                    raise ValueError("R06: Source-only evidence must quote the actual scene source")
                if percentages(claim["text"]) - percentages(text):
                    raise ValueError("R06: Percentage claim is absent from the supplied source")
            elif claim["basis"] == "verified_reference" and claim["evidence"] not in references:
                raise ValueError("R06: Claim must cite a provided, AI-verified reference ID")
        source_text = " ".join(by_cue[c]["text"] for c in scene["source_cues"])
        for beat in planned["beats"]:
            check_percentages(beat["on_screen_text"], planned, source_text)
    return plan


def check_percentages(labels, planned, source_text):
    for label in labels:
        for number in percentages(label) - percentages(source_text):
            supporting = [c for c in planned["claims"] if number in percentages(c["text"])]
            sourced = any(c["basis"] == "verified_reference" for c in supporting)
            illustration = any(c["basis"] == "illustrative" for c in supporting) and any(
                "ILLUSTRATION" in item.upper() or "ILLUSTRATIVE" in item.upper() for item in labels)
            if not sourced and not illustration:
                raise ValueError(f"R06: Unsourced percentage {number}; do not invent success/failure statistics")


class TextGuard:
    """Observe ordinary Pillow text calls while the trusted worker draws a frame."""
    def __init__(self, planned, source_text, size):
        self.planned, self.source_text, self.size = planned, source_text, size
        self.records = []
        self.frame = 0
        self.original = None

    def reset(self, global_frame):
        self.frame, self.records = global_frame, []

    def install(self):
        from PIL import ImageDraw
        self.original = ImageDraw.ImageDraw.text
        guard = self
        original = self.original

        def guarded(draw, xy, text, *args, **kwargs):
            font = kwargs.get("font", args[1] if len(args) > 1 else None)
            color = kwargs.get("fill", args[0] if args else None)
            if isinstance(color, tuple) and len(color) == 4 and color[3] == 0:
                return original(draw, xy, text, *args, **kwargs)
            bbox_args = {key: kwargs[key] for key in
                         ("anchor", "spacing", "align", "direction", "features", "language", "stroke_width", "embedded_color")
                         if key in kwargs}
            box = draw.textbbox(xy, text, font=font, **bbox_args)
            if str(text).strip() and "\n" not in str(text):
                guard.records.append((str(text), box))
            return original(draw, xy, text, *args, **kwargs)

        ImageDraw.ImageDraw.text = guarded

    def finish(self):
        unique = []
        for record in self.records:
            if record not in unique:
                unique.append(record)
        labels = [r[0] for r in unique]
        check_labels(labels)
        check_percentages(labels, self.planned, self.source_text)
        beat = next(b for b in self.planned["beats"] if b["start_frame"] <= self.frame < b["end_frame"])
        declared_lines = [line for label in beat["on_screen_text"] for line in label.splitlines()]
        if any(label not in declared_lines for label in labels):
            raise ValueError("R02/R05: Rendered text is absent from this beat's declared on_screen_text")
        width, height = self.size
        for index, (_, box) in enumerate(unique):
            if box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height:
                raise ValueError("R07: Visible text falls outside the canvas")
            for _, other in unique[:index]:
                if min(box[2],other[2]) > max(box[0],other[0]) and min(box[3],other[3]) > max(box[1],other[1]):
                    raise ValueError("R07: Visible text labels overlap")


def check_blender_text(planned, source_text, objects, frame):
    labels = [obj.data.body for obj in objects if obj.type == "FONT" and not obj.hide_render and obj.data.body.strip()]
    check_labels(labels)
    check_percentages(labels, planned, source_text)
    beat = next(b for b in planned["beats"] if b["start_frame"] <= frame < b["end_frame"])
    if any(label not in beat["on_screen_text"] for label in labels):
        raise ValueError("R02/R05: Blender text is absent from the declared beat")
