// learn.cpp: the network learns to drive inside the simulator (no teacher rule).
// An evolution strategy tries small random changes to the weights, keeps the direction that makes the car
// go further without losing the line, and repeats. Training uses many random cars (motor mismatch, battery,
// sensor noise) on solid, dashed and dotted tape, on tracks that turn left and right.
//
// Car, sensor and motor model match sim/hil_sim.cpp, and the control loop matches linefollower.ino
// (5 ms steps, PWM = 70 + out * 185, stop after 3 s without the line).
//
// Build: g++ -O2 -std=c++17 -pthread learn.cpp -o learn
// Train: ./learn train <init.txt> <nin> <generations> <out.txt>
// Test:  ./learn eval <weights.txt> <nin> [spacing_mm]
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <cstring>
#include <string>
#include <vector>
#include <random>
#include <thread>
#include <algorithm>
#include <numeric>
using namespace std;

static const int MW = 1900, MH = 1200, MOX = 950, MOY = 600, DG = 4, DW = MW / DG, DH = MH / DG;
static const double WHEELBASE = 81, AHEAD = 70, TAPE = 19, VMAX = 450, STALL = 60, TAU = 0.06;
static const int MIN_DUTY = 70, MAX_DUTY = 255;
static double SPACING = 20;

struct Shape {                 // one closed track centreline
  string name; vector<double> x, y, s; double L = 0;
  vector<float> dist; vector<int> near;   // coarse grid: distance to centreline and nearest point index
};
struct Track { const Shape *sh; string style; double gap; vector<unsigned char> mask; };

static Shape makeShape(const string &name, int kind, bool cw) {
  Shape S; S.name = name + (cw ? " (right turns)" : " (left turns)");
  const int N = 6000;
  for (int i = 0; i < N; i++) {
    double t = 2 * M_PI * i / N, x, y;
    if (kind == 0) { x = 891 * cos(t); y = 553 * sin(t); }                       // oval
    else { double R, e; int k;
      if (kind == 1) { R = 480; e = 0.18; k = 3; } else if (kind == 2) { R = 500; e = 0.05; k = 4; } else { R = 455; e = 0.28; k = 2; }
      double r = R * (1 + e * cos(k * t)); x = r * cos(t) * (kind == 3 ? 1.6 : 1.0); y = r * sin(t); }
    S.x.push_back(x); S.y.push_back(y);
  }
  if (cw) { reverse(S.x.begin(), S.x.end()); reverse(S.y.begin(), S.y.end()); }
  S.s.assign(N, 0);
  for (int i = 1; i < N; i++) S.s[i] = S.s[i - 1] + hypot(S.x[i] - S.x[i - 1], S.y[i] - S.y[i - 1]);
  S.L = S.s[N - 1] + hypot(S.x[0] - S.x[N - 1], S.y[0] - S.y[N - 1]);
  S.dist.assign(DW * DH, 1e9); S.near.assign(DW * DH, 0);
  for (int gy = 0; gy < DH; gy++) for (int gx = 0; gx < DW; gx++) {
    double cx = gx * DG - MOX + DG / 2.0, cy = gy * DG - MOY + DG / 2.0, best = 1e18; int bi = 0;
    for (int i = 0; i < N; i += 4) { double d = (S.x[i] - cx) * (S.x[i] - cx) + (S.y[i] - cy) * (S.y[i] - cy); if (d < best) { best = d; bi = i; } }
    S.dist[gy * DW + gx] = (float)sqrt(best); S.near[gy * DW + gx] = bi;
  }
  return S;
}
static Track makeTrack(const Shape *S, const string &style, double gap) {
  Track T; T.sh = S; T.style = style; T.gap = gap; T.mask.assign(MW * MH, 0);
  const double segs[5][2] = {{0, .2}, {.2, .42}, {.42, .6}, {.6, .82}, {.82, 1.01}};
  const char *names[5] = {"solid", "dashed", "solid", "dotted", "solid"};
  int r = (int)(TAPE / 2);
  for (size_t i = 0; i < S->x.size(); i++) {
    double f = S->s[i] / S->L; string st = style;
    if (st == "mixed") for (int k = 0; k < 5; k++) if (f >= segs[k][0] && f < segs[k][1]) { st = names[k]; break; }
    bool on = true;
    if (st == "dashed") on = fmod(S->s[i], 81 + gap) < 81; else if (st == "dotted") on = fmod(S->s[i], TAPE + gap) < TAPE;
    if (!on) continue;
    for (int dy = -r; dy <= r; dy++) for (int dx = -r; dx <= r; dx++) if (dx * dx + dy * dy <= (TAPE / 2) * (TAPE / 2)) {
      int ix = (int)lround(S->x[i]) + dx + MOX, iy = (int)lround(S->y[i]) + dy + MOY;
      if (ix >= 0 && iy >= 0 && ix < MW && iy < MH) T.mask[iy * MW + ix] = 1;
    }
  }
  return T;
}

struct Scn { int track; double gL, gR, batt, noise, lat0, head0, startFrac; unsigned seed; };
struct Result { double progress = 0, meanErr = 0; bool off = false, stopped = false; };

struct Net {
  int nin; vector<float> w;   // order: W1[7][nin], b1[7], W2[7][7], b2[7], W3[2][7], b3[2]
  static int size(int nin) { return 7 * nin + 7 + 49 + 7 + 14 + 2; }
  void forward(const float *in, float *out) const {
    const float *p = w.data(); float h1[7], h2[7];
    for (int j = 0; j < 7; j++) { float a = p[7 * nin + j]; for (int i = 0; i < nin; i++) a += p[j * nin + i] * in[i]; h1[j] = tanhf(a); }
    p += 7 * nin + 7;
    for (int j = 0; j < 7; j++) { float a = p[49 + j]; for (int i = 0; i < 7; i++) a += p[j * 7 + i] * h1[i]; h2[j] = tanhf(a); }
    p += 56;
    for (int j = 0; j < 2; j++) { float a = p[14 + j]; for (int i = 0; i < 7; i++) a += p[j * 7 + i] * h2[i]; out[j] = 1.f / (1.f + expf(-a)); }
  }
};

static Result episode(const Track &T, const Scn &c, const Net &net, double seconds) {
  const Shape &S = *T.sh; mt19937 rng(c.seed); uniform_real_distribution<double> U(0, 1);
  int i0 = (int)(c.startFrac * S.x.size()) % S.x.size();
  // start on tape: move forward to the next point that has tape under it
  for (int k = 0; k < (int)S.x.size(); k++) { int i = (i0 + k) % S.x.size(); int ix = (int)lround(S.x[i]) + MOX, iy = (int)lround(S.y[i]) + MOY; if (T.mask[iy * MW + ix]) { i0 = i; break; } }
  int i1 = (i0 + 3) % S.x.size();
  double th = atan2(S.y[i1] - S.y[i0], S.x[i1] - S.x[i0]) + c.head0;
  double x = S.x[i0] - sin(th) * c.lat0, y = S.y[i0] + cos(th) * c.lat0, vl = 0, vr = 0;
  int dutyL = 0, dutyR = 0; float prev[2] = {0.65f, 0.65f};
  double lastSeen = 0, prog = 0, errSum = 0; int errN = 0, lastIdx = i0; Result R;
  const int steps = (int)(seconds * 1000);
  auto tape = [&](double px, double py) { int ix = (int)lround(px) + MOX, iy = (int)lround(py) + MOY;
    return ix >= 0 && iy >= 0 && ix < MW && iy < MH && T.mask[iy * MW + ix]; };
  for (int ms = 0; ms < steps; ms++) {
    if (ms % 5 == 0) {   // the firmware's control step
      float in[8]; int any = 0;
      double fx = cos(th), fy = sin(th), lx = -sin(th), ly = cos(th);
      for (int i = 0; i < 4; i++) {
        double lat = (1.5 - i) * SPACING, px = x + fx * AHEAD + lx * lat, py = y + fy * AHEAD + ly * lat;
        int hit = tape(px, py), n = 1;
        for (int k = 0; k < 8; k++) { double a = k * M_PI / 4; hit += tape(px + 4 * cos(a), py + 4 * sin(a)); n++; }
        bool on = hit * 2 >= n; if (c.noise > 0 && U(rng) < c.noise) on = !on;
        in[i] = on; any |= on;
      }
      if (any) lastSeen = ms;
      if (ms - lastSeen > 3000) { R.stopped = true; break; }
      if (net.nin > 4) { in[4] = prev[0]; in[5] = prev[1]; }
      float out[2]; net.forward(in, out); prev[0] = out[0]; prev[1] = out[1];
      dutyL = out[0] >= 0.05f ? MIN_DUTY + (int)(out[0] * (MAX_DUTY - MIN_DUTY)) : 0;
      dutyR = out[1] >= 0.05f ? MIN_DUTY + (int)(out[1] * (MAX_DUTY - MIN_DUTY)) : 0;
    }
    auto target = [&](int d, double g) { double e = d * c.batt; return e <= STALL ? 0.0 : (e - STALL) / (255.0 - STALL) * VMAX * g; };
    vl += (target(dutyL, c.gL) - vl) * 0.001 / TAU; vr += (target(dutyR, c.gR) - vr) * 0.001 / TAU;
    double v = (vl + vr) / 2; th += (vr - vl) / WHEELBASE * 0.001; x += cos(th) * v * 0.001; y += sin(th) * v * 0.001;
    if (ms % 20 == 0) {
      int gx = (int)((x + MOX) / DG), gy = (int)((y + MOY) / DG);
      if (gx < 0 || gy < 0 || gx >= DW || gy >= DH) { R.off = true; break; }
      double d = S.dist[gy * DW + gx]; int idx = S.near[gy * DW + gx];
      double ds = S.s[idx] - S.s[lastIdx]; if (ds > S.L / 2) ds -= S.L; if (ds < -S.L / 2) ds += S.L;
      prog += ds; lastIdx = idx; errSum += d; errN++;
      if (d > 70) { R.off = true; break; }
    }
  }
  R.progress = prog; R.meanErr = errN ? errSum / errN : 0; return R;
}

// ---------------- tracks and scenario sampling ----------------
static vector<Shape> shapes; static vector<Track> tracks; static vector<int> trainTracks, testTracks;
static void buildAll(double gap) {
  // training shapes: oval and three-lobe, both directions. Test-only shapes: square-ish and peanut, never seen in training.
  shapes.push_back(makeShape("oval", 0, false)); shapes.push_back(makeShape("oval", 0, true));
  shapes.push_back(makeShape("three-lobe", 1, false)); shapes.push_back(makeShape("three-lobe", 1, true));
  shapes.push_back(makeShape("square", 2, false)); shapes.push_back(makeShape("square", 2, true));
  shapes.push_back(makeShape("peanut", 3, false)); shapes.push_back(makeShape("peanut", 3, true));
  const char *styles[3] = {"mixed", "dashed", "dotted"};
  for (size_t s = 0; s < shapes.size(); s++) for (int k = 0; k < 3; k++) {
    tracks.push_back(makeTrack(&shapes[s], styles[k], gap));
    (s < 4 ? trainTracks : testTracks).push_back((int)tracks.size() - 1);
  }
}
static Scn sample(mt19937 &g, const vector<int> &pool) {
  normal_distribution<double> N(0, 1); uniform_real_distribution<double> U(0, 1);
  Scn c; c.track = pool[g() % pool.size()];
  c.gL = 1 + 0.06 * N(g); c.gR = 1 + 0.06 * N(g); c.batt = 0.75 + 0.25 * U(g);
  double r = U(g); c.noise = r < 0.4 ? 0 : r < 0.8 ? 0.005 : 0.02;
  c.lat0 = 6 * N(g); c.head0 = 0.08 * N(g); c.startFrac = U(g); c.seed = g(); return c;
}

static vector<double> evalMany(const vector<Net> &nets, const vector<Scn> &sc, double seconds, vector<vector<Result>> *all = nullptr) {
  int nt = max(1u, thread::hardware_concurrency());
  vector<double> fit(nets.size(), 0); if (all) all->assign(nets.size(), vector<Result>(sc.size()));
  vector<thread> th; size_t jobs = nets.size() * sc.size(); vector<double> part(jobs);
  for (int t = 0; t < nt; t++) th.emplace_back([&, t] {
    for (size_t j = t; j < jobs; j += nt) { size_t n = j / sc.size(), s = j % sc.size();
      Result R = episode(tracks[sc[s].track], sc[s], nets[n], seconds);
      part[j] = R.progress / (seconds * 300.0) - 0.002 * R.meanErr; if (all) (*all)[n][s] = R; }
  });
  for (auto &x : th) x.join();
  for (size_t j = 0; j < jobs; j++) fit[j / sc.size()] += part[j] / sc.size();
  return fit;
}

static vector<float> loadW(const char *path, int nin) {
  vector<float> w; FILE *f = fopen(path, "r"); double v; while (f && fscanf(f, "%lf", &v) == 1) w.push_back((float)v); if (f) fclose(f);
  if ((int)w.size() != Net::size(nin)) { fprintf(stderr, "expected %d weights in %s, got %zu\n", Net::size(nin), path, w.size()); exit(1); }
  return w;
}
static void saveW(const char *path, const vector<float> &w) { FILE *f = fopen(path, "w"); for (float v : w) fprintf(f, "%.6f\n", v); fclose(f); }

int main(int argc, char **argv) {
  if (argc < 4) { fprintf(stderr, "usage: learn train <init> <nin> <gens> <out> | learn eval <w> <nin> [spacing]\n"); return 1; }
  string mode = argv[1]; int nin = atoi(argv[3]);
  if (mode == "eval" && argc > 4) SPACING = atof(argv[4]);
  buildAll(81);
  Net base{nin, loadW(argv[2], nin)};
  if (mode == "eval") {
    // fixed test set: 40 random cars per track, 30 s each, including the two shapes never used in training
    mt19937 g(argc > 5 ? atoi(argv[5]) : 12345); const char *styles[3] = {"mixed", "dashed", "dotted"};
    for (int set = 0; set < 2; set++) {
      const vector<int> &pool = set == 0 ? trainTracks : testTracks;
      for (int k = 0; k < 3; k++) {
        vector<int> sub; for (int t : pool) if (tracks[t].style == styles[k]) sub.push_back(t);
        vector<Scn> sc; for (int i = 0; i < 40; i++) sc.push_back(sample(g, sub));
        vector<vector<Result>> all; evalMany({base}, sc, 30, &all);
        int clean = 0; double err = 0; for (auto &R : all[0]) { clean += !R.off && !R.stopped; err += R.meanErr; }
        printf("{\"tracks\":\"%s\",\"style\":\"%s\",\"clean\":%d,\"runs\":%zu,\"mean_err_mm\":%.1f}\n",
               set == 0 ? "training shapes" : "new shapes", styles[k], clean, sc.size(), err / sc.size());
      }
    }
    return 0;
  }
  int gens = atoi(argv[4]); const char *out = argv[5];
  int D = Net::size(nin), P = 12; float sigma = 0.06f, lr = 0.02f;
  vector<float> th = base.w, m(D, 0), v(D, 0), best = th; double bestVal = -1e9;
  mt19937 vg(999); vector<Scn> val; for (int i = 0; i < 64; i++) val.push_back(sample(vg, trainTracks));
  mt19937 g(2024); normal_distribution<float> N(0, 1);
  printf("gen,train_fitness,validation_fitness\n");
  for (int gen = 0; gen <= gens; gen++) {
    if (gen % 10 == 0) {
      double vf = evalMany({Net{nin, th}}, val, 25)[0];
      if (vf > bestVal) { bestVal = vf; best = th; }
      printf("%d,,%.4f\n", gen, vf); fflush(stdout);
      if (gen == gens) break;
    }
    vector<Scn> sc; for (int i = 0; i < 16; i++) sc.push_back(sample(g, trainTracks));
    vector<vector<float>> eps(P, vector<float>(D)); vector<Net> nets;
    for (int p = 0; p < P; p++) { for (int d = 0; d < D; d++) eps[p][d] = N(g);
      vector<float> a = th, b = th; for (int d = 0; d < D; d++) { a[d] += sigma * eps[p][d]; b[d] -= sigma * eps[p][d]; }
      nets.push_back(Net{nin, a}); nets.push_back(Net{nin, b}); }
    vector<double> f = evalMany(nets, sc, 15);
    vector<int> order(f.size()); iota(order.begin(), order.end(), 0); sort(order.begin(), order.end(), [&](int a, int b) { return f[a] < f[b]; });
    vector<double> rk(f.size()); for (size_t i = 0; i < order.size(); i++) rk[order[i]] = (double)i / (order.size() - 1) - 0.5;
    double mean = accumulate(f.begin(), f.end(), 0.0) / f.size();
    for (int d = 0; d < D; d++) {
      double gr = 0; for (int p = 0; p < P; p++) gr += (rk[2 * p] - rk[2 * p + 1]) * eps[p][d];
      gr /= (2 * P * sigma); gr -= 0.001 * th[d];
      m[d] = 0.9f * m[d] + 0.1f * gr; v[d] = 0.999f * v[d] + 0.001f * gr * gr;
      double mh = m[d] / (1 - pow(0.9, gen + 1)), vh = v[d] / (1 - pow(0.999, gen + 1));
      th[d] += lr * mh / (sqrt(vh) + 1e-8);
    }
    printf("%d,%.4f,\n", gen, mean); fflush(stdout);
  }
  saveW(out, best); fprintf(stderr, "best validation fitness %.4f saved to %s\n", bestVal, out);
  return 0;
}
