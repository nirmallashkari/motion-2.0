"""Check required local rendering tools without reading credentials or calling APIs."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '_SYSTEM'))
import motion

if __name__ == '__main__':
    tools = motion.tools_for({'scenes': [{'engine': 'blender'}]})
    print('Python:', sys.version.split()[0])
    print('Blender:', tools['blender_version'])
    print('FFmpeg:', tools['ffmpeg_version'])
    print('Speech weights:', 'installed' if (ROOT / '_SYSTEM/assets/models/faster-whisper-small/manifest.json').exists() else 'absent (TXT uses estimated proportional timing)')
    print('Local rendering tool checks passed; API access was not tested.')
