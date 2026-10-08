// C equivalents of bench/loops/loops.jot (gcc -O2); the dotted expression allocates a new array
// each time, as the Jot one does.
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <time.h>
typedef struct { double x, y, vx, vy, life; long tag; } P;
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
#define N 1000000
#define R 20
static double ns(double t, double n) { return t * 1e9 / n; }
__attribute__((noinline)) static void aos(P *ps) { for (int i = 0; i < N; i++) { ps[i].x += ps[i].vx * 0.016; ps[i].y += ps[i].vy * 0.016; } }
__attribute__((noinline)) static void soa(double *x, double *y, double *vx, double *vy) { for (int i = 0; i < N; i++) { x[i] += vx[i] * 0.016; y[i] += vy[i] * 0.016; } }
__attribute__((noinline)) static void arrays(double *xs, double *vs) { for (int i = 0; i < N; i++) xs[i] += vs[i] * 0.016; }
__attribute__((noinline)) static double *dotted(double *xs, double *vs) { double *o = malloc(N * 8); for (int i = 0; i < N; i++) o[i] = xs[i] + vs[i] * 0.016; free(xs); return o; }
__attribute__((noinline)) static double trig(int n, int c) { double s = 0; for (int i = 0; i < n; i++) s += c ? cos(i * 0.001) : sin(i * 0.001); return s; }
int main(void) {
    P *ps = malloc(N * sizeof(P));
    double *sx = malloc(N * 8), *sy = malloc(N * 8), *svx = malloc(N * 8), *svy = malloc(N * 8);
    double *wx = calloc(N, 8), *wv = malloc(N * 8), *xs = calloc(N, 8), *vs = malloc(N * 8);
    for (int i = 0; i < N; i++) { ps[i] = (P){i, 0, 1, 2, 5, i}; sx[i] = i; sy[i] = 0; svx[i] = 1; svy[i] = 2; wv[i] = 1.5; vs[i] = 1.5; }
    double t = now();
    for (int r = 0; r < R; r++) aos(ps);
    printf("aos_update %.2f\n", ns(now() - t, R * N));
    t = now();
    for (int r = 0; r < R; r++) soa(sx, sy, svx, svy);
    printf("soa_update %.2f\n", ns(now() - t, R * N));
    t = now();
    for (int r = 0; r < R; r++) arrays(wx, wv);
    printf("struct_field_arrays %.2f\n", ns(now() - t, R * N));
    t = now();
    for (int r = 0; r < R; r++) arrays(xs, vs);
    printf("plain_arrays %.2f\n", ns(now() - t, R * N));
    t = now();
    for (int r = 0; r < R; r++) xs = dotted(xs, vs);
    printf("dotted_new_array %.2f\n", ns(now() - t, R * N));
    t = now();
    double s = trig(10000000, 0);
    printf("sin %.2f\n", ns(now() - t, 1e7));
    t = now();
    double c = trig(10000000, 1);
    printf("cos %.2f\n", ns(now() - t, 1e7));
    printf("check %.1f\n", s + c + ps[5].x + sx[5] + wx[3] + xs[2]);
}
