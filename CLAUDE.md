# Project notes for Claude

Pipeline (see README): house/plan.yaml -> scripts/twin.py (clay guides) -> AI stills and clips (manual, prompts from scripts/build_prompts.py) -> scripts/assemble.py (HUD + sound).

- `project.yaml` (film) and `house/plan.yaml` (house) are the single sources of truth. Never hard-code scene or room data in scripts.
- `scripts/campath.py` is shared by twin.py (Blender) and assemble.py (minimap). Camera and host-path maths live only there.
- After editing either YAML, run `python scripts/build_prompts.py` and commit the regenerated `prompts/`.
- twin.py runs under Blender's Python (`pip install bpy`, matching Python version, or `blender -b -P scripts/twin.py --`). Headless Linux needs Mesa EGL (`libegl1 libgl1-mesa-dri`) for the Workbench engine.
- Test with clay guides or ffmpeg `testsrc` clips; never commit media.
- Media of real people and the house (`characters/`, `locations/`, `renders/`, `music/`, `sfx/`, `output/`, `house/build/`) is git-ignored on purpose. Do not un-ignore it.
- Keep prompts and cards free of real game logos, titles and character names.
- When transcribing floor plans into plan.yaml: a door between two rooms must be cut in both rooms' walls.
