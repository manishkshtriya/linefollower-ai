#!/bin/bash
# Runs the real firmware against a set of scenarios. Each run is 120 s of simulated time.
cd "$(dirname "$0")"; g++ -O2 -std=c++17 hil_sim.cpp -o hil_sim || exit 1
run() { ./hil_sim --quiet --seconds 120 "$@"; }
run --track mixed
run --track solid
run --track dashed
run --track dotted
run --track mixed --gap 135
run --track mixed --gap 189
run --track mixed --noise 0.01 --seed 3
run --track mixed --noise 0.03 --seed 3
run --track mixed --gainL 0.92
run --track mixed --gainL 0.85 --gainR 1.0
run --track mixed --batt 0.85
run --track mixed --batt 0.7
