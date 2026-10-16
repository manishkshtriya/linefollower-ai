# Test the real firmware in Wokwi (free, in the browser)

Wokwi is a ready-made ESP32 simulator. It compiles and runs the exact `linefollower.ino`, so you can check the
code before touching the car.

- 4 slide switches are the 4 IR sensors (S1 far left to S4 far right). Slide one to the right = that sensor sees the line.
- The red LED is the left motor PWM, the green LED is the right motor PWM. Brighter = faster.
- The Serial Monitor prints what the car decides, for example `0110  L=0.80 R=0.80`.

## Steps

1. Open https://wokwi.com, sign in, and start a new **ESP32** project (Arduino).
2. Replace `sketch.ino` with the contents of `firmware/linefollower/linefollower.ino`.
3. Use the tab menu to add two files, `nn.h` and `weights.h`, and paste in the files from `firmware/linefollower/`.
4. Open the `diagram.json` tab and replace it with `wokwi/diagram.json` from this folder.
5. Press the green Play button.

## What you should see

| Switches (S1 S2 S3 S4) | Serial Monitor | LEDs |
|---|---|---|
| off on on off (line in the middle) | `0110  L=0.80 R=0.80` | both equally bright: go straight |
| on on off off (line to the left) | `1100  L=0.38 R=0.98` | green brighter: turn left |
| off off on on (line to the right) | `0011  L=0.98 R=0.38` | red brighter: turn right |
| all off for more than 3 seconds | printing stops | both LEDs go off: firmware stopped, line lost |

If the numbers match the table, the firmware is doing what the simulations showed. The next step is the sensor test on the real car.
