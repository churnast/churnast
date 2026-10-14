"""Builds every SVG in ../assets from code: an ink dragon on a red sun.

No <script>. Motion is CSS @keyframes plus SMIL <animate> on path data (the dragon's
body and whiskers are re-computed for 12 phases of a wave, so the body really swims).
Text is converted to outlines, because SVGs shown through <img> cannot load web fonts.

Fonts (SIL Open Font License, from Google Fonts, in src/fonts/, not committed):
  Shojumaru (name and titles), Zen Kaku Gothic New Bold (small text), Yuji Boku (the 龍 glyph).

Run: python build.py   (needs fonttools)
"""
import math
import random
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

HERE = Path(__file__).parent
ASSETS = HERE.parent / "assets"


class Font:
    def __init__(self, file):
        self.f = TTFont(HERE / "fonts" / file, lazy=True)
        self.gs = self.f.getGlyphSet()
        self.cmap = self.f.getBestCmap()
        self.upm = self.f["head"].unitsPerEm
        self.hmtx = self.f["hmtx"]

    def glyphs(self, s, size, x, y):
        sc = size / self.upm
        out, cx = [], x
        for ch in s:
            g = self.cmap[ord(ch)]
            adv = self.hmtx[g][0] * sc
            pen = SVGPathPen(self.gs)
            self.gs[g].draw(TransformPen(pen, (sc, 0, 0, -sc, cx, y)))
            out.append((ch, pen.getCommands(), cx, adv))
            cx += adv
        return out

    def width(self, s, size):
        return sum(self.hmtx[self.cmap[ord(c)]][0] for c in s) * size / self.upm

    def path(self, s, size, x, y, fill, extra=""):
        d = " ".join(g[1] for g in self.glyphs(s, size, x, y) if g[1])
        return f'<path d="{d}" fill="{fill}" {extra}/>'


DISPLAY = Font("Shojumaru-Regular.ttf")
BODY = Font("ZenKakuGothicNew-Bold.ttf")
KANJI = Font("YujiBoku-Regular.ttf")
RYU = "龍"  # 龍, "dragon"

THEMES = {
    "dark": dict(bg="#0b0709", bg2="#1d0509", sun="#d4142c", sun2="#ff3348", ink="#070405",
                 cut="#5c0d17", rim="#ff2d44", eye="#ff2d44", text="#f4ece4", sub="#ff3348",
                 smoke="#4a3438", muted="#b9a9ad", paper="#f2ebdf", tag="#140a0c"),
    "light": dict(bg="#f3ecdf", bg2="#e6d9c5", sun="#c8102e", sun2="#e0192f", ink="#151012",
                  cut="#f3ecdf", rim="#151012", eye="#e0192f", text="#151012", sub="#c8102e",
                  smoke="#a2958b", muted="#5d5250", paper="#f3ecdf", tag="#151012"),
}
RED = "#d4142c"


# ---------------------------------------------------------------- geometry
def catmull(pts, closed=False):
    """Smooth path through points (Catmull-Rom to cubic Bezier). Fixed command count."""
    n = len(pts)
    d = [f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"]
    rng = range(n) if closed else range(n - 1)
    for i in rng:
        p0 = pts[(i - 1) % n] if (closed or i > 0) else pts[i]
        p1, p2 = pts[i], pts[(i + 1) % n]
        p3 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    if closed:
        d.append("Z")
    return "".join(d)


def frames_attr(ds, dur, attr="d"):
    vals = ";".join(ds + [ds[0]])
    return f'<animate attributeName="{attr}" dur="{dur}s" repeatCount="indefinite" values="{vals}"/>'


def anim_path(ds, dur, extra):
    return f'<path d="{ds[0]}" {extra}>{frames_attr(ds, dur)}</path>'


class Dragon:
    """A serpentine body along base(s) for s in [0,1] (0 = neck, 1 = tail tip)."""

    def __init__(self, base, n=64, w0=30, amp=14, waves=1.6, legs=(.2, .52), flip=1):
        self.base, self.n, self.w0, self.amp, self.waves, self.legs, self.flip = base, n, w0, amp, waves, legs, flip

    def width(self, s):
        neck = min(1.0, .62 + s * 5)
        return max(1.6, self.w0 * neck * (1 - s) ** .85 + 1.2)

    def spine(self, phase):
        pts = []
        for i in range(self.n):
            s = i / (self.n - 1)
            x, y, nx, ny = self.base(s)
            a = self.amp * min(1, s * 6) * math.sin(2 * math.pi * self.waves * s - phase)
            pts.append((x + nx * a, y + ny * a))
        return pts

    def frame(self, phase):
        P = self.spine(phase)
        n = len(P)
        T, N = [], []
        for i in range(n):
            a, b = P[max(0, i - 1)], P[min(n - 1, i + 1)]
            tx, ty = b[0] - a[0], b[1] - a[1]
            L = math.hypot(tx, ty) or 1
            tx, ty = tx / L, ty / L
            T.append((tx, ty))
            N.append((-ty * self.flip, tx * self.flip))
        W = [self.width(i / (n - 1)) for i in range(n)]
        up = [(P[i][0] + N[i][0] * W[i] / 2, P[i][1] + N[i][1] * W[i] / 2) for i in range(n)]
        dn = [(P[i][0] - N[i][0] * W[i] / 2, P[i][1] - N[i][1] * W[i] / 2) for i in range(n)]
        outline = up + dn[::-1]
        body = catmull(outline, closed=True)
        # dorsal spikes, swept back toward the tail
        sp = []
        for i in range(4, n - 6, 3):
            l = W[i] * .32 + 3
            tip = (up[i][0] + N[i][0] * l + T[i][0] * l * .8, up[i][1] + N[i][1] * l + T[i][1] * l * .8)
            a, b = up[i - 1], up[i + 2]
            sp.append(f"M{a[0]:.1f},{a[1]:.1f}L{tip[0]:.1f},{tip[1]:.1f}L{b[0]:.1f},{b[1]:.1f}Z")
        # belly scales as chevrons
        sc = []
        for i in range(2, n - 8, 2):
            w = W[i] * .36
            a = (P[i][0] + N[i][0] * w, P[i][1] + N[i][1] * w)
            b = (P[i][0] - N[i][0] * w, P[i][1] - N[i][1] * w)
            c = (P[i][0] + T[i][0] * W[i] * .35, P[i][1] + T[i][1] * W[i] * .35)
            sc.append(f"M{a[0]:.1f},{a[1]:.1f}Q{c[0]:.1f},{c[1]:.1f} {b[0]:.1f},{b[1]:.1f}")
        # legs with three claws on the belly side
        lg, cl = [], []
        for s0 in self.legs:
            i = int(s0 * (n - 1))
            base_pt = dn[i]
            k = W[i] * .5 + 12
            knee = (base_pt[0] - N[i][0] * k * .6 + T[i][0] * 10, base_pt[1] - N[i][1] * k * .6 + T[i][1] * 10)
            foot = (base_pt[0] - N[i][0] * k + T[i][0] * 18, base_pt[1] - N[i][1] * k + T[i][1] * 18)
            lg.append(f"M{base_pt[0]:.1f},{base_pt[1]:.1f}Q{knee[0]:.1f},{knee[1]:.1f} {foot[0]:.1f},{foot[1]:.1f}")
            for j, ang in enumerate((-.7, 0, .7)):
                cx = math.cos(ang) * T[i][0] - math.sin(ang) * T[i][1]
                cy = math.sin(ang) * T[i][0] + math.cos(ang) * T[i][1]
                e = (foot[0] + cx * 11, foot[1] + cy * 11)
                h = (e[0] - N[i][0] * 5, e[1] - N[i][1] * 5)
                cl.append(f"M{foot[0]:.1f},{foot[1]:.1f}Q{e[0]:.1f},{e[1]:.1f} {h[0]:.1f},{h[1]:.1f}")
        # tail tuft
        i = n - 1
        tt = P[i]
        tuft = []
        for j, ang in enumerate((-.9, -.3, .4)):
            cx = math.cos(ang) * T[i][0] - math.sin(ang) * T[i][1]
            cy = math.sin(ang) * T[i][0] + math.cos(ang) * T[i][1]
            e = (tt[0] + cx * 26, tt[1] + cy * 26)
            m = (tt[0] + cx * 12 + N[i][0] * 6, tt[1] + cy * 12 + N[i][1] * 6)
            tuft.append(f"M{tt[0] - T[i][0] * 6:.1f},{tt[1] - T[i][1] * 6:.1f}Q{m[0]:.1f},{m[1]:.1f} {e[0]:.1f},{e[1]:.1f}")
        return dict(body=body, spikes="".join(sp), scales="".join(sc), legs="".join(lg),
                    claws="".join(cl), tuft="".join(tuft))

    def head_pose(self):
        P = self.spine(0)
        (x0, y0), (x1, y1) = P[0], P[2]
        return x0, y0, math.degrees(math.atan2(y0 - y1, x0 - x1))

    def svg(self, t, dur=6, frames=12, uid="d", head_scale=1.0, head_extra="", fire="", sync=None, counter=None):
        F = [self.frame(2 * math.pi * k / frames) for k in range(frames)]
        col = lambda key: [f[key] for f in F]
        hx, hy, ang = self.head_pose()
        rim = f'stroke="{t["rim"]}" stroke-width="1.6" stroke-linejoin="round"'
        # keep the head upright: never mirrored vertically, at most 20 degrees off horizontal
        if math.cos(math.radians(ang)) >= 0:
            rot, sx = max(-20, min(20, (ang + 180) % 360 - 180)), head_scale
        else:
            rot, sx = max(-20, min(20, (ang % 360) - 180)), -head_scale
        cnt = f' class="{counter}"' if counter else ""
        return f"""<g>
{anim_path(col("legs"), dur, f'fill="none" stroke="{t["ink"]}" stroke-width="12" stroke-linecap="round"')}
{anim_path(col("claws"), dur, f'fill="none" stroke="{t["ink"]}" stroke-width="3.2" stroke-linecap="round"')}
{anim_path(col("spikes"), dur, f'fill="{t["ink"]}" stroke="{t["rim"]}" stroke-width="1" stroke-opacity=".55" stroke-linejoin="round"')}
{anim_path(col("tuft"), dur, f'fill="none" stroke="{t["ink"]}" stroke-width="4" stroke-linecap="round"')}
{anim_path(col("body"), dur, f'fill="{t["ink"]}" {rim}')}
{anim_path(col("scales"), dur, f'fill="none" stroke="{t["cut"]}" stroke-width="1.7" stroke-linecap="round"')}
<g transform="translate({hx:.1f} {hy:.1f})"><g{cnt}><g transform="rotate({rot:.1f}) scale({sx} {head_scale})"><g class="{("tilt" + sync) if sync else "nod"}">{head(t, uid, dur, fire, sync)}</g></g></g></g>
</g>"""


def path_base(points):
    """Spine through control points (Catmull-Rom), s in [0,1] spread evenly over segments."""
    P = points
    n = len(P) - 1

    def ev(s):
        u = min(max(s, 0), 1) * n
        i = min(int(u), n - 1)
        f = u - i
        p0, p1, p2 = P[max(i - 1, 0)], P[i], P[i + 1]
        p3 = P[min(i + 2, n)]
        def cr(a, b, c, d):
            return .5 * ((2 * b) + (-a + c) * f + (2 * a - 5 * b + 4 * c - d) * f * f + (-a + 3 * b - 3 * c + d) * f ** 3)
        return cr(p0[0], p1[0], p2[0], p3[0]), cr(p0[1], p1[1], p2[1], p3[1])

    def base(s):
        x, y = ev(s)
        x2, y2 = ev(s + .002) if s < .998 else (x, y)
        x1, y1 = ev(s - .002) if s > .002 else (x, y)
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy) or 1
        return x, y, -dy / L, dx / L
    return base


def whisker(x, y, dx, dy, length, curl, phase, segs=14):
    pts = []
    for i in range(segs):
        u = i / (segs - 1)
        bend = curl * u * u
        wob = 7 * u * math.sin(phase + u * 5)
        ang = math.atan2(dy, dx) + bend
        px = x + math.cos(ang) * length * u - math.sin(ang) * wob
        py = y + math.sin(ang) * length * u + math.cos(ang) * wob
        pts.append((px, py))
    return catmull(pts)


def head(t, uid, dur, fire="", sync=None):
    """Head facing +x, neck at the origin, about 100 long."""
    ink, cut, rim = t["ink"], t["cut"], t["rim"]
    R = f'stroke="{rim}" stroke-width="1.6" stroke-linejoin="round"'
    wh1 = [whisker(92, -14, 1, -.3, 120, -2.2, 2 * math.pi * k / 12) for k in range(12)]
    wh2 = [whisker(88, -8, 1, .45, 110, 2.0, 2 * math.pi * k / 12 + 1.5) for k in range(12)]
    wh3 = [whisker(30, 18, -.2, 1, 70, 1.4, 2 * math.pi * k / 12 + 3) for k in range(12)]
    return f"""
<path d="M-6,-14 C-30,-30 -52,-28 -76,-46 C-58,-22 -42,-12 -20,-4Z M-4,-4 C-34,-6 -58,6 -84,-2 C-60,12 -34,12 -8,6Z M-4,8 C-28,20 -46,36 -70,38 C-46,26 -30,16 -10,14Z M2,-18 C-10,-40 -30,-46 -40,-62 C-22,-50 -6,-40 8,-22Z" fill="{ink}" {R}/>
<path d="M10,-18 C-6,-42 -26,-60 -56,-68 C-34,-54 -16,-36 0,-12Z M22,-22 C12,-46 -2,-66 -26,-82 C-10,-62 2,-42 12,-16Z" fill="{ink}" {R}/>
<g class="{("jaw" + sync) if sync else ""}"><path d="M6,8 C24,8 42,11 62,17 C70,19 76,23 74,28 C66,30 48,27 32,23 C20,21 8,19 0,16Z" fill="{ink}" {R}/>
<path d="M40,12 l3,-6 l3,7 M54,15 l3,-6 l3,7" fill="{t['paper']}"/></g>
<g transform="translate(56 7) rotate(9)">{fire}</g>
<path d="M-10,-12 C4,-28 26,-32 46,-28 C60,-26 72,-22 86,-24 C94,-24 100,-18 98,-11 C96,-6 90,-4 82,-4 L52,-2 C40,-1 30,2 20,4 C8,6 -4,6 -10,4Z" fill="{ink}" {R}/>
<path d="M44,-2 l3,6 l3,-6 M56,-3 l3,6 l3,-6 M68,-4 l3,6 l3,-6 M80,-4 l2,5 l2,-5" fill="{t['paper']}" stroke="none"/>
<path d="M24,6 C40,6 56,8 70,4" fill="none" stroke="{t['sun2']}" stroke-width="2" opacity=".8"/>
<path d="M28,-28 L38,-40 L42,-30 L52,-38 L54,-28 L62,-32 L62,-24Z" fill="{ink}" {R}/>
<path d="M88,-18 q4,-4 6,1" fill="none" stroke="{cut}" stroke-width="2" stroke-linecap="round"/>
<path d="M6,-10 C16,-14 24,-14 30,-10 M14,0 C24,-2 30,-2 36,0" fill="none" stroke="{cut}" stroke-width="1.6" stroke-linecap="round"/>
<circle class="eyeglow" cx="42" cy="-18" r="9" fill="{t['eye']}" filter="url(#{uid}glow)"/>
<path d="M33,-18 C37,-24 47,-24 51,-18 C47,-14 39,-14 33,-18Z" fill="{t['eye']}"/>
<ellipse cx="43" cy="-18.5" rx="1.6" ry="4" fill="{ink}"/>
<path d="M30,18 C26,32 16,42 2,50 C16,40 20,30 18,18Z M40,22 C38,34 32,44 22,52 C34,44 40,34 46,22Z" fill="{ink}" {R}/>
{anim_path(wh1, dur / 2, f'fill="none" stroke="{ink}" stroke-width="2.6" stroke-linecap="round"')}
{anim_path(wh2, dur / 2, f'fill="none" stroke="{ink}" stroke-width="2.4" stroke-linecap="round"')}
{anim_path(wh3, dur / 2, f'fill="none" stroke="{ink}" stroke-width="2" stroke-linecap="round" opacity=".8"')}
"""


# ---------------------------------------------------------------- decor
SPARK = "M0,-10 C1.2,-2.4 2.4,-1.2 10,0 C2.4,1.2 1.2,2.4 0,10 C-1.2,2.4 -2.4,1.2 -10,0 C-2.4,-1.2 -1.2,-2.4 0,-10Z"
FLAME = "M0,-30 C12,-14 18,-4 13,9 C9,18 -9,18 -13,9 C-18,-4 -6,-12 0,-30Z"


def splatter(seed, cx, cy, spread, color, count=26, streaks=6):
    rnd = random.Random(seed)
    out = []
    for _ in range(count):
        a = rnd.uniform(0, 2 * math.pi)
        r = spread * rnd.uniform(.55, 1.15)
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * .8
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rnd.uniform(1, 6) ** 1.1:.1f}" fill="{color}"/>')
    for _ in range(streaks):
        a = rnd.uniform(0, 2 * math.pi)
        r = spread * rnd.uniform(.9, 1.2)
        x, y = cx + math.cos(a) * r, cy + math.sin(a) * r * .8
        l = rnd.uniform(16, 40)
        ex, ey = x + math.cos(a) * l, y + math.sin(a) * l
        w = rnd.uniform(2, 5)
        nx, ny = -math.sin(a) * w, math.cos(a) * w
        out.append(f'<path d="M{x + nx:.1f},{y + ny:.1f}L{ex:.1f},{ey:.1f}L{x - nx:.1f},{y - ny:.1f}Z" fill="{color}"/>')
    return f'<g filter="url(#rough)">{"".join(out)}</g>'


def smoke(items, color):
    """Curl-cloud wisps that drift and fade. items: (x, y, scale, delay)."""
    curl = "M0,0 C-6,-14 10,-22 18,-12 C24,-4 16,6 8,2 C2,-1 6,-8 11,-6 M18,-12 C26,-24 46,-22 48,-8 C50,4 38,10 32,4"
    out = []
    for x, y, s, dl in items:
        out.append(f'<g transform="translate({x} {y}) scale({s})"><path class="smk" style="animation-delay:{dl}s" d="{curl}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round"/></g>')
    return "".join(out)


def petals(seed, W, H, color, n=14, dur=7):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        x = rnd.uniform(0, W)
        y = rnd.uniform(-40, H * .6)
        r = rnd.uniform(2.5, 5)
        out.append(f'<ellipse class="ptl" style="animation-delay:{-rnd.uniform(0, dur):.2f}s;animation-duration:{rnd.uniform(dur * .7, dur * 1.3):.1f}s" cx="{x:.0f}" cy="{y:.0f}" rx="{r:.1f}" ry="{r * .45:.1f}" fill="{color}" transform="rotate({rnd.uniform(0, 180):.0f} {x:.0f} {y:.0f})"/>')
    return "".join(out)


def seal(x, y, size, t, text_col=None):
    """Red hanko seal with 龍 cut out."""
    g = KANJI.glyphs(RYU, size * .8, 0, 0)[0]
    w = g[3]
    return (f'<g transform="translate({x} {y}) rotate(-4)" filter="url(#rough)"><rect x="0" y="0" width="{size}" height="{size}" rx="{size * .12:.1f}" fill="{t["sun"]}"/>'
            f'<g transform="translate({(size - w) / 2:.1f} {size * .8:.1f})"><path d="{g[1]}" fill="{text_col or t["paper"]}"/></g></g>')


BASE_CSS = """
.smk{animation:smk 6s ease-in-out infinite;opacity:0}
@keyframes smk{0%{opacity:0;transform:translate(0,0) scale(.7)}25%{opacity:.75}100%{opacity:0;transform:translate(-40px,-28px) scale(1.25)}}
.ptl{animation:ptl 7s linear infinite}
@keyframes ptl{0%{transform:translate(0,0);opacity:0}10%{opacity:.9}100%{transform:translate(-160px,260px);opacity:0}}
.eyeglow{animation:eye 3.2s ease-in-out infinite}
@keyframes eye{0%,70%,100%{opacity:.25}78%{opacity:1}84%{opacity:.5}88%{opacity:1}}
.nod{animation:nod 6s ease-in-out infinite}
@keyframes nod{0%,100%{transform:rotate(0)}50%{transform:rotate(-5deg)}}
.sunp{animation:sunp 5s ease-in-out infinite}
@keyframes sunp{0%,100%{opacity:.35}50%{opacity:.7}}
"""


def defs_common(uid, t):
    return f"""
<filter id="rough" x="-.2" y="-.2" width="1.4" height="1.4"><feTurbulence type="fractalNoise" baseFrequency=".06" numOctaves="2" seed="3"/><feDisplacementMap in="SourceGraphic" scale="6"/></filter>
<filter id="{uid}glow" x="-2" y="-2" width="5" height="5"><feGaussianBlur stdDeviation="5"/></filter>
<filter id="{uid}blur" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="22"/></filter>
<radialGradient id="{uid}sun" cx="45%" cy="40%" r="60%"><stop offset="0" stop-color="{t['sun2']}"/><stop offset="1" stop-color="{t['sun']}"/></radialGradient>
"""


def sun(uid, t, cx, cy, r):
    halo = f'<circle class="sunp" cx="{cx}" cy="{cy}" r="{r * 1.08:.0f}" fill="{t["sun"]}" filter="url(#{uid}blur)"/>' if t is THEMES["dark"] else ""
    return f'{halo}<circle cx="{cx}" cy="{cy}" r="{r}" fill="url(#{uid}sun)" filter="url(#rough)"/>'


def typed(font, text, size, x, y, fill, cycle, start, step, end_pct, cls):
    gl = font.glyphs(text, size, x, y)
    css, parts = [], []
    t0 = start / cycle * 100
    for i, (ch, d, gx, adv) in enumerate(gl):
        p = round((start + i * step) / cycle * 100, 2)
        css.append(f".{cls}{i}{{opacity:0;animation:{cls}{i} {cycle}s infinite}}@keyframes {cls}{i}{{0%,{p:.2f}%{{opacity:0}}{p + .01:.2f}%,{end_pct}%{{opacity:1}}{end_pct + .01:.2f}%,100%{{opacity:0}}}}")
        if d:
            parts.append(f'<path class="{cls}{i}" d="{d}" fill="{fill}"/>')
    frames = [f"0%,{t0:.2f}%{{transform:translateX(0)}}"]
    for i, (ch, d, gx, adv) in enumerate(gl):
        p = round((start + i * step) / cycle * 100, 2)
        frames.append(f"{p + .01:.2f}%{{transform:translateX({gx + adv - x:.1f}px)}}")
    last = gl[-1][2] + gl[-1][3] - x
    frames.append(f"{end_pct}%{{transform:translateX({last:.1f}px)}}{end_pct + .01:.2f}%,100%{{transform:translateX(0)}}")
    css.append(f".{cls}c{{animation:{cls}c {cycle}s infinite steps(1,end)}}@keyframes {cls}c{{{''.join(frames)}}}")
    css.append(f".{cls}b{{animation:{cls}b 1s infinite}}@keyframes {cls}b{{0%,49%{{opacity:1}}50%,100%{{opacity:0}}}}")
    cursor = f'<g class="{cls}c"><rect class="{cls}b" x="{x + 3}" y="{y - size * .8:.1f}" width="3" height="{size * .95:.1f}" fill="{RED}"/></g>'
    return "\n".join(css), "\n".join(parts) + cursor


def svg(w, h, label, defs, css, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}">
<title>{label}</title>
<defs>{defs}</defs>
<style>{BASE_CSS}{css}</style>
{body}
</svg>
"""


def brush_bar(x, y, w, h, color, seed=1):
    rnd = random.Random(seed)
    top = [(x + w * i / 10, y + rnd.uniform(-2, 2)) for i in range(11)]
    bot = [(x + w * (10 - i) / 10 - 6, y + h + rnd.uniform(-3, 3)) for i in range(11)]
    pts = [(x - 10, y + h * .5)] + top + [(x + w + 14, y + h * .4)] + bot
    return f'<path d="{catmull(pts, closed=True)}" fill="{color}" filter="url(#rough)"/>'


# ---------------------------------------------------------------- header
NAME = "Nastya Churaeva"
NAME_SIZE = min(80, round(600 / (DISPLAY.width(NAME, 1)), 1))
HEADER_LABEL = "Nastya Churaeva. AI automation engineer. I hand team routine to bots and AI agents. An ink dragon swims around a red sun."


def header(theme):
    t = THEMES[theme]
    uid = "h" + theme[0]
    W, H = 1280, 320
    SX, SY, SR = 1010, 160, 118

    base = path_base([(880, 128), (950, 84), (1050, 66), (1135, 104), (1160, 180), (1110, 245), (1010, 262), (920, 232), (905, 275), (975, 300), (1080, 298), (1170, 270), (1215, 228)])
    dr = Dragon(base, w0=40, amp=8, waves=2.2, legs=(.18, .45), flip=-1)
    tcss, tbody = typed(BODY, "I hand team routine to bots and AI agents", 26, 76, 226, t["text"], 12, 1.2, .075, 88, f"t{theme[0]}")
    defs = defs_common(uid, t) + f"""
<linearGradient id="{uid}bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg']}"/><stop offset="1" stop-color="{t['bg2']}"/></linearGradient>
<clipPath id="{uid}clip"><rect width="{W}" height="{H}" rx="14"/></clipPath>"""
    ryu = KANJI.path(RYU, 250, 560, 270, t["sun"], 'opacity=".14"')
    tag_w = BODY.width("AI automation engineer", 15) + 36
    body = f"""<g clip-path="url(#{uid}clip)">
<rect width="{W}" height="{H}" fill="url(#{uid}bg)"/>
{ryu}
{sun(uid, t, SX, SY, SR)}
{splatter(7, SX, SY, SR * 1.15, t["sun"], 30, 7)}
{smoke([(1180, 70, 1.1, 0), (840, 250, 1.3, -2), (1200, 230, 1, -4), (880, 70, .9, -1)], t["smoke"])}
<g transform="translate(0 0)">{dr.svg(t, uid=uid, head_scale=1.15)}</g>
{petals(11, W, H, t["sun2"], 16)}
{DISPLAY.path("hi, I'm", 22, 78, 72, t["sub"])}
{DISPLAY.path(NAME, NAME_SIZE, 70, 166, t["text"])}
{tbody}
<rect x="76" y="252" width="{tag_w:.0f}" height="32" fill="{t['tag']}" stroke="{t['sun']}" stroke-width="1.5"/>
{BODY.path("AI automation engineer", 15, 94, 273, "#f4ece4")}
{seal(W - 74, 24, 46, t)}
</g>"""
    return svg(W, H, HEADER_LABEL, defs, tcss, body)


# ---------------------------------------------------------------- covers
def cover_bg(uid, t, W, H):
    return f"""
<linearGradient id="{uid}bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t['bg']}"/><stop offset="1" stop-color="{t['bg2']}"/></linearGradient>
<clipPath id="{uid}clip"><rect width="{W}" height="{H}" rx="14"/></clipPath>"""


def bubble(x, y, text, size, bg, fg, stroke):
    w = BODY.width(text, size) + 36
    h = size + 26
    return (f'<rect x="{x}" y="{y}" width="{w:.0f}" height="{h}" rx="6" fill="{bg}" stroke="{stroke}" stroke-width="1.5"/>'
            f'<path d="M{x + 14},{y + h} l-8,12 l20,-12Z" fill="{bg}"/>'
            + BODY.path(text, size, x + 18, y + h / 2 + size * .36, fg)), w, h


def cover_title(title, sub, x, y, t):
    return (DISPLAY.path(title, 44, x, y, t["text"])
            + BODY.path(sub, 22, x + 4, y + 42, t["sub"]))


def sticker_card(t):
    """A white sticker with an ink cat face, centred on 0,0."""
    return f"""<rect x="-40" y="-40" width="80" height="80" rx="16" fill="#fffaf2" stroke="{RED}" stroke-width="3"/>
<path d="M-24,-6 L-28,-30 L-10,-18Z M24,-6 L28,-30 L10,-18Z" fill="#151012"/>
<ellipse cx="0" cy="4" rx="27" ry="22" fill="#151012"/>
<path d="M-15,0 q5,-6 10,0 M5,0 q5,-6 10,0" stroke="#fffaf2" stroke-width="3" fill="none" stroke-linecap="round"/>
<path d="M-5,12 q5,5 10,0" stroke="#fffaf2" stroke-width="2.5" fill="none" stroke-linecap="round"/>
<circle cx="-17" cy="10" r="3.5" fill="{RED}"/><circle cx="17" cy="10" r="3.5" fill="{RED}"/>"""


def stickers_cover():
    t = THEMES["dark"]
    uid = "cs"
    W, H = 1280, 480
    SX, SY, SR = 320, 240, 160

    base = path_base([(480, 170), (420, 120), (320, 96), (215, 130), (170, 220), (205, 315), (300, 370), (410, 360), (470, 300), (440, 250), (360, 262), (280, 320), (190, 400), (110, 450)])
    dr = Dragon(base, w0=46, amp=9, waves=2.4, legs=(.16, .42), flip=-1)
    hx, hy, ang = dr.head_pose()
    b, bw, bh = bubble(690, 118, "I GOT THE JOB!!!", 24, "#140a0c", "#f4ece4", RED)
    css = """
.stk{animation:stk 6s ease-in-out infinite}
@keyframes stk{0%,18%{transform:translate(0,0) rotate(-8deg)}36%{transform:translate(120px,-50px) rotate(14deg) scale(1.1)}46%,86%{transform:translate(215px,45px) rotate(4deg)}92%{opacity:1}96%{opacity:0;transform:translate(215px,45px)}97%{opacity:0;transform:translate(0,0) rotate(-8deg)}100%{opacity:1}}
.bb{animation:bb 6s infinite}@keyframes bb{0%,6%{opacity:0;transform:translateY(10px)}12%,92%{opacity:1;transform:none}98%,100%{opacity:0}}
.pop{transform-box:fill-box;transform-origin:center;animation:pop 6s infinite}
@keyframes pop{0%,44%{opacity:0;transform:scale(.3)}50%{opacity:1;transform:scale(1.3)}60%,100%{opacity:0;transform:scale(1.8)}}
"""
    body = f"""<g clip-path="url(#{uid}clip)">
<rect width="{W}" height="{H}" fill="url(#{uid}bg)"/>
{KANJI.path(RYU, 300, 940, 420, t["sun"], 'opacity=".1"')}
{sun(uid, t, SX, SY, SR)}
{splatter(21, SX, SY, SR * 1.12, t["sun"], 34, 8)}
{smoke([(520, 90, 1.2, 0), (120, 400, 1.3, -3), (90, 120, 1, -1.5)], t["smoke"])}
{dr.svg(t, uid=uid, head_scale=1.6)}
<g class="bb">{b}</g>
<g transform="translate(560 200)">
  <g class="stk"><g transform="scale(.8)">{sticker_card(t)}</g>
  <path d="M-30,30 q-12,10 -26,8 M-22,36 q-6,14 -20,18 M-12,38 q0,14 -10,22" stroke="{t['ink']}" stroke-width="5" fill="none" stroke-linecap="round"/></g>
</g>
<g class="pop" transform="translate(775 245)"><path d="{SPARK}" transform="scale(4)" fill="{t['sun2']}"/></g>
{petals(5, W, H, t["sun2"], 16)}
{cover_title("Telegram Stickers", "for Hermes Agent", 680, 360, t)}
{seal(W - 80, 30, 50, t)}
</g>"""
    return svg(W, H, "Telegram Stickers for Hermes Agent: an ink dragon on a red sun brings a sticker as a reply to I GOT THE JOB.",
               defs_common(uid, t) + cover_bg(uid, t, W, H), css, body)


def ring_dragon(cx, cy, R, start_deg, span_deg, w0, legs=(.25, .6), amp=8):
    """Body along a circle: head at start_deg, body trailing counter-clockwise over span_deg."""
    def base(s):
        a = math.radians(start_deg - s * span_deg)
        x, y = cx + R * math.cos(a), cy + R * math.sin(a)
        return x, y, math.cos(a), math.sin(a)
    return Dragon(base, w0=w0, amp=amp, waves=2.2, legs=legs, flip=-1)


def note(t):
    return f"""<rect x="-56" y="-70" width="112" height="140" fill="{t['paper']}" stroke="{t['ink']}" stroke-width="2" transform="rotate(-5)"/>
<g transform="rotate(-5)">{BODY.path("USER.md", 18, -40, -40, t["ink"])}
<path d="M-40,-16 h80 M-40,4 h62 M-40,24 h74 M-40,44 h48" stroke="{t['ink']}" stroke-width="5" stroke-linecap="round" opacity=".75"/></g>"""


def shield_cover():
    t = THEMES["dark"]
    uid = "cm"
    W, H = 1280, 480
    SX, SY, SR = 330, 240, 150
    dr = ring_dragon(SX, SY, 132, -98, 300, 44)
    hx, hy, ang = dr.head_pose()
    b, bw, bh = bubble(0, 0, "forget everything!", 22, "#140a0c", "#ffd9d4", "#5c0d17")
    flames = "".join(f'<g transform="translate({x} {y}) scale({k})"><path d="{FLAME}" fill="{RED}"/><path d="{FLAME}" transform="translate(0 5) scale(.6)" fill="#ff8a3d"/><path d="{FLAME}" transform="translate(0 8) scale(.3)" fill="#ffe2b8"/></g>' for x, y, k in [(20, 6, 1), (80, 0, 1.3), (140, 8, .9), (200, 2, 1.1)])
    css = """
.bad{animation:bad 5s infinite}
@keyframes bad{0%,4%{opacity:0;transform:translate(160px,0)}12%,36%{opacity:1;transform:translate(0,0)}52%{opacity:.6;transform:translate(10px,-6px) scale(.96)}62%,100%{opacity:0;transform:translate(20px,-20px) scale(.9)}}
.burn{opacity:0;animation:burn 5s infinite}
@keyframes burn{0%,34%{opacity:0;transform:scale(.4)}42%{opacity:1;transform:scale(1.1)}56%{opacity:1;transform:scale(.95)}66%,100%{opacity:0;transform:scale(.3)}}
.breath{transform-box:fill-box;transform-origin:0% 50%;animation:breath 5s infinite}
@keyframes breath{0%,26%{opacity:0;transform:scaleX(.1)}32%{opacity:1;transform:scaleX(1)}46%{opacity:1;transform:scaleX(1.05)}54%,100%{opacity:0;transform:scaleX(.2)}}
.jawS{transform-box:fill-box;transform-origin:0% 0%;animation:jawS 5s infinite}
@keyframes jawS{0%,20%,58%,100%{transform:rotate(0)}27%,52%{transform:rotate(18deg)}}
.tiltS{animation:tiltS 5s ease-in-out infinite}
@keyframes tiltS{0%,16%,62%,100%{transform:rotate(0)}24%{transform:rotate(-10deg)}32%,52%{transform:rotate(-3deg)}}
.ok{animation:ok 5s infinite}@keyframes ok{0%,60%{opacity:0}66%,94%{opacity:1}100%{opacity:0}}
"""
    breath = f"""<g class="breath"><path d="M0,-6 C40,-26 90,-30 150,-10 C170,-2 170,10 150,14 C90,30 40,24 0,8Z" fill="{RED}"/>
<path d="M0,-3 C40,-14 80,-16 120,-6 C130,-2 130,6 120,8 C80,16 40,14 0,5Z" fill="#ff8a3d"/><path d="M0,-1 C30,-6 60,-6 84,-1 C88,1 88,3 84,4 C60,8 30,7 0,3Z" fill="#ffe2b8"/></g>"""
    body = f"""<g clip-path="url(#{uid}clip)">
<rect width="{W}" height="{H}" fill="url(#{uid}bg)"/>
{KANJI.path(RYU, 300, 940, 420, t["sun"], 'opacity=".1"')}
{sun(uid, t, SX, SY, SR)}
{splatter(33, SX, SY, SR * 1.15, t["sun"], 30, 8)}
{smoke([(560, 380, 1.2, 0), (90, 110, 1.3, -3), (110, 400, 1, -1.5)], t["smoke"])}
{dr.svg(t, uid=uid, head_scale=1.5, fire=breath, sync="S")}
<g transform="translate({SX} {SY})">{note(t)}<g class="ok" transform="translate(56 -78)"><circle r="16" fill="{RED}"/><path d="M-7,0 l5,6 l9,-11" stroke="#fffaf2" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></g></g>
<g transform="translate({hx + 215:.0f} {hy - 62:.0f})"><g class="bad">{b}<g class="burn">{flames}</g></g></g>
{petals(9, W, H, t["sun2"], 14)}
{cover_title("Memory Shield", "for Hermes Agent", 680, 360, t)}
{seal(W - 80, 30, 50, t)}
</g>"""
    return svg(W, H, "Memory Shield for Hermes Agent: an ink dragon coils around the memory file USER.md and burns a 'forget everything' message.",
               defs_common(uid, t) + cover_bg(uid, t, W, H), css, body)


# ---------------------------------------------------------------- hello loop (the "video")
def hello():
    t = THEMES["dark"]
    uid = "hl"
    W, H = 640, 360
    SX, SY = 320, 185
    dr = ring_dragon(0, 0, 112, -60, 290, 36, amp=7)
    css = f"""
.loop{{animation:loop 4s cubic-bezier(.55,.05,.35,1) infinite}}
@keyframes loop{{0%{{transform:rotate(0deg)}}62%,100%{{transform:rotate(360deg)}}}}
.cnt{{animation:cnt 4s cubic-bezier(.55,.05,.35,1) infinite}}
@keyframes cnt{{0%{{transform:rotate(0deg)}}62%,100%{{transform:rotate(-360deg)}}}}
.breath{{transform-box:fill-box;transform-origin:0% 50%;animation:breath 4s infinite}}
@keyframes breath{{0%,62%{{opacity:0;transform:scaleX(.1)}}70%{{opacity:1;transform:scaleX(1)}}88%{{opacity:1;transform:scaleX(1.08)}}96%,100%{{opacity:0;transform:scaleX(.2)}}}}
.jawH{{transform-box:fill-box;transform-origin:0% 0%;animation:jawH 4s infinite}}
@keyframes jawH{{0%,54%,98%,100%{{transform:rotate(0)}}62%,94%{{transform:rotate(18deg)}}}}
.tiltH{{animation:tiltH 4s ease-in-out infinite}}
@keyframes tiltH{{0%,52%,100%{{transform:rotate(0)}}60%{{transform:rotate(-10deg)}}68%,94%{{transform:rotate(-3deg)}}}}
.burst{{transform-box:fill-box;transform-origin:center;animation:burst 4s infinite}}
@keyframes burst{{0%,66%{{opacity:0;transform:scale(.4)}}74%{{opacity:1;transform:scale(1)}}96%,100%{{opacity:0;transform:scale(1.4)}}}}
"""
    breath = f"""<g class="breath"><path d="M0,-6 C40,-30 100,-34 170,-12 C192,-2 192,12 170,16 C100,34 40,26 0,8Z" fill="{RED}"/>
<path d="M0,-3 C40,-16 90,-18 136,-6 C148,-2 148,6 136,9 C90,18 40,16 0,5Z" fill="#ff8a3d"/><path d="M0,-1 C30,-6 64,-7 92,-1 C96,1 96,3 92,4 C64,9 30,8 0,3Z" fill="#ffe2b8"/></g>"""
    body = f"""<rect width="{W}" height="{H}" fill="{t['bg']}"/>
{KANJI.path(RYU, 200, 30, 330, t["sun"], 'opacity=".12"')}
{sun(uid, t, SX, SY, 92)}
{splatter(41, SX, SY, 104, t["sun"], 26, 6)}
{smoke([(80, 80, 1, 0), (540, 300, 1.1, -2.5), (560, 70, .9, -1)], t["smoke"])}
<g transform="translate({SX} {SY})"><g class="loop">{dr.svg(t, uid=uid, dur=4, head_scale=1.15, fire=breath, sync="H", counter="cnt")}</g></g>
<g class="burst" transform="translate(560 120)"><path d="{SPARK}" transform="scale(2.4)" fill="{t['sun2']}"/></g>
{petals(3, W, H, t["sun2"], 12, 5)}
{seal(W - 64, 20, 40, t)}"""
    return svg(W, H, "An ink dragon loops around a red sun and breathes red fire.", defs_common(uid, t), css, body)


# ---------------------------------------------------------------- badges
TG_ICON = "M2,11 L21,3.5 L17.6,20.5 L11.5,16 L8.4,19 L8.8,14.4 L17.6,6.6 L6.8,13.4 Z"
GH_ICON = "M12,1.5a10.5,10.5 0 0 0-3.3,20.5c.5.1.7-.2.7-.5v-1.9c-2.9.6-3.5-1.3-3.5-1.3-.5-1.2-1.2-1.5-1.2-1.5-.9-.6.1-.6.1-.6 1,.1 1.6,1.1 1.6,1.1.9,1.6 2.5,1.1 3.1.9.1-.7.4-1.1.7-1.4-2.3-.3-4.8-1.2-4.8-5.2 0-1.1.4-2.1 1.1-2.8-.1-.3-.5-1.3.1-2.8 0,0 .9-.3 2.9,1.1a10,10 0 0 1 5.3,0c2-1.4 2.9-1.1 2.9-1.1.6,1.5.2,2.5.1,2.8.7.7 1.1,1.7 1.1,2.8 0,4-2.5,4.9-4.8,5.2.4.3.7,1 .7,2v2.9c0,.3.2.6.7.5A10.5,10.5 0 0 0 12,1.5Z"
TAG_ICON = "M3,3 h8 l10,10 l-8,8 l-10,-10Z M7.5,7.5 m-1.6,0 a1.6,1.6 0 1 0 3.2,0 a1.6,1.6 0 1 0 -3.2,0"


def badge(name, label, icon):
    size = 14
    tw = BODY.width(label, size)
    W = int(44 + tw + 18)
    H = 34
    s = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{label}">
<title>{label}</title>
<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" fill="#0b0709" stroke="{RED}" stroke-width="1.5"/>
<rect x=".75" y=".75" width="34" height="{H - 1.5}" fill="{RED}"/>
<g transform="translate(6.5 5.5) scale(.95)"><path d="{icon}" fill="#0b0709" fill-rule="evenodd"/></g>
{BODY.path(label, size, 46, 22, "#f4ece4")}
</svg>
"""
    (ASSETS / "badges" / f"{name}.svg").write_text(s)


def main():
    (ASSETS / "badges").mkdir(parents=True, exist_ok=True)
    for th in ("dark", "light"):
        (ASSETS / f"header-{th}.svg").write_text(header(th))
    (ASSETS / "telegram-stickers.svg").write_text(stickers_cover())
    (ASSETS / "memory-shield.svg").write_text(shield_cover())
    (ASSETS / "hello.svg").write_text(hello())
    badge("telegram", "Telegram @Anastasia_Chur", TG_ICON)
    badge("plugins", "Hermes Agent plugins", TAG_ICON)
    badge("repository", "Repository", GH_ICON)
    badge("releases", "Releases", TAG_ICON)
    stale = ASSETS / "badges" / "install.svg"
    if stale.exists():
        stale.unlink()
    print("ok")


if __name__ == "__main__":
    main()
