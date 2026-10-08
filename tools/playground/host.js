// The Jot compiler, compiled to WebAssembly, run on files kept in memory: the standard library
// (embedded in the page) and the program being edited. It runs in a worker (or, where a page
// cannot start one, on the page itself): each compile gets a fresh instance of the compiler.
//   compile(source) -> { ok, html, log, ms }   html: the program, a complete web page
"use strict";
const jotHost = (() => {
  let compiler = null;          // WebAssembly.Module
  let lib = null;               // path -> Uint8Array
  const enc = new TextEncoder(), dec = new TextDecoder();

  const fromB64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  async function gunzip(bytes) {
    const ds = new DecompressionStream("gzip");
    const out = new Response(new Blob([bytes]).stream().pipeThrough(ds));
    return new Uint8Array(await out.arrayBuffer());
  }

  async function init(wasmGz, libGz) {
    compiler = await WebAssembly.compile(await gunzip(fromB64(wasmGz)));
    const files = JSON.parse(dec.decode(await gunzip(fromB64(libGz))));
    lib = {};
    for (const p of Object.keys(files)) lib[p] = fromB64(files[p]);
  }

  class Exit extends Error { constructor(code) { super("exit " + code); this.code = code; } }

  function compile(source) {
    const t0 = performance.now();
    const files = Object.assign({}, lib);
    files["/play/main.jot"] = enc.encode(source);
    const args = ["/jot/bin/jot", "build", "/play/main.jot", "--target", "wasm", "-o", "/play/main"];
    const envVars = { JOT_LIB: "/jot/lib" };
    let log = "";
    let mem = null;
    const u8 = () => new Uint8Array(mem.buffer);
    const str = (p, n) => dec.decode(u8().subarray(Number(p), Number(p) + Number(n)));
    function give(b, op, cap) {
      u8().set(b.subarray(0, Math.min(b.length, Number(cap))), Number(op));
      return BigInt(b.length);
    }
    function listDir(path) {
      const seen = new Set();
      for (const f of Object.keys(files)) if (f.startsWith(path + "/")) seen.add(f.slice(path.length + 1).split("/")[0]);
      return seen.size > 0 ? [...seen] : null;
    }
    const env = {
      __wasm_write: (fd, p, n) => { log += str(p, n); },
      __wasm_exit: (code) => { throw new Exit(Number(code)); },
      __wasm_now: () => performance.now(),
      __wasm_grow: (n) => BigInt(mem.grow(Number(n))),
      __wasm_env: (np, nn, op, cap) => {
        const v = envVars[str(np, nn)];
        return v === undefined ? -1n : give(enc.encode(v), op, cap);
      },
      __wasm_read_file: (pp, pn, op, cap) => {
        const d = files[str(pp, pn)];
        return d === undefined ? -1n : give(d, op, cap);
      },
      __wasm_write_file: (pp, pn, dp, dn) => {
        files[str(pp, pn)] = u8().slice(Number(dp), Number(dp) + Number(dn));
        return 1n;
      },
      __wasm_list_dir: (pp, pn, op, cap) => {
        const names = listDir(str(pp, pn).replace(/\/+$/, ""));
        return names === null ? -1n : give(enc.encode(names.join("\n")), op, cap);
      },
      __wasm_args: (op, cap) => give(enc.encode(args.join("\0")), op, cap),
    };
    let ok = false;
    try {
      const inst = new WebAssembly.Instance(compiler, { env });
      mem = inst.exports.memory;
      inst.exports.__start();
      ok = true;
    } catch (e) {
      if (e instanceof Exit) ok = e.code === 0;
      else log += "internal compiler error: " + (e && e.message || e) + "\n";
    }
    const out = files["/play/main.html"];
    return { ok: ok && out !== undefined, html: out ? dec.decode(out) : "", log, ms: performance.now() - t0 };
  }

  return { init, compile };
})();

// (as a worker: messages {init: [wasm, lib]} and {source})
if (typeof window === "undefined" && typeof self !== "undefined") {
  self.onmessage = async (ev) => {
    const m = ev.data;
    try {
      if (m.init) {
        await jotHost.init(m.init[0], m.init[1]);
        self.postMessage({ ready: true });
      } else self.postMessage(Object.assign({ id: m.id }, jotHost.compile(m.source)));
    } catch (e) {
      self.postMessage({ id: m.id, ok: false, html: "", log: "playground error: " + (e && e.message || e) + "\n", ms: 0 });
    }
  };
}
