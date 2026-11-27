#!/usr/bin/env python3
"""Cut the final film from the generated clips with ffmpeg.

Reads project.yaml for shot order, cards, aspect and fps; takes
renders/clips/<shot>.mp4 for each shot; adds an opening title card, the
interstitial cards, a closing card, and the music track if present.

  python scripts/assemble.py                 # -> output/film.mp4
  python scripts/assemble.py --music music/track.mp3 --out output/v2.mp4
  python scripts/assemble.py --allow-missing # black placeholder for missing clips

Requires ffmpeg on PATH.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg failed:\n" + " ".join(cmd) + "\n" + r.stderr[-2000:])


def esc(text):
    # escape for ffmpeg drawtext
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\u2019")


def font():
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return None


def card(text, seconds, w, h, fps, dst):
    f = font()
    fontopt = f"fontfile='{f}':" if f else ""
    size = int(min(w, h) * 0.09)
    vf = (
        f"drawtext={fontopt}text='{esc(text)}':fontcolor=white:fontsize={size}:"
        f"x=(w-text_w)/2:y=(h-text_h)/2,"
        f"fade=t=in:st=0:d=0.3,fade=t=out:st={seconds - 0.3}:d=0.3"
    )
    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}:r={fps}:d={seconds}",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-vf", vf, "-t", str(seconds), "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dst),
    ])


def normalize(src, seconds, w, h, fps, dst):
    # scale-to-fill + center crop, fixed fps, trimmed to the planned length,
    # silent stereo track so every segment concatenates cleanly
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
          f"crop={w}:{h},fps={fps},setsar=1")
    run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf", vf, "-t", str(seconds), "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(dst),
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=ROOT / "project.yaml")
    ap.add_argument("--clips", default=ROOT / "renders" / "clips")
    ap.add_argument("--music", default=None, help="audio file laid under the film")
    ap.add_argument("--out", default=ROOT / "output" / "film.mp4")
    ap.add_argument("--card-seconds", type=float, default=1.5)
    ap.add_argument("--allow-missing", action="store_true")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    data = yaml.safe_load(Path(a.project).read_text())
    w, h = SIZES[data.get("aspect", "16:9")]
    fps = data.get("fps", 24)
    clips = Path(a.clips)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    missing = [s["id"] for s in data["shots"] if not (clips / f"{s['id']}.mp4").exists()]
    if missing and not a.allow_missing:
        sys.exit(f"missing clips in {clips}: {', '.join(missing)} "
                 "(use --allow-missing for black placeholders)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        segs = []

        def add_card(text, secs):
            p = tmp / f"seg{len(segs):03d}.mp4"
            card(text, secs, w, h, fps, p)
            segs.append(p)

        add_card(data["title"], 2.5)
        for s in data["shots"]:
            if s.get("card"):
                add_card(s["card"], a.card_seconds)
            p = tmp / f"seg{len(segs):03d}.mp4"
            src = clips / f"{s['id']}.mp4"
            if src.exists():
                normalize(src, s["seconds"], w, h, fps, p)
                segs.append(p)
            else:
                add_card(f"[{s['id']} missing]", s["seconds"])
        add_card(data.get("tagline", ""), 2.5)

        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in segs))
        joined = tmp / "joined.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c", "copy", str(joined)])

        music = Path(a.music) if a.music else None
        if music is None:
            found = sorted((ROOT / "music").glob("*.mp3")) + sorted((ROOT / "music").glob("*.wav"))
            music = found[0] if found else None
        if music:
            dur = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(joined)], capture_output=True, text=True).stdout)
            run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(joined), "-i", str(music),
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-af", f"afade=t=out:st={max(dur - 2, 0)}:d=2", "-t", str(dur),
                 "-c:a", "aac", str(out)])
        else:
            shutil.copy(joined, out)
    print(f"Wrote {out}" + ("" if not missing else f" (placeholders for {', '.join(missing)})"))


if __name__ == "__main__":
    main()
