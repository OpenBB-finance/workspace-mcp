#!/bin/sh
set -eu

UV_INSTALL_URL="${UV_INSTALL_URL:-https://astral.sh/uv/install.sh}"
WORKSPACE_MCP_PYTHON="${WORKSPACE_MCP_PYTHON:-3.13}"
WORKSPACE_MCP_SOURCE="${WORKSPACE_MCP_SOURCE:-https://github.com/OpenBB-finance/workspace-mcp/archive/refs/heads/main.zip}"

info() {
    printf '%s\n' "$*" >&2
}

need_uv() {
    command -v uv >/dev/null 2>&1
}

install_uv() {
    info "uv was not found; installing uv..."

    if command -v curl >/dev/null 2>&1; then
        curl -LsSf "$UV_INSTALL_URL" | sh
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- "$UV_INSTALL_URL" | sh
    else
        info "Could not install uv: neither curl nor wget is available."
        info "Install uv manually, then rerun this command: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi

    PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    export PATH

    if ! need_uv; then
        info "uv was installed, but it is not available on PATH yet."
        info "Add $HOME/.local/bin to PATH, then rerun this command."
        exit 1
    fi
}

if ! need_uv; then
    install_uv
fi

exec uv tool run \
    --python "$WORKSPACE_MCP_PYTHON" \
    --from "$WORKSPACE_MCP_SOURCE" \
    workspace-mcp \
    "$@"
