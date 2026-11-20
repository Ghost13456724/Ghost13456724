"""People tracker: where everyone is, how they feel about Mori, and who knows what.

people.json = {"facts": {id: {"text", "pattern"}}, "people": {name: {...}}}
A person's "knows" lists fact ids they hold the truth of; "told" maps a fact id
to the version they were given instead (a cover story, a half-truth).
"""
import re

FIELDS = ("role", "group", "where", "status", "wants", "last_seen")
BLANK = {"people": {}, "facts": {}}


def load(game):
    data = game.json("people.json", None)
    return data if data else {"people": {}, "facts": {}}


def find(data, name):
    want = name.strip().lower()
    for key, p in data["people"].items():
        if want == key.lower() or want in (a.lower() for a in p.get("aliases", [])):
            return key
    hits = [k for k, p in data["people"].items() if any(want in n.lower().split() for n in [k] + p.get("aliases", []))]
    return hits[0] if len(hits) == 1 else None


def new_person(name, **kw):
    parts = name.split()
    bare = re.sub(r"^(Inspector|Director|Chairman|Boss|Dr\.?|Captain|Master)\s+", "", name)
    p = {"aliases": sorted({parts[-1], bare} - {name}) if len(parts) > 1 else [], "role": "", "group": "", "where": "", "status": "alive",
         "trust": 0, "knows": [], "told": {}, "wants": "", "owes": [], "last_seen": "", "notes": []}
    p.update(kw)
    return p


def init(game):
    """Seed from the bible's People section: '- **Name,** 20, role.'"""
    data = load(game)
    bible = next((game.text(n) for n in sorted(game_files(game)) if "BIBLE" in n.upper() and n.endswith(".md") and "draft" not in n), "")
    m = re.search(r"^## [IVXL]+\. People\s*$(.*?)(?=^## |\Z)", bible, re.M | re.S)
    added, group = [], ""
    for line in (m.group(1) if m else "").splitlines():
        g = re.match(r"\*\*([A-Z][A-Za-z ]+)\*\*\s*$", line.strip())
        if g:
            group = g.group(1)
        e = re.match(r"- \*\*([^*,]+?),?\*\*,?\s*(.*)", line)
        if e and not line.startswith(" "):
            name = re.sub(r"^(Inspector|Director|Chairman|Boss|Uncle|Old)\s+", lambda t: t.group(0), e.group(1)).strip().rstrip(".")
            if name not in data["people"]:
                role = re.split(r"(?<=[a-z\d])\.\s", e.group(2))[0].strip().rstrip(".")
                data["people"][name] = new_person(name, role=role[:120], group=group)
                if re.search(r"\bdied\b|\bdead\b", role):
                    data["people"][name]["status"] = "dead"
                added.append(name)
    return data, added


def game_files(game):
    import os
    return os.listdir(game.dir)


def scan(game, data):
    """Trust changes the log records ('Gangu respect +2') that the tracker has not counted yet."""
    out = []
    seen = set(data.get("counted", []))
    for i, line in enumerate(game.log):
        for m in re.finditer(r"\b([A-Z][a-z]+)(?:'s)? (?:goodwill|respect|trust|favor|favour|grudge) ([+-]\d+)", line):
            key = f"{i}:{m.group(1)}:{m.group(2)}"
            if key not in seen:
                out.append((key, m.group(1), int(m.group(2)), line[:60]))
    return out


def apply_update(data, name, upd, stamp, plan):
    """One person's changes from a scene: {"trust": "+2", "where": "...", "learn": [...], "told": {...}, "note": "..."}"""
    key = find(data, name)
    if key is None:
        key = name
        data["people"][key] = new_person(name)
        plan.note(f"new person: {name}")
    p = data["people"][key]
    for k, v in upd.items():
        if k == "trust":
            old = p.get("trust", 0)
            p["trust"] = old + int(v) if str(v)[:1] in "+-" else int(v)
            plan.note(f"{key}: trust {old} -> {p['trust']}")
        elif k == "learn":
            for fact in v:
                if fact not in data["facts"]:
                    plan.error(f"{key} learns unknown fact '{fact}': add it under facts first")
                elif fact not in p["knows"]:
                    p["knows"].append(fact)
                    p["told"].pop(fact, None)
                    plan.note(f"{key}: now knows {fact}")
        elif k == "told":
            for fact, version in v.items():
                if fact not in data["facts"]:
                    plan.error(f"{key} was told about unknown fact '{fact}': add it under facts first")
                elif fact in p["knows"]:
                    plan.note(f"{key} already knows the truth of {fact}; the cover story will not hold")
                else:
                    p["told"][fact] = version
                    plan.note(f"{key}: told a version of {fact}")
        elif k == "note":
            p["notes"].append(f"{stamp}: {v}")
        elif k == "owes":
            p["owes"].append(v)
        elif k in FIELDS:
            p[k] = v
            if k in ("where", "status"):
                plan.note(f"{key}: {k} -> {v}")
        elif k == "aliases":
            p["aliases"] = sorted(set(p["aliases"]) | set(v))
        else:
            plan.error(f"{key}: unknown field '{k}'")
    p["last_seen"] = upd.get("last_seen", stamp)


def in_scene(data, text):
    """People named in a scene, by any alias."""
    out = []
    for key, p in data["people"].items():
        if any(re.search(rf"\b{re.escape(n)}\b", text) for n in [key] + p.get("aliases", [])):
            out.append(key)
    return out


def scene_findings(data, text, lines):
    finds = []
    present = in_scene(data, text)
    for key in present:
        p = data["people"][key]
        if p.get("status") == "dead":
            finds.append(("WARN", f"{key} is recorded as dead but is named in the scene (fine as a memory or a mention)"))
        elif p.get("status") not in ("alive", "", None):
            finds.append(("NOTE", f"{key} is recorded as '{p['status']}' at {p.get('where') or '?'}; check they could be here"))
    for fid, fact in data["facts"].items():
        if not fact.get("pattern"):
            continue
        hit = next((i for i, l in enumerate(lines, 1) if re.search(fact["pattern"], l, re.I)), None)
        if hit is None:
            continue
        dark = [k for k in present if fid not in data["people"][k]["knows"]]
        lied = [k for k in dark if fid in data["people"][k]["told"]]
        if dark:
            finds.append(("WARN", f"line {hit}: fact '{fid}' surfaces. In the scene but not in the know: {', '.join(dark)}"
                          + (f" (given a cover story: {', '.join(lied)})" if lied else "")
                          + ". An error if one of them says it or acts on it"))
    return finds


def show(data, name=None):
    rows = []
    for key, p in sorted(data["people"].items(), key=lambda kv: (-abs(kv[1].get("trust", 0)), kv[0])):
        if name and find(data, name) != key:
            continue
        rows.append(f"{key:<22} trust {p.get('trust', 0):+d}  {p.get('status', 'alive'):<8} {p.get('where') or '?':<24} "
                    f"last {p.get('last_seen') or '-'}")
        if name:
            for k in ("role", "group", "wants"):
                if p.get(k):
                    rows.append(f"    {k}: {p[k]}")
            if p["knows"]:
                rows.append("    knows: " + ", ".join(p["knows"]))
            for f, v in p["told"].items():
                rows.append(f"    told ({f}): {v}")
            for o in p.get("owes", []):
                rows.append(f"    owes/owed: {o}")
            for n in p["notes"][-6:]:
                rows.append(f"    - {n}")
    return rows
