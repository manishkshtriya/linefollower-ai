"""
BE THE AI: the line follower game.

You drive the AI line follower car against its own neural network (the 107 learned weights from this repository).
Same car, same weak motor, same 4 IR sensors. Hard mode turns the lights off: you only see the 4 sensor lamps,
which is everything the network ever sees.

Run:   python3 line_follower_game.py
Needs: Python 3.9+, pygame, numpy   (pip3 install pygame numpy)
"""
import json
import math
import os
import random
import sys

import numpy as np
import pygame

# ---------------------------------------------------------------- constants
SCREEN_W, SCREEN_H = 1280, 800
TOP = 64                                   # height of the score bar
WW, WH = 1900, 1100                        # world size in millimetres
SCALE = min(SCREEN_W / WW, (SCREEN_H - TOP) / WH)
OX = (SCREEN_W - WW * SCALE) / 2
TAPE, WHEELBASE, AHEAD, SPACING = 19, 81, 70, 20      # mm, same as the firmware and simulator
VMAX, STALL, TAU = 450.0, 60, 0.06                     # motor model
RACE_SECONDS = 60
GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE = os.path.join(os.path.expanduser("~"), ".be_the_ai_scores.json")

INK = (238, 243, 249)
MUTED = (138, 155, 177)
BG = (11, 15, 21)
PANEL = (20, 27, 37)
LINE = (38, 50, 67)
YOU = (255, 210, 63)
AI = (63, 215, 242)
RED = (255, 59, 48)
GREEN = (74, 222, 128)
FLOOR = (223, 229, 236)
TAPE_COL = (10, 13, 18)

LEVELS = [
    {"name": "Solid oval", "shape": "oval", "style": "solid", "weak": 1.00,
     "tip": "Warm-up. A solid line, both motors equal."},
    {"name": "Dashed loops", "shape": "lobe", "style": "dashed", "weak": 0.96,
     "tip": "Gaps between dashes. All four lamps go dark in a gap."},
    {"name": "Dotted peanut", "shape": "peanut", "style": "dotted", "weak": 0.94,
     "tip": "Small dots and a weaker right motor that pulls you right."},
    {"name": "The real test", "shape": "wind", "style": "mixed", "weak": 0.92,
     "tip": "Solid, dashed and dotted on a winding track. Right motor 8% weaker."},
    {"name": "Your own track", "shape": "draw", "style": "mixed", "weak": 0.94,
     "tip": "Draw any closed loop with the mouse, then race on it."},
]

HOW_TO = [
    ("THE IDEA", "This car follows black tape using only 4 IR sensors and a tiny neural network (107 numbers). "
                 "You race against that network. Can a human brain beat it?"),
    ("CONTROLS", "Hold LEFT / RIGHT arrow (or A / D) to steer. Let go to drive straight. P or ESC pauses. "
                 "In menus use the arrow keys and ENTER, or click with the mouse."),
    ("THE SENSOR LAMPS", "The 4 lamps in the bottom-right corner are your car's sensors, left to right. A red lamp means that "
                         "sensor is over tape. Line under the left lamps: steer left. Under the right lamps: steer right."),
    ("GAPS", "On dashed and dotted tape all 4 lamps go dark between marks. Keep going straight and you will find "
             "the next mark. If no lamp sees tape for 3 seconds, the car stops itself: you lose the line."),
    ("THE WEAK MOTOR", "Real motors never match. From level 2 the right motor is weaker, so 'straight' slowly "
                       "pulls you to the right. The AI has the same problem."),
    ("SCORING", "Each race lasts 60 seconds. Your score is the distance you drove in laps. Losing the line "
                "costs you time while the car is put back. Beat the AI to get 3 stars."),
    ("HARD MODE", "The lights go off. You only see the 4 lamps, exactly like the network. "
                  "Most people find out how hard 4 bits really are."),
]


# ---------------------------------------------------------------- the network
def load_weights():
    path = os.path.join(GAME_DIR, "..", "training", "weights.json")
    with open(path) as f:
        d = json.load(f)
    return [np.array(w, dtype=np.float32) for w in d["W"]], [np.array(b, dtype=np.float32) for b in d["b"]]


class Network:
    def __init__(self):
        self.W, self.b = load_weights()

    def __call__(self, bits):
        a = np.array(bits, dtype=np.float32)
        a = np.tanh(self.W[0] @ a + self.b[0])
        a = np.tanh(self.W[1] @ a + self.b[1])
        z = self.W[2] @ a + self.b[2]
        return 1.0 / (1.0 + np.exp(-z))


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
        self.surface = pygame.Surface((int(WW * SCALE), int(WH * SCALE)))
        self.surface.fill(FLOOR)
        for gx in range(0, WW + 1, 100):
            pygame.draw.line(self.surface, (207, 215, 225), (gx * SCALE, 0), (gx * SCALE, WH * SCALE))
        for gy in range(0, WH + 1, 100):
            pygame.draw.line(self.surface, (207, 215, 225), (0, gy * SCALE), (WW * SCALE, gy * SCALE))
        segs = [(0, .15, "solid"), (.15, .45, "dashed"), (.45, .55, "solid"), (.55, .9, "dotted"), (.9, 1.01, "solid")]
        for i, (x, y) in enumerate(self.P):
            st = style
            if st == "mixed":
                f = self.S[i] / self.L
                st = next(s for a, b, s in segs if a <= f < b)
            if st == "dashed" and self.S[i] % 162 >= 81:
                continue
            if st == "dotted" and self.S[i] % 100 >= TAPE:
                continue
            ix, iy = int(round(x)), int(round(y))
            if 10 <= ix < WW - 10 and 10 <= iy < WH - 10:
                self.mask[iy - 10:iy + 11, ix - 10:ix + 11] |= disc
                pygame.draw.circle(self.surface, TAPE_COL, (x * SCALE, y * SCALE), max(2, TAPE / 2 * SCALE))

    def tape(self, x, y):
        ix, iy = int(round(x)), int(round(y))
        return 0 <= ix < WW and 0 <= iy < WH and self.mask[iy, ix] == 1


# ---------------------------------------------------------------- car (same model as sim/hil_sim.cpp)
class Car:
    def __init__(self, track, colour, brain=None, weak=1.0):
        self.track, self.colour, self.brain, self.weak = track, colour, brain, weak
        self.laps = 0; self.fails = 0; self.steer = 0
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
        self.fails += 1; self.frozen = 1200; self.vl = self.vr = 0.0; self.dl = self.dr = 0
        return "lost"

    def step(self):
        """Advance 1 ms. Returns 'lap', 'lost' or None."""
        T = self.track
        if self.frozen > 0:
            self.frozen -= 1
            if self.frozen == 0:
                laps, fails = self.laps, self.fails
                self.place((self.idx + 30) % T.n); self.laps, self.fails = laps, fails
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
        self.t += 1
        if self.t % 20 == 0:
            i, d = self.nearest()
            ds = T.S[i] - T.S[self.idx]
            if ds > T.L / 2: ds -= T.L
            if ds < -T.L / 2: ds += T.L
            self.prog += ds; self.idx = i
            self.trail.append((self.x, self.y)); self.trail = self.trail[-90:]
            if d > 70:
                return self.lose()
            if self.prog >= T.L:
                self.laps += 1; self.prog -= T.L
                return "lap"
        return None

    def draw(self, screen):
        if len(self.trail) > 1:
            pygame.draw.lines(screen, tuple(int(c * .7) for c in self.colour), False,
                              [(OX + x * SCALE, TOP + y * SCALE) for x, y in self.trail], 3)
        c, s = math.cos(self.th), math.sin(self.th)
        to = lambda px, py: (OX + (self.x + px * c - py * s) * SCALE, TOP + (self.y + px * s + py * c) * SCALE)
        for wy in (-42, 42):
            pygame.draw.polygon(screen, (17, 22, 29), [to(-14, wy - 6), to(14, wy - 6), to(14, wy + 6), to(-14, wy + 6)])
        pygame.draw.polygon(screen, self.colour, [to(-55, -34), to(45, -34), to(45, 34), to(-55, 34)])
        pygame.draw.polygon(screen, BG, [to(-55, -34), to(45, -34), to(45, 34), to(-55, 34)], 2)
        pygame.draw.polygon(screen, (30, 58, 138), [to(64, -40), to(76, -40), to(76, 40), to(64, 40)])
        for i in range(4):
            pygame.draw.circle(screen, RED if self.bits[i] else (241, 245, 249), to(70, (1.5 - i) * SPACING * -1), 4)
        if self.frozen > 0:
            f = pygame.font.Font(None, 34).render("LOST", True, RED)
            screen.blit(f, f.get_rect(center=to(0, 0)).move(0, -32))


# ---------------------------------------------------------------- sound (made in code, no files needed)
class Sound:
    def __init__(self):
        self.ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(22050, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            self.make_all()
            self.ok = True
        except (pygame.error, ValueError, TypeError):
            self.ok = False                      # no sound device: play silently

    def make_all(self):
        self.beep = self.tone([880], 0.12)
        self.go = self.tone([1320], 0.35)
        self.lap = self.tone([660, 880, 1320], 0.09)
        self.lost = self.tone([300, 200], 0.18, square=True)
        self.win = self.tone([523, 659, 784, 1047], 0.14)
        self.lose = self.tone([392, 330, 262], 0.2)

    def tone(self, freqs, dur, square=False):
        sr = self.rate; parts = []
        for f in freqs:
            t = np.arange(int(sr * dur)) / sr
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
        s[key] = round(value, 2)
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
        self.clock = pygame.time.Clock()
        self.f_big = pygame.font.SysFont("arialnarrow,arial", 64, bold=True)
        self.f_mid = pygame.font.SysFont("arial", 30, bold=True)
        self.f = pygame.font.SysFont("arial", 21)
        self.f_small = pygame.font.SysFont("arial", 17)
        self.brain = Network()
        self.sound = Sound()
        self.selftest = selftest
        self.state = "menu"; self.menu_i = 0; self.level_i = 0; self.hard = False; self.watch = False
        self.drawn = None; self.draw_buf = []; self.howto_page = 0
        self.preview = Track(shape_points("wind"), "mixed"); self.preview_car = Car(self.preview, AI, self.brain, 0.94)

    # ---------- helpers
    def text(self, s, font, col, pos, anchor="topleft"):
        img = font.render(s, True, col); r = img.get_rect(**{anchor: pos}); self.screen.blit(img, r); return r

    def wrap(self, s, font, width):
        words, lines, cur = s.split(), [], ""
        for w in words:
            if font.size(cur + " " + w)[0] > width and cur:
                lines.append(cur); cur = w
            else:
                cur = (cur + " " + w).strip()
        return lines + [cur]

    def button(self, label, rect, hot):
        pygame.draw.rect(self.screen, YOU if hot else PANEL, rect, border_radius=10)
        pygame.draw.rect(self.screen, YOU if hot else LINE, rect, 2, border_radius=10)
        self.text(label, self.f_mid, BG if hot else INK, rect.center, "center")

    # ---------- states
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
        self.state = "race"

    def finish(self):
        yd, ad = self.you.distance(), self.ai.distance()
        key = f"{LEVELS[self.level_i]['name']}|{'hard' if self.hard else 'normal'}"
        self.new_best = save_score(key, yd) if not self.watch else False
        self.stars = 3 if yd > ad else 2 if yd > 0.75 * ad else 1
        self.result = (yd, ad)
        self.sound.play("win" if yd > ad and not self.watch else "lose")
        self.state = "result"

    # ---------- main loop
    def run(self):
        frames = 0
        while True:
            dt = self.clock.tick(60) / 1000
            frames += 1
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                self.handle(e)
            if self.selftest:
                if not self.autoplay(frames):
                    return
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def autoplay(self, frames):
        """--selftest: clicks through every screen and plays one race with a simple driver, then quits."""
        if frames == 5: self.state = "howto"
        if frames == 10: self.state = "levels"
        if frames == 15: self.hard = False; self.start_level(3)
        if self.state == "race" and self.countdown <= 0:
            b = self.you.bits
            self.you.steer = -1 if (b[0] or b[1]) and not (b[2] or b[3]) else 1 if (b[2] or b[3]) and not (b[0] or b[1]) else 0
            self.t_left -= 0.5          # fast-forward the clock
        if self.state == "result":
            print(f"selftest ok: you {self.result[0]:.2f} laps, AI {self.result[1]:.2f} laps, stars {self.stars}")
            return False
        return frames < 4000

    def handle(self, e):
        keys_down = e.type == pygame.KEYDOWN
        if self.state == "menu":
            items = self.menu_items()
            if keys_down and e.key in (pygame.K_UP, pygame.K_w): self.menu_i = (self.menu_i - 1) % len(items)
            if keys_down and e.key in (pygame.K_DOWN, pygame.K_s): self.menu_i = (self.menu_i + 1) % len(items)
            if keys_down and e.key in (pygame.K_RETURN, pygame.K_SPACE): self.choose(items[self.menu_i][1])
            if e.type == pygame.MOUSEMOTION or e.type == pygame.MOUSEBUTTONDOWN:
                for i, r in enumerate(self.menu_rects):
                    if r.collidepoint(e.pos):
                        self.menu_i = i
                        if e.type == pygame.MOUSEBUTTONDOWN: self.choose(items[i][1])
        elif self.state == "howto":
            if keys_down and e.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE) or e.type == pygame.MOUSEBUTTONDOWN:
                self.state = "menu"
        elif self.state == "levels":
            if keys_down and e.key in (pygame.K_UP, pygame.K_w): self.level_i = (self.level_i - 1) % len(LEVELS)
            if keys_down and e.key in (pygame.K_DOWN, pygame.K_s): self.level_i = (self.level_i + 1) % len(LEVELS)
            if keys_down and e.key in (pygame.K_RETURN, pygame.K_SPACE): self.start_level(self.level_i)
            if keys_down and e.key == pygame.K_ESCAPE: self.state = "menu"
            if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                for i, r in enumerate(self.level_rects):
                    if r.collidepoint(e.pos):
                        self.level_i = i
                        if e.type == pygame.MOUSEBUTTONDOWN: self.start_level(i)
        elif self.state == "draw":
            if e.type == pygame.MOUSEBUTTONDOWN: self.draw_buf = [self.to_world(e.pos)]
            if e.type == pygame.MOUSEMOTION and e.buttons[0] and self.draw_buf:
                p = self.to_world(e.pos); q = self.draw_buf[-1]
                if math.hypot(p[0] - q[0], p[1] - q[1]) > 15: self.draw_buf.append(p)
            if e.type == pygame.MOUSEBUTTONUP and len(self.draw_buf) > 10: self.finish_drawing()
            if keys_down and e.key == pygame.K_ESCAPE: self.state = "levels"
        elif self.state == "race":
            if keys_down and e.key in (pygame.K_p, pygame.K_ESCAPE): self.paused = not self.paused
            if keys_down and self.paused and e.key == pygame.K_q: self.state = "menu"
        elif self.state == "result":
            if keys_down and e.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_r): self.start_level(self.level_i)
            if keys_down and e.key == pygame.K_ESCAPE: self.state = "menu"
            if e.type == pygame.MOUSEBUTTONDOWN:
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
        return ((pos[0] - OX) / SCALE, (pos[1] - TOP) / SCALE)

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
        for _ in range(int(min(dt, 0.05) * 1000)):
            for car, who in ((self.you, "you"), (self.ai, "ai")):
                if self.watch and who == "you":
                    continue
                ev = car.step()
                if ev and (who == "you" or self.watch):
                    self.sound.play(ev)
        self.t_left -= dt
        if self.t_left <= 0:
            self.t_left = 0; self.finish()

    # ---------- drawing
    def draw(self):
        self.screen.fill(BG)
        getattr(self, "draw_" + self.state)()

    def draw_menu(self):
        self.screen.blit(self.preview.surface, (OX, TOP)); self.preview_car.draw(self.screen)
        shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); shade.fill((11, 15, 21, 205)); self.screen.blit(shade, (0, 0))
        self.text("BE THE AI", self.f_big, INK, (SCREEN_W // 2, 110), "center")
        self.text("Drive the line follower against its own neural network", self.f, MUTED, (SCREEN_W // 2, 160), "center")
        self.menu_rects = []
        for i, (label, _) in enumerate(self.menu_items()):
            r = pygame.Rect(0, 0, 440, 62); r.center = (SCREEN_W // 2, 260 + i * 80)
            self.button(label, r, i == self.menu_i); self.menu_rects.append(r)
        self.text("Arrow keys + ENTER, or click", self.f_small, MUTED, (SCREEN_W // 2, SCREEN_H - 40), "center")

    def draw_howto(self):
        self.text("HOW TO PLAY", self.f_big, INK, (60, 40))
        colw = (SCREEN_W - 160) // 2
        for col, items in enumerate((HOW_TO[:4], HOW_TO[4:])):
            x, y = 60 + col * (colw + 40), 130
            for title, body in items:
                self.text(title, self.f_mid, AI, (x, y)); y += 38
                for line in self.wrap(body, self.f, colw):
                    self.text(line, self.f, INK, (x, y)); y += 26
                y += 18
        self.text("Press ENTER or click to go back", self.f_small, MUTED, (80, SCREEN_H - 40))

    def draw_levels(self):
        mode = "WATCH THE AI" if self.watch else "HARD MODE" if self.hard else "RACE THE AI"
        self.text("CHOOSE A TRACK", self.f_big, INK, (80, 50)); self.text(mode, self.f_mid, RED if self.hard else AI, (80, 125))
        scores = load_scores(); self.level_rects = []
        for i, lv in enumerate(LEVELS):
            r = pygame.Rect(80, 185 + i * 110, SCREEN_W - 160, 95); hot = i == self.level_i
            pygame.draw.rect(self.screen, (32, 42, 56) if hot else PANEL, r, border_radius=12)
            pygame.draw.rect(self.screen, YOU if hot else LINE, r, 2, border_radius=12)
            self.text(f"{i + 1}. {lv['name']}", self.f_mid, INK, (r.x + 24, r.y + 14))
            self.text(lv["tip"], self.f, MUTED, (r.x + 24, r.y + 56))
            best = scores.get(f"{lv['name']}|{'hard' if self.hard else 'normal'}")
            if best is not None:
                self.text(f"best {best:.2f} laps", self.f, YOU, (r.right - 24, r.y + 18), "topright")
            self.level_rects.append(r)
        self.text("ENTER or click to start · ESC back", self.f_small, MUTED, (80, SCREEN_H - 40))

    def draw_draw(self):
        pygame.draw.rect(self.screen, FLOOR, (OX, TOP, WW * SCALE, WH * SCALE))
        if len(self.draw_buf) > 1:
            pygame.draw.lines(self.screen, TAPE_COL, False, [(OX + x * SCALE, TOP + y * SCALE) for x, y in self.draw_buf], 6)
        self.text("DRAW YOUR TRACK", self.f_mid, INK, (24, 16))
        self.text(getattr(self, "draw_msg", "Hold the mouse button and draw one closed loop, then let go. ESC to go back."),
                  self.f, MUTED, (330, 22))

    def draw_race(self):
        self.screen.blit(self.track.surface, (OX, TOP))
        if not self.watch:
            self.you.draw(self.screen)
        self.ai.draw(self.screen)
        if self.hard and self.countdown <= 0:
            pygame.draw.rect(self.screen, BG, (0, TOP, SCREEN_W, SCREEN_H - TOP))
            self.text("LIGHTS OFF: only the 4 sensor lamps", self.f_mid, MUTED, (SCREEN_W // 2, TOP + 120), "center")
        # score bar
        pygame.draw.rect(self.screen, PANEL, (0, 0, SCREEN_W, TOP))
        lv = LEVELS[self.level_i]
        self.text(f"{self.level_i + 1}. {lv['name']}", self.f_mid, INK, (20, 14))
        if not self.watch:
            self.text(f"YOU  {self.you.distance():.2f} laps  ·  lost {self.you.fails}", self.f, YOU, (440, 21))
        self.text(f"AI  {self.ai.distance():.2f} laps  ·  lost {self.ai.fails}", self.f, AI, (790, 21))
        self.text(f"{int(math.ceil(self.t_left))}", self.f_mid, INK, (SCREEN_W - 24, 14), "topright")
        # sensor lamps
        car = self.ai if self.watch else self.you
        size = 22 if not self.hard else 70
        pad = pygame.Rect(0, 0, 4 * size * 2 + 40, size * 2 + 40)
        if self.hard:
            pad.center = (SCREEN_W // 2, SCREEN_H // 2 + 40)
        else:
            pad.bottomright = (SCREEN_W - 16, SCREEN_H - 16)
        pygame.draw.rect(self.screen, PANEL, pad, border_radius=16); pygame.draw.rect(self.screen, LINE, pad, 2, border_radius=16)
        for i in range(4):
            cx = pad.x + 20 + size + i * size * 2
            pygame.draw.circle(self.screen, RED if car.bits[i] else (42, 53, 70), (cx, pad.centery), size - 6)
            if car.bits[i]:
                pygame.draw.circle(self.screen, (255, 140, 130), (cx, pad.centery), size - 6, 3)
        if self.watch:
            self.text(f"network output  L {self.ai.out[0]:.2f}   R {self.ai.out[1]:.2f}", self.f, AI, (pad.x - 16, pad.centery - 12), "topright")
        if self.countdown > 0:
            c = int(math.ceil(self.countdown))
            self.text(str(c) if c > 0 else "GO", self.f_big, RED, (SCREEN_W // 2, SCREEN_H // 2 - 60), "center")
            self.text(lv["tip"], self.f, INK, (SCREEN_W // 2, SCREEN_H // 2 + 10), "center")
        if self.paused:
            shade = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA); shade.fill((11, 15, 21, 200)); self.screen.blit(shade, (0, 0))
            self.text("PAUSED", self.f_big, INK, (SCREEN_W // 2, SCREEN_H // 2 - 30), "center")
            self.text("P to resume · Q to quit to menu", self.f, MUTED, (SCREEN_W // 2, SCREEN_H // 2 + 30), "center")

    def draw_result(self):
        yd, ad = self.result
        if self.watch:
            title = f"The AI drove {ad:.2f} laps"
        else:
            title = "YOU BEAT THE NETWORK!" if yd > ad else "THE NETWORK WINS"
        self.text(title, self.f_big, YOU if yd > ad and not self.watch else AI, (SCREEN_W // 2, 170), "center")
        if not self.watch:
            self.text("★" * self.stars + "☆" * (3 - self.stars), self.f_big, YOU, (SCREEN_W // 2, 260), "center")
            self.text(f"You: {yd:.2f} laps, lost the line {self.you.fails}×", self.f_mid, YOU, (SCREEN_W // 2, 350), "center")
        self.text(f"AI: {ad:.2f} laps, lost the line {self.ai.fails}×", self.f_mid, AI, (SCREEN_W // 2, 395), "center")
        if getattr(self, "new_best", False):
            self.text("New personal best!", self.f, GREEN, (SCREEN_W // 2, 440), "center")
        tip = ("Now try hard mode: drive with only the 4 lamps, like the network does." if not self.hard
               else "That is all the car ever knows: 4 lamps, 107 numbers, 200 decisions a second.")
        self.text(tip, self.f, MUTED, (SCREEN_W // 2, 490), "center")
        self.again_rect = pygame.Rect(0, 0, 260, 60); self.again_rect.center = (SCREEN_W // 2 - 150, 590)
        self.menu_rect = pygame.Rect(0, 0, 260, 60); self.menu_rect.center = (SCREEN_W // 2 + 150, 590)
        self.button("Race again (R)", self.again_rect, True); self.button("Menu (ESC)", self.menu_rect, False)


if __name__ == "__main__":
    Game(selftest="--selftest" in sys.argv).run()
    pygame.quit()
