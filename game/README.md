# Be the AI: the line follower game

A desktop game. You drive the AI line follower car against its own neural network, the 107 weights that live in
`training/weights.json`. Same car, same 4 IR sensors, same weak motor. Hard mode hides the track, so you only
see the 4 sensor lamps, which is everything the network ever sees.

## Install and run (Mac)

1. Open **Terminal**.
2. Get the code, if you have not already:
   ```bash
   git clone https://github.com/manishkshtriya/linefollower-ai
   ```
   (Already cloned? Run `cd linefollower-ai && git pull` instead.)
3. Install the two things the game needs:
   ```bash
   python3 -m pip install pygame-ce numpy
   ```
4. Start the game:
   ```bash
   cd linefollower-ai/game
   python3 line_follower_game.py
   ```

If you see `font module not available` (new Python versions such as 3.14), the plain `pygame` package was built without
fonts. Swap it for `pygame-ce`, the maintained version with ready-made installers:
```bash
python3 -m pip uninstall -y pygame
python3 -m pip install pygame-ce
```

Shortcut: after step 2 you can double-click `game/play.command` in Finder. If macOS blocks it, right-click it, choose
**Open**, then **Open** again. Windows and Linux work the same way with `python` instead of `python3`.

## How to play

| | |
|---|---|
| **Goal** | Drive further than the AI in 60 seconds. |
| **Steer** | Hold **←** / **→** (or **A** / **D**). Let go to drive straight. |
| **Pause** | **P** or **ESC**. While paused, **Q** goes back to the menu. |
| **Camera** | **C** switches between the chase camera and the whole track. |
| **Menus** | Arrow keys and **ENTER**, or click with the mouse. |
| **Race again** | **R** on the results screen. |

**The sensor lamps** (right panel, under the minimap) are your car's 4 IR sensors, left to right. Red means that sensor is over tape.
Line under the left lamps: steer left. Under the right lamps: steer right.

**Gaps.** On dashed and dotted tape all 4 lamps go dark between marks. Keep going and you will reach the next mark.
If no lamp sees tape for 3 seconds the car stops itself, exactly like the real firmware, and you lose the line.
The car is put back after a short pause, which costs you distance.

**Weak motor.** From level 2 the right motor is weaker (4 to 8%), so "straight" pulls you to the right. The AI has
the same problem.

**Points and streak.** You score points for distance. Every 5 seconds on the line raises your multiplier by 0.5, up to x3. Losing the line resets it.

**The AI's brain.** The right panel shows the network live: 4 inputs, two layers of 7, 2 outputs. Blue lines push a neuron up, orange push it down.

**Stars.** 3 stars: you beat the AI. 2 stars: within 75% of it. 1 star: you finished.
Best scores are saved on your computer in `~/.be_the_ai_scores.json`.

## Modes

- **Race the AI**: you (yellow) against the network (blue), both visible.
- **Hard mode: sensors only**: the track is hidden; you get 4 big lamps. This is how the network drives.
- **Watch the AI drive**: only the network drives; its live output (left and right motor) is shown.

## Tracks

1. **Solid oval**: warm-up, equal motors.
2. **Dashed loops**: gaps between dashes.
3. **Dotted peanut**: small dots and a weaker right motor.
4. **The real test**: solid, dashed and dotted on a winding track, right motor 8% weaker.
5. **Your own track**: draw any closed loop with the mouse, then race on it.

## How it works

The car physics and sensors are the same as the simulator in `sim/hil_sim.cpp` and the firmware: 4 sensors 20 mm
apart, 70 mm ahead of the wheels, 8 mm sensor spots on 19 mm tape, a control step every 5 ms, PWM = 70 + output × 185,
motors that do not move below PWM 60 and react with a 60 ms lag. The AI car runs the learned network from `learn/`.
Your keys replace the network: left = (0.30, 0.95), right = (0.95, 0.30), nothing = (0.85, 0.85).

## Check it runs without a screen

```bash
SDL_VIDEODRIVER=dummy python3 line_follower_game.py --selftest
```
It clicks through every screen, plays one race with a simple driver and prints the result.
