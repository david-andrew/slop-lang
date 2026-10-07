// Tiny sampling profiler for Jot executables (uses ptrace + frame pointers).
// usage: prof [-i usec] program args...
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>
#include <signal.h>
#include <elf.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/user.h>
#include <time.h>
#include <errno.h>

typedef struct { uint64_t addr, size; char *name; long self, total; int seen; long callers; } Sym;
static const char *focus = NULL;
static Sym *syms; static int nsyms;

static int cmp(const void *a, const void *b) {
  const Sym *x = a, *y = b;
  return x->addr < y->addr ? -1 : x->addr > y->addr;
}

static void load_syms(const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) { perror(path); exit(1); }
  fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  char *buf = malloc(n);
  if (fread(buf, 1, n, f) != (size_t)n) exit(1);
  fclose(f);
  Elf64_Ehdr *eh = (Elf64_Ehdr *)buf;
  Elf64_Shdr *sh = (Elf64_Shdr *)(buf + eh->e_shoff);
  for (int i = 0; i < eh->e_shnum; i++) {
    if (sh[i].sh_type != SHT_SYMTAB) continue;
    Elf64_Sym *st = (Elf64_Sym *)(buf + sh[i].sh_offset);
    int cnt = sh[i].sh_size / sizeof(Elf64_Sym);
    char *strs = buf + sh[sh[i].sh_link].sh_offset;
    syms = calloc(cnt, sizeof(Sym));
    for (int k = 0; k < cnt; k++) {
      if (!st[k].st_value) continue;
      syms[nsyms].addr = st[k].st_value;
      syms[nsyms].size = st[k].st_size;
      syms[nsyms].name = strdup(strs + st[k].st_name);
      nsyms++;
    }
  }
  qsort(syms, nsyms, sizeof(Sym), cmp);
}

static Sym *find(uint64_t a) {
  int lo = 0, hi = nsyms - 1, r = -1;
  while (lo <= hi) { int m = (lo + hi) / 2; if (syms[m].addr <= a) { r = m; lo = m + 1; } else hi = m - 1; }
  if (r < 0) return NULL;
  if (syms[r].size && a >= syms[r].addr + syms[r].size) return NULL;
  return &syms[r];
}

static int by_self(const void *a, const void *b) { const Sym *x = *(Sym **)a, *y = *(Sym **)b; return (y->self > x->self) - (y->self < x->self); }
static int by_total(const void *a, const void *b) { const Sym *x = *(Sym **)a, *y = *(Sym **)b; return (y->total > x->total) - (y->total < x->total); }

int main(int argc, char **argv) {
  int interval = 500;
  int ai = 1;
  while (ai + 1 < argc && argv[ai][0] == '-') {
    if (strcmp(argv[ai], "-i") == 0) interval = atoi(argv[ai + 1]);
    else if (strcmp(argv[ai], "-c") == 0) focus = argv[ai + 1];
    ai += 2;
  }
  if (ai >= argc) { fprintf(stderr, "usage: prof [-i usec] program args...\n"); return 2; }
  load_syms(argv[ai]);
  pid_t pid = fork();
  if (pid == 0) {
    ptrace(PTRACE_TRACEME, 0, 0, 0);
    execv(argv[ai], argv + ai);
    _exit(127);
  }
  int status;
  waitpid(pid, &status, 0);          // stopped at exec
  ptrace(PTRACE_CONT, pid, 0, 0);
  long samples = 0, unknown = 0;
  for (;;) {
    struct timespec ts = {0, interval * 1000};
    nanosleep(&ts, NULL);
    if (kill(pid, SIGSTOP) < 0) break;
    if (waitpid(pid, &status, 0) < 0) break;
    if (WIFEXITED(status) || WIFSIGNALED(status)) break;
    if (WIFSTOPPED(status) && WSTOPSIG(status) != SIGSTOP) {
      ptrace(PTRACE_CONT, pid, 0, WSTOPSIG(status));
      continue;
    }
    struct user_regs_struct regs;
    if (ptrace(PTRACE_GETREGS, pid, 0, &regs) == 0) {
      samples++;
      Sym *s = find(regs.rip);
      if (s) s->self++; else { unknown++; if (unknown < 6) fprintf(stderr, "unknown rip %llx\n", (unsigned long long)regs.rip); }
      for (int i = 0; i < nsyms; i++) syms[i].seen = 0;
      if (s) { s->total++; s->seen = 1; }
      uint64_t bp = regs.rbp;
      int focus_hit = s && focus && strstr(s->name, focus) != NULL;
      int depth0 = 1;
      // the leaf may not have set up its frame yet; walk the rbp chain
      for (int d = 0; d < 200 && bp; d++) {
        errno = 0;
        uint64_t ret = ptrace(PTRACE_PEEKDATA, pid, bp + 8, 0);
        uint64_t nbp = ptrace(PTRACE_PEEKDATA, pid, bp, 0);
        if (errno) break;
        Sym *c = find(ret);
        if (focus_hit && depth0 && c) { c->callers++; depth0 = 0; }
        if (c && !c->seen) { c->total++; c->seen = 1; }
        if (nbp <= bp) break;
        bp = nbp;
      }
    }
    ptrace(PTRACE_CONT, pid, 0, 0);
  }
  Sym **v = malloc(sizeof(Sym *) * nsyms);
  for (int i = 0; i < nsyms; i++) v[i] = &syms[i];
  fprintf(stderr, "\n%ld samples (%ld outside known functions)\n\n  self%%  total%%  function\n", samples, unknown);
  qsort(v, nsyms, sizeof(Sym *), by_self);
  for (int i = 0; i < nsyms && i < 30 && v[i]->self; i++)
    fprintf(stderr, "%6.1f %6.1f   %s\n", 100.0 * v[i]->self / samples, 100.0 * v[i]->total / samples, v[i]->name);
  fprintf(stderr, "\n  by inclusive time:\n");
  qsort(v, nsyms, sizeof(Sym *), by_total);
  for (int i = 0; i < nsyms && i < 30 && v[i]->total; i++)
    fprintf(stderr, "%6.1f %6.1f   %s\n", 100.0 * v[i]->self / samples, 100.0 * v[i]->total / samples, v[i]->name);
  if (focus) {
    fprintf(stderr, "\n  callers of %s:\n", focus);
    for (int i = 0; i < nsyms; i++) for (int j = i + 1; j < nsyms; j++) if (v[j]->callers > v[i]->callers) { Sym *t = v[i]; v[i] = v[j]; v[j] = t; }
    for (int i = 0; i < nsyms && i < 15 && v[i]->callers; i++) fprintf(stderr, "%6ld   %s\n", v[i]->callers, v[i]->name);
  }
  return 0;
}
