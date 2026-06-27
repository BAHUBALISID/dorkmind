import asyncio
import json
import argparse
import subprocess
import sys
import re
import shutil
from pathlib import Path
from datetime import datetime
from dorkbrain import DorkBrain
from dorkengine import DorkEngine
from brain import ActionBrain


def run_subfinder(domain):
    if not shutil.which("subfinder"):
        return []
    print(f"[*] Running subfinder on {domain}")
    try:
        out = subprocess.check_output(["subfinder", "-d", domain, "-silent"], text=True)
        return [line.strip() for line in out.splitlines() if line.strip()]
    except:
        return []

def run_httpx(hosts):
    if not shutil.which("httpx"):
        return [], []
    print(f"[*] Probing {len(hosts)} hosts with httpx")
    try:
        hosts_str = "\n".join(hosts)
        proc = subprocess.run(["httpx", "-silent", "-status-code", "-title", "-tech-detect", "-json"],
                              input=hosts_str, text=True, capture_output=True, timeout=120)
        results = []
        for line in proc.stdout.splitlines():
            if line.strip():
                try:
                    results.append(json.loads(line))
                except:
                    pass
        live = [r['url'] for r in results if 'url' in r]
        return live, results
    except:
        return [], []

def run_nikto(url):
    if not shutil.which("nikto"):
        return []
    print(f"[*] Nikto scanning {url}")
    try:
        out = subprocess.check_output(["nikto", "-h", url, "-Format", "json"], text=True, timeout=120)
        data = json.loads(out)
        findings = []
        for item in data.get("vulnerabilities", []):
            if item.get("severity", "").lower() in ["medium", "high"]:
                findings.append({"tool": "nikto", "url": url, **item})
        return findings
    except:
        return []

def run_nuclei(url):
    if not shutil.which("nuclei"):
        return []
    print(f"[*] Nuclei scanning {url}")
    try:
        out = subprocess.check_output(
            ["nuclei", "-u", url, "-silent", "-json", "-severity", "medium,high,critical"],
            text=True, timeout=120
        )
        findings = []
        for line in out.splitlines():
            try:
                findings.append(json.loads(line))
            except:
                pass
        return findings
    except:
        return []

def get_nmap(host):
    if not shutil.which("nmap"):
        return ""
    out = subprocess.run(["nmap", "-sV", "-p", "1-1000", "-oX", "-", host], capture_output=True, text=True, timeout=120).stdout
    return out

def parse_nmap(xml):
    ports = []
    for line in xml.splitlines():
        if "portid" in line and "open" in line:
            port = re.search(r'portid="(\d+)"', line)
            service = re.search(r'product="([^"]*)"', line)
            version = re.search(r'version="([^"]*)"', line)
            if port:
                ports.append({"port": port.group(1), "service": service.group(1) if service else "", "version": version.group(1) if version else ""})
    return ports

def get_whatweb(url):
    if not shutil.which("whatweb"):
        return {}
    try:
        out = subprocess.check_output(["whatweb", "-q", "--log-json", "/dev/stdout", url], text=True, timeout=30)
        return json.loads(out) if out else {}
    except:
        return {}

def get_waf(url):
    if not shutil.which("wafw00f"):
        return ""
    try:
        return subprocess.check_output(["wafw00f", "-a", url], text=True, timeout=30).strip()
    except:
        return ""

def get_ssl(url):
    if not url.startswith("https://") or not shutil.which("sslscan"):
        return ""
    try:
        return subprocess.check_output(["sslscan", "--no-colour", url], text=True, timeout=30).strip()
    except:
        return ""


async def run_dorking(domain, use_ai=False, ai_count=20):
    with open("data/dorks_base.json") as f:
        dorks_dict = json.load(f)
    dorks = []
    for cat in dorks_dict.values():
        dorks.extend(cat)
    dorks = [f"site:{domain} {d}" for d in dorks]

    if use_ai:
        model_dir = Path("data/model")
        if (model_dir / "dork_model.h5").exists():
            brain = DorkBrain(str(model_dir))
            ai_dorks = [brain.generate_dork() for _ in range(ai_count)]
            dorks.extend([f"site:{domain} {d}" for d in ai_dorks])

    engine = DorkEngine(proxy_list=[], delay_range=(1, 3))
    results = await engine.run(dorks, engine="bing", concurrency=10)

    filtered = set()
    skip_domains = ["bing.com", "google.com", "yandex.ru", "duckduckgo.com"]
    for url_list in results:
        for url in url_list:
            if domain in url.lower() and not any(s in url for s in skip_domains):
                filtered.add(url)
    return list(filtered)


async def main():
    parser = argparse.ArgumentParser(description="HackMind – Full Autonomous Recon & Hunt")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--full", action="store_true", help="Run full scan (recon + dorking + vuln)")
    parser.add_argument("--use-ai", action="store_true", help="Use AI for dork generation and action suggestion")
    parser.add_argument("--ai-count", type=int, default=30)
    parser.add_argument("--output", default="hackmind_results.json")
    parser.add_argument("--dry-run", action="store_true", help="Only suggest AI actions, don't execute dangerous ones")
    parser.add_argument("--training-file", default="data/training_data.json")
    args = parser.parse_args()

    domain = args.domain.strip().lower()
    report = {"domain": domain, "timestamp": datetime.now().isoformat(), "subdomains": [], "live_hosts": [], "dork_urls": [], "vulns": []}

   
    subs = run_subfinder(domain)
    report["subdomains"] = subs
    targets = list(set(subs + [domain]))
    live_urls, _ = run_httpx(targets)
    report["live_hosts"] = [{"url": u} for u in live_urls]

   
    if args.full:
        dork_urls = await run_dorking(domain, use_ai=args.use_ai, ai_count=args.ai_count)
        report["dork_urls"] = dork_urls
        live_urls.extend(dork_urls)

    
    if args.full and live_urls:
       
        ab = ActionBrain(args.training_file) if args.use_ai else None

        for url in live_urls[:10]:  
            host = url.split("//")[-1].split("/")[0]
            print(f"\n[===] Processing {url}")

           
            snapshot = f"url {url}"
            tech = get_whatweb(url)
            if tech:
                report.setdefault("technology", {})[url] = tech
                for t in tech if isinstance(tech, list) else [tech]:
                    if isinstance(t, dict):
                        snapshot += f" {t.get('name','')} {t.get('version','')}"

            nmap_xml = get_nmap(host)
            if nmap_xml:
                ports = parse_nmap(nmap_xml)
                report.setdefault("ports", {})[url] = ports
                for p in ports:
                    snapshot += f" port {p['port']} {p['service']} {p['version']}"

            waf = get_waf(url)
            if waf:
                report.setdefault("waf", {})[url] = waf
                snapshot += " waf present"

            ssl = get_ssl(url)
            if ssl:
                report.setdefault("ssl", {})[url] = ssl

           
            if ab:
                suggestions = ab.suggest(snapshot)
                print(f"[AI] Suggestions for {url}:")
                for s in suggestions:
                    print(f"  - {s.get('condition','')} -> {s.get('action','')} (CVE: {s.get('cve','')})")
                    if not args.dry_run:
                       
                        action = s.get("action", "")
                        if any(cmd in action for cmd in ["nmap", "nikto", "nuclei", "searchsploit -m"]):
                            print(f"    [EXEC] Running: {action}")
                            subprocess.run(action, shell=True)
                        else:
                            print(f"    [SKIP] Not executed (use --dry-run to review)")

            
            report["vulns"].extend(run_nikto(url))
            report["vulns"].extend(run_nuclei(url))

    
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] Report saved to {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
