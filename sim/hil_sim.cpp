// Hardware-in-the-loop style simulation: the real firmware (linefollower.ino) runs unchanged on a PC,
// and a virtual car (motors, wheels, sensors, tape track) answers its pin reads and PWM writes.
//
// Build:  g++ -O2 -std=c++17 hil_sim.cpp -o hil_sim
// Run:    ./hil_sim --track mixed --seconds 60 --log run.csv --mask mask.pgm
#include "arduino_shim.h"
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <random>
#include <algorithm>

// ---------------- virtual car and world (units: mm, seconds, radians; y up) ----------------
struct Cfg {
  std::string track = "mixed";   // mixed | solid | dashed | dotted
  double gap = 81;               // gap between marks, mm
  double seconds = 60;
  double noise = 0;              // chance that a sensor read is wrong
  double gainL = 1, gainR = 1;   // motor strength (1.0 = nominal)
  double batt = 1;               // battery factor, scales the effective PWM
  double vmax = 450;             // wheel speed at full PWM, mm/s
  double stall = 60;             // PWM below this does not move the motor
  double tau = 0.06;             // motor speed time constant, s
  unsigned seed = 1;
  std::string logfile, maskfile;
  bool quiet = false;
} cfg;

static const double WHEELBASE = 81, SENSOR_AHEAD = 70, TAPE_W = 19;
static double SENSOR_SPACING = 20;  // mm between neighbouring sensors, set with --spacing
static const double EA = 891, EB = 553;  // ellipse semi-axes, mm
static const int MW = 1900, MH = 1200, MOX = 950, MOY = 600;  // mask size and origin, 1 mm per cell
static std::vector<unsigned char> mask(MW * MH, 0);
static std::vector<double> cx_, cy_;  // centreline points for cross-track error

struct Car { double x, y, th, vl, vr; } car;
static int pwmDuty[40];         // indexed by pin
static int pinState[40];
static unsigned long sim_us = 0;
static std::mt19937 rng;
static int sensorPin[4] = {34, 35, 32, 33};
SerialPort Serial;
static int serialLines = 0;

// ---------------- Arduino API implemented on the virtual car ----------------
unsigned long millis() { return sim_us / 1000; }
unsigned long micros() { return sim_us; }
void pinMode(int, int) {}
void digitalWrite(int pin, int v) { if (pin >= 0 && pin < 40) pinState[pin] = v; }
void ledcAttach(int, int, int) {}
void ledcWrite(int pin, int duty) { if (pin >= 0 && pin < 40) pwmDuty[pin] = duty < 0 ? 0 : duty > 255 ? 255 : duty; }
int SerialPort::printf(const char *fmt, ...) {
  if (cfg.quiet || serialLines > 12) return 0;
  serialLines++;
  va_list a; va_start(a, fmt); int n = vprintf(fmt, a); va_end(a); return n;
}

static bool tapeAt(double x, double y) {
  int ix = (int)std::lround(x) + MOX, iy = (int)std::lround(y) + MOY;
  return ix >= 0 && iy >= 0 && ix < MW && iy < MH && mask[iy * MW + ix];
}
static bool sensorSees(int i) {
  double lat = (1.5 - i) * SENSOR_SPACING;  // i=0 far left (+45), i=3 far right (-45)
  double fx = std::cos(car.th), fy = std::sin(car.th), lx = -std::sin(car.th), ly = std::cos(car.th);
  double px = car.x + fx * SENSOR_AHEAD + lx * lat, py = car.y + fy * SENSOR_AHEAD + ly * lat;
  int hit = tapeAt(px, py), n = 1;               // sensor spot is about 8 mm wide
  for (int k = 0; k < 8; k++) { double a = k * M_PI / 4; hit += tapeAt(px + 4 * std::cos(a), py + 4 * std::sin(a)); n++; }
  bool on = hit * 2 >= n;
  if (cfg.noise > 0 && std::uniform_real_distribution<double>(0, 1)(rng) < cfg.noise) on = !on;
  return on;
}
int digitalRead(int pin) {
  for (int i = 0; i < 4; i++) if (sensorPin[i] == pin) return sensorSees(i) ? HIGH : LOW;  // module outputs HIGH over the line
  return LOW;
}

// ---------------- physics ----------------
static double motorTarget(int pwm, int in1, int in2, double gain) {
  if (!pinState[23]) return 0;                                  // STBY low
  double d = pwmDuty[pwm] * cfg.batt;
  double mag = d <= cfg.stall ? 0 : (d - cfg.stall) / (255.0 - cfg.stall);
  int dir = (pinState[in1] && !pinState[in2]) ? 1 : (!pinState[in1] && pinState[in2]) ? -1 : 0;
  return dir * mag * cfg.vmax * gain;
}
static void physicsStep(double dt) {
  double tl = motorTarget(25, 26, 27, cfg.gainL), tr = motorTarget(4, 16, 17, cfg.gainR);
  car.vl += (tl - car.vl) * dt / cfg.tau;
  car.vr += (tr - car.vr) * dt / cfg.tau;
  double v = (car.vl + car.vr) / 2, w = (car.vr - car.vl) / WHEELBASE;
  car.th += w * dt; car.x += std::cos(car.th) * v * dt; car.y += std::sin(car.th) * v * dt;
  sim_us += (unsigned long)std::lround(dt * 1e6);
}
void delay(unsigned long ms) { for (unsigned long i = 0; i < ms; i++) physicsStep(0.001); }

// ---------------- track ----------------
static void buildTrack() {
  struct Seg { double a, b; const char *st; };
  const Seg segs[] = {{0, 1.2, "solid"}, {1.2, 2.6, "dashed"}, {2.6, 3.9, "solid"}, {3.9, 5.3, "dotted"}, {5.3, 6.2832, "solid"}};
  const int N = 40000; double s = 0, px = EA, py = 0;
  for (int i = 0; i <= N; i++) {
    double t = i * 2 * M_PI / N, x = EA * std::cos(t), y = EB * std::sin(t);
    if (i) s += std::hypot(x - px, y - py);
    px = x; py = y;
    if (i % 10 == 0) { cx_.push_back(x); cy_.push_back(y); }
    std::string st = cfg.track;
    if (st == "mixed") { st = "solid"; for (auto &g : segs) if (t >= g.a && t < g.b) { st = g.st; break; } }
    bool on = true;
    if (st == "dashed") on = std::fmod(s, 81 + cfg.gap) < 81;
    else if (st == "dotted") on = std::fmod(s, TAPE_W + cfg.gap) < TAPE_W;
    if (!on) continue;
    int r = (int)(TAPE_W / 2);
    for (int dy = -r; dy <= r; dy++) for (int dx = -r; dx <= r; dx++) if (dx * dx + dy * dy <= (TAPE_W / 2) * (TAPE_W / 2)) {
      int ix = (int)std::lround(x) + dx + MOX, iy = (int)std::lround(y) + dy + MOY;
      if (ix >= 0 && iy >= 0 && ix < MW && iy < MH) mask[iy * MW + ix] = 1;
    }
  }
}
static double crossTrack(double x, double y) {
  double best = 1e18;
  for (size_t i = 0; i < cx_.size(); i++) { double d = (cx_[i] - x) * (cx_[i] - x) + (cy_[i] - y) * (cy_[i] - y); if (d < best) best = d; }
  return std::sqrt(best);
}

// ---------------- the real firmware, included unchanged ----------------
#include "../firmware/linefollower/linefollower.ino"

int main(int argc, char **argv) {
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i]; auto nx = [&]() { return std::string(i + 1 < argc ? argv[++i] : ""); };
    if (a == "--track") cfg.track = nx(); else if (a == "--gap") cfg.gap = atof(nx().c_str());
    else if (a == "--seconds") cfg.seconds = atof(nx().c_str()); else if (a == "--noise") cfg.noise = atof(nx().c_str());
    else if (a == "--gainL") cfg.gainL = atof(nx().c_str()); else if (a == "--gainR") cfg.gainR = atof(nx().c_str());
    else if (a == "--batt") cfg.batt = atof(nx().c_str()); else if (a == "--log") cfg.logfile = nx();
    else if (a == "--mask") cfg.maskfile = nx(); else if (a == "--seed") cfg.seed = atoi(nx().c_str());
    else if (a == "--spacing") SENSOR_SPACING = atof(nx().c_str());
    else if (a == "--quiet") cfg.quiet = true;
  }
  rng.seed(cfg.seed);
  buildTrack();
  if (!cfg.maskfile.empty()) {
    FILE *m = fopen(cfg.maskfile.c_str(), "wb"); fprintf(m, "P5\n%d %d\n255\n", MW, MH);
    for (int y = MH - 1; y >= 0; y--) for (int x = 0; x < MW; x++) fputc(mask[y * MW + x] ? 0 : 255, m);
    fclose(m);
  }
  double t0 = 0.02;
  car.x = EA * std::cos(t0); car.y = EB * std::sin(t0);
  car.th = std::atan2(EB * std::cos(t0), -EA * std::sin(t0)); car.vl = car.vr = 0;
  FILE *lg = cfg.logfile.empty() ? nullptr : fopen(cfg.logfile.c_str(), "w");
  if (lg) fprintf(lg, "t,x,y,th,s0,s1,s2,s3,dutyL,dutyR,vl,vr,cte,laps\n");

  setup();                                          // real setup(): pins, PWM, 1 s delay
  double tStart = sim_us / 1e6, ang = std::atan2(car.y / EB, car.x / EA), acc = 0, sumCte = 0, maxCte = 0, onLineT = 0;
  int laps = 0, offEvents = 0, steps = 0, logN = 0; bool off = false, stopped = false; double stopT = -1, travelled = 0;
  while ((sim_us / 1e6 - tStart) < cfg.seconds) {
    double px = car.x, py = car.y;
    physicsStep(0.001);
    travelled += std::hypot(car.x - px, car.y - py);
    loop();                                         // real loop(): reads sensors, runs the network, drives the motors
    steps++;
    double bx = car.x + std::cos(car.th) * SENSOR_AHEAD, by = car.y + std::sin(car.th) * SENSOR_AHEAD;
    if (steps % 5 == 0) {
      double cte = crossTrack(bx, by); sumCte += cte; logN++; maxCte = std::max(maxCte, cte);
      if (cte < 15) onLineT += 0.005;
      if (!off && cte > 60) { off = true; offEvents++; } else if (off && cte < 30) off = false;
      double a2 = std::atan2(car.y / EB, car.x / EA), d = a2 - ang;
      if (d > M_PI) d -= 2 * M_PI;
      if (d < -M_PI) d += 2 * M_PI;
      acc += d; ang = a2;
      if (acc >= 2 * M_PI) { laps++; acc -= 2 * M_PI; }
      if (steps % 20 == 0 && lg) {
        int b[4]; for (int i = 0; i < 4; i++) { double lat = (1.5 - i) * SENSOR_SPACING; double lx = -std::sin(car.th), ly = std::cos(car.th);
          b[i] = tapeAt(bx + lx * lat, by + ly * lat); }
        fprintf(lg, "%.3f,%.1f,%.1f,%.4f,%d,%d,%d,%d,%d,%d,%.1f,%.1f,%.1f,%d\n", sim_us / 1e6 - tStart, car.x, car.y, car.th,
                b[0], b[1], b[2], b[3], pwmDuty[PWMA], pwmDuty[PWMB], car.vl, car.vr, cte, laps);
      }
    }
    if (!stopped && pwmDuty[PWMA] == 0 && pwmDuty[PWMB] == 0 && (sim_us / 1e6 - tStart) > 2.0 && std::fabs(car.vl) < 1 && std::fabs(car.vr) < 1) {
      stopped = true; stopT = sim_us / 1e6 - tStart; break;  // firmware gave up: line lost for too long
    }
  }
  if (lg) fclose(lg);
  double T = sim_us / 1e6 - tStart;
  printf("{\"track\":\"%s\",\"gap_mm\":%.0f,\"noise\":%.3f,\"gainL\":%.2f,\"gainR\":%.2f,\"batt\":%.2f,\"seconds\":%.1f,"
         "\"laps\":%d,\"off_track_events\":%d,\"firmware_stopped\":%s,\"stop_time\":%.1f,\"mean_cte_mm\":%.1f,\"max_cte_mm\":%.1f,"
         "\"on_line_pct\":%.1f,\"distance_m\":%.2f}\n",
         cfg.track.c_str(), cfg.gap, cfg.noise, cfg.gainL, cfg.gainR, cfg.batt, T, laps, offEvents, stopped ? "true" : "false", stopT,
         sumCte / std::max(1, logN), maxCte, 100 * onLineT / std::max(0.001, T), travelled / 1000);
  return 0;
}
