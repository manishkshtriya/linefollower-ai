// Forward pass of the line follower network: 4 -> 7 -> 7 -> 2.
// Hidden layers use tanh, the output layer uses a sigmoid, so each output is 0.0 to 1.0.
#pragma once
#include <math.h>
#include "weights.h"

static inline void nn_forward(const float in[NN_IN], float out[NN_OUT]) {
  float h1[NN_H1], h2[NN_H2];
  for (int j = 0; j < NN_H1; j++) {
    float a = NN_B1[j];
    for (int i = 0; i < NN_IN; i++) a += NN_W1[j][i] * in[i];
    h1[j] = tanhf(a);
  }
  for (int j = 0; j < NN_H2; j++) {
    float a = NN_B2[j];
    for (int i = 0; i < NN_H1; i++) a += NN_W2[j][i] * h1[i];
    h2[j] = tanhf(a);
  }
  for (int j = 0; j < NN_OUT; j++) {
    float a = NN_B3[j];
    for (int i = 0; i < NN_H2; i++) a += NN_W3[j][i] * h2[i];
    out[j] = 1.0f / (1.0f + expf(-a));
  }
}
