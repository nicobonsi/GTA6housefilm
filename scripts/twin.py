"""The 3D twin: build the house from house/plan.yaml and render the grey
"clay" guide video for every scene.

Run with Blender's Python, either way:
  python scripts/twin.py [--scenes s01,s02] [--draft]        (pip install bpy)
  blender -b -P scripts/twin.py -- [--scenes s01,s02] [--draft]

Writes:
  house/build/house.blend, house/build/house.glb   the model
  renders/guides/<scene>.mp4                       clay guide video (camera move)
  renders/guides/<scene>_first.png                 first frame, full resolution
  renders/guides/<scene>_track.json                host position per frame (for the minimap)
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import campath  # noqa: E402
import yaml  # noqa: E402

SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920)}
GREY = {"wall": (0.82, 0.82, 0.80, 1), "floor": (0.55, 0.55, 0.55, 1),
        "ceiling": (0.9, 0.9, 0.9, 1), "prop": (0.68, 0.68, 0.68, 1),
        "person": (0.40, 0.40, 0.42, 1), "ground": (0.48, 0.50, 0.48, 1)}


# ---------------------------------------------------------------- geometry
def box(name, x0, y0, z0, x1, y1, z1, kind, coll):
    if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
        return None
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = name
    o.scale = (x1 - x0, y1 - y0, z1 - z0)
    o.location = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
    o.color = GREY[kind]
    for c in o.users_collection:
        c.objects.unlink(o)
    coll.objects.link(o)
    return o


def wall_with_openings(name, axis, fixed, a0, a1, t, z0, H, openings, coll):
    """A straight wall from a0 to a1 along `axis` ('x' or 'y') at `fixed`,
    thickness t toward the room interior (t may be negative), with gaps."""
    ops = sorted(openings, key=lambda o: o["offset"])
    cur = a0
    segs = []
    for o in ops:
        s, e = a0 + o["offset"], a0 + o["offset"] + o["width"]
        bot, top = o.get("bottom", 0.0), o.get("top", 2.1)
        segs.append((cur, s, 0, H))          # solid before the opening
        segs.append((s, e, 0, bot))          # below (window sill)
        segs.append((s, e, top, H))          # above (lintel)
        cur = e
    segs.append((cur, a1, 0, H))
    f0, f1 = sorted((fixed, fixed + t))
    for i, (s, e, zb, zt) in enumerate(segs):
        if axis == "x":
            box(f"{name}.{i}", s, f0, z0 + zb, e, f1, z0 + zt, "wall", coll)
        else:
            box(f"{name}.{i}", f0, s, z0 + zb, f1, e, z0 + zt, "wall", coll)


def build_house(plan):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    H = plan.get("wall_height", 2.7)
    t = plan.get("wall_thickness", 0.12)
    floors = {f["id"]: f for f in plan["floors"]}
    house = bpy.data.collections.new("house")
    ceil = bpy.data.collections.new("ceilings")
    bpy.context.scene.collection.children.link(house)
    bpy.context.scene.collection.children.link(ceil)
    for r in plan["rooms"]:
        z = floors[r["floor"]]["z"]
        x, y, w, d = r["rect"]
        kind = "ground" if r.get("outdoor") else "floor"
        box(f"{r['id']}.floor", x, y, z - 0.1, x + w, y + d, z, kind, house)
        if r.get("outdoor"):
            continue
        box(f"{r['id']}.ceiling", x, y, z + H, x + w, y + d, z + H + 0.1, "ceiling", ceil)
        ops = {k: [] for k in "nsew"}
        for o in r.get("openings", []):
            ops[o["wall"]].append(o)
        wall_with_openings(f"{r['id']}.s", "x", y, x, x + w, t, z, H, ops["s"], house)
        wall_with_openings(f"{r['id']}.n", "x", y + d, x, x + w, -t, z, H, ops["n"], house)
        wall_with_openings(f"{r['id']}.w", "y", x, y, y + d, t, z, H, ops["w"], house)
        wall_with_openings(f"{r['id']}.e", "y", x + w, y, y + d, -t, z, H, ops["e"], house)
    rooms = {r["id"]: r for r in plan["rooms"]}
    for p in plan.get("props", []):
        z = floors[rooms[p["room"]]["floor"]]["z"]
        x, y, w, d = p["rect"]
        zb = p.get("z", 0.0)
        box(f"prop.{p['name']}", x, y, z + zb, x + w, y + d, z + zb + p["h"], "prop", house)
    return house


def person(name, x, y, z, heading, height=1.75):
    """Clay stand-in: body capsule + head + a nose block showing the facing."""
    coll = bpy.data.collections.get("people") or bpy.data.collections.new("people")
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    root = bpy.data.objects.new(name, None)
    coll.objects.link(root)
    parts = []
    bpy.ops.mesh.primitive_cylinder_add(radius=0.2, depth=height * 0.8,
                                        location=(0, 0, height * 0.4))
    parts.append(bpy.context.active_object)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.13, location=(0, 0, height * 0.87))
    parts.append(bpy.context.active_object)
    bpy.ops.mesh.primitive_cube_add(size=0.06, location=(0.13, 0, height * 0.87))
    parts.append(bpy.context.active_object)
    for p in parts:
        p.color = GREY["person"]
        for c in p.users_collection:
            c.objects.unlink(p)
        coll.objects.link(p)
        p.parent = root
    root.location = (x, y, z)
    root.rotation_euler = (0, 0, heading)
    return root


# ---------------------------------------------------------------- rendering
def setup_render(w, h, fps, draft):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "OBJECT"
    sc.display.shading.show_cavity = True
    sc.display.shading.show_shadows = True
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 50 if draft else 100
    sc.render.fps = fps
    sc.render.image_settings.file_format = "PNG"
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.color = (0.16, 0.17, 0.19)


def render_scene(proj, plan, scene, outdir, draft):
    sc = bpy.context.scene
    floors = {f["id"]: f for f in plan["floors"]}
    rooms = {r["id"]: r for r in plan["rooms"]}
    room = rooms[scene["room"]]
    z = floors[room["floor"]]["z"]
    fps = proj.get("fps", 24)
    w, h = SIZES[proj.get("aspect", "16:9")]
    setup_render(w, h, fps, draft)

    # fresh people for this scene
    ppl = bpy.data.collections.get("people")
    if ppl:
        for o in list(ppl.objects):
            bpy.data.objects.remove(o)
    track = campath.host_track(scene["path"], scene["seconds"], fps,
                               scene.get("facing", 90))
    host = person("host", *track[0][:2], z, track[0][2])
    for cid, pos in (scene.get("place") or {}).items():
        x, y = pos[:2]
        face = math.radians(pos[2]) if len(pos) > 2 else math.atan2(
            track[0][1] - y, track[0][0] - x)
        person(cid, x, y, z, face)

    cam_data = bpy.data.cameras.get("cam") or bpy.data.cameras.new("cam")
    cam_data.lens = scene.get("camera", {}).get("lens", 24)
    cam = bpy.data.objects.get("cam") or bpy.data.objects.new("cam", cam_data)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    cam.animation_data_clear()
    host.animation_data_clear()
    cam.rotation_mode = "QUATERNION"

    ctrack = campath.camera_track(track, scene.get("camera", {}))
    for f, ((x, y, hd), (cp, lp)) in enumerate(zip(track, ctrack), start=1):
        host.location = (x, y, z)
        host.rotation_euler = (0, 0, hd)
        host.keyframe_insert("location", frame=f)
        host.keyframe_insert("rotation_euler", frame=f)
        c = Vector((cp[0], cp[1], z + cp[2]))
        l = Vector((lp[0], lp[1], z + lp[2]))
        cam.location = c
        cam.rotation_quaternion = (l - c).to_track_quat("-Z", "Y")
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_quaternion", frame=f)
    sc.frame_start, sc.frame_end = 1, len(track)

    sid = scene["id"]
    frames = outdir / f"_{sid}_frames"
    shutil.rmtree(frames, ignore_errors=True)
    frames.mkdir(parents=True)
    sc.render.filepath = str(frames / "f_")
    bpy.ops.render.render(animation=True)
    first = sorted(frames.glob("f_*.png"))[0]
    shutil.copy(first, outdir / f"{sid}_first.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", str(frames / "f_%04d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                    str(outdir / f"{sid}.mp4")], check=True)
    shutil.rmtree(frames)
    (outdir / f"{sid}_track.json").write_text(json.dumps({
        "room": scene["room"], "floor": room["floor"], "fps": fps,
        "host": [[round(x, 3), round(y, 3), round(hd, 3)] for x, y, hd in track]}))
    print(f"  {sid}: {len(track)} frames -> {outdir / (sid + '.mp4')}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=ROOT / "project.yaml")
    ap.add_argument("--plan", default=ROOT / "house" / "plan.yaml")
    ap.add_argument("--scenes", default="", help="comma-separated scene ids (default: all)")
    ap.add_argument("--draft", action="store_true", help="half resolution, faster")
    ap.add_argument("--model-only", action="store_true", help="build the house, render nothing")
    a = ap.parse_args(argv)

    proj = yaml.safe_load(Path(a.project).read_text())
    plan = yaml.safe_load(Path(a.plan).read_text())
    build_house(plan)
    build = ROOT / "house" / "build"
    build.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(build / "house.blend"))
    bpy.ops.export_scene.gltf(filepath=str(build / "house.glb"))
    print(f"house model -> {build}")
    if a.model_only:
        return
    want = set(filter(None, a.scenes.split(",")))
    outdir = ROOT / "renders" / "guides"
    outdir.mkdir(parents=True, exist_ok=True)
    for s in proj["scenes"]:
        if not want or s["id"] in want:
            render_scene(proj, plan, s, outdir, a.draft)


if __name__ == "__main__":
    main()
