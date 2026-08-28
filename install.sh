#!/usr/bin/env bash
# ============================================================
# Kemi-Claw v6.2.0 — One-Line Installer
# curl -fsSL https://raw.githubusercontent.com/amiraanime500-crypto/kemi-claw-v4/main/install.sh | bash
# ============================================================
set -euo pipefail

# ── Colors ──
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

KEMI_VERSION="6.2.0"
INSTALL_DIR="${HOME}/.kemi"
REPO_URL="https://github.com/amiraanime500-crypto/kemi-claw-v4.git"

banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════╗"
    echo "║  🐺  Kemi-Claw v${KEMI_VERSION}  —  Autonomous Security Agent  ║"
    echo "║     45 tools · 6 LLMs · Pentest Lab         ║"
    echo "╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
}

info()  { echo -e "${GREEN}→${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $1"; }
error() { echo -e "${RED}✗${NC}  $1"; exit 1; }

# ── Check prerequisites ──
check_prereqs() {
    info "Checking prerequisites..."
    command -v python3 &>/dev/null || error "python3 is required. Install it first: https://python.org"
    command -v git &>/dev/null || error "git is required. Install it first: https://git-scm.com"
    command -v pip3 &>/dev/null || error "pip3 is required. Install it first: python3 -m ensurepip"
    PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    info "Python ${PYTHON_VER} ✓"
    info "git $(git --version | awk '{print $3}') ✓"
}

# ── Clone & install ──
install_kemi() {
    info "Installing Kemi-Claw v${KEMI_VERSION} to ${INSTALL_DIR}..."

    if [[ -d "${INSTALL_DIR}" ]]; then
        warn "Kemi already installed at ${INSTALL_DIR}"
        read -p "    Overwrite? [y/N] " -n 1 -r; echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            info "Installation cancelled."
            exit 0
        fi
        rm -rf "${INSTALL_DIR}"
    fi

    git clone --depth 1 "${REPO_URL}" "${INSTALL_DIR}" 2>&1 | tail -1
    cd "${INSTALL_DIR}"

    info "Installing Python dependencies..."
    pip3 install -q -e ".[dev]" 2>&1 | tail -1
    # Hermes-inspired MCP integration. Keep the MCP SDK explicit so the
    # installer remains functional even when packaging metadata omits the
    # requirements.txt file.
    pip3 install -q "mcp==1.26.0" 2>&1 | tail -1

    info "Core installed. Optional dependencies:"
    echo "    playwright  →  pip3 install playwright && playwright install chromium"
    echo "    nmap        →  apt install nmap (for nmap_scan tool)"
    echo "    shodan      →  pip3 install shodan (for Shodan API integration)"

    info "Dependencies installed ✓"
}

# ── Create CLI launcher ──
create_launcher() {
    LAUNCHER="${HOME}/.local/bin/kemi"
    mkdir -p "${HOME}/.local/bin"

    cat > "${LAUNCHER}" << 'LAUNCHEREOF'
#!/usr/bin/env bash
# Kemi-Claw v6.2.0 Launcher
KEMI_HOME="${HOME}/.kemi"
cd "${KEMI_HOME}"

case "${1:-}" in
    start|server)
        echo "🐺 Starting Kemi server on http://0.0.0.0:8000 ..."
        exec python3 -m uvicorn kemi_claw.server:app --host 0.0.0.0 --port "${PORT:-8000}"
        ;;
    mcp)
        echo "🔌 Starting Kemi MCP server over stdio..."
        echo "   Execution tools are disabled by default."
        exec python3 -m kemi_claw.mcp_server
        ;;
    scan)
        TARGET="${2:-}"
        CONFIRM="${3:-}"
        if [[ -z "${TARGET}" || "${CONFIRM}" != "authorized" ]]; then
            echo "Usage: kemi scan <https://target> authorized"
            echo "Only scan systems you own or have written permission to test."
            exit 1
        fi
        echo "🐺 Scanning ${TARGET} ..."
        export KEMI_CLI_TARGET="${TARGET}"
        exec python3 -c "
import asyncio, os
from kemi_claw.core.agent import KemiClawAgent
async def main():
    agent = KemiClawAgent()
    result = await agent.run('full reconnaissance', os.environ['KEMI_CLI_TARGET'], authorized=True)
    print(f'Scan complete: {len(result.get(\"results\",[]))} steps')
asyncio.run(main())"
        ;;
    agent)
        shift
        GOAL="$*"
        if [[ -z "${GOAL}" ]]; then
            echo "Usage: kemi agent <task>"
            echo "Example: kemi agent download python 3.13"
            echo "Example: kemi agent search for latest AI news"
            exit 1
        fi
        echo "🤖 Kemi Agent: ${GOAL}"
        export KEMI_CLI_GOAL="${GOAL}"
        exec python3 -c "
import asyncio, os
from kemi_claw.core.general_agent import GeneralAgent
async def main():
    agent = GeneralAgent()
    result = await agent.run(os.environ['KEMI_CLI_GOAL'])
    ok = result.get('successful', 0)
    total = result.get('steps_executed', 0)
    print(f'Done: {ok}/{total} steps succeeded in {result.get(\"elapsed_seconds\",0)}s')
asyncio.run(main())"
        ;;
    dashboard)
        echo "📊 Opening Kemi Dashboard..."
        echo "   http://localhost:${PORT:-8000}/dashboard"
        exec python3 -m uvicorn kemi_claw.server:app --host 0.0.0.0 --port "${PORT:-8000}"
        ;;
    test)
        echo "Running unit and security tests..."
        exec python3 -m pytest -q
        ;;
    health)
        curl -s "http://localhost:${PORT:-8000}/health" | python3 -m json.tool 2>/dev/null || echo "Server not running"
        ;;
    update)
        echo "🔄 Updating Kemi..."
        cd "${KEMI_HOME}"
        git pull origin main
        pip3 install -q -e .
        pip3 install -q "mcp==1.26.0"
        echo "✅ Kemi updated to latest version"
        ;;
    env|setup)
        echo "🔧 Kemi Environment Setup"
        echo "─────────────────────────"
        echo "Add these to your ~/.bashrc or ~/.zshrc:"
        echo ""
        echo "  export KEMI_MODEL_PROVIDER=nvidia"
        echo "  export KEMI_MODEL_NAME=meta/llama-3.1-8b-instruct"
        echo "  export NVIDIA_API_KEY=<your-nvidia-api-key>"
        echo "  export KEMI_API_KEY=<strong-random-api-key>"
        echo "  export KEMI_JWT_SECRET=<at-least-24-random-characters>"
        echo "  export KEMI_MCP_ALLOW_EXECUTION=1  # optional: enable MCP agent execution"
        echo "  export TELEGRAM_BOT_TOKEN=<your-telegram-bot-token>  # optional"
        echo ""
        echo "Or create a .env file in ~/.kemi:"
        echo ""
        echo "  KEMI_MODEL_PROVIDER=nvidia"
        echo "  NVIDIA_API_KEY=<your-key>"
        ;;
    pentest)
        echo "🔥 Launching ShadowStrike Pentest Lab..."
        cd "${KEMI_HOME}/pentest-lab"
        echo "Lab ready at: ${KEMI_HOME}/pentest-lab"
        echo "  targets/scope.txt  → add your targets"
        echo "  tools/shadowstrike → modular pentest framework"
        echo "  results/           → scan results appear here"
        ls -la
        ;;
    *)
        echo "Kemi-Claw v6.2.0 — Authorized Security AI Agent"
        echo ""
        echo "Commands:"
        echo "  kemi start         Start the server (http://localhost:8000)"
        echo "  kemi mcp           Start the local MCP server (stdio)"
        echo "  kemi scan <target> authorized  Run an authorized scan"
        echo "  kemi agent <task>  General AI agent (any task)"
        echo "  kemi dashboard     Open live dashboard"
        echo "  kemi test          Run 50-test integration suite"
        echo "  kemi health        Check server health"
        echo "  kemi update        Update to latest version"
        echo "  kemi env           Show environment setup"
        echo "  kemi pentest       Launch pentest lab"
        echo ""
        echo "Quick start:"
        echo "  kemi env    → see environment setup"
        echo "  kemi mcp    → connect Claude Code/Cursor/Codex via MCP"
        echo "  kemi start  → start the server"
        echo "  kemi health → verify it is running"
        ;;
esac
LAUNCHEREOF

    chmod +x "${LAUNCHER}"
    info "CLI launcher created: ${LAUNCHER}"
}

# ── Final setup ──
finalize() {
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":${HOME}/.local/bin:"* ]]; then
        echo 'export PATH="${HOME}/.local/bin:${PATH}"' >> "${HOME}/.bashrc"
        echo 'export PATH="${HOME}/.local/bin:${PATH}"' >> "${HOME}/.zshrc" 2>/dev/null || true
        info "Added ~/.local/bin to PATH (restart shell or run: source ~/.bashrc)"
    fi

    # Create default .env if not exists
    if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
        cat > "${INSTALL_DIR}/.env" << 'ENVEOF'
# Kemi-Claw v6.1 Configuration
KEMI_MODEL_PROVIDER=nvidia
KEMI_MODEL_NAME=meta/llama-3.1-8b-instruct
OPENAI_API_KEY=your-api-key-here
# TELEGRAM_BOT_TOKEN=your-telegram-bot-token
# SHODAN_API_KEY=your-shodan-key
# VIRUSTOTAL_API_KEY=your-virustotal-key
# KEMI_MCP_ALLOW_EXECUTION=1
ENVEOF
        info "Default .env created at ${INSTALL_DIR}/.env"
        warn "Edit ${INSTALL_DIR}/.env and add your API keys!"
    fi

    # Verify installation
    echo ""
    info "Testing Kemi installation..."
    cd "${INSTALL_DIR}"
    python3 -c "
import kemi_claw.tools.env_control
import kemi_claw.core.general_agent
import kemi_claw.mcp_server
from kemi_claw.tools.mcp_registry import registry
print('✅ Kemi-Claw v6.2 installed successfully!')
print(f'🔧 {len(registry.manifest())} tools available')
print('🔌 MCP server available: kemi mcp')
" || warn "Some imports failed — check dependencies"

    echo ""
    echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}${BOLD}║  🐺  Kemi-Claw v${KEMI_VERSION} Installed!                     ║${NC}"
    echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Quick Start:${NC}"
    echo -e "    1. Edit your API key: ${CYAN}nano ~/.kemi/.env${NC}"
    echo -e "    2. Start the server:  ${CYAN}kemi start${NC}"
    echo -e "    3. Open dashboard:    ${CYAN}http://localhost:8000/dashboard${NC}"
    echo -e "    4. Run a scan:        ${CYAN}kemi scan example.com authorized${NC}"
    echo -e "    5. General agent:     ${CYAN}kemi agent search for AI news${NC}"
    echo -e "    6. MCP:               ${CYAN}kemi mcp${NC}"
    echo -e "    7. Pentest lab:       ${CYAN}kemi pentest${NC}"
    echo -e "    8. Run tests:         ${CYAN}kemi test${NC}"
    echo ""
    echo -e "  ${BOLD}Docs:${NC} ${CYAN}https://github.com/amiraanime500-crypto/kemi-claw-v4${NC}"
    echo ""
}

# ── Main ──
main() {
    banner
    check_prereqs
    install_kemi
    create_launcher
    finalize
}

main "$@"