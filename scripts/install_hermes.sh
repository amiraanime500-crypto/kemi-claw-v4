#!/usr/bin/env bash
# Install the official Hermes Agent alongside Kemi, never into Kemi's Python env.
set -euo pipefail
umask 077

readonly HERMES_RELEASE="v2026.8.31"
readonly HERMES_COMMIT="29112bef099274229cadff79cdff7bf7b99c4b77"
readonly HERMES_REPO="https://github.com/NousResearch/hermes-agent.git"

usage() {
    cat <<'EOF'
Usage: bash scripts/install_hermes.sh [--help]

Install the pinned official Hermes Agent release in a separate virtual environment.
No sudo, model credentials, background services, or browser downloads are required.

Environment overrides:
  HERMES_INSTALL_DIR  Source and venv (default: ~/.local/share/hermes-agent)
  HERMES_HOME         Configuration and sessions (default: ~/.hermes)
  HERMES_PYTHON       Python 3.11-3.13 executable (default: python3)

Git and a supported Python with venv/pip must be available. A recent Python
build is recommended so Hermes can use an up-to-date SQLite library.

Existing installations must match the pinned source; unrelated directories and
modified checkouts are never overwritten. Re-running repairs dependencies while
preserving Hermes configuration. Run ~/.local/bin/hermes setup afterwards to
choose a provider, then ~/.local/bin/hermes to chat.
EOF
}

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
    -h|--help) [[ $# -eq 1 ]] || fail "Unexpected arguments. Use --help."; usage; exit 0 ;;
    "") [[ $# -eq 0 ]] || fail "Unexpected arguments. Use --help." ;;
    *) fail "Unknown argument: $1. Use --help." ;;
esac

PYTHON="${HERMES_PYTHON:-python3}"
for executable in git bash "$PYTHON"; do
    command -v "$executable" >/dev/null 2>&1 || fail "$executable is required."
done

# Do not inherit a running Kemi virtualenv's import path.
unset PYTHONPATH PYTHONHOME
"$PYTHON" -c 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' \
    || fail "Hermes requires Python 3.11, 3.12, or 3.13. Set HERMES_PYTHON accordingly."

INSTALL_DIR="${HERMES_INSTALL_DIR:-$HOME/.local/share/hermes-agent}"
export HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
# Resolve paths before upstream's stages change their working directory.
INSTALL_DIR="$("$PYTHON" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$INSTALL_DIR")"
HERMES_HOME="$("$PYTHON" -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).expanduser().resolve())' "$HERMES_HOME")"

if [[ -e "$INSTALL_DIR" ]]; then
    [[ -d "$INSTALL_DIR/.git" ]] || fail "Refusing to overwrite $INSTALL_DIR (not a Hermes checkout)."
    [[ "$(git -C "$INSTALL_DIR" remote get-url origin)" == "$HERMES_REPO" ]] \
        || fail "Refusing to modify a checkout from a different repository."
    [[ "$(git -C "$INSTALL_DIR" rev-parse HEAD)" == "$HERMES_COMMIT" ]] \
        || fail "Existing Hermes version differs from $HERMES_RELEASE; leaving it unchanged."
    git -C "$INSTALL_DIR" diff --quiet HEAD -- \
        || fail "Existing Hermes checkout has modified tracked files; leaving it unchanged."
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    git clone --depth 1 --single-branch --branch "$HERMES_RELEASE" "$HERMES_REPO" "$INSTALL_DIR"
fi

# A moved upstream tag must not silently change the code we install or execute.
[[ "$(git -C "$INSTALL_DIR" rev-parse HEAD)" == "$HERMES_COMMIT" ]] \
    || fail "Release commit verification failed; no package or upstream script was executed."

upstream_stage() {
    bash "$INSTALL_DIR/scripts/install.sh" \
        --dir "$INSTALL_DIR" --hermes-home "$HERMES_HOME" \
        --stage "$1" --non-interactive
}

printf '\nInstalling Hermes %s in %s\n' "$HERMES_RELEASE" "$INSTALL_DIR"
[[ ! -L "$INSTALL_DIR/venv" ]] || fail "Refusing to use a symlinked virtual environment."
if [[ ! -e "$INSTALL_DIR/venv" ]]; then
    "$PYTHON" -m venv "$INSTALL_DIR/venv"
fi
VENV_PYTHON="$INSTALL_DIR/venv/bin/python"
[[ -x "$VENV_PYTHON" ]] || fail "Incomplete virtual environment at $INSTALL_DIR/venv; leaving it unchanged."
"$VENV_PYTHON" -c '
import sys
from pathlib import Path
ok = (sys.prefix != sys.base_prefix
      and Path(sys.prefix).resolve() == Path(sys.argv[1]).resolve()
      and (3, 11) <= sys.version_info[:2] < (3, 14))
sys.exit(0 if ok else 1)
' "$INSTALL_DIR/venv" || fail "Virtual environment validation failed; no packages were installed."
if ! "$VENV_PYTHON" -m pip --version >/dev/null 2>&1; then
    "$VENV_PYTHON" -m ensurepip --upgrade
fi
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install --editable "$INSTALL_DIR[all]"
"$VENV_PYTHON" -m pip check

# Use only upstream's configuration/launcher stages: no apt, browser, desktop,
# setup wizard, or gateway/service installation. Templates preserve existing data.
FRESH_CONFIG=false
[[ -e "$HERMES_HOME/config.yaml" ]] || FRESH_CONFIG=true
upstream_stage config
if [[ "$FRESH_CONFIG" == true ]]; then
    # The release's template has no schema version. Initialize new profiles
    # non-interactively, but never migrate an existing user's config on re-run.
    "$VENV_PYTHON" -c 'from hermes_cli.config import migrate_config; migrate_config(interactive=False)'
fi
upstream_stage path

"$HOME/.local/bin/hermes" --version
printf '\nHermes installed. In your terminal, run:\n'
printf '  export PATH="$HOME/.local/bin:$PATH"\n'
printf '  export HERMES_HOME=%q\n' "$HERMES_HOME"
printf '  hermes setup\n  hermes\n'
