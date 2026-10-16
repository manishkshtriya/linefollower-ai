// Minimal Arduino API for running the real linefollower.ino on a PC.
// The simulator (hil_sim.cpp) defines these functions and connects them to a virtual car.
#pragma once
#include <cstdio>
#include <cstdarg>
#include <cstdint>
#include <cmath>

#define HIGH 1
#define LOW 0
#define INPUT 0
#define OUTPUT 1

unsigned long millis();
unsigned long micros();
void delay(unsigned long ms);
void pinMode(int pin, int mode);
void digitalWrite(int pin, int value);
int  digitalRead(int pin);
void ledcAttach(int pin, int freq, int bits);
void ledcWrite(int pin, int duty);

struct SerialPort {
  void begin(long) {}
  int printf(const char *fmt, ...) __attribute__((format(printf, 2, 3)));
};
extern SerialPort Serial;
