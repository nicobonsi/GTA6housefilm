# GTA6 House Film

A trailer-style short film set in our own house, starring our own people, in a
stylized open-world crime-saga look: neon sunset palette, painted key art,
title cards between shots, one big music track.

> **Status:** project skeleton. The two reference links
> (5warm.ai "house-film" lab and the "GTA6PARTY" video) could not be opened
> from the setup session, so the pipeline below is the standard
> reference-photos → AI image → AI video → edit workflow, **not** a copy of
> theirs. Once the references are readable, compare and adjust.

## How it works

```
your photos ──► stylized start frame per shot ──► 3-6 s video clip per shot ──► assembled trailer
 (people,          (image model + ref photos       (image-to-video model)        (scripts/assemble.py:
  rooms)            + prompt from project.yaml)                                    cards, music, export)
```

Everything is driven by **`project.yaml`**: title, look, characters, locations
and the shot list. Two scripts do the mechanical parts:

| Script | What it does |
|---|---|
| `scripts/build_prompts.py` | Turns `project.yaml` into a copy-paste prompt for every shot (`prompts/SHEET.md`, plus one `.txt` per shot). |
| `scripts/assemble.py` | Takes `renders/clips/<shot>.mp4`, crops to 16:9 or 9:16, adds the title and interstitial cards, lays the music under it and writes `output/film.mp4`. |

The generation itself (image and video models) happens in the providers' web
apps. That keeps it at zero code and lets you re-roll shots by eye, which you
will do a lot.

## Step by step

### 1. Gather references (about 1 hour)
- `characters/<id>/`: 3-10 photos per person (see `characters/README.md`).
- `locations/<id>/`: photos and a walk-through video per room (see `locations/README.md`).
- These folders are git-ignored, so faces and your floor plan don't end up on GitHub.

### 2. Write the film (about 30 min)
Edit `project.yaml`:
- names and outfits in `characters`
- the rooms you'll use in `locations`
- the shot list: 20-30 shots of 3-6 s each gives a 60-90 s trailer.
  The trailer formula: establishing shots of the house → one "character intro"
  shot per person, each with a name card → escalating party/action shots →
  a black card → one last gag shot → title.

Then:
```bash
pip install -r requirements.txt
python scripts/build_prompts.py
```
Open `prompts/SHEET.md`.

### 3. Make the start frames (the important step)
For each shot, give an image model the prompt **plus** the reference photos
listed for that shot, and save the best result as `renders/frames/<shot>.png`.

Use a model that takes several reference images and keeps faces consistent.
As of late 2026 the strong options are Google's Gemini image models, OpenAI's
image model in ChatGPT, and FLUX Kontext. Confidence: moderate; this field
changes monthly, so test two of them on shot 2 and keep the winner.

Tips:
- First make one **character sheet** per person (front, side, full body in
  the style) and use that sheet as the reference for all later shots. It
  locks the look far better than raw photos.
- Generate 4 variants per shot and pick one. Bad hands or faces mean re-roll,
  not fix later.

### 4. Animate each frame
Upload `renders/frames/<shot>.png` to an image-to-video model with
`prompts/<shot>_video.txt`, and save as `renders/clips/<shot>.mp4`.
Good options: Kling, Google Veo, Runway, Seedance, Hailuo. Expect to pay for
credits; at typical late-2026 prices a 25-shot trailer with re-rolls costs
roughly $30-$100 (confidence: low; check current pricing).

Optional house fly-throughs: scan rooms with a phone Gaussian-splat app
(Scaniverse, Polycam or Luma), record a camera path through the scan, then
restyle that clip with a video-to-video model. It's more work, but the camera
moves are really your house.

### 5. Music
Drop one track into `music/` (mp3 or wav). An AI music generator such as Suno
works for an original track; check its licence terms if you'll post publicly.

### 6. Assemble
```bash
python scripts/assemble.py                    # needs every clip
python scripts/assemble.py --allow-missing    # rough cut with black placeholders
```
Output is `output/film.mp4`. For finer timing or cutting to the beat, import
`renders/clips/` into CapCut, DaVinci Resolve or iMovie and use this only for
rough cuts.

## Notes
- Keep logos, the game's title treatment and its character names out of the
  prompts and cards: they're trademarks, and image models produce garbled text
  anyway. The look carries the reference by itself.
- `aspect: "9:16"` in `project.yaml` makes a vertical version for Reels or TikTok.
