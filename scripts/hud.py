"""Game-trailer overlays drawn with Pillow: cash counter, minimap with floor
ladder, notification toasts, freeze-frame character cards, the drinks wheel,
centred text, title and end cards.

All sizes are designed at 1080 px on the short side and scaled from there.
"""
import glob
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

PINK = (255, 64, 160)
ORANGE = (255, 150, 60)
GREEN = (120, 220, 110)
WARN = (255, 90, 60)
KIND_COLOR = {"achievement": PINK, "warning": WARN, "vehicle": PINK}

FONT_GLOBS = [
    "assets/fonts/*.ttf", "assets/fonts/*.otf",
    "/usr/share/fonts/**/Inter*Display*Bold.otf", "/usr/share/fonts/**/Inter*Bold.otf",
    "/usr/share/fonts/**/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
]


def ease(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def money(v):
    return f"${int(round(v)):,}"


class Hud:
    def __init__(self, proj, plan, W, H, root):
        self.proj, self.plan, self.W, self.H = proj, plan, W, H
        self.root = Path(root)
        self.k = min(W, H) / 1080
        self.floors = plan["floors"]
        self.rooms = {r["id"]: r for r in plan["rooms"]}
        self.cast = {c["id"]: c for c in proj.get("cast", [])}
        self._fonts = {}
        self._fontpath = self._find_font()
        self._card_art = {}

    # ---------------------------------------------------------- helpers
    def _find_font(self):
        for g in FONT_GLOBS:
            pat = g if g.startswith("/") or ":" in g else str(self.root / g)
            hits = sorted(glob.glob(pat, recursive=True))
            if hits:
                return hits[0]
        return None

    def font(self, size):
        size = max(8, int(size * self.k))
        if size not in self._fonts:
            self._fonts[size] = (ImageFont.truetype(self._fontpath, size) if self._fontpath
                                 else ImageFont.load_default(size=size))
        return self._fonts[size]

    def s(self, v):
        return int(v * self.k)

    def _gradient_text(self, img, text, size, cy, colors=(PINK, ORANGE), alpha=1.0):
        f = self.font(size)
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = d.textbbox((0, 0), text, font=f, stroke_width=self.s(4))
        w, h = x1 - x0, y1 - y0
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).text((-x0, -y0), text, font=f, fill=255)
        outline = Image.new("L", (w, h), 0)
        ImageDraw.Draw(outline).text((-x0, -y0), text, font=f, fill=255,
                                     stroke_width=self.s(4), stroke_fill=255)
        grad = Image.new("RGB", (w, h))
        gd = ImageDraw.Draw(grad)
        for yy in range(h):
            t = yy / max(1, h - 1)
            c = tuple(int(colors[0][i] + (colors[1][i] - colors[0][i]) * t) for i in range(3))
            gd.line([(0, yy), (w, yy)], fill=c)
        px, py = (self.W - w) // 2, int(cy - h / 2)
        a = lambda m: m.point(lambda v: int(v * alpha))  # noqa: E731
        img.paste((20, 10, 30), (px, py), a(outline))
        img.paste(grad, (px, py), a(mask))
        return py + h

    @staticmethod
    def _fade_paste(img, layer, xy, alpha):
        """Paste an RGBA layer with its alpha scaled (Pillow text ignores fill alpha)."""
        if alpha <= 0:
            return
        a = layer.getchannel("A")
        if alpha < 1:
            a = a.point(lambda v: int(v * alpha))
        img.paste(layer.convert("RGB"), xy, a)

    def _center_text(self, img, text, size, y, fill=(255, 255, 255), alpha=1.0, spacing=0):
        if spacing:
            text = (" " * spacing).join(text)
        f = self.font(size)
        sw = self.s(2)
        x0, y0, x1, y1 = ImageDraw.Draw(img).textbbox((0, 0), text, font=f, stroke_width=sw)
        layer = Image.new("RGBA", (x1 - x0 + 2, y1 - y0 + 2), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((-x0, -y0), text, font=f, fill=fill + (255,),
                                   stroke_width=sw, stroke_fill=(0, 0, 0, 160))
        self._fade_paste(img, layer, (int((self.W - layer.width) / 2), int(y + y0)), alpha)

    # ---------------------------------------------------------- always-on HUD
    def cash(self, img, value):
        if value is None or value < 0.5:
            return
        d = ImageDraw.Draw(img, "RGBA")
        f = self.font(54)
        txt = money(value)
        w = d.textlength(txt, font=f)
        d.text((self.W - w - self.s(44), self.s(30)), txt, font=f, fill=GREEN,
               stroke_width=self.s(3), stroke_fill=(0, 0, 0))

    def minimap(self, img, room_id, x, y, heading):
        room = self.rooms[room_id]
        floor = room["floor"]
        size, m = self.s(250), self.s(40)
        scale = 15 * self.k                     # px per metre
        tile = Image.new("RGBA", (size, size), (10, 10, 14, 210))
        d = ImageDraw.Draw(tile)
        cx = cy = size / 2

        def to_px(px, py):
            return cx + (px - x) * scale, cy - (py - y) * scale

        for r in self.plan["rooms"]:
            if r["floor"] != floor:
                continue
            rx, ry, rw, rd = r["rect"]
            a, b = to_px(rx, ry + rd), to_px(rx + rw, ry)
            if r.get("outdoor"):
                fill = (70, 120, 110, 255) if r["id"] == room_id else (45, 70, 65, 255)
            else:
                fill = (235, 235, 235, 255) if r["id"] == room_id else (150, 150, 155, 255)
            d.rectangle([a, b], fill=fill, outline=(20, 20, 24, 255), width=max(1, self.s(2)))
        # player arrow (map y is flipped)
        L = self.s(16)
        hx, hy = math.cos(heading), -math.sin(heading)
        pts = [(cx + hx * L, cy + hy * L),
               (cx - hx * L * 0.6 - hy * L * 0.6, cy - hy * L * 0.6 + hx * L * 0.6),
               (cx - hx * L * 0.25, cy - hy * L * 0.25),
               (cx - hx * L * 0.6 + hy * L * 0.6, cy - hy * L * 0.6 - hx * L * 0.6)]
        d.polygon(pts, fill=PINK, outline=(255, 255, 255))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        ox, oy = m, self.H - m - size
        ImageDraw.Draw(img, "RGBA").ellipse([ox - 4, oy - 4, ox + size + 3, oy + size + 3],
                                            outline=(255, 255, 255, 200), width=max(2, self.s(3)))
        img.paste(tile.convert("RGB"), (ox, oy), mask)
        # floor ladder
        d2 = ImageDraw.Draw(img, "RGBA")
        f = self.font(20)
        lx = ox + size + self.s(16)
        step = self.s(34)
        top = oy + size / 2 - step * len(self.floors) / 2
        for i, fl in enumerate(self.floors):
            ty = top + i * step
            w = d2.textlength(fl["name"], font=f)
            if fl["id"] == floor:
                d2.rounded_rectangle([lx - self.s(8), ty - self.s(4), lx + w + self.s(8), ty + self.s(26)],
                                     radius=self.s(8), fill=PINK + (235,))
                d2.text((lx, ty), fl["name"], font=f, fill=(255, 255, 255))
            else:
                d2.text((lx, ty), fl["name"], font=f, fill=(220, 220, 220, 200),
                        stroke_width=1, stroke_fill=(0, 0, 0, 160))

    # ---------------------------------------------------------- events
    def toast(self, img, ev, t):
        """t = seconds since the toast started. Visible for 3.2 s."""
        if t < 0 or t > 3.2:
            return
        slide = ease(t / 0.3)
        alpha = 1.0 if t < 2.9 else max(0.0, (3.2 - t) / 0.3)
        color = KIND_COLOR.get(ev.get("kind", "achievement"), PINK)
        label = ev.get("label", "ACHIEVEMENT UNLOCKED")
        fl, ft = self.font(18), self.font(34)
        d0 = ImageDraw.Draw(img)
        w = max(d0.textlength(label, font=fl), d0.textlength(ev["text"], font=ft)) + self.s(110)
        h = self.s(86)
        layer = Image.new("RGBA", (int(w) + 4, h + 4), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, "RGBA")
        ox = self.s(40) - (1 - slide) * (w + self.s(60))
        oy = self.s(36)
        x = y = 1
        A = 225
        d.rounded_rectangle([x, y, x + w, y + h], radius=self.s(10), fill=(18, 18, 24, A),
                            outline=color + (A,), width=max(1, self.s(2)))
        r = self.s(22)
        icx, icy = x + self.s(40), y + h / 2
        d.ellipse([icx - r, icy - r, icx + r, icy + r], fill=color + (A,))
        star = [(icx + r * 0.65 * math.cos(math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45),
                 icy - r * 0.65 * math.sin(math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.45))
                for i in range(10)]
        if ev.get("kind") == "warning":
            fb = self.font(30)
            bw = d.textlength("!", font=fb)
            d.text((icx - bw / 2, icy - self.s(19)), "!", font=fb, fill=(255, 255, 255, A))
        else:
            d.polygon(star, fill=(255, 255, 255, A))
        tx = x + self.s(76)
        d.text((tx, y + self.s(12)), label, font=fl, fill=color + (A,))
        d.text((tx, y + self.s(36)), ev["text"], font=ft, fill=(255, 255, 255, A))
        ix = int(ox)
        if -ix >= layer.width:  # still fully off-screen
            return
        if ix < 0:  # sliding in from off-screen
            layer = layer.crop((-ix, 0, layer.width, layer.height))
            ix = 0
        if layer.width > 0:
            self._fade_paste(img, layer, (ix, int(oy)), alpha)

    def text(self, img, ev, t):
        dur = ev.get("seconds", 2.5)
        if t < 0 or t > dur:
            return
        a = min(1.0, t / 0.4, (dur - t) / 0.4)
        self._center_text(img, ev["text"], 30, self.H * 0.47, alpha=max(0.0, a), spacing=1)

    def _art(self, cid):
        if cid in self._card_art:
            return self._card_art[cid]
        c = self.cast.get(cid, {})
        folder = self.root / (c.get("refs") or f"characters/{cid}/")
        cand = [folder / "card.png", folder / "card.jpg"]
        cand += sorted(p for p in folder.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
        art = None
        for p in cand:
            if p.exists():
                try:
                    art = Image.open(p).convert("RGB")
                    break
                except OSError:
                    continue
        if art is None:  # placeholder silhouette
            art = Image.new("RGB", (600, 800), (120, 90, 160))
            d = ImageDraw.Draw(art)
            d.ellipse([200, 150, 400, 380], fill=(60, 40, 90))
            d.rounded_rectangle([130, 400, 470, 820], radius=120, fill=(60, 40, 90))
        self._card_art[cid] = art
        return art

    def card(self, frozen_rgb, ev, t):
        """Black & white freeze with the character card sliding in."""
        img = ImageOps.grayscale(frozen_rgb).convert("RGB")
        img = ImageOps.autocontrast(img, cutoff=1)
        cid = ev["who"]
        c = self.cast.get(cid, {})
        info = c.get("card") or {"title": c.get("name", cid), "subtitle": ""}
        ch = int(self.H * 0.6)
        cw = int(ch * 0.75)
        art = ImageOps.fit(self._art(cid), (cw, ch), centering=(0.5, 0.3))
        bw = self.s(10)
        framed = Image.new("RGBA", (cw + 2 * bw, ch + 2 * bw), (255, 255, 255, 255))
        framed.paste(art, (bw, bw))
        rot = framed.rotate(5, expand=True, resample=Image.BICUBIC)
        shadow = Image.new("RGBA", rot.size, (0, 0, 0, 0))
        shadow.paste((0, 0, 0, 120), (0, 0), rot.split()[3])
        shadow = shadow.filter(ImageFilter.GaussianBlur(self.s(12)))
        p = ease(t / 0.3)
        left = self.W > self.H
        x = int((self.W * 0.06 if left else (self.W - rot.width) / 2) - (1 - p) * self.W * 0.5)
        y = int(self.H * 0.1)
        base = img.convert("RGBA")
        base.alpha_composite(shadow, (max(0, x + self.s(14)), y + self.s(18)))
        if x >= 0:
            base.alpha_composite(rot, (x, y))
        elif x + rot.width > 0:
            base.alpha_composite(rot.crop((-x, 0, rot.width, rot.height)), (0, y))
        img = base.convert("RGB")
        d = ImageDraw.Draw(img, "RGBA")
        fn, fs = self.font(84), self.font(28)
        nx = x + self.s(20)
        ny = y + rot.height - self.s(70)
        d.text((nx, ny), info["title"], font=fn, fill=(255, 255, 255),
               stroke_width=self.s(6), stroke_fill=(30, 20, 60))
        if info.get("subtitle"):
            sy = ny + self.s(100)
            d.rectangle([nx, sy, nx + self.s(6), sy + self.s(34)], fill=PINK)
            d.text((nx + self.s(18), sy), info["subtitle"], font=fs, fill=(255, 255, 255),
                   stroke_width=self.s(2), stroke_fill=(0, 0, 0))
        return img

    def wheel(self, frozen_rgb, ev, t):
        img = frozen_rgb.filter(ImageFilter.GaussianBlur(self.s(8)))
        img = Image.blend(img, Image.new("RGB", img.size, (0, 0, 0)), 0.35)
        d = ImageDraw.Draw(img, "RGBA")
        items = ev["items"]
        n = len(items)
        p = ease(t / 0.25)
        R, r = self.s(250) * (0.6 + 0.4 * p), self.s(110) * (0.6 + 0.4 * p)
        cx, cy = self.W / 2, self.H / 2
        picked = t > 0.6
        f = self.font(22)
        for i, it in enumerate(items):
            a0 = -90 + i * 360 / n - 180 / n
            a1 = a0 + 360 / n - 2
            on = picked and it == ev.get("pick")
            d.pieslice([cx - R, cy - R, cx + R, cy + R], a0, a1,
                       fill=(PINK + (220,)) if on else (20, 20, 28, 190))
            am = math.radians((a0 + a1) / 2)
            tx, ty = cx + math.cos(am) * (R + r) / 2, cy + math.sin(am) * (R + r) / 2
            w = d.textlength(it, font=f)
            d.text((tx - w / 2, ty - self.s(12)), it, font=f, fill=(255, 255, 255, int(255 * p)))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 10, 14, 235),
                  outline=(255, 255, 255, 120), width=max(1, self.s(2)))
        if picked:
            lab = ev.get("pick", "")
            fl = self.font(26)
            w = d.textlength(lab, font=fl)
            d.rounded_rectangle([cx - w / 2 - self.s(14), cy + R + self.s(16),
                                 cx + w / 2 + self.s(14), cy + R + self.s(56)],
                                radius=self.s(8), fill=(20, 20, 28, 230), outline=PINK + (255,))
            d.text((cx - w / 2, cy + R + self.s(22)), lab, font=fl, fill=(255, 255, 255))
        return img

    # ---------------------------------------------------------- full-screen cards
    def title_card(self, t, dur):
        art = self.root / "brand" / "title.png"
        img = Image.new("RGB", (self.W, self.H), (8, 8, 12))
        if art.exists():
            a = Image.open(art).convert("RGBA")
            a.thumbnail((int(self.W * 0.7), int(self.H * 0.7)))
            img.paste(a, ((self.W - a.width) // 2, (self.H - a.height) // 2), a)
            return img
        alpha = min(1.0, t / 0.4, max(0.0, (dur - t) / 0.4))
        bottom = self._gradient_text(img, self.proj.get("title", ""), 150, self.H * 0.46, alpha=alpha)
        if self.proj.get("subtitle"):
            self._center_text(img, self.proj["subtitle"], 34, bottom + self.s(24), alpha=alpha, spacing=1)
        return img

    def end_card(self, last_rgb, t):
        img = Image.blend(last_rgb, Image.new("RGB", last_rgb.size, (0, 0, 0)), 0.45)
        a = ease(t / 0.4)
        bottom = self._gradient_text(img, self.proj.get("end_text", "MISSION COMPLETE"), 110,
                                     self.H * 0.48, alpha=a)
        if self.proj.get("end_subtitle"):
            self._center_text(img, self.proj["end_subtitle"], 24, bottom + self.s(16), alpha=a)
        return img
