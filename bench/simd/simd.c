// bench/simd/simd.jot in C (gcc -O2 vectorizes these loops itself, with SSE2: it does not
// assume more of the processor than the x86-64 baseline unless told to).
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <time.h>
enum { N = 4096, R = 20000 };
static double now(void) { struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t); return t.tv_sec + t.tv_nsec * 1e-9; }
__attribute__((noinline)) static void axpy(float *ys, const float *xs, float a, int n) { for (int i = 0; i < n; i++) ys[i] = ys[i] + a * xs[i]; }
__attribute__((noinline)) static void scale(double *ys, const double *xs, double k, int n) { for (int i = 0; i < n; i++) ys[i] = xs[i] * k + 1.0; }
__attribute__((noinline)) static void iadd(int32_t *ys, const int32_t *xs, int n) { for (int i = 0; i < n; i++) ys[i] = ys[i] + xs[i] * 3; }
__attribute__((noinline)) static double *dotted(double *d, const double *e, int n) { double *o = malloc(n * 8); for (int i = 0; i < n; i++) o[i] = d[i] + e[i] * 0.016; free(d); return o; }
int main(void) {
    static float ys[N], xs[N]; static double a[N], b[N]; static int32_t p[N], q[N];
    for (int i = 0; i < N; i++) { ys[i] = 1; xs[i] = i * 0.5f; b[i] = i; p[i] = 1; q[i] = i; }
    double t = now();
    for (int r = 0; r < R; r++) axpy(ys, xs, 0.001f, N);
    printf("axpy_f32 %.3f %g\n", (now() - t) * 1e9 / ((double)R * N), ys[100]);
    t = now();
    for (int r = 0; r < R; r++) scale(a, b, 0.5, N);
    printf("scale_f64 %.3f %g\n", (now() - t) * 1e9 / ((double)R * N), a[100]);
    t = now();
    for (int r = 0; r < R; r++) iadd(p, q, N);
    printf("iadd_i32 %.3f %d\n", (now() - t) * 1e9 / ((double)R * N), p[100]);
    double *d = malloc(N * 8), *e = malloc(N * 8);
    for (int i = 0; i < N; i++) { d[i] = i; e[i] = 1.5; }
    t = now();
    for (int r = 0; r < R / 10; r++) d = dotted(d, e, N);
    printf("dotted_f64 %.3f %g\n", (now() - t) * 1e9 / ((double)(R / 10) * N), d[10]);
    return 0;
}
