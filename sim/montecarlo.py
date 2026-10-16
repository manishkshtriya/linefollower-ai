"""Random trials: every run gets a different motor mismatch, battery level and sensor noise.
Usage: python3 montecarlo.py [runs_per_track] [spacing_mm]"""
import json, random, subprocess, sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
sp = sys.argv[2] if len(sys.argv) > 2 else "20"
random.seed(7)
for track in ["mixed", "dashed", "dotted"]:
    ok = 0; stops = 0; offs = 0; cte = []
    for i in range(n):
        gl, gr = random.gauss(1, 0.06), random.gauss(1, 0.06)
        batt = random.uniform(0.75, 1.0); noise = random.choice([0, 0.005, 0.02])
        r = json.loads(subprocess.check_output(["./hil_sim", "--quiet", "--seconds", "60", "--track", track, "--spacing", sp,
            "--gainL", f"{gl:.3f}", "--gainR", f"{gr:.3f}", "--batt", f"{batt:.3f}", "--noise", str(noise), "--seed", str(i)]))
        good = (not r["firmware_stopped"]) and r["off_track_events"] == 0
        ok += good; stops += r["firmware_stopped"]; offs += r["off_track_events"] > 0; cte.append(r["mean_cte_mm"])
    print(f"{track:7} spacing {sp} mm: {ok}/{n} clean runs, {stops} firmware stops, {offs} runs left the line, mean cross-track error {sum(cte)/len(cte):.1f} mm")
