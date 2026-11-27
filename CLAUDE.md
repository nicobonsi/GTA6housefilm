# Project notes for Claude

- `project.yaml` is the single source of truth (characters, locations, shots). Scripts read it; never hard-code shot data elsewhere.
- After editing `project.yaml`, run `python scripts/build_prompts.py` and commit the regenerated `prompts/`.
- Test `scripts/assemble.py` with generated test clips (ffmpeg `testsrc`) in a temp dir, never with files committed to the repo.
- Media of real people and the house (`characters/`, `locations/`, `renders/`, `music/`, `output/`) is git-ignored on purpose. Do not un-ignore it or commit such files.
- Keep prompts free of real game logos, titles and character names.
