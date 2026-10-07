// Jot web runtime: instantiates the embedded wasm module and provides its imports.
"use strict";
const jot = (() => {
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
  };
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
  return { run, extra, env, Exit };
})();
