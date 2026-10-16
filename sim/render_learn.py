"""Before/after video: the old network (copied from a hand-written rule) vs the network learned in the simulator,
both running the real firmware with a right motor 8% weaker on dotted tape. Usage: python3 render_learn.py out.mp4"""
import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import imageio.v2 as imageio
from render import View, load_mask, load_log, pad, title_frame, FPS, W, H, INK, MUTED, BLUE, RED, GREEN, BG

def main(out):
    rgb = load_mask()
    lo, ln = pad(load_log("old.csv"), 30), pad(load_log("new.csv"), 30)
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    wr = imageio.get_writer(out, fps=FPS, codec="libx264", quality=8, macro_block_size=None, pixelformat="yuv420p")
    def grab():
        fig.canvas.draw(); wr.append_data(np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy())
    title_frame(fig, "The AI learns the fix", "Same firmware, same weak right motor, dotted tape.\nOnly the 107 weights are different.")
    for _ in range(FPS * 4): grab()
    fig.clf(); fig.patch.set_facecolor(BG)
    fig.text(.02, .955, "Dotted tape, right motor 8% weaker, sensors 20 mm apart", fontsize=15, fontweight="bold", color=INK, va="center")
    v1 = View(fig, [.01, .14, .48, .74], rgb, lo, 20, "Before: copied a hand-written rule")
    v2 = View(fig, [.51, .14, .48, .74], rgb, ln, 20, "After: learned in the simulator")
    for k in range(30 * FPS):
        t = k / FPS; v1.draw(t, 11.5); v2.draw(t, None); grab()
    # learning curve and results
    fig.clf(); fig.patch.set_facecolor(BG)
    d = np.genfromtxt("learn_log4.csv", delimiter=",", names=True)
    m = ~np.isnan(d["validation_fitness"])
    ax = fig.add_axes([.07, .16, .42, .62])
    ax.plot(d["gen"][m], d["validation_fitness"][m], color=BLUE, lw=3, marker="o")
    ax.set_xlabel("training round", fontsize=12, color=INK); ax.set_ylabel("driving score", fontsize=12, color=INK)
    ax.grid(alpha=.3); ax.set_facecolor("white")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    fig.text(.07, .88, "How it learned", fontsize=24, fontweight="bold", color=INK)
    fig.text(.07, .83, "Each round: try 24 small changes to the weights on 16 random cars, keep what drives further.", fontsize=11, color=MUTED)
    rows = [("Random cars, training tracks", "77", "104", "of 120"), ("Random cars, new track shapes", "64", "101", "of 120"),
            ("Real firmware, 90 random cars", "77", "87", "of 90")]
    fig.text(.56, .74, "Clean runs", fontsize=20, fontweight="bold", color=INK)
    fig.text(.80, .74, "before", fontsize=13, color=MUTED); fig.text(.88, .74, "after", fontsize=13, color=MUTED)
    for i, (a, b, c, e) in enumerate(rows):
        y = .64 - i * .12
        fig.text(.56, y, a, fontsize=13, color=INK); fig.text(.80, y, b, fontsize=18, color=RED, fontweight="bold")
        fig.text(.88, y, c, fontsize=18, color=GREEN, fontweight="bold"); fig.text(.935, y, e, fontsize=10, color=MUTED)
    fig.text(.56, .22, "New shapes were never used in training.\nStill 4 inputs, 107 weights: sir's design.\nAll simulation. Not yet on the real car.", fontsize=12, color=MUTED, va="top", linespacing=1.6)
    for _ in range(FPS * 9): grab()
    wr.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "ai_learns_the_fix.mp4")
