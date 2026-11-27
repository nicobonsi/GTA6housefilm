# GTA6 House Film

A game-trailer-style party film of our real house, starring our real people:
third-person camera following the host room by room, with a minimap, a cash
counter, freeze-frame character cards, a drinks wheel, achievement toasts and
"MISSION COMPLETE" at the end.

Modelled on Swarm Labs' [House film](https://5warm.ai/labs/house-film/)
(their finished film: about 75 s, 1080×608, 24 fps, about 20 shots).

## Their method, and what this repo automates

| # | Stage | Their tools | Here |
|---|---|---|---|
| 1 | Floor plans + about 50 phone photos | phone | `house/plan.yaml`, `locations/`, `characters/` |
| 2 | 3D twin; a grey "clay" chase-cam video per room | Blender, Cycles | **`scripts/twin.py`**: builds the house from the plan and renders every guide |
| 3 | AI still from guide frame + cast photos | Gemini 3 Pro Image (Nano Banana Pro) | **`scripts/build_prompts.py`**: exact uploads and prompts per scene |
| 4 | Motion: still + guide video → clip | Higgsfield, Seedance 2.5 | same sheet; you run it on Higgsfield |
| 5 | Game-trailer edit: HUD, minimap, cash, drinks wheel, character cards | FilmCraft / EffectCraft (their own) | **`scripts/assemble.py`** + `scripts/hud.py` |
| 6 | Sound: music muffled in hallways, opening up in rooms; SFX | Fish Audio, ElevenLabs, Whisper | `assemble.py` muffles music per scene and drops SFX on events |
| 7 | Crew: agents + approval of every paid step | Claude agents | Claude Code in this repo |

The key idea in their method is the **3D guide**. A plain AI video model
invents rooms that drift and walls that move. Rendering the camera path
through a model of the actual house first, then giving the AI the guide's
first frame (for the still) and the guide video (for the motion), keeps the
real layout.

## Folder map

```
project.yaml          the film: cast, scenes, camera paths, HUD events
house/plan.yaml       the house: floors, rooms, doors, windows, furniture (metres)
characters/<id>/      photos of each person (+ card.png for the intro card)   [git-ignored]
locations/<room>/     photos of each room                                     [git-ignored]
renders/guides/       clay guide videos + first frames (from twin.py)         [git-ignored]
renders/stills/       AI stills you save                                      [git-ignored]
renders/clips/        AI clips you save                                       [git-ignored]
music/  sfx/          one music track; optional sound effects                 [git-ignored]
output/film.mp4       the film                                                [git-ignored]
brand/title.png       optional title-card art (else a text title is drawn)
```

## Setup (once)

```bash
pip install -r requirements.txt
```

You also need ffmpeg (on a Mac: `brew install ffmpeg`). For the 3D step you need
either the `bpy` package (`pip install bpy`, which needs the matching Python
version: Python 3.13 for bpy 5.3) or the Blender app; then use
`blender -b -P scripts/twin.py --` in place of `python scripts/twin.py`.

## Step by step

### 1. The real house (1-2 h)
- Floor plans: a photo or PDF of each level, with dimensions if you have them.
- About 50 phone photos: every room you'll use, from the corners and the doorway, lights on.
  Tidy first. See `locations/README.md`.
- 3-10 photos per person. See `characters/README.md`.

### 2. The 3D twin
Put the plan into `house/plan.yaml`: rooms are rectangles in metres, plus doors,
windows and big furniture. (The current file is a demo house.) Claude can do
this from photos of the floor plans; that's the quickest route.

```bash
python scripts/twin.py --draft          # quick half-resolution pass
python scripts/twin.py                  # full resolution, once paths look right
```

Then write the scenes in `project.yaml`: for each one, the room, the host's
walking path (points in plan metres), where the guests stand, and the camera.
Re-run and watch `renders/guides/*.mp4` until every camera move works.
Tip: the chase camera sits `dist` metres behind the host, so start each walk at
least that far from the wall behind it (or shorten `dist`), otherwise the first
frames look at the inside of a wall.

**Watch the free animatic now:** `python scripts/assemble.py` cuts the whole
film from the clay guides, with the full HUD. Fix the timing here, before
paying for any AI.

### 3. Stills (Nano Banana Pro or another multi-reference image model)
```bash
python scripts/build_prompts.py
```
Follow `prompts/SHEET.md` scene by scene: upload the guide's first frame
**first**, then room photos, then the people's photos, and paste the prompt.
Check faces against the photos and walls against the guide before moving on.
Do the character-card portraits from the same sheet.

### 4. Motion (Seedance on Higgsfield, or similar)
Per scene: the still as start frame + the guide video as motion reference +
the video prompt. Do **one scene as a pilot** before batch-running the rest
(they capped the price of every paid run and approved each one).

### 5. Music and sound
- One track in `music/` (for an original track, Suno or similar; check its licence before posting publicly).
- `music: muffled` scenes get a low-pass filter and lower volume, like hearing
  the party from the hallway; `open` scenes get the full mix.
- Optional effects: add `sfx: sfx/whoosh.wav` to any event.

### 6. Final cut
```bash
python scripts/assemble.py
```
`output/film.mp4`. Finished clips replace clay guides automatically.

## Cost and time (estimates; confidence low to moderate)
- Stills: a few dollars on a paid Gemini or Higgsfield plan.
- Video: about 20 clips × 5 s, plus re-rolls. Plan on **$50-$150** in
  Higgsfield or Seedance credits. Check current prices before you start.
- Time: a weekend for one person, most of it on stills and re-rolls.

## Rules we keep
- Photos of people and the house never go to GitHub (`.gitignore`).
- No real game logos, title treatments or character names in prompts or cards.
  The look sells it, and it avoids trademark trouble if the film is shared.
