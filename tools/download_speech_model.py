"""Explicit setup download; production speech inference never accesses the network."""
import hashlib
import json
from pathlib import Path
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]

def main():
    manifest = json.loads(Path(__file__).with_name('speech_model_manifest.json').read_text())
    target = ROOT / '_SYSTEM/assets/models/faster-whisper-small'
    target.mkdir(parents=True, exist_ok=True)
    for name, expected in manifest['files'].items():
        installed = target / name
        if installed.is_file() and hashlib.sha256(installed.read_bytes()).hexdigest() == expected:
            print(f'Already verified: {name}')
            continue
        downloaded = Path(hf_hub_download(repo_id=manifest['repository'], filename=name,
            revision=manifest['revision'], local_dir=str(target)))
        if hashlib.sha256(downloaded.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Pinned speech model checksum failed: {name}')
        print(f'Verified: {name}')
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Offline speech model installed. Repository: Systran/faster-whisper-small (MIT).')

if __name__ == '__main__':
    main()
