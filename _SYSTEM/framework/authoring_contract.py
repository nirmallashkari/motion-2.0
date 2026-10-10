"""Unified, file-only authoring contract for Motion 2.0."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import time
import zipfile

from jsonschema import Draft202012Validator

SYSTEM = Path(__file__).resolve().parent
FRAMEWORK = SYSTEM / "framework" if (SYSTEM / "framework/project.schema.json").is_file() else SYSTEM
PYTHON_ENGINE = SYSTEM / "engines/python"
if (PYTHON_ENGINE / "EXTERNAL_AI_FRAMEWORK").is_dir():
    sys.path.insert(0, str(PYTHON_ENGINE / "EXTERNAL_AI_FRAMEWORK"))
from caption_text import parse_srt
from code_policy import validate_code
from quality_policy import RULEBOOK_VERSION, validate_plan

VERSION = "motion-unified-2.0"
MAX_BYTES = 512 * 1024**2
MAX_FILES = 3000
AUDIO_SUFFIXES = (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg")


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject(value):
        raise ValueError(f"Non-finite JSON: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique, parse_constant=reject)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024**2), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                         encoding="utf-8")
    for attempt in range(20):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.02)


def no_links(path, base):
    path, base = Path(path).absolute(), Path(base).absolute()
    if not path.is_relative_to(base):
        raise ValueError(f"Path escaped its boundary: {path}")
    for current in (path, *path.parents):
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError(f"Links/junctions are not supported: {current}")
        if current == base:
            break
    return path


def safe_path(base, relative):
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError(f"Use a plain package-relative forward-slash path: {relative}")
    name = PurePosixPath(relative)
    if name.is_absolute() or any(part in ("..", ".", "") for part in relative.split("/")):
        raise ValueError(f"Unsafe package path: {relative}")
    for part in name.parts:
        stem = part.split(".")[0].upper()
        if part.endswith((" ", ".")) or stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
            raise ValueError(f"Unsupported Windows filename: {relative}")
        if any(char in part for char in '<>"|?*'):
            raise ValueError(f"Unsupported Windows filename: {relative}")
    return no_links(Path(base) / name, base)


def package_files(base):
    base = no_links(base, base)
    files, total = [], 0
    stack = [base]
    while stack:
        for item in stack.pop().iterdir():
            no_links(item, base)
            if item.is_dir():
                stack.append(item)
            elif item.is_file():
                safe_path(base, item.relative_to(base).as_posix())
                files.append(item)
                total += item.stat().st_size
                if len(files) > MAX_FILES or total > MAX_BYTES:
                    raise ValueError("Package exceeds 3000 files / 512 MB")
            else:
                raise ValueError(f"Unsupported filesystem entry: {item}")
    names = [p.relative_to(base).as_posix().casefold() for p in files]
    if len(names) != len(set(names)):
        raise ValueError("Case-insensitive duplicate package paths")
    return sorted(files)


def extract_zip(archive, target):
    """Validate all members before writing any; never call extractall."""
    if archive.stat().st_size > MAX_BYTES:
        raise ValueError("ZIP exceeds 512 MB")
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError("Expanded ZIP exceeds 3000 entries / 512 MB")
        seen = set()
        for info in infos:
            relative = info.filename.rstrip("/")
            safe_path(target, relative)
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or info.flag_bits & 1:
                raise ValueError("ZIP links/encrypted entries are not supported")
            if relative.casefold() in seen:
                raise ValueError("Duplicate ZIP path")
            seen.add(relative.casefold())
        for info in infos:
            path = safe_path(target, info.filename.rstrip("/"))
            if info.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                count = 0
                with bundle.open(info) as source, path.open("wb") as destination:
                    for block in iter(lambda: source.read(1024**2), b""):
                        count += len(block)
                        if count > info.file_size:
                            raise ValueError("ZIP member exceeds declared size")
                        destination.write(block)
                if count != info.file_size:
                    raise ValueError("Truncated ZIP member")


def entry_signature(tree, name, arguments):
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if len({n.name for n in functions}) != len(functions):
        raise ValueError("Duplicate top-level functions")
    node = next((n for n in functions if n.name == name), None)
    if node is None:
        raise ValueError(f"Missing top-level function {name}")
    args = node.args
    if ([a.arg for a in args.args] != arguments or args.posonlyargs or args.defaults
            or args.vararg or args.kwarg or args.kwonlyargs):
        raise ValueError(f"{name} must have signature ({', '.join(arguments)})")


def blender_code(source):
    """A conservative authoring policy, not a security sandbox."""
    tree = ast.parse(source)
    allowed = {"bpy", "math", "mathutils", "random", "blender_sdk"}
    forbidden = {"open", "exec", "eval", "compile", "__import__", "getattr", "setattr", "delattr",
                 "globals", "locals", "vars", "input", "breakpoint"}
    blocked_attrs = {"save_as_mainfile", "open_mainfile", "read_factory_settings", "render",
                     "filepath", "handlers", "timers", "driver_namespace", "driver_add",
                     "load", "write", "save", "remove", "unlink", "mkdir", "rmdir"}
    for node in tree.body:
        if not isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.AnnAssign)) and not (
                isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            raise ValueError("Blender code may only declare imports, constants and functions at module level")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name not in allowed for a in node.names):
                raise ValueError("Unsupported Blender import")
        if isinstance(node, ast.ImportFrom):
            if node.level or node.module not in allowed or any(a.name.startswith("_") or a.name == "*" for a in node.names):
                raise ValueError("Unsupported Blender import")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in forbidden:
            raise ValueError(f"Unsupported Blender operation: {node.id}")
        if isinstance(node, ast.Attribute) and (node.attr.startswith("__") or node.attr in blocked_attrs):
            raise ValueError(f"Unsupported Blender attribute: {node.attr}")
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise ValueError("Blender decorators are not supported")
        if isinstance(node, (ast.AsyncFunctionDef, ast.Global, ast.Nonlocal)):
            raise ValueError("Unsupported Blender syntax")
    entry_signature(tree, "build", ["ctx", "spec"])
    return tree


def validate_package(package, original=None):
    package = Path(package).absolute()
    files = package_files(package)
    for name in ("project.json", "source.srt", "storyboard.md", "qa_report.json", "creative_plan.json"):
        if not (package / name).is_file():
            raise ValueError(f"Missing {name}. Supply a complete unified return.zip, not the framework ZIP.")
    project = read_json(package / "project.json")
    if project.get("format") != VERSION:
        raise ValueError("This is an older/separate engine package. Give AI the new MOTION_AI_FRAMEWORK.zip and request a unified return.")
    schema = read_json(FRAMEWORK / "project.schema.json")
    Draft202012Validator(schema).validate(project)
    cues = parse_srt(package / "source.srt")
    if original and cues != parse_srt(original):
        raise ValueError("Returned source.srt changes the supplied captions or timestamps")
    fps = project["canvas"]["fps"]
    if (project["canvas"]["width"], project["canvas"]["height"]) not in {(1280,720),(1920,1080),(720,1280),(1080,1920)}:
        raise ValueError("Use a supported landscape/portrait canvas")
    total = project["total_frames"]
    duration = cues[-1]["end"] / 1000
    tail = project.get("narration_tail_frames", 0)
    if tail > fps:
        raise ValueError("Narration closing animation may extend the source by at most one second")
    if total != (cues[-1]["end"] * fps + 500) // 1000 + tail:
        raise ValueError("total_frames must equal rounded SRT end plus declared narration_tail_frames")
    previous, ids = 0, set()
    declared_code = set()
    for scene in project["scenes"]:
        safe_path(package, scene["id"] + ".mp4")
        if scene["id"] in ids:
            raise ValueError("Duplicate scene ID")
        ids.add(scene["id"])
        if scene["start_frame"] != previous or scene["end_frame"] <= previous:
            raise ValueError(f"{scene['id']}: scenes must cover frames contiguously from zero")
        previous = scene["end_frame"]
        expected = [c["id"] for c in cues if c["start"] < scene["end_frame"] / fps * 1000 - 1e-7
                    and c["end"] > scene["start_frame"] / fps * 1000 + 1e-7]
        if scene["source_cues"] != expected:
            raise ValueError(f"{scene['id']}: source_cues must be {expected}")
        path = safe_path(package, scene["script"])
        if not path.is_file():
            raise ValueError(f"Missing scene code: {scene['script']}")
        code = path.read_text(encoding="utf-8-sig")
        if scene["engine"] == "python":
            if scene["script"] != "scenes.py":
                raise ValueError("Python scenes must use scenes.py")
            entry_signature(validate_code(code), scene["entry"], ["t", "ctx"])
        else:
            if not re.fullmatch(r"scripts/[A-Za-z0-9_-]+\.py", scene["script"]) or scene["entry"] != "build":
                raise ValueError("Blender scenes must use scripts/<name>.py and entry build")
            blender_code(code)
        declared_code.add(scene["script"])
    if previous != total:
        raise ValueError("Last scene must end at total_frames")
    declared_assets = set()
    for asset in project["assets"]:
        if not asset["path"].startswith("assets/"):
            raise ValueError("Asset paths must be under assets/")
        path = safe_path(package, asset["path"])
        if not path.is_file() or asset["path"] in declared_assets:
            raise ValueError(f"Missing/duplicate asset: {asset['path']}")
        if asset["sha256"] is not None and sha(path) != asset["sha256"]:
            raise ValueError(f"Asset hash mismatch: {asset['path']}")
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".ttf", ".otf"}:
            raise ValueError("Only raster images and fonts are supported as package assets; voiceover is supplied separately")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
        declared_assets.add(asset["path"])
    validate_plan(read_json(package / "creative_plan.json"), project, cues)
    expected_files = {"project.json", "source.srt", "storyboard.md", "qa_report.json", "creative_plan.json"} | declared_code | declared_assets
    actual_files = {p.relative_to(package).as_posix() for p in files}
    if actual_files != expected_files:
        raise ValueError(f"Undeclared/missing package files: {sorted(actual_files.symmetric_difference(expected_files))}")
    qa = read_json(package / "qa_report.json")
    Draft202012Validator(read_json(FRAMEWORK / "qa.schema.json")).validate(qa)
    if qa["status"] == "frame_checked" and not qa["capabilities"]["image_inspection"]:
        raise ValueError("frame_checked requires image_inspection capability")
    if qa["status"] == "video_checked" and not qa["capabilities"]["video_inspection"]:
        raise ValueError("video_checked requires video_inspection capability")
    if qa["blocking_issues"] or qa["status"] == "blocked":
        raise ValueError("AI reported unresolved blocking issues; request a repaired return")
    if not (package / "storyboard.md").read_text(encoding="utf-8-sig").strip():
        raise ValueError("storyboard.md cannot be empty")
    return project, cues, qa
