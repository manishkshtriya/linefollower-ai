"""Voice-over for render_learn.py's video. Usage: python3 narrate_learn.py <kokoro dir> in.mp4 out.mp4"""
import sys, subprocess, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro
mdir, src, dst = sys.argv[1:4]; SR = 24000
LINES = [
    (0.3, "Can the network learn to fix this by itself? Same firmware, same weak motor. Only the weights change."),
    (7.0, "On the left, the old network that copied a hand-written rule. On the right, the network after learning in the simulator."),
    (15.9, "The old one drifts off in the gaps, and the firmware stops it."),
    (21.5, "The learned one drives faster through the gaps and steers harder at the edges, so it stays on the dots."),
    (34.3, "It learned by trial and error. Small changes to its one hundred and seven weights, keeping whatever drove further, on hundreds of random cars."),
    (43.5, "Clean runs went from seventy-seven to one hundred and four out of one hundred and twenty. On track shapes it never saw, from sixty-four to one hundred and one. Still sir's four-input design. Next, the real car."),
]
k = Kokoro(f"{mdir}/kokoro.onnx", f"{mdir}/voices.bin"); clips, t = [], 0.0
for start, text in LINES:
    a, sr = k.create(text, voice="af_heart", speed=1.0, lang="en-us")
    st = max(start, t + 0.3); clips.append((st, a)); t = st + len(a) / SR; print(f"{st:5.1f}-{t:5.1f} {text[:50]}")
vid = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]))
total = max(vid, t + 1.0); n = int(total * SR) + SR; mix = np.zeros(n, np.float32)
for st, a in clips: i = int(st * SR); mix[i:i + len(a)] += a
d = np.genfromtxt("new.csv", delimiter=",", names=True); ts = np.arange(n) / SR
pwm = np.zeros(n); msk = (ts >= 4) & (ts < 34); pwm[msk] = np.interp(ts[msk] - 4, d["t"], (d["dutyL"] + d["dutyR"]) / 2)
ph = 2 * np.pi * np.cumsum(70 + pwm * 0.55) / SR
mix += np.convolve((np.sin(ph) + .5 * np.sin(2 * ph)) * pwm / 255 * 0.04, np.ones(48) / 48, mode="same")
s0 = int(15.5 * SR)
for j, f in enumerate((880, 660)):
    seg = np.arange(int(.18 * SR)); i0 = s0 + j * int(.22 * SR); mix[i0:i0 + len(seg)] += .12 * np.sin(2 * np.pi * f * seg / SR) * np.hanning(len(seg))
mix /= max(1.0, np.abs(mix).max() / .95); sf.write("narration_learn.wav", mix[:int(total * SR)], SR)
pad = max(0.0, total - vid); vf = f"tpad=stop_mode=clone:stop_duration={pad:.2f}" if pad > 0 else "null"
subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", "narration_learn.wav", "-vf", vf, "-c:v", "libx264", "-crf", "20",
    "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "160k", "-shortest", dst])
print("done", total)
