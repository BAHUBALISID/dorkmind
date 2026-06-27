import requests, json, subprocess, re, shutil
from pathlib import Path

def fetch_nvd_cves(days=30):
    url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?pubStartDate={(datetime.utcnow()-timedelta(days=days)).isoformat()}&pubEndDate={datetime.utcnow().isoformat()}&resultsPerPage=100"
    resp = requests.get(url).json()
    patterns = []
    for vuln in resp.get('vulnerabilities', []):
        cve = vuln['cve']['id']
        desc = vuln['cve']['descriptions'][0]['value']
        products = set(re.findall(r'(?:Apache|nginx|WordPress|Drupal|Joomla|Tomcat|PHP|Python|Django|Flask|Laravel|Microsoft|Windows|Linux|Cisco|Juniper)[\w.-]*', desc, re.I))
        for prod in products:
            patterns.append({
                "tool": "manual / msf",
                "condition": f"product contains {prod}",
                "action": f"searchsploit {prod} && msfconsole -q -x 'search {prod}; exit'",
                "cve": cve,
                "source": "nvd"
            })
    return patterns

def fetch_exploitdb():
    out = subprocess.run(["searchsploit", "--json"], capture_output=True, text=True).stdout
    data = json.loads(out)
    patterns = []
    for exp in data.get('RESULTS_EXPLOIT', []):
        title = exp.get('Title', '')
        cve_match = re.search(r'CVE-\d{4}-\d{4,}', title)
        cve = cve_match.group(0) if cve_match else ''
        patterns.append({
            "tool": "searchsploit",
            "condition": f"title like '%{title}%'",
            "action": f"searchsploit -m {exp.get('EDB-ID','')}",
            "cve": cve,
            "source": "exploitdb"
        })
    return patterns

def fetch_msf_modules():
   
    return []

def update_training(patterns):
    with open("data/training_data.json", "a") as f:
        for p in patterns:
            f.write(json.dumps(p) + "\n")

if __name__ == "__main__":
    update_training(fetch_nvd_cves() + fetch_exploitdb() + fetch_msf_modules())
