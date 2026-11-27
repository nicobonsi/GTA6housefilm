#!/usr/bin/env python3
"""Cut the trailer: every scene's clip + game HUD + freeze-frame events,
title and end cards, then music with per-room muffling and sound effects.

Per scene it uses, in order of preference:
  renders/clips/<scene>.mp4    the finished AI clip
  renders/guides/<scene>.mp4   the grey clay guide (a free animatic)
  a black placeholder

  python scripts/assemble.py                       -> output/film.mp4
  python scripts/assemble.py --scenes s02,s03      -> just those (quick check)
  python scripts/assemble.py --no-hud              -> clean cut, no overlays

Music: first .mp3/.wav in music/ (or --music). Sound effects: give an event
`sfx: sfx/whoosh.wav` and it is played when the event starts.
Requires ffmpeg on PATH, plus: pip install -r requirements.txt
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import campath  # noqa: E402
from hud import Hud, ease  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
FREEZE = {"card", "wheel"}
TITLE_SECONDS, END_SECONDS, OUTRO_SECONDS = 2.5, 3.0, 2.0


def reader(src, W, H, fps, seconds):
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}"
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(src), "-vf", vf,
                          "-t", str(seconds), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield Image.frombytes("RGB", (W, H), b)
    p.wait()


class Writer:
    def __init__(self, path, W, H, fps):
        self.fps, self.n = fps, 0
        self.p = subprocess.Popen(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
             "-crf", "18", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)

    def put(self, img):
        self.p.stdin.write(img.tobytes())
        self.n += 1

    @property
    def t(self):
        return self.n / self.fps

    def close(self):
        self.p.stdin.close()
        if self.p.wait():
            sys.exit("ffmpeg encoder failed")


def placeholder(W, H, text, hud):
    img = Image.new("RGB", (W, H), (12, 12, 16))
    hud._center_text(img, text, 40, H * 0.47, fill=(160, 160, 170))
    return img


def scene_frames(scene, W, H, fps, hud):
    """Source frames for a scene, padded/trimmed to its planned length."""
    n = max(1, round(scene["seconds"] * fps))
    for folder, label in (("clips", "clip"), ("guides", "clay guide")):
        src = ROOT / "renders" / folder / f"{scene['id']}.mp4"
        if src.exists():
            frames = list(reader(src, W, H, fps, scene["seconds"]))
            if frames:
                frames += [frames[-1]] * (n - len(frames))
                return frames[:n], label
    ph = placeholder(W, H, f"{scene['id']}  ·  {scene['room']}  ·  no clip yet", hud)
    return [ph] * n, "placeholder"


def track_for(scene, fps):
    tj = ROOT / "renders" / "guides" / f"{scene['id']}_track.json"
    if tj.exists():
        return json.loads(tj.read_text())["host"]
    return campath.host_track(scene["path"], scene["seconds"], fps, scene.get("facing", 90))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=ROOT / "project.yaml")
    ap.add_argument("--plan", default=ROOT / "house" / "plan.yaml")
    ap.add_argument("--scenes", default="")
    ap.add_argument("--music", default=None)
    ap.add_argument("--out", default=ROOT / "output" / "film.mp4")
    ap.add_argument("--no-hud", action="store_true")
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")

    proj = yaml.safe_load(Path(a.project).read_text())
    plan = yaml.safe_load(Path(a.plan).read_text())
    W, H = SIZES[proj.get("aspect", "16:9")]
    fps = proj.get("fps", 24)
    hud = Hud(proj, plan, W, H, ROOT)
    want = set(filter(None, a.scenes.split(",")))
    scenes = [s for s in proj["scenes"] if not want or s["id"] in want]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    silent = out.with_suffix(".silent.mp4")

    w = Writer(silent, W, H, fps)
    muffled, sfx = [], []
    cash_prev, cash_now = None, None
    last = None
    for s in scenes:
        frames, used = scene_frames(s, W, H, fps, hud)
        track = track_for(s, fps)
        start = w.t
        cash_prev, cash_now = cash_now, s.get("cash", cash_now)
        evs = sorted(s.get("events") or [], key=lambda e: e["at"])
        freezes = [e for e in evs if e["type"] in FREEZE]
        overlays = [e for e in evs if e["type"] not in FREEZE]
        fired = set()

        def cash_value(t_out):
            if cash_now is None:
                return None
            if cash_prev is None or cash_prev == cash_now:
                return cash_now
            return cash_prev + (cash_now - cash_prev) * ease(t_out / 0.8)

        def decorate(img, t_src, show_map=True):
            if a.no_hud:
                return img
            i = min(len(track) - 1, int(t_src * fps))
            if show_map:
                hud.minimap(img, s["room"], *track[i][:3])
            hud.cash(img, cash_value(w.t - start))
            for e in overlays:
                if e["type"] == "toast":
                    hud.toast(img, e, t_src - e["at"])
                elif e["type"] == "text":
                    hud.text(img, e, t_src - e["at"])
            return img

        for i, fr in enumerate(frames):
            t_src = i / fps
            for e in overlays:
                if e.get("sfx") and id(e) not in fired and t_src >= e["at"]:
                    fired.add(id(e))
                    sfx.append((w.t, ROOT / e["sfx"]))
            for e in freezes:
                if id(e) in fired or t_src < e["at"]:
                    continue
                fired.add(id(e))
                if e.get("sfx"):
                    sfx.append((w.t, ROOT / e["sfx"]))
                hold = e.get("hold", 2.0)
                for j in range(round(hold * fps)):
                    tf = j / fps
                    if a.no_hud:
                        img = fr.copy()
                    elif e["type"] == "card":
                        img = decorate(hud.card(fr, e, tf), t_src, show_map=False)
                    else:
                        img = decorate(hud.wheel(fr, e, tf), t_src)
                    w.put(img)
            img = decorate(fr.copy(), t_src)
            w.put(img)
            last = fr
        if s.get("music") == "muffled":
            muffled.append((start, w.t))
        print(f"  {s['id']}: {used}, {w.t - start:.1f}s")

        if s["id"] == proj.get("title_after") and not a.no_hud:
            for j in range(round(TITLE_SECONDS * fps)):
                w.put(hud.title_card(j / fps, TITLE_SECONDS))

    if last is not None and not a.no_hud:
        for j in range(round(END_SECONDS * fps)):
            w.put(hud.end_card(last, j / fps))
        for j in range(round(OUTRO_SECONDS * fps)):
            w.put(hud.title_card(j / fps, OUTRO_SECONDS))
    total = w.t
    w.close()

    music = Path(a.music) if a.music else next(
        (p for p in sorted((ROOT / "music").glob("*")) if p.suffix.lower() in (".mp3", ".wav", ".m4a")), None)
    sfx = [(t, p) for t, p in sfx if p.exists()]
    if not music and not sfx:
        silent.replace(out)
        print(f"Wrote {out} ({total:.1f}s, no music found in music/)")
        return

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent)]
    chains, labels = [], []
    idx = 1
    if music:
        cmd += ["-i", str(music)]
        f = "volume=0.9"
        if muffled:
            en = "+".join(f"between(t,{a0:.2f},{b0:.2f})" for a0, b0 in muffled)
            f += f",lowpass=f=650:enable='{en}',volume=0.55:enable='{en}'"
        f += f",atrim=0:{total:.2f},afade=t=out:st={max(0, total - 2.5):.2f}:d=2.5"
        chains.append(f"[{idx}:a]{f}[m]")
        labels.append("[m]")
        idx += 1
    for t, p in sfx:
        cmd += ["-i", str(p)]
        ms = int(t * 1000)
        chains.append(f"[{idx}:a]adelay={ms}|{ms}[x{idx}]")
        labels.append(f"[x{idx}]")
        idx += 1
    chains.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
                  f"atrim=0:{total:.2f}[aout]")
    cmd += ["-filter_complex", ";".join(chains), "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("audio mix failed:\n" + r.stderr[-1500:])
    silent.unlink()
    print(f"Wrote {out} ({total:.1f}s, music: {music.name if music else 'none'}, sfx: {len(sfx)})")


if __name__ == "__main__":
    main()
