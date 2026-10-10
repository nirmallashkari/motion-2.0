"""Stage and collect a generated three-second installation smoke test."""
import argparse
import json
from pathlib import Path
import math
import shutil
import struct
import time
import wave
import zipfile

from contract import SYSTEM, package_files, sha, write_json

ROOT = SYSTEM.parent
RECORD = SYSTEM / "reports/SMOKE_STAGE.json"


def stage():
    user_files = [p for p in (ROOT / "INPUT").iterdir() if p.name != "README.txt"]
    if user_files:
        raise ValueError("Do not stage a smoke test over existing user input")
    if any(p.name != "README.txt" for p in (ROOT / "OUTPUT").iterdir()):
        raise ValueError("Do not stage a smoke test over existing user output")
    archive = ROOT / "INPUT/installation_test.zip"
    package = SYSTEM / "framework/example_return"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in package_files(package):
            bundle.write(path, path.relative_to(package).as_posix())
    voice = ROOT / "INPUT/installation_test.wav"
    samples = b"".join(struct.pack("<h", round(3000 * math.sin(2*math.pi*440*i/48000))) for i in range(144000))
    with wave.open(str(voice), "wb") as stream:
        stream.setparams((1, 2, 48000, 144000, "NONE", "not compressed"))
        stream.writeframes(samples)
    write_json(RECORD, dict(generated_inputs={p.name: sha(p) for p in (archive, voice)},
                           type="synthetic tone, not human narration", duration_seconds=3))
    print("Generated test staged. Run the real root RUN_VIDEO.bat -NoPause.")


def collect():
    record = json.loads(RECORD.read_text())
    for name, signature in record["generated_inputs"].items():
        if sha(ROOT / "INPUT" / name) != signature:
            raise ValueError("Generated input changed; do not move user data")
    qa = json.loads((ROOT / "OUTPUT/qa_report.json").read_text())
    movie = ROOT / "OUTPUT/final.mp4"
    if qa["technical"]["sha256"] != sha(movie) or qa["technical"]["frames"] != 72:
        raise ValueError("Smoke delivery failed its integrity/frame check")
    if [s["engine"] for s in qa["scenes"]] != ["python", "blender", "python"]:
        raise ValueError("Both engines were not exercised in the expected order")
    evidence = SYSTEM / "reports/installation_smoke"
    evidence.mkdir(exist_ok=True)
    for name in record["generated_inputs"]:
        destination = evidence / "input" / name
        destination.parent.mkdir(exist_ok=True)
        shutil.move(str(ROOT / "INPUT" / name), str(destination))
    for path in (ROOT / "OUTPUT").iterdir():
        if path.name == "README.txt":
            continue
        shutil.move(str(path), str(evidence / path.name))
    write_json(SYSTEM / "reports/INTEGRATION_TEST.json",
               dict(status="passed", launcher="RUN_VIDEO.bat", mixed_engines=True,
                    voice_attachment="verified with synthetic 440Hz tone", technical=qa["technical"],
                    visual_quality="smoke frames only; not a claim of production quality",
                    evidence=str(evidence)))
    (ROOT / "OUTPUT/STATUS.txt").write_text("Ready for your project. Place a complete return ZIP and one voiceover in INPUT.\n", encoding="utf-8")
    print(f"Smoke evidence preserved: {evidence}\nUser INPUT is clean; no reset was executed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("stage", "collect"))
    args = parser.parse_args()
    stage() if args.action == "stage" else collect()
