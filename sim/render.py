"""Renders the simulation logs to an mp4. Usage: python3 render.py out.mp4"""
import sys, subprocess, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle
import imageio.v2 as imageio

FPS, W, H = 30, 1280, 720
INK, MUTED, BLUE, RED, GREEN, BG = "#0e1a2b", "#53647d", "#0a6ea8", "#e5322d", "#1a8a5a", "#f5f8fc"

def run(args, log):
    out = subprocess.check_output(["./hil_sim", "--quiet", "--log", log, "--mask", "mask.pgm"] + args)
    return json.loads(out)

def load_mask():
    with open("mask.pgm", "rb") as f:
        f.readline(); w, h = map(int, f.readline().split()); f.readline()
        a = np.frombuffer(f.read(), dtype=np.uint8).reshape(h, w)
    rgb = np.empty((h, w, 3), np.uint8); rgb[:] = (236, 240, 246); rgb[a == 0] = (16, 21, 28)
    return rgb

def load_log(path):
    return np.genfromtxt(path, delimiter=",", names=True)

def rect(x0, x1, y0, y1): return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], float)

class View:
    """One track window with the car, the path it left, and a small status panel."""
    def __init__(self, fig, box, rgb, log, spacing, title, hud_box=None, inset_box=None):
        self.log, self.sp = log, spacing
        self.ax = fig.add_axes(box); self.ax.set_xlim(-980, 980); self.ax.set_ylim(-610, 610); self.ax.axis("off")
        self.ax.imshow(rgb, extent=(-950, 950, -600, 600), interpolation="bilinear", zorder=0)
        self.ax.set_title(title, fontsize=13, color=INK, loc="left", fontweight="bold")
        self.trail, = self.ax.plot([], [], color=BLUE, lw=2, alpha=.55, zorder=2)
        self.body = Polygon(rect(-55, 45, -33, 33), closed=True, fc=BLUE, ec=INK, lw=1, zorder=5); self.ax.add_patch(self.body)
        self.wl = Polygon(rect(-14, 14, 35, 46), fc="#14171c", zorder=4); self.wr = Polygon(rect(-14, 14, -46, -35), fc="#14171c", zorder=4)
        self.bar = Polygon(rect(64, 76, -(1.5 * spacing + 9), 1.5 * spacing + 9), fc="#1a4fd0", ec=INK, lw=.6, zorder=5)
        self.arm = Polygon(rect(45, 64, -5, 5), fc="#222", zorder=4)
        for p in (self.wl, self.wr, self.bar, self.arm): self.ax.add_patch(p)
        self.leds = [Circle((0, 0), 11, fc="white", ec=INK, lw=1, zorder=6) for _ in range(4)]
        for c in self.leds: self.ax.add_patch(c)
        self.hud = self.ax.text(0, -0.02, "", fontsize=11, color=INK, family="monospace", va="top", zorder=9, transform=self.ax.transAxes)
        self.banner = self.ax.text(0, 0, "", fontsize=20, color="white", ha="center", va="center", fontweight="bold", zorder=10,
                                   bbox=dict(fc=RED, ec="none", boxstyle="round,pad=.5"))
        self.inset = None
        if inset_box:
            self.inset = fig.add_axes(inset_box); self.inset.imshow(rgb, extent=(-950, 950, -600, 600), interpolation="nearest")
            self.inset.set_xticks([]); self.inset.set_yticks([])
            for s in self.inset.spines.values(): s.set_edgecolor(INK); s.set_linewidth(1.5)
            self.ip = [Polygon(np.zeros((4, 2)), fc=c) for c in (BLUE, "#14171c", "#14171c", "#1a4fd0")]
            for p in self.ip: self.inset.add_patch(p)
            self.ic = [Circle((0, 0), 6, fc="white", ec=INK, lw=1) for _ in range(4)]
            for c in self.ic: self.inset.add_patch(c)
            self.inset.set_title("Close-up: sensors on the tape", fontsize=9, color=MUTED, loc="left")
        self.n = len(log)
        self.end = self.n - 1

    @staticmethod
    def tf(poly, x, y, th):
        c, s = np.cos(th), np.sin(th)
        return poly @ np.array([[c, s], [-s, c]]) + [x, y]

    def draw(self, t, failed_at=None):
        i = min(int(t * 50), self.n - 1); r = self.log[i]
        x, y, th = r["x"], r["y"], r["th"]
        j = max(0, i - 150); self.trail.set_data(self.log["x"][j:i + 1], self.log["y"][j:i + 1])
        for p, base in ((self.body, rect(-55, 45, -33, 33)), (self.wl, rect(-14, 14, 35, 46)), (self.wr, rect(-14, 14, -46, -35)),
                        (self.bar, rect(64, 76, -(1.5 * self.sp + 9), 1.5 * self.sp + 9)), (self.arm, rect(45, 64, -5, 5))):
            p.set_xy(self.tf(base, x, y, th))
        on = [int(r[f"s{k}"]) for k in range(4)]
        for k, c in enumerate(self.leds):
            lat = (1.5 - k) * self.sp; px, py = self.tf(np.array([[70.0, lat]]), x, y, th)[0]
            c.center = (px, py); c.set_facecolor(RED if on[k] else "white")
        L, Rr = r["dutyL"], r["dutyR"]
        self.hud.set_text(f"t {t:4.1f} s   laps {int(r['laps'])}   sensors {''.join(map(str, on))}   PWM L {int(L):3d} R {int(Rr):3d}   off line {r['cte']:3.0f} mm")
        stopped = failed_at is not None and t >= failed_at
        self.banner.set_text("LINE LOST: firmware stopped" if stopped else "")
        self.banner.set_position((0, 0))
        if self.inset is not None:
            self.inset.set_xlim(x - 150, x + 150); self.inset.set_ylim(y - 100, y + 100)
            for p, base in zip(self.ip, (rect(-55, 45, -33, 33), rect(-14, 14, 35, 46), rect(-14, 14, -46, -35), rect(64, 76, -(1.5 * self.sp + 9), 1.5 * self.sp + 9))):
                p.set_xy(self.tf(base, x, y, th))
            for k, c in enumerate(self.ic):
                lat = (1.5 - k) * self.sp; c.center = tuple(self.tf(np.array([[70.0, lat]]), x, y, th)[0]); c.set_facecolor(RED if on[k] else "white")

def pad(log, seconds):
    need = int(seconds * 50) + 1
    if len(log) >= need: return log[:need]
    return np.concatenate([log, np.repeat(log[-1:], need - len(log))])

def title_frame(fig, big, small):
    fig.clf(); fig.patch.set_facecolor(BG)
    fig.text(.06, .58, big, fontsize=40, fontweight="bold", color=INK, va="center")
    fig.text(.06, .38, small, fontsize=17, color=MUTED, va="top", linespacing=1.6)

def main(out):
    rgb = load_mask()
    # clip A: nominal, mixed track
    a = run(["--track", "mixed", "--seconds", "32"], "a.csv"); la = pad(load_log("a.csv"), 32)
    # clip B: weak right motor, same track; 30 mm vs 20 mm sensor spacing
    b1 = run(["--track", "mixed", "--seconds", "26", "--gainR", "0.92", "--spacing", "30"], "b1.csv")
    b2 = run(["--track", "mixed", "--seconds", "26", "--gainR", "0.92", "--spacing", "20"], "b2.csv")
    lb1, lb2 = pad(load_log("b1.csv"), 26), pad(load_log("b2.csv"), 26)
    print(a, b1, b2, sep="\n")
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    wr = imageio.get_writer(out, fps=FPS, codec="libx264", quality=8, macro_block_size=None, pixelformat="yuv420p")
    def grab():
        fig.canvas.draw(); wr.append_data(np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy())
    # title
    title_frame(fig, "AI line follower car", "The real ESP32 firmware, run on a PC against a virtual car.\nFour IR sensors, a 107-weight neural network, two motors.\nSimulation, not a real car.")
    for _ in range(FPS * 4): grab()
    # clip A
    fig.clf(); fig.patch.set_facecolor(BG)
    fig.text(.02, .955, "Run 1: mixed track (solid, dashed, solid, dotted, solid)", fontsize=15, fontweight="bold", color=INK, va="center")
    va = View(fig, [.02, .12, .70, .78], rgb, la, 20, "", inset_box=[.735, .56, .245, .30])
    fig.text(.735, .50, f"Result over 32 s\nlaps: {a['laps']}\nmean error: {a['mean_cte_mm']:.1f} mm\nworst error: {a['max_cte_mm']:.1f} mm\nstayed on the line: {a['on_line_pct']:.0f}%", fontsize=12, color=INK, va="top", family="monospace", linespacing=1.5)
    fig.text(.735, .22, "Gaps in the dashed and\ndotted parts read 0000.\nThe car just keeps going\nstraight until it sees tape.", fontsize=11, color=MUTED, va="top", linespacing=1.5)
    for k in range(32 * FPS): va.draw(k / FPS); grab()
    # title B
    title_frame(fig, "Same car, weak right motor", "Real motors never match: here the right one is 8% weaker.\nSensor spacing decides whether the car survives it.")
    for _ in range(FPS * 3): grab()
    # clip B
    fig.clf(); fig.patch.set_facecolor(BG)
    fig.text(.02, .955, "Right motor 8% weaker, mixed track", fontsize=15, fontweight="bold", color=INK, va="center")
    s1 = f"Sensors 30 mm apart" ; s2 = "Sensors 20 mm apart"
    v1 = View(fig, [.01, .14, .48, .74], rgb, lb1, 30, s1); v2 = View(fig, [.51, .14, .48, .74], rgb, lb2, 20, s2)
    f1 = b1["stop_time"] if b1["firmware_stopped"] else None; f2 = b2["stop_time"] if b2["firmware_stopped"] else None
    for k in range(26 * FPS):
        t = k / FPS; v1.draw(t, f1); v2.draw(t, f2); grab()
    for _ in range(FPS * 1): grab()
    # summary
    title_frame(fig, "What the simulation found", "20 mm sensor spacing: 11 of 12 hard scenarios clean.\n30 mm spacing: 5 of 12.\nRandom motor mismatch and noise, mixed tape: 30 of 30 clean runs.\nNot yet tested on a real car.")
    for _ in range(FPS * 5): grab()
    wr.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "line_follower_sim.mp4")
