# Public source verification

Verified locally on 2026-10-10 in an isolated source export, with a newly created
Python virtual environment. The installed production project's input/output and
credentials were excluded and preserved.

| Check | Result |
| --- | --- |
| Core dependency installation from `requirements.txt` | Passed in a fresh Python 3.13.7 environment |
| Public setup script | Passed; detected Blender 5.1.1 and FFmpeg 8.0.1 |
| Existing host/regression suite | 231 tests passed, including real FFmpeg integration |
| Publication guard regression cases | 3 tests passed |
| Tracked source and staged blob audit | No installed API key matches; no forbidden runtime/credential paths |

Tests use synthetic fixtures and mocked API calls. This verification did not call
a live DeepSeek account or spend API credit. It does not establish universal story
coverage, natural character acting or continuous visual quality.

The optional speech model's installer uses the pinned revision and SHA-256 values
in `tools/speech_model_manifest.json`. Large model weights are not part of Git.
Their download is a separate optional setup operation.

Reproduce the source checks using the commands in [CONTRIBUTING.md](../CONTRIBUTING.md).
CI covers Windows regression and FFmpeg integration, not a full Blender production
render or live API availability.
