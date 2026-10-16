"""Epic-style teaser trailer (original, no film-studio branding). Usage: python3 trailer.py <kokoro dir> out.mp4"""
import os, subprocess, sys, math
import numpy as np
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame, imageio.v2 as imageio, soundfile as sf
from kokoro_onnx import Kokoro
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "game")); import line_follower_game as G
W, H, FPS, SR = 1280, 720, 30, 24000
TMP = os.path.join(HERE, "tmp_t"); os.makedirs(TMP, exist_ok=True)
pygame.init(); scr = pygame.Surface((W, H))
fT = pygame.font.SysFont("arialblack,arial", 96, bold=True); fM = pygame.font.SysFont("arialblack,arial", 52, bold=True); fS = pygame.font.SysFont("arial", 26, bold=True)
CYAN, GOLD, WHITE = (90, 220, 255), (255, 190, 60), (240, 245, 250)

# (kind, seconds, payload, narration or None, sound at start)
SHOTS = [
 ("card", 3.0, ("", "IN A WORLD OF EXPENSIVE ROBOTS"), None, "tick"),
 ("card", 4.2, ("", "ONE STUDENT ASKED A SIMPLE QUESTION"), "They said a car needs a supercomputer to follow a line.", "braam"),
 ("lamps", 4.6, None, "I gave it four sensors. And a hundred and seven numbers.", "braam"),
 ("clip", 3.2, ("sim/line_follower_sim.mp4", 10), None, "hit"),
 ("card", 3.4, ("", "EVERY GAP IS A CHANCE TO GET LOST"), "Every gap in the line is a chance to get lost.", "braam"),
 ("clip", 3.4, ("sim/line_follower_sim.mp4", 50), "So I built a world to break it in.", "hit"),
 ("clip", 3.6, ("sim/ai_learns_the_fix.mp4", 18), "Then I let it learn.", "braam"),
 ("card", 2.2, ("77  →  104", "CLEAN RUNS. NO RULES FROM ME."), None, "hit"),
 ("game", 4.2, None, "Think you can drive better? Prove it.", "hit"),
 ("riser", 2.6, None, None, "riser"),
 ("title", 5.5, ("AI LINE FOLLOWER", "FOUR SENSORS · 107 NUMBERS · ONE LINE"), None, "boom"),
 ("card", 3.6, ("", "COMING SOON TO A REAL TRACK"), None, "tick"),
]

def bars():
    pygame.draw.rect(scr, (0, 0, 0), (0, 0, W, 70)); pygame.draw.rect(scr, (0, 0, 0), (0, H - 70, W, 70))

def glow_text(s, font, col, center, alpha=255, scale=1.0):
    img = font.render(s, True, col)
    if scale != 1.0: img = pygame.transform.rotozoom(img, 0, scale)
    for r, a in ((8, 40), (4, 70)):
        g = pygame.transform.smoothscale(img, (img.get_width() + r * 2, img.get_height() + r)); g.set_alpha(int(a * alpha / 255))
        scr.blit(g, g.get_rect(center=center))
    img.set_alpha(alpha); scr.blit(img, img.get_rect(center=center))

def card(t, d, p):
    scr.fill((4, 8, 14)); big, small = p
    a = int(255 * min(1, t / .25, (d - t) / .35)); sc = 1.08 - 0.06 * min(1, t / d)
    if big: glow_text(big, fT, GOLD, (W // 2, H // 2 - 30), a, sc)
    glow_text(small, fM if not big else fS, WHITE if not big else CYAN, (W // 2, H // 2 + (55 if big else 0)), a, sc if not big else 1)
    if t < .08: scr.fill((255, 255, 255), special_flags=pygame.BLEND_ADD)
    bars()

def lamps(t, d, p):
    scr.fill((4, 8, 14)); seq = [[0,0,0,0],[0,1,1,0],[1,1,0,0],[0,0,1,1],[1,0,0,1]]
    bits = seq[min(len(seq) - 1, int(t / .8))]
    for i in range(4):
        cx = W // 2 - 270 + i * 180; cy = H // 2
        if bits[i]:
            g = pygame.Surface((300, 300), pygame.SRCALPHA); pygame.draw.circle(g, (255, 40, 30, 60), (150, 150), 120); scr.blit(g, (cx - 150, cy - 150))
        pygame.draw.circle(scr, (255, 50, 40) if bits[i] else (30, 40, 55), (cx, cy), 62); pygame.draw.circle(scr, (90, 110, 140), (cx, cy), 62, 3)
    glow_text("".join(map(str, bits)), fM, CYAN, (W // 2, H // 2 + 130), int(255 * min(1, t / .4)))
    bars()

def riser(t, d, p):
    scr.fill((4, 8, 14)); n = int(6 + t * 30)
    for k in range(n):
        x = (k * 97 + int(t * 900)) % W; pygame.draw.line(scr, (60, 180, 230), (x, 70), (x, H - 70), 1)
    scr.fill((int(255 * (t / d) ** 3),) * 3, special_flags=pygame.BLEND_ADD); bars()

def title(t, d, p):
    scr.fill((4, 8, 14)); a = int(255 * min(1, t / .2)); sc = 1.25 - 0.25 * min(1, t / 1.2)
    glow_text(p[0], fT, WHITE, (W // 2, H // 2 - 20), a, sc)
    glow_text(p[1], fS, CYAN, (W // 2, H // 2 + 60), int(255 * min(1, max(0, t - .8) / .6)))
    if t < .12: scr.fill((255, 255, 255), special_flags=pygame.BLEND_ADD)
    bars()

def game_shot(t, d, p, st={}):
    if "g" not in st:
        g = G.Game(); g.selftest = True; g.start_level(3); g.countdown = 0
        for _ in range(60): g.update(1 / 30)
        st["g"] = g
    g = st["g"]; b = g.you.bits
    g.you.steer = -1 if (b[0] or b[1]) and not (b[2] or b[3]) else 1 if (b[2] or b[3]) and not (b[0] or b[1]) else 0
    g.update(1 / FPS); g.draw()
    img = pygame.transform.smoothscale(g.screen, (1037, 648)); scr.fill((4, 8, 14)); scr.blit(img, ((W - 1037) // 2, 36))
    shade = pygame.Surface((W, H), pygame.SRCALPHA); shade.fill((0, 20, 40, 70)); scr.blit(shade, (0, 0)); bars()

DRAW = {"card": card, "lamps": lamps, "riser": riser, "title": title, "game": game_shot}

def snd(kind, n):
    t = np.arange(n) / SR
    if kind == "braam":
        x = np.sign(np.sin(2 * np.pi * 55 * t)) * .5 + np.sin(2 * np.pi * 27.5 * t) + .4 * np.sin(2 * np.pi * 110 * t)
        return np.tanh(x * 1.5) * np.exp(-t / 1.4) * .55
    if kind == "hit":
        return (np.sin(2 * np.pi * 50 * t * np.exp(-t * 3)) * np.exp(-t / .35) + np.random.randn(n) * np.exp(-t / .05) * .3) * .7
    if kind == "boom":
        return (np.tanh(2 * np.sin(2 * np.pi * 40 * t * np.exp(-t))) * np.exp(-t / 2.2) + np.random.randn(n) * np.exp(-t / .1) * .4) * .8
    if kind == "riser":
        f = 200 + 2400 * (t / t[-1]) ** 2
        return (np.random.randn(n) * .25 + .3 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * (t / t[-1]) ** 2 * .6
    if kind == "tick":
        out = np.zeros(n)
        for k in range(int(t[-1] / .5) + 1):
            i = int(k * .5 * SR); m = min(n, i + 600)
            out[i:m] += np.sin(2 * np.pi * 2000 * t[:m - i]) * np.exp(-np.arange(m - i) / 120) * .35
        return out
    return np.zeros(n)

def main(mdir, out):
    k = Kokoro(f"{mdir}/kokoro.onnx", f"{mdir}/voices.bin")
    parts, voice_tl, fx_tl, t0 = [], [], [], 0.0
    for idx, (kind, d, p, line, s) in enumerate(SHOTS):
        if line:
            a, _ = k.create(line, voice="am_michael", speed=0.9, lang="en-us"); d = max(d, len(a) / SR + .5); voice_tl.append((t0 + .25, a))
        fx_tl.append((t0, s, d))
        seg = os.path.join(TMP, f"{idx:02d}.mp4")
        if kind == "clip":
            src, st = p
            vf = "scale=1280:720,eq=contrast=1.25:saturation=0.55:brightness=-0.08,colorbalance=bs=0.25:bm=0.1,drawbox=y=0:w=iw:h=70:color=black:t=fill,drawbox=y=ih-70:w=iw:h=70:color=black:t=fill"
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", str(st), "-i", os.path.join(ROOT, src), "-t", f"{d:.2f}", "-an", "-vf", vf, "-r", str(FPS),
                                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", seg])
        else:
            wr = imageio.get_writer(seg, fps=FPS, codec="libx264", quality=8, macro_block_size=None, pixelformat="yuv420p")
            for i in range(int(d * FPS)):
                DRAW[kind](i / FPS, d, p); wr.append_data(pygame.surfarray.array3d(scr).swapaxes(0, 1))
            wr.close()
        parts.append(seg); t0 += d; print(f"{t0:5.1f}s {kind}", flush=True)
    total = t0
    lst = os.path.join(TMP, "l.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    vid = os.path.join(TMP, "v.mp4")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", vid])
    n = int((total + 2) * SR); mix = np.zeros(n)
    ts = np.arange(n) / SR
    mix += (np.sin(2 * np.pi * 36.7 * ts) + .5 * np.sin(2 * np.pi * 73.4 * ts)) * .06 * np.clip(ts / 3, 0, 1) * np.clip((total + 1 - ts) / 2, 0, 1)  # drone
    for st, s, d in fx_tl:
        L = int(min(d + 2.5, 6) * SR); i = int(st * SR); seg = snd(s, L); mix[i:i + L] += seg[: max(0, n - i)]
    for st, a in voice_tl:
        i = int(st * SR); mix[i:i + len(a)] += a[: max(0, n - i)] * 1.3
    mix /= max(1, np.abs(mix).max() / .95); wav = os.path.join(TMP, "a.wav"); sf.write(wav, mix.astype(np.float32), SR)
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", wav, "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-1:LRA=9", "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print("done", round(total, 1))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
