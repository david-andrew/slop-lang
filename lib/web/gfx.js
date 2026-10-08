// WebGL2, canvas, input and frame loop for Jot programs running in the browser.
jot.extra.push({
  imports(getMem, getExports) {
    // views of wasm memory, made again only when the memory grows (no garbage per GL call)
    let vbuf = null, vu8 = null, vf32 = null;
    const views = () => { const b = getMem().buffer; if (b !== vbuf) { vbuf = b; vu8 = new Uint8Array(b); vf32 = new Float32Array(b); } };
    const u8 = () => { views(); return vu8; };
    const f32 = () => { views(); return vf32; };
    const bytes = (p, n) => u8().subarray(Number(p), Number(p) + Number(n));
    const text = (p, n) => new TextDecoder().decode(bytes(p, n));
    let gl = null, canvas = null;
    const objs = [null];            // integer handle -> WebGL object
    const add = (o) => { objs.push(o); return objs.length - 1; };
    const get = (h) => objs[h] || null;
    const locs = [null];
    let fixedSize = false;
    const keymap = {};
    "abcdefghijklmnopqrstuvwxyz".split("").forEach((c, i) => keymap["Key" + c.toUpperCase()] = 1 + i);
    for (let i = 0; i < 10; i++) keymap["Digit" + i] = 27 + i;
    const named = ["Space", "Enter", "Escape", "Tab", "Backspace", "Delete", "Insert", "Home", "End", "PageUp", "PageDown",
      "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Shift", "Control", "Alt", "Meta"];
    named.forEach((n, i) => keymap[n] = 37 + i);
    keymap["ShiftLeft"] = keymap["ShiftRight"] = keymap["Shift"];
    keymap["ControlLeft"] = keymap["ControlRight"] = keymap["Control"];
    keymap["AltLeft"] = keymap["AltRight"] = keymap["Alt"];
    keymap["MetaLeft"] = keymap["MetaRight"] = keymap["Meta"];
    keymap["NumpadEnter"] = keymap["Enter"];
    for (let i = 1; i <= 12; i++) keymap["F" + i] = 55 + i;
    ["Minus", "Equal", "Comma", "Period", "Slash", "Semicolon", "Quote", "BracketLeft", "BracketRight", "Backslash", "Backquote"]
      .forEach((n, i) => keymap[n] = 68 + i);
    // the clipboard: a page may read it only as it is pasted
    let clipText = "";
    if (typeof document !== "undefined") document.addEventListener("paste", (e) => { clipText = e.clipboardData ? e.clipboardData.getData("text") : ""; });
    const enc = new TextEncoder();
    return {
      __web_set_title(tp, tn) { document.title = text(tp, tn); },
      __web_fullscreen(on) {
        if (on) { const r = canvas && canvas.requestFullscreen && canvas.requestFullscreen(); if (r) r.catch(() => {}); }
        else if (document.fullscreenElement) { const r = document.exitFullscreen(); if (r) r.catch(() => {}); }
      },
      __web_is_fullscreen: () => (typeof document !== "undefined" && document.fullscreenElement) ? 1 : 0,
      __web_clipboard_get(out, cap) {
        const b = enc.encode(clipText);
        u8().set(b.subarray(0, cap), Number(out));
        return b.length;
      },
      __web_clipboard_set(p, n) {
        clipText = text(p, n);
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(clipText).catch(() => {});
      },
      __web_canvas_open(tp, tn, w, h) {
        document.title = text(tp, tn);
        canvas = document.getElementById("jot-canvas");
        // the canvas fills the page (the program sees the new size each frame, as when a window
        // is resized), drawn at the screen's pixel density up to about 2.6 million pixels
        const fit = () => {
          const cw = window.innerWidth, ch = window.innerHeight;
          canvas.style.width = cw + "px"; canvas.style.height = ch + "px";
          const d = Math.min(window.devicePixelRatio || 1, Math.sqrt(2.6e6 / Math.max(cw * ch, 1)));
          canvas.width = Math.max(1, Math.round(cw * d)); canvas.height = Math.max(1, Math.round(ch * d));
        };
        fit(); window.addEventListener("resize", fit);
        document.body.style.overflow = "hidden";
        document.getElementById("log").style.display = "none";
        gl = canvas.getContext("webgl2", { antialias: true, alpha: false, preserveDrawingBuffer: false });
        if (!gl) throw new Error("WebGL2 is not available in this browser");
        const ex = getExports();
        const key = (e, down) => {
          const k = keymap[e.code] || keymap[e.key];
          // (ctrl+V/C/X stay with the browser, so pasting and copying work)
          const clip = (e.ctrlKey || e.metaKey) && (e.code === "KeyV" || e.code === "KeyC" || e.code === "KeyX");
          if (k) { ex.__key(k, down ? (e.repeat ? 2 : 1) : 0); if (!clip) e.preventDefault(); }
          if (down && e.key.length === 1 && !e.ctrlKey && !e.metaKey && ex.__char) ex.__char(e.key.charCodeAt(0));
        };
        window.addEventListener("keydown", (e) => key(e, true));
        window.addEventListener("keyup", (e) => key(e, false));
        const pos = (e) => { const r = canvas.getBoundingClientRect(); return [(e.clientX - r.left) * canvas.width / r.width, (e.clientY - r.top) * canvas.height / r.height]; };
        canvas.addEventListener("mousemove", (e) => { const p = pos(e); ex.__mouse(0, p[0], p[1], 0); });
        const btn = (b) => b === 0 ? 0 : b === 1 ? 1 : 2;
        canvas.addEventListener("mousedown", (e) => { canvas.focus(); const p = pos(e); ex.__mouse(0, p[0], p[1], 0); ex.__mouse(1, 0, 0, btn(e.button)); jot.resumeAudio && jot.resumeAudio(); });
        window.addEventListener("mouseup", (e) => ex.__mouse(2, 0, 0, btn(e.button)));
        canvas.addEventListener("wheel", (e) => { ex.__mouse(3, 0, -Math.sign(e.deltaY), 0); e.preventDefault(); }, { passive: false });
        canvas.addEventListener("contextmenu", (e) => e.preventDefault());
        window.addEventListener("keydown", () => jot.resumeAudio && jot.resumeAudio(), { once: true });
        canvas.focus();
      },
      // GPU arrays: a WebGL 2 context on the page's canvas (the same one a window uses later);
      // 1 if it can render to float textures
      __web_gpu_init() {
        if (typeof document === "undefined") return 0;
        if (!gl) {
          canvas = document.getElementById("jot-canvas");
          gl = canvas && canvas.getContext("webgl2", { antialias: true, alpha: false, preserveDrawingBuffer: false });
        }
        return gl && gl.getExtension("EXT_color_buffer_float") ? 1 : 0;
      },
      __web_canvas_size(out) {
        const a = new Int32Array(getMem().buffer, Number(out), 2);
        a[0] = canvas ? canvas.width : 0; a[1] = canvas ? canvas.height : 0;
      },
      glClearColor: (r, g, b, a) => gl.clearColor(r, g, b, a),
      glClear: (m) => gl.clear(m),
      glViewport: (x, y, w, h) => gl.viewport(x, y, w, h),
      glScissor: (x, y, w, h) => gl.scissor(x, y, w, h),
      glEnable: (c) => gl.enable(c),
      glDisable: (c) => gl.disable(c),
      glBlendFunc: (s, d) => gl.blendFunc(s, d),
      glBlendFuncSeparate: (s, d, sa, da) => gl.blendFuncSeparate(s, d, sa, da),
      glDepthFunc: (f) => gl.depthFunc(f),
      glDepthMask: (f) => gl.depthMask(!!f),
      glCullFace: (m) => gl.cullFace(m),
      glFrontFace: (m) => gl.frontFace(m),
      glColorMask: (r, g, b, a) => gl.colorMask(!!r, !!g, !!b, !!a),
      glCreateBuffer: () => add(gl.createBuffer()),
      glDeleteBuffer: (b) => gl.deleteBuffer(get(b)),
      glBindBuffer: (t, b) => gl.bindBuffer(t, get(b)),
      glBufferData: (t, size, p, usage) => { if (Number(p) === 0) gl.bufferData(t, Number(size), usage); else gl.bufferData(t, u8(), usage, Number(p), Number(size)); },
      glBufferSubData: (t, off, size, p) => gl.bufferSubData(t, Number(off), u8(), Number(p), Number(size)),
      glCreateVertexArray: () => add(gl.createVertexArray()),
      glDeleteVertexArray: (v) => gl.deleteVertexArray(get(v)),
      glBindVertexArray: (v) => gl.bindVertexArray(get(v)),
      glEnableVertexAttribArray: (i) => gl.enableVertexAttribArray(i),
      glDisableVertexAttribArray: (i) => gl.disableVertexAttribArray(i),
      glVertexAttribPointer: (i, size, ty, norm, stride, off) => gl.vertexAttribPointer(i, size, ty, !!norm, stride, Number(off)),
      glVertexAttribDivisor: (i, d) => gl.vertexAttribDivisor(i, d),
      glDrawArrays: (m, f, c) => gl.drawArrays(m, f, c),
      glDrawElements: (m, c, t, off) => gl.drawElements(m, c, t, Number(off)),
      glDrawArraysInstanced: (m, f, c, n) => gl.drawArraysInstanced(m, f, c, n),
      glDrawElementsInstanced: (m, c, t, off, n) => gl.drawElementsInstanced(m, c, t, Number(off), n),
      glCreateProgramFrom(vp, vn, fp, fn) {
        const mk = (kind, src) => {
          const s = gl.createShader(kind);
          gl.shaderSource(s, src); gl.compileShader(s);
          if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error("shader error: " + gl.getShaderInfoLog(s) + "\n" + src);
          return s;
        };
        const p = gl.createProgram();
        gl.attachShader(p, mk(gl.VERTEX_SHADER, text(vp, vn)));
        gl.attachShader(p, mk(gl.FRAGMENT_SHADER, text(fp, fn)));
        gl.linkProgram(p);
        if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error("link error: " + gl.getProgramInfoLog(p));
        return add(p);
      },
      glUseProgram: (p) => gl.useProgram(get(p)),
      glDeleteProgram: (p) => gl.deleteProgram(get(p)),
      glGetUniformLocationStr(p, np, nn) {
        const l = gl.getUniformLocation(get(p), text(np, nn));
        if (!l) return -1;
        locs.push(l); return locs.length - 1;
      },
      glUniform1i: (l, v) => l >= 0 && gl.uniform1i(locs[l], v),
      glUniform1f: (l, v) => l >= 0 && gl.uniform1f(locs[l], v),
      glUniform2f: (l, x, y) => l >= 0 && gl.uniform2f(locs[l], x, y),
      glUniform3f: (l, x, y, z) => l >= 0 && gl.uniform3f(locs[l], x, y, z),
      glUniform4f: (l, x, y, z, w) => l >= 0 && gl.uniform4f(locs[l], x, y, z, w),
      glUniform4i: (l, x, y, z, w) => l >= 0 && gl.uniform4i(locs[l], x, y, z, w),
      glUniformMatrix4fv: (l, n, tr, p) => l >= 0 && gl.uniformMatrix4fv(locs[l], !!tr, f32(), Number(p) >> 2, 16 * n),
      glUniform4fv: (l, n, p) => l >= 0 && gl.uniform4fv(locs[l], f32(), Number(p) >> 2, 4 * n),
      glCreateTexture: () => add(gl.createTexture()),
      glDeleteTexture: (t) => gl.deleteTexture(get(t)),
      glBindTexture: (t, x) => gl.bindTexture(t, get(x)),
      glActiveTexture: (u) => gl.activeTexture(u),
      // (float data needs a Float32Array view)
      glTexImage2D: (t, lvl, internal, w, h, b, fmt, ty, p, size) => Number(p) === 0 ? gl.texImage2D(t, lvl, internal, w, h, b, fmt, ty, null)
        : ty === 0x1406 ? gl.texImage2D(t, lvl, internal, w, h, b, fmt, ty, f32(), Number(p) >> 2) : gl.texImage2D(t, lvl, internal, w, h, b, fmt, ty, u8(), Number(p)),
      glTexSubImage2D: (t, lvl, x, y, w, h, fmt, ty, p, size) => ty === 0x1406 ? gl.texSubImage2D(t, lvl, x, y, w, h, fmt, ty, f32(), Number(p) >> 2)
        : gl.texSubImage2D(t, lvl, x, y, w, h, fmt, ty, u8(), Number(p)),
      glTexParameteri: (t, n, v) => gl.texParameteri(t, n, v),
      glGenerateMipmap: (t) => gl.generateMipmap(t),
      glPixelStorei: (n, v) => gl.pixelStorei(n, v),
      glCreateFramebuffer: () => add(gl.createFramebuffer()),
      glDeleteFramebuffer: (f) => gl.deleteFramebuffer(get(f)),
      glBindFramebuffer: (t, f) => gl.bindFramebuffer(t, get(f)),
      glFramebufferTexture2D: (t, a, tt, tex, lvl) => gl.framebufferTexture2D(t, a, tt, get(tex), lvl),
      glCreateRenderbuffer: () => add(gl.createRenderbuffer()),
      glDeleteRenderbuffer: (r) => gl.deleteRenderbuffer(get(r)),
      glBindRenderbuffer: (t, r) => gl.bindRenderbuffer(t, get(r)),
      glRenderbufferStorage: (t, f, w, h) => gl.renderbufferStorage(t, f, w, h),
      glFramebufferRenderbuffer: (t, a, rt, r) => gl.framebufferRenderbuffer(t, a, rt, get(r)),
      glCheckFramebufferStatus: (t) => gl.checkFramebufferStatus(t),
      glReadPixels: (x, y, w, h, fmt, ty, p, size) => ty === 0x1406 ? gl.readPixels(x, y, w, h, fmt, ty, f32(), Number(p) >> 2) : gl.readPixels(x, y, w, h, fmt, ty, u8(), Number(p)),
    };
  },
  start(ex) {
    if (!ex.__frame) return;
    const frame = (t) => {
      if (ex.__pad_present && navigator.getGamepads) {
        const pads = navigator.getGamepads();
        let g = null;
        for (const p of pads) if (p && p.connected) { g = p; break; }
        ex.__pad_present(g ? 1 : 0);
        if (g) {
          for (let i = 0; i < 4 && i < g.axes.length; i++) ex.__pad_axis(i, g.axes[i]);
          const bv = (i) => g.buttons[i] ? g.buttons[i].value : 0;
          ex.__pad_axis(4, bv(6)); ex.__pad_axis(5, bv(7));
          // standard mapping -> a b x y lb rb back start home ls rs up down left right
          const order = [0, 1, 2, 3, 4, 5, 8, 9, 16, 10, 11, 12, 13, 14, 15];
          order.forEach((src, i) => ex.__pad_button(i, g.buttons[src] && g.buttons[src].pressed ? 1 : 0));
        }
      }
      try { ex.__frame(t); } catch (e) { if (e instanceof jot.Exit) return; const l = document.getElementById("log"); l.style.display = "block"; l.textContent += "error: " + (e.stack || e) + "\n"; throw e; }
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  },
});
