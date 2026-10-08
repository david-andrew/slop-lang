#include <stdio.h>
int main(void) {
    int size = 1600; long total = 0;
    for (int y = 0; y < size; y++) {
        double ci = 2.0 * y / size - 1.0;
        for (int x = 0; x < size; x++) {
            double cr = 2.0 * x / size - 1.5, zr = 0, zi = 0;
            int k = 0;
            while (k < 50 && zr * zr + zi * zi <= 4.0) { double t = zr * zr - zi * zi + cr; zi = 2.0 * zr * zi + ci; zr = t; k++; }
            if (k == 50) total++;
        }
    }
    printf("%ld\n", total);
}
