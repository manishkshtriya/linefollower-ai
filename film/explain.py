"""Two explainer videos of the whole project: a professional one (for the professor) and a Gen-Z one.
Usage: python3 explain.py <kokoro dir> pro|genz out.mp4"""
import math, os, subprocess, sys
import numpy as np
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame, imageio.v2 as imageio, soundfile as sf
from kokoro_onnx import Kokoro
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import film as F                      # shared drawing helpers, fonts and the drawn scenes from the first film
from film import W, H, FPS, SR, INK, MUTED, BG, AI, YOU, RED, GREEN, LINE, text, fade, ease, lamps

scr = F.screen
f_big, f_mid, f_txt, f_small = F.f_big, F.f_mid, F.f_txt, F.f_small
f_code = pygame.font.SysFont("menlo,dejavusansmono,couriernew", 22, bold=True)
PURPLE, PINK, LIME = (124, 58, 237), (236, 72, 153), (101, 163, 13)


# ---------------------------------------------------------------- small drawing helpers
def phone(cx, cy, w=190, h=360):
    r = pygame.Rect(0, 0, w, h); r.center = (cx, cy)
    pygame.draw.rect(scr, (210, 218, 228), r.move(6, 8), border_radius=28)
    pygame.draw.rect(scr, INK, r, border_radius=28)
    s = r.inflate(-18, -40); pygame.draw.rect(scr, (255, 255, 255), s, border_radius=14)
    pygame.draw.rect(scr, (60, 70, 85), (r.centerx - 30, r.y + 10, 60, 8), border_radius=4)
    return s


def chip(cx, cy, label="ESP32"):
    r = pygame.Rect(0, 0, 220, 150); r.center = (cx, cy)
    for k in range(7):
        pygame.draw.rect(scr, (180, 188, 198), (r.x + 18 + k * 28, r.y - 14, 12, 14))
        pygame.draw.rect(scr, (180, 188, 198), (r.x + 18 + k * 28, r.bottom, 12, 14))
    pygame.draw.rect(scr, (20, 30, 48), r, border_radius=12)
    pygame.draw.rect(scr, (190, 196, 205), r.inflate(-110, -60), border_radius=5)
    text(label, f_txt, (255, 255, 255), (r.centerx, r.bottom - 22))
    return r


def wifi(cx, cy, t, col=AI):
    for k in range(3):
        ph = (t * 1.6 + k / 3) % 1
        rad = int(30 + ph * 90); a = int(255 * (1 - ph))
        s = pygame.Surface((rad * 2 + 8, rad * 2 + 8), pygame.SRCALPHA)
        pygame.draw.arc(s, col + (a,), (4, 4, rad * 2, rad * 2), math.radians(40), math.radians(140), 6)
        scr.blit(s, (cx - rad - 4, cy - rad - 4))


def file_card(name, lines, center, alpha=255, w=300):
    h = 46 + 28 * len(lines)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (255, 255, 255, alpha), (0, 0, w, h), border_radius=12)
    pygame.draw.rect(s, LINE + (alpha,), (0, 0, w, h), 2, border_radius=12)
    s.blit(f_txt.render(name, True, AI), (16, 10))
    for i, ln in enumerate(lines):
        s.blit(f_code.render(ln, True, INK), (16, 44 + i * 28))
    s.set_alpha(alpha); scr.blit(s, s.get_rect(center=center))


def wheel(cx, cy, r, angle, col=(24, 28, 36)):
    pygame.draw.circle(scr, col, (cx, cy), r); pygame.draw.circle(scr, (200, 206, 214), (cx, cy), int(r * .45))
    for k in range(4):
        a = angle + k * math.pi / 2
        pygame.draw.line(scr, YOU, (cx, cy), (cx + math.cos(a) * r * .45, cy + math.sin(a) * r * .45), 5)


def title(s, t, y=70):
    text(s, f_big, INK, (W // 2, y), alpha=fade(t, .2))


# ---------------------------------------------------------------- new scenes
def scene_overview(t, d):
    soft_bg(); title("THE WHOLE IDEA", t)
    boxes = [("SENSE", "4 IR sensors", "0110"), ("THINK", "neural network", "107 numbers"), ("ACT", "2 BO motors", "PWM 0-255")]
    for i, (h, a, b) in enumerate(boxes):
        al = fade(t, .6 + i * 1.4)
        if al == 0: continue
        r = pygame.Rect(0, 0, 300, 230); r.center = (220 + i * 420, H // 2 + 40)
        s = pygame.Surface(r.size, pygame.SRCALPHA); pygame.draw.rect(s, (255, 255, 255, al), (0, 0, *r.size), border_radius=18)
        pygame.draw.rect(s, (AI if i == 1 else LINE) + (al,), (0, 0, *r.size), 3, border_radius=18); scr.blit(s, r)
        text(h, f_mid, AI if i == 1 else INK, (r.centerx, r.y + 44), alpha=al)
        text(a, f_txt, MUTED, (r.centerx, r.y + 110), alpha=al); text(b, f_mid, RED if i == 0 else INK, (r.centerx, r.y + 165), alpha=al)
        if i < 2 and t > 1.4 + i * 1.4:
            x0 = r.right + 15; pygame.draw.line(scr, AI, (x0, r.centery), (x0 + 90, r.centery), 6)
            pygame.draw.polygon(scr, AI, [(x0 + 100, r.centery), (x0 + 84, r.centery - 12), (x0 + 84, r.centery + 12)])
    text("200 times every second", f_txt, MUTED, (W // 2, H - 90), alpha=fade(t, 5))


def scene_ota(t, d):
    soft_bg(); title("OVER-THE-AIR UPDATES", t)
    ph = phone(300, 400, 170, 320); c = chip(960, 400)
    steps = [(0.5, "1  ESP32 makes its own WiFi"), (d * .33, "2  Phone gives it your home WiFi"), (d * .62, "3  New firmware flies over the air")]
    for i, (st, s) in enumerate(steps):
        text(s, f_txt, INK if t > st else (200, 206, 214), (W // 2, 150 + i * 36), alpha=fade(t, st))
    if t < steps[1][0]: wifi(c.centerx, c.y - 10, t)
    elif t < steps[2][0]: wifi(ph.centerx, ph.y + 30, t, PURPLE)
    else:
        f = ease((t - steps[2][0]) / 2.2); x = 300 + (960 - 300) * f
        file_card("firmware.bin", [], (x, 400 - 120 * math.sin(f * math.pi)), 255, 220)
        bar = pygame.Rect(c.x, c.bottom + 40, c.w, 14); pygame.draw.rect(scr, (226, 232, 240), bar, border_radius=7)
        pygame.draw.rect(scr, GREEN, (bar.x, bar.y, bar.w * f, bar.h), border_radius=7)
        if f >= 1: text("updated, no cable", f_txt, GREEN, (c.centerx, bar.bottom + 30))
    text("WiFi setup", f_small, MUTED, (ph.centerx, ph.y + 40)); text("linefollower.local", f_small, AI, (ph.centerx, ph.y + 70))


def scene_config(t, d):
    soft_bg(); title("CHANGE THE BRAIN, NOT THE CODE", t)
    ph = phone(200, 420, 160, 300); c = chip(1060, 420)
    cards = [("weights.json", ['{"W": [[-0.64, 0.62,', '        -0.96, 1.01],', '       ...], "b": [...]}'], 0.8),
             ("speed.csv", ["min_pwm,70", "max_pwm,255", "trim_right,1.04"], d * .45)]
    for name, lines, st in cards:
        f = ease((t - st) / 2.0)
        if t < st: continue
        x = 330 + (870 - 330) * f if f < 1 else 870
        file_card(name, lines, (x if f < 1 else 640, 330 if name.endswith("json") else 520), 255 if f < 1 else 255, 330)
    if t > d * .8:
        text("saved in flash: keeps after power-off", f_txt, GREEN, (c.centerx, c.bottom + 50))


def scene_feedback(t, d):
    soft_bg(); title("THE CAR REPORTS BACK", t)
    s = phone(380, 420, 260, 470)
    pats = [[0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 0]]; bits = pats[int(t / 1.3) % 4]; out = F.net(bits)
    for i in range(4):
        cx = s.x + 32 + i * 52; pygame.draw.circle(scr, RED if bits[i] else (214, 222, 232), (cx, s.y + 60), 20)
    for i, (nm, v) in enumerate((("L", out[0]), ("R", out[1]))):
        y = s.y + 120 + i * 46; text(nm, f_txt, INK, (s.x + 20, y), "topleft")
        pygame.draw.rect(scr, (226, 232, 240), (s.x + 50, y + 6, 160, 16), border_radius=8)
        pygame.draw.rect(scr, AI, (s.x + 50, y + 6, 160 * float(v), 16), border_radius=8)
    text("raw IR  812  265  240  790", f_small, MUTED, (s.x + 14, s.y + 230), "topleft")
    text("WiFi -52 dBm   battery 7.6 V", f_small, MUTED, (s.x + 14, s.y + 258), "topleft")
    rows = ["t,s1,s2,s3,s4,L,R"] + [f"{k * 0.02:.2f},{p[0]},{p[1]},{p[2]},{p[3]},{F.net(p)[0]:.2f},{F.net(p)[1]:.2f}" for k, p in enumerate(pats * 3)]
    n = min(len(rows), 1 + int(t * 2.2))
    file_card("drive_log.csv", rows[max(0, n - 9):n], (900, 430), fade(t, 1), 420)
    text("send the log to Claude to debug", f_txt, PURPLE, (900, 680), alpha=fade(t, d * .6))


def scene_bomotor(t, d):
    soft_bg(); title("BO MOTORS: REAL SPEED", t)
    ang = t * 6
    pygame.draw.rect(scr, (250, 204, 21), (140, 300, 200, 110), border_radius=12); pygame.draw.rect(scr, INK, (140, 300, 200, 110), 3, border_radius=12)
    text("BO motor", f_txt, INK, (240, 355)); wheel(420, 355, 85, ang)
    text("v = π × D × RPM / 60", f_mid, AI, (900, 230), alpha=fade(t, 1))
    text("Example: 65 mm wheel at 150 RPM", f_txt, INK, (900, 300), alpha=fade(t, 3))
    text("v = 3.1416 × 0.065 × 150 / 60 = 0.51 m/s", f_txt, INK, (900, 340), alpha=fade(t, 4))
    for i, (lab, col) in enumerate((("5 V", (147, 197, 253)), ("9 V", AI))):
        al = fade(t, 6 + i)
        r = pygame.Rect(720 + i * 200, 420, 140, 150)
        s = pygame.Surface(r.size, pygame.SRCALPHA); pygame.draw.rect(s, col + (al,), (0, 150 - (70 + 60 * i), 140, 70 + 60 * i), border_radius=10); scr.blit(s, r)
        text(lab, f_mid, INK, (r.centerx, r.bottom + 30), alpha=al)
    text("RPM at each voltage: from the datasheet", f_txt, MUTED, (900, 640), alpha=fade(t, 7))
    text("→ into the simulator", f_txt, GREEN, (900, 675), alpha=fade(t, 8))


def scene_bench(t, d):
    soft_bg(); title("BENCH TEST: WHEELS IN THE AIR", t)
    sheet = pygame.Rect(240, 330, 800, 300); pygame.draw.rect(scr, (255, 255, 255), sheet, border_radius=8); pygame.draw.rect(scr, LINE, sheet, 2, border_radius=8)
    text("printed test sheet", f_small, MUTED, (sheet.x + 12, sheet.bottom - 28), "topleft")
    cx = W // 2; lx = cx + math.sin(t * 1.1) * 150
    pygame.draw.rect(scr, (16, 20, 27), (lx - 28, sheet.y, 57, sheet.h))
    sx = [cx + (i - 1.5) * 60 for i in range(4)]
    bits = [1 if abs(lx - x) < 32 else 0 for x in sx]; out = F.net(bits)
    pygame.draw.rect(scr, (180, 150, 110), (cx - 330, 210, 660, 40), border_radius=6); text("stand", f_small, INK, (cx - 300, 220), "topleft")
    car = pygame.Surface((420, 200), pygame.SRCALPHA); pygame.draw.rect(car, (10, 120, 180, 150), (60, 0, 300, 150), border_radius=14); scr.blit(car, (cx - 210, 250))
    pygame.draw.rect(scr, (30, 70, 190), (cx - 120, 455, 240, 18), border_radius=4)
    for i, x in enumerate(sx): pygame.draw.circle(scr, RED if bits[i] else (241, 245, 249), (x, 464), 12); pygame.draw.circle(scr, INK, (x, 464), 12, 2)
    wheel(cx - 240, 320, 50, t * 12 * out[0]); wheel(cx + 240, 320, 50, t * 12 * out[1])
    text(f"L {out[0]:.2f}", f_txt, AI, (cx - 240, 395)); text(f"R {out[1]:.2f}", f_txt, AI, (cx + 240, 395))
    turn = "turns LEFT" if out[1] - out[0] > .08 else "turns RIGHT" if out[0] - out[1] > .08 else "straight"
    text(f"{''.join(map(str, bits))}  →  {turn}", f_mid, RED if any(bits) else MUTED, (W // 2, 680))


def scene_calib(t, d):
    soft_bg(); title("FIX THE LIGHTING: CALIBRATE", t)
    bright = [3400, 900, 850, 3300]; dim = [2300, 1300, 1250, 2200]
    k = ease((t - d * .3) / 1.5); vals = [b + (m - b) * k for b, m in zip(bright, dim)]
    calib = t > d * .62
    base = 620; scale = 0.11
    for i, v in enumerate(vals):
        x = 330 + i * 170; h = v * scale
        pygame.draw.rect(scr, (16, 20, 27) if v < 1600 or (calib and v < (dim[i] + dim[0]) / 2 and i in (1, 2)) else (214, 222, 232), (x, base - h, 90, h), border_radius=8)
        text(f"{int(v)}", f_txt, INK, (x + 45, base - h - 24)); text(f"S{i + 1}", f_txt, MUTED, (x + 45, base + 26))
    thr = 2000 if not calib else 1750
    y = base - thr * scale; pygame.draw.line(scr, RED if not calib else GREEN, (290, y), (1000, y), 4)
    text("threshold" if not calib else "calibrated threshold", f_txt, RED if not calib else GREEN, (1010, y), "midleft")
    text("bright room" if k < .5 else "dim room: same tape, different numbers", f_txt, INK, (W // 2, 150), alpha=fade(t, .5))
    if calib: text("Slide over black and white once: the car learns both values", f_txt, GREEN, (W // 2, 190))


def scene_flex(t, d):
    soft_bg(); title("THE REAL TRACK: FLEX PRINT", t)
    cols, rows = 6, 3; tw, th = 150, 150; x0, y0 = W // 2 - cols * tw // 2, 190
    shown = int(t / 0.25)
    for k in range(min(shown, cols * rows)):
        cx, cy = k % cols, k // cols
        pygame.draw.rect(scr, (255, 255, 255), (x0 + cx * tw + 3, y0 + cy * th + 3, tw - 6, th - 6), border_radius=4)
    if shown >= cols * rows:
        pts = []
        for i in range(200):
            a = 2 * math.pi * i / 200; r = 1 + 0.18 * math.cos(3 * a)
            pts.append((W // 2 + math.cos(a) * r * 380, y0 + th * 1.5 + math.sin(a) * r * 170))
        pygame.draw.lines(scr, (16, 20, 27), True, pts, 9)
        p = pts[int((t * 25) % 200)]; pygame.draw.circle(scr, AI, (int(p[0]), int(p[1])), 14)
    text("then harder tracks and higher speed", f_txt, MUTED, (W // 2, 680), alpha=fade(t, d * .6))


def scene_paper(t, d):
    soft_bg(); title("NEXT: A RESEARCH PAPER", t)
    pg = pygame.Rect(0, 0, 420, 520); pg.center = (470, 420)
    pygame.draw.rect(scr, (220, 226, 234), pg.move(8, 10), border_radius=6); pygame.draw.rect(scr, (255, 255, 255), pg, border_radius=6)
    text("A 107-Parameter Neural Line Follower", f_small, INK, (pg.centerx, pg.y + 40))
    text("with Simulation-Based Self-Training", f_small, INK, (pg.centerx, pg.y + 64))
    n = int(t * 6)
    for k in range(min(n, 14)):
        w = 340 if k % 5 != 4 else 200
        pygame.draw.rect(scr, (214, 222, 232), (pg.x + 40, pg.y + 110 + k * 26, w, 10), border_radius=5)
    lk = pygame.Rect(820, 330, 140, 110); pygame.draw.rect(scr, INK, lk, border_radius=14)
    pygame.draw.arc(scr, INK, (lk.x + 30, lk.y - 60, 80, 110), 0, math.pi, 10)
    text("private", f_txt, (255, 255, 255), lk.center)
    text("GitHub repo stays private", f_txt, INK, (890, 480), alpha=fade(t, 2))
    text("until the paper is published", f_txt, MUTED, (890, 515), alpha=fade(t, 2.5))


def soft_bg():
    """Light background with a faint grid and a soft blue glow (professional version)."""
    scr.fill((247, 250, 253))
    for x in range(0, W, 40): pygame.draw.line(scr, (236, 241, 247), (x, 0), (x, H))
    for y in range(0, H, 40): pygame.draw.line(scr, (236, 241, 247), (0, y), (W, y))
    g = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.circle(g, (10, 120, 180, 14), (W - 160, 120), 360); pygame.draw.circle(g, (232, 150, 0, 10), (160, H - 80), 300)
    scr.blit(g, (0, 0))


def scene_title(t, d):
    soft_bg()
    w = int(560 * ease(t / 1.2)); pygame.draw.rect(scr, AI, (W // 2 - w // 2, 250, w, 5), border_radius=3)
    text("AI LINE FOLLOWER", F.f_huge if hasattr(F, "f_huge") else f_big, INK, (W // 2, 180), alpha=fade(t, .2))
    text("A 107-parameter neural network on an ESP32", f_mid, AI, (W // 2, 300), alpha=fade(t, 1))
    text("Manish M P", f_mid, INK, (W // 2, 420), alpha=fade(t, 2))
    text("Under the guidance of Dr. Jason Elroy Martis", f_txt, MUTED, (W // 2, 465), alpha=fade(t, 2.6))
    text("NMAM Institute of Technology, Nitte", f_txt, MUTED, (W // 2, 500), alpha=fade(t, 3.2))


def scene_why_ann(t, d):
    soft_bg(); title("WHY AN ANN, NOT A CNN?", t)
    cols = [("CNN", (190, 70, 60), ["Built for images", "Needs a camera", "320 x 240 x 3 = 230,400 inputs", "Thousands to millions of weights", "Needs a GPU board (Jetson)"]),
            ("ANN  (chosen)", GREEN, ["Built for a few numbers", "4 IR sensor values", "4 inputs", "107 weights", "Runs on an ESP32, 200 times a second"])]
    for i, (head, col, rows) in enumerate(cols):
        al = fade(t, .6 + i * 2.2)
        if al == 0: continue
        r = pygame.Rect(0, 0, 520, 420); r.center = (W // 2 - 290 + i * 580, 420)
        s = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (255, 255, 255, al), (0, 0, *r.size), border_radius=18)
        pygame.draw.rect(s, col + (al,), (0, 0, *r.size), 4 if i else 2, border_radius=18)
        pygame.draw.rect(s, col + (int(al * .12),), (0, 0, r.w, 70), border_top_left_radius=18, border_top_right_radius=18)
        scr.blit(s, r)
        text(head, f_mid, col, (r.centerx, r.y + 36), alpha=al)
        for k, row in enumerate(rows):
            text(row, f_txt, INK if i else MUTED, (r.x + 36, r.y + 100 + k * 58), "topleft", fade(t, 1 + i * 2.2 + k * .35))
    text("Our input is 1-D and tiny, so a small fully connected network is enough", f_txt, AI, (W // 2, 668), alpha=fade(t, d * .7))


def scene_close(t, d, version):
    scr.fill(BG)
    lines = (["FOUR SENSORS.", "107 PARAMETERS.", "ONE LINE."] if version == "pro" else ["FOUR EYES.", "107 NUMBERS.", "LET'S BUILD IT."])
    for i, s in enumerate(lines):
        text(s, f_big, (AI if version == "pro" else PINK) if i == 2 else INK, (W // 2, 200 + i * 85), alpha=fade(t, .3 + i * 1.1))
    if version == "pro":
        text("Manish M P", f_mid, INK, (W // 2, 500), alpha=fade(t, 3.6))
        text("Guide: Dr. Jason Elroy Martis  ·  NMAMIT, Nitte", f_txt, MUTED, (W // 2, 545), alpha=fade(t, 4))
    else:
        text("AI Line Follower  ·  Manish M P  ·  NMAMIT", f_txt, MUTED, (W // 2, 520), alpha=fade(t, 4))


DRAWN = {"title": scene_title, "why_ann": scene_why_ann, "overview": scene_overview, "tracks": F.scene_tracks, "brain": F.scene_brain, "ota": scene_ota, "config": scene_config,
         "feedback": scene_feedback, "bomotor": scene_bomotor, "bench": scene_bench, "calib": scene_calib, "flex": scene_flex, "paper": scene_paper}
CLIPS = {"sim": F.CLIPS["sim"], "flaw": F.CLIPS["flaw"], "learn": F.CLIPS["learn"]}

SCRIPTS = {
 "pro": {"voice": "af_heart", "speed": 0.97, "lines": [
  ("title", "", "A I line follower. A project by Manish M P, under the guidance of Doctor Jason Elroy Martis, at N M A M Institute of Technology."),
  ("overview", "Concept", "This project is an A I line follower. Four infrared sensors feed a neural network of one hundred and seven parameters, which sets the speed of two motors."),
  ("tracks", "The challenge", "The goal is to follow solid, dashed and dotted lines, where every sensor goes dark in the gaps."),
  ("brain", "The network", "The network has four inputs, two hidden layers of seven neurons, and two outputs. It runs on an E S P thirty-two, at two hundred decisions per second."),
  ("why_ann", "Why an ANN", "Why an A N N, and not a C N N? A C N N is built for images, and would need a camera and a much larger processor. Our input is just four sensor values, so a small fully connected network is enough. That keeps the model at one hundred and seven parameters, small enough for an E S P thirty-two."),
  ("sim", "Simulation", "Before building hardware, the real firmware was tested in a custom simulator, with motor stall, motor lag and sensor noise."),
  ("flaw", "A finding", "The simulator showed that sensor spacing matters. Twenty millimetres works far better than thirty, especially with a weaker motor."),
  ("learn", "Training", "Training has two stages. Supervised learning with Adam, then self-improvement with an evolution strategy. Clean runs rose from one hundred and forty-one to two hundred and five, out of two hundred and forty."),
  ("ota", "Over-the-air updates", "Next, the firmware supports over-the-air updates. The E S P thirty-two is set up over WiFi from a phone, and is not reflashed by cable again."),
  ("config", "Configuration", "Weights and speed settings are uploaded as JSON or CSV files and stored in flash, so only the configuration changes, never the code."),
  ("feedback", "Telemetry", "The car streams live sensor and motor data to the phone, and records a log for debugging."),
  ("bomotor", "Motor model", "Motor parameters come from the B O motor datasheet. Wheel speed equals pi, times wheel diameter, times R P M, over sixty. Speeds at five and nine volts will go into the simulator."),
  ("bench", "Bench test", "Hardware testing starts on a stand. The wheels spin freely while a printed line sheet moves under the sensors, so every response can be checked safely."),
  ("calib", "Calibration", "Infrared readings change with lighting, so each sensor is calibrated on the actual floor before running."),
  ("flex", "Track test", "Then the car runs on a large flex-printed track, followed by harder tracks and higher speeds."),
  ("paper", "Publication", "The results will be written up as a research paper. The repository stays private until publication."),
  ("close", "", "Four sensors. One hundred and seven parameters. One line. Thank you."),
 ]},
 "genz": {"voice": "af_bella", "speed": 1.06, "lines": [
  ("overview", "THE SQUAD", "Okay so here's the vibe. Four little eyes, one tiny brain, two motors. That's literally the whole car."),
  ("tracks", "EASY vs HARD MODE", "Solid line? Easy mode. Dashes and dots? That's where most bots fumble, because every sensor goes dark."),
  ("brain", "NO CAP", "The brain is just one hundred and seven numbers. Four in, seven, seven, two out. It runs on a cheap E S P thirty-two, two hundred times a second. No Jetson needed."),
  ("sim", "MAIN CHARACTER", "You haven't even built it yet, and you already tested the real code in your own simulator. Main character energy."),
  ("flaw", "PLOT TWIST", "Plot twist. Sensors thirty millimetres apart? The car loses the line. Twenty millimetres? It locks in."),
  ("learn", "GLOW UP", "Then the network trained itself. Trial and error on hundreds of virtual cars. Clean runs went from one forty-one to two oh five. Glow up."),
  ("ota", "NEW QUEST", "New quest. Over the air updates. Flash once with the cable, then update from your phone forever. No more cable drama."),
  ("config", "BIG BRAIN MOVE", "Weights and speeds? Just upload a JSON or CSV. Change the brain without touching the code."),
  ("feedback", "IT TEXTS YOU", "The car basically texts you. Live sensors, motor speeds, and a log you can send straight to Claude when something is off."),
  ("bomotor", "HOMEWORK", "Homework from sir. The B O motor datasheet. Speed equals pi times wheel diameter times R P M. Check five volts and nine volts."),
  ("bench", "DON'T ZOOM YET", "Don't let it zoom off yet. Put it on a stand, wheels in the air, slide the printed line under it, and check it turns the right way."),
  ("calib", "TRUST THE PROCESS", "Lighting messes with I R sensors, so calibrate on your actual floor. Trust the process."),
  ("flex", "LET IT RIP", "Then print the big flex track and let it rip. Harder tracks and more speed after that."),
  ("paper", "FINAL BOSS", "And the final boss. A research paper with sir. Keep the repo private till then. Shh."),
  ("close", "LET'S GO", "Four eyes. One hundred and seven numbers. One line. Let's build it."),
 ]},
}


def overlay(version, label, idx, total, t):
    """Section marker on top of a frame (scr)."""
    if version == "pro":
        if label:
            r = f_small.render(f"{idx}/{total - 1}   {label.upper()}", True, MUTED)
            scr.blit(r, (34, H - 40))
        pygame.draw.rect(scr, (226, 232, 240), (0, 0, W, 5)); pygame.draw.rect(scr, AI, (0, 0, W * idx / (total - 1), 5))
        if idx > 0:
            r2 = f_small.render("Manish M P  ·  Guide: Dr. Jason Elroy Martis  ·  NMAMIT", True, (150, 162, 180))
            scr.blit(r2, r2.get_rect(bottomright=(W - 30, H - 18)))
    else:
        if label:
            img = pygame.font.SysFont("arialblack,arial", 34, bold=True).render(label, True, (255, 255, 255))
            pad = img.get_rect().inflate(34, 18); s = pygame.Surface(pad.size, pygame.SRCALPHA)
            colour = [PINK, PURPLE, LIME, YOU][idx % 4]
            pygame.draw.rect(s, colour, (0, 0, *pad.size), border_radius=14); s.blit(img, img.get_rect(center=s.get_rect().center))
            pop = 1.0 + 0.25 * max(0, 1 - t / .25)
            s = pygame.transform.rotozoom(s, 4 if idx % 2 else -4, pop); scr.blit(s, s.get_rect(bottomleft=(28, H - 24)))
        pygame.draw.rect(scr, (226, 232, 240), (0, H - 8, W, 8)); pygame.draw.rect(scr, PINK, (0, H - 8, W * idx / (total - 1), 8))


def music(version, n, total):
    ts = np.arange(n) / SR; out = np.zeros(n, np.float32)
    if version == "pro":
        chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
        for ci in range(int(total / 4) + 2):
            a, b = int(ci * 4 * SR), min(n, int((ci + 1) * 4 * SR))
            if a >= n: break
            st = ts[a:b] - ci * 4; env = np.minimum(1, st) * np.minimum(1, 4 - st)
            out[a:b] += sum(np.sin(2 * np.pi * f * ts[a:b]) for f in chords[ci % 4]) * env * .045
    else:
        bpm = 112; beat = 60 / bpm; bass = [110.0, 87.31, 130.81, 98.0]
        for k in range(int(total / beat) + 4):
            p = int(k * beat * SR)
            if p >= n: break
            q = min(n, p + int(.25 * SR)); tt = np.arange(q - p) / SR
            out[p:q] += np.sin(2 * np.pi * 55 * tt * np.exp(-tt * 20)) * np.exp(-tt / .12) * .35          # kick
            h = p + int(beat / 2 * SR); hq = min(n, h + int(.05 * SR))
            if h < n: out[h:hq] += np.random.randn(hq - h) * np.exp(-np.arange(hq - h) / (0.01 * SR)) * .08  # hat
            bq = min(n, p + int(beat * .9 * SR)); bt = np.arange(bq - p) / SR
            out[p:bq] += np.sign(np.sin(2 * np.pi * bass[(k // 4) % 4] * bt)) * np.exp(-bt / .3) * .05       # bass
    return out


def build(mdir, version, out):
    cfg = SCRIPTS[version]; k = Kokoro(f"{mdir}/kokoro.onnx", f"{mdir}/voices.bin")
    tmp = os.path.join(HERE, f"tmp_{version}"); os.makedirs(tmp, exist_ok=True)
    parts, voice, t0, total_n = [], [], 0.0, len(cfg["lines"])
    for idx, (name, label, line) in enumerate(cfg["lines"]):
        a, _ = k.create(line, voice=cfg["voice"], speed=cfg["speed"], lang="en-us")
        dur = len(a) / SR + (2.2 if name == "close" else 1.2); voice.append((t0 + .5, a))
        seg = os.path.join(tmp, f"{idx:02d}_{name}.mp4")
        if name in CLIPS:
            src, start, cap = CLIPS[name]
            vid = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]))
            pad = max(0.0, dur - max(.5, vid - start))
            ov = os.path.join(tmp, f"ov_{idx}.png"); scr.fill((0, 0, 0)); scr.set_colorkey(None)
            surf = pygame.Surface((W, H), pygame.SRCALPHA); prev = F.screen
            # draw the overlay onto a transparent surface
            globals()["scr"] = surf; overlay(version, label, idx, total_n, 1.0); globals()["scr"] = prev
            pygame.image.save(surf, ov)
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", src, "-i", ov, "-t", f"{dur:.2f}", "-an", "-filter_complex",
                                   f"[0]scale=1280:720,tpad=stop_mode=clone:stop_duration={pad:.2f}[v];[v][1]overlay=0:0", "-r", str(FPS),
                                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", seg])
        else:
            wr = imageio.get_writer(seg, fps=FPS, codec="libx264", quality=8, macro_block_size=None, pixelformat="yuv420p")
            n = int(dur * FPS)
            for i in range(n):
                tt = i / FPS
                if name == "close": scene_close(tt, dur, version)
                else: DRAWN[name](tt, dur)
                overlay(version, label, idx, total_n, tt)
                if i > n - 10 and name != "close":
                    sh = pygame.Surface((W, H), pygame.SRCALPHA); sh.fill((245, 248, 252, int(255 * (i - (n - 10)) / 10))); scr.blit(sh, (0, 0))
                wr.append_data(pygame.surfarray.array3d(scr).swapaxes(0, 1))
            wr.close()
        parts.append(seg); t0 += dur; print(f"{t0:6.1f}s {name}", flush=True)
    total = t0
    lst = os.path.join(tmp, "l.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    vid = os.path.join(tmp, "v.mp4")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", vid])
    n = int((total + 1) * SR); v = np.zeros(n, np.float32)
    for st, a in voice: i = int(st * SR); v[i:i + len(a)] += a[: max(0, n - i)]
    m = music(version, n, total)
    duck = np.convolve((np.abs(v) > .01).astype(np.float32), np.ones(int(.3 * SR)) / int(.3 * SR), mode="same")
    m *= (1 - .55 * np.clip(duck * 3, 0, 1)) * np.clip((total + 1 - np.arange(n) / SR) / 2.5, 0, 1)
    mix = v + m; mix /= max(1, np.abs(mix).max() / .95)
    wav = os.path.join(tmp, "a.wav"); sf.write(wav, mix, SR)
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", wav, "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print("done", round(total, 1), out)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3])
