// The Jot extension: a language client for `jot lsp` (written out here instead of depending on
// vscode-languageclient: the protocol subset it needs is small), and commands to run files.

const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const path = require('path');

let client = null;
let output = null;
let diagnostics = null;
let restarts = 0;

// ---- the server connection (JSON-RPC with Content-Length framing) ----

class Connection {
    constructor(command, onNotification, onExit) {
        this.nextId = 1;
        this.pending = new Map();
        this.buffer = Buffer.alloc(0);
        this.onNotification = onNotification;
        this.proc = cp.spawn(command, ['lsp'], { stdio: ['pipe', 'pipe', 'pipe'] });
        this.proc.stdout.on('data', (chunk) => this.receive(chunk));
        this.proc.stderr.on('data', (chunk) => output.append(chunk.toString()));
        this.proc.on('error', (err) => {
            output.appendLine(`jot: cannot start '${command} lsp': ${err.message}`);
            vscode.window.showErrorMessage(`Jot: cannot start the language server (${command}). Set jot.path to the jot compiler.`);
        });
        this.proc.on('exit', (code, signal) => {
            for (const [, p] of this.pending) p.resolve(null);
            this.pending.clear();
            onExit(code, signal);
        });
    }

    receive(chunk) {
        this.buffer = Buffer.concat([this.buffer, chunk]);
        for (;;) {
            const end = this.buffer.indexOf('\r\n\r\n');
            if (end < 0) return;
            const header = this.buffer.slice(0, end).toString('ascii');
            const m = /content-length:\s*(\d+)/i.exec(header);
            const n = m ? parseInt(m[1], 10) : 0;
            if (this.buffer.length < end + 4 + n) return;
            const body = this.buffer.slice(end + 4, end + 4 + n).toString('utf8');
            this.buffer = this.buffer.slice(end + 4 + n);
            let msg;
            try { msg = JSON.parse(body); } catch (e) { continue; }
            if (msg.id !== undefined && msg.method === undefined) {
                const p = this.pending.get(msg.id);
                if (!p) continue;
                this.pending.delete(msg.id);
                if (msg.error) p.reject(new Error(msg.error.message));
                else p.resolve(msg.result);
            } else if (msg.method) {
                this.onNotification(msg.method, msg.params);
            }
        }
    }

    send(msg) {
        const body = Buffer.from(JSON.stringify(msg), 'utf8');
        this.proc.stdin.write(`Content-Length: ${body.length}\r\n\r\n`);
        this.proc.stdin.write(body);
    }

    request(method, params, token) {
        const id = this.nextId++;
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
            this.send({ jsonrpc: '2.0', id, method, params });
            if (token) token.onCancellationRequested(() => this.send({ jsonrpc: '2.0', method: '$/cancelRequest', params: { id } }));
        });
    }

    notify(method, params) { this.send({ jsonrpc: '2.0', method, params }); }

    stop() {
        const proc = this.proc;
        this.request('shutdown', null).then(() => this.notify('exit', null), () => {});
        setTimeout(() => proc.kill(), 1000);
    }
}

// ---- conversions between the protocol and VS Code ----

const toPosition = (p) => new vscode.Position(p.line, p.character);
const toRange = (r) => new vscode.Range(toPosition(r.start), toPosition(r.end));
const toLocation = (l) => new vscode.Location(vscode.Uri.parse(l.uri), toRange(l.range));
const fromPosition = (p) => ({ line: p.line, character: p.character });
const textDocument = (doc) => ({ uri: doc.uri.toString() });
const at = (doc, pos) => ({ textDocument: textDocument(doc), position: fromPosition(pos) });

function toSymbol(s) {
    // (LSP symbol kinds start at 1, VS Code's at 0)
    const sym = new vscode.DocumentSymbol(s.name, s.detail || '', s.kind - 1, toRange(s.range), toRange(s.selectionRange));
    sym.children = (s.children || []).map(toSymbol);
    return sym;
}

function toWorkspaceEdit(we) {
    const edit = new vscode.WorkspaceEdit();
    for (const uri of Object.keys(we.changes || {})) {
        for (const e of we.changes[uri]) edit.replace(vscode.Uri.parse(uri), toRange(e.range), e.newText);
    }
    return edit;
}

function onNotification(method, params) {
    if (method === 'textDocument/publishDiagnostics') {
        const ds = params.diagnostics.map((d) => {
            const diag = new vscode.Diagnostic(toRange(d.range), d.message, (d.severity || 1) - 1);
            diag.source = d.source || 'jot';
            return diag;
        });
        diagnostics.set(vscode.Uri.parse(params.uri), ds);
    }
}

// ---- which jot ----

function jotCommand() {
    const configured = vscode.workspace.getConfiguration('jot').get('path');
    if (configured) return configured;
    // working on Jot itself: its own compiler
    for (const folder of vscode.workspace.workspaceFolders || []) {
        const p = path.join(folder.uri.fsPath, 'bin', 'jot');
        if (fs.existsSync(p) && fs.existsSync(path.join(folder.uri.fsPath, 'lib', 'core', 'rt.jot'))) return p;
    }
    return 'jot';
}

// ---- starting, stopping ----

function isJot(doc) { return doc.languageId === 'jot' && doc.uri.scheme === 'file'; }

function start() {
    const conn = new Connection(jotCommand(), onNotification, (code, signal) => {
        if (client !== conn) return;
        client = null;
        output.appendLine(`jot lsp exited (${signal || code})`);
        if (restarts < 5) {
            restarts++;
            setTimeout(start, 500 * restarts);
        }
    });
    client = conn;
    conn.request('initialize', {
        processId: process.pid,
        rootUri: vscode.workspace.workspaceFolders ? vscode.workspace.workspaceFolders[0].uri.toString() : null,
        capabilities: {},
    }).then(() => {
        conn.notify('initialized', {});
        for (const doc of vscode.workspace.textDocuments) open(doc);
    }, (err) => output.appendLine(`initialize failed: ${err.message}`));
}

function open(doc) {
    if (!client || !isJot(doc)) return;
    client.notify('textDocument/didOpen', {
        textDocument: { uri: doc.uri.toString(), languageId: 'jot', version: doc.version, text: doc.getText() },
    });
}

// a request, or null when there is no server (or it failed)
async function ask(method, params, token) {
    if (!client) return null;
    try {
        return await client.request(method, params, token);
    } catch (e) {
        return null;
    }
}

// ---- running ----

function runInTerminal(args) {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== 'jot') return;
    const doc = editor.document;
    doc.save().then(() => {
        let term = vscode.window.terminals.find((t) => t.name === 'Jot');
        if (!term) term = vscode.window.createTerminal('Jot');
        term.show(true);
        const quote = (s) => `'${s.replace(/'/g, `'\\''`)}'`;
        term.sendText([jotCommand(), ...args, doc.uri.fsPath].map(quote).join(' '));
    });
}

// ---- the extension ----

function activate(context) {
    output = vscode.window.createOutputChannel('Jot');
    diagnostics = vscode.languages.createDiagnosticCollection('jot');
    context.subscriptions.push(output, diagnostics);
    const selector = { language: 'jot', scheme: 'file' };
    const L = vscode.languages;

    context.subscriptions.push(
        vscode.workspace.onDidOpenTextDocument(open),
        vscode.workspace.onDidChangeTextDocument((e) => {
            if (!client || !isJot(e.document) || e.contentChanges.length === 0) return;
            client.notify('textDocument/didChange', {
                textDocument: { uri: e.document.uri.toString(), version: e.document.version },
                contentChanges: [{ text: e.document.getText() }],
            });
        }),
        vscode.workspace.onDidSaveTextDocument((doc) => {
            if (client && isJot(doc)) client.notify('textDocument/didSave', { textDocument: textDocument(doc) });
        }),
        vscode.workspace.onDidCloseTextDocument((doc) => {
            if (!client || !isJot(doc)) return;
            client.notify('textDocument/didClose', { textDocument: textDocument(doc) });
            diagnostics.delete(doc.uri);
        }),

        L.registerHoverProvider(selector, {
            async provideHover(doc, pos, token) {
                const r = await ask('textDocument/hover', at(doc, pos), token);
                if (!r || !r.contents) return null;
                const md = new vscode.MarkdownString(r.contents.value);
                return new vscode.Hover(md);
            },
        }),
        L.registerDefinitionProvider(selector, {
            async provideDefinition(doc, pos, token) {
                const r = await ask('textDocument/definition', at(doc, pos), token);
                if (!r) return null;
                return Array.isArray(r) ? r.map(toLocation) : toLocation(r);
            },
        }),
        L.registerReferenceProvider(selector, {
            async provideReferences(doc, pos, ctx, token) {
                const r = await ask('textDocument/references', { ...at(doc, pos), context: { includeDeclaration: ctx.includeDeclaration } }, token);
                return (r || []).map(toLocation);
            },
        }),
        L.registerDocumentHighlightProvider(selector, {
            async provideDocumentHighlights(doc, pos, token) {
                const r = await ask('textDocument/documentHighlight', at(doc, pos), token);
                return (r || []).map((h) => new vscode.DocumentHighlight(toRange(h.range)));
            },
        }),
        L.registerRenameProvider(selector, {
            async prepareRename(doc, pos, token) {
                if (!client) throw new Error('the Jot language server is not running');
                const r = await client.request('textDocument/prepareRename', at(doc, pos), token);
                return toRange(r);
            },
            async provideRenameEdits(doc, pos, newName, token) {
                if (!client) return null;
                const r = await client.request('textDocument/rename', { ...at(doc, pos), newName }, token);
                return r ? toWorkspaceEdit(r) : null;
            },
        }),
        L.registerCompletionItemProvider(selector, {
            async provideCompletionItems(doc, pos, token) {
                const r = await ask('textDocument/completion', at(doc, pos), token);
                if (!r) return null;
                const items = (r.items || r).map((c) => {
                    // (LSP completion kinds start at 1, VS Code's at 0)
                    const item = new vscode.CompletionItem(c.label, (c.kind || 1) - 1);
                    item.detail = c.detail;
                    item.sortText = c.sortText;
                    return item;
                });
                return new vscode.CompletionList(items, !!r.isIncomplete);
            },
        }, '.'),
        L.registerSignatureHelpProvider(selector, {
            async provideSignatureHelp(doc, pos, token) {
                const r = await ask('textDocument/signatureHelp', at(doc, pos), token);
                if (!r || !r.signatures || r.signatures.length === 0) return null;
                const help = new vscode.SignatureHelp();
                help.signatures = r.signatures.map((s) => {
                    const info = new vscode.SignatureInformation(s.label, s.documentation ? new vscode.MarkdownString(s.documentation) : undefined);
                    info.parameters = (s.parameters || []).map((p) => new vscode.ParameterInformation(p.label));
                    return info;
                });
                help.activeSignature = r.activeSignature || 0;
                help.activeParameter = r.activeParameter || 0;
                return help;
            },
        }, { triggerCharacters: ['(', ','], retriggerCharacters: [','] }),
        L.registerInlayHintsProvider(selector, {
            async provideInlayHints(doc, range, token) {
                const r = await ask('textDocument/inlayHint', { textDocument: textDocument(doc), range: { start: fromPosition(range.start), end: fromPosition(range.end) } }, token);
                return (r || []).map((h) => {
                    const hint = new vscode.InlayHint(toPosition(h.position), h.label, vscode.InlayHintKind.Type);
                    hint.paddingLeft = !!h.paddingLeft;
                    return hint;
                });
            },
        }),
        L.registerDocumentSymbolProvider(selector, {
            async provideDocumentSymbols(doc, token) {
                const r = await ask('textDocument/documentSymbol', { textDocument: textDocument(doc) }, token);
                return (r || []).map(toSymbol);
            },
        }),

        vscode.commands.registerCommand('jot.run', () => runInTerminal([])),
        vscode.commands.registerCommand('jot.runWeb', () => runInTerminal(['--web'])),
        vscode.commands.registerCommand('jot.test', () => runInTerminal(['test'])),
        vscode.commands.registerCommand('jot.restartServer', () => {
            restarts = 0;
            const old = client;
            client = null;
            if (old) old.stop();
            start();
        }),
        vscode.workspace.onDidChangeConfiguration((e) => {
            if (e.affectsConfiguration('jot.path')) vscode.commands.executeCommand('jot.restartServer');
        }),
    );
    start();
}

function deactivate() {
    if (client) client.stop();
    client = null;
}

module.exports = { activate, deactivate };
