// Run a Sloppy-generated .html (wasm target) under node: extracts the script and executes it.
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const m = html.match(/<script>([\s\S]*)<\/script>/);
if (!m) { console.error("no script found"); process.exit(1); }
const vm = require("vm");
// (the program's files are the real ones; its arguments follow the page's name)
const path = require("path");
const sloppyArgs = [path.basename(process.argv[2]).replace(/\.html$/, "")].concat(process.argv.slice(3));
const ctx = { console, process, Buffer, TextDecoder, TextEncoder, WebAssembly, performance, Proxy, Error, Uint8Array, Object, sloppyFs: fs, sloppyArgs };
vm.createContext(ctx);
vm.runInContext(m[1], ctx);
