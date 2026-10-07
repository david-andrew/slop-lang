#include "jot0.h"

typedef struct {
  Token *t; int n, i;
  int file;
  int no_struct_lit; // unused
} Parser;

static Parser *P;
static int no_tuple; // inside an inline lambda body: ',' ends the statement

Node *new_node(int kind, Pos pos) {
  Node *n = arena_alloc(sizeof(Node));
  n->kind = kind; n->pos = pos;
  return n;
}

static NodeList clone_list(NodeList l) {
  NodeList r = {0};
  for (int i = 0; i < l.len; i++) vpush(r, clone_node(l.data[i]));
  return r;
}
Node *clone_node(Node *n) {
  if (!n) return NULL;
  Node *c = arena_alloc(sizeof(Node));
  *c = *n;
  c->a = clone_node(n->a); c->b = clone_node(n->b); c->c = clone_node(n->c); c->d = clone_node(n->d);
  c->list = clone_list(n->list);
  c->list2 = clone_list(n->list2);
  if (n->kind != N_FN && n->kind != N_STRUCT && n->kind != N_ENUM) c->sym = NULL;
  if (n->kind != N_CONV) c->type = NULL;
  if (n->kind == N_CONV) c->type = n->type;
  c->flags &= ~NF_CHECKED;
  return c;
}

static Token *peek(void) { return &P->t[P->i]; }
static Token *peekn(int k) { int j = P->i + k; return &P->t[j < P->n ? j : P->n - 1]; }
static int pk(void) { return P->t[P->i].kind; }
static Token *next(void) { Token *t = &P->t[P->i]; if (P->i < P->n - 1) P->i++; return t; }
static bool accept(int k) { if (pk() == k) { next(); return true; } return false; }
static Token *expect(int k, const char *what) {
  if (pk() != k) {
    Token *t = peek();
    if (t->kind == TK_IDENT || t->kind == TK_INT)
      fatal(t->pos, "expected %s, found '%.*s'", what ? what : tok_name(k), t->len, t->start);
    fatal(t->pos, "expected %s, found %s", what ? what : tok_name(k), tok_name(t->kind));
  }
  return next();
}
static Pos cur_pos(void) { return peek()->pos; }
static Str tok_str(Token *t) { return intern(t->start, t->len); }
static Str expect_ident(const char *what) { return tok_str(expect(TK_IDENT, what)); }
static void skip_newlines(void) { while (pk() == TK_NEWLINE) next(); }

static Node *parse_expr(void);
static Node *parse_type(void);
static Node *parse_block(void);
static Node *parse_stmt(void);
static Node *parse_simple_stmt(void);
static Node *parse_fn(bool lambda);

// ---------- types ----------
static Node *parse_type_primary(void) {
  Pos pos = cur_pos();
  Node *n;
  switch (pk()) {
  case TK_IDENT: {
    n = new_node(N_TNAME, pos);
    n->name = expect_ident(NULL);
    if (accept(TK_DOT)) { // module.Type
      n->sval = n->name;
      n->name = expect_ident("type name");
    }
    if (pk() == TK_LBRACK) {
      next();
      do { vpush(n->list, parse_type()); } while (accept(TK_COMMA));
      expect(TK_RBRACK, NULL);
    }
    return n;
  }
  case TK_LBRACK:
    next();
    n = new_node(N_TARRAY, pos);
    n->a = parse_type();
    if (accept(TK_SEMI)) { n->b = parse_expr(); }
    expect(TK_RBRACK, NULL);
    return n;
  case TK_LBRACE:
    next();
    n = new_node(N_TMAP, pos);
    n->a = parse_type();
    expect(TK_COLON, NULL);
    n->b = parse_type();
    expect(TK_RBRACE, NULL);
    return n;
  case TK_LPAREN:
    next();
    n = new_node(N_TTUPLE, pos);
    if (pk() != TK_RPAREN) {
      do { if (pk() == TK_RPAREN) break; vpush(n->list, parse_type()); } while (accept(TK_COMMA));
    }
    expect(TK_RPAREN, NULL);
    if (n->list.len == 1) return n->list.data[0];
    return n;
  case TK_STAR:
    next();
    n = new_node(N_TPTR, pos);
    n->a = parse_type_primary();
    return n;
  case TK_FN: {
    next();
    n = new_node(N_TFN, pos);
    expect(TK_LPAREN, NULL);
    while (pk() != TK_RPAREN) {
      Node *pt;
      bool m = accept(TK_MUT);
      pt = parse_type();
      if (m) pt->flags |= NF_MUT;
      vpush(n->list, pt);
      if (!accept(TK_COMMA)) break;
    }
    expect(TK_RPAREN, NULL);
    if (accept(TK_ARROW)) n->a = parse_type();
    return n;
  }
  case TK_NONE: // allow 'none' as void-ish? no
  default:
    fatal(pos, "expected a type, found %s", tok_name(pk()));
  }
}
static Node *parse_type(void) {
  Node *t = parse_type_primary();
  while (pk() == TK_QUESTION) {
    Node *o = new_node(N_TOPT, cur_pos());
    next();
    o->a = t;
    t = o;
  }
  return t;
}

// ---------- strings ----------
static int hexval(int c) { return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 : -1; }

// decode escapes in [s, s+n) into a fresh buffer
static Str decode_str(const char *s, int n, Pos pos, bool raw) {
  char *buf = arena_alloc(n + 1);
  int j = 0;
  for (int i = 0; i < n; i++) {
    char c = s[i];
    if (c == '\\' && !raw) {
      c = s[++i];
      switch (c) {
      case 'n': buf[j++] = '\n'; break; case 't': buf[j++] = '\t'; break;
      case 'r': buf[j++] = '\r'; break; case '0': buf[j++] = 0; break;
      case '\\': buf[j++] = '\\'; break; case '"': buf[j++] = '"'; break;
      case '\'': buf[j++] = '\''; break; case '{': buf[j++] = '{'; break; case '}': buf[j++] = '}'; break;
      case 'e': buf[j++] = 27; break;
      case 'x': { int h = hexval(s[i + 1]), l = hexval(s[i + 2]);
        if (h < 0 || l < 0) fatal(pos, "bad \\x escape"); buf[j++] = h * 16 + l; i += 2; break; }
      case '\n': // line continuation inside string
        while (i + 1 < n && (s[i + 1] == ' ' || s[i + 1] == '\t')) i++;
        break;
      default: fatal(pos, "unknown escape \\%c", c);
      }
    } else if (!raw && (c == '{' || c == '}') && i + 1 < n && s[i + 1] == c) {
      buf[j++] = c; i++;
    } else buf[j++] = c;
  }
  buf[j] = 0;
  return (Str){buf, j};
}

// Strip common leading indentation of triple-quoted strings and the first/last newline.
static void dedent_triple(const char **ps, int *pn) {
  const char *s = *ps; int n = *pn;
  if (n && s[0] == '\n') { s++; n--; }
  else if (n > 1 && s[0] == '\r' && s[1] == '\n') { s += 2; n -= 2; }
  // drop trailing whitespace line
  int e = n;
  while (e > 0 && (s[e - 1] == ' ' || s[e - 1] == '\t')) e--;
  if (e > 0 && s[e - 1] == '\n') n = e - 1;
  *ps = s; *pn = n;
}

static Node *parse_string_token(Token *t) {
  Pos pos = t->pos;
  const char *s = t->start; int n = t->len;
  bool raw = t->flags & STRF_RAW;
  int common = -1;
  if (t->flags & STRF_TRIPLE) {
    dedent_triple(&s, &n);
    // compute common indentation
    const char *p = s, *e = s + n;
    while (p < e) {
      int ind = 0; const char *q = p;
      while (q < e && (*q == ' ' || *q == '\t')) { ind++; q++; }
      if (q < e && *q != '\n') { if (common < 0 || ind < common) common = ind; }
      while (q < e && *q != '\n') q++;
      p = q + 1;
    }
    if (common > 0) {
      char *buf = arena_alloc(n + 1); int j = 0;
      p = s;
      while (p < e) {
        int k = 0;
        while (k < common && p < e && (*p == ' ' || *p == '\t')) { p++; k++; }
        while (p < e && *p != '\n') buf[j++] = *p++;
        if (p < e) buf[j++] = *p++;
      }
      s = buf; n = j;
    }
  }
  Node *str = new_node(N_STR, pos);
  // split into literal parts and interpolations
  int i = 0, lit_start = 0;
  bool has_interp = false;
  while (i < n && !raw) {
    if (s[i] == '\\') { i += 2; continue; }
    if (s[i] == '{' && i + 1 < n && s[i + 1] == '{') { i += 2; continue; }
    if (s[i] == '}' && i + 1 < n && s[i + 1] == '}') { i += 2; continue; }
    if (s[i] == '{') {
      has_interp = true;
      if (i > lit_start) {
        Node *lit = new_node(N_STR, pos);
        lit->sval = decode_str(s + lit_start, i - lit_start, pos, raw);
        vpush(str->list, lit);
      }
      int depth = 1, j = i + 1, colon = -1;
      while (j < n && depth) {
        if (s[j] == '{') depth++;
        else if (s[j] == '}') { if (--depth == 0) break; }
        else if (s[j] == '"') { j++; while (j < n && s[j] != '"') { if (s[j] == '\\') j++; j++; } }
        else if (s[j] == ':' && depth == 1 && colon < 0 && !(j + 1 < n && s[j + 1] == '=')) colon = j;
        j++;
      }
      int eend = colon >= 0 ? colon : j;
      // lex+parse the expression text
      int fidx = g_files.len;
      SrcFile sf = g_files.data[pos.file];
      char *sub = xstrndup(s + i + 1, eend - i - 1);
      // keep line info: use same file entry but separate source
      SrcFile nf = {sf.path, sf.dir, sub, eend - i - 1};
      vpush(g_files, nf);
      int nt;
      Token *toks = lex_file(fidx, &nt);
      for (int k = 0; k < nt; k++) { toks[k].pos.file = pos.file; toks[k].pos.line = pos.line; toks[k].pos.col = pos.col + (int)(toks[k].pos.col); }
      Parser sub_p = {toks, nt, 0, pos.file, 0};
      Parser *saved = P;
      P = &sub_p;
      Node *e = parse_expr();
      skip_newlines();
      if (pk() != TK_EOF) fatal(pos, "invalid expression in string interpolation");
      P = saved;
      Node *part = new_node(N_CALL, pos); // marker: interpolation part
      part->kind = N_PAIR;
      part->a = e;
      if (colon >= 0) part->sval = intern(s + colon + 1, j - colon - 1);
      vpush(str->list, part);
      i = j + 1;
      lit_start = i;
      continue;
    }
    i++;
  }
  if (!has_interp) {
    str->sval = decode_str(s, n, pos, raw);
    return str;
  }
  if (lit_start < n) {
    Node *lit = new_node(N_STR, pos);
    lit->sval = decode_str(s + lit_start, n - lit_start, pos, raw);
    vpush(str->list, lit);
  }
  str->aux = 1; // interpolated
  return str;
}

// ---------- expressions ----------
static Node *parse_args(Node *call) {
  // after '('
  while (pk() != TK_RPAREN) {
    Pos pos = cur_pos();
    if (pk() == TK_IDENT && peekn(1)->kind == TK_ASSIGN) {
      Node *na = new_node(N_NAMEDARG, pos);
      na->name = expect_ident(NULL);
      next();
      na->a = parse_expr();
      vpush(call->list, na);
    } else {
      bool m = accept(TK_MUT);
      Node *e = parse_expr();
      if (m) e->flags |= NF_MUT;
      vpush(call->list, e);
    }
    if (!accept(TK_COMMA)) break;
  }
  expect(TK_RPAREN, NULL);
  return call;
}

static Node *parse_if(bool is_expr);
static Node *parse_match(void);

static Node *parse_primary(void) {
  Token *t = peek();
  Pos pos = t->pos;
  Node *n;
  switch (t->kind) {
  case TK_INT:
    next();
    n = new_node(N_INT, pos); n->ival = t->ival; n->flags |= NF_LITERAL;
    if (t->flags & INTF_CHAR) n->aux = 1;
    return n;
  case TK_FLOAT:
    next();
    n = new_node(N_FLOAT, pos); n->fval = t->fval; n->flags |= NF_LITERAL;
    return n;
  case TK_STR:
    next();
    return parse_string_token(t);
  case TK_TRUE: case TK_FALSE:
    next();
    n = new_node(N_BOOL, pos); n->ival = t->kind == TK_TRUE;
    return n;
  case TK_NONE: next(); return new_node(N_NONE, pos);
  case TK_NULL: next(); return new_node(N_NULL, pos);
  case TK_IDENT:
    next();
    if (t->len == 1 && t->start[0] == '_') return new_node(N_HOLE, pos);
    n = new_node(N_IDENT, pos);
    n->name = tok_str(t);
    return n;
  case TK_DOT:
    next();
    n = new_node(N_DOTNAME, pos);
    n->name = expect_ident("name after '.'");
    return n;
  case TK_LPAREN: {
    next();
    if (accept(TK_RPAREN)) { n = new_node(N_TUPLE, pos); return n; }
    Node *e = parse_expr();
    if (pk() == TK_COMMA) {
      n = new_node(N_TUPLE, pos);
      vpush(n->list, e);
      while (accept(TK_COMMA)) {
        if (pk() == TK_RPAREN) break;
        vpush(n->list, parse_expr());
      }
      expect(TK_RPAREN, NULL);
      return n;
    }
    expect(TK_RPAREN, NULL);
    return e;
  }
  case TK_LBRACK: {
    next();
    n = new_node(N_ARRAY, pos);
    while (pk() != TK_RBRACK) {
      vpush(n->list, parse_expr());
      if (accept(TK_SEMI)) { n->b = parse_expr(); break; } // [value; count]
      if (!accept(TK_COMMA)) break;
    }
    expect(TK_RBRACK, NULL);
    return n;
  }
  case TK_LBRACE: {
    next();
    n = new_node(N_MAP, pos);
    while (pk() != TK_RBRACE) {
      Node *pr = new_node(N_PAIR, cur_pos());
      pr->a = parse_expr();
      expect(TK_COLON, NULL);
      pr->b = parse_expr();
      vpush(n->list, pr);
      if (!accept(TK_COMMA)) break;
    }
    expect(TK_RBRACE, NULL);
    return n;
  }
  case TK_FN:
    return parse_fn(true);
  case TK_IF:
    return parse_if(true);
  case TK_MATCH:
    return parse_match();
  case TK_STAR: { // pointer type in expression position, e.g. `x as *u8` handled by parse_type
    fatal(pos, "unexpected '*'");
  }
  default:
    if (t->kind == TK_IDENT || t->kind == TK_INT) fatal(pos, "unexpected '%.*s'", t->len, t->start);
    fatal(pos, "expected an expression, found %s", tok_name(t->kind));
  }
}

static Node *parse_postfix(Node *e) {
  for (;;) {
    Pos pos = cur_pos();
    switch (pk()) {
    case TK_LPAREN: {
      next();
      Node *c = new_node(N_CALL, pos);
      c->a = e;
      e = parse_args(c);
      break;
    }
    case TK_LBRACK: {
      next();
      Node *ix = new_node(N_INDEX, pos);
      ix->a = e;
      if (pk() == TK_DOTDOT || pk() == TK_DOTDOTEQ) {
        // xs[..b]
        Node *r = new_node(N_RANGE, pos);
        if (next()->kind == TK_DOTDOTEQ) r->flags |= NF_INCLUSIVE;
        if (pk() != TK_RBRACK) r->b = parse_expr();
        ix->b = r;
      } else {
        ix->b = parse_expr();
        if (pk() == TK_COMMA) { // generic type args: Name[A, B]
          vpush(ix->list, ix->b);
          while (accept(TK_COMMA)) vpush(ix->list, parse_expr());
          ix->b = NULL;
        }
      }
      expect(TK_RBRACK, NULL);
      e = ix;
      break;
    }
    case TK_DOT: {
      next();
      Node *f = new_node(N_FIELD, pos);
      f->a = e;
      if (pk() == TK_INT) { // tuple field
        Token *t = next();
        f->name = intern(t->start, t->len);
        f->aux = -2; f->ival = t->ival;
      } else if (pk() == TK_FLOAT) { // x.0.1 lexed as float "0.1"
        Token *t = next();
        const char *dot = memchr(t->start, '.', t->len);
        Node *f2 = new_node(N_FIELD, pos);
        f->name = intern(t->start, dot - t->start); f->aux = -2; f->ival = atoi(t->start);
        f2->a = f; f2->name = intern(dot + 1, t->len - (dot + 1 - t->start)); f2->aux = -2; f2->ival = atoi(dot + 1);
        e = f2;
        break;
      } else {
        f->name = expect_ident("field name");
      }
      e = f;
      break;
    }
    case TK_BANG: {
      next();
      Node *u = new_node(N_UNWRAP, pos);
      u->a = e;
      e = u;
      break;
    }
    default:
      return e;
    }
  }
}

static Node *parse_prefix(void) {
  Pos pos = cur_pos();
  int k = pk();
  if (k == TK_MINUS || k == TK_TILDE || k == TK_AMP) {
    next();
    Node *operand = parse_prefix();
    if (k == TK_MINUS && (operand->kind == N_INT || operand->kind == N_FLOAT) && (operand->flags & NF_LITERAL) && !operand->aux2) {
      operand->ival = -operand->ival; operand->fval = -operand->fval; operand->pos = pos;
      operand->aux2 = 1;
      return operand;
    }
    Node *n = new_node(k == TK_AMP ? N_ADDR : N_UNARY, pos);
    n->op = k;
    n->a = operand;
    return n;
  }
  return parse_postfix(parse_primary());
}

static Node *parse_unary(void) {
  Node *e = parse_prefix();
  while (pk() == TK_AS) {
    Node *c = new_node(N_CAST, cur_pos());
    next();
    c->a = e;
    c->b = parse_type();
    e = c;
  }
  return e;
}

static int binprec(int k) {
  switch (k) {
  case TK_STAR: case TK_SLASH: case TK_PERCENT: return 10;
  case TK_PLUS: case TK_MINUS: return 9;
  case TK_SHL: case TK_SHR: return 8;
  case TK_AMP: return 7;
  case TK_CARET: return 6;
  case TK_PIPE: return 5;
  case TK_DOTDOT: case TK_DOTDOTEQ: return 4;
  case TK_QQ: return 3;
  case TK_EQ: case TK_NE: case TK_LT: case TK_LE: case TK_GT: case TK_GE: case TK_IN: return 2;
  default: return -1;
  }
}

static Node *parse_binary(int minprec) {
  Node *lhs = parse_unary();
  for (;;) {
    int k = pk();
    if (k == TK_NOT && peekn(1)->kind == TK_IN) k = TK_IN; // `not in`
    int prec = binprec(k);
    if (prec < minprec) return lhs;
    Pos pos = cur_pos();
    bool negate = false;
    if (pk() == TK_NOT) { next(); negate = true; }
    next();
    if (k == TK_DOTDOT || k == TK_DOTDOTEQ) {
      Node *r = new_node(N_RANGE, pos);
      r->a = lhs;
      if (k == TK_DOTDOTEQ) r->flags |= NF_INCLUSIVE;
      if (pk() != TK_RBRACK && pk() != TK_RPAREN && pk() != TK_COMMA && pk() != TK_COLON) r->b = parse_binary(prec + 1);
      lhs = r;
      continue;
    }
    Node *rhs = parse_binary(k == TK_QQ ? prec : prec + 1);
    Node *b;
    if (k == TK_QQ) { b = new_node(N_COALESCE, pos); }
    else { b = new_node(N_BINARY, pos); b->op = k; }
    b->a = lhs; b->b = rhs;
    if (negate) { Node *nn = new_node(N_NOT, pos); nn->a = b; b = nn; }
    lhs = b;
  }
}

static Node *parse_not(void) {
  if (pk() == TK_NOT) {
    Pos pos = cur_pos(); next();
    Node *n = new_node(N_NOT, pos);
    n->a = parse_not();
    return n;
  }
  return parse_binary(0);
}
static Node *parse_and(void) {
  Node *l = parse_not();
  while (pk() == TK_AND) {
    Node *n = new_node(N_AND, cur_pos()); next();
    n->a = l; n->b = parse_not(); l = n;
  }
  return l;
}
static Node *parse_or(void) {
  Node *l = parse_and();
  while (pk() == TK_OR) {
    Node *n = new_node(N_OR, cur_pos()); next();
    n->a = l; n->b = parse_and(); l = n;
  }
  return l;
}
static Node *parse_expr(void) { return parse_or(); }

// ---------- blocks / statements ----------

// After ':' — either inline statement(s) or NEWLINE INDENT stmts DEDENT.
static Node *parse_block(void) {
  Node *b = new_node(N_BLOCK, cur_pos());
  if (pk() == TK_NEWLINE) {
    next();
    if (pk() != TK_INDENT) fatal(cur_pos(), "expected an indented block");
    next();
    while (pk() != TK_DEDENT && pk() != TK_EOF) {
      Node *s = parse_stmt();
      if (s) vpush(b->list, s);
    }
    expect(TK_DEDENT, "end of block");
    b->flags |= NF_TERMINATED;
    return b;
  }
  // inline: simple statements separated by ';'
  vpush(b->list, parse_simple_stmt());
  while (pk() == TK_SEMI && peekn(1)->kind != TK_NEWLINE) { next(); vpush(b->list, parse_simple_stmt()); }
  return b;
}

static Node *parse_if(bool is_expr) {
  Pos pos = cur_pos();
  expect(TK_IF, NULL);
  Node *n = new_node(N_IF, pos);
  // if v := opt:
  if (pk() == TK_IDENT && peekn(1)->kind == TK_DECL) {
    n->kind = N_IFLET;
    n->name = expect_ident(NULL);
    next();
  }
  n->a = parse_expr();
  expect(TK_COLON, NULL);
  n->b = parse_block();
  // allow `else` on following line after an indented block
  int save = P->i;
  if (pk() == TK_NEWLINE && peekn(1)->kind == TK_ELSE && !(n->b->flags & NF_TERMINATED)) next();
  if (pk() == TK_ELSE) {
    next();
    if (pk() == TK_IF) {
      Node *b = new_node(N_BLOCK, cur_pos());
      Node *inner = parse_if(is_expr);
      vpush(b->list, inner);
      if (inner->flags & NF_TERMINATED) b->flags |= NF_TERMINATED;
      n->c = b;
    } else {
      expect(TK_COLON, NULL);
      n->c = parse_block();
    }
    if (n->c->flags & NF_TERMINATED) n->flags |= NF_TERMINATED;
  } else {
    P->i = save;
    if (n->b->flags & NF_TERMINATED) n->flags |= NF_TERMINATED;
  }
  (void)is_expr;
  return n;
}

static Node *parse_pattern(void) {
  Pos pos = cur_pos();
  if (pk() == TK_IDENT && peek()->len == 1 && peek()->start[0] == '_') { next(); return new_node(N_PWILD, pos); }
  if (pk() == TK_DOT || (pk() == TK_IDENT && (peekn(1)->kind == TK_LPAREN || peekn(1)->kind == TK_COLON || peekn(1)->kind == TK_COMMA))) {
    if (pk() == TK_DOT) next();
    Node *v = new_node(N_PVARIANT, pos);
    v->name = expect_ident("variant name");
    if (accept(TK_LPAREN)) {
      while (pk() != TK_RPAREN) {
        Node *b = new_node(N_IDENT, cur_pos());
        b->name = expect_ident("binding name");
        vpush(v->list, b);
        if (!accept(TK_COMMA)) break;
      }
      expect(TK_RPAREN, NULL);
      v->aux = 1;
    }
    return v;
  }
  Node *e = parse_binary(3);
  if (e->kind == N_RANGE) { e->kind = N_PRANGE; return e; }
  Node *l = new_node(N_PLIT, pos);
  l->a = e;
  return l;
}

static Node *parse_match(void) {
  Pos pos = cur_pos();
  expect(TK_MATCH, NULL);
  Node *m = new_node(N_MATCH, pos);
  m->a = parse_expr();
  expect(TK_COLON, NULL);
  expect(TK_NEWLINE, NULL);
  expect(TK_INDENT, "indented match arms");
  while (pk() != TK_DEDENT && pk() != TK_EOF) {
    Node *arm = new_node(N_ARM, cur_pos());
    if (pk() == TK_ELSE) { next(); vpush(arm->list, new_node(N_PWILD, arm->pos)); }
    else {
      do { vpush(arm->list, parse_pattern()); } while (accept(TK_COMMA));
    }
    expect(TK_COLON, NULL);
    arm->b = parse_block();
    if (!(arm->b->flags & NF_TERMINATED)) { if (pk() != TK_DEDENT) expect(TK_NEWLINE, NULL); }
    vpush(m->list, arm);
  }
  expect(TK_DEDENT, NULL);
  m->flags |= NF_TERMINATED;
  return m;
}

static Node *parse_params(Node *fn) {
  expect(TK_LPAREN, NULL);
  while (pk() != TK_RPAREN) {
    Node *p = new_node(N_PARAM, cur_pos());
    if (accept(TK_MUT)) p->flags |= NF_MUT;
    p->name = expect_ident("parameter name");
    if (accept(TK_COLON)) {
      if (accept(TK_MUT)) p->flags |= NF_MUT;
      p->a = parse_type();
    }
    if (accept(TK_ASSIGN)) p->b = parse_expr();
    vpush(fn->list, p);
    if (!accept(TK_COMMA)) break;
  }
  expect(TK_RPAREN, NULL);
  return fn;
}

static const int op_tokens[] = { TK_PLUS, TK_MINUS, TK_STAR, TK_SLASH, TK_PERCENT, TK_EQ, TK_LT, TK_LE, TK_GT, TK_GE, TK_AMP, TK_PIPE, TK_CARET, TK_SHL, TK_SHR, TK_NE, TK_LBRACK };

static Node *parse_fn(bool lambda) {
  Pos pos = cur_pos();
  expect(TK_FN, NULL);
  Node *fn = new_node(lambda ? N_LAMBDA : N_FN, pos);
  if (!lambda) {
    if (pk() == TK_IDENT) fn->name = expect_ident(NULL);
    else {
      bool ok = false;
      for (size_t i = 0; i < sizeof op_tokens / sizeof *op_tokens; i++) if (pk() == op_tokens[i]) ok = true;
      if (!ok) fatal(pos, "expected function name");
      Token *t = next();
      if (t->kind == TK_LBRACK) { expect(TK_RBRACK, NULL); fn->name = internc("[]"); if (accept(TK_ASSIGN)) fn->name = internc("[]="); }
      else fn->name = intern(t->start, t->len);
      fn->aux2 = 1; // operator
    }
    if (pk() == TK_LBRACK) { // generic params
      next();
      while (pk() != TK_RBRACK) {
        Node *tp = new_node(N_IDENT, cur_pos());
        tp->name = expect_ident("type parameter");
        vpush(fn->list2, tp);
        if (!accept(TK_COMMA)) break;
      }
      expect(TK_RBRACK, NULL);
      fn->flags |= NF_GENERIC;
    }
  }
  parse_params(fn);
  if (accept(TK_ARROW)) fn->a = parse_type();
  if (pk() == TK_COLON) {
    next();
    int saved_nt = no_tuple;
    no_tuple = lambda && pk() != TK_NEWLINE;
    fn->b = parse_block();
    no_tuple = saved_nt;
    if (fn->b->flags & NF_TERMINATED) fn->flags |= NF_TERMINATED;
  } else if (!lambda && pk() == TK_NEWLINE) {
    // declaration without body (extern)
  } else fatal(cur_pos(), "expected ':' and function body");
  for (int i = 0; i < fn->list.len; i++) if (!fn->list.data[i]->a) fn->flags |= NF_GENERIC;
  return fn;
}

static bool is_assign_op(int k) {
  return k == TK_ASSIGN || k == TK_PLUSEQ || k == TK_MINUSEQ || k == TK_STAREQ || k == TK_SLASHEQ ||
    k == TK_PERCENTEQ || k == TK_AMPEQ || k == TK_PIPEEQ || k == TK_CARETEQ || k == TK_SHLEQ || k == TK_SHREQ;
}

static Node *parse_simple_stmt(void) {
  Pos pos = cur_pos();
  switch (pk()) {
  case TK_RETURN: {
    next();
    Node *r = new_node(N_RETURN, pos);
    int k = pk();
    if (k != TK_NEWLINE && k != TK_SEMI && k != TK_DEDENT && k != TK_EOF && k != TK_ELSE && k != TK_RPAREN && k != TK_COMMA) {
      r->a = parse_expr();
      if (pk() == TK_COMMA) { // return a, b
        Node *t = new_node(N_TUPLE, r->a->pos);
        vpush(t->list, r->a);
        while (accept(TK_COMMA)) vpush(t->list, parse_expr());
        r->a = t;
      }
    }
    return r;
  }
  case TK_BREAK: next(); return new_node(N_BREAK, pos);
  case TK_PASS: next(); return new_node(N_BLOCK, pos);
  case TK_CONTINUE: next(); return new_node(N_CONTINUE, pos);
  case TK_DEFER: {
    next();
    Node *d = new_node(N_DEFER, pos);
    if (pk() == TK_COLON) { next(); d->a = parse_block(); }
    else d->a = parse_simple_stmt();
    return d;
  }
  default: break;
  }
  // typed declaration: name: Type [= expr]
  if (pk() == TK_IDENT && peekn(1)->kind == TK_COLON) {
    Node *d = new_node(N_VARDECL, pos);
    d->name = expect_ident(NULL);
    next();
    d->a = parse_type();
    if (accept(TK_ASSIGN)) d->b = parse_expr();
    return d;
  }
  Node *e = parse_expr();
  if (no_tuple) {
    Node *s = new_node(N_EXPRSTMT, pos);
    s->a = e;
    return s;
  }
  if (pk() == TK_COMMA) { // tuple target list
    Node *t = new_node(N_TUPLE, e->pos);
    vpush(t->list, e);
    while (accept(TK_COMMA)) vpush(t->list, parse_expr());
    e = t;
  }
  if (pk() == TK_DECL) {
    next();
    Node *d = new_node(N_VARDECL, pos);
    if (e->kind == N_IDENT) d->name = e->name;
    else if (e->kind == N_TUPLE) {
      for (int i = 0; i < e->list.len; i++) if (e->list.data[i]->kind != N_IDENT && e->list.data[i]->kind != N_HOLE) fatal(e->list.data[i]->pos, "expected a name");
      d->list = e->list;
    } else fatal(e->pos, "left side of ':=' must be a name");
    d->b = parse_expr();
    if (pk() == TK_COMMA) {
      Node *t = new_node(N_TUPLE, d->b->pos);
      vpush(t->list, d->b);
      while (accept(TK_COMMA)) vpush(t->list, parse_expr());
      d->b = t;
    }
    return d;
  }
  if (is_assign_op(pk())) {
    Node *a = new_node(N_ASSIGN, cur_pos());
    a->op = next()->kind;
    a->a = e;
    a->b = parse_expr();
    if (pk() == TK_COMMA) {
      Node *t = new_node(N_TUPLE, a->b->pos);
      vpush(t->list, a->b);
      while (accept(TK_COMMA)) vpush(t->list, parse_expr());
      a->b = t;
    }
    return a;
  }
  if (e->kind == N_TUPLE && e->list.len > 1 && pk() != TK_NEWLINE) fatal(e->pos, "unexpected ','");
  Node *s = new_node(N_EXPRSTMT, pos);
  s->a = e;
  if (e->flags & NF_TERMINATED) s->flags |= NF_TERMINATED;
  return s;
}

static void end_stmt(Node *s) {
  if (s && (s->flags & NF_TERMINATED)) { accept(TK_NEWLINE); return; }
  if (pk() == TK_SEMI) { next(); accept(TK_NEWLINE); return; }
  if (pk() == TK_DEDENT || pk() == TK_EOF) return;
  if (P->i > 0 && P->t[P->i - 1].kind == TK_DEDENT) return;
  expect(TK_NEWLINE, "end of statement");
}

static Node *parse_toplevel(void);
static bool when_top;
static Node *parse_top_block(void) {
  Node *b = new_node(N_BLOCK, cur_pos());
  expect(TK_NEWLINE, "newline");
  if (pk() != TK_INDENT) fatal(cur_pos(), "expected an indented block");
  next();
  while (pk() != TK_DEDENT && pk() != TK_EOF) {
    Node *s = parse_toplevel();
    if (s) vpush(b->list, s);
    skip_newlines();
  }
  expect(TK_DEDENT, "end of block");
  b->flags |= NF_TERMINATED;
  return b;
}
static Node *parse_when(void) {
  Pos pos = cur_pos();
  expect(TK_WHEN, NULL);
  Node *w = new_node(N_WHEN, pos);
  w->a = parse_expr();
  expect(TK_COLON, NULL);
  w->b = when_top ? parse_top_block() : parse_block();
  int save = P->i;
  if (pk() == TK_NEWLINE && peekn(1)->kind == TK_ELSE) next();
  if (pk() == TK_ELSE) {
    next();
    if (pk() == TK_WHEN || pk() == TK_IF) {
      if (pk() == TK_IF) P->t[P->i].kind = TK_WHEN;
      Node *b = new_node(N_BLOCK, cur_pos());
      vpush(b->list, parse_when());
      b->flags |= NF_TERMINATED;
      w->c = b;
    } else {
      expect(TK_COLON, NULL);
      w->c = when_top ? parse_top_block() : parse_block();
    }
  } else P->i = save;
  w->flags |= NF_TERMINATED;
  return w;
}

static Node *parse_stmt(void) {
  Pos pos = cur_pos();
  Node *s;
  switch (pk()) {
  case TK_NEWLINE: next(); return NULL;
  case TK_IF: s = parse_if(false); s->flags |= NF_STMT; break;
  case TK_WHEN: s = parse_when(); break;
  case TK_WHILE: {
    next();
    s = new_node(N_WHILE, pos);
    if (pk() == TK_IDENT && peekn(1)->kind == TK_DECL) {
      s->name = expect_ident(NULL); next(); s->aux = 1;
    }
    s->a = parse_expr();
    expect(TK_COLON, NULL);
    s->b = parse_block();
    if (s->b->flags & NF_TERMINATED) s->flags |= NF_TERMINATED;
    break;
  }
  case TK_FOR: {
    next();
    s = new_node(N_FOR, pos);
    if (accept(TK_MUT)) s->flags |= NF_MUT;
    do {
      Node *v = new_node(N_IDENT, cur_pos());
      v->name = expect_ident("loop variable");
      vpush(s->list, v);
    } while (accept(TK_COMMA));
    if (s->list.len > 2) fatal(pos, "too many loop variables");
    expect(TK_IN, NULL);
    s->a = parse_expr();
    expect(TK_COLON, NULL);
    s->b = parse_block();
    if (s->b->flags & NF_TERMINATED) s->flags |= NF_TERMINATED;
    break;
  }
  case TK_MATCH: s = new_node(N_EXPRSTMT, pos); s->a = parse_match(); s->a->flags |= NF_STMT; s->flags |= NF_TERMINATED; break;
  case TK_FN:
    if (peekn(1)->kind == TK_IDENT) { // local function
      Node *f = parse_fn(false);
      s = new_node(N_VARDECL, pos);
      s->name = f->name;
      f->kind = N_LAMBDA;
      s->b = f;
      if (f->flags & NF_TERMINATED) s->flags |= NF_TERMINATED;
      break;
    }
    s = parse_simple_stmt();
    break;
  case TK_CONST: {
    next();
    s = new_node(N_CONST, pos);
    s->name = expect_ident("constant name");
    if (accept(TK_COLON)) s->a = parse_type();
    expect(TK_ASSIGN, NULL);
    s->b = parse_expr();
    break;
  }
  default:
    s = parse_simple_stmt();
    if (s->kind == N_VARDECL && s->b && (s->b->flags & NF_TERMINATED)) s->flags |= NF_TERMINATED;
    if (s->kind == N_ASSIGN && s->b && (s->b->flags & NF_TERMINATED)) s->flags |= NF_TERMINATED;
    if (s->kind == N_RETURN && s->a && (s->a->flags & NF_TERMINATED)) s->flags |= NF_TERMINATED;
    break;
  }
  end_stmt(s);
  return s;
}

static Node *parse_struct(void) {
  Pos pos = cur_pos();
  expect(TK_STRUCT, NULL);
  Node *s = new_node(N_STRUCT, pos);
  s->name = expect_ident("struct name");
  if (accept(TK_LBRACK)) {
    while (pk() != TK_RBRACK) {
      Node *tp = new_node(N_IDENT, cur_pos());
      tp->name = expect_ident("type parameter");
      vpush(s->list2, tp);
      if (!accept(TK_COMMA)) break;
    }
    expect(TK_RBRACK, NULL);
    s->flags |= NF_GENERIC;
  }
  expect(TK_COLON, NULL);
  Node *body = parse_block();
  for (int i = 0; i < body->list.len; i++) {
    Node *f = body->list.data[i];
    if (f->kind != N_VARDECL || f->list.len) fatal(f->pos, "expected a field declaration (name: Type or name := default)");
    vpush(s->list, f);
  }
  s->flags |= NF_TERMINATED;
  return s;
}

static Node *parse_variant(void) {
  Node *v = new_node(N_VARIANT, cur_pos());
  v->name = expect_ident("variant name");
  if (accept(TK_LPAREN)) {
    int idx = 0;
    while (pk() != TK_RPAREN) {
      Node *f = new_node(N_VARDECL, cur_pos());
      if (pk() == TK_IDENT && peekn(1)->kind == TK_COLON) { f->name = expect_ident(NULL); next(); }
      else f->name = internc(fmt("%d", idx));
      f->a = parse_type();
      vpush(v->list, f);
      idx++;
      if (!accept(TK_COMMA)) break;
    }
    expect(TK_RPAREN, NULL);
  }
  if (accept(TK_ASSIGN)) v->a = parse_expr();
  return v;
}

static Node *parse_enum(void) {
  Pos pos = cur_pos();
  expect(TK_ENUM, NULL);
  Node *e = new_node(N_ENUM, pos);
  e->name = expect_ident("enum name");
  if (accept(TK_LBRACK)) {
    while (pk() != TK_RBRACK) {
      Node *tp = new_node(N_IDENT, cur_pos());
      tp->name = expect_ident("type parameter");
      vpush(e->list2, tp);
      if (!accept(TK_COMMA)) break;
    }
    expect(TK_RBRACK, NULL);
    e->flags |= NF_GENERIC;
  }
  expect(TK_COLON, NULL);
  if (accept(TK_NEWLINE)) {
    expect(TK_INDENT, NULL);
    while (pk() != TK_DEDENT) {
      vpush(e->list, parse_variant());
      if (accept(TK_COMMA)) { if (pk() == TK_NEWLINE) next(); continue; }
      if (pk() != TK_DEDENT) expect(TK_NEWLINE, NULL);
    }
    expect(TK_DEDENT, NULL);
    e->flags |= NF_TERMINATED;
  } else {
    do { vpush(e->list, parse_variant()); } while (accept(TK_COMMA));
  }
  return e;
}

static Node *parse_toplevel(void) {
  Pos pos = cur_pos();
  Node *d;
  VEC(Node *) attrs = {0};
  while (pk() == TK_AT) {
    next();
    Node *at = new_node(N_IDENT, cur_pos());
    at->name = expect_ident("attribute name");
    if (accept(TK_LPAREN)) { at->a = parse_expr(); expect(TK_RPAREN, NULL); }
    vpush(attrs, at);
    skip_newlines();
  }
  switch (pk()) {
  case TK_FN: d = parse_fn(false); break;
  case TK_EXTERN: next(); d = parse_fn(false); d->flags |= NF_EXTERN; break;
  case TK_STRUCT: d = parse_struct(); break;
  case TK_ENUM: d = parse_enum(); break;
  case TK_IMPORT: case TK_USE: {
    bool use = next()->kind == TK_USE;
    d = new_node(N_IMPORT, pos);
    if (use) d->aux = 1;
    Str name = expect_ident("module name");
    char buf[512]; int n = snprintf(buf, sizeof buf, "%.*s", name.len, name.p);
    Str last = name;
    while (accept(TK_DOT)) { last = expect_ident("module name"); n += snprintf(buf + n, sizeof buf - n, "/%.*s", last.len, last.p); }
    d->sval = internc(buf);
    d->name = last;
    if (accept(TK_AS)) d->name = expect_ident("alias");
    break;
  }
  case TK_TEST: {
    next();
    d = new_node(N_TEST, pos);
    Token *t = expect(TK_STR, "test name");
    d->sval = intern(t->start, t->len);
    expect(TK_COLON, NULL);
    d->b = parse_block();
    d->flags |= NF_TERMINATED;
    break;
  }
  case TK_WHEN: {
    bool saved = when_top;
    when_top = true;
    d = parse_when();
    when_top = saved;
    return d;
  }
  case TK_BUILD: {
    next();
    d = new_node(N_BUILD, pos);
    expect(TK_COLON, NULL);
    d->b = parse_block();
    d->flags |= NF_TERMINATED;
    break;
  }
  default:
    d = parse_stmt();
    return d;
  }
  if (attrs.len) { Node *ab = new_node(N_BLOCK, pos); for (int i = 0; i < attrs.len; i++) vpush(ab->list, attrs.data[i]); d->c = ab; }
  end_stmt(d);
  return d;
}

void parse_file(int file, NodeList *decls) {
  int nt;
  Token *toks = lex_file(file, &nt);
  Parser p = {toks, nt, 0, file, 0};
  Parser *saved = P;
  P = &p;
  skip_newlines();
  while (pk() != TK_EOF) {
    Node *d = parse_toplevel();
    if (d) vpush(*decls, d);
    skip_newlines();
  }
  P = saved;
}
