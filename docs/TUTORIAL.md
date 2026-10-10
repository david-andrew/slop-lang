# Make a game

This tutorial builds **Firefly**, a small platformer: a firefly hops across a dusky world,
gathering lights and dodging thorns on the way to a lantern. Each step is a whole program that
runs; on the website, "Run it in the playground" opens it in your browser, and with Sloppy
installed `sloppy firefly.jo` runs it in a window. (The [second tutorial](TUTORIAL_REBOUND.md)
builds an arcade game, a small version of
[Rebound](https://github.com/david-andrew/sloppy-lang/blob/master/examples/rebound/rebound.jo).)

## 1. A window

```gdscript
# step 1: a window, and something in it
draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    circle(vec2(640, 360), 16, rgb(1, 0.9, 0.5))

window("Firefly", 1280, 720)
```

A program with a `draw` function is a game: Sloppy opens the window (`window` gives its title
and size) and calls `draw` 60 times a second (or as often as the screen refreshes). The screen is
1280 x 720 units whatever the window's real size; `(0, 0)` is the top left and y goes down.

## 2. Moving

```gdscript
# step 2: moving with the keyboard (or a gamepad)
pos = vec2(640, 360)

update = (dt: f64):
    pos += input_axis() * f32(400 * dt)

draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    circle(pos, 16, rgb(1, 0.9, 0.5))

window("Firefly", 1280, 720)
```

`update` runs before each frame is drawn, with `dt`: the seconds since the last one. Moving by
`speed * dt` makes the speed the same on every computer. `input_axis()` is the direction the
arrow keys, WASD or a gamepad's stick point in, as a `vec2` from -1 to 1.

(`f32(...)`: positions are `vec2`s of 32-bit floats, while `dt` and most numbers are 64-bit
`f64`s. Sloppy converts between number types only when you ask; `f32(x)` asks.)

## 3. Gravity and jumping

```gdscript
# step 3: gravity, ground and jumping
const GRAVITY = 1800.0
const JUMP = 700.0
const GROUND = 600.0

pos = vec2(640, 300)
vel = vec2(0, 0)

update = (dt: f64):
    vel.x = input_axis().x * 400.0
    vel.y += f32(GRAVITY * dt)
    on_ground = pos.y >= GROUND
    if on_ground and key_pressed(.space): vel.y = f32(-JUMP)
    pos += vel * f32(dt)
    if pos.y > GROUND:
        pos.y = GROUND
        vel.y = 0.0

draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    rect(0, GROUND + 16.0, 1280, 120, rgb(0.2, 0.18, 0.26))
    circle(pos, 16, rgb(1, 0.9, 0.5))

window("Firefly", 1280, 720)
```

Velocity is how far the firefly moves each second; gravity adds to it each frame, and a jump
sets it to point up. `key_pressed` is true only in the frame a key goes down (`key_down` is true
as long as it is held).

## 4. Platforms

```gdscript
# step 4: platforms to stand on
const GRAVITY = 1800.0
const JUMP = 700.0
const SIZE = 16.0

platforms = [
    Rect(0, 616, 1280, 120),            # the ground: x, y, width, height
    Rect(300, 480, 200, 24),
    Rect(620, 380, 200, 24),
    Rect(940, 280, 200, 24),
]
pos = vec2(100, 500)
vel = vec2(0, 0)
on_ground = false

# the box the firefly takes up, when it is at p
box = (p: vec2) -> Rect: Rect(p.x - SIZE, p.y - SIZE, SIZE * 2.0, SIZE * 2.0)

blocked = (p: vec2) -> bool:
    loop r in platforms:
        if overlaps(box(p), r): return true
    false

update = (dt: f64):
    vel.x = input_axis().x * 400.0
    vel.y += f32(GRAVITY * dt)
    if on_ground and key_pressed(.space): vel.y = f32(-JUMP)
    # move across, then up or down, each only as far as nothing is in the way
    next = pos + vec2(vel.x * f32(dt), 0)
    if not blocked(next): pos = next
    next = pos + vec2(0, vel.y * f32(dt))
    on_ground = false
    if blocked(next):
        if vel.y > 0.0: on_ground = true
        vel.y = 0.0
    else: pos = next

draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    loop r in platforms: rect(r.x, r.y, r.w, r.h, rgb(0.25, 0.22, 0.32))
    circle(pos, SIZE, rgb(1, 0.9, 0.5))

window("Firefly", 1280, 720)
```

`Rect(x, y, width, height)` is a rectangle, and `overlaps` says whether two touch. The firefly
moves across and then up or down, each only if nothing is in the way, so it slides along walls
and lands on top of platforms. Landing is what makes `on_ground` true, so jumps only start from
the ground.

## 5. Things to collect

```gdscript
# step 5: lights to collect, a count, and a sound
const GRAVITY = 1800.0
const JUMP = 700.0
const SIZE = 16.0

platforms = [
    Rect(0, 616, 1280, 120),            # the ground: x, y, width, height
    Rect(300, 480, 200, 24),
    Rect(620, 380, 200, 24),
    Rect(940, 280, 200, 24),
]
lights = [vec2(400, 440), vec2(720, 340), vec2(1040, 240), vec2(1180, 560)]
collected = 0
chime = sfx_chime()                     # a ready-made sound (also: sfx_jump, sfx_hit, tone, melody)

pos = vec2(100, 500)
vel = vec2(0, 0)
on_ground = false

# the box the firefly takes up, when it is at p
box = (p: vec2) -> Rect: Rect(p.x - SIZE, p.y - SIZE, SIZE * 2.0, SIZE * 2.0)

blocked = (p: vec2) -> bool:
    loop r in platforms:
        if overlaps(box(p), r): return true
    false

update = (dt: f64):
    vel.x = input_axis().x * 400.0
    vel.y += f32(GRAVITY * dt)
    if on_ground and key_pressed(.space): vel.y = f32(-JUMP)
    # move across, then up or down, each only as far as nothing is in the way
    next = pos + vec2(vel.x * f32(dt), 0)
    if not blocked(next): pos = next
    next = pos + vec2(0, vel.y * f32(dt))
    on_ground = false
    if blocked(next):
        if vel.y > 0.0: on_ground = true
        vel.y = 0.0
    else: pos = next
    # take the lights the firefly touches
    i = 0
    loop i < lights.len():
        if circles_overlap(pos, SIZE, lights[i], 10.0):
            lights.remove(i)
            collected += 1
            play(chime)
        else: i += 1

draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    loop r in platforms: rect(r.x, r.y, r.w, r.h, rgb(0.25, 0.22, 0.32))
    loop l in lights: circle(l, 8, rgb(1, 0.8, 0.4))
    circle(pos, SIZE, rgb(1, 0.9, 0.5))
    text("lights {collected}", vec2(24, 20), 28)

window("Firefly", 1280, 720)
```

`circles_overlap` checks whether the firefly touches a light; taken lights are removed from the
array (the index only moves on when nothing was removed). `sfx_chime()` makes a sound once, at
the start; `play` plays it. `text` draws on the screen, and `{collected}` puts a value into a
string.

## 6. A bigger world

```gdscript
# step 6: a bigger world, a camera that follows, and thorns
const GRAVITY = 1800.0
const JUMP = 700.0
const SIZE = 16.0
const WORLD_W = 6000.0

platforms: Rect[]
thorns: Rect[]
lights: vec2[]
collected = 0
chime = sfx_chime()
ouch = sfx_hit()

pos = vec2(100, 500)
vel = vec2(0, 0)
on_ground = false
cam = vec2(0, 0)

# a new world: stretches of ground with gaps, ledges above them, thorns and lights
make_world = ():
    seed_random(7)                      # the same world every time
    x = 0.0
    loop x < WORLD_W:
        w = random(400.0, 900.0)
        y = 616.0 + random(-50.0, 50.0)
        platforms.push(Rect(f32(x), f32(y), f32(w), 400))
        lights.push(vec2(f32(x + w / 2.0), f32(y - 40.0)))
        if random() < 0.7:
            lx = x + random(50.0, w - 250.0)
            platforms.push(Rect(f32(lx), f32(y - 150.0), 200, 24))
            lights.push(vec2(f32(lx + 100.0), f32(y - 190.0)))
        if x > 500.0 and random() < 0.5:
            thorns.push(Rect(f32(x + w - 160.0), f32(y - 14.0), 80, 14))
        x += w + random(80.0, 200.0)

box = (p: vec2) -> Rect: Rect(p.x - SIZE, p.y - SIZE, SIZE * 2.0, SIZE * 2.0)

blocked = (p: vec2) -> bool:
    loop r in platforms:
        if overlaps(box(p), r): return true
    false

# back to the start (the lights stay taken)
restart = ():
    play(ouch)
    pos = vec2(100, 400)
    vel = vec2(0, 0)

update = (dt: f64):
    vel.x = input_axis().x * 400.0
    vel.y += f32(GRAVITY * dt)
    if on_ground and key_pressed(.space): vel.y = f32(-JUMP)
    next = pos + vec2(vel.x * f32(dt), 0)
    if not blocked(next): pos = next
    next = pos + vec2(0, vel.y * f32(dt))
    on_ground = false
    if blocked(next):
        if vel.y > 0.0: on_ground = true
        vel.y = 0.0
    else: pos = next
    i = 0
    loop i < lights.len():
        if circles_overlap(pos, SIZE, lights[i], 10.0):
            lights.remove(i)
            collected += 1
            play(chime)
        else: i += 1
    loop t in thorns:
        if overlaps(box(pos), t): restart()
    if pos.y > 1200.0: restart()               # fell into a gap
    # the camera eases toward the firefly
    cam = approach(cam, vec2(pos.x - 640.0, 0), 5.0, dt)

draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    push_transform()
    translate(f64(-cam.x), f64(-cam.y))        # draw the world as the camera sees it
    loop r in platforms: rect(r.x, r.y, r.w, r.h, rgb(0.25, 0.22, 0.32))
    loop t in thorns: rect(t.x, t.y, t.w, t.h, rgb(0.6, 0.15, 0.25))
    loop l in lights: circle(l, 8, rgb(1, 0.8, 0.4))
    circle(pos, SIZE, rgb(1, 0.9, 0.5))
    pop_transform()
    text("lights {collected}", vec2(24, 20), 28)    # (after pop_transform: on the screen, not in the world)

window("Firefly", 1280, 720)
make_world()
```

The world is made by code now: stretches of ground of random widths with gaps between them,
ledges above, thorns and lights. `seed_random(7)` makes the random numbers the same each run,
so the world is too (change the 7 for another). A camera follows the firefly: `translate`
shifts everything drawn after it, and `approach` eases the camera toward where it should be, so
it glides instead of jerking. The count is drawn after `pop_transform`, so it stays put on the
screen.

## 7. A beginning and an end

```gdscript
# step 7: a title screen, a goal, and a best time that is kept
build:
    name = "Firefly"                    # (save_data keeps data under the program's name)

const GRAVITY = 1800.0
const JUMP = 700.0
const SIZE = 16.0
const WORLD_W = 6000.0

enum Screen: title, play, won
screen = Screen.title
time = 0.0
best = to_float(load_data("best") ?? "") ?? 0.0     # 0: no best time yet

platforms: Rect[]
thorns: Rect[]
lights: vec2[]
collected = 0
chime = sfx_chime()
ouch = sfx_hit()

pos = vec2(100, 500)
vel = vec2(0, 0)
on_ground = false
cam = vec2(0, 0)

# a new world: stretches of ground with gaps, ledges above them, thorns and lights
make_world = ():
    seed_random(7)                      # the same world every time
    x = 0.0
    loop x < WORLD_W:
        w = random(400.0, 900.0)
        y = 616.0 + random(-50.0, 50.0)
        platforms.push(Rect(f32(x), f32(y), f32(w), 400))
        lights.push(vec2(f32(x + w / 2.0), f32(y - 40.0)))
        if random() < 0.7:
            lx = x + random(50.0, w - 250.0)
            platforms.push(Rect(f32(lx), f32(y - 150.0), 200, 24))
            lights.push(vec2(f32(lx + 100.0), f32(y - 190.0)))
        if x > 500.0 and random() < 0.5:
            thorns.push(Rect(f32(x + w - 160.0), f32(y - 14.0), 80, 14))
        x += w + random(80.0, 200.0)

box = (p: vec2) -> Rect: Rect(p.x - SIZE, p.y - SIZE, SIZE * 2.0, SIZE * 2.0)

blocked = (p: vec2) -> bool:
    loop r in platforms:
        if overlaps(box(p), r): return true
    false

start = ():
    platforms.clear()
    thorns.clear()
    lights.clear()
    make_world()
    collected = 0
    time = 0.0
    pos = vec2(100, 400)
    vel = vec2(0, 0)
    screen = .play

# back to the start (the lights stay taken)
restart = ():
    play(ouch)
    pos = vec2(100, 400)
    vel = vec2(0, 0)

update = (dt: f64):
    if screen != .play: return
    time += dt
    vel.x = input_axis().x * 400.0
    vel.y += f32(GRAVITY * dt)
    if on_ground and key_pressed(.space): vel.y = f32(-JUMP)
    next = pos + vec2(vel.x * f32(dt), 0)
    if not blocked(next): pos = next
    next = pos + vec2(0, vel.y * f32(dt))
    on_ground = false
    if blocked(next):
        if vel.y > 0.0: on_ground = true
        vel.y = 0.0
    else: pos = next
    i = 0
    loop i < lights.len():
        if circles_overlap(pos, SIZE, lights[i], 10.0):
            lights.remove(i)
            collected += 1
            play(chime)
        else: i += 1
    loop t in thorns:
        if overlaps(box(pos), t): restart()
    if pos.y > 1200.0: restart()               # fell into a gap
    # the camera eases toward the firefly
    cam = approach(cam, vec2(pos.x - 640.0, 0), 5.0, dt)
    # the lantern at the end of the world
    if pos.x > WORLD_W - 200.0:
        if best == 0.0 or time < best:
            best = time
            save_data("best", "{best}")
        screen = .won

draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    push_transform()
    translate(f64(-cam.x), f64(-cam.y))        # draw the world as the camera sees it
    loop r in platforms: rect(r.x, r.y, r.w, r.h, rgb(0.25, 0.22, 0.32))
    loop t in thorns: rect(t.x, t.y, t.w, t.h, rgb(0.6, 0.15, 0.25))
    loop l in lights: circle(l, 8, rgb(1, 0.8, 0.4))
    circle(vec2(f32(WORLD_W - 150.0), 520), 30, rgb(1, 0.7, 0.3))     # the lantern
    circle(pos, SIZE, rgb(1, 0.9, 0.5))
    pop_transform()
    if screen == .title:
        text_centered("FIREFLY", vec2(640, 200), 96)
        text_centered("reach the lantern", vec2(640, 280), 28)
        ui_begin("title", vec2(640, 400))
        if ui_button("Play"): start()
        if best > 0.0: ui_text("best {best:.1} s")
        ui_end()
    else:
        text("lights {collected}   time {time:.1}", vec2(24, 20), 28)    # (after pop_transform: on the screen)
    if screen == .won:
        text_centered("you made it in {time:.1} s", vec2(640, 220), 56)
        ui_begin("won", vec2(640, 340))
        if ui_button("Again"): start()
        ui_end()

window("Firefly", 1280, 720)
make_world()
```

An `enum` says which screen the game is on. The menus come from `ui_begin` and `ui_button`:
each button is drawn every frame, and is true in the frame it is chosen (with the arrow keys and
enter, a gamepad, or a click). `save_data` and `load_data` keep the best time between runs:
in a file in your user folder, or in the browser's storage on the web. `build: name = "Firefly"`
names the program, so its saved data has a place of its own.

## 8. Polish

```gdscript
# step 8: polish: glow, sparks, music
build:
    name = "Firefly"                    # (save_data keeps data under the program's name)

const GRAVITY = 1800.0
const JUMP = 700.0
const SIZE = 16.0
const WORLD_W = 6000.0

enum Screen: title, play, won
screen = Screen.title
time = 0.0
best = to_float(load_data("best") ?? "") ?? 0.0     # 0: no best time yet

platforms: Rect[]
thorns: Rect[]
lights: vec2[]
collected = 0
chime = sfx_chime()
ouch = sfx_hit()
hop = sfx_jump()
sparks = Particles(gravity = vec2(0, 300), drag = 1.0)
music = melody("E4 - G4 B4 - A4 G4 - E4 - D4 E4 - - . . C4 - E4 G4 - F#4 E4 - B3 - C4 D4 - - . .", 90.0, .triangle, 0.15)

pos = vec2(100, 500)
vel = vec2(0, 0)
on_ground = false
cam = vec2(0, 0)

# a new world: stretches of ground with gaps, ledges above them, thorns and lights
make_world = ():
    seed_random(7)                      # the same world every time
    x = 0.0
    loop x < WORLD_W:
        w = random(400.0, 900.0)
        y = 616.0 + random(-50.0, 50.0)
        platforms.push(Rect(f32(x), f32(y), f32(w), 400))
        lights.push(vec2(f32(x + w / 2.0), f32(y - 40.0)))
        if random() < 0.7:
            lx = x + random(50.0, w - 250.0)
            platforms.push(Rect(f32(lx), f32(y - 150.0), 200, 24))
            lights.push(vec2(f32(lx + 100.0), f32(y - 190.0)))
        if x > 500.0 and random() < 0.5:
            thorns.push(Rect(f32(x + w - 160.0), f32(y - 14.0), 80, 14))
        x += w + random(80.0, 200.0)

box = (p: vec2) -> Rect: Rect(p.x - SIZE, p.y - SIZE, SIZE * 2.0, SIZE * 2.0)

blocked = (p: vec2) -> bool:
    loop r in platforms:
        if overlaps(box(p), r): return true
    false

start = ():
    platforms.clear()
    thorns.clear()
    lights.clear()
    make_world()
    collected = 0
    time = 0.0
    pos = vec2(100, 400)
    vel = vec2(0, 0)
    screen = .play

# back to the start (the lights stay taken)
restart = ():
    play(ouch)
    pos = vec2(100, 400)
    vel = vec2(0, 0)

update = (dt: f64):
    if screen != .play: return
    time += dt
    vel.x = input_axis().x * 400.0
    vel.y += f32(GRAVITY * dt)
    if on_ground and key_pressed(.space):
        vel.y = f32(-JUMP)
        play(hop, 0.5)
    next = pos + vec2(vel.x * f32(dt), 0)
    if not blocked(next): pos = next
    next = pos + vec2(0, vel.y * f32(dt))
    on_ground = false
    if blocked(next):
        if vel.y > 0.0: on_ground = true
        vel.y = 0.0
    else: pos = next
    i = 0
    loop i < lights.len():
        if circles_overlap(pos, SIZE, lights[i], 10.0):
            lights.remove(i)
            collected += 1
            play(chime)
            emit(sparks, pos, 20, 250.0, rgba(1, 0.8, 0.4, 1), 0.7, 4.0)
        else: i += 1
    loop t in thorns:
        if overlaps(box(pos), t): restart()
    if pos.y > 1200.0: restart()               # fell into a gap
    update(sparks, dt)
    # the camera eases toward the firefly
    cam = approach(cam, vec2(pos.x - 640.0, 0), 5.0, dt)
    # the lantern at the end of the world
    if pos.x > WORLD_W - 200.0:
        if best == 0.0 or time < best:
            best = time
            save_data("best", "{best}")
        screen = .won

draw = ():
    clear(rgb(0.1, 0.1, 0.18))
    v = visible_rect()
    rect_gradient(f64(v.x), f64(v.y), f64(v.z), f64(v.w), rgb(0.08, 0.08, 0.2), rgb(0.35, 0.2, 0.3))    # a dusk sky
    push_transform()
    translate(f64(-cam.x), f64(-cam.y))        # draw the world as the camera sees it
    loop r in platforms: rect(r.x, r.y, r.w, r.h, rgb(0.25, 0.22, 0.32))
    loop t in thorns: rect(t.x, t.y, t.w, t.h, rgb(0.6, 0.15, 0.25))
    # glows: drawn with additive blending, so light adds up
    blend(.add)
    loop l in lights: circle_gradient(l, 40, rgba(1, 0.7, 0.3, 0.5), rgba(1, 0.5, 0.2, 0))
    circle_gradient(pos, 90, rgba(1, 0.9, 0.5, 0.5), rgba(1, 0.7, 0.3, 0))
    circle_gradient(vec2(f32(WORLD_W - 150.0), 520), 200, rgba(1, 0.7, 0.3, 0.6), rgba(1, 0.5, 0.2, 0))
    blend(.alpha)
    loop l in lights: circle(l, 6, rgb(1, 0.95, 0.8))
    circle(vec2(f32(WORLD_W - 150.0), 520), 26, rgb(1, 0.85, 0.6))     # the lantern
    circle(pos, SIZE, rgb(1, 0.97, 0.85))
    draw(sparks)
    pop_transform()
    if screen == .title:
        text_centered("FIREFLY", vec2(640, 200), 96)
        text_centered("reach the lantern", vec2(640, 280), 28)
        ui_begin("title", vec2(640, 400))
        if ui_button("Play"): start()
        if best > 0.0: ui_text("best {best:.1} s")
        ui_end()
    else:
        text("lights {collected}   time {time:.1}", vec2(24, 20), 28)    # (after pop_transform: on the screen)
    if screen == .won:
        text_centered("you made it in {time:.1} s", vec2(640, 220), 56)
        ui_begin("won", vec2(640, 340))
        if ui_button("Again"): start()
        ui_end()

window("Firefly", 1280, 720)
make_world()
play(music, 0.6, looping = true)
```

Light that glows: `blend(.add)` makes colors add up instead of covering each other, and
`circle_gradient` fades from a color in the middle to nothing at the edge. `Particles` are
sparks that fly, slow down and fade (`emit` makes some, `update` and `draw` run them). `melody`
writes music from note names, `looping = true` keeps it playing, and a dusk sky behind it all
is one `rect_gradient`.

## 9. Sharing it

```sh
sloppy firefly.jo                                # run it
sloppy build firefly.jo                          # firefly: a program for this system (firefly.exe on Windows)
sloppy build firefly.jo --target windows         # firefly.exe for Windows, from any system
sloppy build firefly.jo --target wasm            # firefly.html: one file that runs in any browser
sloppy build firefly.jo --target wasm -o firefly.zip   # the same, ready to upload to itch.io
```

Each is a single file with nothing to install: send it, or upload it. In the `build:` block,
`icon = "icon.png"` gives the Windows program and the web page an icon.

From here:
- [Make an arcade game](TUTORIAL_REBOUND.md): the second tutorial, a small version of Rebound.
- [The language](language.html): everything Sloppy has, with examples.
- [The library](api.html): drawing, sound, input, 3D, GPU programs and the rest.
- `sloppy watch firefly.jo` keeps the game running while you edit it: save, and the change
  appears without restarting.
