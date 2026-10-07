// Run a Jot-generated .html (wasm target) under node: extracts the script and executes it.
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const m = html.match(/<script>([\s\S]*)<\/script>/);
if (!m) { console.error("no script found"); process.exit(1); }
const vm = require("vm");
const ctx = { console, process, Buffer, TextDecoder, TextEncoder, WebAssembly, performance, Proxy, Error, Uint8Array, Object };
vm.createContext(ctx);
vm.runInContext(m[1], ctx);
