import json
import datetime
from cruel.core import paths

"""
A history of every run that ended in death, kept in attempts.json so it survives between games.
Each attempt records how deep the player got (the deepest floor reached, even if they went back up).
"""

ATTEMPTS_FILE = paths.savePath("attempts.json")


def load(fileName=ATTEMPTS_FILE) -> list:
    try:
        with open(fileName, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        return []
    return [a for a in data if isinstance(a, dict) and "deepest" in a]


def record(deepest, gold, fileName=ATTEMPTS_FILE):
    attempts = load(fileName)
    attempts.append({"number": len(attempts) + 1, "deepest": deepest, "gold": gold,
                     "date": datetime.date.today().isoformat()})
    with open(fileName, "w") as f:
        json.dump(attempts, f, indent=2)


def deepestFirst(attempts) -> list:
    """Deepest floor first. Ties go to the earlier attempt (it got there first)."""
    return sorted(attempts, key=lambda a: (-a["deepest"], a["number"]))
