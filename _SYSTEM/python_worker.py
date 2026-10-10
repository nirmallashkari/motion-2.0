"""Supervised pure-frame Pillow worker for the unified scene contract."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import shlex
import time

from PIL import Image
import PIL
from quality_policy import TextGuard

sys.dont_write_bytecode = True


def write_progress(path, completed, total):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(dict(completed=completed, total=total)), encoding="utf-8")
    for attempt in range(20):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(.02)


def install_audit(package, output, clip, sdk_root, executable, log):
    reads = [package, sdk_root, Path(sys.base_prefix), Path(sys.prefix), Path(PIL.__file__).resolve().parent]
    writes = [output]
    allowed = {clip.resolve(), clip.with_suffix(".partial.mp4").resolve(), log.resolve()}

    def audit(event, args):
        if event == "open":
            name, mode, flags = args
            if isinstance(name, int):
                return
            if os.fsdecode(name).upper() in {"NUL", "\\\\.\\NUL", os.devnull.upper()}:
                return
            path = Path(os.fsdecode(name)).resolve()
            writing = bool((flags or 0) & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            roots = writes if writing else reads + writes
            if path not in allowed and not any(path.is_relative_to(p.resolve()) for p in roots):
                raise PermissionError(f"Worker file access outside its contract: {path}")
        if event.startswith("socket.") or event in {"os.system", "os.remove", "os.rmdir", "os.symlink", "os.link"}:
            raise PermissionError(f"Unsupported worker operation: {event}")
        if event == "os.rename":
            for name in args[:2]:
                path = Path(name).resolve()
                if path not in allowed and not any(path.is_relative_to(p.resolve()) for p in writes):
                    raise PermissionError("Worker rename outside its output")
        if event == "subprocess.Popen":
            candidate = args[0]
            if candidate is None:
                arguments = args[1]
                candidate = arguments[0] if isinstance(arguments, (list, tuple)) else shlex.split(arguments, posix=False)[0].strip('"')
            if Path(candidate).resolve() != Path(executable).resolve():
                raise PermissionError("Only the host FFmpeg encoder may run in a Python worker")

    sys.addaudithook(audit)


def main():
    task = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    project, scene = task["project"], task["scene"]
    package, output, clip = Path(task["package"]), Path(task["output"]), Path(task["clip"])
    sdk_root = Path(task["sdk_root"])
    planned = task["creative_scene"]
    guard = TextGuard(planned, task["source_text"], (project["canvas"]["width"], project["canvas"]["height"]))
    guard.install()
    canvas = project["canvas"]
    width, height, fps = (canvas[k] for k in ("width", "height", "fps"))
    count = scene["end_frame"] - scene["start_frame"]
    progress = output / "progress.json"
    log = output / "encoder.log"
    sys.path.insert(0, str(sdk_root))
    import motion_sdk as sdk
    sdk.Context  # Import trusted SDK before restricting module access.
    install_audit(package, output, clip, sdk_root, task["ffmpeg"], log)
    spec = importlib.util.spec_from_file_location("external_scenes", package / scene["script"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, scene["entry"])
    if task.get('preview') is True:
        indices=[round((count-1)*q) for q in (.08,.50,.94)]
        write_progress(progress,0,len(indices))
        for number,local_frame in enumerate(indices,1):
            ctx=sdk.Context(width,height,fps,(scene['start_frame']+local_frame)/fps,
                scene['start_frame']/fps,scene['end_frame']/fps,scene['id'],package/'assets')
            guard.reset(scene['start_frame']+local_frame)
            image=function(local_frame/fps,ctx);guard.finish()
            if not isinstance(image,Image.Image) or image.mode!='RGB' or image.size!=(width,height):
                raise ValueError('Preview requires an exact-size RGB scene frame.')
            guard.reset(scene['start_frame']+local_frame)
            repeated=function(local_frame/fps,ctx);guard.finish()
            if image.tobytes()!=repeated.tobytes():raise ValueError('Preview frame is not deterministic.')
            image.resize((320,180),Image.Resampling.LANCZOS).save(output/f'preview_{number:02}.png')
            write_progress(progress,number,len(indices))
        return
    partial = clip.with_suffix(".partial.mp4")
    samples = {0, min(8, count-1), count//2, count-1}
    command = [task["ffmpeg"], "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{width}x{height}", "-r", str(fps), "-i", "pipe:0", "-an",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
               "-threads", "2", "-movflags", "+faststart", str(partial)]
    write_progress(progress, 0, count)
    with log.open("ab") as stderr:
        encoder = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr)
        try:
            for local_frame in range(count):
                global_time = (scene["start_frame"] + local_frame) / fps
                ctx = sdk.Context(width, height, fps, global_time, scene["start_frame"]/fps,
                                  scene["end_frame"]/fps, scene["id"], package / "assets")
                guard.reset(scene["start_frame"] + local_frame)
                image = function(local_frame / fps, ctx)
                guard.finish()
                if not isinstance(image, Image.Image) or image.mode != "RGB" or image.size != (width, height):
                    raise ValueError("Scene must return an exact-size RGB Pillow Image")
                if local_frame in samples:
                    guard.reset(scene["start_frame"] + local_frame)
                    repeated = function(local_frame/fps, ctx)
                    guard.finish()
                    if not isinstance(repeated, Image.Image) or repeated.mode != image.mode or repeated.size != image.size or repeated.tobytes() != image.tobytes():
                        raise ValueError("Repeated scene frame is not deterministic")
                encoder.stdin.write(image.tobytes())
                write_progress(progress, local_frame+1, count)
            encoder.stdin.close()
            if encoder.wait(timeout=120):
                raise ValueError("FFmpeg scene encoding failed")
        finally:
            if encoder.stdin and not encoder.stdin.closed:
                try:
                    encoder.stdin.close()
                except (OSError, BrokenPipeError):
                    pass
            if encoder.poll() is None:
                encoder.terminate()
                try:
                    encoder.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    encoder.kill()
                    encoder.wait(timeout=5)
    partial.replace(clip)


if __name__ == "__main__":
    main()
