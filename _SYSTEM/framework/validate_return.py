"""Run the same structural authoring contract enforced by the local host."""
import argparse
from pathlib import Path
from authoring_contract import validate_package

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    args = parser.parse_args()
    project, cues, qa = validate_package(args.package)
    print(f"Contract passed: {len(cues)} cues, {len(project['scenes'])} scenes, {project['total_frames']} frames.")
    print("Rendering, audio/video verification and visual judgment remain separate checks.")

if __name__ == "__main__":
    main()
