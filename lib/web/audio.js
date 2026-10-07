// WebAudio output for the Jot mixer: audio is pulled from wasm a little ahead of time.
jot.extra.push({
  imports(getMem, getExports) {
    let ctx = null, next = 0, rate = 48000;
    function pump() {
      if (!ctx || ctx.state !== "running") return;
      const ex = getExports();
      const ahead = 0.09;
      if (next < ctx.currentTime) next = ctx.currentTime + 0.02;
      while (next < ctx.currentTime + ahead) {
        const n = 1024;
        const p = Number(ex.__audio_fill(n));
        const f = new Float32Array(getMem().buffer, p, n * 2);
        const buf = ctx.createBuffer(2, n, rate);
        const l = buf.getChannelData(0), r = buf.getChannelData(1);
        for (let i = 0; i < n; i++) { l[i] = f[2 * i]; r[i] = f[2 * i + 1]; }
        const src = ctx.createBufferSource();
        src.buffer = buf;
        src.connect(ctx.destination);
        src.start(next);
        next += n / rate;
      }
    }
    jot.resumeAudio = () => { if (ctx && ctx.state !== "running") ctx.resume(); };
    jot.pumpAudio = pump;
    return {
      __web_audio_start(r) {
        rate = r;
        try { ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: r }); } catch (e) { ctx = null; }
        setInterval(pump, 20);
      },
    };
  },
});
