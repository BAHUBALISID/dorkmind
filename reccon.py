#!/usr/bin/env python3
import subprocess
import json
import shutil
import sys
import re
import os
from pathlib import Path
from datetime import datetime

def run(cmd, timeout=60, stdin=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=stdin)
        return p.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        print(f"[-] Error: {e}")
        return ""

def tool_exists(name):
    return shutil.which(name) is not None

def get_dns(domain):
    records = {}
    if tool_exists("dig"):
        for rtype in ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "SOA"]:
            out = run(["dig", "+short", rtype, domain])
            if out:
                records[rtype] = out.splitlines()
    return records

def get_http_headers(url):
    if not tool_exists("curl"):
        return {}
    out = run(["curl", "-sIL", "-o", "/dev/null", "-D", "-", url, "--max-time", "15"])
    headers = {}
    for line in out.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            headers[key.strip().lower()] = val.strip()
    return headers

def get_robots_sitemap(url):
    robots = ""
    sitemap = ""
    if tool_exists("curl"):
        robots = run(["curl", "-sk", f"{url}/robots.txt", "--max-time", "10"])
        sitemap = run(["curl", "-sk", f"{url}/sitemap.xml", "--max-time", "10"])
    return robots, sitemap

def get_ssl_cert(host, port=443):
    if not tool_exists("openssl"):
        return {}
    out = run(["openssl", "s_client", "-connect", f"{host}:{port}", "-servername", host, "-showcerts"], timeout=15)
    cert_info = {}
    if "BEGIN CERTIFICATE" in out:
        cert_info["subject"] = re.search(r'subject=(.*)', out)
        if cert_info["subject"]:
            cert_info["subject"] = cert_info["subject"].group(1)
        cert_info["issuer"] = re.search(r'issuer=(.*)', out)
        if cert_info["issuer"]:
            cert_info["issuer"] = cert_info["issuer"].group(1)
        not_before = re.search(r'notBefore=(.*)', out)
        not_after = re.search(r'notAfter=(.*)', out)
        if not_before:
            cert_info["notBefore"] = not_before.group(1)
        if not_after:
            cert_info["notAfter"] = not_after.group(1)
        # Check if expired
        if not_after:
            try:
                from datetime import datetime
                expire = datetime.strptime(not_after.group(1), "%b %d %H:%M:%S %Y %Z")
                if expire < datetime.now():
                    cert_info["expired"] = True
            except:
                pass
    return cert_info

def get_tech(url):
    if tool_exists("whatweb"):
        out = run(["whatweb", "-q", "--log-json", "/dev/stdout", url], timeout=30)
        try:
            data = json.loads(out)
            return data if isinstance(data, list) else [data]
        except:
            pass
    return []

def get_ports(host):
    if tool_exists("nmap"):
        out = run(["nmap", "-sV", "--top-ports", "20", "-oX", "-", host], timeout=120)
        ports = []
        for line in out.splitlines():
            if 'portid=' in line and 'open' in line:
                p = re.search(r'portid="(\d+)"', line)
                s = re.search(r'product="([^"]*)"', line)
                v = re.search(r'version="([^"]*)"', line)
                if p:
                    ports.append({"port": p.group(1), "service": s.group(1) if s else "", "version": v.group(1) if v else ""})
        return ports
    return []

def get_subdomains(domain):
    if tool_exists("subfinder"):
        out = run(["subfinder", "-d", domain, "-silent"], timeout=120)
        return out.splitlines()
    return []

def check_security_headers(headers):
    missing = []
    required = ["x-frame-options", "x-content-type-options", "content-security-policy", "strict-transport-security", "x-xss-protection", "referrer-policy", "permissions-policy"]
    for h in required:
        if h not in headers:
            missing.append(h)
    return missing

def main():
    if len(sys.argv) < 2:
        print("Usage: python advanced_recon.py <domain>")
        sys.exit(1)
    domain = sys.argv[1]
    report = {"domain": domain, "timestamp": datetime.now().isoformat()}
    print(f"[*] Advanced Recon on {domain}")

    # Subdomains
    subs = get_subdomains(domain)
    report["subdomains"] = subs
    targets = list(set([domain] + subs))

    # DNS
    report["dns"] = get_dns(domain)

    # For main domain and live subdomains (we'll check live later)
    hosts_to_scan = []
    if tool_exists("httpx"):
        targets_str = "\n".join(targets)
        out = run(["httpx", "-silent", "-status-code", "-title", "-tech-detect", "-json"], input_text=targets_str, timeout=180)
        live = []
        for line in out.splitlines():
            try:
                d = json.loads(line)
                live.append(d)
            except:
                pass
        report["live_hosts"] = live
        hosts_to_scan = [h.get("url") for h in live if h.get("url")]
    else:
        # fallback: check domain directly
        hosts_to_scan = [f"https://{domain}", f"http://{domain}"]

    # Detailed scan on each live host (limited to 5 to avoid overload)
    for url in hosts_to_scan[:5]:
        print(f"[*] Scanning {url}")
        host = url.split("//")[-1].split("/")[0].split(":")[0]

        headers = get_http_headers(url)
        report.setdefault("headers", {})[url] = headers
        missing_sec = check_security_headers(headers)
        if missing_sec:
            report.setdefault("security_missing_headers", {})[url] = missing_sec

        robots, sitemap = get_robots_sitemap(url)
        if robots:
            report.setdefault("robots", {})[url] = robots
        if sitemap:
            report.setdefault("sitemap", {})[url] = sitemap

        tech = get_tech(url)
        if tech:
            report.setdefault("technology", {})[url] = tech

        ports = get_ports(host)
        if ports:
            report.setdefault("ports", {})[url] = ports

        if url.startswith("https"):
            ssl_info = get_ssl_cert(host)
            if ssl_info:
                report.setdefault("ssl", {})[url] = ssl_info

    # Save full report
    outfile = f"recon_{domain}.json"
    with open(outfile, "w") as f:
        json.dump(report, f, indent=2)
    print(f"[+] Full report saved to {outfile}")

    # Generate training data for AI
    training_entries = []
    # Missing headers -> training pattern
    for url, missing in report.get("security_missing_headers", {}).items():
        entry = {
            "dork": f"site:{domain} inurl:{url.split('/')[-1]}",  # very simple, could be refined
            "url": url,
            "success": True,
            "info": f"Missing security headers: {', '.join(missing)}"
        }
        training_entries.append(entry)
    # Outdated software from technology
    for url, tech_list in report.get("technology", {}).items():
        for t in tech_list:
            if isinstance(t, dict):
                name = t.get("name", "")
                version = t.get("version", "")
                if version and name:
                    entry = {
                        "dork": f'site:{domain} intitle:"{name}" "{version}"',
                        "url": url,
                        "success": True,
                        "info": f"Technology: {name} {version}"
                    }
                    training_entries.append(entry)
    # Open ports
    for url, ports in report.get("ports", {}).items():
        for p in ports:
            if p.get("service"):
                entry = {
                    "dork": f"site:{domain} inurl:{p['service']}",
                    "url": url,
                    "success": True,
                    "info": f"Open port {p['port']} ({p['service']} {p['version']})"
                }
                training_entries.append(entry)

    if training_entries:
        train_file = Path("data/training_data.json")
        with open(train_file, "a") as f:
            for entry in training_entries:
                f.write(json.dumps(entry) + "\n")
        print(f"[+] Added {len(training_entries)} training records to {train_file}")

if __name__ == "__main__":
    main()
