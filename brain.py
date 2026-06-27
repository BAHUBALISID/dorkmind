import json
from pathlib import Path

class ActionBrain:
    def __init__(self, training_file="data/training_data.json"):
        self.training_file = Path(training_file)
        self.actions = []  
        self.load()

    def load(self):
        if self.training_file.exists():
            with open(self.training_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        # We only load entries that have condition and action
                        if "condition" in entry and "action" in entry:
                            self.actions.append(entry)
                    except json.JSONDecodeError:
                        pass

    def suggest(self, recon_info, max_results=5):
       
        recon_lower = recon_info.lower()
        scored = []
        for act in self.actions:
            condition = act.get("condition", "").lower()
            keywords = condition.split()
            if not keywords:
                continue
            score = sum(1 for kw in keywords if kw in recon_lower)
            if score > 0:
                scored.append((score, act))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:max_results]]

    def add_entry(self, condition, action, cve="", source="manual"):
        entry = {
            "condition": condition,
            "action": action,
            "cve": cve,
            "source": source
        }
        self.actions.append(entry)
        with open(self.training_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def reinforce(self, recon_info, successful_action):
        """After a successful exploitation, reinforce the pattern."""
        self.add_entry(recon_info, successful_action, source="reinforcement")
