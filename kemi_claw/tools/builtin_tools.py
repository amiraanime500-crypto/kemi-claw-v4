"""Built-in tools. Run real commands ONLY against authorized targets."""
import asyncio
import shlex

from .mcp_registry import registry


async def _run(cmd: str, timeout: int = 300):
    proc = await asyncio.create_subprocess_exec(
        *shlex.split(cmd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout)
        return {"exit": proc.returncode, "output": out.decode(errors="ignore")}
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "timeout"}


async def nmap_scan(target: str, flags: str = "-sV -T4"):
    return await _run(f"nmap {flags} {target}")


async def http_probe(url: str):
    import httpx

    async with httpx.AsyncClient(verify=False, timeout=30) as c:
        r = await c.get(url)
        return {"status": r.status_code, "headers": dict(r.headers)}


registry.register(
    "nmap_scan",
    "Run an authorized Nmap scan",
    {"target": "str", "flags": "str"},
    nmap_scan,
)
registry.register(
    "http_probe",
    "Probe an HTTP endpoint",
    {"url": "str"},
    http_probe,
)
