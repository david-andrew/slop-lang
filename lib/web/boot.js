// start the program once all runtime modules are registered
if (typeof JOT_WASM !== "undefined") {
  const bin = typeof atob === "function" ? Uint8Array.from(atob(JOT_WASM), c => c.charCodeAt(0)) : Buffer.from(JOT_WASM, "base64");
  if (typeof window !== "undefined") {
    const fail = (e) => { const l = document.getElementById("log"); l.style.display = "block"; l.textContent += "error: " + (e && e.stack || e) + "\n"; };
    window.addEventListener("error", (ev) => fail(ev.error || ev.message));
    window.addEventListener("load", () => { try { jot.run(bin); } catch (e) { fail(e); } });
  } else jot.run(bin);
}
