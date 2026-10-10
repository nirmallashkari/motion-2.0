"""Repair only existing virtual-environment console launchers after relocation."""
from importlib import metadata
from pathlib import Path
import sys

from pip._vendor.distlib.scripts import ScriptMaker


def main():
    scripts = Path(sys.executable).resolve().parent
    maker = ScriptMaker(None, str(scripts))
    maker.executable = str(scripts / "python.exe")
    maker.clobber = True
    maker.variants = {""}
    repaired = []
    for distribution in metadata.distributions():
        for entry in distribution.entry_points:
            if entry.group == "console_scripts" and (scripts / (entry.name + ".exe")).is_file():
                maker.make(entry.name + " = " + entry.value)
                repaired.append(entry.name)
    for name in ("pip", "pip3", f"pip{sys.version_info.major}.{sys.version_info.minor}"):
        if (scripts / (name + ".exe")).is_file():
            maker.make(name + " = pip._internal.cli.main:main")
            repaired.append(name)
    config = scripts.parent / "pyvenv.cfg"
    text = config.read_text()
    lines = [("command = " + sys.base_prefix + r"\python.exe -m venv " + str(scripts.parent))
             if line.startswith("command = ") else line for line in text.splitlines()]
    config.write_text("\n".join(lines) + "\n")
    print(f"Repaired {scripts}: {', '.join(sorted(set(repaired)))}")


if __name__ == "__main__":
    main()
