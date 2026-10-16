"""Adds a voice-over and a quiet motor sound (driven by the logged PWM) to line_follower_sim.mp4.
Needs: pip install kokoro-onnx soundfile, plus kokoro.onnx and voices.bin from the kokoro-onnx releases.
Usage: python3 narrate.py <model dir> in.mp4 out.mp4"""
import sys, subprocess, numpy as np, soundfile as sf
from kokoro_onnx import Kokoro

mdir, src, dst = sys.argv[1:4]
SR = 24000
LINES = [  # (earliest start in seconds, text)
    (0.3, "This is the A I line follower car. The real E S P thirty-two firmware is running on a computer, driving a virtual car."),
    (7.5, "Four infrared sensors read the tape. The neural network turns them into two motor speeds."),
    (14.0, "The red dots are sensors that see the line. In the dashed and dotted parts, the sensors read zero between the marks, so the car simply keeps going straight."),
    (25.5, "Over this run, the car stays within about two millimetres of the line on average, and completes two laps."),
    (36.3, "Now a harder test. Real motors never match, so here the right motor is eight percent weaker."),
    (43.0, "On the left, the sensors are thirty millimetres apart. On the right, twenty."),
    (52.3, "With thirty millimetres, the line slips between the sensors. The car drifts off, and the firmware stops it safely."),
    (60.0, "With twenty millimetres, the same car keeps following the line."),
    (66.2, "So the build will use twenty millimetre sensor spacing. All of this is simulation. The next step is the real car."),
]
k = Kokoro(f"{mdir}/kokoro.onnx", f"{mdir}/voices.bin")
clips, t = [], 0.0
for start, text in LINES:
    a, sr = k.create(text, voice="af_heart", speed=1.0, lang="en-us"); assert sr == SR
    st = max(start, t + 0.3); clips.append((st, a)); t = st + len(a) / SR
    print(f"{st:5.1f}-{t:5.1f}  {text[:60]}")
vid = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src]))
total = max(vid, t + 1.0)
voice = np.zeros(int(total * SR) + SR, np.float32)
for st, a in clips:
    i = int(st * SR); voice[i:i + len(a)] += a

# motor sound: pitch and loudness follow the average PWM in the logs (clip A from 4 s, clip B from 39 s)
def duty_track(path, offset, seconds):
    d = np.genfromtxt(path, delimiter=",", names=True)
    tt = d["t"] + offset; pwm = (d["dutyL"] + d["dutyR"]) / 2
    return tt, pwm, offset + seconds
tA, pA, eA = duty_track("a.csv", 4.0, 32)
tB, pB, eB = duty_track("b2.csv", 39.0, 26)
n = len(voice); ts = np.arange(n) / SR
pwm = np.zeros(n)
for tt, pp, end in ((tA, pA, eA), (tB, pB, eB)):
    m = (ts >= tt[0]) & (ts < min(end, tt[-1]))
    pwm[m] = np.interp(ts[m], tt, pp)
freq = 70 + pwm * 0.55
phase = 2 * np.pi * np.cumsum(freq) / SR
hum = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase)) * (pwm / 255) * 0.045
hum = np.convolve(hum, np.ones(48) / 48, mode="same")  # soften
# short two-tone alert when the 30 mm car's firmware stops (51.8 s)
al = np.zeros(n); s0 = int(51.8 * SR)
for j, f in enumerate((880, 660)):
    seg = np.arange(int(0.18 * SR)); i0 = s0 + j * int(0.22 * SR)
    al[i0:i0 + len(seg)] = 0.12 * np.sin(2 * np.pi * f * seg / SR) * np.hanning(len(seg))
mix = voice * 0.95 + hum + al
mix = mix / max(1.0, np.abs(mix).max() / 0.95)
sf.write("narration.wav", mix[: int(total * SR)], SR)
pad = max(0.0, total - vid)
vf = f"tpad=stop_mode=clone:stop_duration={pad:.2f}" if pad > 0 else "null"
subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", src, "-i", "narration.wav", "-vf", vf, "-c:v", "libx264", "-crf", "20",
                       "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", dst])
print("video", vid, "-> total", total)
