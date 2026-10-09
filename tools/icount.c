// Count instructions retired (user space) by a command: deterministic, unlike wall time. Also
// the CPU cycles it used (user space): unlike wall time, barely moved by other programs running.
// usage: icount program args...
#define _GNU_SOURCE
#include <linux/perf_event.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdint.h>

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: icount program args...\n"); return 2; }
    struct perf_event_attr pe, pc;
    memset(&pe, 0, sizeof pe);
    pe.type = PERF_TYPE_HARDWARE;
    pe.size = sizeof pe;
    pe.config = PERF_COUNT_HW_INSTRUCTIONS;
    pe.disabled = 1;
    pe.exclude_kernel = 1;
    pe.exclude_hv = 1;
    pe.inherit = 1;
    pe.enable_on_exec = 1;
    pc = pe;
    pc.config = PERF_COUNT_HW_CPU_CYCLES;
    int go[2];
    if (pipe(go) != 0) return 1;
    pid_t pid = fork();
    if (pid == 0) {
        char c;
        close(go[1]);
        if (read(go[0], &c, 1) != 1) _exit(127);
        execvp(argv[1], argv + 1);
        perror("exec");
        _exit(127);
    }
    int fd = syscall(SYS_perf_event_open, &pe, pid, -1, -1, 0);
    if (fd < 0) { perror("perf_event_open"); kill(pid, 9); return 1; }
    int fc = syscall(SYS_perf_event_open, &pc, pid, -1, -1, 0);
    close(go[0]);
    if (write(go[1], "x", 1) != 1) return 1;
    int status;
    waitpid(pid, &status, 0);
    uint64_t count = 0;
    if (read(fd, &count, sizeof count) != sizeof count) { perror("read"); return 1; }
    uint64_t cycles = 0;
    if (fc < 0 || read(fc, &cycles, sizeof cycles) != sizeof cycles) cycles = 0;
    if (cycles) fprintf(stderr, "%.3f G instructions, %.3f G cycles\n", count / 1e9, cycles / 1e9);
    else fprintf(stderr, "%.3f G instructions\n", count / 1e9);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
