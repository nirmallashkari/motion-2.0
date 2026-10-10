"""Single Motion 2.0 launcher: validate, route scenes, assemble, attach narration."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from PIL import Image, ImageDraw, features

from contract import (SYSTEM, VERSION, AUDIO_SUFFIXES, extract_zip, no_links, package_files,
                      read_json, safe_path, sha, validate_package, write_json)
from quality_check import check_motion


@contextmanager
def workspace_lock(workspace):
    lock = no_links(Path(workspace) / "_SYSTEM/session.lock", workspace)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError("Motion is already running. Wait for that render/reset to finish.")
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)


def tools_for(project):
    tools = {}
    for name in ("ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        if not executable:
            raise ValueError(f"{name} is missing from PATH. Restore the installed tool before running.")
        tools[name] = str(Path(executable).resolve())
    tools["ffmpeg_version"] = subprocess.check_output(
        [tools["ffmpeg"], "-version"], text=True, encoding="utf-8", errors="replace", timeout=20).splitlines()[0]
    if any(s["engine"] == "blender" for s in project["scenes"]):
        choices = [os.environ.get("MOTION_BLENDER"), shutil.which("blender"),
                   r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"]
        executable = next((p for p in choices if p and Path(p).is_file()), None)
        if not executable:
            raise ValueError("Blender 5.1.1 is required for these scenes. Set MOTION_BLENDER to its executable.")
        version = subprocess.check_output([executable, "--version"], text=True, timeout=20).splitlines()[0]
        if version != "Blender 5.1.1":
            raise ValueError(f"This framework requires Blender 5.1.1; found {version}")
        tools["blender"] = str(Path(executable).resolve())
        tools["blender_version"] = version
    return tools


def probe(path, tools, count=False):
    command = [tools["ffprobe"], "-v", "error"]
    if count:
        command += ["-count_frames"]
    command += ["-show_streams", "-show_format", "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if result.returncode:
        raise ValueError(f"Cannot inspect {path.name}: {result.stderr[-1500:]}")
    return json.loads(result.stdout)


def encode(command, log, timeout=600):
    with Path(log).open("ab") as stream:
        result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=stream, timeout=timeout)
    if result.returncode:
        raise ValueError(f"FFmpeg failed. Log: {log}\n{Path(log).read_text(errors='replace')[-2000:]}")


def verify_movie(path, canvas, frames, tools, audio, log):
    info = probe(path, tools, True)
    streams = info["streams"]
    videos = [s for s in streams if s["codec_type"] == "video"]
    audios = [s for s in streams if s["codec_type"] == "audio"]
    if len(videos) != 1 or len(audios) != int(audio):
        raise ValueError("Unexpected video/audio stream count")
    video = videos[0]
    expected = frames / canvas["fps"]
    if (video["width"], video["height"], video["codec_name"], video["pix_fmt"]) != (
            canvas["width"], canvas["height"], "h264", "yuv420p"):
        raise ValueError("Video resolution/codec/pixel format failed verification")
    if int(video["nb_read_frames"]) != frames or Fraction(video["avg_frame_rate"]) != canvas["fps"]:
        raise ValueError("Frame count/FPS failed verification")
    if abs(float(video["duration"]) - expected) > .002:
        raise ValueError("Video duration failed verification")
    if audios and (audios[0]["codec_name"] != "aac" or abs(float(audios[0].get("duration", info["format"]["duration"])) - expected) > .08):
        raise ValueError("Narration duration/codec failed verification")
    if any(s["codec_type"] == "subtitle" for s in streams):
        raise ValueError("Subtitles must be OFF")
    encode([tools["ffmpeg"], "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"], log)
    return dict(width=video["width"], height=video["height"], fps=canvas["fps"], frames=frames,
                duration_seconds=expected, video_codec="h264", audio_codec="aac" if audio else None,
                subtitles="off", full_decode="passed", sha256=sha(path))


def write_concat_manifest(path, scenes, fps):
    """Use timeline frame counts, avoiding rounded MP4 container durations."""
    Path(path).write_text("".join(
        f"file '{scene['id']}.mp4'\nduration {(scene['end_frame'] - scene['start_frame']) / fps:.12f}\n"
        for scene in scenes), encoding="utf-8")


def select_inputs(inbox):
    no_links(inbox, inbox.parent)
    candidates = []
    for path in inbox.iterdir():
        no_links(path, inbox)
        if path.is_file() and path.suffix.lower() == ".zip":
            candidates.append(path)
        elif path.is_dir() and path.name == "return":
            candidates.append(path)
    if len(candidates) != 1:
        raise ValueError("Place exactly ONE external AI return ZIP (or return folder) in INPUT. Do not place the framework ZIP here.")
    voices = [p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES]
    if len(voices) > 1:
        raise ValueError("Keep only ONE voiceover audio file in INPUT; remove ambiguity before running.")
    voice = voices[0] if voices else None
    if voice and voice.stat().st_size > 300 * 1024**2:
        raise ValueError("Voiceover exceeds 300 MB")
    sources = [inbox/name for name in ("source.srt", "SCRIPT.txt") if (inbox/name).is_file()]
    if sources:
        from caption_text import parse_srt
        parsed = parse_srt(sources[0])
        if any(parse_srt(p) != parsed for p in sources[1:]):
            raise ValueError("R03: source.srt and SCRIPT.txt disagree. Keep one authoritative timed source.")
    return candidates[0], sources[0] if sources else None, voice


def narration_info(voice, duration, tools):
    if not voice:
        return dict(present=False, cue_sync_verified=False)
    info = probe(voice, tools)
    audios = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if len(audios) != 1:
        raise ValueError("Voiceover must contain exactly one audio stream")
    length = float(audios[0].get("duration", info["format"]["duration"]))
    difference = length - duration
    if abs(difference) > .2 + 1e-7:
        raise ValueError(f"Voiceover is {length:.3f}s but the script/video is {duration:.3f}s. Supply aligned audio/SRT; no time stretching is applied.")
    return dict(present=True, original_file=voice.name, input_seconds=length, video_seconds=duration,
                tail_adjustment_seconds=round(-difference, 6), cue_sync_verified=False,
                policy="Only up to 0.2s of tail padding/trimming; original narration speed and start retained.")


def fingerprint(package, voice, tools):
    import PIL
    digest = hashlib.sha256(VERSION.encode())
    for path in package_files(package):
        digest.update(path.relative_to(package).as_posix().encode() + bytes.fromhex(sha(path)))
    for path in sorted(SYSTEM.glob("*.py")):
        digest.update(path.name.encode() + bytes.fromhex(sha(path)))
    for name in ("motion_sdk.py", "blender_sdk.py", "code_policy.py", "authoring_contract.py", "quality_policy.py",
                 "project.schema.json", "creative_plan.schema.json", "qa.schema.json"):
        digest.update(name.encode() + bytes.fromhex(sha(SYSTEM / "framework" / name)))
    for path in sorted((SYSTEM / "framework/fonts").glob("*")):
        if path.is_file():
            digest.update(path.name.encode() + bytes.fromhex(sha(path)))
    digest.update(bytes.fromhex(sha(voice)) if voice else b"silent")
    digest.update(json.dumps(dict(tools=tools, python=sys.version, pillow=PIL.__version__),
                             sort_keys=True).encode())
    return digest.hexdigest()


def stop_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=20)
    else:
        process.kill()
    process.wait(timeout=20)


def run_worker(command, progress, log, label, timeout, stall):
    started = changed = last_print = time.monotonic()
    previous = None
    with Path(log).open("ab") as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=stream, stdin=subprocess.DEVNULL)
        try:
            while process.poll() is None:
                now = time.monotonic()
                state = None
                if progress.exists():
                    try:
                        state = read_json(progress)
                    except (OSError, ValueError):
                        pass
                signature = json.dumps(state, sort_keys=True) if state else None
                if signature != previous:
                    changed, previous = now, signature
                if now - last_print >= 5:
                    suffix = f"{state['completed']}/{state['total']} frames" if state else "starting"
                    print(f"  {label}: {suffix}", flush=True)
                    last_print = now
                if now - started > timeout or now - changed > stall:
                    raise TimeoutError(f"{label}: render timed out/stalled. Work retained; inspect {log}")
                time.sleep(.2)
            if process.returncode:
                raise ValueError(f"{label} failed ({process.returncode}). {log}\n{Path(log).read_text(errors='replace')[-2500:]}")
        finally:
            stop_tree(process)


def review_frames(job, project, tools, log):
    review = job / "review"
    review.mkdir(exist_ok=True)
    frames = []
    for scene in project["scenes"]:
        count = scene["end_frame"] - scene["start_frame"]
        indices = sorted({0, min(8, count-1), count//2, count-1})
        for index in indices:
            path = review / f"{scene['id']}_{index:06d}.png"
            encode([tools["ffmpeg"], "-v", "error", "-y", "-i", str(job / "clips" / f"{scene['id']}.mp4"),
                    "-vf", f"select=eq(n\\,{index})", "-frames:v", "1", str(path)], log)
            frames.append(dict(path=path.name, scene=scene["id"], global_frame=scene["start_frame"]+index))
    pages = []
    for offset in range(0, len(frames), 24):
        batch = frames[offset:offset+24]
        sheet = Image.new("RGB", (960, ((len(batch)+2)//3)*210), "#09182e")
        draw = ImageDraw.Draw(sheet)
        for i, sample in enumerate(batch):
            with Image.open(review / sample["path"]) as image:
                image.thumbnail((320, 180))
                x, y = i % 3 * 320, i // 3 * 210
                sheet.paste(image, (x+(320-image.width)//2, y+(180-image.height)//2))
                draw.text((x+6, y+184), f"{sample['scene']} / frame {sample['global_frame']}", fill="white")
        path = review / f"contact_sheet_{offset//24+1:03d}.jpg"
        sheet.save(path, quality=92)
        pages.append(path.name)
    write_json(review / "frames.json", dict(frames=frames, contact_sheets=pages, visual_status="awaiting_user_review"))


def render_scenes(job, project, tools):
    canvas = project["canvas"]
    creative = read_json(job / "source/creative_plan.json")
    from caption_text import parse_srt
    cues = parse_srt(job / "source/source.srt")
    plans = {item["id"]: item for item in creative["scenes"]}
    for number, scene in enumerate(project["scenes"], 1):
        write_json(job / "active_scene.json", dict(id=scene["id"]))
        count = scene["end_frame"] - scene["start_frame"]
        clip = job / "clips" / f"{scene['id']}.mp4"
        record = clip.with_suffix(".verified.json")
        log = job / "logs" / f"{scene['id']}.log"
        if record.exists() and clip.exists() and read_json(record).get("sha256") == sha(clip):
            try:
                verify_movie(clip, canvas, count, tools, False, log)
                print(f"Reusing verified scene {number}/{len(project['scenes'])}: {scene['id']}", flush=True)
                continue
            except (ValueError, KeyError):
                pass
        print(f"Rendering {number}/{len(project['scenes'])}: {scene['id']} [{scene['engine']}], {count} frames", flush=True)
        output = job / "renders" / scene["id"]
        output.mkdir(parents=True, exist_ok=True)
        task = dict(project=project, scene=scene, package=str(job / "source"), output=str(output),
                    clip=str(clip), ffmpeg=tools["ffmpeg"], sdk_root=str(SYSTEM / "framework"),
                    creative_scene=plans[scene["id"]],
                    source_text=" ".join(c["text"] for c in cues if c["id"] in scene["source_cues"]))
        task_path = job / "tasks" / f"{scene['id']}.json"
        write_json(task_path, task)
        if scene["engine"] == "python":
            command = [sys.executable, "-u", str(SYSTEM / "python_worker.py"), str(task_path)]
            run_worker(command, output / "progress.json", log, scene["id"], 1800, 90)
        else:
            command = [tools["blender"], "--background", "--factory-startup", "--disable-autoexec",
                       "--python-exit-code", "1", "--python", str(SYSTEM / "blender_worker.py"), "--", str(task_path)]
            run_worker(command, output / "progress.json", log, scene["id"], 14400, 600)
            encode([tools["ffmpeg"], "-v", "error", "-y", "-framerate", str(canvas["fps"]),
                    "-start_number", "0", "-i", str(output / "frame_%06d.png"), "-frames:v", str(count),
                    "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
                    "-threads", "2", "-movflags", "+faststart", str(clip)], log)
        technical = verify_movie(clip, canvas, count, tools, False, log)
        write_json(record, technical)


def publish(workspace, job, project, audio, technical, identity):
    output = workspace / "OUTPUT"
    movie_name = "final.mp4" if audio["present"] else "silent_preview.mp4"
    delivery = output / "deliveries" / identity[:16]
    delivery.mkdir(parents=True, exist_ok=True)
    report = dict(format=VERSION, project=project["title"], job_id=identity,
                  status="technical_checks_passed", visual_review="awaiting_user_review",
                  storytelling_checks=read_json(job / "quality_report.json"),
                  cue_level_voice_sync_verified=False, audio=audio, technical=technical,
                  scenes=[dict(id=s["id"], engine=s["engine"], start_frame=s["start_frame"], end_frame=s["end_frame"])
                          for s in project["scenes"]])
    if (job / "review/local_ai_review.json").is_file():
        report["local_ai_review"] = read_json(job / "review/local_ai_review.json")
    write_json(job / "qa_report.json", report)
    for source, name in [(job / "movie.mp4", movie_name), (job / "source/source.srt", "timing.srt"),
                         (job / "qa_report.json", "qa_report.json"), (job / "quality_report.json", "quality_report.json")]:
        shutil.copy2(source, delivery / name)
    shutil.copytree(job / "review", delivery / "review", dirs_exist_ok=True)
    editable = delivery / "editable_project.zip"
    with zipfile.ZipFile(editable, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in package_files(job / "source"):
            bundle.write(path, "return/" + path.relative_to(job / "source").as_posix())
        for path in sorted((job / "renders").rglob("*.blend")):
            bundle.write(path, "blender/" + path.relative_to(job / "renders").as_posix())
        if audio["present"]:
            bundle.write(job / "voiceover", "input/" + audio["original_file"])
    for name in (movie_name, "qa_report.json", "timing.srt", "quality_report.json"):
        temporary = output / (name + ".tmp")
        shutil.copy2(delivery / name, temporary)
        temporary.replace(output / name)
    # A silent current run must not expose a stale narrated movie as its own final.
    if not audio["present"] and (output / "final.mp4").exists():
        history = output / "history"
        history.mkdir(exist_ok=True)
        (output / "final.mp4").replace(history / f"previous_final_{time.time_ns()}.mp4")
    (output / "LATEST.txt").write_text(str(output / movie_name) + "\n", encoding="utf-8")
    if (output / "ERROR.json").exists():
        (output / "ERROR.json").replace(delivery / "previous_error.json")
    if (output / "REPAIR_REQUEST.json").exists():
        (output / "REPAIR_REQUEST.json").replace(delivery / "previous_repair_request.json")
    state = "READY: narrated movie" if audio["present"] else "SILENT PREVIEW: add one voiceover audio file to INPUT and rerun."
    (output / "STATUS.txt").write_text(state + "\nVisual review: awaiting user review.\n" + str(delivery) + "\n", encoding="utf-8")
    print(f"{state}\nVIDEO: {output / movie_name}\nREVIEW: {delivery / 'review'}", flush=True)


def execute(workspace, selection=None, reviewer=None, self_mode=False):
    inbox = workspace / "INPUT"
    output = workspace / "OUTPUT"
    selected, original, voice = selection if selection is not None else select_inputs(inbox)
    with tempfile.TemporaryDirectory(dir=workspace / "_SYSTEM/work", prefix="import_") as temporary:
        package = Path(temporary) / "return"
        package.mkdir()
        if selected.is_file():
            extract_zip(selected, package)
        else:
            for path in package_files(selected):
                target = package / path.relative_to(selected)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        project, cues, qa = validate_package(package, original)
        canvas = project["canvas"]
        if (canvas["width"], canvas["height"]) not in {(1280,720),(1920,1080),(720,1280),(1080,1920)}:
            raise ValueError("Use a supported landscape/portrait canvas")
        if not features.check("raqm"):
            for path in package_files(package):
                if path.suffix == ".py" and any("\u0900" <= c <= "\u097f" for c in path.read_text(encoding="utf-8-sig")):
                    raise ValueError("Hindi on-screen code requires verified font shaping. Use English design labels with the installed runtime; source SRT can remain Hindi.")
        tools = tools_for(project)
        duration = project["total_frames"] / canvas["fps"]
        if project.get("narration_tail_frames") and not voice:
            raise ValueError("A declared narration closing animation requires the original voiceover")
        audio = narration_info(voice, duration, tools)
        if project.get("narration_tail_frames"):
            source_seconds = cues[-1]["end"] / 1000
            if audio["input_seconds"] <= source_seconds + .2:
                raise ValueError("Narration closing animation is only allowed when full voice extends beyond the original SRT")
            audio["source_end_seconds"] = source_seconds
            audio["closing_animation_seconds"] = project["narration_tail_frames"] / canvas["fps"]
            audio["source_timestamps_unchanged"] = True
        identity = fingerprint(package, voice, tools)
        job = workspace / "_SYSTEM/work" / identity
        job.mkdir(exist_ok=True)
        if not (job / "source").exists():
            shutil.copytree(package, job / "source")
        if voice and not (job / "voiceover").exists():
            shutil.copy2(voice, job / "voiceover")
        for name in ("clips", "tasks", "renders", "logs", "review"):
            (job / name).mkdir(exist_ok=True)
        package_hashes = {p.relative_to(package).as_posix(): sha(p) for p in package_files(package)}
        actual_hashes = {p.relative_to(job / "source").as_posix(): sha(p) for p in package_files(job / "source")}
        if package_hashes != actual_hashes:
            raise ValueError("Validated project snapshot changed. Reset the render cache or restore the original project.")
        write_json(job / "inputs.json", dict(format=VERSION, identity=identity, project=project, audio=audio,
                   package_hashes=package_hashes))
    # Render only the validated immutable snapshot, not mutable operator input.
    validate_package(job / "source")
    if voice and sha(job / "voiceover") != sha(voice):
        raise ValueError("Narration snapshot changed")
    print(f"Project: {project['title']}\nScenes: {len(project['scenes'])}; duration: {duration:.3f}s; "
          f"{canvas['width']}x{canvas['height']} @ {canvas['fps']}fps\nSubtitles: OFF; voiceover: {'YES' if voice else 'NO'}", flush=True)
    try:
        render_scenes(job, project, tools)
    except Exception as exc:
        if reviewer is not None and (job / "active_scene.json").is_file():
            from local_pipeline import SceneFailure
            raise SceneFailure([read_json(job / "active_scene.json")["id"]], str(exc)) from exc
        raise
    log = job / "logs/assembly.log"
    concat = job / "clips/concat.txt"
    write_concat_manifest(concat, project["scenes"], canvas["fps"])
    silent = job / "silent.mp4"
    encode([tools["ffmpeg"], "-v", "error", "-y", "-f", "concat", "-safe", "1", "-i", str(concat),
            "-an", "-c:v", "copy", "-movflags", "+faststart", str(silent)], log)
    movie = job / "movie.mp4"
    if voice:
        encode([tools["ffmpeg"], "-v", "error", "-y", "-i", str(silent), "-i", str(job / "voiceover"),
                "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-af", f"apad,atrim=duration={duration:.9f},asetpts=PTS-STARTPTS",
                "-movflags", "+faststart", str(movie)], log)
    else:
        shutil.copy2(silent, movie)
    technical = verify_movie(movie, canvas, project["total_frames"], tools, bool(voice), log)
    quality = check_motion(movie, project, tools, log)
    write_json(job / "quality_report.json", quality)
    if quality["failures"]:
        write_json(workspace / "OUTPUT/REPAIR_REQUEST.json", dict(status="changes_required",
                   failures=quality["failures"], action=("The registered local renderer failed a motion check. Read the engineering logs; preserve the original SRT and voice. No external AI package is required." if self_mode else "External AI must repair scene actions; preserve original SRT and voice.")))
        message = "Visual quality gate failed: " + "; ".join(quality["failures"])
        if reviewer is not None:
            from local_pipeline import SceneFailure
            raise SceneFailure([s["id"] for s in quality["scenes"] if s["longest_near_static_seconds"] > 3], message)
        raise ValueError(message)
    review_frames(job, project, tools, log)
    if reviewer is not None:
        reviewer(job, project, tools)
    if (job / "source/project.json").is_file() and project.get("narration_tail_frames"):
        # Keep the source cue end intact while the final illustration covers the voice tail.
        technical["original_source_end_seconds"] = cues[-1]["end"] / 1000
    publish(workspace, job, project, audio, technical, identity)
    return 0


def reset_plan(workspace):
    paths = []
    for relative in ("INPUT", "OUTPUT", "_SYSTEM/work"):
        folder = no_links(workspace / relative, workspace)
        if not folder.is_dir():
            raise ValueError(f"Missing reset boundary: {relative}")
        for child in folder.iterdir():
            if relative in {"INPUT", "OUTPUT"} and child.name == "README.txt":
                continue
            no_links(child, workspace)
            if child.is_dir():
                stack = [child]
                while stack:
                    for entry in stack.pop().iterdir():
                        no_links(entry, workspace)
                        if entry.is_dir():
                            stack.append(entry)
            paths.append(child)
    return paths


def reset(workspace, dry_run=False, confirmation=""):
    paths = reset_plan(workspace)
    print("Reset removes project inputs, generated outputs and render cache.")
    print("Engines, framework, examples and engineering reports are preserved.")
    for path in paths:
        print("  " + str(path.relative_to(workspace)))
    if dry_run:
        print("DRY RUN: nothing removed.")
        return 0
    answer = confirmation or input("Type RESET to clear this project, or press Enter to cancel: ").strip()
    if answer != "RESET":
        print("Cancelled. No project data removed.")
        return 0
    for path in paths:
        no_links(path, workspace)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    write_json(workspace / "_SYSTEM/reports" / f"reset_{time.time_ns()}.json",
               dict(status="completed", removed=[str(p.relative_to(workspace)) for p in paths]))
    (workspace / "OUTPUT/STATUS.txt").write_text("Ready for a new script. Add a timed source and voiceover to INPUT for local AI, or a return ZIP for external AI.\n", encoding="utf-8")
    print("Reset complete. Ready for a new script.")
    return 0


def check(workspace):
    import PIL
    print(f"Workspace: {workspace}\nPython: {sys.version.split()[0]}\nPillow: {PIL.__version__}")
    for name in ("ffmpeg", "ffprobe"):
        print(f"{name}: {shutil.which(name) or 'MISSING'}")
    print(f"Active rulebook: {SYSTEM / 'RULEBOOK.md'}")
    from local_pipeline import configuration
    config = configuration(workspace)
    if config["authoring_mode"] == "hybrid":
        from cloud_planner import configuration as cloud_configuration
        cloud=cloud_configuration(workspace)
        if cloud['enabled']:
            print(f"Hybrid mode: {cloud['provider']} planner {cloud['model']}; Blender/Python and voice remain local; internet required for fresh plans.")
        else:
            print(f"Hybrid mode: Blender/Python registered library; local planner: {'ON' if config['enabled'] else 'OFF'}; model: {config['model']}")
    elif config["authoring_mode"] == "self":
        print("Self mode: ENABLED; offline rules and assets; no runtime model calls.")
    else:
        print(f"Local AI: {'ENABLED' if config['enabled'] else 'OFF'}; model: {config['model']}")
    print("Inputs: timed source.srt/SCRIPT.txt + one voiceover; a return ZIP selects the external workflow.")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "reset", "check"))
    parser.add_argument("--workspace", type=Path, default=SYSTEM.parent)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirmation", default="")
    args = parser.parse_args(argv)
    workspace = args.workspace.absolute()
    try:
        if not (workspace / "_SYSTEM/installation.json").is_file() or read_json(workspace / "_SYSTEM/installation.json").get("format") != VERSION:
            raise ValueError("Workspace installation marker is missing or unsupported")
        for relative in ("INPUT", "OUTPUT", "_SYSTEM", "_SYSTEM/work", "_SYSTEM/reports"):
            no_links(workspace / relative, workspace)
        if args.action == "check":
            return check(workspace)
        with workspace_lock(workspace):
            if args.action == "reset":
                return reset(workspace, args.dry_run, args.confirmation)
            config = {}
            try:
                from local_pipeline import configuration, external_present, run_local
                config = configuration(workspace)
                if (config["enabled"] or config["authoring_mode"] in {"self", "hybrid"}) and not external_present(workspace / "INPUT"):
                    return run_local(workspace, config)
                return execute(workspace)
            except Exception as exc:
                if config.get("authoring_mode") in {"self", "hybrid"}:
                    state_path = workspace / "OUTPUT/SYSTEM_STATUS.json"
                    state = read_json(state_path) if state_path.is_file() else dict(mode="self",runtime_ai_calls=0)
                    write_json(state_path,dict(state,status="failed",error=str(exc)))
                write_json(workspace / "OUTPUT/ERROR.json", dict(status="failed", error=str(exc),
                           action="Read STATUS.txt and SYSTEM_STATUS.json. For unmatched passages, follow NEEDS_VISUAL_CHOICES.json. Check source/voice timing and rerun RUN_VIDEO.bat."))
                (workspace / "OUTPUT/STATUS.txt").write_text("FAILED: current input did not produce a new movie.\nPrevious deliveries, if any, belong to earlier inputs.\n" + str(exc) + "\n", encoding="utf-8")
                raise
    except KeyboardInterrupt:
        print("Interrupted. Rerun RUN_VIDEO.bat to reuse verified scenes.")
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
