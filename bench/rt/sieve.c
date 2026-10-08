#include <stdio.h>
#include <stdlib.h>
int main(void) {
    long n = 20000000;
    char *comp = calloc(n + 1, 1);
    long count = 0;
    for (long i = 2; i <= n; i++) {
        if (!comp[i]) {
            count++;
            for (long j = i * i; j <= n; j += i) comp[j] = 1;
        }
    }
    printf("%ld\n", count);
}
