# The network learns to drive (no teacher)

The first network copied a steering rule written by hand. Here it learns by itself, inside the simulator.

`learn.cpp` runs an evolution strategy: each round it tries 24 small random changes to the 107 weights on 16 random
cars, and moves the weights toward the changes that drove further without losing the line. Every car is different:
each motor's strength varies (6% spread), the battery is 75 to 100%, the sensors read wrong 0 to 2% of the time, and
the tape is mixed, dashed or dotted on tracks that turn left and right. Car, sensors and control loop match
`sim/hil_sim.cpp` and the firmware. The network keeps sir's design: 4 inputs, two hidden layers of 7, 2 outputs.

```bash
g++ -O2 -std=c++17 -pthread learn.cpp -o learn
./learn train init4.txt 4 80 learned4.txt > log4.csv   # about 2 minutes on 2 cores
./learn eval learned4.txt 4                           # 240 random cars, 30 s each
python3 patterns.py init4.txt learned4.txt            # what changed, pattern by pattern
python3 export.py learned4.txt                        # writes the firmware weights.h and training/weights.json
```

## Results

Clean runs (never left the line, firmware never stopped), 40 random cars per row, 30 s each:

| Tracks | Tape | Before (rule copy) | After (learned) |
|---|---|---|---|
| Training shapes | mixed | 24 | 33 |
| Training shapes | dashed | 31 | 39 |
| Training shapes | dotted | 22 | 32 |
| New shapes, never trained on | mixed | 36 | 39 |
| New shapes, never trained on | dashed | 15 | 33 |
| New shapes, never trained on | dotted | 13 | 29 |
| **Total** | | **141 / 240** | **205 / 240** |

Checked again on the **real firmware** in `sim/hil_sim` (90 random cars, 60 s, sensors 20 mm apart):
mixed 30 → 30, dashed 25 → 30, dotted 22 → 27 clean runs. The case that failed before (dotted tape, right motor 8% weaker)
now completes 4 laps in 60 s.

What it learned (from `patterns.py`): in a gap (`0000`) it now drives at 0.95 instead of 0.65, so it spends less time
blind and drifts less; and it steers harder when only an outer sensor sees the line.

Also tried: giving the network its last two outputs as extra inputs (6 inputs). It scored about the same, so the
4-input version was kept. Longer training (250 more rounds) did not improve the selection score either.

One regression to know about: on the mixed oval with 135 mm gaps the learned weights lost the line once in 60 s,
which the old weights did not.

All of this is simulation. Next: the real car, then retrain with logged real driving.
