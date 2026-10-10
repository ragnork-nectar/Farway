"""
Sunday Hunter Mode v2 — Legal-First Recon Tools
=================================================
⚠️  ETHICAL USE ONLY:
- Only test domains you OWN or have WRITTEN PERMISSION to test
- Bug bounty programs: STAY within defined scope
- Never test unauthorized targets — it's ILLEGAL (IT Act 2000, IPC 66, etc.)
- Terms of use must be accepted on first run
"""

import socket
import ssl
import json
import re
import time
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import dns.resolver
    DNS_OK = True
except ImportError:
    DNS_OK = False


# ============================================================
# PATHS
# ============================================================
ROOT_DIR = Path(__file__).parent.resolve()
HUNTER_DIR = ROOT_DIR / "user_files" / "hunter"
HUNTER_DIR.mkdir(parents=True, exist_ok=True)

FINDINGS_FILE = HUNTER_DIR / "findings.json"
SCOPE_FILE = HUNTER_DIR / "scope.txt"
TERMS_FILE = HUNTER_DIR / "terms_accepted.json"
AUDIT_FILE = HUNTER_DIR / "audit.log"


# ============================================================
# LEGAL TERMS & DISCLAIMER
# ============================================================
LEGAL_NOTICE = (
    "Hunter mode tools must only be used on targets you own or have "
    "written authorization to test. Unauthorized scanning is illegal "
    "under IT Act 2000 and IPC 66."
)

LEGAL_TERMS_TEXT = (
    "TERMS OF USE — Sunday Hunter Mode:\n"
    "1. I will only scan targets I OWN or have WRITTEN PERMISSION to test.\n"
    "2. I will respect bug bounty program scope rules.\n"
    "3. I understand unauthorized scanning is ILLEGAL.\n"
    "4. I take full legal responsibility for any tool use.\n"
    "5. Sunday Hunter is a helper — not a license to hack."
)


def terms_accepted():
    """Check if user accepted legal terms."""
    if not TERMS_FILE.exists():
        return False
    try:
        data = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
        return bool(data.get("accepted"))
    except Exception:
        return False


def accept_terms():
    """Record user acceptance of legal terms."""
    try:
        TERMS_FILE.write_text(json.dumps({
            "accepted": True,
            "timestamp": datetime.now().isoformat(),
            "terms": LEGAL_TERMS_TEXT,
        }, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def get_legal_notice():
    """Return a short notice for first hunter command."""
    return (
        "IMPORTANT: Hunter tools must only be used on targets you own or have "
        "written permission to test. Unauthorized scanning is illegal. "
        "Say 'accept terms' to continue."
    )


# ============================================================
# AUDIT LOG
# ============================================================
def audit_log(action, target, result="ok"):
    """Log every hunter action for accountability."""
    try:
        entry = {
            "time": datetime.now().isoformat(),
            "action": action,
            "target": target,
            "result": result,
        }
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ============================================================
# RATE LIMITER (prevent mass-scanning)
# ============================================================
_last_scan_time = [0.0]
_RATE_LIMIT_SECONDS = 10


def rate_limit_check():
    """Only allow 1 scan every 10 seconds."""
    now = time.time()
    if now - _last_scan_time[0] < _RATE_LIMIT_SECONDS:
        remaining = int(_RATE_LIMIT_SECONDS - (now - _last_scan_time[0]))
        return False, f"Rate limit: wait {remaining}s before next scan"
    _last_scan_time[0] = now
    return True, "OK"


# ============================================================
# BLOCKED TLDs (extra protection)
# ============================================================
BLOCKED_TLDS = [".gov", ".mil", ".gov.in", ".nic.in", ".police.uk"]


def is_blocked_tld(target):
    """Refuse known government/military TLDs unless explicitly allowed."""
    t = target.lower().strip()
    for tld in BLOCKED_TLDS:
        if t.endswith(tld):
            return True
    return False


# ============================================================
# SCOPE MANAGEMENT
# ============================================================
def load_scope():
    """Load authorized in-scope domains."""
    if not SCOPE_FILE.exists():
        return []
    try:
        return [
            line.strip().lower()
            for line in SCOPE_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    except Exception:
        return []


def is_in_scope(target):
    """Check if target is in authorized scope."""
    scope = load_scope()
    if not scope:
        return None

    target = target.lower().strip()
    if "://" in target:
        target = urlparse(target).netloc
    target = target.split("/")[0].split(":")[0]

    for allowed in scope:
        if target == allowed or target.endswith("." + allowed):
            return True
    return False


def add_to_scope(domain):
    """Add a domain to authorized scope."""
    domain = _clean_target(domain)
    if not domain:
        return "Please specify a valid domain."

    if is_blocked_tld(domain):
        return f"Refused: {domain} uses a protected TLD. Not allowed."

    scope = load_scope()
    if domain not in scope:
        scope.append(domain)
        try:
            SCOPE_FILE.write_text("\n".join(scope), encoding="utf-8")
        except Exception as e:
            return f"Could not save scope: {e}"
        audit_log("scope_add", domain)
        return f"Added {domain} to authorized scope."
    return f"{domain} is already in scope."


def remove_from_scope(domain):
    """Remove a domain from scope."""
    domain = _clean_target(domain)
    scope = load_scope()
    if domain in scope:
        scope.remove(domain)
        try:
            SCOPE_FILE.write_text("\n".join(scope), encoding="utf-8")
        except Exception:
            pass
        audit_log("scope_remove", domain)
        return f"Removed {domain} from scope."
    return f"{domain} not in scope."


def show_scope():
    """List all in-scope domains."""
    scope = load_scope()
    if not scope:
        return "No scope set. Add one with 'add to scope <domain>' first."
    return "In-scope domains: " + ", ".join(scope)


# ============================================================
# FINDINGS MANAGEMENT
# ============================================================
def load_findings():
    if not FINDINGS_FILE.exists():
        return []
    try:
        return json.loads(FINDINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_findings(findings):
    try:
        FINDINGS_FILE.write_text(
            json.dumps(findings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[Hunter] Save failed: {e}")


def add_finding(target, category, description):
    """Save a finding to the notes file."""
    findings = load_findings()
    findings.append({
        "target": target,
        "category": category,
        "description": description,
        "timestamp": datetime.now().isoformat(),
    })
    save_findings(findings)
    audit_log("finding_add", target, category)
    return f"Finding saved for {target}"


def show_findings(limit=10):
    findings = load_findings()
    if not findings:
        return "No findings saved yet."
    recent = findings[-limit:]
    lines = [
        f"{i+1}. [{f['category']}] {f['target']}: {f['description'][:60]}"
        for i, f in enumerate(recent)
    ]
    return ". ".join(lines)


def clear_findings():
    save_findings([])
    return "All findings cleared."


# ============================================================
# TARGET CLEANING + SAFETY
# ============================================================
def _clean_target(target):
    """Clean target — remove protocol, path, port."""
    t = (target or "").lower().strip()
    if "://" in t:
        t = urlparse(t).netloc
    t = t.split("/")[0].split(":")[0]
    # Basic domain validation
    if not re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", t):
        return ""
    return t


def _safety_check(target):
    """
    Returns (safe: bool, message: str).
    Performs:
      - Terms accepted
      - Not blocked TLD
      - In scope
      - Rate limit
    """
    # 1) Terms
    if not terms_accepted():
        return False, "Legal terms not accepted. Say 'accept terms' first."

    # 2) Blocked TLD
    if is_blocked_tld(target):
        return False, f"Refused: {target} uses a protected TLD."

    # 3) Scope
    in_scope = is_in_scope(target)
    if in_scope is None:
        return False, (
            f"No scope set. Add {target} with 'add to scope {target}' "
            "only if you own it or have written permission."
        )
    if not in_scope:
        return False, (
            f"REFUSED: {target} is not in authorized scope. "
            f"This tool must not be used on unauthorized targets. "
            f"Add with 'add to scope {target}' only if you have permission."
        )

    # 4) Rate limit
    ok, msg = rate_limit_check()
    if not ok:
        return False, msg

    return True, "OK"


# ============================================================
# HUNTER TOOLS
# ============================================================
def dns_lookup(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("dns_lookup", target, f"blocked: {msg}")
        return msg

    if not DNS_OK:
        try:
            ip = socket.gethostbyname(target)
            audit_log("dns_lookup", target, "ok")
            return f"A record: {ip} (pip install dnspython for full DNS)"
        except Exception as e:
            return f"DNS failed: {e}"

    results = []
    for rtype in ["A", "AAAA", "MX", "NS", "TXT"]:
        try:
            answers = dns.resolver.resolve(target, rtype, lifetime=5)
            records = [str(r) for r in answers]
            results.append(f"{rtype}: {', '.join(records[:3])}")
        except Exception:
            continue

    audit_log("dns_lookup", target, "ok")
    if results:
        return ". ".join(results)
    return f"No DNS records found for {target}"


def http_headers(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("http_headers", target, f"blocked: {msg}")
        return msg

    if not REQUESTS_OK:
        return "requests library not installed."

    for scheme in ["https", "http"]:
        try:
            r = requests.get(
                f"{scheme}://{target}",
                timeout=8,
                allow_redirects=True,
                verify=False,
            )
            headers = r.headers
            server = headers.get("Server", "unknown")
            powered = headers.get("X-Powered-By", "unknown")
            title = ""
            m = re.search(r"<title>(.*?)</title>", r.text[:2000], re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()[:60]

            audit_log("http_headers", target, "ok")
            return f"Status {r.status_code}. Server: {server}. Powered by: {powered}. Title: {title}"
        except Exception:
            continue
    return f"Could not connect to {target}"


def robots_check(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("robots_check", target, f"blocked: {msg}")
        return msg

    if not REQUESTS_OK:
        return "requests library not installed."

    try:
        r = requests.get(f"https://{target}/robots.txt", timeout=8)
        if r.status_code != 200:
            return f"No robots.txt (status {r.status_code})"

        content = r.text[:800]
        lines = [
            l.strip() for l in content.splitlines()
            if l.strip() and not l.startswith("#")
        ]
        disallowed = [l for l in lines if l.lower().startswith("disallow")]
        sitemaps = [l for l in lines if l.lower().startswith("sitemap")]

        parts = [f"Found robots.txt with {len(lines)} rules"]
        if disallowed:
            parts.append(f"Disallowed ({len(disallowed)}): {', '.join(disallowed[:5])}")
        if sitemaps:
            parts.append(f"Sitemaps: {', '.join(sitemaps[:3])}")
        audit_log("robots_check", target, "ok")
        return ". ".join(parts)
    except Exception as e:
        return f"Robots check failed: {e}"


def ssl_info(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("ssl_info", target, f"blocked: {msg}")
        return msg

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with socket.create_connection((target, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=target) as ssock:
                cert = ssock.getpeercert()

        if not cert:
            ctx2 = ssl.create_default_context()
            with socket.create_connection((target, 443), timeout=8) as sock:
                with ctx2.wrap_socket(sock, server_hostname=target) as ssock:
                    cert = ssock.getpeercert()

        subject = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))
        not_after = cert.get("notAfter", "unknown")
        san = cert.get("subjectAltName", [])

        cn = subject.get("commonName", "N/A")
        issuer_cn = issuer.get("commonName", "N/A")

        audit_log("ssl_info", target, "ok")
        return f"CN: {cn}. Issuer: {issuer_cn}. Expires: {not_after}. SANs: {len(san)}"
    except Exception as e:
        return f"SSL check failed: {e}"


COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    80: "HTTP", 110: "POP3", 111: "RPC", 135: "MSRPC", 139: "NetBIOS",
    143: "IMAP", 443: "HTTPS", 445: "SMB", 993: "IMAPS", 995: "POP3S",
    1433: "MSSQL", 1521: "Oracle", 1723: "PPTP", 3306: "MySQL",
    3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
    5985: "WinRM-HTTP", 5986: "WinRM-HTTPS", 6379: "Redis",
    8000: "HTTP-Alt", 8080: "HTTP-Proxy", 8443: "HTTPS-Alt",
    9200: "Elasticsearch", 27017: "MongoDB",
}


def port_scan(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("port_scan", target, f"blocked: {msg}")
        return msg

    try:
        ip = socket.gethostbyname(target)
    except Exception as e:
        return f"Could not resolve {target}: {e}"

    open_ports = []
    for port, service in COMMON_PORTS.items():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                result = s.connect_ex((ip, port))
                if result == 0:
                    open_ports.append(f"{port} ({service})")
        except Exception:
            continue

    audit_log("port_scan", target, f"ok: {len(open_ports)} open")
    if open_ports:
        return f"Open ports on {target}: {', '.join(open_ports)}"
    return f"No common ports open on {target}"


def whois_lookup(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("whois", target, f"blocked: {msg}")
        return msg

    parts = target.split(".")
    root = ".".join(parts[-2:]) if len(parts) > 2 else target

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect(("whois.iana.org", 43))
            s.sendall((root + "\r\n").encode())

            response = b""
            while True:
                data = s.recv(4096)
                if not data:
                    break
                response += data
                if len(response) > 4000:
                    break

        text = response.decode("utf-8", errors="ignore")
        info = []
        for line in text.splitlines():
            low = line.lower()
            if any(k in low for k in ["registrar:", "creation date:", "expiry", "org:", "country:"]):
                info.append(line.strip())

        audit_log("whois", target, "ok")
        if info:
            return ". ".join(info[:5])
        return f"Whois done for {root}."
    except Exception as e:
        return f"Whois failed: {e}"


COMMON_SUBDOMAINS = [
    "www", "mail", "ftp", "webmail", "smtp", "pop", "ns1", "ns2",
    "dev", "staging", "test", "api", "app", "admin", "portal",
    "blog", "shop", "store", "cdn", "static", "assets",
    "dashboard", "panel", "cpanel", "whm", "webdisk",
    "vpn", "remote", "gateway", "router", "git", "gitlab",
    "jenkins", "ci", "stage", "uat", "demo", "beta",
]


def subdomain_scan(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("subdomain_scan", target, f"blocked: {msg}")
        return msg

    parts = target.split(".")
    root = ".".join(parts[-2:]) if len(parts) > 2 else target

    found = []
    for sub in COMMON_SUBDOMAINS:
        fqdn = f"{sub}.{root}"
        try:
            ip = socket.gethostbyname(fqdn)
            found.append(f"{sub} → {ip}")
        except Exception:
            continue

    audit_log("subdomain_scan", target, f"ok: {len(found)} found")
    if found:
        return f"Found {len(found)} subdomains: {', '.join(found[:8])}"
    return f"No common subdomains found for {root}"


def tech_detect(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("tech_detect", target, f"blocked: {msg}")
        return msg

    if not REQUESTS_OK:
        return "requests library not installed."

    try:
        r = requests.get(f"https://{target}", timeout=8, verify=False)
        headers = r.headers
        body_lower = r.text[:5000].lower()

        techs = []
        checks = {
            "Server": "server",
            "X-Powered-By": "powered",
            "X-AspNet-Version": "ASP.NET",
            "X-Generator": "generator",
        }
        for header, label in checks.items():
            val = headers.get(header)
            if val:
                techs.append(f"{label}: {val}")

        patterns = {
            "WordPress": ["wp-content", "wp-includes"],
            "React": ["_next", "react"],
            "Angular": ["ng-app", "angular"],
            "Vue": ["vue.js", "vue.min"],
            "jQuery": ["jquery"],
            "Bootstrap": ["bootstrap"],
            "Cloudflare": ["cloudflare"],
            "Drupal": ["drupal"],
            "Joomla": ["joomla"],
        }
        for name, sigs in patterns.items():
            if any(s in body_lower for s in sigs):
                techs.append(name)

        audit_log("tech_detect", target, "ok")
        if techs:
            return "Detected: " + ", ".join(techs[:6])
        return f"No specific tech detected on {target}"
    except Exception as e:
        return f"Tech detect failed: {e}"


# ============================================================
# COMMAND PARSER
# ============================================================
def handle_hunter_command(text):
    """
    Parse and execute hunter commands.
    Returns (reply_text, handled: bool).
    """
    t = text.lower().strip()

    # ---- Legal Terms ----
    if "accept terms" in t or "i accept" in t or "accept legal" in t:
        if accept_terms():
            return "Legal terms accepted. Stay ethical — only test authorized targets.", True
        return "Could not save acceptance.", True

    if "legal terms" in t or "show terms" in t or "legal notice" in t:
        return LEGAL_TERMS_TEXT.replace("\n", " "), True

    if "audit log" in t or "show audit" in t or "show log" in t:
        try:
            if AUDIT_FILE.exists():
                lines = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
                recent = lines[-10:]
                return f"Last {len(recent)} audit entries: " + " | ".join(recent), True
            return "Audit log empty.", True
        except Exception as e:
            return f"Audit read failed: {e}", True

    # ---- Scope ----
    if t.startswith("add to scope ") or t.startswith("add scope "):
        domain = t.replace("add to scope ", "").replace("add scope ", "").strip()
        return add_to_scope(domain), True

    if t.startswith("remove from scope ") or t.startswith("remove scope "):
        domain = t.replace("remove from scope ", "").replace("remove scope ", "").strip()
        return remove_from_scope(domain), True

    if "show scope" in t or "list scope" in t or "what's in scope" in t or "whats in scope" in t:
        return show_scope(), True

    # ---- Findings ----
    if t.startswith("save finding ") or t.startswith("save note "):
        rest = t.replace("save finding ", "").replace("save note ", "").strip()
        if not rest:
            return "What finding should I save?", True
        if ":" in rest:
            target, desc = rest.split(":", 1)
            return add_finding(target.strip(), "note", desc.strip()), True
        return add_finding("general", "note", rest), True

    if "show findings" in t or "list findings" in t or "what findings" in t:
        return show_findings(), True

    if "clear findings" in t or "delete findings" in t:
        return clear_findings(), True

    # ---- Tools ----
    if t.startswith("dns lookup ") or t.startswith("dns ") or t.startswith("dns check "):
        target = t.replace("dns lookup ", "").replace("dns check ", "").replace("dns ", "").strip()
        if target:
            return dns_lookup(target), True

    if "http header" in t or "headers of" in t or t.startswith("http headers "):
        target = t.replace("http headers ", "").replace("http header ", "").replace("headers of ", "").strip()
        if target:
            return http_headers(target), True

    if "robots" in t and ("check" in t or "scan" in t or "read" in t):
        target = t
        for kw in ["robots check", "robots scan", "robots read", "check robots", "scan robots", "read robots"]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return robots_check(target), True

    if "ssl info" in t or "ssl check" in t or t.startswith("ssl ") or "certificate" in t:
        target = t
        for kw in ["ssl info", "ssl check", "certificate"]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return ssl_info(target), True

    if "port scan" in t or "scan ports" in t:
        target = t.replace("port scan ", "").replace("scan ports ", "").strip()
        if target:
            return port_scan(target), True

    if "whois" in t:
        target = t.replace("whois lookup ", "").replace("whois ", "").strip()
        if target:
            return whois_lookup(target), True

    if "subdomain" in t and ("scan" in t or "find" in t or "list" in t or "check" in t):
        target = t
        for kw in ["subdomain scan", "subdomain find", "subdomain list", "subdomain check",
                   "scan subdomains", "find subdomains", "check subdomains"]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return subdomain_scan(target), True
        return "Please specify a domain.", True

    if "tech detect" in t or "what tech" in t or t.startswith("tech "):
        target = t
        for kw in ["tech detect", "what tech on", "what tech", "tech "]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return tech_detect(target), True

    # ---- Help ----
    if "hunter help" in t or "what can you do" in t or "hunter commands" in t:
        return (
            "Hunter commands: 'accept terms', 'add to scope example.com', "
            "'remove from scope example.com', 'show scope', "
            "'dns lookup example.com', 'http headers example.com', "
            "'robots check example.com', 'ssl info example.com', "
            "'port scan example.com', 'whois example.com', "
            "'subdomain scan example.com', 'tech detect example.com', "
            "'save finding target: desc', 'show findings', 'audit log', "
            "'hunter exit'."
        ), True

    return None, False


# ============================================================
# SELF TEST
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Sunday Hunter Mode v2 — Legal-First Test")
    print("=" * 60)
    print(f"\nHunter data dir: {HUNTER_DIR}")
    print(f"Scope file:      {SCOPE_FILE}")
    print(f"Findings file:   {FINDINGS_FILE}")
    print(f"Terms accepted:  {terms_accepted()}")
    print(f"\nCurrent scope:   {show_scope()}")
    print(f"\n{LEGAL_NOTICE}\n")
    print("Ready. Integration with sunday.py next.")