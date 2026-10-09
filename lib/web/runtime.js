// Sloppy web runtime: instantiates the embedded wasm module and provides its imports.
"use strict";
const sloppy = (() => {
  const isNode = typeof window === "undefined";
  let mem = null, exports = null;
  const logEl = isNode ? null : document.getElementById("log");
  const dec = new TextDecoder();
  let pending = ["", ""];
  const u8 = () => new Uint8Array(mem.buffer);
  const str = (p, n) => dec.decode(u8().subarray(Number(p), Number(p) + Number(n)));
  function out(fd, text) {
    pending[fd - 1] += text;
    let i;
    while ((i = pending[fd - 1].indexOf("\n")) >= 0) {
      const line = pending[fd - 1].slice(0, i);
      pending[fd - 1] = pending[fd - 1].slice(i + 1);
      if (isNode) (fd === 2 ? process.stderr : process.stdout).write(line + "\n");
      else {
        (fd === 2 ? console.error : console.log)(line);
        if (logEl) { const d = document.createElement("div"); d.textContent = line; if (fd === 2) d.style.color = "#f77"; logEl.appendChild(d); }
      }
    }
  }
  class Exit extends Error { constructor(code) { super("exit " + code); this.code = code; } }
  const env = {
    __wasm_write: (fd, p, n) => out(Number(fd), str(p, n)),
    __wasm_exit: (code) => { throw new Exit(Number(code)); },
    __wasm_now: () => performance.now(),
    __wasm_grow: (n) => BigInt(mem.grow(Number(n))),
    // environment variables: the page's URL parameters (?SLOPPY_STATS=1, or ?stats)
    __wasm_env: (np, nn, op, cap) => {
      const name = str(np, nn);
      let v = null;
      if (isNode) v = process.env[name] ?? null;
      else {
        const q = new URLSearchParams(location.search);
        v = q.get(name);
        if (v === null && name.startsWith("SLOPPY_")) v = q.get(name.slice(4).toLowerCase());
        if (v === "") v = "1";
      }
      if (v === null) return -1n;
      return give(new TextEncoder().encode(v), op, cap);
    },
    // files: the page's own (sloppy.files: path -> Uint8Array), or under node the real ones
    __wasm_read_file: (pp, pn, op, cap) => {
      const d = readFile(str(pp, pn));
      return d === null ? -1n : give(d, op, cap);
    },
    __wasm_write_file: (pp, pn, dp, dn) => {
      const path = str(pp, pn), d = u8().slice(Number(dp), Number(dp) + Number(dn));
      if (nodeFs) { try { nodeFs.writeFileSync(path, d); return 1n; } catch (e) { return 0n; } }
      files[path] = d;
      return 1n;
    },
    __wasm_list_dir: (pp, pn, op, cap) => {
      const path = str(pp, pn).replace(/\/+$/, "");
      let names = null;
      if (nodeFs) { try { names = nodeFs.readdirSync(path); } catch (e) { names = null; } }
      else {
        const seen = new Set();
        for (const f of Object.keys(files)) if (f.startsWith(path + "/")) seen.add(f.slice(path.length + 1).split("/")[0]);
        names = seen.size > 0 ? [...seen] : null;
      }
      return names === null ? -1n : give(new TextEncoder().encode(names.join("\n")), op, cap);
    },
    __wasm_args: (op, cap) => give(new TextEncoder().encode(args.join("\0")), op, cap),
  };
  // (copy bytes to a buffer in wasm memory; the size there is the length needed)
  function give(b, op, cap) {
    u8().set(b.subarray(0, Math.min(b.length, Number(cap))), Number(op));
    return BigInt(b.length);
  }
  const files = {};
  const nodeFs = isNode && typeof sloppyFs !== "undefined" ? sloppyFs : null;
  let args = isNode && typeof sloppyArgs !== "undefined" ? sloppyArgs : ["page"];
  function readFile(path) {
    if (nodeFs) { try { return new Uint8Array(nodeFs.readFileSync(path)); } catch (e) { return null; } }
    return files[path] ?? null;
  }
  const extra = [];   // modules (graphics, audio, input) register their imports here
  function run(bytes) {
    for (const f of extra) Object.assign(env, f.imports(() => mem, () => exports));
    const mod = new WebAssembly.Module(bytes);
    const inst = new WebAssembly.Instance(mod, { env: new Proxy(env, {
      get: (t, k) => k in t ? t[k] : (() => { throw new Error("missing import: " + String(k)); }) }) });
    exports = inst.exports;
    mem = exports.memory;
    try {
      exports.__start();
      for (const f of extra) if (f.start) f.start(exports);
    } catch (e) {
      if (e instanceof Exit) { flush(); if (isNode) process.exitCode = e.code; return; }
      flush();
      if (isNode) { console.error(e.stack || e); process.exitCode = 101; } else throw e;
    }
    flush();
  }
  function flush() { for (let fd = 1; fd <= 2; fd++) if (pending[fd - 1]) { out(fd, "\n"); } }
  return { run, extra, env, Exit, files, setArgs: (a) => { args = a; } };
})();
