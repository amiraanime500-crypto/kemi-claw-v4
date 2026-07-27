"""Smart CLI output — colored, progress bars, formatted tables."""
import sys, json, time
from datetime import datetime

class Colors:
    GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
    BLUE = "\033[94m"; CYAN = "\033[96m"; MAGENTA = "\033[95m"
    BOLD = "\033[1m"; DIM = "\033[2m"; RESET = "\033[0m"
    @staticmethod
    def ok(s): return f"{Colors.GREEN}{s}{Colors.RESET}"
    def fail(s): return f"{Colors.RED}{s}{Colors.RESET}"
    def warn(s): return f"{Colors.YELLOW}{s}{Colors.RESET}"
    def info(s): return f"{Colors.BLUE}{s}{Colors.RESET}"
    def bold(s): return f"{Colors.BOLD}{s}{Colors.RESET}"


class ProgressBar:
    def __init__(self, total, prefix="", width=30):
        self.total = total; self.current = 0; self.prefix = prefix
        self.width = width; self.start = time.time()
    
    def update(self, n=1, status=""):
        self.current += n
        pct = self.current / max(self.total, 1)
        filled = int(self.width * pct)
        bar = "█" * filled + "░" * (self.width - filled)
        elapsed = time.time() - self.start
        rate = self.current / elapsed if elapsed > 0 else 0
        sys.stdout.write(f"\r{self.prefix} |{bar}| {int(pct*100)}% ({self.current}/{self.total}) [{rate:.1f}/s] {status}")
        sys.stdout.flush()
    
    def done(self, msg=""):
        self.current = self.total
        self.update(0, msg)
        print()


class KemiTable:
    @staticmethod
    def print(headers, rows, title=None):
        if title: print(f"\n{Colors.BOLD}{title}{Colors.RESET}")
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        sep = "+" + "+".join("-" * (w+2) for w in col_widths) + "+"
        header_line = "|" + "|".join(f" {h.ljust(w)} " for h, w in zip(headers, col_widths)) + "|"
        print(sep); print(header_line); print(sep)
        for row in rows:
            line = "|" + "|".join(f" {str(c).ljust(w)} " for c, w in zip(row, col_widths)) + "|"
            print(line)
        print(sep)


def print_scan_header(target, goal, tools_count):
    print(f"{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}🐺 KEMI-CLAW v6.1 — Security Scan{Colors.RESET}")
    print(f"{'='*60}")
    print(f"  Target: {Colors.BOLD}{target}{Colors.RESET}")
    print(f"  Goal:   {Colors.DIM}{goal}{Colors.RESET}")
    print(f"  Tools:  {Colors.info(str(tools_count))} available")
    print(f"  Time:   {Colors.DIM}{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.RESET}")
    print(f"{'─'*60}")


def print_scan_result(results, elapsed):
    total = len(results)
    errs = sum(1 for r in results if isinstance(r.get("result"), dict) and "error" in r.get("result", {}))
    success = total - errs
    rate = success / max(total, 1) * 100
    color = Colors.GREEN if rate >= 80 else Colors.YELLOW if rate >= 50 else Colors.RED
    
    print(f"\n{Colors.CYAN}{'─'*60}{Colors.RESET}")
    print(f"  Results: {Colors.bold(str(total))} steps | {color}{int(rate)}%{Colors.RESET} success")
    print(f"  Passed:  {Colors.ok(str(success))} | Failed: {Colors.fail(str(errs))}")
    print(f"  Time:    {Colors.DIM}{elapsed:.1f}s{Colors.RESET}")
    
    tools = set()
    for r in results:
        step = r.get("step", {}) if isinstance(r.get("step"), dict) else {}
        if step.get("tool"): tools.add(step["tool"])
    
    print(f"  Tools:   {', '.join(sorted(tools))}")
    print(f"{Colors.CYAN}{'='*60}{Colors.RESET}\n")


def print_finding(tool, severity, detail=""):
    icon = {"CRITICAL": "🔥", "HIGH": "⚠️", "MEDIUM": "⚡", "LOW": "ℹ️"}.get(severity, "•")
    color = {"CRITICAL": Colors.RED, "HIGH": Colors.YELLOW, "MEDIUM": Colors.BLUE, "LOW": Colors.DIM}.get(severity, Colors.RESET)
    print(f"  {icon} {color}[{severity}]{Colors.RESET} {Colors.bold(tool)}")
    if detail:
        print(f"     {Colors.DIM}{detail[:120]}{Colors.RESET}")
