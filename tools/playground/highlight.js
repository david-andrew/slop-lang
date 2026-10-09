// Sloppy syntax highlighting for web pages (the playground's editor, the site's code blocks):
// sloppyHighlight(text, errLine) -> HTML with <span class="c|k|s|n|t|f|d|v|o"> around tokens
// (errLine: a line to mark with class "errline", or 0).
"use strict";
const KW = new Set("if else loop in break continue return match when defer pass struct enum type const extern use import as and or not xor is mut let soa test build".split(" "));
const CONSTS = new Set(["true", "false", "none", "null", "TARGET", "DEBUG"]);
const TYPES = new Set("int i8 i16 i32 i64 u8 u16 u32 u64 byte f32 f64 bool str void never vec2 vec3 vec4 ivec2 mat4 cfn".split(" "));
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const TOKEN = /(#.*)|(r?"""[\s\S]*?(?:"""|$))|(r?"(?:\\.|[^"\\\n])*"?)|('(?:\\.|[^'\\\n])*'?)|(\b0[xX][0-9a-fA-F_]+\b|\b\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?[A-Za-z_]*)|([A-Za-z_][A-Za-z0-9_]*)|(->|\.\.\.?|[-+*/%^&|<>=!~?:.,;@]+)|(\s+)|(.)/g;
function sloppyHighlight(text, errLine) {
  let html = "", m, line = 1, lineStart = true, prev = "", lineText = "";
  const lines = text.split("\n");
  const defs = new Set();
  lines.forEach((l, i) => { if (/^\s*[A-Za-z_]\w*\s*(\[[^\]]*\])?\s*=\s*\([^)]*\)?.*?(->[^:]*)?:\s*(#.*)?$/.test(l) || /^\s*[A-Za-z_]\w*\s*(\[[^\]]*\])?\s*=\s*\(/.test(l) && /\)\s*(->.*)?:/.test(l)) defs.add(i + 1); });
  TOKEN.lastIndex = 0;
  let open = errLine === 1 ? '<span class="errline">' : "";
  html += open;
  let firstIdent = true;
  while ((m = TOKEN.exec(text)) !== null) {
    const t = m[0];
    let cls = "";
    if (m[1]) cls = "c";
    else if (m[2] || m[3] || m[4]) cls = "s";
    else if (m[5]) cls = "n";
    else if (m[6]) {
      const after = text.slice(TOKEN.lastIndex);
      if (KW.has(t)) cls = "k";
      else if (t === "from" && firstIdent && /^\s+\S+\s+import\b/.test(after)) cls = "k";     // from m import x
      else if (CONSTS.has(t)) cls = "v";
      else if (TYPES.has(t)) cls = "t";
      else if (firstIdent && defs.has(line)) cls = "d";
      else if (/^\.?\(/.test(after)) cls = /^[A-Z]/.test(t) ? "t" : "f";
      else if (/^[A-Z][a-z]/.test(t)) cls = "t";
      else if (prev === "." && /(^|[\s(,=\[])\.$/.test(lineText)) cls = "v";
      firstIdent = false;
    } else if (m[7]) cls = "o";
    if (t.includes("\n")) {
      // (whitespace or a triple-quoted string across lines)
      const parts = t.split("\n");
      parts.forEach((p, k) => {
        if (k > 0) {
          if (errLine === line) html += "</span>";
          line++;
          html += "\n";
          if (errLine === line) html += '<span class="errline">';
          firstIdent = true;
          lineText = "";
        }
        if (p) html += cls ? `<span class="${cls}">${esc(p)}</span>` : esc(p);
        lineText += p;
      });
    } else {
      html += cls ? `<span class="${cls}">${esc(t)}</span>` : esc(t);
      lineText += t;
    }
    if (!/^\s+$/.test(t)) prev = t;
  }
  if (errLine === line) html += "</span>";
  return html + "\n";
}

