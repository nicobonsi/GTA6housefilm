#!/usr/bin/env python3
"""Turn project.yaml into ready-to-paste prompts for every shot.

Writes:
  prompts/<shot>_image.txt   -> paste into the image model (with the ref photos)
  prompts/<shot>_video.txt   -> paste into the image-to-video model
  prompts/SHEET.md           -> one page with every shot, refs and prompts

Usage: python scripts/build_prompts.py [path/to/project.yaml]
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    data = yaml.safe_load(Path(path).read_text())
    chars = {c["id"]: c for c in data.get("characters", [])}
    locs = {l["id"]: l for l in data.get("locations", [])}
    errors = []
    seen = set()
    for s in data.get("shots", []):
        if s["id"] in seen:
            errors.append(f"duplicate shot id {s['id']}")
        seen.add(s["id"])
        if s["location"] not in locs:
            errors.append(f"{s['id']}: unknown location '{s['location']}'")
        for c in s.get("characters") or []:
            if c not in chars:
                errors.append(f"{s['id']}: unknown character '{c}'")
    if errors:
        sys.exit("project.yaml errors:\n  " + "\n  ".join(errors))
    return data, chars, locs


def image_prompt(data, shot, chars, locs):
    loc = locs[shot["location"]]
    people = [chars[c] for c in shot.get("characters") or []]
    parts = [data["style"].strip()]
    parts.append(f"Setting: {loc['description']}.")
    for i, p in enumerate(people, 1):
        parts.append(
            f"Character {i} ({p['name']}): {p['look']}; keep the face identical "
            f"to the reference photos of {p['name']}."
        )
    parts.append(f"Action: {shot['action']}.")
    parts.append(f"Framing: {shot['camera']}. Aspect ratio {data['aspect']}.")
    parts.append(f"Avoid: {data['negative'].strip()}")
    return "\n".join(parts)


def video_prompt(data, shot):
    return (
        f"{shot['action']}. Camera: {shot['camera']}. "
        f"Duration {shot['seconds']} seconds. Keep the art style, faces and "
        f"lighting of the start frame exactly; smooth cinematic motion, no "
        f"morphing, no text."
    )


def refs_for(shot, chars, locs):
    refs = [locs[shot["location"]]["refs"]]
    refs += [chars[c]["refs"] for c in shot.get("characters") or []]
    return refs


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else ROOT / "project.yaml"
    data, chars, locs = load(path)
    out = ROOT / "prompts"
    out.mkdir(exist_ok=True)
    sheet = [f"# {data['title']} - prompt sheet\n"]
    total = 0
    for s in data["shots"]:
        ip = image_prompt(data, s, chars, locs)
        vp = video_prompt(data, s)
        (out / f"{s['id']}_image.txt").write_text(ip + "\n")
        (out / f"{s['id']}_video.txt").write_text(vp + "\n")
        total += s["seconds"]
        sheet += [
            f"## {s['id']} - {locs[s['location']]['name']} ({s['seconds']}s)",
            f"Card before shot: {s.get('card') or '-'}",
            "Reference folders: " + ", ".join(f"`{r}`" for r in refs_for(s, chars, locs)),
            "Save start frame as: `renders/frames/%s.png`" % s["id"],
            "Save clip as: `renders/clips/%s.mp4`\n" % s["id"],
            "**Image prompt**\n```\n" + ip + "\n```",
            "**Video prompt**\n```\n" + vp + "\n```\n",
        ]
    sheet.insert(1, f"{len(data['shots'])} shots, {total}s of footage before cards.\n")
    (out / "SHEET.md").write_text("\n".join(sheet))
    print(f"Wrote prompts for {len(data['shots'])} shots ({total}s) to {out}")


if __name__ == "__main__":
    main()
