"""Prints what a weights file does for all 16 sensor patterns. Usage: python3 patterns.py weights.txt [compare.txt]"""
import sys, numpy as np
def load(p):
    w = np.loadtxt(p); i = 0
    W1 = w[i:i+28].reshape(7, 4); i += 28; b1 = w[i:i+7]; i += 7
    W2 = w[i:i+49].reshape(7, 7); i += 49; b2 = w[i:i+7]; i += 7
    W3 = w[i:i+14].reshape(2, 7); i += 14; b3 = w[i:i+2]
    return lambda x: 1/(1+np.exp(-(W3 @ np.tanh(W2 @ np.tanh(W1 @ x + b1) + b2) + b3)))
fs = [load(p) for p in sys.argv[1:]]
print("pattern  " + "   ".join(f"{p.split('/')[-1]:>14}" for p in sys.argv[1:]))
for n in range(16):
    x = np.array([(n >> 3) & 1, (n >> 2) & 1, (n >> 1) & 1, n & 1], float)
    print(f"{''.join(str(int(v)) for v in x)}     " + "   ".join("L=%.2f R=%.2f" % tuple(f(x)) for f in fs))
