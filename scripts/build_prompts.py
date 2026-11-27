#!/usr/bin/env python3
"""Turn project.yaml into the exact uploads + prompts for every AI step.

  prompts/SHEET.md             one page: per scene, what to upload and what to paste
  prompts/<scene>_still.txt    image model (e.g. Nano Banana Pro): guide frame + photos -> still
  prompts/<scene>_video.txt    video model (e.g. Seedance on Higgsfield): still + guide video -> clip
  prompts/card_<cast>.txt      illustrated portrait for each character intro card

Usage: python scripts/build_prompts.py
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load():
    proj = yaml.safe_load((ROOT / "project.yaml").read_text())
    plan = yaml.safe_load((ROOT / "house" / "plan.yaml").read_text())
    cast = {c["id"]: c for c in proj.get("cast", [])}
    rooms = {r["id"]: r for r in plan["rooms"]}
    errs, seen = [], set()
    for s in proj["scenes"]:
        if s["id"] in seen:
            errs.append(f"duplicate scene id {s['id']}")
        seen.add(s["id"])
        if s["room"] not in rooms:
            errs.append(f"{s['id']}: room '{s['room']}' is not in house/plan.yaml")
        for c in list(s.get("cast") or []) + list((s.get("place") or {}).keys()):
            if c not in cast:
                errs.append(f"{s['id']}: unknown cast id '{c}'")
        for e in s.get("events") or []:
            if e["type"] == "card" and e.get("who") not in cast:
                errs.append(f"{s['id']}: card for unknown cast id '{e.get('who')}'")
            if e["at"] > s["seconds"]:
                errs.append(f"{s['id']}: event at {e['at']}s is after the scene ends")
    if errs:
        sys.exit("errors:\n  " + "\n  ".join(errs))
    return proj, plan, cast, rooms


def who_line(s, cast):
    ids = list(dict.fromkeys(list(s.get("cast") or []) + list((s.get("place") or {}).keys())))
    lines = []
    for i, cid in enumerate(ids):
        c = cast[cid]
        where = ("the figure the camera follows, seen from behind/over the shoulder"
                 if i == 0 and cid == (s.get("cast") or [None])[0]
                 else "the other grey figure in the guide frame")
        lines.append(f"- {c['name']} ({where}): {c['look']}. Face and build exactly as in "
                     f"the photos of {c['name']}.")
    return ids, "\n".join(lines)


def still_prompt(proj, s, cast, room):
    _, who = who_line(s, cast)
    return f"""Image 1 is a grey 3D render of a real room. Keep its camera, lens, framing and
the position of every wall, door, window and piece of furniture exactly. Each
grey figure in image 1 is a person; put the people listed below exactly there.

Turn it into a finished film frame of the {room['name'].lower()} during a house party.
Use the room photos for real materials, colours and light fittings.
Use the people photos for faces; they must be recognisable.

Scene: {s['action']}.
People:
{who}

Style: {proj['style'].strip()}
No text, no logos, no UI, no watermark. Aspect ratio {proj.get('aspect', '16:9')}."""


def video_prompt(proj, s, cast):
    return f"""Start frame: the attached still. Camera motion: follow the attached grey guide
video exactly, frame by frame (same path, speed and framing); the guide is only
for motion and layout, never for colours or textures.
Action: {s['action']}.
Keep every face identical to the start frame, keep walls and furniture fixed,
natural walking, party extras moving in the background, no morphing,
no text or UI. {s['seconds']} seconds, {proj.get('fps', 24)} fps."""


def card_prompt(c):
    return f"""Illustrated character portrait of the person in the attached photos, in the style
of a glossy open-world crime game loading screen: bold painted illustration,
clean ink lines, sunset gradient sky of pink, orange and purple with palm
trees, dramatic rim light. Waist-up, confident pose, looking at the viewer,
{c['look']}. Keep the face clearly recognisable. Portrait 3:4. No text, no logo."""


def main():
    proj, plan, cast, rooms = load()
    out = ROOT / "prompts"
    out.mkdir(exist_ok=True)
    for old in out.glob("*.txt"):
        old.unlink()
    sheet = [f"# {proj['title']}: prompt sheet", ""]
    total = 0
    for s in proj["scenes"]:
        room = rooms[s["room"]]
        ids, _ = who_line(s, cast)
        sp, vp = still_prompt(proj, s, cast, room), video_prompt(proj, s, cast)
        (out / f"{s['id']}_still.txt").write_text(sp + "\n")
        (out / f"{s['id']}_video.txt").write_text(vp + "\n")
        total += s["seconds"]
        people = ", ".join(f"`{cast[c]['refs']}`" for c in ids) or "none"
        sheet += [
            f"## {s['id']}: {room['name']} ({s['seconds']} s)", "",
            "**Step A: still** (image model)", "",
            f"Upload: `renders/guides/{s['id']}_first.png` FIRST, then 2-3 photos from "
            f"`locations/{s['room']}/`, then photos from {people}.", "",
            "```", sp, "```", "",
            f"Check: faces match the photos, walls/doors match the guide. Save as `renders/stills/{s['id']}.png`.", "",
            "**Step B: motion** (video model)", "",
            f"Upload: `renders/stills/{s['id']}.png` as start frame and `renders/guides/{s['id']}.mp4` "
            "as motion/camera reference.", "",
            "```", vp, "```", "",
            f"Save as `renders/clips/{s['id']}.mp4`.", "",
        ]
    cards = [c for c in cast.values() if c.get("card")]
    if cards:
        sheet += ["## Character cards", ""]
        for c in cards:
            cp = card_prompt(c)
            (out / f"card_{c['id']}.txt").write_text(cp + "\n")
            sheet += [f"### {c['name']}", "", f"Upload 3-5 photos from `{c['refs']}`.", "",
                      "```", cp, "```", "", f"Save as `{c['refs'].rstrip('/')}/card.png`.", ""]
    sheet.insert(1, f"{len(proj['scenes'])} scenes, {total} s of footage before freezes and cards.")
    (out / "SHEET.md").write_text("\n".join(sheet))
    print(f"Wrote prompts for {len(proj['scenes'])} scenes and {len(cards)} cards to {out}")


if __name__ == "__main__":
    main()
