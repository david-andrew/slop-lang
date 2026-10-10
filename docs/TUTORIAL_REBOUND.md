# Make an arcade game

This tutorial builds **Little Rebound**, a small version of [Rebound](../examples/rebound/rebound.jo):
turrets around a core fire at it, and you turn a shield to catch their bolts and send them back.
It is a different kind of game from the [first tutorial](TUTORIAL.md)'s platformer: everything
happens around one point, so it works in angles; there are many things at once (turrets, bolts,
blasts), kept in arrays of structs; and a destroyed turret can set off the next, in chains. Each
step is a whole program that runs; on the website, "Run it in the playground" opens it in your
browser, and with Sloppy installed `sloppy rebound.jo` runs it in a window.

## 1. A core and a shield

```gdscript
# step 1: a core, and a shield that turns around it
const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
CENTER = vec2(640, 360)

shield = -PI / 2.0                      # the shield's angle: straight up

update = (dt: f64):
    if key_down(.left) or key_down(.a): shield -= TURN * dt
    if key_down(.right) or key_down(.d): shield += TURN * dt

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))         # the shield's track
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    arc(CENTER, ORBIT_R, 9, shield - SHIELD_HALF, shield + SHIELD_HALF, rgb(0.35, 0.95, 1))

window("Little Rebound", 1280, 720)
```

Angles are in radians: a full turn is `TAU` (`2 * PI`). Angle 0 points right, and angles
grow clockwise on the screen (its y axis points down), so `-PI / 2.0` points up. `arc` draws part
of a ring, from one angle to another: the shield is the stretch of its ring from
`shield - SHIELD_HALF` to `shield + SHIELD_HALF`. `TURN * dt` turns it by its speed (radians a
second) times the length of the frame (seconds), so it turns as fast on any screen.

The numbers that decide how the game plays are `const`s at the top, with names. Try others: a
wider shield, a faster turn.

## 2. Turrets that fire

```gdscript
# step 2: turrets that fire at the core, and a shield that stops their bolts
const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
CENTER = vec2(640, 360)

struct Turret:
    pos: vec2
    cool: f64                           # seconds until it fires

struct Bolt:
    pos: vec2
    vel: vec2
    alive = true

turrets: Turret[]
bolts: Bolt[]
shield = -PI / 2.0                      # the shield's angle: straight up
core = 3                                # hits the core can take

# the point at angle a, distance r from the core
polar = (a: f64, r: f64) -> vec2: CENTER + from_angle(a) * f32(r)
# an angle as -pi .. pi (the short way round)
wrap = (a: f64) -> f64: mod(a + PI, TAU) - PI

# is there shield where a bolt crosses the shield's ring at angle a?
shielded = (a: f64) -> bool: abs(wrap(a - shield)) <= SHIELD_HALF

update = (dt: f64):
    if key_down(.left) or key_down(.a): shield = wrap(shield - TURN * dt)
    if key_down(.right) or key_down(.d): shield = wrap(shield + TURN * dt)
    loop mut t in turrets:
        t.cool -= dt
        if t.cool <= 0.0:
            t.cool = random(2.0, 4.0)
            bolts.push(Bolt(t.pos, normalize(CENTER - t.pos) * 180.0))
    loop mut b in bolts:
        before = length(b.pos - CENTER)
        b.pos += b.vel * f32(dt)
        d = length(b.pos - CENTER)
        # it crossed the shield's ring this frame, where the shield is: stopped
        if before > ORBIT_R and d <= ORBIT_R and shielded(angle(b.pos - CENTER)): b.alive = false
        else if d < CORE_R:
            b.alive = false
            core -= 1
    bolts = bolts.filter((b): b.alive)

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))
    loop t in turrets:
        a = angle(CENTER - t.pos)       # a triangle pointing at the core
        tip = t.pos + from_angle(a) * 22.0
        triangle(tip, t.pos + from_angle(a + 2.4) * 17.0, t.pos + from_angle(a - 2.4) * 17.0, rgb(1, 0.33, 0.42))
    loop b in bolts: circle(b.pos, 6, rgb(1, 0.85, 0.5))
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    arc(CENTER, ORBIT_R, 9, shield - SHIELD_HALF, shield + SHIELD_HALF, rgb(0.35, 0.95, 1))
    text("core {core}", vec2(24, 20), 32)

loop i in [0..4): turrets.push(Turret(polar(random(0.0, TAU), random(200.0, 290.0)), random(1.0, 3.0)))
window("Little Rebound", 1280, 720)
```

A `struct` is a kind of value with named fields; `turrets: Turret[]` is an array of them, and
`turrets.push(Turret(...))` adds one. `loop mut t in turrets` goes through the array with `t`
standing for each element itself, so changing `t.cool` changes the turret in the array (plain
`loop t in turrets` gives copies to read). `bolts.filter((b): b.alive)` keeps the bolts that are
still alive: `(b): b.alive` is a small function, called for each bolt.

Two helpers do the geometry. `polar(a, r)` is the point at angle `a`, distance `r` from the core.
`wrap` turns any angle into one from `-PI` to `PI`, so `abs(wrap(a - shield))` is how far apart
two angles are the short way round, even when one is just below `PI` and the other just above
`-PI`.

A bolt moves several pixels a frame, so it is almost never exactly on the shield's ring. Instead,
each frame compares its distance from the core before and after it moved: if it was outside the
ring and now is inside, it crossed it this frame, at the angle where it is.

## 3. Send them back

```gdscript
# step 3: send the bolts back
const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
CENTER = vec2(640, 360)

struct Turret:
    pos: vec2
    cool: f64                           # seconds until it fires
    alive = true

struct Bolt:
    pos: vec2
    vel: vec2
    from: vec2                          # where it was fired from
    mine = false                        # sent back by the shield
    alive = true

turrets: Turret[]
bolts: Bolt[]
shield = -PI / 2.0                      # the shield's angle: straight up
core = 3                                # hits the core can take
score = 0
spawn = 0.0                             # seconds until the next turret comes

# the point at angle a, distance r from the core
polar = (a: f64, r: f64) -> vec2: CENTER + from_angle(a) * f32(r)
# an angle as -pi .. pi (the short way round)
wrap = (a: f64) -> f64: mod(a + PI, TAU) - PI

# is there shield where a bolt crosses the shield's ring at angle a?
shielded = (a: f64) -> bool: abs(wrap(a - shield)) <= SHIELD_HALF

update = (dt: f64):
    if key_down(.left) or key_down(.a): shield = wrap(shield - TURN * dt)
    if key_down(.right) or key_down(.d): shield = wrap(shield + TURN * dt)
    # a new turret every few seconds
    spawn -= dt
    if spawn <= 0.0 and turrets.len() < 6:
        turrets.push(Turret(polar(random(0.0, TAU), random(200.0, 290.0)), random(1.0, 2.5)))
        spawn = 3.0
    loop mut t in turrets:
        t.cool -= dt
        if t.cool <= 0.0:
            t.cool = random(2.5, 4.0)
            bolts.push(Bolt(t.pos, normalize(CENTER - t.pos) * 180.0, t.pos))
    loop mut b in bolts:
        before = length(b.pos - CENTER)
        b.pos += b.vel * f32(dt)
        d = length(b.pos - CENTER)
        if b.mine:
            # on its way back out: it destroys the turret it meets
            loop mut t in turrets:
                if t.alive and length(t.pos - b.pos) < 22.0:
                    t.alive = false
                    b.alive = false
                    score += 100
            if d > 800.0: b.alive = false
        else if before > ORBIT_R and d <= ORBIT_R and shielded(angle(b.pos - CENTER)):
            # caught: back where it came from, faster
            b.mine = true
            b.vel = normalize(b.from - b.pos) * 700.0
        else if d < CORE_R:
            b.alive = false
            core -= 1
    bolts = bolts.filter((b): b.alive)
    turrets = turrets.filter((t): t.alive)

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))
    loop t in turrets:
        a = angle(CENTER - t.pos)       # a triangle pointing at the core
        tip = t.pos + from_angle(a) * 22.0
        triangle(tip, t.pos + from_angle(a + 2.4) * 17.0, t.pos + from_angle(a - 2.4) * 17.0, rgb(1, 0.33, 0.42))
    loop b in bolts:
        if b.mine: circle(b.pos, 6, rgb(0.85, 1, 1))
        else: circle(b.pos, 6, rgb(1, 0.85, 0.5))
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    arc(CENTER, ORBIT_R, 9, shield - SHIELD_HALF, shield + SHIELD_HALF, rgb(0.35, 0.95, 1))
    text("{score}    core {core}", vec2(24, 20), 32)

window("Little Rebound", 1280, 720)
```

Each bolt remembers where it came `from`, so a caught bolt (`mine`) can fly straight back there,
faster. On the way out it is checked against every turret: the first one it touches is
destroyed (`alive = false`), and both are dropped by the `filter`s at the end of the frame.
Removing things only there keeps the loops simple: nothing disappears from an array while a loop
is going through it. A timer, `spawn`, brings a new turret every three seconds.

## 4. Bank shots and a multiplier

```gdscript
# step 4: bank shots, and a multiplier for catches in a row
const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
const DEFLECT = 0.7                     # how far a catch at the shield's edge turns a bolt
CENTER = vec2(640, 360)

struct Turret:
    pos: vec2
    cool: f64                           # seconds until it fires
    alive = true

struct Bolt:
    pos: vec2
    vel: vec2
    from: vec2                          # where it was fired from
    mine = false                        # sent back by the shield
    bank = false                        # sent to a turret that did not fire it
    alive = true

turrets: Turret[]
bolts: Bolt[]
shield = -PI / 2.0                      # the shield's angle: straight up
core = 3                                # hits the core can take
score = 0
streak = 0                              # catches in a row
spawn = 0.0                             # seconds until the next turret comes

# the point at angle a, distance r from the core
polar = (a: f64, r: f64) -> vec2: CENTER + from_angle(a) * f32(r)
# an angle as -pi .. pi (the short way round)
wrap = (a: f64) -> f64: mod(a + PI, TAU) - PI
mult = () -> int: min(1 + streak / 4, 8)

# where a bolt crossing the shield's ring at angle a meets the shield: -1 (one edge) to 1 (the
# other), or -9: no shield there
shield_offset = (a: f64) -> f64:
    d = wrap(a - shield)
    if abs(d) <= SHIELD_HALF: return d / SHIELD_HALF
    -9.0

# what a bolt leaving p at angle dir is headed for: the turret nearest that line, or far away
aim = (p: vec2, dir: f64) -> vec2:
    goal = p + from_angle(dir) * 1000.0
    nearest = 0.5
    loop t in turrets:
        d = abs(wrap(angle(t.pos - p) - dir))
        if d < nearest:
            nearest = d
            goal = t.pos
    goal

catch = (b: mut Bolt, off: f64):
    # straight back out from the middle of the shield; turned, from nearer its edges
    goal = aim(b.pos, angle(b.pos - CENTER) + off * DEFLECT)
    b.mine = true
    b.bank = goal != b.from
    b.vel = normalize(goal - b.pos) * 700.0
    streak += 1

update = (dt: f64):
    if key_down(.left) or key_down(.a): shield = wrap(shield - TURN * dt)
    if key_down(.right) or key_down(.d): shield = wrap(shield + TURN * dt)
    # a new turret every few seconds
    spawn -= dt
    if spawn <= 0.0 and turrets.len() < 6:
        turrets.push(Turret(polar(random(0.0, TAU), random(200.0, 290.0)), random(1.0, 2.5)))
        spawn = 3.0
    loop mut t in turrets:
        t.cool -= dt
        if t.cool <= 0.0:
            t.cool = random(2.5, 4.0)
            bolts.push(Bolt(t.pos, normalize(CENTER - t.pos) * 180.0, t.pos))
    loop mut b in bolts:
        before = length(b.pos - CENTER)
        b.pos += b.vel * f32(dt)
        d = length(b.pos - CENTER)
        if b.mine:
            # on its way back out: it destroys the turret it meets
            loop mut t in turrets:
                if t.alive and length(t.pos - b.pos) < 22.0:
                    t.alive = false
                    b.alive = false
                    points = 100 * mult()
                    if b.bank: points *= 2
                    score += points
            if d > 800.0: b.alive = false
        else if before > ORBIT_R and d <= ORBIT_R and shield_offset(angle(b.pos - CENTER)) > -2.0:
            catch(b, shield_offset(angle(b.pos - CENTER)))
        else if d < CORE_R:
            b.alive = false
            core -= 1
            streak = 0
    bolts = bolts.filter((b): b.alive)
    turrets = turrets.filter((t): t.alive)

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))
    loop t in turrets:
        a = angle(CENTER - t.pos)       # a triangle pointing at the core
        tip = t.pos + from_angle(a) * 22.0
        triangle(tip, t.pos + from_angle(a + 2.4) * 17.0, t.pos + from_angle(a - 2.4) * 17.0, rgb(1, 0.33, 0.42))
    loop b in bolts:
        if b.mine: circle(b.pos, 6, rgb(0.85, 1, 1))
        else: circle(b.pos, 6, rgb(1, 0.85, 0.5))
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    arc(CENTER, ORBIT_R, 9, shield - SHIELD_HALF, shield + SHIELD_HALF, rgb(0.35, 0.95, 1))
    text("{score}   x{mult()}    core {core}", vec2(24, 20), 32)

window("Little Rebound", 1280, 720)
```

`shield_offset` says not just whether the shield is there, but where on it a bolt lands: 0 in
the middle, -1 and 1 at the edges (and -9, a value no catch can have, when it misses). A catch in
the middle sends the bolt straight back out; nearer an edge, it is turned by up to `DEFLECT`.
`aim` then finds the turret nearest the bolt's new line (within half a radian) and heads for it.
A bolt that hits a turret other than the one that fired it is a bank shot, worth double.

Catches in a row (`streak`) raise the multiplier, `mult()`: one more for every four catches, up
to eight. A bolt that reaches the core resets it.

## 5. Chain reactions

```gdscript
# step 5: chain reactions, sparks and shake
const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
const DEFLECT = 0.7                     # how far a catch at the shield's edge turns a bolt
const BLAST_R = 100.0
CENTER = vec2(640, 360)

struct Turret:
    pos: vec2
    cool: f64                           # seconds until it fires
    alive = true

struct Bolt:
    pos: vec2
    vel: vec2
    from: vec2                          # where it was fired from
    mine = false                        # sent back by the shield
    bank = false                        # sent to a turret that did not fire it
    alive = true

struct Blast:
    pos: vec2
    r: f64
    depth: int                          # 0: a bolt hit the turret; 1, 2, ...: another blast did
    age = 0.0
    done = false                        # it has set off the turrets near it

turrets: Turret[]
bolts: Bolt[]
blasts: Blast[]
sparks = Particles(gravity = vec2(0, 0), drag = 3.0)
shield = -PI / 2.0                      # the shield's angle: straight up
core = 3                                # hits the core can take
score = 0
streak = 0                              # catches in a row
spawn = 0.0                             # seconds until the next turrets come
shake = 0.0

# the point at angle a, distance r from the core
polar = (a: f64, r: f64) -> vec2: CENTER + from_angle(a) * f32(r)
# an angle as -pi .. pi (the short way round)
wrap = (a: f64) -> f64: mod(a + PI, TAU) - PI
mult = () -> int: min(1 + streak / 4, 8)

# one to three turrets side by side, somewhere around the core
add_turrets = ():
    a = random(0.0, TAU)
    r = random(200.0, 290.0)
    loop i in [0..random_int(1, 4)):
        p = polar(a + 0.3 * f64(i), r)
        if not turrets.any((t): length(t.pos - p) < 60.0): turrets.push(Turret(p, random(1.0, 2.5)))

# where a bolt crossing the shield's ring at angle a meets the shield: -1 (one edge) to 1 (the
# other), or -9: no shield there
shield_offset = (a: f64) -> f64:
    d = wrap(a - shield)
    if abs(d) <= SHIELD_HALF: return d / SHIELD_HALF
    -9.0

# what a bolt leaving p at angle dir is headed for: the turret nearest that line, or far away
aim = (p: vec2, dir: f64) -> vec2:
    goal = p + from_angle(dir) * 1000.0
    nearest = 0.5
    loop t in turrets:
        d = abs(wrap(angle(t.pos - p) - dir))
        if d < nearest:
            nearest = d
            goal = t.pos
    goal

catch = (b: mut Bolt, off: f64):
    # straight back out from the middle of the shield; turned, from nearer its edges
    goal = aim(b.pos, angle(b.pos - CENTER) + off * DEFLECT)
    b.mine = true
    b.bank = goal != b.from
    b.vel = normalize(goal - b.pos) * 700.0
    streak += 1
    emit(sparks, b.pos, 12, 250.0, rgba(0.5, 1, 1, 1), 0.3, 4.0)

destroy = (t: mut Turret, depth: int, bank: bool):
    t.alive = false
    points = 100 * mult() * (depth + 1)
    if bank: points *= 2
    score += points
    blasts.push(Blast(t.pos, BLAST_R, depth))
    emit(sparks, t.pos, 40, 450.0, rgba(1, 0.45, 0.4, 1), 0.7, 6.0)
    shake = max(shake, 8.0 + 3.0 * f64(depth))

update = (dt: f64):
    update(sparks, dt)
    shake = max(shake - dt * 40.0, 0.0)
    if key_down(.left) or key_down(.a): shield = wrap(shield - TURN * dt)
    if key_down(.right) or key_down(.d): shield = wrap(shield + TURN * dt)
    spawn -= dt
    if spawn <= 0.0 and turrets.len() < 6:
        add_turrets()
        spawn = 3.0
    loop mut t in turrets:
        t.cool -= dt
        if t.cool <= 0.0:
            t.cool = random(2.5, 4.0)
            bolts.push(Bolt(t.pos, normalize(CENTER - t.pos) * 180.0, t.pos))
    loop mut b in bolts:
        before = length(b.pos - CENTER)
        b.pos += b.vel * f32(dt)
        d = length(b.pos - CENTER)
        if b.mine:
            # on its way back out: it destroys the turret it meets
            loop mut t in turrets:
                if t.alive and length(t.pos - b.pos) < 22.0:
                    destroy(t, 0, b.bank)
                    b.alive = false
            if d > 800.0: b.alive = false
        else if before > ORBIT_R and d <= ORBIT_R and shield_offset(angle(b.pos - CENTER)) > -2.0:
            catch(b, shield_offset(angle(b.pos - CENTER)))
        else if d < CORE_R:
            b.alive = false
            core -= 1
            streak = 0
            shake = 25.0
    # blasts set off the turrets near them, a moment later: chains
    i = 0
    loop i < blasts.len():
        blasts[i].age += dt
        if not blasts[i].done and blasts[i].age > 0.1:
            blasts[i].done = true
            x = blasts[i]
            loop mut t in turrets:
                if t.alive and length(t.pos - x.pos) < x.r: destroy(t, x.depth + 1, false)
        i += 1
    bolts = bolts.filter((b): b.alive)
    turrets = turrets.filter((t): t.alive)
    blasts = blasts.filter((x): x.age < 0.6)

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    push_transform()
    translate(random(-shake, shake), random(-shake, shake))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))
    loop t in turrets:
        a = angle(CENTER - t.pos)       # a triangle pointing at the core
        tip = t.pos + from_angle(a) * 22.0
        triangle(tip, t.pos + from_angle(a + 2.4) * 17.0, t.pos + from_angle(a - 2.4) * 17.0, rgb(1, 0.33, 0.42))
    # blasts: rings that grow and fade
    loop x in blasts:
        k = x.age / 0.6
        ring(x.pos, x.r * ease_out(min(k * 1.5, 1.0)), 10.0 * (1.0 - k) + 1.0, rgba(1, 0.7, 0.3, f32(1.0 - k)))
    loop b in bolts:
        if b.mine: circle(b.pos, 6, rgb(0.85, 1, 1))
        else: circle(b.pos, 6, rgb(1, 0.85, 0.5))
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    arc(CENTER, ORBIT_R, 9, shield - SHIELD_HALF, shield + SHIELD_HALF, rgb(0.35, 0.95, 1))
    draw(sparks)
    pop_transform()
    text("{score}   x{mult()}    core {core}", vec2(24, 20), 32)

window("Little Rebound", 1280, 720)
```

A destroyed turret leaves a `Blast`. A tenth of a second later, the blast destroys every turret
within its radius, and each of those leaves a blast of its own: a chain, which travels from
turret to turret where you can watch it. `depth` counts the steps, and each step of a chain is
worth more. Turrets now come in twos and threes, side by side, so there are chains to set off.

The blasts are gone through with `loop i < blasts.len()` rather than `loop ... in blasts`,
because `destroy` adds blasts to the array during that loop, and this way the loop reaches the
new ones too, in the same frame.

`Particles` are sparks: `emit` makes some, `update` moves and fades them, `draw` draws them.
The screen shakes by drawing everything moved a little, at random: `translate` between
`push_transform` and `pop_transform`, with the score drawn after, so it holds still.

(Nothing ends the game yet: the core count just goes below zero.)

## 6. A beginning and an end

```gdscript
# step 6: a beginning and an end
build:
    name = "Little Rebound"             # (save_data keeps data under the program's name)

const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
const DEFLECT = 0.7                     # how far a catch at the shield's edge turns a bolt
const BLAST_R = 100.0
CENTER = vec2(640, 360)

struct Turret:
    pos: vec2
    cool: f64                           # seconds until it fires
    alive = true

struct Bolt:
    pos: vec2
    vel: vec2
    from: vec2                          # where it was fired from
    mine = false                        # sent back by the shield
    bank = false                        # sent to a turret that did not fire it
    alive = true

struct Blast:
    pos: vec2
    r: f64
    depth: int                          # 0: a bolt hit the turret; 1, 2, ...: another blast did
    age = 0.0
    done = false                        # it has set off the turrets near it

enum Screen: title, play, over
screen = Screen.title
best = to_int(load_data("best") ?? "") ?? 0

turrets: Turret[]
bolts: Bolt[]
blasts: Blast[]
sparks = Particles(gravity = vec2(0, 0), drag = 3.0)
shield = -PI / 2.0                      # the shield's angle: straight up
core = 3                                # rings the core has left
score = 0
streak = 0                              # catches in a row
time = 0.0
spawn = 0.0                             # seconds until the next turrets come
shake = 0.0

# the point at angle a, distance r from the core
polar = (a: f64, r: f64) -> vec2: CENTER + from_angle(a) * f32(r)
# an angle as -pi .. pi (the short way round)
wrap = (a: f64) -> f64: mod(a + PI, TAU) - PI
mult = () -> int: min(1 + streak / 4, 8)

start = ():
    turrets.clear()
    bolts.clear()
    blasts.clear()
    shield = -PI / 2.0
    core = 3
    score = 0
    streak = 0
    time = 0.0
    spawn = 0.5
    screen = .play

# one to three turrets side by side, somewhere around the core
add_turrets = ():
    a = random(0.0, TAU)
    r = random(200.0, 290.0)
    loop i in [0..random_int(1, 4)):
        p = polar(a + 0.3 * f64(i), r)
        if not turrets.any((t): length(t.pos - p) < 60.0): turrets.push(Turret(p, random(1.0, 2.5)))

# where a bolt crossing the shield's ring at angle a meets a shield: -1 (one edge) to 1 (the
# other), or -9: no shield there
shield_offset = (a: f64) -> f64:
    d = wrap(a - shield)
    if abs(d) <= SHIELD_HALF: return d / SHIELD_HALF
    -9.0

# what a bolt leaving p at angle dir is headed for: the turret nearest that line, or far away
aim = (p: vec2, dir: f64) -> vec2:
    goal = p + from_angle(dir) * 1000.0
    nearest = 0.5
    loop t in turrets:
        d = abs(wrap(angle(t.pos - p) - dir))
        if d < nearest:
            nearest = d
            goal = t.pos
    goal

catch = (b: mut Bolt, off: f64):
    # straight back out from the middle of the shield; turned, from nearer its edges
    goal = aim(b.pos, angle(b.pos - CENTER) + off * DEFLECT)
    b.mine = true
    b.bank = goal != b.from
    b.vel = normalize(goal - b.pos) * 700.0
    streak += 1
    emit(sparks, b.pos, 12, 250.0, rgba(0.5, 1, 1, 1), 0.3, 4.0)

destroy = (t: mut Turret, depth: int, bank: bool):
    t.alive = false
    points = 100 * mult() * (depth + 1)
    if bank: points *= 2
    score += points
    blasts.push(Blast(t.pos, BLAST_R, depth))
    emit(sparks, t.pos, 40, 450.0, rgba(1, 0.45, 0.4, 1), 0.7, 6.0)
    shake = max(shake, 8.0 + 3.0 * f64(depth))

hit_core = ():
    core -= 1
    streak = 0
    shake = 25.0
    emit(sparks, CENTER, 60, 400.0, rgba(1, 0.3, 0.4, 1), 0.9, 7.0)
    if core <= 0:
        if score > best:
            best = score
            save_data("best", "{best}")
        screen = .over

update = (dt: f64):
    update(sparks, dt)
    shake = max(shake - dt * 40.0, 0.0)
    if screen != .play: return
    time += dt
    # the shield
    if key_down(.left) or key_down(.a): shield = wrap(shield - TURN * dt)
    if key_down(.right) or key_down(.d): shield = wrap(shield + TURN * dt)
    # more turrets, faster bolts, as time goes on
    spawn -= dt
    if spawn <= 0.0 and turrets.len() < 3 + int(time / 15.0):
        add_turrets()
        spawn = max(4.0 - time * 0.02, 1.5)
    speed = min(180.0 + time, 300.0)
    loop mut t in turrets:
        t.cool -= dt
        if t.cool <= 0.0:
            t.cool = random(2.5, 4.0)
            if bolts.len() < 3 + int(time / 20.0):
                bolts.push(Bolt(t.pos, normalize(CENTER - t.pos) * f32(speed), t.pos))
    # the bolts
    loop mut b in bolts:
        before = length(b.pos - CENTER)
        b.pos += b.vel * f32(dt)
        d = length(b.pos - CENTER)
        if b.mine:
            loop mut t in turrets:
                if t.alive and length(t.pos - b.pos) < 22.0:
                    destroy(t, 0, b.bank)
                    b.alive = false
            if d > 800.0: b.alive = false
        else if before > ORBIT_R and d <= ORBIT_R and shield_offset(angle(b.pos - CENTER)) > -2.0:
            catch(b, shield_offset(angle(b.pos - CENTER)))
        else if d < CORE_R:
            b.alive = false
            hit_core()
    # blasts set off the turrets near them, a moment later: chains
    i = 0
    loop i < blasts.len():
        blasts[i].age += dt
        if not blasts[i].done and blasts[i].age > 0.1:
            blasts[i].done = true
            x = blasts[i]
            loop mut t in turrets:
                if t.alive and length(t.pos - x.pos) < x.r: destroy(t, x.depth + 1, false)
        i += 1
    bolts = bolts.filter((b): b.alive)
    turrets = turrets.filter((t): t.alive)
    blasts = blasts.filter((x): x.age < 0.6)

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    push_transform()
    translate(random(-shake, shake), random(-shake, shake))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))
    ring(CENTER, 310, 1, rgba(0.6, 0.8, 1, 0.08))
    loop t in turrets:
        a = angle(CENTER - t.pos)       # a triangle pointing at the core
        tip = t.pos + from_angle(a) * 22.0
        triangle(tip, t.pos + from_angle(a + 2.4) * 17.0, t.pos + from_angle(a - 2.4) * 17.0, rgb(1, 0.33, 0.42))
    loop x in blasts:
        k = x.age / 0.6
        ring(x.pos, x.r * ease_out(min(k * 1.5, 1.0)), 10.0 * (1.0 - k) + 1.0, rgba(1, 0.7, 0.3, f32(1.0 - k)))
    loop b in bolts:
        if b.mine: circle(b.pos, 6, rgb(0.85, 1, 1))
        else: circle(b.pos, 6, rgb(1, 0.85, 0.5))
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    loop i in [0..core): ring(CENTER, CORE_R + 9.0 + 7.0 * f64(i), 3, rgba(0.35, 0.95, 1, 0.8))
    if screen != .over: arc(CENTER, ORBIT_R, 9, shield - SHIELD_HALF, shield + SHIELD_HALF, rgb(0.35, 0.95, 1))
    draw(sparks)
    pop_transform()
    text("{score}   x{mult()}", vec2(24, 20), 36)
    if screen != .play: rect(0, 0, 1280, 720, rgba(0, 0.01, 0.03, 0.6))      # (dim the arena behind a menu)
    if screen == .title:
        text_centered("LITTLE REBOUND", vec2(640, 150), 80)
        text_centered("turn the shield (left / right) to catch the bolts", vec2(640, 220), 26)
        ui_begin("title", vec2(640, 520))
        if ui_button("Play"): start()
        if best > 0: ui_text("best {best}")
        ui_end()
    else if screen == .over:
        text_centered("the core is lost", vec2(640, 150), 48)
        text_centered("{score}   (best {best})", vec2(640, 220), 36)
        ui_begin("over", vec2(640, 520))
        if ui_button("Again"): start()
        ui_end()

window("Little Rebound", 1280, 720)
```

An `enum` says which screen the game is on; `update` only plays the game on `.play`. `start`
sets everything up for a new run. The menus come from `ui_begin` and `ui_button`: a button is
drawn every frame and is true in the frame it is chosen. `save_data("best", ...)` keeps the best
score between runs, and `load_data("best")` reads it back: it is an optional value (there is
nothing saved the first time), so `?? ""` gives a string either way and `to_int(...) ?? 0` a
number.

The game gets harder with `time`: bolts go faster, and more turrets come, sooner. A limit on the
bolts in the air keeps it from ever being hopeless.

## 7. Upgrades

```gdscript
# step 7: upgrades
build:
    name = "Little Rebound"             # (save_data keeps data under the program's name)

const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
const DEFLECT = 0.7                     # how far a catch at the shield's edge turns a bolt
const BLAST_R = 100.0
CENTER = vec2(640, 360)

struct Turret:
    pos: vec2
    cool: f64                           # seconds until it fires
    alive = true

struct Bolt:
    pos: vec2
    vel: vec2
    from: vec2                          # where it was fired from
    mine = false                        # sent back by the shield
    bank = false                        # sent to a turret that did not fire it
    alive = true

struct Blast:
    pos: vec2
    r: f64
    depth: int                          # 0: a bolt hit the turret; 1, 2, ...: another blast did
    age = 0.0
    done = false                        # it has set off the turrets near it

enum Screen: title, play, upgrade, over
screen = Screen.title
best = to_int(load_data("best") ?? "") ?? 0

turrets: Turret[]
bolts: Bolt[]
blasts: Blast[]
sparks = Particles(gravity = vec2(0, 0), drag = 3.0)
shield = -PI / 2.0                      # the shield's angle: straight up
core = 3                                # rings the core has left
score = 0
streak = 0                              # catches in a row
kills = 0
time = 0.0
spawn = 0.0                             # seconds until the next turrets come
shake = 0.0
wide = 0                                # upgrades taken
twin = false
bigger = 0
next_upgrade = 8                        # at this many turrets destroyed

# the point at angle a, distance r from the core
polar = (a: f64, r: f64) -> vec2: CENTER + from_angle(a) * f32(r)
# an angle as -pi .. pi (the short way round)
wrap = (a: f64) -> f64: mod(a + PI, TAU) - PI
mult = () -> int: min(1 + streak / 4, 8)
half = () -> f64: SHIELD_HALF * (1.0 + 0.3 * f64(wide))

start = ():
    turrets.clear()
    bolts.clear()
    blasts.clear()
    shield = -PI / 2.0
    core = 3
    score = 0
    streak = 0
    kills = 0
    time = 0.0
    spawn = 0.5
    wide = 0
    twin = false
    bigger = 0
    next_upgrade = 8
    screen = .play

# one to three turrets side by side, somewhere around the core
add_turrets = ():
    a = random(0.0, TAU)
    r = random(200.0, 290.0)
    loop i in [0..random_int(1, 4)):
        p = polar(a + 0.3 * f64(i), r)
        if not turrets.any((t): length(t.pos - p) < 60.0): turrets.push(Turret(p, random(1.0, 2.5)))

# where a bolt crossing the shield's ring at angle a meets a shield: -1 (one edge) to 1 (the
# other), or -9: no shield there
shield_offset = (a: f64) -> f64:
    d = wrap(a - shield)
    if abs(d) <= half(): return d / half()
    if twin:
        d = wrap(a - shield - PI)
        if abs(d) <= half(): return d / half()
    -9.0

# what a bolt leaving p at angle dir is headed for: the turret nearest that line, or far away
aim = (p: vec2, dir: f64) -> vec2:
    goal = p + from_angle(dir) * 1000.0
    nearest = 0.5
    loop t in turrets:
        d = abs(wrap(angle(t.pos - p) - dir))
        if d < nearest:
            nearest = d
            goal = t.pos
    goal

catch = (b: mut Bolt, off: f64):
    # straight back out from the middle of the shield; turned, from nearer its edges
    goal = aim(b.pos, angle(b.pos - CENTER) + off * DEFLECT)
    b.mine = true
    b.bank = goal != b.from
    b.vel = normalize(goal - b.pos) * 700.0
    streak += 1
    emit(sparks, b.pos, 12, 250.0, rgba(0.5, 1, 1, 1), 0.3, 4.0)

destroy = (t: mut Turret, depth: int, bank: bool):
    t.alive = false
    kills += 1
    points = 100 * mult() * (depth + 1)
    if bank: points *= 2
    score += points
    blasts.push(Blast(t.pos, BLAST_R * (1.0 + 0.3 * f64(bigger)), depth))
    emit(sparks, t.pos, 40, 450.0, rgba(1, 0.45, 0.4, 1), 0.7, 6.0)
    shake = max(shake, 8.0 + 3.0 * f64(depth))

hit_core = ():
    core -= 1
    streak = 0
    shake = 25.0
    emit(sparks, CENTER, 60, 400.0, rgba(1, 0.3, 0.4, 1), 0.9, 7.0)
    if core <= 0:
        if score > best:
            best = score
            save_data("best", "{best}")
        screen = .over

update = (dt: f64):
    update(sparks, dt)
    shake = max(shake - dt * 40.0, 0.0)
    if screen != .play: return
    time += dt
    # the shield
    if key_down(.left) or key_down(.a): shield = wrap(shield - TURN * dt)
    if key_down(.right) or key_down(.d): shield = wrap(shield + TURN * dt)
    # more turrets, faster bolts, as time goes on
    spawn -= dt
    if spawn <= 0.0 and turrets.len() < 3 + int(time / 15.0):
        add_turrets()
        spawn = max(4.0 - time * 0.02, 1.5)
    speed = min(180.0 + time, 300.0)
    loop mut t in turrets:
        t.cool -= dt
        if t.cool <= 0.0:
            t.cool = random(2.5, 4.0)
            if bolts.len() < 3 + int(time / 20.0):
                bolts.push(Bolt(t.pos, normalize(CENTER - t.pos) * f32(speed), t.pos))
    # the bolts
    loop mut b in bolts:
        before = length(b.pos - CENTER)
        b.pos += b.vel * f32(dt)
        d = length(b.pos - CENTER)
        if b.mine:
            loop mut t in turrets:
                if t.alive and length(t.pos - b.pos) < 22.0:
                    destroy(t, 0, b.bank)
                    b.alive = false
            if d > 800.0: b.alive = false
        else if before > ORBIT_R and d <= ORBIT_R and shield_offset(angle(b.pos - CENTER)) > -2.0:
            catch(b, shield_offset(angle(b.pos - CENTER)))
        else if d < CORE_R:
            b.alive = false
            hit_core()
    # blasts set off the turrets near them, a moment later: chains
    i = 0
    loop i < blasts.len():
        blasts[i].age += dt
        if not blasts[i].done and blasts[i].age > 0.1:
            blasts[i].done = true
            x = blasts[i]
            loop mut t in turrets:
                if t.alive and length(t.pos - x.pos) < x.r: destroy(t, x.depth + 1, false)
        i += 1
    bolts = bolts.filter((b): b.alive)
    turrets = turrets.filter((t): t.alive)
    blasts = blasts.filter((x): x.age < 0.6)
    if kills >= next_upgrade and screen == .play:
        next_upgrade += 10
        screen = .upgrade

draw_shield = (a: f64):
    arc(CENTER, ORBIT_R, 9, a - half(), a + half(), rgb(0.35, 0.95, 1))

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    push_transform()
    translate(random(-shake, shake), random(-shake, shake))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))
    ring(CENTER, 310, 1, rgba(0.6, 0.8, 1, 0.08))
    loop t in turrets:
        a = angle(CENTER - t.pos)       # a triangle pointing at the core
        tip = t.pos + from_angle(a) * 22.0
        triangle(tip, t.pos + from_angle(a + 2.4) * 17.0, t.pos + from_angle(a - 2.4) * 17.0, rgb(1, 0.33, 0.42))
    loop x in blasts:
        k = x.age / 0.6
        ring(x.pos, x.r * ease_out(min(k * 1.5, 1.0)), 10.0 * (1.0 - k) + 1.0, rgba(1, 0.7, 0.3, f32(1.0 - k)))
    loop b in bolts:
        if b.mine: circle(b.pos, 6, rgb(0.85, 1, 1))
        else: circle(b.pos, 6, rgb(1, 0.85, 0.5))
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    loop i in [0..core): ring(CENTER, CORE_R + 9.0 + 7.0 * f64(i), 3, rgba(0.35, 0.95, 1, 0.8))
    if screen != .over:
        draw_shield(shield)
        if twin: draw_shield(shield + PI)
    draw(sparks)
    pop_transform()
    text("{score}   x{mult()}", vec2(24, 20), 36)
    if screen != .play: rect(0, 0, 1280, 720, rgba(0, 0.01, 0.03, 0.6))      # (dim the arena behind a menu)
    if screen == .title:
        text_centered("LITTLE REBOUND", vec2(640, 150), 80)
        text_centered("turn the shield (left / right) to catch the bolts", vec2(640, 220), 26)
        ui_begin("title", vec2(640, 520))
        if ui_button("Play"): start()
        if best > 0: ui_text("best {best}")
        ui_end()
    else if screen == .upgrade:
        text_centered("choose an upgrade", vec2(640, 150), 48)
        ui_begin("upgrade", vec2(640, 440))
        if ui_button("A wider shield", wide < 3):
            wide += 1
            screen = .play
        if ui_button("A second shield", not twin):
            twin = true
            screen = .play
        if ui_button("Bigger blasts", bigger < 3):
            bigger += 1
            screen = .play
        if ui_button("Mend the core", core < 3):
            core += 1
            screen = .play
        ui_end()
    else if screen == .over:
        text_centered("the core is lost", vec2(640, 150), 48)
        text_centered("{score}   (best {best})", vec2(640, 220), 36)
        ui_begin("over", vec2(640, 520))
        if ui_button("Again"): start()
        ui_end()

window("Little Rebound", 1280, 720)
```

Every ten turrets the game stops on a menu of upgrades. `ui_button("A second shield", not
twin)` is a button that can only be chosen while it is still worth taking. The upgrades only
change a few numbers, and the rest of the game reads them: the shield's width comes from
`half()` now, the blasts' size from `bigger`, and `shield_offset` looks for a second shield
across the core when there is one.

## 8. Sound and polish

```gdscript
# step 8: upgrades, sound and polish
build:
    name = "Little Rebound"             # (save_data keeps data under the program's name)

const CORE_R = 30.0
const ORBIT_R = 100.0                   # the shield's distance from the core
const SHIELD_HALF = 0.4                 # half the shield's width, as an angle (radians)
const TURN = 7.0                        # how fast the shield turns (radians a second)
const DEFLECT = 0.7                     # how far a catch at the shield's edge turns a bolt
const BLAST_R = 100.0
CENTER = vec2(640, 360)

struct Turret:
    pos: vec2
    cool: f64                           # seconds until it fires
    alive = true

struct Bolt:
    pos: vec2
    vel: vec2
    from: vec2                          # where it was fired from
    mine = false                        # sent back by the shield
    bank = false                        # sent to a turret that did not fire it
    alive = true

struct Blast:
    pos: vec2
    r: f64
    depth: int                          # 0: a bolt hit the turret; 1, 2, ...: another blast did
    age = 0.0
    done = false                        # it has set off the turrets near it

enum Screen: title, play, upgrade, over
screen = Screen.title
best = to_int(load_data("best") ?? "") ?? 0

turrets: Turret[]
bolts: Bolt[]
blasts: Blast[]
sparks = Particles(gravity = vec2(0, 0), drag = 3.0)
shield = -PI / 2.0                      # the shield's angle: straight up
core = 3                                # rings the core has left
score = 0
streak = 0                              # catches in a row
kills = 0
time = 0.0
spawn = 0.0                             # seconds until the next turrets come
shake = 0.0
wide = 0                                # upgrades taken
twin = false
bigger = 0
next_upgrade = 8                        # at this many turrets destroyed

snd_catch = tone(523.0, 0.15, .triangle, 0.4, 0.001, 0.12)
snd_boom = mix([tone(80.0, 0.6, .noise, 0.5, 0.001, 0.55, 0.3), tone(130.0, 0.4, .sine, 0.5, 0.001, 0.35, 0.35)])
snd_hit = sfx_hit()
bass = melody_loop("A2 . A3 A2 . A2 G3 A2 F2 . F3 F2 . F2 E3 F2 C3 . C4 C3 . C3 B3 C3 G2 . G3 G2 . G2 B2 D3", 124.0, .saw, 0.06)
tune = melody_loop("E5 - - - D5 - C5 - A4 - - - - - - - G4 - - - A4 - C5 - D5 - - - - - E5 -", 124.0, .triangle, 0.05)
music = mix([bass, tune])

# the point at angle a, distance r from the core
polar = (a: f64, r: f64) -> vec2: CENTER + from_angle(a) * f32(r)
# an angle as -pi .. pi (the short way round)
wrap = (a: f64) -> f64: mod(a + PI, TAU) - PI
mult = () -> int: min(1 + streak / 4, 8)
half = () -> f64: SHIELD_HALF * (1.0 + 0.3 * f64(wide))

start = ():
    turrets.clear()
    bolts.clear()
    blasts.clear()
    shield = -PI / 2.0
    core = 3
    score = 0
    streak = 0
    kills = 0
    time = 0.0
    spawn = 0.5
    wide = 0
    twin = false
    bigger = 0
    next_upgrade = 8
    screen = .play

# one to three turrets side by side, somewhere around the core
add_turrets = ():
    a = random(0.0, TAU)
    r = random(200.0, 290.0)
    loop i in [0..random_int(1, 4)):
        p = polar(a + 0.3 * f64(i), r)
        if not turrets.any((t): length(t.pos - p) < 60.0): turrets.push(Turret(p, random(1.0, 2.5)))

# where a bolt crossing the shield's ring at angle a meets a shield: -1 (one edge) to 1 (the
# other), or -9: no shield there
shield_offset = (a: f64) -> f64:
    d = wrap(a - shield)
    if abs(d) <= half(): return d / half()
    if twin:
        d = wrap(a - shield - PI)
        if abs(d) <= half(): return d / half()
    -9.0

# what a bolt leaving p at angle dir is headed for: the turret nearest that line, or far away
aim = (p: vec2, dir: f64) -> vec2:
    goal = p + from_angle(dir) * 1000.0
    nearest = 0.5
    loop t in turrets:
        d = abs(wrap(angle(t.pos - p) - dir))
        if d < nearest:
            nearest = d
            goal = t.pos
    goal

catch = (b: mut Bolt, off: f64):
    # straight back out from the middle of the shield; turned, from nearer its edges
    goal = aim(b.pos, angle(b.pos - CENTER) + off * DEFLECT)
    b.mine = true
    b.bank = goal != b.from
    b.vel = normalize(goal - b.pos) * 700.0
    streak += 1
    play(snd_catch, 0.5, pitch = 1.0 + 0.06 * f64(min(streak, 20)))
    emit(sparks, b.pos, 12, 250.0, rgba(0.5, 1, 1, 1), 0.3, 4.0)

destroy = (t: mut Turret, depth: int, bank: bool):
    t.alive = false
    kills += 1
    points = 100 * mult() * (depth + 1)
    if bank: points *= 2
    score += points
    blasts.push(Blast(t.pos, BLAST_R * (1.0 + 0.3 * f64(bigger)), depth))
    emit(sparks, t.pos, 40, 450.0, rgba(1, 0.45, 0.4, 1), 0.7, 6.0)
    shake = max(shake, 8.0 + 3.0 * f64(depth))
    play(snd_boom, 0.5, pitch = 1.0 + 0.15 * f64(depth))

hit_core = ():
    core -= 1
    streak = 0
    shake = 25.0
    play(snd_hit)
    emit(sparks, CENTER, 60, 400.0, rgba(1, 0.3, 0.4, 1), 0.9, 7.0)
    if core <= 0:
        if score > best:
            best = score
            save_data("best", "{best}")
        screen = .over

update = (dt: f64):
    update(sparks, dt)
    shake = max(shake - dt * 40.0, 0.0)
    if screen != .play: return
    time += dt
    # the shield
    if key_down(.left) or key_down(.a): shield = wrap(shield - TURN * dt)
    if key_down(.right) or key_down(.d): shield = wrap(shield + TURN * dt)
    # more turrets, faster bolts, as time goes on
    spawn -= dt
    if spawn <= 0.0 and turrets.len() < 3 + int(time / 15.0):
        add_turrets()
        spawn = max(4.0 - time * 0.02, 1.5)
    speed = min(180.0 + time, 300.0)
    loop mut t in turrets:
        t.cool -= dt
        if t.cool <= 0.0:
            t.cool = random(2.5, 4.0)
            if bolts.len() < 3 + int(time / 20.0):
                bolts.push(Bolt(t.pos, normalize(CENTER - t.pos) * f32(speed), t.pos))
    # the bolts
    loop mut b in bolts:
        before = length(b.pos - CENTER)
        b.pos += b.vel * f32(dt)
        d = length(b.pos - CENTER)
        if b.mine:
            loop mut t in turrets:
                if t.alive and length(t.pos - b.pos) < 22.0:
                    destroy(t, 0, b.bank)
                    b.alive = false
            if d > 800.0: b.alive = false
        else if before > ORBIT_R and d <= ORBIT_R and shield_offset(angle(b.pos - CENTER)) > -2.0:
            catch(b, shield_offset(angle(b.pos - CENTER)))
        else if d < CORE_R:
            b.alive = false
            hit_core()
    # blasts set off the turrets near them, a moment later: chains
    i = 0
    loop i < blasts.len():
        blasts[i].age += dt
        if not blasts[i].done and blasts[i].age > 0.1:
            blasts[i].done = true
            x = blasts[i]
            loop mut t in turrets:
                if t.alive and length(t.pos - x.pos) < x.r: destroy(t, x.depth + 1, false)
        i += 1
    bolts = bolts.filter((b): b.alive)
    turrets = turrets.filter((t): t.alive)
    blasts = blasts.filter((x): x.age < 0.6)
    if kills >= next_upgrade and screen == .play:
        next_upgrade += 10
        screen = .upgrade

draw_shield = (a: f64):
    blend(.add)
    arc(CENTER, ORBIT_R, 28, a - half(), a + half(), rgba(0.35, 0.95, 1, 0.15))
    blend(.alpha)
    arc(CENTER, ORBIT_R, 9, a - half(), a + half(), rgb(0.35, 0.95, 1))

draw = ():
    clear(rgb(0.01, 0.02, 0.05))
    push_transform()
    translate(random(-shake, shake), random(-shake, shake))
    ring(CENTER, ORBIT_R, 2, rgba(0.35, 0.95, 1, 0.1))
    ring(CENTER, 310, 1, rgba(0.6, 0.8, 1, 0.08))
    loop t in turrets:
        # a turret glows just before it fires
        glow = clamp(1.0 - t.cool / 0.7, 0.0, 1.0)
        blend(.add)
        circle_gradient(t.pos, 40, rgba(1, 0.6, 0.3, f32(0.1 + 0.4 * glow)), rgba(1, 0.4, 0.3, 0))
        blend(.alpha)
        a = angle(CENTER - t.pos)       # a triangle pointing at the core
        tip = t.pos + from_angle(a) * 22.0
        triangle(tip, t.pos + from_angle(a + 2.4) * 17.0, t.pos + from_angle(a - 2.4) * 17.0, rgb(1, 0.33, 0.42))
    blend(.add)
    loop x in blasts:
        k = x.age / 0.6
        ring(x.pos, x.r * ease_out(min(k * 1.5, 1.0)), 10.0 * (1.0 - k) + 1.0, rgba(1, 0.7, 0.3, f32(1.0 - k)))
    loop b in bolts:
        c = rgba(1, 0.72, 0.28, 0.6)
        if b.mine: c = rgba(0.85, 1, 1, 0.6)
        circle_gradient(b.pos, 20, c, with_alpha(c, 0))
    circle_gradient(CENTER, 140, rgba(0.4, 0.9, 1, 0.25), rgba(0.4, 0.9, 1, 0))
    blend(.alpha)
    loop b in bolts: circle(b.pos, 6, rgb(1, 0.95, 0.8))
    circle(CENTER, CORE_R, rgb(0.85, 0.98, 1))
    loop i in [0..core): ring(CENTER, CORE_R + 9.0 + 7.0 * f64(i), 3, rgba(0.35, 0.95, 1, 0.8))
    if screen != .over:
        draw_shield(shield)
        if twin: draw_shield(shield + PI)
    draw(sparks)
    pop_transform()
    text("{score}   x{mult()}", vec2(24, 20), 36)
    if screen != .play: rect(0, 0, 1280, 720, rgba(0, 0.01, 0.03, 0.6))      # (dim the arena behind a menu)
    if screen == .title:
        text_centered("LITTLE REBOUND", vec2(640, 150), 80)
        text_centered("turn the shield (left / right) to catch the bolts", vec2(640, 220), 26)
        ui_begin("title", vec2(640, 520))
        if ui_button("Play"): start()
        if best > 0: ui_text("best {best}")
        ui_end()
    else if screen == .upgrade:
        text_centered("choose an upgrade", vec2(640, 150), 48)
        ui_begin("upgrade", vec2(640, 440))
        if ui_button("A wider shield", wide < 3):
            wide += 1
            screen = .play
        if ui_button("A second shield", not twin):
            twin = true
            screen = .play
        if ui_button("Bigger blasts", bigger < 3):
            bigger += 1
            screen = .play
        if ui_button("Mend the core", core < 3):
            core += 1
            screen = .play
        ui_end()
    else if screen == .over:
        text_centered("the core is lost", vec2(640, 150), 48)
        text_centered("{score}   (best {best})", vec2(640, 220), 36)
        ui_begin("over", vec2(640, 520))
        if ui_button("Again"): start()
        ui_end()

window("Little Rebound", 1280, 720)
play(music, 0.6, looping = true)
```

Every sound is made by the program: `tone` is a note of a waveform (sine, square, triangle,
saw or noise) with an attack and a release, and `mix` plays several at once. A catch's note
climbs with the streak (`pitch`), and the explosions go up with the chain. `melody_loop` writes
a tune from note names, made to repeat without a seam: a bass line and a melody, mixed.

Glow is additive blending: between `blend(.add)` and `blend(.alpha)`, colors add up instead of
covering each other, and `circle_gradient` fades from a color to nothing. The most useful glow is
the turrets': a turret lights up for 0.7 s before it fires, so you can be there in time.

## 9. From here to Rebound

[Rebound](../examples/rebound/rebound.jo) is this game, grown. It has:

- turrets of five kinds (bursts, orbiters that move around the ring, splitters whose bolts split
  in two, armored ones that take two hits) that arrive in groups;
- a firing schedule that never sends more than the shield can reach in time;
- returns that steer after their turret, upgrade cards, mouse and gamepad control, and settings;
- an autopilot that plays behind the title (with a reaction delay, it is also how the
  difficulty was tested).

Run it with `sloppy watch rebound.jo` and change its tuning constants while it runs: the game
picks up the new numbers without restarting. Or change them in
[the playground](https://sloppy-lang.org/playground/#example=rebound).

To share a game, `sloppy build game.jo --target wasm` makes one web page, and
`--target windows` a Windows program: see [sharing](TUTORIAL.md#9-sharing-it) in the first
tutorial.
