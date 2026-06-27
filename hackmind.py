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

# ---------- Recon helpers ----------
def run_subfinder(domain):
    if not shutil.which("subfinder"):
        return []
    out = subprocess.run(["subfinder","-d",domain,"-silent"], capture_output=True, text=True)
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]

def run_httpx(hosts):
    if not shutil.which("httpx"):
        return [], []
    hosts_str = "\n".join(hosts)
    proc = subprocess.run(["httpx","-silent","-status-code","-title","-tech-detect","-json"],
                          input=hosts_str, text=True, capture_output=True, timeout=180)
    results = []
    for line in proc.stdout.splitlines():
        if line.strip():
            try:
                results.append(json.loads(line))
            except:
                pass
    live = [r['url'] for r in results if 'url' in r]
    return live, results

def run_nikto(url):
    if not shutil.which("nikto"):
        return []
    try:
        out = subprocess.check_output(["nikto","-h",url,"-Format","json"], text=True, timeout=120)
        data = json.loads(out)
        return [{"tool":"nikto","url":url,**v} for v in data.get("vulnerabilities",[]) if v.get("severity","").lower() in ["medium","high"]]
    except:
        return []

def run_nuclei(url):
    if not shutil.which("nuclei"):
        return []
    try:
        out = subprocess.check_output(["nuclei","-u",url,"-silent","-json","-severity","medium,high,critical"],
                                      text=True, timeout=120)
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
    return subprocess.run(["nmap","-sV","-p","1-1000","-oX","-",host], capture_output=True, text=True, timeout=120).stdout

def parse_nmap(xml):
    ports = []
    for line in xml.splitlines():
        if "portid" in line and "open" in line:
            p = re.search(r'portid="(\d+)"', line)
            s = re.search(r'product="([^"]*)"', line)
            v = re.search(r'version="([^"]*)"', line)
            if p:
                ports.append({"port":p.group(1),"service":s.group(1) if s else "","version":v.group(1) if v else ""})
    return ports

def get_whatweb(url):
    if not shutil.which("whatweb"):
        return {}
    try:
        out = subprocess.check_output(["whatweb","-q","--log-json","/dev/stdout",url], text=True, timeout=30)
        if out.strip():
            return json.loads(out)
    except:
        pass
    return {}

def get_waf(url):
    if not shutil.which("wafw00f"):
        return ""
    try:
        return subprocess.check_output(["wafw00f","-a",url], text=True, timeout=30).strip()
    except:
        return ""

def get_ssl(url):
    if not url.startswith("https://") or not shutil.which("sslscan"):
        return ""
    try:
        return subprocess.check_output(["sslscan","--no-colour",url], text=True, timeout=30).strip()
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

    engine = DorkEngine(proxy_list=[], delay_range=(1,3))
    results = await engine.run(dorks, engine="bing", concurrency=10)

    filtered = set()
    skip_domains = ["bing.com","google.com","yandex.ru","duckduckgo.com","yahoo.com"]
    for url_list in results:
        for url in url_list:
            if domain in url.lower() and not any(s in url for s in skip_domains):
                filtered.add(url)
    return list(filtered)


def build_snapshot(url, host, tech, nmap_ports, waf, ssl):
    snap = f"url {url}"
    if tech:
        for t in (tech if isinstance(tech, list) else [tech]):
            if isinstance(t, dict):
                snap += f" {t.get('name','')} {t.get('version','')}"
    if nmap_ports:
        for p in nmap_ports:
            snap += f" port {p['port']} {p['service']} {p['version']}"
    if waf:
        snap += " waf present"
    if ssl:
        snap += " ssl scan done"
    return snap


async def main():
    parser = argparse.ArgumentParser(description="HackMind – Flexible Autonomous Recon & Hunt")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--mode", choices=["recon-only","scan-only","full","auto"], default="full",
                        help="Operation mode: recon-only, scan-only, full (recon+dork+vuln), auto (AI decides)")
    parser.add_argument("--use-ai", action="store_true", help="Use AI for dork generation and action suggestions")
    parser.add_argument("--ai-count", type=int, default=30, help="Number of AI-generated dorks")
    parser.add_argument("--output", default="hackmind_results.json")
    parser.add_argument("--dry-run", action="store_true", help="Only show AI suggestions, don't execute")
    parser.add_argument("--training-file", default="data/training_data.json")
    args = parser.parse_args()

    domain = args.domain.strip().lower()
    report = {
        "domain": domain,
        "timestamp": datetime.now().isoformat(),
        "subdomains": [],
        "live_hosts": [],
        "dork_urls": [],
        "vulns": [],
        "ai_decisions": []
    }

    
    print("[*] Starting recon...")
    subs = run_subfinder(domain)
    report["subdomains"] = subs
    targets = list(set(subs + [domain]))
    live_urls, live_details = run_httpx(targets)
    report["live_hosts"] = [{"url": u} for u in live_urls]
    live_urls = live_urls[:10]  

    if args.mode == "recon-only":
        for url in live_urls:
            host = url.split("//")[-1].split("/")[0]
            tech = get_whatweb(url)
            if tech:
                report.setdefault("technology",{})[url] = tech
            nmap_xml = get_nmap(host)
            if nmap_xml:
                report.setdefault("ports",{})[url] = parse_nmap(nmap_xml)
            waf = get_waf(url)
            if waf:
                report.setdefault("waf",{})[url] = waf
            ssl = get_ssl(url)
            if ssl:
                report.setdefault("ssl",{})[url] = ssl
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"[+] Recon saved to {args.output}")
        return

   
    ab = ActionBrain(args.training_file) if args.use_ai else None

   
    if args.mode == "scan-only":
       
        prev = Path(args.output)
        if prev.exists():
            with open(prev) as f:
                old = json.load(f)
            live_urls = [h['url'] for h in old.get('live_hosts', [])] or live_urls
      
   
    if args.mode == "full":
        print("[*] Dorking...")
        dork_urls = await run_dorking(domain, use_ai=args.use_ai, ai_count=args.ai_count)
        report["dork_urls"] = dork_urls
        live_urls = list(set(live_urls + dork_urls))

    
    for url in live_urls:
        host = url.split("//")[-1].split("/")[0]
        print(f"\n[===] {url}")

        tech = get_whatweb(url)
        nmap_xml = get_nmap(host)
        ports = parse_nmap(nmap_xml) if nmap_xml else []
        waf = get_waf(url)
        ssl = get_ssl(url)

        if tech:
            report.setdefault("technology",{})[url] = tech
        if ports:
            report.setdefault("ports",{})[url] = ports
        if waf:
            report.setdefault("waf",{})[url] = waf
        if ssl:
            report.setdefault("ssl",{})[url] = ssl

        snapshot = build_snapshot(url, host, tech, ports, waf, ssl)

        
        if ab:
            suggestions = ab.suggest(snapshot, max_results=3)
            if args.mode == "auto":
               
                top_action = None
                for s in suggestions:
                    action = s.get('action','')
                    if any(cmd in action for cmd in ["nuclei","wpscan","searchsploit -m"]):
                        top_action = s
                        break
                if not top_action and args.use_ai:
               
                    pass
                if top_action:
                    print(f"[AI] Auto-selected action: {top_action.get('condition','')} -> {top_action.get('action','')}")
                    report["ai_decisions"].append({"url":url, "action":top_action})
                    if not args.dry_run:
                        cmd = top_action['action'].replace("$URL", url)
                        try:
                            subprocess.run(cmd, shell=True, timeout=120)
                        except:
                            pass
            else:
               
                print("[AI] Top suggestions:")
                for s in suggestions:
                    print(f"  {s.get('condition','')} -> {s.get('action','')} (CVE: {s.get('cve','')})")
                    if not args.dry_run and any(cmd in s.get('action','') for cmd in ["nuclei","nikto","searchsploit -m","wpscan"]):
                        cmd = s['action'].replace("$URL", url)
                        print(f"    [EXEC] {cmd}")
                        try:
                            subprocess.run(cmd, shell=True, timeout=120)
                        except:
                            pass

       
        if args.mode in ["full","scan-only"]:
            print("[*] Running standard scans...")
            nikto_findings = run_nikto(url)
            nuclei_findings = run_nuclei(url)
            for f in nikto_findings:
                f["url"] = url
            for f in nuclei_findings:
                f["url"] = url
            report["vulns"].extend(nikto_findings)
            report["vulns"].extend(nuclei_findings)

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n[+] Report saved to {args.output}")

if __name__ == "__main__":
    asyncio.run(main())
