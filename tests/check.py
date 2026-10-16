#!/usr/bin/env python3
"""Check that the C forward pass in nn.h gives the same answers as the Python network.

Run from the linefollower-ai folder after training:
  python3 tests/check.py
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FW = os.path.join(ROOT, "firmware", "linefollower")
WJSON = os.path.join(ROOT, "training", "weights.json")

C_SRC = r"""
#include <stdio.h>
#include "nn.h"
int main(void) {
  for (int p = 0; p < 16; p++) {
    float in[NN_IN] = {(p >> 3) & 1, (p >> 2) & 1, (p >> 1) & 1, p & 1}, out[NN_OUT];
    nn_forward(in, out);
    printf("%.7f %.7f\n", out[0], out[1]);
  }
  return 0;
}
"""


def main():
    with open(WJSON) as f:
        d = json.load(f)
    W = [np.array(w) for w in d["W"]]
    b = [np.array(x) for x in d["b"]]
    X = np.array([[(p >> 3) & 1, (p >> 2) & 1, (p >> 1) & 1, p & 1] for p in range(16)], dtype=float)
    a = X
    for l in range(len(W)):
        z = a @ W[l].T + b[l]
        a = 1 / (1 + np.exp(-z)) if l == len(W) - 1 else np.tanh(z)

    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "t.c")
        exe = os.path.join(tmp, "t")
        with open(src, "w") as f:
            f.write(C_SRC)
        subprocess.run(["gcc", "-O2", "-I", FW, src, "-o", exe, "-lm"], check=True)
        out = subprocess.run([exe], check=True, capture_output=True, text=True).stdout.split()
    c_out = np.array(out, dtype=float).reshape(16, 2)
    diff = float(np.abs(c_out - a).max())
    print(f"largest difference between C and Python outputs: {diff:.2e}")
    if diff > 1e-4:
        sys.exit("MISMATCH: the C code does not match the Python network")
    print("OK: the C forward pass matches")


if __name__ == "__main__":
    main()
