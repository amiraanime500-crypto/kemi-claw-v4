"""Self-healing + auto-dependency installer for Kemi."""
import subprocess, sys, os, importlib, asyncio

PIP_PACKAGES = {
    "httpx": "httpx", "fastapi": "fastapi", "uvicorn": "uvicorn",
    "pydantic": "pydantic", "aiohttp": "aiohttp",
    "duckduckgo_search": "duckduckgo_search",
    "ddgs": "ddgs", "apscheduler": "apscheduler",
    "whois": "python-whois", "dns": "dnspython",
    "playwright": "playwright", "shodan": "shodan",
    "jinja2": "jinja2", "yaml": "pyyaml",
}


async def auto_install_missing():
    """Auto-detect and install missing Python packages."""
    installed = []
    failed = []
    
    for module_name, pip_name in PIP_PACKAGES.items():
        try:
            importlib.import_module(module_name.replace("-", "_"))
        except ImportError:
            try:
                proc = await asyncio.create_subprocess_exec(
                    sys.executable, "-m", "pip", "install", pip_name, "-q",
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await asyncio.wait_for(proc.communicate(), timeout=30)
                if proc.returncode == 0:
                    installed.append(pip_name)
                else:
                    failed.append(pip_name)
            except:
                failed.append(pip_name)
    
    return {"installed": installed, "failed": failed, "total_checked": len(PIP_PACKAGES)}


async def check_system_health() -> dict:
    """Run a comprehensive system health check."""
    checks = {}
    
    # Python version
    checks["python_version"] = sys.version
    checks["python_ok"] = sys.version_info >= (3, 9)
    
    # Disk space
    import shutil
    try:
        usage = shutil.disk_usage("/")
        checks["disk_free_gb"] = round(usage.free / 1e9, 1)
        checks["disk_ok"] = usage.free > 500_000_000  # 500MB minimum
    except:
        checks["disk_ok"] = True
    
    # Network
    try:
        import socket
        s = socket.socket()
        s.settimeout(5)
        s.connect(("8.8.8.8", 53))
        s.close()
        checks["network_ok"] = True
    except:
        checks["network_ok"] = False
    
    # Core imports
    imports_ok = True
    core_modules = [
        "kemi_claw.config", "kemi_claw.core.agent", "kemi_claw.core.general_agent",
        "kemi_claw.tools.env_control", "kemi_claw.tools.web_search",
    ]
    for mod in core_modules:
        try:
            importlib.import_module(mod)
            checks[f"import_{mod.split('.')[-1]}"] = True
        except Exception as e:
            checks[f"import_{mod.split('.')[-1]}"] = str(e)[:80]
            imports_ok = False
    checks["imports_ok"] = imports_ok
    
    # Tool count
    try:
        from kemi_claw.tools.mcp_registry import registry
        checks["tools_count"] = len(registry.manifest())
    except:
        checks["tools_count"] = 0
    
    # API keys
    for key in ["OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "SHODAN_API_KEY", "VIRUSTOTAL_API_KEY"]:
        val = os.getenv(key, "")
        checks[f"has_{key.lower()}"] = bool(val)
    
    checks["all_ok"] = all([
        checks.get("python_ok", True),
        checks.get("disk_ok", True),
        checks.get("network_ok", True),
        checks.get("imports_ok", True),
        checks.get("tools_count", 0) > 0,
    ])
    
    return checks


async def self_repair() -> dict:
    """Attempt to automatically fix common issues."""
    fixes = []
    
    # Install missing packages
    installed = await auto_install_missing()
    if installed["installed"]:
        fixes.append(f"Installed {len(installed['installed'])} packages: {installed['installed']}")
    
    # Fix permissions
    try:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(data_dir, exist_ok=True)
        os.chmod(data_dir, 0o755)
        fixes.append("Created/fixed data directory")
    except: pass
    
    return {"fixes_applied": len(fixes), "fixes": fixes, "health": await check_system_health()}
