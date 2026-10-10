"""
Sunday Hunter Mode v5 — STT-Friendly Commands
==============================================
NEW in v5:
- "whois" — many STT variants (who is, who's, hu is)
- "wayback" — variants (way back, we back)
- "payload sqli" — accepts "s q l i", "sequel", "sql injection"
- Short auto-bot commands: "bot dns X" (defaults: 30s, 5 runs)
"""

import socket
import ssl
import json
import re
import time
import threading
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
REPORTS_DIR = HUNTER_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# STT ERROR CORRECTIONS
# ============================================================
DOMAIN_CORRECTIONS = {
    "figure": "swigger",
    "figures": "swigger",
    "swagger": "swigger",
    "swigert": "swigger",
    "port figure": "portswigger",
    "port swigger": "portswigger",
    "port sweeter": "portswigger",
    "dotnet": ".net",
    "dot net": ".net",
    "dot com": ".com",
    "dot org": ".org",
    "dot in": ".in",
    "dot io": ".io",
    "dot co": ".co",
    "hack the box": "hackthebox",
    "hack thebox": "hackthebox",
    "try hack me": "tryhackme",
    "try hack": "tryhackme",
    "juice shop": "juiceshop",
    "o wasp": "owasp",
    "pico ctf": "picoctf",
    "hacker one": "hackerone",
    "bug crowd": "bugcrowd",
    "you tube": "youtube",
    "git hub": "github",
}


def correct_domain(text):
    t = text.lower().strip()
    for wrong, right in sorted(DOMAIN_CORRECTIONS.items(), key=lambda x: -len(x[0])):
        t = t.replace(wrong, right)
    t = re.sub(r"\s*\.\s*", ".", t)
    t = re.sub(r"\s+", "", t)
    return t


# ============================================================
# LEGAL
# ============================================================
LEGAL_TERMS_TEXT = (
    "TERMS OF USE — Sunday Hunter Mode: "
    "1. I will only scan targets I OWN or have WRITTEN PERMISSION to test. "
    "2. I will respect bug bounty program scope rules. "
    "3. I understand unauthorized scanning is ILLEGAL. "
    "4. I take full legal responsibility for any tool use. "
    "5. Sunday Hunter is a helper — not a license to hack."
)


def terms_accepted():
    if not TERMS_FILE.exists():
        return False
    try:
        data = json.loads(TERMS_FILE.read_text(encoding="utf-8"))
        return bool(data.get("accepted"))
    except Exception:
        return False


def accept_terms():
    try:
        TERMS_FILE.write_text(json.dumps({
            "accepted": True,
            "timestamp": datetime.now().isoformat(),
        }, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


# ============================================================
# AUDIT LOG
# ============================================================
def audit_log(action, target, result="ok"):
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
# RATE LIMIT
# ============================================================
_last_scan_time = [0.0]
_RATE_LIMIT_SECONDS = 10


def rate_limit_check():
    now = time.time()
    if now - _last_scan_time[0] < _RATE_LIMIT_SECONDS:
        remaining = int(_RATE_LIMIT_SECONDS - (now - _last_scan_time[0]))
        return False, f"Rate limit: wait {remaining}s"
    _last_scan_time[0] = now
    return True, "OK"


# ============================================================
# BLOCKED TLDs
# ============================================================
BLOCKED_TLDS = [".gov", ".mil", ".gov.in", ".nic.in", ".police.uk"]


def is_blocked_tld(target):
    t = target.lower().strip()
    return any(t.endswith(tld) for tld in BLOCKED_TLDS)


# ============================================================
# SCOPE
# ============================================================
def load_scope():
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


def _clean_target(target):
    t = (target or "").lower().strip()
    t = correct_domain(t)
    if "://" in t:
        t = urlparse(t).netloc
    t = t.split("/")[0].split(":")[0]
    if not re.match(r"^[a-z0-9.\-]+\.[a-z]{2,}$", t):
        return ""
    return t


def add_to_scope(domain):
    raw = domain.lower().strip()
    corrected = correct_domain(raw)
    domain = _clean_target(corrected)
    if not domain:
        return f"Invalid domain: '{raw}'."
    if is_blocked_tld(domain):
        return f"Refused: {domain} uses a protected TLD."
    scope = load_scope()
    if domain not in scope:
        scope.append(domain)
        try:
            SCOPE_FILE.write_text("\n".join(scope), encoding="utf-8")
        except Exception as e:
            return f"Could not save scope: {e}"
        audit_log("scope_add", domain)
        if corrected != raw:
            return f"Added {domain} to scope (corrected from '{raw}')."
        return f"Added {domain} to authorized scope."
    return f"{domain} is already in scope."


def remove_from_scope(domain):
    raw = domain.lower().strip()
    corrected = correct_domain(raw)
    domain = _clean_target(corrected)
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
    scope = load_scope()
    if not scope:
        return "No scope set. Add one with 'add to scope <domain>' first."
    return "In-scope domains: " + ", ".join(scope)


# ============================================================
# FINDINGS
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


def add_finding(target, category, description, severity="info"):
    findings = load_findings()
    findings.append({
        "target": target,
        "category": category,
        "description": description,
        "severity": severity,
        "timestamp": datetime.now().isoformat(),
    })
    save_findings(findings)
    audit_log("finding_add", target, category)
    return f"Finding saved for {target} ({severity})."


def show_findings(limit=10):
    findings = load_findings()
    if not findings:
        return "No findings saved yet."
    recent = findings[-limit:]
    lines = [
        f"{i+1}. [{f.get('severity','info').upper()}][{f['category']}] {f['target']}: {f['description'][:50]}"
        for i, f in enumerate(recent)
    ]
    return ". ".join(lines)


def clear_findings():
    save_findings([])
    return "All findings cleared."


# ============================================================
# PAYLOAD LIBRARY
# ============================================================
PAYLOAD_LIBRARY = {
    "xss": [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "\"><svg/onload=alert(1)>",
        "'-alert(1)-'",
    ],
    "sqli": [
        "' OR '1'='1",
        "' OR 1=1--",
        "admin' --",
        "' UNION SELECT NULL--",
        "1' AND SLEEP(5)--",
    ],
    "ssrf": [
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost:8080/admin",
        "file:///etc/passwd",
        "gopher://localhost:8080/",
    ],
    "lfi": [
        "../../../../etc/passwd",
        "....//....//....//etc/passwd",
        "/etc/passwd%00",
        "..%2f..%2f..%2fetc%2fpasswd",
    ],
    "open_redirect": [
        "//evil.com",
        "https://evil.com",
        "/\\evil.com",
        "https:evil.com",
    ],
    "xxe": [
        '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><root>&xxe;</root>',
    ],
}

# STT variants for payload types
PAYLOAD_TYPE_ALIASES = {
    # XSS
    "x s s": "xss",
    "excess": "xss",
    # SQLi — MANY variants because Google STT struggles
    "sqli": "sqli",
    "s q l i": "sqli",
    "s q l": "sqli",
    "sql": "sqli",
    "sql injection": "sqli",
    "sequel": "sqli",
    "sequel injection": "sqli",
    "sql eye": "sqli",
    # SSRF
    "ssrf": "ssrf",
    "s s r f": "ssrf",
    "s s r": "ssrf",
    # LFI
    "lfi": "lfi",
    "l f i": "lfi",
    "local file inclusion": "lfi",
    # Open redirect
    "open redirect": "open_redirect",
    "open redirection": "open_redirect",
    # XXE
    "xxe": "xxe",
    "x x e": "xxe",
    "x x e injection": "xxe",
}


def _normalize_payload_type(text):
    """Convert STT-heard payload type to canonical."""
    t = text.lower().strip()

    # Check full phrase first
    for alias, canonical in sorted(PAYLOAD_TYPE_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in t:
            return canonical

    return None


def get_payloads(payload_type):
    """Return payloads by type."""
    canonical = _normalize_payload_type(payload_type)
    if canonical and canonical in PAYLOAD_LIBRARY:
        payloads = PAYLOAD_LIBRARY[canonical]
        return f"{canonical.upper()} payloads ({len(payloads)}): " + " | ".join(payloads[:5])
    return f"Unknown payload type. Available: {', '.join(PAYLOAD_LIBRARY.keys())}"


def list_payload_types():
    return "Available payloads: xss, sqli, ssrf, lfi, open redirect, xxe"


# ============================================================
# AUTO-BOT MODE
# ============================================================
AUTO_BOT_STATE = {
    "active": False,
    "task": None,
    "target": None,
    "interval": 30,
    "max_runs": 5,      # default 5 runs (was 10)
    "runs_done": 0,
    "thread": None,
    "stop_flag": threading.Event(),
}

AUTO_BOT_SPEAK_CALLBACK = None


def set_speak_callback(callback):
    global AUTO_BOT_SPEAK_CALLBACK
    AUTO_BOT_SPEAK_CALLBACK = callback


def _bot_speak(text):
    if AUTO_BOT_SPEAK_CALLBACK:
        try:
            AUTO_BOT_SPEAK_CALLBACK(text)
        except Exception:
            pass
    print(f"[AutoBot] {text}")


def _bot_worker(task, target, interval, max_runs):
    global AUTO_BOT_STATE
    run_num = 0

    while not AUTO_BOT_STATE["stop_flag"].is_set():
        run_num += 1
        AUTO_BOT_STATE["runs_done"] = run_num

        try:
            if task == "dns":
                result = dns_lookup(target)
            elif task == "http":
                result = http_headers(target)
            elif task == "port":
                result = port_scan(target)
            elif task == "subdomain":
                result = subdomain_scan(target)
            elif task == "tech":
                result = tech_detect(target)
            elif task == "ssl":
                result = ssl_info(target)
            else:
                result = f"Unknown task: {task}"

            _bot_speak(f"Run {run_num} of {task} on {target}: {result[:100]}")
        except Exception as e:
            _bot_speak(f"Run {run_num} failed: {e}")

        if max_runs > 0 and run_num >= max_runs:
            _bot_speak(f"Auto-bot complete — {run_num} runs done.")
            break

        for _ in range(interval):
            if AUTO_BOT_STATE["stop_flag"].is_set():
                return
            time.sleep(1)

    AUTO_BOT_STATE["active"] = False


def start_autobot(task, target, interval=30, max_runs=5):
    global AUTO_BOT_STATE

    if AUTO_BOT_STATE["active"]:
        return "Auto-bot already running. Say 'stop bot' first."

    target = _clean_target(target)
    if not target:
        return "Invalid target."

    safe, msg = _safety_check(target)
    if not safe:
        return msg

    valid_tasks = ["dns", "http", "port", "subdomain", "tech", "ssl"]
    if task not in valid_tasks:
        return f"Invalid task. Available: {', '.join(valid_tasks)}"

    AUTO_BOT_STATE["stop_flag"].clear()
    AUTO_BOT_STATE["active"] = True
    AUTO_BOT_STATE["task"] = task
    AUTO_BOT_STATE["target"] = target
    AUTO_BOT_STATE["interval"] = interval
    AUTO_BOT_STATE["max_runs"] = max_runs
    AUTO_BOT_STATE["runs_done"] = 0

    t = threading.Thread(
        target=_bot_worker,
        args=(task, target, interval, max_runs),
        daemon=True,
    )
    AUTO_BOT_STATE["thread"] = t
    t.start()

    runs_str = f"max {max_runs}" if max_runs > 0 else "infinite"
    return f"Auto-bot started: {task} on {target}, every {interval}s, {runs_str}."


def stop_autobot():
    global AUTO_BOT_STATE
    if not AUTO_BOT_STATE["active"]:
        return "Auto-bot not running."
    AUTO_BOT_STATE["stop_flag"].set()
    return f"Auto-bot stopped. Total runs: {AUTO_BOT_STATE['runs_done']}."


def autobot_status():
    if AUTO_BOT_STATE["active"]:
        return f"Auto-bot running: {AUTO_BOT_STATE['task']} on {AUTO_BOT_STATE['target']}, run #{AUTO_BOT_STATE['runs_done']}."
    return "Auto-bot not running."


# ============================================================
# SAFETY
# ============================================================
def _safety_check(target):
    if not terms_accepted():
        return False, "Legal terms not accepted. Say 'accept terms' first."
    if is_blocked_tld(target):
        return False, f"Refused: {target} uses a protected TLD."
    in_scope = is_in_scope(target)
    if in_scope is None:
        return False, f"No scope set. Add {target} with 'add to scope {target}'."
    if not in_scope:
        return False, f"REFUSED: {target} not in scope."
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
            return f"A record: {ip}"
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
        return msg
    if not REQUESTS_OK:
        return "requests not installed."

    for scheme in ["https", "http"]:
        try:
            r = requests.get(f"{scheme}://{target}", timeout=8,
                             allow_redirects=True, verify=False)
            headers = r.headers
            server = headers.get("Server", "unknown")
            powered = headers.get("X-Powered-By", "unknown")
            title = ""
            m = re.search(r"<title>(.*?)</title>", r.text[:2000],
                          re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()[:60]
            audit_log("http_headers", target, "ok")
            return f"Status {r.status_code}. Server: {server}. Powered by: {powered}. Title: {title}"
        except Exception:
            continue
    return f"Could not connect to {target}"


def security_headers_check(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("security_headers", target, f"blocked: {msg}")
        return msg
    if not REQUESTS_OK:
        return "requests not installed."

    try:
        response = requests.get(
            f"https://{target}",
            timeout=8,
            allow_redirects=False,
        )
    except Exception as e:
        audit_log("security_headers", target, f"failed: {e}")
        return f"Security header check failed: {e}"

    headers = response.headers
    checked_headers = [
        "Strict-Transport-Security",
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    ]
    missing = [name for name in checked_headers if not headers.get(name)]
    final_url = getattr(response, "url", f"https://{target}")
    if not final_url.lower().startswith("https://"):
        missing.insert(0, "HTTPS redirect (final URL is not HTTPS)")
    redirect_note = ""
    if 300 <= response.status_code < 400:
        redirect_note = ". Redirect not followed to avoid leaving the authorized scope"

    audit_log(
        "security_headers",
        target,
        f"ok: {len(checked_headers) - len([h for h in checked_headers if h in missing])} present, {len(missing)} missing",
    )
    if missing:
        return (
            f"HTTP {response.status_code}. Missing/review: "
            f"{', '.join(missing)}. Present: "
            f"{', '.join(name for name in checked_headers if headers.get(name)) or 'none'}"
            f"{redirect_note}"
        )
    return (
        f"HTTP {response.status_code}. All checked security headers are present."
        f"{redirect_note}"
    )


def email_dns_check(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        audit_log("email_dns_check", target, f"blocked: {msg}")
        return msg
    if not DNS_OK:
        return "dnspython not installed; email DNS posture check is unavailable."

    try:
        txt_records = dns.resolver.resolve(target, "TXT", lifetime=5)
        spf_records = [
            str(record).strip('"')
            for record in txt_records
            if re.search(r"\bv=spf1\b", str(record), re.IGNORECASE)
        ]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        spf_records = []
    except Exception as e:
        audit_log("email_dns_check", target, f"failed: {e}")
        return f"Email DNS lookup failed for {target}: {e}"

    try:
        dmarc_records = dns.resolver.resolve(
            f"_dmarc.{target}", "TXT", lifetime=5
        )
        dmarc_records = [
            str(record).strip('"')
            for record in dmarc_records
            if re.search(r"\bv=dmarc1\b", str(record), re.IGNORECASE)
        ]
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        dmarc_records = []
    except Exception as e:
        audit_log("email_dns_check", target, f"failed: {e}")
        return f"Email DNS lookup failed for {target}: {e}"

    findings = []
    if not spf_records:
        findings.append("no SPF record found")
    elif len(spf_records) > 1:
        findings.append(f"{len(spf_records)} SPF records found; review for duplicates")
    else:
        findings.append(f"SPF: {spf_records[0][:180]}")

    if not dmarc_records:
        findings.append("no DMARC record found")
    else:
        policy = re.search(
            r"(?:^|;)\s*p\s*=\s*(none|quarantine|reject)\b",
            dmarc_records[0],
            re.IGNORECASE,
        )
        if policy:
            findings.append(f"DMARC policy: {policy.group(1).lower()}")
        else:
            findings.append("DMARC record found; policy could not be read")

    audit_log(
        "email_dns_check",
        target,
        f"ok: {len(spf_records)} SPF, {len(dmarc_records)} DMARC",
    )
    return ". ".join(findings)


def http_methods(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        return msg
    if not REQUESTS_OK:
        return "requests not installed."

    methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "TRACE"]
    allowed = []
    for m in methods:
        try:
            r = requests.request(m, f"https://{target}", timeout=5, verify=False)
            if r.status_code < 400 or r.status_code == 401:
                allowed.append(f"{m}({r.status_code})")
        except Exception:
            continue

    audit_log("http_methods", target, "ok")
    if allowed:
        return f"Allowed methods on {target}: {', '.join(allowed)}"
    return f"No methods responded on {target}"


def robots_check(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        return msg
    if not REQUESTS_OK:
        return "requests not installed."

    try:
        r = requests.get(f"https://{target}/robots.txt", timeout=8)
        if r.status_code != 200:
            return f"No robots.txt (status {r.status_code})"
        content = r.text[:800]
        lines = [l.strip() for l in content.splitlines()
                 if l.strip() and not l.startswith("#")]
        disallowed = [l for l in lines if l.lower().startswith("disallow")]
        sitemaps = [l for l in lines if l.lower().startswith("sitemap")]
        parts = [f"robots.txt has {len(lines)} rules"]
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
        return msg

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        with socket.create_connection((target, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=target) as ssock:
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
    1433: "MSSQL", 1521: "Oracle", 1723: "PPTP", 2049: "NFS",
    3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC",
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
                if s.connect_ex((ip, port)) == 0:
                    open_ports.append(f"{port}({service})")
        except Exception:
            continue

    audit_log("port_scan", target, f"ok: {len(open_ports)} open")
    if open_ports:
        return f"Open ports on {target} ({len(open_ports)}): {', '.join(open_ports)}"
    return f"No common ports open on {target}"


def whois_lookup(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
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
    "m", "mobile", "secure", "ssl", "login", "auth", "sso",
    "docs", "wiki", "support", "help", "forum", "community",
]


def subdomain_scan(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        return msg

    parts = target.split(".")
    root = ".".join(parts[-2:]) if len(parts) > 2 else target

    found = []
    for sub in COMMON_SUBDOMAINS:
        fqdn = f"{sub}.{root}"
        try:
            ip = socket.gethostbyname(fqdn)
            found.append(f"{sub}({ip})")
        except Exception:
            continue

    audit_log("subdomain_scan", target, f"ok: {len(found)} found")
    if found:
        return f"Found {len(found)} subdomains: {', '.join(found[:10])}"
    return f"No common subdomains found for {root}"


def wayback_urls(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        return msg
    if not REQUESTS_OK:
        return "requests not installed."

    try:
        url = f"http://web.archive.org/cdx/search/cdx?url={target}/*&output=json&limit=100&fl=original"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return f"Wayback API returned {r.status_code}"

        data = r.json()
        if not data or len(data) < 2:
            return f"No wayback URLs found for {target}"

        urls = [row[0] for row in data[1:] if row]
        unique = list(set(urls))[:10]

        save_path = HUNTER_DIR / f"wayback_{target.replace('.', '_')}.txt"
        try:
            save_path.write_text("\n".join(urls), encoding="utf-8")
        except Exception:
            pass

        audit_log("wayback_urls", target, f"ok: {len(urls)} urls")
        return f"Found {len(urls)} wayback URLs. Sample: {', '.join(unique[:5])}."
    except Exception as e:
        return f"Wayback fetch failed: {e}"


def tech_detect(target):
    target = _clean_target(target)
    if not target:
        return "Invalid domain."
    safe, msg = _safety_check(target)
    if not safe:
        return msg
    if not REQUESTS_OK:
        return "requests not installed."

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
# REPORT GENERATOR
# ============================================================
def generate_report():
    findings = load_findings()
    if not findings:
        return "No findings to report."

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / f"report_{timestamp}.md"

    lines = [
        f"# Sunday Hunter Report",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Total Findings**: {len(findings)}",
        "",
        "## Summary by Severity",
        "",
    ]

    severity_counts = {}
    for f in findings:
        sev = f.get("severity", "info").upper()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    for sev, cnt in severity_counts.items():
        lines.append(f"- **{sev}**: {cnt}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Findings")
    lines.append("")

    for i, f in enumerate(findings, 1):
        sev = f.get("severity", "info").upper()
        lines.append(f"### {i}. [{sev}] {f['target']}")
        lines.append(f"- **Category**: {f['category']}")
        lines.append(f"- **Description**: {f['description']}")
        lines.append(f"- **Time**: {f.get('timestamp', 'N/A')}")
        lines.append("")

    try:
        report_path.write_text("\n".join(lines), encoding="utf-8")
        audit_log("report_generate", "all", str(report_path))
        return f"Report generated: {report_path.name} ({len(findings)} findings)"
    except Exception as e:
        return f"Report failed: {e}"


# ============================================================
# COMMAND PARSER
# ============================================================
def handle_hunter_command(text):
    t = text.lower().strip()

    # ---- Legal ----
    if "accept terms" in t or "i accept" in t or "accept legal" in t or t.strip() == "acceptance":
        if accept_terms():
            return "Legal terms accepted. Stay ethical.", True
        return "Could not save acceptance.", True

    if "legal terms" in t or "show terms" in t:
        return LEGAL_TERMS_TEXT, True

    if "audit log" in t or "show audit" in t or "show log" in t:
        try:
            if AUDIT_FILE.exists():
                lines = AUDIT_FILE.read_text(encoding="utf-8").strip().splitlines()
                return f"Last {len(lines[-10:])} entries: " + " | ".join(lines[-10:]), True
            return "Audit log empty.", True
        except Exception as e:
            return f"Audit read failed: {e}", True

    # ---- AUTO-BOT (SHORT COMMANDS) ----
    # "bot dns example.com" → defaults 30s, 5 runs
    # "bot dns example.com every 60" → 60s, 5 runs
    # "bot dns example.com max 3" → 30s, 3 runs
    # "bot dns example.com every 60 max 3" → custom
    if t.startswith("bot ") and "stop" not in t and "status" not in t:
        # Format: "bot <task> <target> [every N] [max M]"
        rest = t[4:].strip()

        # Extract task
        task = None
        for tk in ["dns", "http", "port", "subdomain", "tech", "ssl"]:
            if rest.startswith(tk + " ") or rest == tk:
                task = tk
                rest = rest[len(tk):].strip()
                break

        if not task:
            return "Usage: 'bot dns example.com' or 'bot port example.com every 60 max 3'", True

        # Extract optional "every N" and "max M"
        interval = 30
        max_runs = 5

        m = re.search(r"every (\d+)", rest)
        if m:
            interval = int(m.group(1))
            rest = re.sub(r"every \d+", "", rest).strip()

        m = re.search(r"max (\d+)", rest)
        if m:
            max_runs = int(m.group(1))
            rest = re.sub(r"max \d+", "", rest).strip()

        target = rest.strip()
        if not target:
            return "Please specify a target. Example: 'bot dns example.com'", True

        return start_autobot(task, target, interval, max_runs), True

    # Old-style bot commands (keep for backward compatibility)
    if "start bot" in t or "auto bot" in t or "autobot" in t:
        target = ""
        task = ""
        interval = 30
        max_runs = 5

        for tk in ["dns", "http", "port", "subdomain", "tech", "ssl"]:
            if tk in t:
                task = tk
                break

        if " on " in t:
            target = t.split(" on ", 1)[1].strip()
        elif task:
            idx = t.find(task)
            if idx != -1:
                after = t[idx + len(task):].strip()
                after = re.sub(r"every \d+.*", "", after).strip()
                after = re.sub(r"max \d+.*", "", after).strip()
                target = after

        m = re.search(r"every (\d+)", t)
        if m:
            interval = int(m.group(1))

        m = re.search(r"max (\d+)", t)
        if m:
            max_runs = int(m.group(1))

        target = target.strip()
        if not task or not target:
            return "Usage: 'bot dns example.com' (default 30s, 5 runs)", True

        return start_autobot(task, target, interval, max_runs), True

    if "stop bot" in t or "bot stop" in t or "end bot" in t:
        return stop_autobot(), True

    if "bot status" in t or "show bot" in t:
        return autobot_status(), True

    # ---- Payloads (STT-friendly) ----
    if "payload" in t or "play load" in t or "pay load" in t:
        # Extract what comes after "payload"
        rest = t
        for trigger in ["payload", "play load", "pay load"]:
            if trigger in rest:
                rest = rest.split(trigger, 1)[1].strip()
                break

        canonical = _normalize_payload_type(rest)
        if canonical:
            return get_payloads(canonical), True

        # If no type found, list all
        if not rest:
            return list_payload_types(), True

        return f"Unknown payload type: '{rest}'. {list_payload_types()}", True

    # ---- Report ----
    if "generate report" in t or "make report" in t or "create report" in t:
        return generate_report(), True

    # ---- Scope ----
    scope_add_prefixes = [
        "add to scope", "add to score", "add scope", "add the scope",
        "at to scope", "add to skip", "add to scoop", "add to school",
    ]
    for p in scope_add_prefixes:
        if t.startswith(p + " "):
            domain = t[len(p):].strip()
            return add_to_scope(domain), True

    scope_remove_prefixes = [
        "remove from scope", "remove scope", "remove from score",
        "delete from scope", "delete scope",
    ]
    for p in scope_remove_prefixes:
        if t.startswith(p + " "):
            domain = t[len(p):].strip()
            return remove_from_scope(domain), True

    if "show scope" in t or "list scope" in t:
        return show_scope(), True

    # ---- Findings ----
    if t.startswith("save finding ") or t.startswith("save note "):
        rest = t.replace("save finding ", "").replace("save note ", "").strip()
        if not rest:
            return "What finding should I save?", True
        severity = "info"
        for sev in ["critical", "high", "medium", "low", "info"]:
            if sev in rest:
                severity = sev
                rest = rest.replace(sev, "").strip()
                break
        if ":" in rest:
            target, desc = rest.split(":", 1)
            return add_finding(target.strip(), "note", desc.strip(), severity), True
        return add_finding("general", "note", rest, severity), True

    if "show findings" in t or "list findings" in t:
        return show_findings(), True

    if "clear findings" in t or "delete findings" in t:
        return clear_findings(), True

    # ---- Tools ----

    # Passive security posture checks
    for prefix in ("security headers ", "header audit ", "check security headers "):
        if t.startswith(prefix):
            target = t[len(prefix):].strip()
            if target:
                return security_headers_check(target), True

    for prefix in ("email dns ", "email security ", "spf dmarc "):
        if t.startswith(prefix):
            target = t[len(prefix):].strip()
            if target:
                return email_dns_check(target), True

    # DNS
    if t.startswith("dns lookup ") or t.startswith("dns check "):
        target = t.replace("dns lookup ", "").replace("dns check ", "").strip()
        if target:
            return dns_lookup(target), True

    if t.startswith("dns ") and "lookup" not in t:
        target = t.replace("dns ", "").strip()
        if target:
            return dns_lookup(target), True

    # HTTP methods
    if t.startswith("http methods ") or t.startswith("methods of "):
        target = t.replace("http methods ", "").replace("methods of ", "").strip()
        if target:
            return http_methods(target), True

    # HTTP headers
    if t.startswith("http headers ") or t.startswith("http header "):
        target = t.replace("http headers ", "").replace("http header ", "").strip()
        if target:
            return http_headers(target), True

    if "headers of" in t:
        target = t.split("headers of", 1)[1].strip()
        if target:
            return http_headers(target), True

    # Robots
    if "robots" in t and ("check" in t or "scan" in t or "read" in t):
        target = t
        for kw in ["robots check", "robots scan", "robots read",
                   "check robots", "scan robots", "read robots"]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return robots_check(target), True

    # SSL
    if "ssl info" in t or "ssl check" in t or "certificate" in t:
        target = t
        for kw in ["ssl info", "ssl check", "certificate"]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return ssl_info(target), True

    # Port scan
    if "port scan" in t or "scan ports" in t:
        target = t.replace("port scan ", "").replace("scan ports ", "").strip()
        if target:
            return port_scan(target), True

    # Wayback (with STT variants)
    wayback_triggers = ["wayback", "way back", "wait back", "we back",
                        "wait bag", "archived urls", "archive urls"]
    for trigger in wayback_triggers:
        if trigger in t:
            target = t
            for tk in wayback_triggers:
                target = target.replace(tk, "")
            target = target.replace("urls", "").strip()
            if target:
                return wayback_urls(target), True

    # Whois (with STT variants)
    whois_triggers = ["whois", "who is", "who's", "hu is", "who ease",
                      "who's lookup", "who is lookup"]
    for trigger in whois_triggers:
        if trigger in t:
            target = t
            for tk in whois_triggers:
                target = target.replace(tk, "")
            target = target.replace("lookup", "").strip()
            if target:
                return whois_lookup(target), True

    # Subdomain
    if "subdomain" in t and ("scan" in t or "find" in t or "list" in t or "check" in t):
        target = t
        for kw in ["subdomain scan", "subdomain find", "subdomain list",
                   "subdomain check", "scan subdomains", "find subdomains",
                   "check subdomains"]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return subdomain_scan(target), True
        return "Please specify a domain.", True

    # Tech detect
    if "tech detect" in t or "what tech" in t:
        target = t
        for kw in ["tech detect", "what tech on", "what tech"]:
            target = target.replace(kw, "")
        target = target.strip()
        if target:
            return tech_detect(target), True

    # ---- Help ----
    if "hunter help" in t or "hunter commands" in t:
        return (
            "Commands: 'accept terms', 'add to scope X', 'show scope', 'dns X', "
            "'http headers X', 'http methods X', 'robots check X', 'ssl X', "
            "'security headers X', 'email dns X' (SPF/DMARC posture), "
            "'port scan X', 'subdomain scan X', 'wayback X', 'tech detect X', 'whois X', "
            "'payload xss/sqli/ssrf/lfi', 'save finding X: desc', 'show findings', "
            "'generate report', 'bot dns X', 'stop bot', 'bot status', 'hunter exit'."
        ), True

    return None, False


# ============================================================
# SELF TEST
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  Sunday Hunter Mode v5 — STT-Friendly Test")
    print("=" * 60)
    print(f"\nTerms accepted: {terms_accepted()}")
    print(f"Current scope: {show_scope()}")
    print(f"Payloads: {list_payload_types()}")

    # STT tests
    print("\n--- STT Variant Tests ---")
    tests = [
        ("who is tryhackme.com", "whois"),
        ("way back tryhackme.com", "wayback"),
        ("payload s q l i", "sqli"),
        ("payload sequel", "sqli"),
        ("bot dns tryhackme.com", "autobot short"),
        ("bot port tryhackme.com every 60 max 3", "autobot custom"),
    ]
    for test, label in tests:
        print(f"  [{label}] '{test}'")