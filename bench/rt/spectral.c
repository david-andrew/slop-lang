#include <stdio.h>
#include <math.h>
static double a(long i, long j) { return 1.0 / (double)((i + j) * (i + j + 1) / 2 + i + 1); }
static void mul_av(const double *v, double *out, int n) {
    for (int i = 0; i < n; i++) { double s = 0; for (int j = 0; j < n; j++) s += a(i, j) * v[j]; out[i] = s; }
}
static void mul_atv(const double *v, double *out, int n) {
    for (int i = 0; i < n; i++) { double s = 0; for (int j = 0; j < n; j++) s += a(j, i) * v[j]; out[i] = s; }
}
int main(void) {
    enum { N = 1500 };
    static double u[N], v[N], tmp[N];
    for (int i = 0; i < N; i++) u[i] = 1;
    for (int k = 0; k < 10; k++) { mul_av(u, tmp, N); mul_atv(tmp, v, N); mul_av(v, tmp, N); mul_atv(tmp, u, N); }
    double vbv = 0, vv = 0;
    for (int i = 0; i < N; i++) { vbv += u[i] * v[i]; vv += v[i] * v[i]; }
    printf("%.9f\n", sqrt(vbv / vv));
}
