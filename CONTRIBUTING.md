# Contributing to Motion 2.0

We welcome improvements to reusable animation capabilities, production reliability
and onboarding. Start with a small change tied to an issue and a synthetic example.

## Development setup

Fork and clone the repository. Install Python 3.13, FFmpeg and Blender 5.1.1, then
run `SETUP_MOTION.bat`. The optional speech model is not required for unit tests.
An API key is only needed for a live production run; tests use mocked providers.

```powershell
.\_SYSTEM\engines\python\.venv\Scripts\python.exe -m unittest discover -s _SYSTEM/tests -v
python tools/check_public_tree.py
```

Tests create disposable files under `_SYSTEM/reports`; setup creates this folder.
Full tests include real FFmpeg encodes. They do not establish continuous Blender
visual quality or validate the availability of live API models.

## What to change

Read `AGENTS.md` and `_SYSTEM/RULEBOOK.md` first. Active host modules live directly
under `_SYSTEM`; canonical schemas and SDKs live in `_SYSTEM/framework`.
Generated reports and work folders are evidence/cache, not source code.
Historical Ollama/Kaggle modules remain disabled; do not silently route production
away from the active API Director.

For a new action, update the registered vocabulary, validation, renderer behavior
and meaningful contract tests together. Preserve identity consistency, scene order,
input hashes, credential handling and offline render workers. Use a synthetic story
to demonstrate the capability; do not hand-author a user's current story and present
that as autonomous system behavior.

## Pull request checklist

- Describe the trigger, observed problem and resulting behavior.
- Explain the tests you ran and any visual check limitations.
- Include small synthetic repros; remove personal narration and story data.
- Keep third-party licenses/provenance for any new assets.
- Do not commit keys, encrypted backups, `.env`, model weights, environments or generated media.
- Never weaken a safety/quality gate just to obtain a successful render.

Prefer one focused change per pull request. Maintainers may ask for a smaller repro,
clearer screenshots or a renderer test before merging. Do not claim a universal
quality score without defined measurements and evidence.

## Finding a first task

[Good first issues](https://github.com/nirmallashkari/motion-2.0/issues?q=is%3Aopen%20label%3A%22good%20first%20issue%22)
are scoped for newcomers. Larger renderer/architecture changes are labelled
`help wanted`. Discuss substantial provider, contract or dependency changes in an
issue before investing in an implementation. Issues and Discussions are for project
collaboration; security reports belong in the private reporting channel.
