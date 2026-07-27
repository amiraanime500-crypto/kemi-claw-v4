"""Full Environment Control — system, files, processes, network, packages.

What OpenClaw/Hermes agents can do: control the host completely.
This module gives Kemi the same power.
"""
import asyncio, os, subprocess, platform, shutil, json, time, socket
from .mcp_registry import registry


# ═══════════════════════════════════
# 1. SYSTEM INFORMATION
# ═══════════════════════════════════
async def sys_info() -> dict:
    """Get complete system information: OS, CPU, memory, disk, uptime."""
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "arch": platform.machine(),
        "processor": platform.processor(),
        "cwd": os.getcwd(),
        "user": os.getenv("USER", os.getenv("USERNAME", "unknown")),
        "home": os.path.expanduser("~"),
    }

    # CPU count
    try: info["cpu_count"] = os.cpu_count()
    except: pass

    # Memory (Linux)
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if "MemTotal" in line:
                    info["mem_total_kb"] = int(line.split()[1])
                elif "MemAvailable" in line:
                    info["mem_available_kb"] = int(line.split()[1])
                    break
    except: pass

    # Disk usage
    try:
        usage = shutil.disk_usage("/")
        info["disk_total_gb"] = round(usage.total / 1e9, 1)
        info["disk_free_gb"] = round(usage.free / 1e9, 1)
        info["disk_used_percent"] = round((1 - usage.free / usage.total) * 100, 1)
    except: pass

    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_sec = float(f.read().split()[0])
            info["uptime_hours"] = round(uptime_sec / 3600, 1)
    except: pass

    return info


async def sys_env() -> dict:
    """List all environment variables (sanitized — values truncated)."""
    env = {}
    for k, v in os.environ.items():
        if any(s in k.upper() for s in ["KEY", "TOKEN", "SECRET", "PASS", "AUTH"]):
            env[k] = f"{v[:4]}...{v[-4:]}" if len(v) > 10 else "***"
        else:
            env[k] = v[:200] if len(v) > 200 else v
    return {"env_count": len(env), "env": env}


# ═══════════════════════════════════
# 2. FILE SYSTEM OPERATIONS
# ═══════════════════════════════════
async def file_read(path: str, max_lines: int = 100) -> dict:
    """Read a file from the filesystem."""
    try:
        if not os.path.exists(path):
            return {"error": f"File not found: {path}"}
        if os.path.getsize(path) > 10_000_000:
            return {"error": f"File too large: {os.path.getsize(path)} bytes"}
        with open(path, "r", errors="replace") as f:
            lines = f.readlines()[:max_lines]
        return {"path": path, "lines": len(lines), "content": "".join(lines), "size": os.path.getsize(path)}
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": str(e)}


async def file_write(path: str, content: str) -> dict:
    """Write content to a file (create or overwrite)."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return {"path": path, "written": len(content), "ok": True}
    except PermissionError:
        return {"error": f"Permission denied: {path}"}
    except Exception as e:
        return {"error": str(e)}


async def file_list(directory: str = ".", pattern: str = "*") -> dict:
    """List files in a directory."""
    try:
        import glob
        files = glob.glob(os.path.join(directory, pattern))
        result = []
        for f in files[:100]:
            try:
                st = os.stat(f)
                result.append({
                    "name": os.path.basename(f) if os.path.isfile(f) else os.path.basename(f) + "/",
                    "size": st.st_size,
                    "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                    "type": "dir" if os.path.isdir(f) else "file",
                })
            except: pass
        return {"directory": directory, "pattern": pattern, "count": len(result), "files": result}
    except Exception as e:
        return {"error": str(e)}


async def file_delete(path: str) -> dict:
    """Delete a file or directory."""
    try:
        if not os.path.exists(path):
            return {"error": f"Not found: {path}"}
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.unlink(path)
        return {"path": path, "deleted": True}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════
# 3. PROCESS MANAGEMENT
# ═══════════════════════════════════
async def proc_list(filter_name: str = "") -> dict:
    """List running processes (Linux)."""
    try:
        result = await asyncio.create_subprocess_exec(
            "ps", "aux", "--no-headers",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)
        processes = []
        for line in stdout.decode().split("\n")[:50]:
            if not line.strip(): continue
            parts = line.split()
            if len(parts) >= 11:
                proc = {"user": parts[0], "pid": parts[1], "cpu": parts[2], "mem": parts[3],
                        "command": " ".join(parts[10:])[:80]}
                if not filter_name or filter_name.lower() in proc["command"].lower():
                    processes.append(proc)
        return {"count": len(processes), "filter": filter_name, "processes": processes}
    except Exception as e:
        return {"error": str(e)}


async def proc_kill(pid: int) -> dict:
    """Kill a process by PID."""
    try:
        os.kill(pid, 15)  # SIGTERM
        await asyncio.sleep(0.5)
        try: os.kill(pid, 0); return {"pid": pid, "killed": False, "note": "process still alive"}
        except: return {"pid": pid, "killed": True}
    except ProcessLookupError:
        return {"error": f"Process {pid} not found"}
    except PermissionError:
        return {"error": f"Permission denied to kill {pid}"}


# ═══════════════════════════════════
# 4. NETWORK MANAGEMENT
# ═══════════════════════════════════
async def net_interfaces() -> dict:
    """List network interfaces and their addresses."""
    try:
        result = await asyncio.create_subprocess_exec(
            "ip", "addr", "show",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)
        return {"interfaces": stdout.decode()[:3000]}
    except:
        try:
            result = await asyncio.create_subprocess_exec(
                "ifconfig", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)
            return {"interfaces": stdout.decode()[:3000]}
        except Exception as e:
            return {"error": str(e)}


async def net_connections() -> dict:
    """List active network connections."""
    try:
        result = await asyncio.create_subprocess_exec(
            "ss", "-tulpn",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(result.communicate(), timeout=10)
        return {"connections": stdout.decode()[:3000]}
    except Exception as e:
        return {"error": str(e)}


async def net_dns_lookup(hostname: str) -> dict:
    """DNS lookup for a hostname."""
    try:
        ips = socket.getaddrinfo(hostname, None)
        result = []
        for ip in ips[:10]:
            result.append({"family": str(ip[0]), "address": ip[4][0]})
        return {"hostname": hostname, "addresses": result}
    except Exception as e:
        return {"error": str(e), "hostname": hostname}


# ═══════════════════════════════════
# 5. PACKAGE MANAGEMENT
# ═══════════════════════════════════
async def pkg_install(package: str) -> dict:
    """Install a Python package via pip."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pip", "install", package, "-q",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        return {
            "package": package,
            "success": proc.returncode == 0,
            "output": (stdout + stderr).decode("utf-8", errors="replace")[:1000]
        }
    except Exception as e:
        return {"error": str(e)}


async def pkg_list() -> dict:
    """List installed Python packages."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pip", "list", "--format=columns",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {"packages": stdout.decode()[:5000]}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════
# 6. SHELL EXECUTION (FULL TERMINAL)
# ═══════════════════════════════════
async def shell_exec(command: str, timeout_sec: int = 30) -> dict:
    """Execute arbitrary shell command with full terminal access."""
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        return {
            "command": command,
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:8000],
            "stderr": stderr.decode("utf-8", errors="replace")[:2000],
        }
    except asyncio.TimeoutError:
        return {"error": f"Command timed out after {timeout_sec}s", "command": command}
    except Exception as e:
        return {"error": str(e), "command": command}


async def shell_script(script: str, timeout_sec: int = 60) -> dict:
    """Execute a multi-line shell script."""
    try:
        proc = await asyncio.create_subprocess_shell(
            script,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[:8000],
            "stderr": stderr.decode("utf-8", errors="replace")[:2000],
        }
    except asyncio.TimeoutError:
        return {"error": f"Script timed out after {timeout_sec}s"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════
# REGISTER ALL TOOLS
# ═══════════════════════════════════
registry.register("sys_info", "Get full system info (OS, CPU, memory, disk, uptime)", {}, sys_info)
registry.register("sys_env", "List environment variables (sanitized)", {}, sys_env)
registry.register("file_read", "Read a file from filesystem", {"path": "str", "max_lines": "int"}, file_read)
registry.register("file_write", "Write content to a file", {"path": "str", "content": "str"}, file_write)
registry.register("file_list", "List files in a directory", {"directory": "str", "pattern": "str"}, file_list)
registry.register("file_delete", "Delete a file or directory", {"path": "str"}, file_delete)
registry.register("proc_list", "List running processes", {"filter_name": "str"}, proc_list)
registry.register("proc_kill", "Kill a process by PID", {"pid": "int"}, proc_kill)
registry.register("net_interfaces", "List network interfaces", {}, net_interfaces)
registry.register("net_connections", "List active network connections", {}, net_connections)
registry.register("net_dns_lookup", "DNS lookup for a hostname", {"hostname": "str"}, net_dns_lookup)
registry.register("shell_exec", "Execute full shell command", {"command": "str", "timeout_sec": "int"}, shell_exec)
registry.register("shell_script", "Execute multi-line shell script", {"script": "str", "timeout_sec": "int"}, shell_script)
registry.register("pkg_install", "Install Python package via pip", {"package": "str"}, pkg_install)
registry.register("pkg_list", "List installed Python packages", {}, pkg_list)
