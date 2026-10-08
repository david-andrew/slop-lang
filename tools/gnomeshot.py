#!/usr/bin/env python3
"""Run a program in a headless GNOME Shell (nothing appears on the screen; a throwaway HOME, so
no settings or autostart programs are touched) and screenshot the desktop, optionally after
injecting input. For checking how windows look and behave on GNOME: decorations, fullscreen,
input, the clipboard.

usage: tools/gnomeshot.py out.png [--monitor 1920x1080] [--scale 1.0] [--delay 3] [--input ACTIONS] -- program args...
  ACTIONS: comma-separated move=X;Y (screen pixels), click, type=TEXT, sleep=SECONDS
needs: gnome-shell, pipewire (for --input), dbus-run-session, python3-gobject"""
import os, subprocess, sys, tempfile, time


def main():
    a = sys.argv[1:]
    if "--" not in a or len(a) < 3:
        sys.exit(__doc__)
    cut = a.index("--")
    opts, cmd = a[:cut], a[cut + 1:]
    out = os.path.abspath(opts[0])
    monitor, delay, actions, scale = "1920x1080", 3.0, "", 1.0
    i = 1
    while i < len(opts):
        if opts[i] == "--monitor": monitor = opts[i + 1]
        elif opts[i] == "--delay": delay = float(opts[i + 1])
        elif opts[i] == "--input": actions = opts[i + 1]
        elif opts[i] == "--scale": scale = float(opts[i + 1])
        i += 2
    if os.environ.get("JOT_GNOMESHOT_INNER") != "1":
        env = dict(os.environ, JOT_GNOMESHOT_INNER="1")
        r = subprocess.run(["dbus-run-session", "--", sys.executable, __file__] + sys.argv[1:], env=env)
        sys.exit(r.returncode)
    inner(out, monitor, delay, actions, cmd, scale)


def inner(out, monitor, delay, actions, cmd, scale):
    import gi
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib
    home = tempfile.mkdtemp(prefix="jot-gnome-")
    env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=home + "/.config", XDG_DATA_HOME=home + "/.local/share",
               XDG_CACHE_HOME=home + "/.cache", XDG_STATE_HOME=home + "/.local/state", XDG_RUNTIME_DIR=home + "/run")
    os.makedirs(env["XDG_RUNTIME_DIR"], mode=0o700)
    for k in ["DISPLAY", "WAYLAND_DISPLAY"]: env.pop(k, None)
    procs = []
    log = open(os.path.join(home, "shell.log"), "w")
    if actions:
        procs.append(subprocess.Popen(["pipewire"], env=env, stdout=log, stderr=log))
        time.sleep(0.5)
    procs.append(subprocess.Popen(["gnome-shell", "--headless", "--wayland", "--no-x11", "--virtual-monitor", monitor,
                                   "--wayland-display", "jot-test"], env=env, stdout=log, stderr=log))
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def call(dest, path, iface, method, args=None):
        return bus.call_sync(dest, path, iface, method, args, None, 0, 10000, None).unpack()

    # (the session starts in the overview)
    for _ in range(100):
        try:
            call("org.gnome.Shell", "/org/gnome/Shell", "org.freedesktop.DBus.Properties", "Set",
                 GLib.Variant("(ssv)", ("org.gnome.Shell", "OverviewActive", GLib.Variant("b", False))))
            break
        except Exception:
            time.sleep(0.1)
    if scale != 1.0:
        # (fractional scales need the experimental setting, as on desktops that use them)
        subprocess.run(["gsettings", "set", "org.gnome.mutter", "experimental-features", "['scale-monitor-framebuffer']"], env=env)
        time.sleep(0.5)
        dc = "org.gnome.Mutter.DisplayConfig"
        serial, monitors, logical, props = call(dc, "/org/gnome/Mutter/DisplayConfig", dc, "GetCurrentState")
        conn = monitors[0][0][0]
        mode = [m for m in monitors[0][1] if m[6].get("is-current")][0]
        scales = mode[5]
        best = min(scales, key=lambda s: abs(s - scale))
        call(dc, "/org/gnome/Mutter/DisplayConfig", dc, "ApplyMonitorsConfig",
             GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})", (serial, 1, [(0, 0, best, 0, True, [(conn, mode[0], {})])], {})))
        time.sleep(1.0)
    # (the shell lets the owners of these names take screenshots)
    for name in ["org.gnome.Screenshot", "org.freedesktop.impl.portal.desktop.gtk", "org.gnome.SettingsDaemon.MediaKeys"]:
        call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName", GLib.Variant("(su)", (name, 4)))
    time.sleep(1.0)
    app = subprocess.Popen(cmd, env=dict(env, WAYLAND_DISPLAY="jot-test"))
    time.sleep(delay)
    if actions:
        rd = "org.gnome.Mutter.RemoteDesktop"
        (sess,) = call(rd, "/org/gnome/Mutter/RemoteDesktop", rd, "CreateSession")
        S = rd + ".Session"
        sid = bus.call_sync(rd, sess, "org.freedesktop.DBus.Properties", "Get", GLib.Variant("(ss)", (S, "SessionId")), None, 0, 5000, None).unpack()[0]
        sc = "org.gnome.Mutter.ScreenCast"
        (scs,) = call(sc, "/org/gnome/Mutter/ScreenCast", sc, "CreateSession", GLib.Variant("(a{sv})", ({"remote-desktop-session-id": GLib.Variant("s", sid)},)))
        (stream,) = call(sc, scs, sc + ".Session", "RecordMonitor", GLib.Variant("(sa{sv})", ("", {})))
        call(rd, sess, S, "Start")
        time.sleep(0.5)
        for act in actions.split(","):
            op, _, arg = act.partition("=")
            if op == "move":
                x, y = map(float, arg.split(";"))
                call(rd, sess, S, "NotifyPointerMotionAbsolute", GLib.Variant("(sdd)", (stream, x, y)))
            elif op == "click":
                call(rd, sess, S, "NotifyPointerButton", GLib.Variant("(ib)", (0x110, True)))
                time.sleep(0.05)
                call(rd, sess, S, "NotifyPointerButton", GLib.Variant("(ib)", (0x110, False)))
            elif op == "type":
                for ch in arg:
                    call(rd, sess, S, "NotifyKeyboardKeysym", GLib.Variant("(ub)", (ord(ch), True)))
                    time.sleep(0.02)
                    call(rd, sess, S, "NotifyKeyboardKeysym", GLib.Variant("(ub)", (ord(ch), False)))
                    time.sleep(0.02)
            elif op == "sleep":
                time.sleep(float(arg))
            time.sleep(0.15)
        time.sleep(1.0)
    call("org.gnome.Shell", "/org/gnome/Shell", "org.freedesktop.DBus.Properties", "Set",
         GLib.Variant("(ssv)", ("org.gnome.Shell", "OverviewActive", GLib.Variant("b", False))))
    time.sleep(0.6)
    ok = call("org.gnome.Shell.Screenshot", "/org/gnome/Shell/Screenshot", "org.gnome.Shell.Screenshot", "Screenshot",
              GLib.Variant("(bbs)", (False, False, out)))[0]
    print(out if ok else "screenshot failed")
    for p in [app] + procs[::-1]:
        p.terminate()
        try: p.wait(timeout=3)
        except subprocess.TimeoutExpired: p.kill()


main()
