#!/usr/bin/env bash
# Install Sloppy:
#   curl -fsSL https://sloppy-lang.org/install | bash
#   curl -fsSL https://sloppy-lang.org/install | bash -s v0.2.0     (a version)
# Installs to ~/.sloppy (or $SLOPPY_INSTALL): bin/sloppy and the standard library beside it, and puts
# ~/.sloppy/bin on your PATH (in your shell's startup file). Running it again updates.
# (`sloppy update` runs it with SLOPPY_CURRENT, the version installed: nothing to do if it is the latest)
set -euo pipefail

REPO="david-andrew/sloppy-lang"
ASSET="sloppy-linux-x86_64.tar.gz"
VERSION="${1:-latest}"
INSTALL="${SLOPPY_INSTALL:-$HOME/.sloppy}"
CURRENT="${SLOPPY_CURRENT:-}"

if [ -t 1 ]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'; CYAN=$'\033[36m'; RESET=$'\033[0m'
else
    BOLD=""; DIM=""; GREEN=""; RED=""; CYAN=""; RESET=""
fi
say() { printf '%s\n' "$*"; }
fail() { printf '%serror%s: %s\n' "$RED" "$RESET" "$*" >&2; exit 1; }

# ---- what this machine is ----
os="$(uname -s)"
arch="$(uname -m)"
[ "$os" = "Linux" ] || fail "Sloppy runs on Linux (this is $os). Its programs also run in any browser: see https://sloppy-lang.org/playground/"
case "$arch" in
    x86_64|amd64) ;;
    *) fail "Sloppy's compiler makes x86-64 programs and runs on x86-64 (this machine is $arch)" ;;
esac
command -v tar >/dev/null || fail "tar is needed"
if command -v curl >/dev/null; then
    get() { curl --fail --location --silent --show-error --output "$2" "$1"; }
elif command -v wget >/dev/null; then
    get() { wget --quiet --output-document="$2" "$1"; }
else
    fail "curl or wget is needed"
fi

if [ "$VERSION" = "latest" ]; then
    # which version that is: where releases/latest leads (.../releases/tag/vX.Y.Z)
    latest="https://github.com/$REPO/releases/latest"
    if command -v curl >/dev/null; then
        tag="$(curl -fsSLI -o /dev/null -w '%{url_effective}' "$latest" 2>/dev/null || true)"
    else
        tag="$(wget --max-redirect=0 --server-response --spider "$latest" 2>&1 | sed -n 's/^ *[Ll]ocation: *//p' | tr -d '\r' | tail -n 1 || true)"
    fi
    tag="${tag##*/}"
    case "$tag" in v[0-9]*) VERSION="$tag" ;; esac
fi
if [ "$VERSION" = "latest" ]; then
    base="https://github.com/$REPO/releases/latest/download"
else
    case "$VERSION" in v*) ;; *) VERSION="v$VERSION" ;; esac
    base="https://github.com/$REPO/releases/download/$VERSION"
    if [ -n "$CURRENT" ] && [ "$VERSION" = "v$CURRENT" ]; then
        if [ "${1:-latest}" = "latest" ]; then say "sloppy $CURRENT is the latest version: nothing to update"
        else say "sloppy $CURRENT is the version installed: nothing to do"; fi
        exit 0
    fi
fi

# (SLOPPY_DOWNLOAD_BASE: somewhere else holding the release files, for testing)
base="${SLOPPY_DOWNLOAD_BASE:-$base}"

# ---- download and check ----
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
say "${DIM}downloading $base/$ASSET${RESET}"
get "$base/$ASSET" "$tmp/$ASSET" || fail "could not download $base/$ASSET (is there a release ${VERSION}?)"
if get "$base/$ASSET.sha256" "$tmp/$ASSET.sha256" 2>/dev/null; then
    want="$(cut -d' ' -f1 < "$tmp/$ASSET.sha256")"
    if command -v sha256sum >/dev/null; then have="$(sha256sum "$tmp/$ASSET" | cut -d' ' -f1)"
    else have="$(shasum -a 256 "$tmp/$ASSET" | cut -d' ' -f1)"; fi
    [ "$want" = "$have" ] || fail "the download is damaged (checksum $have, expected $want)"
fi
tar -xzf "$tmp/$ASSET" -C "$tmp"
src="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d -name 'sloppy-*' | head -n 1)"
[ -n "$src" ] && [ -x "$src/bin/sloppy" ] || fail "the download does not hold bin/sloppy"

# ---- install (replacing an earlier one whole: no stale library files) ----
mkdir -p "$(dirname "$INSTALL")"
if [ -d "$INSTALL" ]; then
    rm -rf "$INSTALL.old"
    mv "$INSTALL" "$INSTALL.old"
fi
mv "$src" "$INSTALL"
rm -rf "$INSTALL.old"
installed="$("$INSTALL/bin/sloppy" --version 2>/dev/null)" || fail "$INSTALL/bin/sloppy does not run on this machine"

# ---- on the PATH ----
bin="$INSTALL/bin"
shown="${bin/#$HOME/\~}"
home_shown="${INSTALL/#$HOME/\~}"
on_path=false
case ":$PATH:" in *":$bin:"*) on_path=true ;; esac
note=""
if ! $on_path; then
    shell_name="$(basename "${SHELL:-bash}")"
    case "$shell_name" in
        fish)
            rc="$HOME/.config/fish/conf.d/sloppy.fish"
            mkdir -p "$(dirname "$rc")"
            line="fish_add_path \"$bin\""
            ;;
        zsh) rc="${ZDOTDIR:-$HOME}/.zshrc"; line="export PATH=\"$bin:\$PATH\"" ;;
        bash)
            rc="$HOME/.bashrc"
            [ -f "$rc" ] || rc="$HOME/.bash_profile"
            line="export PATH=\"$bin:\$PATH\""
            ;;
        *) rc="$HOME/.profile"; line="export PATH=\"$bin:\$PATH\"" ;;
    esac
    if ! grep -qsF "$bin" "$rc"; then
        printf '\n# sloppy\n%s\n' "$line" >> "$rc"
        note="added $shown to your PATH in ${rc/#$HOME/\~}"
    fi
fi

# ---- done ----
say ""
if [ -n "$CURRENT" ]; then
    say "${GREEN}sloppy $CURRENT was replaced by ${BOLD}${installed}${RESET}${GREEN} in ${home_shown}${RESET}"
    [ -n "$note" ] && say "${DIM}${note}${RESET}"
    exit 0
fi
say "${GREEN}${BOLD}${installed}${RESET}${GREEN} was installed to ${home_shown}${RESET}"
[ -n "$note" ] && say "${DIM}${note}${RESET}"
say ""
if ! $on_path; then
    say "To use it in this terminal, start a new one or run:"
    say "  ${CYAN}export PATH=\"$bin:\$PATH\"${RESET}"
    say ""
fi
say "Then:"
say "  ${CYAN}sloppy${RESET}                 an interactive prompt"
say "  ${CYAN}sloppy game.jo${RESET}        compile and run a program"
say "  ${CYAN}sloppy --web game.jo${RESET}  the same in the browser"
editor=""
command -v cursor >/dev/null && editor="cursor"
command -v code >/dev/null && [ -z "$editor" ] && editor="code"
if [ -n "$editor" ]; then
    say ""
    say "Editor support (highlighting, errors as you type, completion...):"
    say "  ${CYAN}$editor --install-extension RedFoxLabs.sloppy${RESET}"
fi
say ""
say "${DIM}Docs: https://sloppy-lang.org  ·  update: sloppy update  ·  uninstall: rm -rf $home_shown${RESET}"
