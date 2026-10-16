"""Makes the project film: narration (kokoro TTS), music, animated scenes and real simulator/game footage.
Usage: python3 film.py <kokoro dir> out.mp4"""
import math, os, subprocess, sys, json, random
import numpy as np
os.environ.setdefault("SDL_VIDEODRIVER", "dummy"); os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame, imageio.v2 as imageio, soundfile as sf
from kokoro_onnx import Kokoro

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "game"))
import line_follower_game as G

W, H, FPS, SR = 1280, 720, 30, 24000
INK, MUTED, BG, AI, YOU, RED, GREEN, LINE = (14, 26, 43), (83, 100, 125), (245, 248, 252), (10, 120, 180), (232, 150, 0), (225, 40, 35), (26, 138, 90), (205, 215, 228)
pygame.init(); screen = pygame.Surface((W, H))
F = lambda size, bold=True: pygame.font.SysFont("arialblack,arial" if bold and size > 40 else "arial", size, bold=bold)
f_huge, f_big, f_mid, f_txt, f_small = F(96), F(60), F(36), F(26, False), F(20, False)
TMP = os.path.join(HERE, "tmp"); os.makedirs(TMP, exist_ok=True)

SCENES = [
 ("eyes",   "This car has four eyes. Four tiny infrared sensors, looking straight down at the floor. Each one can only say one thing. Line. Or no line."),
 ("tracks", "Following a solid line is easy. But real tracks break. Dashes. Dots. Gaps where every sensor goes dark. That is where most line followers get lost."),
 ("brain",  "My professor had an idea. Give the car a brain. Not a big computer. A tiny neural network. Four inputs, two hidden layers, two motor outputs. One hundred and seven numbers. Small enough for a cheap E S P thirty-two chip."),
 ("sim",    "Before touching any hardware, I built a simulator, and ran the real car code on a virtual car. On a mixed track, it worked. Two laps, about two millimetres from the line on average."),
 ("flaw",   "Then I made it realistic. Real motors never match. With the right motor eight percent weaker and the sensors thirty millimetres apart, the car lost the line in the gaps. The simulator found a real problem before I bought a single part. Moving the sensors to twenty millimetres fixed most of it."),
 ("learn",  "But dotted tape still beat it. So I let the network teach itself. Hundreds of virtual cars, with weak motors and noisy sensors. Small changes to its weights, keeping whatever drove further. No rules from me."),
 ("curve",  "Clean runs went from seventy-seven to one hundred and four, out of one hundred and twenty. On track shapes it had never seen, from sixty-four to one hundred and one."),
 ("game",   "Then a question. Could a human do better? So I turned it into a game. You race the network. In hard mode the track disappears, and you get only the four lamps. Exactly what the network sees. It is much harder than it looks."),
 ("chip",   "The same code compiles for a real E S P thirty-two, using twenty-one percent of its memory. The compiler even caught a bug the simulator could not."),
 ("next",   "Everything so far is simulation. The next chapter is the real car, on real tape, learning from real driving."),
 ("end",    "Four sensors. One hundred and seven numbers. One line. This is the A I line follower."),
]

def text(s, font, col, pos, anchor="center", alpha=255):
    img = font.render(s, True, col)
    if alpha < 255: img.set_alpha(alpha)
    r = img.get_rect(**{anchor: pos}); screen.blit(img, r); return r

ease = lambda x: 0 if x <= 0 else 1 if x >= 1 else x * x * (3 - 2 * x)
fade = lambda t, a, d=0.6: int(255 * ease((t - a) / d))

def lamps(bits, center, size):
    pad = pygame.Rect(0, 0, 4 * size * 2 + 40, size * 2 + 40); pad.center = center
    pygame.draw.rect(screen, (255, 255, 255), pad, border_radius=20); pygame.draw.rect(screen, LINE, pad, 3, border_radius=20)
    for i in range(4):
        cx = pad.x + 20 + size + i * size * 2
        if bits[i]:
            glow = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 60, 40, 70), (size * 2, size * 2), int(size * 1.5)); screen.blit(glow, (cx - size * 2, pad.centery - size * 2))
        pygame.draw.circle(screen, RED if bits[i] else (214, 222, 232), (cx, pad.centery), size - 6)
        pygame.draw.circle(screen, (150, 20, 15) if bits[i] else (190, 200, 214), (cx, pad.centery), size - 6, 3)

def caption(t, label):
    if label:
        a = fade(t, 0.2)
        r = text(label, f_small, MUTED, (40, H - 34), "topleft", a)

# ---------------------------------------------------------------- drawn scenes
def scene_eyes(t, dur):
    screen.fill(BG)
    pats = [[0, 0, 0, 0], [0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 0, 0], [0, 1, 1, 0]]
    bits = pats[min(len(pats) - 1, int(t / 1.6))] if t > 1.2 else [0, 0, 0, 0]
    lamps(bits, (W // 2, H // 2 + 20), 70)
    text("FOUR EYES", f_big, INK, (W // 2, 150), alpha=fade(t, 0.3))
    text("".join(map(str, bits)), f_mid, RED if any(bits) else MUTED, (W // 2, H // 2 + 150), alpha=fade(t, 1.2))
    text("1 = line   0 = no line", f_txt, MUTED, (W // 2, H // 2 + 195), alpha=fade(t, 4))

def scene_tracks(t, dur):
    screen.fill(BG)
    y = H // 2 + 30; x0, x1 = 80, W - 80
    pygame.draw.rect(screen, (226, 232, 239), (40, y - 90, W - 80, 180), border_radius=16)
    seg = (x1 - x0) / 3
    for k, name in enumerate(("SOLID", "DASHED", "DOTTED")):
        a = fade(t, 0.5 + k * 1.6)
        if a == 0: continue
        sx = x0 + k * seg
        surf = pygame.Surface((W, H), pygame.SRCALPHA)
        if k == 0: pygame.draw.rect(surf, (16, 20, 27, a), (sx, y - 8, seg, 16))
        elif k == 1:
            for d in range(int(sx), int(sx + seg), 60): pygame.draw.rect(surf, (16, 20, 27, a), (d, y - 8, 30, 16))
        else:
            for d in range(int(sx), int(sx + seg), 38): pygame.draw.circle(surf, (16, 20, 27, a), (d + 6, y), 8)
        screen.blit(surf, (0, 0))
        text(name, f_mid, INK, (sx + seg / 2, y - 130), alpha=a)
    cx = x0 + (x1 - x0) * ease(max(0, t - 1) / max(1, dur - 2))
    pygame.draw.rect(screen, AI, (cx - 50, y - 30, 70, 60), border_radius=8); pygame.draw.rect(screen, (30, 70, 190), (cx + 24, y - 34, 10, 68))
    k = int((cx - x0) // seg)
    on = k == 0 or (k == 1 and int(cx - x0 - seg) % 60 < 30) or (k == 2 and int(cx - x0 - 2 * seg) % 38 < 14)
    lamps([0, 1 if on else 0, 1 if on else 0, 0], (W // 2, H - 110), 26)
    text("GAPS: every sensor goes dark", f_txt, RED, (W // 2, 120), alpha=fade(t, 5.5))

net = G.Network()
def scene_brain(t, dur):
    screen.fill(BG)
    pats = [[0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 1, 1], [1, 0, 0, 0], [0, 0, 0, 1], [0, 1, 1, 0]]
    bits = pats[int(t / 2.0) % len(pats)]; out = net(bits); acts = net.acts
    sizes = [4, 7, 7, 2]; cols = [190 + k * 240 for k in range(4)]
    top, bot = 150, H - 120
    pos = [[(cols[l], top + (i + .5) * (bot - top) / sizes[l]) for i in range(sizes[l])] for l in range(4)]
    grow = ease(t / 3)
    for l in range(3):
        for j in range(sizes[l + 1]):
            for i in range(sizes[l]):
                c = net.W[l][j, i] * acts[l][i]
                if abs(c) < .05 or grow < (l + 1) / 4: continue
                pygame.draw.line(screen, AI if c > 0 else (232, 135, 14), pos[l][i], pos[l + 1][j], max(1, min(6, int(abs(c) * 4))))
    for l in range(4):
        if grow < l / 4: continue
        for i, p in enumerate(pos[l]):
            a = float(acts[l][i])
            fill = (RED if a > .5 else (230, 235, 242)) if l == 0 else tuple(int(255 - (255 - c) * min(1, abs(a))) for c in (AI if a >= 0 else (232, 135, 14)))
            pygame.draw.circle(screen, fill, p, 18 if l in (0, 3) else 14); pygame.draw.circle(screen, INK, p, 18 if l in (0, 3) else 14, 2)
    for i, nm in enumerate(("LEFT MOTOR", "RIGHT MOTOR")):
        text(f"{nm}  {out[i]:.2f}", f_txt, AI, (pos[3][i][0] + 34, pos[3][i][1]), "midleft", fade(t, 2.5))
    for i in range(4): text(f"S{i + 1}", f_txt, MUTED, (pos[0][i][0] - 34, pos[0][i][1]), "midright", fade(t, .5))
    text("107 NUMBERS", f_big, INK, (W // 2, 70), alpha=fade(t, 6))
    text("4 → 7 → 7 → 2   ·   runs on an ESP32", f_txt, MUTED, (W // 2, 118), alpha=fade(t, 8))

def scene_chip(t, dur):
    screen.fill(BG)
    chip = pygame.Rect(0, 0, 360, 220); chip.center = (W // 2 - 220, H // 2 + 10)
    pygame.draw.rect(screen, (20, 30, 48), chip, border_radius=14)
    for k in range(10):
        pygame.draw.rect(screen, (190, 196, 205), (chip.x + 20 + k * 33, chip.y - 18, 14, 18)); pygame.draw.rect(screen, (190, 196, 205), (chip.x + 20 + k * 33, chip.bottom, 14, 18))
    pygame.draw.rect(screen, (190, 196, 205), (chip.x + 110, chip.y + 50, 140, 110), border_radius=6)
    text("ESP32", f_mid, INK, (chip.centerx + 0, chip.centery + 5))
    x = W // 2 + 20
    text("Compiled with the official toolchain", f_txt, MUTED, (x, 230), "topleft", fade(t, .5))
    text("283 KB", f_huge, AI, (x, 270), "topleft", fade(t, 1.2))
    text("21% of flash  ·  6% of RAM", f_mid, INK, (x, 390), "topleft", fade(t, 2))
    text("Bug caught: B1, B2, B3 clash with Arduino", f_txt, RED, (x, 450), "topleft", fade(t, 5))

def scene_next(t, dur):
    screen.fill(BG)
    steps = ["Simulation", "Self-learning", "Real car", "Learn from real driving"]
    for i, s in enumerate(steps):
        a = fade(t, .4 + i * .9); cx = 200 + i * 290; cy = H // 2
        done = i < 2
        pygame.draw.circle(screen, GREEN if done else (226, 232, 240), (cx, cy), 46)
        pygame.draw.circle(screen, GREEN if done else LINE, (cx, cy), 46, 4)
        if done and a > 0:
            pygame.draw.lines(screen, (255, 255, 255), False, [(cx - 18, cy + 2), (cx - 4, cy + 16), (cx + 20, cy - 14)], 7)
        elif not done:
            text(str(i + 1), f_mid, MUTED, (cx, cy), alpha=a)
        text(s, f_txt, INK if done else MUTED, (cx, cy + 80), alpha=a)
        if i < 3: pygame.draw.line(screen, LINE, (cx + 52, cy), (cx + 238, cy), 4)
    text("NEXT: THE REAL CAR", f_big, INK, (W // 2, 150), alpha=fade(t, 3.5))

def scene_end(t, dur):
    screen.fill(BG)
    lines = ["FOUR SENSORS.", "107 NUMBERS.", "ONE LINE."]
    for i, s in enumerate(lines):
        text(s, f_big, AI if i == 2 else INK, (W // 2, 180 + i * 85), alpha=fade(t, .3 + i * 1.3))
    text("AI Line Follower", f_mid, INK, (W // 2, 470), alpha=fade(t, 5))
    text("Built by Manish  ·  idea by my professor  ·  NMAMIT", f_txt, MUTED, (W // 2, 520), alpha=fade(t, 5.5))
    text("github.com/manishkshtriya/linefollower-ai", f_txt, AI, (W // 2, 560), alpha=fade(t, 6))

def scene_game(t, dur, state={}):
    if "g" not in state:
        g = G.Game(); g.selftest = True; g.start_level(3); g.countdown = 0; state["g"] = g
    g = state["g"]
    g.hard = t > dur * 0.55
    b = g.you.bits
    g.you.steer = -1 if (b[0] or b[1]) and not (b[2] or b[3]) else 1 if (b[2] or b[3]) and not (b[0] or b[1]) else 0
    g.update(1 / FPS); g.draw()
    img = pygame.transform.smoothscale(g.screen, (1152, 720))
    screen.fill(BG); screen.blit(img, (64, 0))
    label = "HARD MODE: only the four lamps" if g.hard else "BE THE AI: you vs the network"
    r = f_mid.render(label, True, (255, 255, 255)); box = r.get_rect(midbottom=(W // 2, H - 24)).inflate(30, 14)
    pygame.draw.rect(screen, RED if g.hard else YOU, box, border_radius=10); screen.blit(r, r.get_rect(center=box.center))

DRAWN = {"eyes": scene_eyes, "tracks": scene_tracks, "brain": scene_brain, "chip": scene_chip, "next": scene_next, "end": scene_end, "game": scene_game}
CLIPS = {  # (file, start second, label)
    "sim": (os.path.join(ROOT, "sim", "line_follower_sim.mp4"), 6.0, "Simulator running the real firmware"),
    "flaw": (os.path.join(ROOT, "sim", "line_follower_sim.mp4"), 39.0, "Right motor 8% weaker: 30 mm vs 20 mm sensor spacing"),
    "learn": (os.path.join(ROOT, "sim", "ai_learns_the_fix.mp4"), 4.0, "Before vs after learning"),
    "curve": (os.path.join(ROOT, "sim", "ai_learns_the_fix.mp4"), 34.2, "Clean runs, before and after"),
}

def main(mdir, out):
    k = Kokoro(f"{mdir}/kokoro.onnx", f"{mdir}/voices.bin")
    parts, timeline, t0 = [], [], 0.0
    for name, line in SCENES:
        a, sr = k.create(line, voice="af_heart", speed=0.98, lang="en-us")
        dur = len(a) / SR + (2.4 if name == "end" else 1.3)
        timeline.append((t0 + 0.6, a)); seg = os.path.join(TMP, f"{len(parts):02d}_{name}.mp4")
        cached = os.path.exists(seg.replace(".mp4", "_c.mp4") if name in CLIPS else seg) and name not in os.environ.get("RERENDER", "all").split(",") and os.environ.get("RERENDER")
        if cached:
            seg = seg.replace(".mp4", "_c.mp4") if name in CLIPS else seg
        elif name in CLIPS:
            src, start, label = CLIPS[name]
            vid = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]))
            avail = max(0.5, vid - start); pad = max(0.0, dur - avail)
            vf = f"scale=1280:720,tpad=stop_mode=clone:stop_duration={pad:.2f},drawbox=x=0:y=ih-56:w=iw:h=56:color=white@0.85:t=fill"
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", src, "-t", f"{dur:.2f}", "-an", "-vf", vf,
                                   "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", seg])
            # caption bar text drawn by a second pass with pygame would need decoding; keep ffmpeg box and add label frames below
            cap = os.path.join(TMP, f"cap_{name}.png")
            s2 = pygame.Surface((W, 56), pygame.SRCALPHA); s2.blit(f_txt.render(label, True, INK), (30, 14)); pygame.image.save(s2, cap)
            seg2 = seg.replace(".mp4", "_c.mp4")
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", seg, "-i", cap, "-filter_complex", "[0][1]overlay=0:H-56",
                                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", seg2]); seg = seg2
        else:
            wr = imageio.get_writer(seg, fps=FPS, codec="libx264", quality=8, macro_block_size=None, pixelformat="yuv420p")
            n = int(dur * FPS)
            for i in range(n):
                tt = i / FPS; DRAWN[name](tt, dur)
                if i > n - 12 and name != "end":  # short fade to the next scene
                    sh = pygame.Surface((W, H), pygame.SRCALPHA); sh.fill((245, 248, 252, int(255 * (i - (n - 12)) / 12))); screen.blit(sh, (0, 0))
                wr.append_data(pygame.surfarray.array3d(screen).swapaxes(0, 1))
            wr.close()
        parts.append(seg); print(f"{t0:6.1f}s  {name:7s} {dur:5.1f}s", flush=True); t0 += dur
    total = t0
    # concat video
    lst = os.path.join(TMP, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    silent = os.path.join(TMP, "video.mp4")
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-r", str(FPS), silent])
    # audio: narration + soft music bed (Am - F - C - G)
    n = int((total + 1) * SR); voice = np.zeros(n, np.float32)
    for st, a in timeline: i = int(st * SR); voice[i:i + len(a)] += a[: max(0, n - i)]
    ts = np.arange(n) / SR; music = np.zeros(n, np.float32)
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 196.0, 261.63), (196.0, 246.94, 293.66)]
    bar = 4.0
    for ci in range(int(total / bar) + 2):
        a, b = int(ci * bar * SR), int((ci + 1) * bar * SR)
        if a >= n: break
        seg_t = ts[a:min(b, n)] - ci * bar; env = np.minimum(1, seg_t / 1.0) * np.minimum(1, (bar - seg_t) / 1.0)
        tone = sum(np.sin(2 * np.pi * f * ts[a:min(b, n)]) + .3 * np.sin(4 * np.pi * f * ts[a:min(b, n)]) for f in chords[ci % 4])
        music[a:min(b, n)] += tone * env * 0.05
        for beat in range(4):  # soft pulse
            p = a + int(beat * SR); q = min(n, p + int(.12 * SR))
            if p < n: music[p:q] += np.sin(2 * np.pi * chords[ci % 4][0] * 2 * ts[p:q]) * np.exp(-np.arange(q - p) / (0.03 * SR)) * 0.08
    duck = np.convolve((np.abs(voice) > 0.01).astype(np.float32), np.ones(int(.3 * SR)) / int(.3 * SR), mode="same")
    music *= (1 - 0.6 * np.clip(duck * 3, 0, 1)); fade_out = np.clip((total + 1 - ts) / 2.5, 0, 1); music *= fade_out
    mix = voice + music; mix /= max(1.0, np.abs(mix).max() / .95)
    wav = os.path.join(TMP, "audio.wav"); sf.write(wav, mix, SR)
    subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", silent, "-i", wav, "-c:v", "copy", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", out])
    print("done", round(total, 1), "s ->", out)

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "ai_line_follower_film.mp4")
