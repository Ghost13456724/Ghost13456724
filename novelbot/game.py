"""Open a game folder (ledger.json, foes.json, events.json, LOG.md, STATE_NOW.md, gm.py).

All combat numbers come from the folder's own gm.py, so this tool can never
disagree with the dice engine the game is played with.
"""
import copy
import importlib.util
import json
import os
import re
import sys


class Game:
    def __init__(self, folder):
        self.dir = os.path.abspath(folder)
        if not os.path.exists(self.path("ledger.json")):
            raise FileNotFoundError(f"no ledger.json in {self.dir}")
        self.ledger = self.json("ledger.json", {})
        self.foes = self.json("foes.json", {})
        self.events = self.json("events.json", [])
        self.log = self.text("LOG.md").splitlines()
        self.state = self.text("STATE_NOW.md")
        sys.dont_write_bytecode = True   # leave no __pycache__ in the game folder
        spec = importlib.util.spec_from_file_location("game_gm", self.path("gm.py"))
        self.gm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.gm)

    def path(self, name):
        return os.path.join(self.dir, name)

    def text(self, name):
        try:
            with open(self.path(name), encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def json(self, name, default):
        text = self.text(name)
        return json.loads(text) if text.strip() else default

    def sheet(self, level=None, fresh=False):
        """A copy of the ledger; optionally projected to a level and/or fully rested."""
        L = copy.deepcopy(self.ledger)
        if level and level > L["level"]:
            for k in L["stats"]:
                L["stats"][k] += level - L["level"]   # the System gives +1 to every stat per level
            L["level"] = level
            fresh = True
        if fresh:
            self.gm.recalc(L, restore=True)
            L["injuries"] = []
        return L

    def foe(self, name):
        if name in self.foes:
            return name
        want = name.lower().replace(" ", "_")
        hits = [k for k, f in self.foes.items() if want in k.lower() or name.lower() in f.get("name", "").lower()]
        exact = [k for k in hits if k.lower() == want or self.foes[k].get("name", "").lower() == name.lower()]
        if len(exact) == 1 or len(hits) == 1:
            return (exact or hits)[0]
        raise KeyError(f"unknown foe '{name}'" + (f"; did you mean {', '.join(hits)}?" if hits else ""))

    def log_day(self):
        days = [int(m.group(1)) for line in self.log for m in [re.match(r"- D(\d+)", line)] if m]
        return max(days) if days else None

    def rolls(self):
        """Dice the engine logged: (action, foe id, die, dc)."""
        out = []
        for line in self.log:
            m = re.search(r"roll (\w+) (\S*) ?d(\d+) need (-?\d+) \((\d+)%\) dc(\d+)", line)
            if m:
                out.append({"action": m.group(1), "foe": m.group(2), "d": int(m.group(3)), "dc": int(m.group(6))})
        return out
