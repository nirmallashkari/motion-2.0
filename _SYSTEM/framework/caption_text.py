"""Dependency-free parsing of timed captions supplied as text or UTF-8 SRT."""
from pathlib import Path
import re


def stamp_ms(text):
    match = re.fullmatch(r"(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})", text)
    if not match:
        raise ValueError(f"Invalid SRT time: {text}")
    h, m, s, ms = map(int, match.groups())
    if m > 59 or s > 59:
        raise ValueError(f"Invalid SRT minute/second: {text}")
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def parse_srt_text(text):
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").strip()
    cues = []
    for block in re.split(r"\n[ \t]*\n", text):
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].isdigit():
            raise ValueError("SRT blocks need a cue number, timestamp and text.")
        bounds = re.fullmatch(r"(\d{2,}:\d{2}:\d{2}[,.]\d{3})\s+-->\s+(\d{2,}:\d{2}:\d{2}[,.]\d{3})", lines[1])
        if not bounds:
            raise ValueError(f"Cue {lines[0]}: malformed timestamp line.")
        start, end = map(stamp_ms, bounds.groups())
        cue = {"id": int(lines[0]), "start": start, "end": end, "text": "\n".join(lines[2:])}
        if cue["id"] < 1 or end <= start or not cue["text"].strip():
            raise ValueError(f"Cue {lines[0]}: invalid ID, interval or empty text.")
        if cues and (cue["id"] in {c["id"] for c in cues} or start < cues[-1]["end"]):
            raise ValueError(f"Cue {lines[0]}: duplicate ID, out-of-order cue or overlapping interval.")
        cues.append(cue)
    if not 1 <= len(cues) <= 1500 or cues[-1]["end"] > 3600000:
        raise ValueError("SRT supports 1–1500 cues and a maximum timeline of one hour.")
    return cues


def parse_srt(path):
    return parse_srt_text(Path(path).read_text(encoding="utf-8-sig"))
