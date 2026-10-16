#!/bin/bash
# Scores the firmware on 12 hard scenarios (120 s each) for different sensor spacings.
# A scenario passes if the firmware never stops and the car never leaves the line.
cd "$(dirname "$0")"
g++ -O2 -std=c++17 hil_sim.cpp -o hil_sim || exit 1
for SP in ${SPACINGS:-12 16 20 25 30}; do
  pass=0; tot=0; line=""
  while read -r args; do
    r=$(./hil_sim --quiet --seconds 120 --spacing $SP $args)
    ok=$(echo "$r" | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(1 if (not d['firmware_stopped'] and d['off_track_events']==0) else 0)")
    pass=$((pass+ok)); tot=$((tot+1)); line="$line$ok"
  done <<'LIST'
--track mixed
--track dashed
--track dotted
--track mixed --gap 135
--track mixed --gap 189
--track mixed --gainL 0.92
--track mixed --gainR 0.92
--track mixed --gainL 0.85
--track mixed --gainR 0.85
--track dashed --gainR 0.92
--track dotted --gainL 0.92
--track mixed --noise 0.03 --seed 3
LIST
  echo "spacing=${SP}mm  passed $pass/$tot  [$line]"
done
