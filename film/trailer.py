"""Epic-style trailer (original: holographic lab look, generated score, narrator). Usage: python3 trailer.py <kokoro dir> out.mp4"""
import math, os, subprocess, sys, random
import numpy as np
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame, imageio.v2 as imageio, soundfile as sf
from kokoro_onnx import Kokoro
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "game")); import line_follower_game as G
W, H, FPS, SR = 1280, 720, 30, 24000
BG, INK, CY, CY2, RED, GOLD = (244, 248, 252), (14, 26, 43), (0, 160, 215), (150, 220, 245), (225, 40, 35), (232, 150, 0)
pygame.init(); scr = pygame.Surface((W, H))
FB = lambda s: pygame.font.SysFont("arialblack,arial", s, bold=True); FN = lambda s: pygame.font.SysFont("arial", s)
f_title, f_big, f_mid, f_small, f_mono = FB(110), FB(64), FB(34), FN(22), pygame.font.SysFont("menlo,couriernew", 18, bold=True)
TMP = os.path.join(HERE, "tmp_t"); os.makedirs(TMP, exist_ok=True)
ease = lambda x: 0 if x <= 0 else 1 if x >= 1 else x * x * (3 - 2 * x)
def txt(s, f, c, pos, a=255, anchor="center", spacing=0):
    img = f.render(s, True, c); img.set_alpha(a); r = img.get_rect(**{anchor: pos}); scr.blit(img, r); return r
def grid(t):
    scr.fill(BG)
    for x in range(0, W, 40): pygame.draw.line(scr, (228, 236, 244), (x, 0), (x, H))
    for y in range(0, H, 40): pygame.draw.line(scr, (228, 236, 244), (0, y), (W, y))
    sy = int((t * 260) % (H + 200)) - 100
    s = pygame.Surface((W, 90), pygame.SRCALPHA)
    for k in range(90): pygame.draw.line(s, (0, 160, 215, int(40 * (1 - k / 90))), (0, k), (W, k))
    scr.blit(s, (0, sy))
def glow_line(a, b, col, w=3):
    s = pygame.Surface((W, H), pygame.SRCALPHA); pygame.draw.line(s, (*col, 60), a, b, w + 8); scr.blit(s, (0, 0)); pygame.draw.line(scr, col, a, b, w)
def bars(t, dur):  # letterbox
    pygame.draw.rect(scr, INK, (0, 0, W, 54)); pygame.draw.rect(scr, INK, (0, H - 54, W, 54))

# ---------- scenes
def s_open(t, d):
    scr.fill(BG); a = int(255 * ease(t / 1.2) * ease((d - t) / .6))
    txt("EVERY MACHINE", f_big, INK, (W // 2, H // 2 - 40), a); txt("NEEDS A WAY TO SEE", f_big, CY, (W // 2, H // 2 + 40), int(255 * ease((t - 1.6) / 1) * ease((d - t) / .6)))
def car3d(t, cx, cy, s, rot):
    def P(x, y, z):
        c, si = math.cos(rot), math.sin(rot); x, y = x * c - y * si, x * si + y * c
        return (cx + (x - y) * 0.87 * s, cy + ((x + y) * 0.5 - z) * s)
    box = [(-55, -34), (45, -34), (45, 34), (-55, 34)]
    for z in (14, 18):
        pts = [P(x, y, z) for x, y in box]
        for i in range(4): glow_line(pts[i], pts[(i + 1) % 4], CY, 2)
    for x, y in box: glow_line(P(x, y, 14), P(x, y, 18), CY, 1)
    for wy in (-42, 42):
        ring = [P(11 * math.cos(a), wy, 11 + 11 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 18)]
        for i in range(17): glow_line(ring[i], ring[i + 1], CY, 2)
    glow_line(P(64, -40, 6), P(64, 40, 6), CY, 3)
    sens = [P(70, (1.5 - i) * 20, 4) for i in range(4)]
    for i, p in enumerate(sens): pygame.draw.circle(scr, RED if (int(t * 3) + i) % 3 == 0 else CY, p, 6)
    return P, sens
def s_hud(t, d):
    grid(t); P, sens = car3d(t, W // 2 - 60, H // 2 + 40, 2.4 * ease(t / 1.5) + .01, t * .5)
    calls = [(0.8, "4 IR SENSORS", sens[1], (W - 330, 170)), (2.2, "107 PARAMETERS", P(0, 0, 18), (W - 330, 320)), (3.6, "ESP32 · 200 Hz", P(-20, 0, 20), (60, 230))]
    for t0, label, a, b in calls:
        k = ease((t - t0) / .5)
        if k <= 0: continue
        glow_line(a, (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k), CY, 2)
        if k >= 1:
            r = txt(label, f_mid, INK, b, 255, "topleft"); pygame.draw.line(scr, CY, (r.x, r.bottom + 4), (r.right, r.bottom + 4), 3)
    txt("SYSTEM ONLINE", f_mono, CY, (40, 76), 255 if int(t * 4) % 2 else 120, "topleft"); bars(t, d)
def lamps(bits, c, size):
    for i in range(4):
        x = c[0] + (i - 1.5) * size * 2.3
        if bits[i]:
            g = pygame.Surface((size * 5, size * 5), pygame.SRCALPHA); pygame.draw.circle(g, (255, 60, 40, 80), (size * 2.5, size * 2.5), size * 2); scr.blit(g, (x - size * 2.5, c[1] - size * 2.5))
        pygame.draw.circle(scr, RED if bits[i] else (214, 222, 232), (x, c[1]), size); pygame.draw.circle(scr, CY, (x, c[1]), size + 4, 2)
def s_eyes(t, d):
    grid(t); pats = [[0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1], [0, 0, 0, 0]]
    lamps(pats[int(t * 1.6) % 4], (W // 2, H // 2 + 10), 60)
    txt("FOUR EYES. FOUR BITS.", f_big, INK, (W // 2, 150), int(255 * ease(t / .8))); bars(t, d)
def s_blind(t, d):
    grid(t); lamps([0, 0, 0, 0], (W // 2, H // 2 + 10), 60)
    a = int(255 * ease(t / .5)); txt("WHEN THE LINE BREAKS", f_big, INK, (W // 2, 150), a)
    if t > 1.8:
        gl = random.randint(-6, 6) if int(t * 12) % 3 == 0 else 0
        txt("IT IS BLIND", f_title, RED, (W // 2 + gl, H - 160), int(255 * ease((t - 1.8) / .3)))
    bars(t, d)
net = G.Network()
def s_brain(t, d):
    grid(t); bits = [[0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 0, 0]][int(t / 1.2) % 4]; net(bits); acts = net.acts
    sizes = [4, 7, 7, 2]; cols = [250 + k * 260 for k in range(4)]
    pos = [[(cols[l], 150 + (i + .5) * 440 / sizes[l]) for i in range(sizes[l])] for l in range(4)]
    for l in range(3):
        for j in range(sizes[l + 1]):
            for i in range(sizes[l]):
                c = net.W[l][j, i] * acts[l][i]
                if abs(c) < .08: continue
                col = CY if c > 0 else GOLD; glow_line(pos[l][i], pos[l + 1][j], col, max(1, min(4, int(abs(c) * 3))))
                ph = (t * 1.5 + i * .13 + j * .07) % 1; p = (pos[l][i][0] + (pos[l + 1][j][0] - pos[l][i][0]) * ph, pos[l][i][1] + (pos[l + 1][j][1] - pos[l][i][1]) * ph)
                pygame.draw.circle(scr, col, p, 3)
    for l in range(4):
        for i, p in enumerate(pos[l]):
            a = float(acts[l][i]); pygame.draw.circle(scr, RED if (l == 0 and a > .5) else (255, 255, 255), p, 14); pygame.draw.circle(scr, CY, p, 14, 3)
    txt("SO WE GAVE IT A BRAIN", f_big, INK, (W // 2, 92), int(255 * ease(t / .8))); bars(t, d)
def s_card(lines, cols=None, big=None):
    def f(t, d):
        grid(t)
        for k, s in enumerate(lines):
            a = int(255 * ease((t - k * .5) / .4) * ease((d - t) / .3))
            txt(s, big or f_big, (cols or [INK] * 9)[k], (W // 2, H // 2 - (len(lines) - 1) * 45 + k * 90), a)
        bars(t, d)
    return f
def s_title(t, d):
    scr.fill(BG); k = ease(t / 1.2)
    w = int(W * .7 * k); pygame.draw.line(scr, CY, (W // 2 - w // 2, H // 2 + 70), (W // 2 + w // 2, H // 2 + 70), 4)
    g = f_title.render("LINE FOLLOWER", True, INK); g = pygame.transform.rotozoom(g, 0, .9 + .1 * k); g.set_alpha(int(255 * k)); scr.blit(g, g.get_rect(center=(W // 2, H // 2 - 30)))
    txt("A I", f_big, CY, (W // 2, H // 2 + 130), int(255 * ease((t - 1) / .8)))
    txt("COMING TO A REAL TRACK", f_mid, INK, (W // 2, H - 120), int(255 * ease((t - 2.2) / .8)))
    txt("Built by Manish  ·  idea by my professor  ·  NMAMIT", f_small, (83, 100, 125), (W // 2, H - 70), int(255 * ease((t - 3) / .8)))
def s_game(t, d, st={}):
    if "g" not in st:
        g = G.Game(); g.selftest = True; g.start_level(3); g.countdown = 0; st["g"] = g
    g = st["g"]; g.hard = t > d * .5; b = g.you.bits
    g.you.steer = -1 if (b[0] or b[1]) and not (b[2] or b[3]) else 1 if (b[2] or b[3]) and not (b[0] or b[1]) else 0
    g.update(1 / FPS); g.draw(); scr.blit(pygame.transform.smoothscale(g.screen, (1152, 720)), (64, 0)); bars(t, d)

# ---------- edit list: (kind, arg, seconds, narration or None, sfx)
CLIP = lambda f: os.path.join(ROOT, "sim", f)
EDL = [
 ("draw", s_open, 4.2, "Every machine needs a way to see.", "boom"),
 ("draw", s_hud, 5.0, None, "riser"),
 ("draw", s_eyes, 3.6, "This one had four eyes. Four bits.", "hit"),
 ("draw", s_blind, 4.2, "And one weakness. When the line breaks, it is blind.", "braam"),
 ("clip", (CLIP("line_follower_sim.mp4"), 49.5), 3.4, None, "hit"),
 ("draw", s_brain, 5.0, "So we gave it a brain. One hundred and seven numbers.", "braam"),
 ("draw", s_card(["WE LET IT FAIL", "A THOUSAND TIMES"], [INK, RED]), 3.2, "We let it fail. A thousand times.", "hit"),
 ("clip", (CLIP("ai_learns_the_fix.mp4"), 12.0), 2.6, None, "hit"),
 ("draw", s_card(["UNTIL IT LEARNED"], [CY], f_title), 2.4, "Until it learned.", "braam"),
 ("clip", (CLIP("ai_learns_the_fix.mp4"), 24.0), 2.2, None, "hit"),
 ("clip", (CLIP("ai_learns_the_fix.mp4"), 35.0), 2.6, "Weak motors. Broken lines. Tracks it had never seen.", "hit"),
 ("clip", (CLIP("line_follower_sim.mp4"), 20.0), 2.0, None, "hit"),
 ("draw", s_card(["THE QUESTION IS NO LONGER", "CAN IT FOLLOW THE LINE"]), 3.8, "The question is no longer, can it follow the line.", "riser"),
 ("draw", s_card(["CAN YOU?"], [GOLD], f_title), 2.6, "The question is, can you?", "braam"),
 ("draw", s_game, 6.0, None, "pulse"),
 ("draw", s_title, 6.5, "Line Follower A I. Coming to a real track.", "boom"),
]

# ---------- score
def sfx(name, n):
    t = np.arange(n) / SR
    if name == "boom": return np.sin(2 * np.pi * (60 * np.exp(-t * 3)) * t) * np.exp(-t * 1.6) * .9
    if name == "hit": return (np.sin(2 * np.pi * 55 * t) * .8 + np.random.randn(n) * .25 * np.exp(-t * 25)) * np.exp(-t * 6)
    if name == "braam":
        s = sum(((t * f) % 1 * 2 - 1) for f in (55, 55.4, 82.4, 110)) / 4
        s = np.convolve(s, np.ones(18) / 18, mode="same"); return s * np.minimum(1, t / .08) * np.exp(-t * .9) * 1.1
    if name == "riser": return np.random.randn(n) * (t / t[-1]) ** 2 * .35 * np.convolve(np.ones(n), [1], mode="same")[:n] / 1 + np.sin(2 * np.pi * (200 + 900 * (t / t[-1]) ** 2) * t) * (t / t[-1]) ** 2 * .2
    if name == "pulse":
        out = np.zeros(n)
        for k in range(int(t[-1] / .25)):
            i = int(k * .25 * SR); m = min(n - i, int(.15 * SR)); out[i:i + m] += np.sin(2 * np.pi * 70 * t[:m]) * np.exp(-t[:m] * 18) * .9
        return out
    return np.zeros(n)

def main(mdir, out):
    k = Kokoro(f"{mdir}/kokoro.onnx", f"{mdir}/voices.bin")
    segs, voice_ev, sfx_ev, t0 = [], [], [], 0.0
    for idx, (kind, arg, dur, line, fx) in enumerate(EDL):
        if line:
            a, _ = k.create(line, voice="bm_george", speed=0.88, lang="en-us"); dur = max(dur, len(a) / SR + 0.5); voice_ev.append((t0 + .25, a))
        sfx_ev.append((t0, fx, dur)); seg = os.path.join(TMP, f"{idx:02d}.mp4")
        if kind == "clip":
            src, st = arg
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", str(st), "-i", src, "-t", f"{dur:.2f}", "-an",
                "-vf", f"scale=1280:720,eq=contrast=1.12:saturation=1.15,tpad=stop_mode=clone:stop_duration=3,drawbox=x=0:y=0:w=iw:h=54:color=0x0e1a2b:t=fill,drawbox=x=0:y=ih-54:w=iw:h=54:color=0x0e1a2b:t=fill",
                "-t", f"{dur:.2f}", "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", seg])
        else:
            wr = imageio.get_writer(seg, fps=FPS, codec="libx264", quality=8, macro_block_size=None, pixelformat="yuv420p")
            n = int(dur * FPS)
            for i in range(n):
                arg(i / FPS, dur)
                if i < 3:  # white flash on the cut
                    s = pygame.Surface((W, H), pygame.SRCALPHA); s.fill((255, 255, 255, int(200 * (1 - i / 3)))); scr.blit(s, (0, 0))
                wr.append_data(pygame.surfarray.array3d(scr).swapaxes(0, 1))
            wr.close()
        segs.append(seg); print(f"{t0:5.1f}s {dur:4.1f}s {fx}", flush=True); t0 += dur
    total = t0; n = int((total + .5) * SR)
    lst = os.path.join(TMP, "l.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in segs))
    vid = os.path.join(TMP, "v.mp4")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-r", str(FPS), vid])
    voice = np.zeros(n); music = np.zeros(n); ts = np.arange(n) / SR
    for st, a in voice_ev: i = int(st * SR); voice[i:i + len(a)] += a[:n - i]
    drone = (np.sin(2 * np.pi * 41.2 * ts) + .5 * np.sin(2 * np.pi * 61.7 * ts) + .3 * np.sin(2 * np.pi * 82.4 * ts * (1 + .002 * np.sin(ts)))) * .12
    music += drone * np.clip(ts / 3, 0, 1) * np.clip((total - ts) / 2, 0, 1)
    for st, fx, dur in sfx_ev:
        i = int(st * SR); m = min(n - i, int((dur if fx in ("riser", "pulse") else 3.0) * SR))
        if fx == "riser": i = int(max(0, (st + dur - 3.0)) * SR); m = min(n - i, int(3.0 * SR))
        music[i:i + m] += sfx(fx, m)
    music = np.convolve(music, [.5, .5], mode="same")
    duck = np.convolve((np.abs(voice) > .01).astype(float), np.ones(int(.25 * SR)) / int(.25 * SR), mode="same")
    mix = voice * 1.1 + music * (1 - .45 * np.clip(duck * 3, 0, 1)); mix /= max(1, np.abs(mix).max() / .95)
    wav = os.path.join(TMP, "a.wav"); sf.write(wav, mix.astype(np.float32), SR)
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", wav, "-c:v", "copy", "-af", "loudnorm=I=-15:TP=-1:LRA=9", "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print("done", round(total, 1))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
