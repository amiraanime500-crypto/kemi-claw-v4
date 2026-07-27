#!/usr/bin/env python3
"""Kemi Interactive Shell — full CLI client for the Kemi agent."""
import asyncio, os, sys, json, readline

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

BANNER = r"""
╔══════════════════════════════════════════════════╗
║  🐺  Kemi-Claw v6.1 — Interactive Shell        ║
║  Type 'help' for commands, 'exit' to quit       ║
╚══════════════════════════════════════════════════╝"""

HELP_TEXT = """
Commands:
  scan <target>          Run comprehensive security scan
  quick <target>         Fast vulnerability scan only
  vuln <target> <type>   Specific vuln scan (sqli|xss|ssrf|lfi|xxe|ssti)
  recon <target>         Reconnaissance only
  agent <task>           General AI agent (any task)
  search <query>         Web search
  cve <id>               Look up specific CVE
  tech <target>          Detect technologies on target
  waf <target>           Detect WAF protecting target
  dirs <target>          Directory bruteforce
  sensitive <target>     Scan for exposed sensitive files
  dns <domain>           DNS enumeration + subdomains
  whois <domain>         WHOIS lookup
  jwt <token>            Analyze JWT token
  cors <target>          Test CORS configuration
  api <target>           API endpoint discovery
  report <target>        Generate and save HTML report
  health                 System health check
  stats                  Show cache, session, and scan stats
  history                Show recent scan sessions
  config                 Show current configuration
  clear                  Clear screen
  help                   Show this help
  exit                   Exit the shell
"""


class KemiShell:
    def __init__(self):
        self.history = []
        self._setup_readline()
    
    def _setup_readline(self):
        hist_file = os.path.expanduser("~/.kemi_shell_history")
        try:
            readline.read_history_file(hist_file)
        except: pass
        readline.set_history_length(100)
        import atexit
        atexit.register(lambda: readline.write_history_file(hist_file))
    
    async def run(self):
        print(BANNER)
        
        while True:
            try:
                cmd = input("\n🐺 kemi> ").strip()
                if not cmd: continue
                self.history.append(cmd)
                
                if cmd == "exit" or cmd == "quit":
                    print("Goodbye! 🐺")
                    break
                elif cmd == "help":
                    print(HELP_TEXT)
                elif cmd == "clear":
                    os.system("clear" if os.name != "nt" else "cls")
                    print(BANNER)
                elif cmd == "health":
                    await self._cmd_health()
                elif cmd == "stats":
                    await self._cmd_stats()
                elif cmd == "history":
                    await self._cmd_history()
                elif cmd == "config":
                    await self._cmd_config()
                elif cmd.startswith("scan "):
                    await self._cmd_scan(cmd[5:])
                elif cmd.startswith("quick "):
                    await self._cmd_quick(cmd[6:])
                elif cmd.startswith("vuln "):
                    parts = cmd[5:].split()
                    if len(parts) >= 2:
                        await self._cmd_vuln(parts[0], parts[1])
                    else:
                        print("Usage: vuln <target> <type>")
                elif cmd.startswith("recon "):
                    await self._cmd_recon(cmd[6:])
                elif cmd.startswith("agent "):
                    await self._cmd_agent(cmd[6:])
                elif cmd.startswith("search "):
                    await self._cmd_search(cmd[7:])
                elif cmd.startswith("cve "):
                    await self._cmd_cve(cmd[4:])
                elif cmd.startswith("tech "):
                    await self._cmd_tech(cmd[5:])
                elif cmd.startswith("waf "):
                    await self._cmd_waf(cmd[4:])
                elif cmd.startswith("dirs "):
                    await self._cmd_dirs(cmd[5:])
                elif cmd.startswith("sensitive "):
                    await self._cmd_sensitive(cmd[10:])
                elif cmd.startswith("dns "):
                    await self._cmd_dns(cmd[4:])
                elif cmd.startswith("whois "):
                    await self._cmd_whois(cmd[6:])
                elif cmd.startswith("jwt "):
                    await self._cmd_jwt(cmd[4:])
                elif cmd.startswith("cors "):
                    await self._cmd_cors(cmd[5:])
                elif cmd.startswith("api "):
                    await self._cmd_api(cmd[4:])
                elif cmd.startswith("report "):
                    await self._cmd_report(cmd[7:])
                else:
                    print(f"Unknown command: {cmd}")
                    print("Type 'help' for available commands")
                    
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except EOFError:
                break
    
    async def _cmd_health(self):
        from kemi_claw.utils.self_heal import check_system_health
        h = await check_system_health()
        print(f"System: {'✅' if h['all_ok'] else '❌'}")
        print(f"  Python: {'✅' if h.get('python_ok') else '❌'} {h.get('python_version','')[:30]}")
        print(f"  Network: {'✅' if h.get('network_ok') else '❌'}")
        print(f"  Disk: {h.get('disk_free_gb',0)} GB free")
        print(f"  Tools: {h.get('tools_count',0)}")
        for k, v in h.items():
            if k.startswith("has_"):
                print(f"  {k}: {'✅' if v else '❌'}")
    
    async def _cmd_stats(self):
        from kemi_claw.utils.cache import cache_stats, sessions
        cs = cache_stats()
        s = sessions.list_sessions(limit=10)
        print(f"Cache: {cs['entries']} entries ({cs['size_mb']} MB)")
        print(f"Sessions: {len(s)} total")
        for sess in s[:5]:
            print(f"  {sess['id']} | {sess['target']} | {sess['status']}")
    
    async def _cmd_history(self):
        from kemi_claw.utils.cache import sessions
        s = sessions.list_sessions(limit=20)
        if s:
            for sess in s:
                print(f"  [{sess['status'].upper()}] {sess['target']} — {sess['goal'][:50]} ({sess['created']})")
        else:
            print("No scan history yet")
    
    async def _cmd_config(self):
        from kemi_claw.models.multi_model import get_current, list_providers
        cfg = get_current()
        print(f"Provider: {cfg['provider']}")
        print(f"Model: {cfg['model']}")
        print("Available:")
        for p in list_providers():
            print(f"  {p['id']}: {p['name']} ({p['default_model']})")
    
    async def _cmd_scan(self, target):
        print(f"🐺 Scanning {target}...")
        from kemi_claw.tools.parallel_scanner import full_audit_parallel
        result = await full_audit_parallel(target)
        print(f"  {result['success']}/{result['total']} tools | {result['findings']} findings | {result['elapsed_seconds']}s")
    
    async def _cmd_quick(self, target):
        from kemi_claw.tools.parallel_scanner import parallel_vuln_scan
        result = await parallel_vuln_scan(target)
        print(f"  {result['tested']} tests | {result['vulnerable']} vulns found")
    
    async def _cmd_vuln(self, target, vtype):
        from kemi_claw.tools.mcp_registry import registry
        tool_map = {"sqli": "scan_sqli", "xss": "scan_xss", "ssrf": "scan_ssrf", 
                     "lfi": "scan_lfi", "xxe": "scan_xxe", "ssti": "scan_ssti"}
        tool = tool_map.get(vtype.lower())
        if tool:
            result = await registry.call(tool, {"target": target})
            print(json.dumps(result, indent=2, default=str)[:1000])
    
    async def _cmd_recon(self, target):
        from kemi_claw.tools.tech_detect import detect_tech
        from kemi_claw.tools.waf_detector import detect_waf
        tech = await detect_tech(target)
        waf = await detect_waf(target)
        print(f"Technologies ({tech.get('tech_count',0)}): {tech.get('technologies',[])}")
        print(f"WAF: {waf.get('wafs', [])}")
    
    async def _cmd_agent(self, task):
        from kemi_claw.core.general_agent import GeneralAgent
        agent = GeneralAgent()
        result = await agent.run(task)
        print(f"  {result['successful']}/{result['steps_executed']} succeeded in {result['elapsed_seconds']}s")
    
    async def _cmd_search(self, query):
        from kemi_claw.tools.web_search import web_search
        r = await web_search(query, 5)
        for i, res in enumerate(r.get("results", [])[:5], 1):
            print(f"  {i}. {res['title'][:80]}")
            print(f"     {res['url']}")
    
    async def _cmd_cve(self, cve_id):
        from kemi_claw.tools.nvd_correlator import nvd_cve_lookup
        r = await nvd_cve_lookup(cve_id)
        if r.get("found"):
            print(f"  {r['cve']} [{r.get('severity','?')}] CVSS {r.get('cvss_score','?')}")
            print(f"  {r.get('description','')[:300]}")
    
    async def _cmd_tech(self, target):
        from kemi_claw.tools.tech_detect import detect_tech
        r = await detect_tech(target)
        print(f"  Found {r.get('tech_count',0)} technologies:")
        for t in r.get("technologies", []):
            print(f"    • {t}")
    
    async def _cmd_waf(self, target):
        from kemi_claw.tools.waf_detector import detect_waf
        r = await detect_waf(target)
        if r.get("waf_detected"):
            print(f"  WAFs detected: {r.get('wafs',[])}")
        else:
            print(f"  No WAF detected")
    
    async def _cmd_dirs(self, target):
        from kemi_claw.tools.dir_bruteforce import dir_quick_scan
        r = await dir_quick_scan(target)
        print(f"  {r['found']}/{r['tested']} paths found")
        for p in r.get("results", [])[:10]:
            print(f"    {p['status']} {p['path']}")
    
    async def _cmd_sensitive(self, target):
        from kemi_claw.tools.sensitive_scanner import scan_sensitive
        r = await scan_sensitive(target)
        print(f"  {r['found']}/{r['tested']} exposed ({r['critical']} critical)")
        for p in r.get("results", [])[:10]:
            print(f"    [{p['severity']}] {p['path']}")
    
    async def _cmd_dns(self, domain):
        from kemi_claw.tools.dns_enum import subdomain_enum
        r = await subdomain_enum(domain)
        print(f"  {r['found']}/{r['tested']} subdomains")
        for s in r.get("subdomains", [])[:10]:
            print(f"    {s['subdomain']} → {s['ip']}")
    
    async def _cmd_whois(self, domain):
        from kemi_claw.tools.dns_enum import whois_lookup
        r = await whois_lookup(domain)
        for k, v in r.items():
            if k != "error": print(f"  {k}: {v}")
    
    async def _cmd_jwt(self, token):
        from kemi_claw.tools.api_security import analyze_jwt
        r = await analyze_jwt(token)
        print(f"  Header: {r.get('header')}")
        print(f"  Payload: {r.get('payload')}")
        for w in r.get("weaknesses", []):
            print(f"  ⚠️  {w}")
    
    async def _cmd_cors(self, target):
        from kemi_claw.tools.api_security import test_cors
        r = await test_cors(target)
        print(f"  Origin: {r.get('allow_origin','none')}")
        for i in r.get("issues", []):
            print(f"  ⚠️  {i}")
    
    async def _cmd_api(self, target):
        from kemi_claw.tools.api_security import api_scan
        r = await api_scan(target)
        print(f"  {r['endpoints_found']}/{r['endpoints_tested']} endpoints")
        for f in r.get("findings", [])[:10]:
            print(f"    HTTP {f['status']} {f['endpoint']}")
    
    async def _cmd_report(self, target):
        from kemi_claw.tools.parallel_scanner import full_audit_parallel
        from kemi_claw.tools.reporter import save_report
        print(f"Running scan on {target}...")
        result = await full_audit_parallel(target)
        path = f"pentest-lab/results/report_{target.replace('/', '_')}.html"
        r = await save_report(target, result.get("results", []), path)
        print(f"Report saved: {path} ({r.get('size',0)} bytes)")


if __name__ == "__main__":
    shell = KemiShell()
    asyncio.run(shell.run())
