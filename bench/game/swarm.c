// The swarm benchmark (swarm.jo) in plain C, as a C programmer would write it: the same
// agents, spatial hash, steering, bullets, events, sparks and scoreboard, with buffers reused
// instead of made per call. Its own random numbers, so the counts differ a little from Sloppy's.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

enum { N = 3000, FRAMES = 300 };
#define DT (1.0 / 60.0)
#define WORLD 2400.0
#define CELL 64.0

typedef struct { float x, y; } vec2;
static vec2 v2(float x, float y) { vec2 r = {x, y}; return r; }
static vec2 add(vec2 a, vec2 b) { return v2(a.x + b.x, a.y + b.y); }
static vec2 sub(vec2 a, vec2 b) { return v2(a.x - b.x, a.y - b.y); }
static vec2 mul(vec2 a, float k) { return v2(a.x * k, a.y * k); }
static vec2 dv(vec2 a, float k) { return v2(a.x / k, a.y / k); }
static float len(vec2 a) { return sqrtf(a.x * a.x + a.y * a.y); }
static float len_sq(vec2 a) { return a.x * a.x + a.y * a.y; }

typedef struct {
    int id; char *name; vec2 pos, vel; int team; float hp, cooldown; int target; int kills; int alive;
} Agent;
typedef struct { vec2 pos, vel; int owner, team; float life; } Bullet;
typedef struct { vec2 pos, vel; float life; } Spark;
typedef struct { int kind, who, by; float dmg; } Event;   // kind 0 hit, 1 kill

static Agent agents[N];
static Bullet *bullets; static int nbullets, cbullets;
static Spark *sparks; static int nsparks, csparks;
static Event *events; static int nevents, cevents;
static char *logv[512]; static int nlog;
static int next_id;
static long shots, hits, kills, respawns;

static uint64_t rng = 0x9E3779B97F4A7C15ull;
static double rnd(void) {
    rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17;
    return (double)(rng >> 11) / 9007199254740992.0;
}
static double rnd2(double lo, double hi) { return lo + (hi - lo) * rnd(); }

#define PUSH(arr, n, cap, v) do { if (n == cap) { cap = cap ? cap * 2 : 16; arr = realloc(arr, cap * sizeof(*arr)); } arr[n++] = (v); } while (0)

// spatial hash: open addressing from cell key to a list of agent indices
typedef struct { int key; int n, cap; int *items; } Cell;
static Cell cells[8192]; static int used_cells[8192]; static int nused;
static Cell *cell_get(int key, int create) {
    uint64_t h = (uint64_t)key * 0x9E3779B97F4A7C15ull;
    int i = (int)(h >> 51);
    for (;;) {
        Cell *c = &cells[i];
        if (c->n > 0 && c->key == key) return c;
        if (c->n == 0) {
            if (!create) return NULL;
            c->key = key; used_cells[nused++] = i;
            return c;
        }
        i = (i + 1) & 8191;
    }
}
static void build_grid(void) {
    for (int k = 0; k < nused; k++) cells[used_cells[k]].n = 0;
    nused = 0;
    for (int i = 0; i < N; i++) {
        if (!agents[i].alive) continue;
        int cx = (int)(fmin(fmax(agents[i].pos.x, 0.0), WORLD - 1.0) / CELL);
        int cy = (int)(fmin(fmax(agents[i].pos.y, 0.0), WORLD - 1.0) / CELL);
        Cell *c = cell_get(cy * 1000 + cx, 1);
        PUSH(c->items, c->n, c->cap, i);
    }
}
static int nbuf[N];
static int neighbors(vec2 p, float r) {
    int n = 0;
    int cx = (int)(fmin(fmax(p.x, 0.0), WORLD - 1.0) / CELL);
    int cy = (int)(fmin(fmax(p.y, 0.0), WORLD - 1.0) / CELL);
    for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++) {
            Cell *c = cell_get((cy + dy) * 1000 + cx + dx, 0);
            if (!c) continue;
            for (int k = 0; k < c->n; k++) {
                int j = c->items[k];
                if (len_sq(sub(agents[j].pos, p)) < r * r) nbuf[n++] = j;
            }
        }
    return n;
}

static Agent spawn(int team) {
    next_id++;
    double side = team == 0 ? WORLD / 2 - 260 : WORLD / 2 + 260;
    Agent a = {0};
    a.id = next_id;
    char buf[32]; snprintf(buf, sizeof buf, "%s-%d", team == 0 ? "red" : "blue", next_id);
    a.name = strdup(buf);
    a.pos = v2((float)(side + rnd2(-150, 150)), (float)rnd2(100, WORLD - 100));
    a.team = team; a.hp = 100; a.cooldown = (float)rnd2(0, 1); a.target = -1; a.alive = 1;
    return a;
}

static void steer(void) {
    for (int i = 0; i < N; i++) {
        Agent *a = &agents[i];
        if (!a->alive) continue;
        vec2 sep = v2(0, 0), center = v2(0, 0), heading = v2(0, 0);
        int friends = 0, best = -1; double best_d = 1e9;
        int n = neighbors(a->pos, 120);
        for (int k = 0; k < n; k++) {
            int j = nbuf[k];
            if (j == i) continue;
            Agent *b = &agents[j];
            vec2 d = sub(b->pos, a->pos);
            float dist = len(d);
            if (b->team == a->team) {
                friends++; center = add(center, b->pos); heading = add(heading, b->vel);
                if (dist < 24 && dist > 0) sep = sub(sep, dv(d, dist * dist));
            } else if (dist < best_d) { best_d = dist; best = j; }
        }
        vec2 force = mul(sep, 900);
        if (friends > 0) {
            force = add(force, mul(sub(dv(center, friends), a->pos), 0.6f));
            force = add(force, mul(sub(dv(heading, friends), a->vel), 0.4f));
        }
        vec2 goal = a->team == 0 ? v2(WORLD, a->pos.y) : v2(0, a->pos.y);
        if (best >= 0) goal = agents[best].pos;
        vec2 tg = sub(goal, a->pos);
        float gl = len(tg);
        if (gl > 0) force = add(force, mul(dv(tg, gl), 60));
        vec2 v = add(a->vel, mul(force, (float)DT));
        float sp = len(v);
        if (sp > 140) v = mul(dv(v, sp), 140);
        a->vel = v; a->target = best;
    }
}

static void move_and_shoot(void) {
    for (int i = 0; i < N; i++) {
        Agent *a = &agents[i];
        if (!a->alive) continue;
        a->pos = add(a->pos, mul(a->vel, (float)DT));
        a->pos.x = fminf(fmaxf(a->pos.x, 0), WORLD); a->pos.y = fminf(fmaxf(a->pos.y, 0), WORLD);
        a->cooldown -= (float)DT;
        if (a->cooldown <= 0 && a->target >= 0) {
            vec2 aim = sub(agents[a->target].pos, a->pos);
            float l = len(aim);
            if (l > 0 && l < 110) {
                Bullet b = {a->pos, mul(dv(aim, l), 420), a->id, a->team, 0.5f};
                PUSH(bullets, nbullets, cbullets, b);
                a->cooldown = 0.6f; shots++;
            }
        }
    }
}

static void fly(void) {
    for (int k = 0; k < nbullets; k++) {
        Bullet *b = &bullets[k];
        b->pos = add(b->pos, mul(b->vel, (float)DT));
        b->life -= (float)DT;
        if (b->life <= 0) continue;
        int n = neighbors(b->pos, 10);
        for (int q = 0; q < n; q++) {
            int j = nbuf[q];
            if (agents[j].team != b->team && agents[j].alive) {
                Event e = {0, j, b->owner, 25};
                PUSH(events, nevents, cevents, e);
                b->life = 0; break;
            }
        }
    }
    int m = 0;
    for (int k = 0; k < nbullets; k++) if (bullets[k].life > 0) bullets[m++] = bullets[k];
    nbullets = m;
}

static void handle_events(void) {
    for (int k = 0; k < nevents; k++) {   // (events added while handling are handled too)
        Event e = events[k];
        if (e.kind == 0) {
            Agent *a = &agents[e.who];
            if (!a->alive) continue;
            a->hp -= e.dmg; hits++;
            for (int s = 0; s < 4; s++) {
                double ang = rnd2(0, 2 * M_PI);
                Spark sp = {a->pos, mul(v2((float)cos(ang), (float)sin(ang)), 90), 0.3f};
                PUSH(sparks, nsparks, csparks, sp);
            }
            if (a->hp <= 0) { a->alive = 0; Event ke = {1, e.who, e.by, 0}; PUSH(events, nevents, cevents, ke); }
        } else {
            kills++;
            for (int i = 0; i < N; i++) if (agents[i].id == e.by) agents[i].kills++;
            char buf[64]; snprintf(buf, sizeof buf, "%s was taken out", agents[e.who].name);
            if (nlog == 512) { for (int q = 0; q < 100; q++) free(logv[q]); memmove(logv, logv + 100, 412 * sizeof(char *)); nlog = 412; }
            logv[nlog++] = strdup(buf);
        }
    }
    nevents = 0;
    for (int i = 0; i < N; i++)
        if (!agents[i].alive) { free(agents[i].name); agents[i] = spawn(agents[i].team); respawns++; }
}

static void update_sparks(void) {
    int m = 0;
    for (int k = 0; k < nsparks; k++) {
        Spark *s = &sparks[k];
        s->pos = add(s->pos, mul(s->vel, (float)DT)); s->vel = mul(s->vel, 0.9f); s->life -= (float)DT;
        if (s->life > 0) sparks[m++] = *s;
    }
    nsparks = m;
}

static int by_kills(const void *x, const void *y) {
    const Agent *a = &agents[*(const int *)x], *b = &agents[*(const int *)y];
    long ka = -(long)a->kills * 100000 + a->id, kb = -(long)b->kills * 100000 + b->id;
    return ka < kb ? -1 : ka > kb;
}
static char board[256];
static void scoreboard(void) {
    static int order[N];
    for (int i = 0; i < N; i++) order[i] = i;
    qsort(order, N, sizeof(int), by_kills);
    int o = 0;
    for (int k = 0; k < 5; k++)
        o += snprintf(board + o, sizeof board - o, "%s%d. %s %d", k ? " | " : "", k + 1, agents[order[k]].name, agents[order[k]].kills);
}

int main(void) {
    for (int i = 0; i < N; i++) agents[i] = spawn(i % 2);
    void (*systems[])(void) = {steer, move_and_shoot, fly, handle_events, update_sparks};
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int frame = 0; frame < FRAMES; frame++) {
        build_grid();
        for (int s = 0; s < 5; s++) systems[s]();
        if (frame % 30 == 0) scoreboard();
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double t = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double checksum = 0;
    for (int i = 0; i < N; i++) checksum += agents[i].pos.x * 0.001 + agents[i].pos.y * 0.002 + agents[i].kills;
    printf("checksum %.3f\nshots %ld hits %ld kills %ld bullets %d sparks %d\ntop: %s\n", checksum, shots, hits, kills, nbullets, nsparks, board);
    fprintf(stderr, "%.3f ms per frame\n", t * 1000 / FRAMES);
    return 0;
}
