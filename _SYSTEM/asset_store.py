"""Verified offline GitHub asset catalog; no network requests during production."""
from pathlib import Path
import hashlib
import io
import json

from PIL import Image
import resvg_py

ROOT = Path(__file__).resolve().parent / "assets/github"
COLORS = {"teal": "#68ded1", "gold": "#ffd16a", "coral": "#ff8187", "white": "#f2eee5", "ink": "#254a59"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AssetStore:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.source = json.loads((self.root / "source.json").read_text())
        if digest(self.root / "tabler.json") != self.source["sha256"]:
            raise ValueError("Offline Tabler catalog checksum mismatch. Restore the installed asset store.")
        self.data = json.loads((self.root / "tabler.json").read_text())
        if self.data["info"]["license"]["spdx"] != "MIT":
            raise ValueError("The installed catalog is outside the MIT asset profile.")
        self.animated = {entry["name"]: entry for entry in json.loads((self.root / "animated_manifest.json").read_text())}
        self.cache = self.root / "raster_cache"
        self.cache.mkdir(exist_ok=True)

    def names(self):
        return sorted(name for name, value in self.data["icons"].items() if not value.get("hidden"))

    def resolve(self, name):
        if name in self.data["icons"] and not self.data["icons"][name].get("hidden"):
            return name, self.data["icons"][name]
        alias = self.data.get("aliases", {}).get(name)
        if alias and alias.get("parent") in self.data["icons"]:
            return alias["parent"], self.data["icons"][alias["parent"]]
        raise ValueError(f"Unknown offline icon: {name}")

    def icon(self, name, color="teal"):
        name, value = self.resolve(name)
        color_value = COLORS[color]
        identity = hashlib.sha256((value["body"] + color_value + "raster-v1").encode()).hexdigest()
        target = self.cache / f"{identity}.png"
        record = self.cache / f"{identity}.json"
        if not target.exists() or not record.exists() or digest(target) != json.loads(record.read_text())["sha256"]:
            width = value.get("width", self.data.get("width", 24))
            height = value.get("height", self.data.get("height", 24))
            body = value["body"].replace("currentColor", color_value)
            svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 {width} {height}">{body}</svg>'
            target.write_bytes(resvg_py.svg_to_bytes(svg_string=svg, width=512, height=512))
            with Image.open(target) as image:
                if not image.getbbox() or image.size != (512, 512):
                    raise ValueError(f"Empty or malformed icon raster: {name}")
            record.write_text(json.dumps({"sha256": digest(target)}))
        return target, {"library": "Tabler Icons", "icon": name, "license": "MIT",
                        "repository": "https://github.com/tabler/tabler-icons",
                        "catalog_commit": self.source["commit"], "sha256": digest(target)}

    def animation(self, name):
        entry = self.animated[name]
        path = self.root / entry["local_path"]
        if digest(path) != entry["sha256"]:
            raise ValueError(f"Offline animation checksum mismatch: {name}")
        return path, dict(entry, library="Microsoft Fluent Emoji Animated")

    def copy_asset(self, package, name, animated=False, color="teal"):
        import shutil
        source, evidence = self.animation(name) if animated else self.icon(name, color)
        key = digest(source)
        relative = f"assets/{key[:24]}.png"
        target = Path(package) / relative
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy2(source, target)
        return relative, evidence
