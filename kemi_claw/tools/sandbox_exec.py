"""Code sandbox — execute Python/Bash in isolated subprocess for POCs."""
import asyncio, os, tempfile
from .mcp_registry import registry
SANDBOX_TIMEOUT = int(os.getenv("KEMI_SANDBOX_TIMEOUT", "30"))

async def sandbox_exec(code: str, language: str = "python"):
    os.makedirs("/tmp/kemi_sandbox", exist_ok=True)
    try:
        if language == "python":
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", dir="/tmp/kemi_sandbox", delete=False) as f:
                f.write(code)
                sp = f.name
            proc = await asyncio.create_subprocess_exec("python3", sp, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd="/tmp/kemi_sandbox")
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SANDBOX_TIMEOUT)
            os.unlink(sp)
        elif language == "bash":
            proc = await asyncio.create_subprocess_exec("bash", "-c", code, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd="/tmp/kemi_sandbox")
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SANDBOX_TIMEOUT)
        else: return {"error": f"Unsupported: {language}"}
        return {"exit_code": proc.returncode, "stdout": stdout.decode()[:5000], "stderr": stderr.decode()[:2000], "language": language}
    except asyncio.TimeoutError: return {"error": f"Timeout after {SANDBOX_TIMEOUT}s"}
    except Exception as e: return {"error": str(e)}

registry.register("sandbox_exec", "Execute Python/Bash code in isolated sandbox", {"code": "str", "language": "str"}, sandbox_exec)