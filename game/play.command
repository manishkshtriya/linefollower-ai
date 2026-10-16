#!/bin/bash
# Double-click on a Mac (or run ./play.command) to install what the game needs and start it.
cd "$(dirname "$0")"
python3 -m pip uninstall -y -q pygame 2>/dev/null; python3 -m pip install --user --quiet pygame-ce numpy
python3 line_follower_game.py
