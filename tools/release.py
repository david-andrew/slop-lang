#!/usr/bin/env python3
"""Package a release of Jot (needs bin/jot, built by tools/bootstrap.sh) into build/release:
  jot-linux-x86_64.tar.gz          jot-<version>/{bin/jot, lib/, editors/jot.vsix, README.md}
  jot-linux-x86_64.tar.gz.sha256   its checksum (tools/install.sh checks it)
  jot-<version>.vsix               the VS Code / Cursor extension
usage: tools/release.py [--tag vX.Y.Z]   (--tag: fail unless it is the compiler's version)"""
import hashlib, io, os, shutil, subprocess, sys, tarfile

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, "build", "release")
jot = os.path.join(root, "bin", "jot")
version = subprocess.run([jot, "--version"], capture_output=True, text=True, check=True).stdout.split()[-1]
if "--tag" in sys.argv:
    tag = sys.argv[sys.argv.index("--tag") + 1]
    if tag != "v" + version:
        sys.exit(f"the tag {tag} is not the compiler's version {version} (JOT_VERSION in compiler/main.jot)")
if os.path.exists(out): shutil.rmtree(out)
os.makedirs(out)
vsix = os.path.join(out, f"jot-{version}.vsix")
subprocess.run([sys.executable, os.path.join(root, "tools", "vsix.py"), vsix], check=True, capture_output=True)

top = f"jot-{version}"
tgz = os.path.join(out, "jot-linux-x86_64.tar.gz")
def add(tar, path, arc, mode=None):
    info = tar.gettarinfo(path, arc)
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mtime = 0
    if mode is not None: info.mode = mode
    if info.isfile():
        with open(path, "rb") as f: tar.addfile(info, f)
    else: tar.addfile(info)
with tarfile.open(tgz, "w:gz", format=tarfile.PAX_FORMAT) as tar:
    add(tar, jot, f"{top}/bin/jot", 0o755)
    for d, dirs, names in os.walk(os.path.join(root, "lib")):
        dirs.sort()
        for n in sorted(names):
            full = os.path.join(d, n)
            add(tar, full, f"{top}/lib/" + os.path.relpath(full, os.path.join(root, "lib")), 0o644)
    add(tar, vsix, f"{top}/editors/jot.vsix", 0o644)
    add(tar, os.path.join(root, "README.md"), f"{top}/README.md", 0o644)
    add(tar, os.path.join(root, "LICENSE"), f"{top}/LICENSE", 0o644)
digest = hashlib.sha256(open(tgz, "rb").read()).hexdigest()
open(tgz + ".sha256", "w").write(f"{digest}  jot-linux-x86_64.tar.gz\n")
print(f"jot {version}: {tgz} ({os.path.getsize(tgz) // 1024} KB), {vsix}")
