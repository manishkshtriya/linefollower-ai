"""
BE THE AI: the line follower game.

You drive the AI line follower car against its own neural network (the 107 learned weights in this repository).
Same car, same weak motor, same 4 IR sensors. Hard mode hides the track: you only see the 4 sensor lamps,
which is everything the network ever sees. The right-hand panel shows the network thinking, live.

Run:   python3 line_follower_game.py
Needs: Python 3.9+, pygame-ce, numpy   (pip3 install pygame-ce numpy)
"""
import json
import math
import os
import random
import sys

import numpy as np
import pygame

# ---------------------------------------------------------------- layout and constants
SCREEN_W, SCREEN_H = 1280, 800
TOP = 64                                   # score bar
SIDE = 320                                 # right panel width
VIEW_W, VIEW_H = SCREEN_W - SIDE, SCREEN_H - TOP
ZOOM = 0.95                                # chase camera: pixels per millimetre
WW, WH = 1900, 1100                        # world size, mm
TAPE, WHEELBASE, AHEAD, SPACING = 19, 81, 70, 20      # mm, same as the firmware and simulator
VMAX, STALL, TAU = 450.0, 60, 0.06                     # motor model
RACE_SECONDS = 60
GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(os.path.expanduser("~"), ".be_the_ai_scores.json")

INK = (14, 26, 43)
MUTED = (83, 100, 125)
BG = (245, 248, 252)
PANEL = (255, 255, 255)
LINE = (205, 215, 228)
YOU = (232, 150, 0)
AI = (10, 120, 180)
RED = (225, 40, 35)
GREEN = (26, 138, 90)
FLOOR = (226, 232, 239)
TAPE_COL = (16, 20, 27)

LEVELS = [
    {"name": "Solid oval", "shape": "oval", "style": "solid", "weak": 1.00, "tip": "Warm-up. A solid line, both motors equal."},
    {"name": "Dashed loops", "shape": "lobe", "style": "dashed", "weak": 0.96, "tip": "Gaps between dashes. All four lamps go dark in a gap."},
    {"name": "Dotted peanut", "shape": "peanut", "style": "dotted", "weak": 0.94, "tip": "Small dots and a weaker right motor that pulls you right."},
    {"name": "The real test", "shape": "wind", "style": "mixed", "weak": 0.92, "tip": "Solid, dashed and dotted on a winding track. Right motor 8% weaker."},
    {"name": "Your own track", "shape": "draw", "style": "mixed", "weak": 0.94, "tip": "Draw any closed loop with the mouse, then race on it."},
]

HOW_TO = [
    ("THE IDEA", "This car follows black tape using only 4 IR sensors and a tiny neural network (107 numbers). "
                 "You race against that network. Can a human brain beat it?"),
    ("CONTROLS", "Hold LEFT / RIGHT arrow (or A / D) to steer. Let go to drive straight. P or ESC pauses. "
                 "C switches camera (chase / whole track). Menus: arrow keys and ENTER, or click."),
    ("THE SENSOR LAMPS", "The 4 lamps under the minimap are your car's sensors, left to right. Red means that sensor "
                         "is over tape. Line under the left lamps: steer left. Under the right lamps: steer right."),
    ("GAPS", "On dashed and dotted tape all 4 lamps go dark between marks. Keep going and you reach the next mark. "
             "If no lamp sees tape for 3 seconds, the car stops itself: you lose the line."),
    ("THE WEAK MOTOR", "Real motors never match. From level 2 the right motor is weaker, so 'straight' slowly "
                       "pulls you right. The AI has the same problem."),
    ("SCORING", "60 seconds. Points come from distance, multiplied by your streak: every 5 seconds on the line "
                "adds x0.5, up to x3. Losing the line resets the streak and costs time. Beat the AI for 3 stars."),
    ("THE AI'S BRAIN", "The panel on the right is the AI's network, live: 4 inputs, two layers of 7, 2 outputs. "
                       "Blue means a neuron pushes up, orange pushes down."),
    ("HARD MODE", "The track is hidden. You only get the 4 lamps, exactly like the network. "
                  "Most people find out how hard 4 bits really are."),
]


# ---------------------------------------------------------------- the network
class Network:
    def __init__(self):
        with open(os.path.join(GAME_DIR, "..", "training", "weights.json")) as f:
            d = json.load(f)
        self.W = [np.array(w, dtype=np.float32) for w in d["W"]]
        self.b = [np.array(b, dtype=np.float32) for b in d["b"]]
        self.acts = [np.zeros(4), np.zeros(7), np.zeros(7), np.zeros(2)]

    def __call__(self, bits):
        a0 = np.array(bits, dtype=np.float32)
        a1 = np.tanh(self.W[0] @ a0 + self.b[0])
        a2 = np.tanh(self.W[1] @ a1 + self.b[1])
        a3 = 1.0 / (1.0 + np.exp(-(self.W[2] @ a2 + self.b[2])))
        self.acts = [a0, a1, a2, a3]
        return a3


# ---------------------------------------------------------------- track
def shape_points(kind):
    pts = []
    for i in range(2400):
        t = 2 * math.pi * i / 2400
        if kind == "oval":
            x, y = 860 * math.cos(t), 440 * math.sin(t)
        elif kind == "lobe":
            r = 400 * (1 + 0.18 * math.cos(3 * t)); x, y = 1.6 * r * math.cos(t), r * math.sin(t)
        elif kind == "peanut":
            r = 380 * (1 + 0.38 * math.cos(2 * t)); x, y = 1.55 * r * math.cos(t), 1.15 * r * math.sin(t)
        else:
            r = 390 * (1 + 0.22 * math.cos(3 * t) + 0.08 * math.sin(5 * t)); x, y = 1.55 * r * math.cos(t), r * math.sin(t)
        pts.append((WW / 2 + x, WH / 2 + y))
    return pts


def resample(pts, step=2.0):
    out, carry = [pts[0]], 0.0
    for i in range(1, len(pts) + 1):
        a, b = pts[i - 1], pts[i % len(pts)]
        d = math.hypot(b[0] - a[0], b[1] - a[1]); t0 = 0.0
        while d > 0 and carry + d - t0 >= step:
            t0 += step - carry; f = t0 / d
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)); carry = 0.0
        carry += d - t0
    return out


class Track:
    def __init__(self, pts, style):
        self.P = resample(pts)
        n = len(self.P)
        self.S = [0.0] * n
        for i in range(1, n):
            self.S[i] = self.S[i - 1] + math.hypot(self.P[i][0] - self.P[i - 1][0], self.P[i][1] - self.P[i - 1][1])
        self.L = self.S[-1] + math.hypot(self.P[0][0] - self.P[-1][0], self.P[0][1] - self.P[-1][1])
        self.n = n
        self.mask = np.zeros((WH, WW), dtype=np.uint8)
        yy, xx = np.mgrid[-10:11, -10:11]
        disc = (xx * xx + yy * yy) <= (TAPE / 2) ** 2
        # world surface for the chase camera (ZOOM px/mm), with a tiled floor
        self.world = pygame.Surface((int(WW * ZOOM), int(WH * ZOOM)))
        self.world.fill(FLOOR)
        tile = int(150 * ZOOM)
        for ty in range(0, self.world.get_height(), tile):
            for tx in range(0, self.world.get_width(), tile):
                if (tx // tile + ty // tile) % 2:
                    pygame.draw.rect(self.world, (219, 226, 234), (tx, ty, tile, tile))
        for g in range(0, WW + 1, 150):
            pygame.draw.line(self.world, (206, 214, 224), (g * ZOOM, 0), (g * ZOOM, WH * ZOOM))
        for g in range(0, WH + 1, 150):
            pygame.draw.line(self.world, (206, 214, 224), (0, g * ZOOM), (WW * ZOOM, g * ZOOM))
        segs = [(0, .15, "solid"), (.15, .45, "dashed"), (.45, .55, "solid"), (.55, .9, "dotted"), (.9, 1.01, "solid")]
        self.on = []
        for i, (x, y) in enumerate(self.P):
            st = style
            if st == "mixed":
                f = self.S[i] / self.L
                st = next(s for a, b, s in segs if a <= f < b)
            on = not (st == "dashed" and self.S[i] % 162 >= 81) and not (st == "dotted" and self.S[i] % 100 >= TAPE)
            self.on.append(on)
            if not on:
                continue
            ix, iy = int(round(x)), int(round(y))
            if 10 <= ix < WW - 10 and 10 <= iy < WH - 10:
                self.mask[iy - 10:iy + 11, ix - 10:ix + 11] |= disc
                pygame.draw.circle(self.world, TAPE_COL, (x * ZOOM, y * ZOOM), TAPE / 2 * ZOOM)
        # start / finish line
        a, b = self.P[0], self.P[3]
        ang = math.atan2(b[1] - a[1], b[0] - a[0]); nx, ny = -math.sin(ang), math.cos(ang)
        for k in range(-4, 4):
            c = (255, 255, 255) if k % 2 else INK
            p0 = ((a[0] + nx * k * 9) * ZOOM, (a[1] + ny * k * 9) * ZOOM)
            pygame.draw.circle(self.world, c, p0, 4)
        self.mini = pygame.transform.smoothscale(self.world, (SIDE - 40, int((SIDE - 40) * WH / WW)))

    def tape(self, x, y):
        ix, iy = int(round(x)), int(round(y))
        return 0 <= ix < WW and 0 <= iy < WH and self.mask[iy, ix] == 1


# ---------------------------------------------------------------- particles
class Particles:
    def __init__(self):
        self.p = []

    def burst(self, x, y, colours, n=30, speed=260, life=0.9):
        for _ in range(n):
            a = random.uniform(0, 2 * math.pi); v = random.uniform(.3, 1) * speed
            self.p.append([x, y, math.cos(a) * v, math.sin(a) * v, life, life, random.choice(colours)])

    def update(self, dt):
        for q in self.p:
            q[0] += q[2] * dt; q[1] += q[3] * dt; q[2] *= .94; q[3] *= .94; q[4] -= dt
        self.p = [q for q in self.p if q[4] > 0]

    def draw(self, surf, cam):
        for x, y, _, _, life, full, col in self.p:
            sx, sy = cam(x, y)
            pygame.draw.circle(surf, col, (sx, sy), max(1, int(5 * life / full)))


# ---------------------------------------------------------------- car (same model as sim/hil_sim.cpp)
class Car:
    def __init__(self, track, colour, brain=None, weak=1.0):
        self.track, self.colour, self.brain, self.weak = track, colour, brain, weak
        self.laps = 0; self.fails = 0; self.steer = 0
        self.time_ms = 0; self.lap_start = 0; self.best_lap = None; self.last_lap = None
        self.streak_ms = 0; self.points = 0.0; self.wheel_phase = 0.0
        self.place(0)

    def place(self, idx):
        T = self.track
        for k in range(T.n):
            i = (idx + k) % T.n
            if T.tape(*T.P[i]):
                idx = i; break
        a, b = T.P[idx], T.P[(idx + 3) % T.n]
        self.x, self.y = a
        self.th = math.atan2(b[1] - a[1], b[0] - a[0])
        self.vl = self.vr = 0.0; self.dl = self.dr = 0
        self.t = 0; self.seen = 0; self.idx = idx; self.prog = 0.0; self.frozen = 0
        self.bits = [0, 0, 0, 0]; self.out = (0.0, 0.0); self.trail = []

    def distance(self):
        return self.laps + self.prog / self.track.L

    def speed(self):
        return abs(self.vl + self.vr) / 2

    def multiplier(self):
        return min(3.0, 1.0 + 0.5 * (self.streak_ms // 5000))

    def nearest(self):
        T, best, bi = self.track, 1e18, self.idx
        for k in range(-40, 41):
            i = (self.idx + k) % T.n
            dx, dy = T.P[i][0] - self.x, T.P[i][1] - self.y
            d = dx * dx + dy * dy
            if d < best:
                best, bi = d, i
        return bi, math.sqrt(best)

    def lose(self):
        self.fails += 1; self.frozen = 1200; self.vl = self.vr = 0.0; self.dl = self.dr = 0; self.streak_ms = 0
        return "lost"

    def step(self):
        """Advance 1 ms. Returns 'lap', 'lost' or None."""
        T = self.track
        self.time_ms += 1
        if self.frozen > 0:
            self.frozen -= 1
            if self.frozen == 0:
                keep = (self.laps, self.fails, self.time_ms, self.lap_start, self.best_lap, self.last_lap, self.points)
                self.place((self.idx + 30) % T.n)
                self.laps, self.fails, self.time_ms, self.lap_start, self.best_lap, self.last_lap, self.points = keep
            return None
        if self.t % 5 == 0:                                   # the firmware's 5 ms control step
            fx, fy, lx, ly = math.cos(self.th), math.sin(self.th), math.sin(self.th), -math.cos(self.th)
            any_on = 0
            for i in range(4):
                lat = (1.5 - i) * SPACING
                px, py = self.x + fx * AHEAD + lx * lat, self.y + fy * AHEAD + ly * lat
                hit = T.tape(px, py) + sum(T.tape(px + 4 * math.cos(a), py + 4 * math.sin(a))
                                           for a in (0, .785, 1.571, 2.356, 3.142, 3.927, 4.712, 5.498))
                self.bits[i] = 1 if hit * 2 >= 9 else 0
                any_on |= self.bits[i]
            if any_on:
                self.seen = self.t
            if self.t - self.seen > 3000:                      # firmware gives up after 3 s without the line
                return self.lose()
            if self.brain is not None:
                self.out = tuple(float(v) for v in self.brain(self.bits))
            else:
                self.out = {-1: (0.3, 0.95), 1: (0.95, 0.3), 0: (0.85, 0.85)}[self.steer]
            self.dl = 70 + int(self.out[0] * 185); self.dr = 70 + int(self.out[1] * 185)
        tgt = lambda d: 0.0 if d <= STALL else (d - STALL) / (255 - STALL) * VMAX
        self.vl += (tgt(self.dl) - self.vl) * 0.001 / TAU
        self.vr += (tgt(self.dr) * self.weak - self.vr) * 0.001 / TAU
        v = (self.vl + self.vr) / 2
        self.th += (self.vl - self.vr) / WHEELBASE * 0.001
        self.x += math.cos(self.th) * v * 0.001; self.y += math.sin(self.th) * v * 0.001
        self.wheel_phase += v * 0.001
        self.t += 1; self.streak_ms += 1
        if self.t % 20 == 0:
            i, d = self.nearest()
            ds = T.S[i] - T.S[self.idx]
            if ds > T.L / 2: ds -= T.L
            if ds < -T.L / 2: ds += T.L
            self.prog += ds; self.idx = i
            if ds > 0:
                self.points += ds / 10 * self.multiplier()
            self.trail.append((self.x, self.y)); self.trail = self.trail[-120:]
            if d > 70:
                return self.lose()
            if self.prog >= T.L:
                self.laps += 1; self.prog -= T.L
                lap = (self.time_ms - self.lap_start) / 1000; self.lap_start = self.time_ms; self.last_lap = lap
                self.best_lap = lap if self.best_lap is None else min(self.best_lap, lap)
                return "lap"
        return None

    def draw(self, surf, cam, z):
        """Draw with a camera function cam(x_mm, y_mm) -> screen px and zoom z (px per mm)."""
        if len(self.trail) > 1:
            pts = [cam(x, y) for x, y in self.trail]
            for k in range(1, len(pts)):
                a = k / len(pts)
                col = tuple(int(255 - (255 - c) * a * .8) for c in self.colour)
                pygame.draw.line(surf, col, pts[k - 1], pts[k], max(2, int(4 * z)))
        c, s = math.cos(self.th), math.sin(self.th)
        to = lambda px, py: cam(self.x + px * c - py * s, self.y + px * s + py * c)
        # sensor beams on the floor
        for i in range(4):
            lat = (1.5 - i) * SPACING * -1
            if self.bits[i]:
                glow = pygame.Surface((int(40 * z), int(40 * z)), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 60, 40, 90), glow.get_rect().center, int(18 * z))
                surf.blit(glow, glow.get_rect(center=to(70, lat)))
        # shadow
        sh = [to(-58 + 6, -38 + 6), to(48 + 6, -38 + 6), to(48 + 6, 38 + 6), to(-58 + 6, 38 + 6)]
        shadow = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(shadow, (0, 0, 0, 45), sh); surf.blit(shadow, (0, 0))
        # wheels with moving tread marks
        for wy in (-42, 42):
            pygame.draw.polygon(surf, (24, 28, 36), [to(-15, wy - 7), to(15, wy - 7), to(15, wy + 7), to(-15, wy + 7)])
            off = (self.wheel_phase * 0.4) % 10
            for k in range(-2, 3):
                xx = k * 10 + off - 5
                if -14 < xx < 14:
                    pygame.draw.line(surf, (70, 78, 92), to(xx, wy - 6), to(xx, wy + 6), 1)
        # body, battery, board, sensor bar
        pygame.draw.polygon(surf, self.colour, [to(-55, -34), to(45, -34), to(45, 34), to(-55, 34)])
        pygame.draw.polygon(surf, INK, [to(-55, -34), to(45, -34), to(45, 34), to(-55, 34)], 2)
        pygame.draw.polygon(surf, (250, 250, 250), [to(-48, -18), to(-20, -18), to(-20, 18), to(-48, 18)])
        pygame.draw.polygon(surf, (20, 30, 48), [to(-12, -16), to(30, -16), to(30, 16), to(-12, 16)])
        pygame.draw.polygon(surf, (190, 196, 205), [to(-2, -8), to(14, -8), to(14, 8), to(-2, 8)])
        pygame.draw.polygon(surf, (40, 40, 48), [to(45, -4), to(64, -4), to(64, 4), to(45, 4)])
        pygame.draw.polygon(surf, (30, 70, 190), [to(64, -40), to(76, -40), to(76, 40), to(64, 40)])
        for i in range(4):
            pygame.draw.circle(surf, RED if self.bits[i] else (241, 245, 249), to(70, (1.5 - i) * SPACING * -1), max(2, int(5 * z)))


# ---------------------------------------------------------------- sound (made in code, no files needed)
class Sound:
    def __init__(self):
        self.ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            self.beep = self.tone([880], 0.12); self.go = self.tone([1320], 0.35)
            self.lap = self.tone([660, 880, 1320], 0.09); self.lost = self.tone([300, 200], 0.18, square=True)
            self.win = self.tone([523, 659, 784, 1047], 0.14); self.lose = self.tone([392, 330, 262], 0.2)
            self.streak = self.tone([988, 1319], 0.07)
            self.ok = True
        except (pygame.error, ValueError, TypeError):
            self.ok = False                      # no sound device: play silently

    def tone(self, freqs, dur, square=False):
        parts = []
        for f in freqs:
            t = np.arange(int(self.rate * dur)) / self.rate
            w = np.sign(np.sin(2 * np.pi * f * t)) * 0.4 if square else np.sin(2 * np.pi * f * t)
            parts.append(w * np.hanning(len(t)) * 0.35)
        wave = (np.concatenate(parts) * 32767).astype(np.int16)
        if self.channels > 1:
            wave = np.ascontiguousarray(np.column_stack([wave] * self.channels))
        return pygame.sndarray.make_sound(wave)

    def play(self, name):
        if self.ok:
            getattr(self, name).play()


# ---------------------------------------------------------------- saved scores
def load_scores():
    try:
        with open(SAVE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_score(key, value):
    s = load_scores()
    if value > s.get(key, 0):
        s[key] = round(value, 1)
        try:
            with open(SAVE_FILE, "w") as f:
                json.dump(s, f)
        except OSError:
            pass
        return True
    return False


# ---------------------------------------------------------------- the game
class Game:
    def __init__(self, selftest=False):
        pygame.init()
        pygame.display.set_caption("Be the AI: line follower")
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.view = pygame.Surface((VIEW_W, VIEW_H))
        self.clock = pygame.time.Clock()
        self.f_huge = pygame.font.SysFont("arialblack,arial", 110, bold=True)
        self.f_big = pygame.font.SysFont("arialblack,arial", 60, bold=True)
        self.f_mid = pygame.font.SysFont("arial", 28, bold=True)
        self.f = pygame.font.SysFont("arial", 20)
        self.f_b = pygame.font.SysFont("arial", 20, bold=True)
        self.f_small = pygame.font.SysFont("arial", 16)
        self.f_mono = pygame.font.SysFont("menlo,consolas,couriernew", 15, bold=True)
        self.brain = Network()
        self.sound = Sound()
        self.fx = Particles()
        self.selftest = selftest
        self.state = "menu"; self.menu_i = 0; self.level_i = 0; self.hard = False; self.watch = False
        self.drawn = None; self.draw_buf = []; self.chase = True; self.shake = 0.0; self.t_anim = 0.0
        self.menu_rects, self.level_rects = [], []
        self.again_rect = self.menu_rect = pygame.Rect(0, 0, 0, 0)
        self.preview = Track(shape_points("wind"), "mixed")
        self.preview_car = Car(self.preview, AI, self.brain, 0.94)

    # ---------- small drawing helpers
    def text(self, s, font, col, pos, anchor="topleft", surf=None):
        img = font.render(s, True, col); r = img.get_rect(**{anchor: pos}); (surf or self.screen).blit(img, r); return r

    def wrap(self, s, font, width):
        words, lines, cur = s.split(), [], ""
        for w in words:
            if font.size(cur + " " + w)[0] > width and cur:
                lines.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        return lines + [cur]

    def card(self, rect, hot=False, colour=None):
        sh = rect.move(0, 4)
        pygame.draw.rect(self.screen, (225, 231, 239), sh, border_radius=14)
        pygame.draw.rect(self.screen, colour or ((255, 246, 228) if hot else PANEL), rect, border_radius=14)
        pygame.draw.rect(self.screen, YOU if hot else LINE, rect, 2, border_radius=14)

    def button(self, label, rect, hot):
        sh = rect.move(0, 4)
        pygame.draw.rect(self.screen, (214, 140, 0) if hot else (220, 227, 236), sh, border_radius=12)
        pygame.draw.rect(self.screen, YOU if hot else PANEL, rect, border_radius=12)
        pygame.draw.rect(self.screen, YOU if hot else LINE, rect, 2, border_radius=12)
        self.text(label, self.f_mid, (255, 255, 255) if hot else INK, rect.center, "center")

    # ---------- flow
    def start_level(self, i):
        lv = LEVELS[i]; self.level_i = i
        if lv["shape"] == "draw":
            if not self.drawn:
                self.state = "draw"; self.draw_buf = []; return
            pts = self.drawn
        else:
            pts = shape_points(lv["shape"])
        self.track = Track(pts, lv["style"])
        self.you = Car(self.track, YOU, None, lv["weak"])
        self.ai = Car(self.track, AI, self.brain, lv["weak"])
        self.t_left = RACE_SECONDS; self.countdown = 3.999; self.last_count = 4; self.paused = False
        self.fx = Particles(); self.cam_x, self.cam_y = self.you.x, self.you.y; self.popups = []
        self.state = "race"

    def finish(self):
        yd, ad = self.you.distance(), self.ai.distance()
        key = f"{LEVELS[self.level_i]['name']}|{'hard' if self.hard else 'normal'}"
        self.new_best = save_score(key, self.you.points) if not self.watch else False
        self.stars = 3 if yd > ad else 2 if yd > 0.75 * ad else 1
        self.result = (yd, ad)
        self.sound.play("win" if yd > ad and not self.watch else "lose")
        if yd > ad and not self.watch:
            for _ in range(6):
                self.fx.burst(random.uniform(200, SCREEN_W - 200), random.uniform(150, 400), [YOU, AI, GREEN, RED], 40, 400, 1.6)
        self.state = "result"

    def run(self):
        frames = 0
        while True:
            dt = self.clock.tick(60) / 1000
            frames += 1
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                self.handle(e)
            if self.selftest and not self.autoplay(frames):
                return
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def autoplay(self, frames):
        """--selftest: visits every screen and plays one race with a simple driver, then quits."""
        if frames == 5: self.state = "howto"
        if frames == 10: self.state = "levels"
        if frames == 15: self.hard = False; self.start_level(3)
        if self.state == "race" and self.countdown <= 0:
            b = self.you.bits
            self.you.steer = -1 if (b[0] or b[1]) and not (b[2] or b[3]) else 1 if (b[2] or b[3]) and not (b[0] or b[1]) else 0
            self.t_left -= 0.5
        if self.state == "result":
            print(f"selftest ok: you {self.result[0]:.2f} laps ({self.you.points:.0f} pts), AI {self.result[1]:.2f} laps, stars {self.stars}")
            return False
        return frames < 4000

    def handle(self, e):
        down = e.type == pygame.KEYDOWN
        mouse = e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN)
        click = e.type == pygame.MOUSEBUTTONDOWN
        if self.state == "menu":
            items = self.menu_items()
            if down and e.key in (pygame.K_UP, pygame.K_w): self.menu_i = (self.menu_i - 1) % len(items)
            if down and e.key in (pygame.K_DOWN, pygame.K_s): self.menu_i = (self.menu_i + 1) % len(items)
            if down and e.key in (pygame.K_RETURN, pygame.K_SPACE): self.choose(items[self.menu_i][1])
            if mouse:
                for i, r in enumerate(self.menu_rects):
                    if r.collidepoint(e.pos):
                        self.menu_i = i
                        if click: self.choose(items[i][1])
        elif self.state == "howto":
            if (down and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE)) or click:
                self.state = "menu"
        elif self.state == "levels":
            if down and e.key in (pygame.K_UP, pygame.K_w): self.level_i = (self.level_i - 1) % len(LEVELS)
            if down and e.key in (pygame.K_DOWN, pygame.K_s): self.level_i = (self.level_i + 1) % len(LEVELS)
            if down and e.key in (pygame.K_RETURN, pygame.K_SPACE): self.start_level(self.level_i)
            if down and e.key == pygame.K_ESCAPE: self.state = "menu"
            if mouse:
                for i, r in enumerate(self.level_rects):
                    if r.collidepoint(e.pos):
                        self.level_i = i
                        if click: self.start_level(i)
        elif self.state == "draw":
            if click: self.draw_buf = [self.to_world(e.pos)]
            if e.type == pygame.MOUSEMOTION and e.buttons[0] and self.draw_buf:
                p = self.to_world(e.pos); q = self.draw_buf[-1]
                if math.hypot(p[0] - q[0], p[1] - q[1]) > 15: self.draw_buf.append(p)
            if e.type == pygame.MOUSEBUTTONUP and len(self.draw_buf) > 10: self.finish_drawing()
            if down and e.key == pygame.K_ESCAPE: self.state = "levels"
        elif self.state == "race":
            if down and e.key in (pygame.K_p, pygame.K_ESCAPE): self.paused = not self.paused
            if down and e.key == pygame.K_c: self.chase = not self.chase
            if down and self.paused and e.key == pygame.K_q: self.state = "menu"
        elif self.state == "result":
            if down and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r): self.start_level(self.level_i)
            if down and e.key == pygame.K_ESCAPE: self.state = "menu"
            if click:
                if self.again_rect.collidepoint(e.pos): self.start_level(self.level_i)
                if self.menu_rect.collidepoint(e.pos): self.state = "menu"

    def menu_items(self):
        return [("Race the AI", "normal"), ("Hard mode: sensors only", "hard"), ("Watch the AI drive", "watch"),
                ("How to play", "howto"), ("Quit", "quit")]

    def choose(self, what):
        if what == "quit": pygame.quit(); sys.exit()
        if what == "howto": self.state = "howto"; return
        self.hard = what == "hard"; self.watch = what == "watch"; self.state = "levels"

    def to_world(self, pos):
        s = min(SCREEN_W / WW, (SCREEN_H - TOP) / WH); ox = (SCREEN_W - WW * s) / 2
        return ((pos[0] - ox) / s, (pos[1] - TOP) / s)

    def finish_drawing(self):
        P = self.draw_buf
        length = sum(math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]) for i in range(1, len(P)))
        if length < 1800:
            self.draw_msg = "Too short. Draw a bigger loop."; self.draw_buf = []; return
        for _ in range(3):
            Q = []
            for i in range(len(P)):
                a, b = P[i], P[(i + 1) % len(P)]
                Q += [(.75 * a[0] + .25 * b[0], .75 * a[1] + .25 * b[1]), (.25 * a[0] + .75 * b[0], .25 * a[1] + .75 * b[1])]
            P = Q
        self.drawn = [(min(WW - 80, max(80, x)), min(WH - 80, max(80, y))) for x, y in P]
        self.start_level(self.level_i)

    def update(self, dt):
        self.t_anim += dt
        self.fx.update(dt); self.shake = max(0.0, self.shake - dt * 2.5)
        if self.state == "menu":
            for _ in range(int(dt * 1000)): self.preview_car.step()
        if self.state != "race" or self.paused:
            return
        if self.countdown > 0:
            self.countdown -= dt
            c = int(math.ceil(self.countdown))
            if c != self.last_count:
                self.last_count = c; self.sound.play("go" if c <= 0 else "beep")
            return
        keys = pygame.key.get_pressed()
        l, r = keys[pygame.K_LEFT] or keys[pygame.K_a], keys[pygame.K_RIGHT] or keys[pygame.K_d]
        if not self.selftest:
            self.you.steer = -1 if l and not r else 1 if r and not l else 0
        before = self.you.multiplier()
        for _ in range(int(min(dt, 0.05) * 1000)):
            for car, who in ((self.you, "you"), (self.ai, "ai")):
                if self.watch and who == "you":
                    continue
                ev = car.step()
                if ev and (who == "you" or (self.watch and who == "ai")):
                    self.sound.play(ev)
                    if ev == "lost":
                        self.fx.burst(car.x, car.y, [RED, (255, 160, 0), INK], 36, 300); self.shake = 1.0
                        self.popups.append([car.x, car.y, "LINE LOST", RED, 1.4])
                    if ev == "lap":
                        self.fx.burst(car.x, car.y, [YOU, AI, GREEN, (255, 255, 255)], 60, 380, 1.3)
                        self.popups.append([car.x, car.y, f"LAP {car.laps}  {car.last_lap:.1f}s", GREEN, 1.6])
        if self.you.multiplier() > before and not self.watch:
            self.sound.play("streak"); self.popups.append([self.you.x, self.you.y, f"STREAK x{self.you.multiplier():.1f}", YOU, 1.3])
        for p in self.popups: p[4] -= dt; p[1] -= 40 * dt
        self.popups = [p for p in self.popups if p[4] > 0]
        self.t_left -= dt
        if self.t_left <= 0:
            self.t_left = 0; self.finish()

    # ---------- drawing
    def draw(self):
        self.screen.fill(BG)
        getattr(self, "draw_" + self.state)()

    def draw_menu(self):
        s = min(SCREEN_W / WW, (SCREEN_H) / WH); ox = (SCREEN_W - WW * s) / 2; oy = (SCREEN_H - WH * s) / 2
        bg = pygame.transform.smoothscale(self.preview.world, (int(WW * s), int(WH * s)))
        self.screen.blit(bg, (ox, oy))
        self.preview_car.draw(self.screen, lambda x, y: (ox + x * s, oy + y * s), s)
        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); shade.fill((245, 248, 252, 200)); self.screen.blit(shade, (0, 0))
        bob = math.sin(self.t_anim * 2) * 4
        self.text("BE THE", self.f_big, INK, (SCREEN_W // 2, 70 + bob), "center")
        self.text("AI", self.f_huge, AI, (SCREEN_W // 2, 150 + bob), "center")
        self.text("Race a neural network at its own job: following a line with 4 sensors", self.f, MUTED, (SCREEN_W // 2, 222), "center")
        self.menu_rects = []
        for i, (label, _) in enumerate(self.menu_items()):
            r = pygame.Rect(0, 0, 460, 60); r.center = (SCREEN_W // 2, 300 + i * 78)
            self.button(label, r, i == self.menu_i); self.menu_rects.append(r)
        self.text("Arrow keys + ENTER, or click", self.f_small, MUTED, (SCREEN_W // 2, SCREEN_H - 30), "center")

    def draw_howto(self):
        self.text("HOW TO PLAY", self.f_big, INK, (60, 26))
        colw = (SCREEN_W - 160) // 2
        for col, items in enumerate((HOW_TO[:4], HOW_TO[4:])):
            x, y = 60 + col * (colw + 40), 120
            for title, body in items:
                self.text(title, self.f_mid, AI, (x, y)); y += 34
                for line in self.wrap(body, self.f, colw):
                    self.text(line, self.f, INK, (x, y)); y += 25
                y += 16
        self.text("Press ENTER or click to go back", self.f_small, MUTED, (60, SCREEN_H - 34))

    def draw_levels(self):
        mode = "WATCH THE AI" if self.watch else "HARD MODE" if self.hard else "RACE THE AI"
        self.text("CHOOSE A TRACK", self.f_big, INK, (60, 26)); self.text(mode, self.f_mid, RED if self.hard else AI, (64, 104))
        scores = load_scores(); self.level_rects = []
        for i, lv in enumerate(LEVELS):
            r = pygame.Rect(60, 160 + i * 112, SCREEN_W - 120, 96); hot = i == self.level_i
            self.card(r, hot)
            badge = pygame.Rect(r.x + 18, r.y + 18, 60, 60)
            pygame.draw.rect(self.screen, YOU if hot else (236, 241, 247), badge, border_radius=12)
            self.text(str(i + 1), self.f_big, (255, 255, 255) if hot else MUTED, badge.center, "center")
            self.text(lv["name"], self.f_mid, INK, (r.x + 100, r.y + 16))
            self.text(lv["tip"], self.f, MUTED, (r.x + 100, r.y + 56))
            best = scores.get(f"{lv['name']}|{'hard' if self.hard else 'normal'}")
            if best is not None:
                self.text(f"best {best:.0f} pts", self.f_b, YOU, (r.right - 24, r.y + 18), "topright")
            self.level_rects.append(r)
        self.text("ENTER or click to start · ESC back", self.f_small, MUTED, (60, SCREEN_H - 30))

    def draw_draw(self):
        s = min(SCREEN_W / WW, (SCREEN_H - TOP) / WH); ox = (SCREEN_W - WW * s) / 2
        pygame.draw.rect(self.screen, FLOOR, (ox, TOP, WW * s, WH * s))
        if len(self.draw_buf) > 1:
            pygame.draw.lines(self.screen, TAPE_COL, False, [(ox + x * s, TOP + y * s) for x, y in self.draw_buf], 6)
        self.text("DRAW YOUR TRACK", self.f_mid, INK, (24, 16))
        self.text(getattr(self, "draw_msg", "Hold the mouse button and draw one closed loop, then let go. ESC to go back."),
                  self.f, MUTED, (330, 22))

    def camera(self):
        """Returns (blit offset, cam function, zoom) for the race view."""
        target = self.ai if self.watch else self.you
        if self.chase:
            look = 120
            tx, ty = target.x + math.cos(target.th) * look, target.y + math.sin(target.th) * look
            self.cam_x += (tx - self.cam_x) * 0.12; self.cam_y += (ty - self.cam_y) * 0.12
            sx = random.uniform(-1, 1) * 10 * self.shake; sy = random.uniform(-1, 1) * 10 * self.shake
            ox = VIEW_W / 2 - self.cam_x * ZOOM + sx; oy = VIEW_H / 2 - self.cam_y * ZOOM + sy
            return (ox, oy), (lambda x, y: (ox + x * ZOOM, oy + y * ZOOM)), ZOOM
        z = min(VIEW_W / WW, VIEW_H / WH); ox = (VIEW_W - WW * z) / 2; oy = (VIEW_H - WH * z) / 2
        return None, (lambda x, y: (ox + x * z, oy + y * z)), z

    def draw_race(self):
        v = self.view; v.fill((210, 218, 228))
        off, cam, z = self.camera()
        if off is not None:
            v.blit(self.track.world, off)
        else:
            v.blit(pygame.transform.smoothscale(self.track.world, (int(WW * z), int(WH * z))), cam(0, 0))
        if not self.watch:
            self.you.draw(v, cam, z)
        self.ai.draw(v, cam, z)
        self.fx.draw(v, cam)
        for x, y, msg, col, life in self.popups:
            img = self.f_b.render(msg, True, col); img.set_alpha(int(255 * min(1, life)))
            v.blit(img, img.get_rect(center=cam(x, y - 90)))
        if self.hard and self.countdown <= 0:
            v.fill((228, 234, 242))
            self.text("TRACK HIDDEN", self.f_big, (190, 200, 214), (VIEW_W // 2, 120), "center", v)
            self.text("Steer with only the 4 sensor lamps, like the network", self.f, MUTED, (VIEW_W // 2, 175), "center", v)
            self.draw_lamps(v, self.you.bits, (VIEW_W // 2, VIEW_H // 2 + 40), 64)
        if self.countdown > 0:
            c = int(math.ceil(self.countdown)); frac = self.countdown - math.floor(self.countdown)
            img = self.f_huge.render(str(c) if c > 0 else "GO", True, RED)
            img = pygame.transform.rotozoom(img, 0, 0.7 + frac * 0.6)
            v.blit(img, img.get_rect(center=(VIEW_W // 2, VIEW_H // 2 - 40)))
            tip = self.f_b.render(LEVELS[self.level_i]["tip"], True, INK)
            pygame.draw.rect(v, PANEL, tip.get_rect(center=(VIEW_W // 2, VIEW_H // 2 + 60)).inflate(30, 16), border_radius=10)
            v.blit(tip, tip.get_rect(center=(VIEW_W // 2, VIEW_H // 2 + 60)))
        self.screen.blit(v, (0, TOP))
        self.draw_topbar(); self.draw_side()
        if self.paused:
            shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); shade.fill((245, 248, 252, 215)); self.screen.blit(shade, (0, 0))
            self.text("PAUSED", self.f_big, INK, (SCREEN_W // 2, SCREEN_H // 2 - 30), "center")
            self.text("P to resume · Q to quit to menu", self.f, MUTED, (SCREEN_W // 2, SCREEN_H // 2 + 30), "center")

    def draw_topbar(self):
        pygame.draw.rect(self.screen, PANEL, (0, 0, SCREEN_W, TOP)); pygame.draw.line(self.screen, LINE, (0, TOP - 1), (SCREEN_W, TOP - 1), 2)
        lv = LEVELS[self.level_i]
        self.text(f"{self.level_i + 1}. {lv['name'].upper()}", self.f_mid, INK, (20, 16))
        x = 360
        if not self.watch:
            self.text(f"YOU {self.you.points:5.0f} pts", self.f_mid, YOU, (x, 16))
            self.text(f"x{self.you.multiplier():.1f}", self.f_b, YOU, (x + 200, 22))
        self.text(f"AI {self.ai.points:5.0f} pts", self.f_mid, AI, (x + 290, 16))
        t = max(0, self.t_left); bar = pygame.Rect(SCREEN_W - 230, 22, 150, 20)
        pygame.draw.rect(self.screen, (236, 241, 247), bar, border_radius=10)
        pygame.draw.rect(self.screen, RED if t < 10 else GREEN, (bar.x, bar.y, bar.w * t / RACE_SECONDS, bar.h), border_radius=10)
        self.text(f"{int(math.ceil(t))}s", self.f_mid, RED if t < 10 else INK, (SCREEN_W - 20, 16), "topright")

    def draw_lamps(self, surf, bits, center, size):
        pad = pygame.Rect(0, 0, 4 * size * 2 + 30, size * 2 + 30); pad.center = center
        pygame.draw.rect(surf, PANEL, pad, border_radius=14); pygame.draw.rect(surf, LINE, pad, 2, border_radius=14)
        for i in range(4):
            cx = pad.x + 15 + size + i * size * 2
            if bits[i]:
                glow = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow, (255, 60, 40, 70), (size * 2, size * 2), int(size * 1.4)); surf.blit(glow, (cx - size * 2, pad.centery - size * 2))
            pygame.draw.circle(surf, RED if bits[i] else (214, 222, 232), (cx, pad.centery), size - 5)
            pygame.draw.circle(surf, (150, 20, 15) if bits[i] else (190, 200, 214), (cx, pad.centery), size - 5, 2)

    def gauge(self, center, r, value, colour, label):
        x, y = center
        pygame.draw.arc(self.screen, (226, 232, 240), (x - r, y - r, 2 * r, 2 * r), math.radians(-30), math.radians(210), 8)
        frac = max(0.0, min(1.0, value / VMAX))
        a0, a1 = math.radians(210 - 240 * frac), math.radians(210)
        if frac > 0.01:
            pygame.draw.arc(self.screen, colour, (x - r, y - r, 2 * r, 2 * r), a0, a1, 8)
        self.text(f"{value / 1000:.2f}", self.f_b, INK, (x, y - 6), "center")
        self.text("m/s", self.f_small, MUTED, (x, y + 14), "center")
        self.text(label, self.f_b, colour, (x, y + r - 4), "center")

    def draw_side(self):
        x0 = VIEW_W; pygame.draw.rect(self.screen, PANEL, (x0, TOP, SIDE, SCREEN_H - TOP))
        pygame.draw.line(self.screen, LINE, (x0, TOP), (x0, SCREEN_H), 2)
        # minimap
        mini = self.track.mini; mx, my = x0 + 20, TOP + 14
        if not self.hard or self.countdown > 0:
            self.screen.blit(mini, (mx, my))
            ms = mini.get_width() / WW
            for car in ((self.ai,) if self.watch else (self.ai, self.you)):
                pygame.draw.circle(self.screen, car.colour, (mx + car.x * ms, my + car.y * ms), 6)
                pygame.draw.circle(self.screen, INK, (mx + car.x * ms, my + car.y * ms), 6, 1)
        else:
            pygame.draw.rect(self.screen, (236, 241, 247), (mx, my, mini.get_width(), mini.get_height()), border_radius=8)
            self.text("map hidden", self.f_small, MUTED, (mx + mini.get_width() // 2, my + mini.get_height() // 2), "center")
        y = my + mini.get_height() + 10
        car = self.ai if self.watch else self.you
        self.text("YOUR SENSORS" if not self.watch else "AI SENSORS", self.f_mono, MUTED, (x0 + 20, y)); y += 22
        self.draw_lamps(self.screen, car.bits, (x0 + SIDE // 2, y + 26), 22); y += 70
        # gauges
        if not self.watch:
            self.gauge((x0 + 88, y + 52), 46, self.you.speed(), YOU, "YOU")
        self.gauge((x0 + SIDE - 88, y + 52), 46, self.ai.speed(), AI, "AI")
        y += 112
        # laps
        def lap_line(car, name, yy):
            best = f"{car.best_lap:.1f}s" if car.best_lap else "--"
            self.text(f"{name}  lap {car.laps}  best {best}  lost {car.fails}", self.f_small, car.colour, (x0 + 20, yy))
        if not self.watch:
            lap_line(self.you, "YOU", y); y += 20
        lap_line(self.ai, "AI ", y); y += 28
        # the AI's brain
        self.text("THE AI'S BRAIN, LIVE", self.f_mono, MUTED, (x0 + 20, y)); y += 20
        self.draw_brain(pygame.Rect(x0 + 16, y, SIDE - 32, SCREEN_H - y - 12))

    def draw_brain(self, r):
        acts = self.brain.acts
        sizes = [4, 7, 7, 2]
        cols = [r.x + 16 + k * (r.w - 90) / 3 for k in range(4)]
        pos = [[(cols[l], r.y + 10 + (i + .5) * (r.h - 20) / sizes[l]) for i in range(sizes[l])] for l in range(4)]
        for l in range(3):
            W = self.brain.W[l]
            for j in range(sizes[l + 1]):
                for i in range(sizes[l]):
                    c = W[j, i] * acts[l][i]
                    if abs(c) < 0.05:
                        continue
                    col = AI if c > 0 else (232, 135, 14)
                    w = max(1, min(4, int(abs(c) * 3)))
                    pygame.draw.line(self.screen, col, pos[l][i], pos[l + 1][j], w)
        for l in range(4):
            for i, p in enumerate(pos[l]):
                a = float(acts[l][i])
                if l == 0:
                    fill = RED if a > 0.5 else (230, 235, 242)
                elif l == 3:
                    k = a; fill = (int(255 - (255 - AI[0]) * k), int(255 - (255 - AI[1]) * k), int(255 - (255 - AI[2]) * k))
                else:
                    base = AI if a >= 0 else (232, 135, 14); k = min(1, abs(a))
                    fill = tuple(int(255 - (255 - c) * k) for c in base)
                pygame.draw.circle(self.screen, fill, p, 9 if l in (0, 3) else 7)
                pygame.draw.circle(self.screen, INK, p, 9 if l in (0, 3) else 7, 1)
        for i, name in enumerate(("L", "R")):
            self.text(f"{name} {float(acts[3][i]):.2f}", self.f_mono, AI, (pos[3][i][0] + 14, pos[3][i][1] - 8))

    def draw_result(self):
        yd, ad = self.result
        win = yd > ad and not self.watch
        title = f"THE AI DROVE {ad:.2f} LAPS" if self.watch else ("YOU BEAT THE NETWORK!" if win else "THE NETWORK WINS")
        self.text(title, self.f_big, YOU if win else AI, (SCREEN_W // 2, 110), "center")
        if not self.watch:
            for k in range(3):
                cx = SCREEN_W // 2 + (k - 1) * 90; cy = 205
                pts = [(cx + math.cos(math.radians(-90 + i * 36)) * (38 if i % 2 == 0 else 16),
                        cy + math.sin(math.radians(-90 + i * 36)) * (38 if i % 2 == 0 else 16)) for i in range(10)]
                pygame.draw.polygon(self.screen, YOU if k < self.stars else (226, 232, 240), pts)
        card = pygame.Rect(0, 0, 760, 220); card.center = (SCREEN_W // 2, 400); self.card(card)
        rows = []
        if not self.watch:
            rows.append(("YOU", self.you, YOU))
        rows.append(("AI", self.ai, AI))
        self.text("", self.f, INK, card.topleft)
        heads = ["", "points", "laps", "best lap", "lost line"]
        xs = [card.x + 40, card.x + 220, card.x + 370, card.x + 500, card.x + 640]
        for h, x in zip(heads, xs):
            self.text(h, self.f_small, MUTED, (x, card.y + 24))
        for k, (name, car, col) in enumerate(rows):
            yy = card.y + 60 + k * 64
            vals = [name, f"{car.points:.0f}", f"{car.distance():.2f}", f"{car.best_lap:.1f}s" if car.best_lap else "--", str(car.fails)]
            for v_, x in zip(vals, xs):
                self.text(v_, self.f_big if x == xs[0] else self.f_mid, col, (x, yy))
        if getattr(self, "new_best", False):
            self.text("New personal best!", self.f_b, GREEN, (SCREEN_W // 2, card.bottom + 22), "center")
        tip = ("Now try hard mode: drive with only the 4 lamps, like the network does." if not self.hard
               else "That is all the car ever knows: 4 lamps, 107 numbers, 200 decisions a second.")
        self.text(tip, self.f, MUTED, (SCREEN_W // 2, card.bottom + 56), "center")
        self.again_rect = pygame.Rect(0, 0, 270, 60); self.again_rect.center = (SCREEN_W // 2 - 155, 700)
        self.menu_rect = pygame.Rect(0, 0, 270, 60); self.menu_rect.center = (SCREEN_W // 2 + 155, 700)
        self.button("Race again (R)", self.again_rect, True); self.button("Menu (ESC)", self.menu_rect, False)
        self.fx.draw(self.screen, lambda x, y: (x, y))


if __name__ == "__main__":
    Game(selftest="--selftest" in sys.argv).run()
    pygame.quit()
