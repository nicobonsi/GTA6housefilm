"""Shared path maths: where the host walks and where the camera sits, per frame.

Pure Python (no Blender), so the Blender guide renderer and the HUD minimap
compute exactly the same positions.

Coordinates are the floor-plan coordinates from house/plan.yaml, in metres:
x to the right, y up the page, z up from the floor of the scene's level.
"""
import math


def _seglens(pts):
    return [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]


def _ease(s):
    # gentle ease-in/out so the walk starts and stops like a person
    return s * s * (3 - 2 * s) * 0.6 + s * 0.4


def point_at(pts, s):
    """Point at fraction s (0..1) of the polyline's length."""
    if len(pts) == 1:
        return tuple(pts[0])
    lens = _seglens(pts)
    total = sum(lens) or 1e-9
    d = max(0.0, min(1.0, s)) * total
    for i, L in enumerate(lens):
        if d <= L or i == len(lens) - 1:
            f = 0 if L == 0 else min(1.0, d / L)
            a, b = pts[i], pts[i + 1]
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        d -= L


def host_track(path, seconds, fps, facing_deg=90.0):
    """Per-frame (x, y, heading_rad) for the host walking `path`."""
    n = max(1, round(seconds * fps))
    pts = [tuple(p) for p in path]
    out = []
    for i in range(n):
        s = _ease(i / max(1, n - 1))
        x, y = point_at(pts, s)
        out.append([x, y])
    # heading from motion, smoothed; stationary -> facing_deg
    head = math.radians(facing_deg)
    hx, hy = math.cos(head), math.sin(head)
    track = []
    for i, (x, y) in enumerate(out):
        j = min(len(out) - 1, i + 3)
        k = max(0, j - 6)
        dx, dy = out[j][0] - out[k][0], out[j][1] - out[k][1]
        if math.hypot(dx, dy) > 1e-3:
            m = math.hypot(dx, dy)
            hx, hy = hx * 0.8 + dx / m * 0.2, hy * 0.8 + dy / m * 0.2
            m = math.hypot(hx, hy)
            hx, hy = hx / m, hy / m
        track.append((x, y, math.atan2(hy, hx)))
    # backfill the first frames so a walk doesn't start facing the default
    if len(track) > 1 and len(path) > 1:
        dx, dy = path[1][0] - path[0][0], path[1][1] - path[0][1]
        h0 = math.atan2(dy, dx)
        for i in range(min(4, len(track))):
            if math.hypot(out[min(len(out) - 1, i + 3)][0] - out[i][0],
                          out[min(len(out) - 1, i + 3)][1] - out[i][1]) < 1e-3:
                track[i] = (track[i][0], track[i][1], h0)
    return track


def camera_track(track, cam):
    """Per-frame (cam_xyz, look_xyz) relative to the scene's floor level.

    cam modes:
      chase  - behind the host, following (the game third-person view)
      lead   - in front of the host, walking backwards, looking at the face
      static - fixed: cam.pos [x,y,z] and cam.look [x,y,z]
    """
    mode = cam.get("mode", "chase")
    if mode == "static":
        p, l = tuple(cam["pos"]), tuple(cam["look"])
        return [(p, l)] * len(track)
    dist = cam.get("dist", 2.4)
    height = cam.get("height", 1.75)
    look_h = cam.get("look_height", 1.35)
    lead = cam.get("lead", 1.0)
    side = cam.get("side", 0.35)  # over-the-shoulder offset to the right
    sign = 1 if mode == "chase" else -1
    out = []
    sx = sy = None
    for x, y, h in track:
        dx, dy = math.cos(h), math.sin(h)
        # right-hand perpendicular for the shoulder offset
        rx, ry = dy, -dx
        cx = x - sign * dx * dist + rx * side
        cy = y - sign * dy * dist + ry * side
        # damped camera, like a spring arm
        if sx is None:
            sx, sy = cx, cy
        else:
            sx, sy = sx + (cx - sx) * 0.25, sy + (cy - sy) * 0.25
        lx, ly = x + sign * dx * lead * 0.3, y + sign * dy * lead * 0.3
        out.append(((sx, sy, height), (lx, ly, look_h)))
    return out
