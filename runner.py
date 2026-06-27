import asyncio
import json
import argparse
import sys
from pathlib import Path
from dorkengine import DorkEngine
from dorkbrain import DorkBrain

def load_dorks(json_path):
    with open(json_path, "r") as f:
        dorks_dict = json.load(f)
    all_dorks = []
    for cat in dorks_dict.values():
        all_dorks.extend(cat)
    return all_dorks

def load_proxies(path):
    proxies = []
    if Path(path).exists():
        with open(path) as f:
            proxies = [line.strip() for line in f if line.strip()]
    return proxies

def save_results(results, output_path):
    with open(output_path, "w") as f:
        for record in results:
            f.write(json.dumps(record) + "\n")

def filter_interesting(dork, urls, keywords):
    interesting = []
    for url in urls:
        if any(kw in url.lower() for kw in keywords):
            interesting.append({"dork": dork, "url": url})
    return interesting

async def main():
    parser = argparse.ArgumentParser(description="DorkMind Lite Runner")
    parser.add_argument("--dorks-file", default="data/dorks_base.json", help="Path to base dorks JSON")
    parser.add_argument("--model-dir", default="data/model", help="Path to AI model directory")
    parser.add_argument("--use-ai", action="store_true", help="Generate new dorks with AI")
    parser.add_argument("--ai-count", type=int, default=20, help="Number of AI-generated dorks")
    parser.add_argument("--engine", default="duckduckgo", choices=["google", "bing", "duckduckgo", "yahoo"])
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--delay", nargs=2, type=float, default=[2.0, 5.0], metavar=("MIN", "MAX"))
    parser.add_argument("--proxies-file", default="proxies.txt")
    parser.add_argument("--output", default="results.json", help="Output file for interesting results")
    parser.add_argument("--keywords", nargs="+", default=["backup", "config", "admin", ".env", "sql", "password", "index of", "secret", "private", "credential", "dump", "db"])
    parser.add_argument("--training-output", default="data/training_data.json", help="File to append training records")
    parser.add_argument("--domain", default=None, help="Target domain (e.g. example.com)")
    args = parser.parse_args()

    base_dorks = load_dorks(args.dorks_file)
    all_dorks = list(base_dorks)

    if args.use_ai and Path(args.model_dir, "dork_model.h5").exists():
        brain = DorkBrain(args.model_dir)
        ai_generated = [brain.generate_dork() for _ in range(args.ai_count)]
        all_dorks.extend(ai_generated)
        print(f"[+] Added {len(ai_generated)} AI-generated dorks")
    elif args.use_ai:
        print("[-] AI model not found, skipping generation")

    if args.domain:
        domain_filter = args.domain.strip()
        all_dorks = [f"site:{domain_filter} {d}" for d in all_dorks]
        print(f"[+] Domain filter applied: site:{domain_filter}")

    proxies = load_proxies(args.proxies_file)
    if proxies:
        print(f"[+] Loaded {len(proxies)} proxies")
    else:
        print("[!] No proxies, running directly")

    engine = DorkEngine(proxy_list=proxies, delay_range=tuple(args.delay))
    print(f"[*] Running {len(all_dorks)} dorks on {args.engine} with concurrency {args.concurrency}")

    results = await engine.run(all_dorks, engine=args.engine, concurrency=args.concurrency)

   
    if args.domain:
        domain_clean = args.domain.strip().lower()
        cleaned_results = []
        for url_list in results:
           
            cleaned_urls = [url for url in url_list if domain_clean in url.lower()]
            cleaned_results.append(cleaned_urls)
        results = cleaned_results
  

    interesting_records = []
    training_records = []
    for dork, urls in zip(all_dorks, results):
        filtered = filter_interesting(dork, urls, args.keywords)
        interesting_records.extend(filtered)
        for item in filtered:
            training_records.append(item)

    save_results(interesting_records, args.output)
    print(f"[*] Saved {len(interesting_records)} interesting results to {args.output}")

    if training_records and Path(args.training_output).exists():
        with open(args.training_output, "a") as f:
            for rec in training_records:
                f.write(json.dumps(rec) + "\n")
        print(f"[*] Appended {len(training_records)} records to training data")
    elif training_records:
        with open(args.training_output, "w") as f:
            for rec in training_records:
                f.write(json.dumps(rec) + "\n")
        print(f"[*] Created training data with {len(training_records)} records")

if __name__ == "__main__":
    asyncio.run(main())
