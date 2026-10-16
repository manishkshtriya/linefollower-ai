# Firmware-in-the-loop simulator

This runs the **real** car program, `firmware/linefollower/linefollower.ino`, unchanged on a PC.
A small Arduino layer (`arduino_shim.h`) answers the firmware's `digitalRead`, `digitalWrite`,
`ledcWrite` and `millis` calls from a virtual car instead of real pins:

- **Sensors:** four IR spots, 8 mm wide, over 19 mm black tape. A sensor reads 1 when at least half of its spot is on tape.
- **Motors:** TB6612FNG direction pins and standby are honoured. PWM below 60 does not move the wheel (stall),
  full PWM gives 450 mm/s, and the wheel speed follows the command with a 60 ms lag.
- **Car:** 81 mm between the wheels, sensors 70 mm ahead of the axle, 1 ms physics steps.
- **Faults you can add:** weak motor (`--gainL`, `--gainR`), low battery (`--batt`), wrong sensor reads (`--noise`).

It does not emulate the ESP32 chip itself (timing, interrupts, ADC), wheel slip, or uneven floors.
Those still need the real car.

## Run it

```bash
cd sim
g++ -O2 -std=c++17 hil_sim.cpp -o hil_sim
./hil_sim --track mixed --seconds 60            # prints a JSON summary
./hil_sim --track dotted --gainR 0.92 --log run.csv
./grid.sh                                       # 12 hard scenarios, several sensor spacings
python3 montecarlo.py 30 20                     # 30 random cars per track, 20 mm spacing
python3 render.py line_follower_sim.mp4         # makes the video (needs numpy, matplotlib, imageio-ffmpeg)
python3 narrate.py <kokoro dir> line_follower_sim.mp4 out.mp4   # adds voice-over and motor sound (kokoro-onnx)
```

Options: `--track mixed|solid|dashed|dotted`, `--gap <mm>`, `--spacing <mm>`, `--seconds`, `--noise`,
`--gainL`, `--gainR`, `--batt`, `--seed`, `--log file.csv`, `--mask file.pgm`, `--quiet`.

## What it found

(The tables below were made with the first, rule-copying weights. The learned weights in `learn/` do better; see `learn/README.md`.)

**Sensor spacing matters more than anything else.** With 19 mm tape and sensors 30 mm apart, a centred line
falls in the gap between the middle two sensors, so the car often reads `0000` even while it is on the line.
On dashed and dotted tape it then misses marks, and any difference between the two motors makes it drift off.

12 hard scenarios, 120 s each (pass = the firmware never stops and the car never leaves the line):

| Sensor spacing | Passed |
|---|---|
| 12 mm | 7 / 12 |
| 16 mm | 10 / 12 |
| 18 mm | 10 / 12 |
| **20 mm** | **11 / 12** |
| 22 mm | 7 / 12 |
| 25 mm | 5 / 12 |
| 30 mm | 5 / 12 |

With 20 mm spacing, 120 s per run:

| Scenario | Laps | Left the line | Mean error | Worst error |
|---|---|---|---|---|
| Mixed track | 8 | 0 | 1.9 mm | 18 mm |
| Dashed only | 8 | 0 | 3.9 mm | 21 mm |
| Dotted only | 8 | 0 | 7.5 mm | 31 mm |
| Mixed, 135 mm gaps | 8 | 0 | 4.0 mm | 31 mm |
| Mixed, 189 mm gaps | 0 | stopped at 8 s | | |
| Mixed, 3% wrong sensor reads | 8 | 0 | 2.6 mm | 27 mm |
| Right motor 8% weaker | 8 | 0 | 3.9 mm | 33 mm |
| Battery at 70% | 4 | 0 | 1.6 mm | 11 mm |

Random cars (each run gets a random motor mismatch with 6% spread, battery 75 to 100%, and 0 to 2% sensor noise), 60 s each:

| Track | 20 mm spacing | 30 mm spacing |
|---|---|---|
| Mixed | 30 / 30 clean | 28 / 30 |
| Dashed only | 25 / 30 | 12 / 30 |
| Dotted only | 22 / 30 | 6 / 30 |

Other changes tested:
- `LOST_STOP_MS` raised from 1500 to 3000 ms. At 1500 ms the car sometimes stopped on dotted tape while it was still on the line.
- Holding an average of recent steering while in a gap made things worse (0 / 12) and was not kept.

## Real ESP32 build

The firmware was also compiled with the official Arduino-ESP32 core 3.3.12 for an ESP32 DevKit. It builds and uses 283 KB
of flash (21%) and 22 KB of RAM (6%). That build caught one bug the PC test could not: the weight arrays were named
`B1`, `B2`, `B3`, which Arduino already defines as binary constants. They are now `NN_W1` ... `NN_B3`.
Booting the binary in Espressif's QEMU ESP32 emulator did not get past start-up (it is a known weak spot of the emulator
with Arduino core 3.x), so the closed-loop testing above is done with the PC simulator.

## Limits

All of this is simulation. The car has not been built. Expect to retune `MIN_DUTY`, the sensor height and the
sensor threshold on the real car, then log real driving and retrain.
