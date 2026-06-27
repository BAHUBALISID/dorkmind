```markdown
# DorkMind Lite

Self-learning Google Dorking tool for ethical bug bounty hunters. 
Lightweight, low-resource, runs entirely on your local machine. Features over 3000+ categorized dorks, AI-powered dork generation that learns from your successful findings, and automatic search engine rotation.


## Features

- **3000+ Curated Dorks** – Organized in categories (sensitive files, open directories, login portals, cameras, etc.)
- **AI Dork Generation** – LSTM-based model learns from your training data and generates new high-value dorks
- **Multi-Engine Search** – DuckDuckGo, Bing, Yahoo, Google (no API key required)
- **Proxy Support** – Rotate through a list of proxies to avoid rate limits
- **Async & Fast** – Built with `aiohttp` for concurrent requests
- **Low RAM** – Designed to run on machines with as little as 4 GB RAM
- **Continuous Learning** – Feed successful bug bounty findings back into the AI to improve future dorks


## Installation

### Prerequisites
- Python 3.8 or higher
- pip

### Steps
1. Clone the repository or extract the source code.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
```

3. (Optional) If you want to use proxies, create proxies.txt with one proxy per line (e.g., 127.0.0.1:8080).


Directory Structure

```
dorkmind_lite/
├── data/
│   ├── dorks_base.json          # 3000+ base dorks
│   ├── training_data.json       # Successful dorks for AI learning
│   └── model/                   # Trained AI model files
│       ├── dork_model.h5
│       └── tokenizer.pkl
├── dorkengine.py                # Async search engine
├── dorkbrain.py                 # AI generation & learning
├── runner.py                    # Main CLI
├── train_model.py               # One-time script to create model
├── config.yaml                  # Configuration file
├── requirements.txt
└── README.md
```

---

Quick Start

Run with default settings (DuckDuckGo, no AI, 5 concurrent requests):

```bash
python runner.py
```

This will:

· Load dorks from data/dorks_base.json
· Search each dork on DuckDuckGo
· Save interesting URLs (those matching keywords) to results.json
· Append successful dorks to data/training_data.json for future AI training

---

Configuration

Edit config.yaml to customize:

```yaml
search:
  engine: duckduckgo          # google, bing, yahoo
  concurrency: 5              # simultaneous requests
  delay: {min: 2.0, max: 5.0} # random delay between requests

proxy:
  list_file: proxies.txt
  use_proxies: true

ai:
  use_ai: false               # enable AI dork generation
  generate_count: 20          # number of AI dorks to add
  model_dir: data/model

output:
  results_file: results.json
  training_file: data/training_data.json
  interesting_keywords:       # filter results
    - backup
    - config
    - admin
    - .env
    - sql
    - password
    - index of
    - secret
    - private
    - credential
    - dump
    - db
```

---

Command-Line Options

Argument Description Default
--dorks-file Path to base dorks JSON data/dorks_base.json
--model-dir AI model directory data/model
--use-ai Enable AI-generated dorks False
--ai-count Number of AI dorks to generate 20
--engine Search engine (duckduckgo, bing, yahoo, google) duckduckgo
--concurrency Concurrent search requests 5
--delay MIN MAX Random delay range (seconds) 2.0 5.0
--proxies-file Proxy list file proxies.txt
--output Results output file results.json
--keywords Space-separated keywords to flag (see config)
--training-output Training data file data/training_data.json

Example with AI and Bing:

```bash
python runner.py --use-ai --ai-count 30 --engine bing --concurrency 3
```

---

Training the AI

The AI model learns from successful dorks stored in data/training_data.json. To train it:

1. After finding interesting results, the tool automatically appends them to the training file.
2. Train the model using train_model.py (recommended first time) or manually:
   ```bash
   python train_model.py
   ```
   This will create dork_model.h5 and tokenizer.pkl in data/model/.
3. To retrain with new data later:
   ```python
   from dorkbrain import DorkBrain
   import json
   
   brain = DorkBrain("data/model")
   with open("data/training_data.json") as f:
       good_dorks = [json.loads(line)["dork"] for line in f]
   brain.train(good_dorks, epochs=5)
   brain.save("data/model")
   ```
4. Next time you run with --use-ai, the updated model will generate better dorks tailored to your targets.

---

Important Notes

· Legal: Use only on systems you own or have explicit written permission to test (bug bounty programs, authorized penetration tests). Unauthorized scanning is illegal under laws like the Indian IT Act 2000 and Computer Fraud and Abuse Act (CFAA).
· Ethics: Never misuse this tool for malicious purposes. The included dorks are for educational and authorized security research.
· Rate Limits: Always use reasonable delays and proxies to avoid IP bans. DuckDuckGo is the safest choice for anonymous scanning.
· Results: The tool only captures publicly indexed information. It does not exploit vulnerabilities.

---

Example Workflow

1. Configure config.yaml with your preferred engine and keywords.
2. Run the tool to collect initial interesting URLs.
   ```bash
   python runner.py
   ```
3. Review results.json for potential exposed files/directories.
4. Manually verify each finding in your authorized scope.
5. Add genuinely valuable dorks to training_data.json.
6. Retrain the AI model with python train_model.py.
7. Re-run with --use-ai to let the model generate new, high-probability dorks.

---

Troubleshooting

· ModuleNotFoundError: Run pip install -r requirements.txt.
· No results: Try a different search engine (--engine bing), increase delays, or use proxies.
· Low RAM: Reduce concurrency (--concurrency 2) and avoid AI generation on weaker machines.
· 403/Blocked: Increase delay range, add more proxies, or switch to DuckDuckGo.

---

License

This project is intended for ethical security research only. The author assumes no liability for misuse.

```
