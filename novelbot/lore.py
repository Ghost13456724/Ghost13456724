"""Lore keeper and world dresser: a world that feels lived in.

lore.json = {"places": {name: {"desc", "details": [...], "regulars": [...], "changes": [...]}},
             "entries": [{"id", "kind", "term", "text", "place", "source"}]}

Three ideas:
  * A detail established once must stay true and should come back. Every detail the story invents
    (a stall, a price, a habit, a headline, a smell) is recorded, and the ones not seen for longest
    are offered again as callbacks.
  * The player's bible is full of lore the story has not shown yet. `lore unseen` lists it, so it can
    arrive through objects and people instead of explanation.
  * Each scene gets an `ambient` sheet: date, weekday, time of day, weather, the place and its
    regulars, a callback, a piece of unseen lore, and what the wider world is doing.
Everything here is player-facing material (the bible and scenes already read), so nothing is hidden.
"""
import hashlib
import os
import re

KINDS = ("place", "custom", "price", "slang", "food", "news", "rumour", "person", "object", "history", "law")
# rough Incheon climate by month: (low C, high C, [(weight, sky)])
CLIMATE = {1: (-6, 2, "clear,clear,overcast,snow,wind"), 2: (-4, 5, "clear,overcast,snow,wind,haze"),
           3: (1, 10, "clear,haze,overcast,drizzle,wind,yellow dust"), 4: (7, 16, "clear,haze,rain,wind,yellow dust,clear"),
           5: (12, 21, "clear,clear,rain,haze,overcast"), 6: (17, 26, "overcast,rain,humid haze,clear,rain"),
           7: (22, 29, "monsoon rain,monsoon rain,humid,overcast,thunder"), 8: (23, 30, "humid,clear,thunder,typhoon wind,rain"),
           9: (17, 26, "clear,clear,rain,overcast,wind"), 10: (10, 19, "clear,clear,haze,wind,overcast"),
           11: (3, 11, "overcast,clear,drizzle,wind,first snow"), 12: (-3, 4, "clear,snow,overcast,wind,clear")}


def load(game):
    return game.json("lore.json", None) or {"places": {}, "entries": []}


def bible(game):
    name = next((n for n in sorted(os.listdir(game.dir)) if "BIBLE" in n.upper() and n.endswith(".md") and "draft" not in n), None)
    return game.text(name) if name else ""


def bible_topics(game):
    """Every bolded term in the player's bible, with the section it belongs to and the line it sits on."""
    out, section = {}, ""
    for line in bible(game).splitlines():
        h = re.match(r"##+\s*(?:[IVXL]+\.\s*)?(.*)", line)
        if h:
            section = h.group(1).strip()
            continue
        if re.match(r"\|?\s*-{3}", line) or section.lower().startswith(("for you", "how we play")):
            continue
        for term in re.findall(r"\*\*([^*]{3,40}?)[.,:]?\*\*", line):
            term = term.strip()
            if term and not term[0].isdigit() and term.lower() not in out:
                out[term.lower()] = {"term": term, "section": section, "line": re.sub(r"\*\*|^\s*[-|]\s*", "", line).strip()[:220]}
    return out


def init(game, data):
    """Seed places from the bible's Places section."""
    m = re.search(r"^## [IVXL]+\. Places\s*$(.*?)(?=^## |^---|\Z)", bible(game), re.M | re.S)
    added = 0
    for line in (m.group(1) if m else "").splitlines():
        for name in re.findall(r"\*\*([^*]+?)\.?\*\*", line):
            if name not in data["places"]:
                data["places"][name] = {"desc": re.sub(r"\*\*|^\s*-\s*", "", line).strip(), "details": [], "regulars": [], "changes": []}
                added += 1
    return added


def scenes(game):
    from . import archive as AR
    return [(s, game.text(s["file"])) for s in AR.live(AR.load(game))]


def _uses(text_by_scene, phrase):
    words = [w for w in re.findall(r"[A-Za-z']{4,}", phrase.lower())][:4]
    if not words:
        return 0, None
    n, last = 0, None
    for s, text in text_by_scene:
        low = text.lower()
        if sum(1 for w in words if w in low) >= max(1, len(words) - 1):
            n, last = n + 1, s["n"]
    return n, last


def add(game, data, term, fields, plan):
    kind = fields.get("kind", "custom")
    if kind not in KINDS:
        return plan.error(f"kind must be one of {', '.join(KINDS)}")
    if not fields.get("text"):
        return plan.error("text=... is required: the detail exactly as the story established it")
    place = fields.get("place")
    if kind == "place" and term not in data["places"]:
        data["places"][term] = {"desc": fields["text"], "details": [], "regulars": [], "changes": []}
        return plan.note(f"place + {term}")
    if place:
        key = find_place(data, place)
        if not key:
            return plan.error(f"unknown place '{place}': add it first with kind=place")
        slot = "regulars" if kind == "person" else "changes" if fields.get("change") else "details"
        data["places"][key][slot].append(f"{term}: {fields['text']}" if kind == "person" else fields["text"])
        plan.note(f"{key}: {slot[:-1]} + {fields['text'][:70]}")
    data["entries"].append({"id": f"L{len(data['entries']) + 1}", "kind": kind, "term": term, "text": fields["text"],
                            "place": place, "source": fields.get("source", game.stamp())})
    plan.note(f"lore + [{kind}] {term}")


def find_place(data, name):
    want = name.lower()
    hits = [k for k in data["places"] if want == k.lower()] or [k for k in data["places"] if want in k.lower() or k.lower() in want]
    return hits[0] if hits else None


def find(game, data, query):
    """Has this been established? Search recorded lore, then the bible, then the scenes."""
    words = [w for w in re.findall(r"[\w']{3,}", query.lower())]
    hit = lambda text: all(w in text.lower() for w in words)
    rows = [f"lore {e['id']} [{e['kind']}] {e['term']}: {e['text']} ({e['source']})" for e in data["entries"] if hit(e["term"] + " " + e["text"])]
    rows += [f"place {k}: {p['desc']}" for k, p in data["places"].items() if hit(k + " " + p["desc"] + " ".join(p["details"]))]
    rows += ["bible: " + re.sub(r"\*\*", "", l).strip()[:200] for l in bible(game).splitlines() if hit(l)][:6]
    for s, text in scenes(game):
        for l in text.splitlines():
            if hit(l):
                rows.append(f"scene {s['n']} (D{s['day']}): {l.strip()[:160]}")
                break
    return rows


def unseen(game, limit=12):
    """Bible lore the story has not shown yet, grouped by section. Empty archive = everything is unseen."""
    text = " ".join(t for _, t in scenes(game)).lower()
    out = {}
    for key, t in bible_topics(game).items():
        if key not in text:
            out.setdefault(t["section"], []).append(t)
    return out


def callbacks(game, data, limit=3):
    """Recorded details the story has gone longest without touching."""
    sc = scenes(game)
    rows = []
    for e in data["entries"]:
        n, last = _uses(sc, e["term"] + " " + e["text"])
        rows.append((last or 0, n, e))
    rows.sort(key=lambda r: (r[0], r[1]))
    return [(e, n, last) for last, n, e in rows[:limit]]


def weather(game, day):
    """The same day always gets the same weather, so the sky is a fact of the world."""
    date = game.date_of(day)
    month = date.month if date else 3
    lo, hi, skies = CLIMATE[month]
    h = int(hashlib.sha1(f"{game.ledger.get('flags', {}).get('world', '')}:{day}".encode()).hexdigest(), 16)
    sky = skies.split(",")[h % len(skies.split(","))]
    prev = skies.split(",")[int(hashlib.sha1(f"{game.ledger.get('flags', {}).get('world', '')}:{day - 1}".encode()).hexdigest(), 16) % len(skies.split(","))]
    t_lo, t_hi = lo + (h >> 8) % 4, hi - (h >> 12) % 4
    return {"sky": sky, "low": t_lo, "high": t_hi, "yesterday": prev}


def daypart(time):
    h = int(str(time or "12:00").split(":")[0])
    return ("the dead of night" if h < 5 else "dawn" if h < 7 else "morning" if h < 11 else "midday" if h < 14 else
            "afternoon" if h < 17 else "evening" if h < 20 else "night")


def ambient(game, data, place=None, gm=False):
    """One sheet for the scene about to be written."""
    from . import people as PE, world as W, book as B
    L, rows = game.ledger, []
    date = game.date_of(L["day"])
    w = weather(game, L["day"])
    rows.append(f"WHEN  D{L['day']}" + (f" {date.strftime('%A %d %B %Y')}" if date else "") + f", {L.get('time', '')} ({daypart(L.get('time'))})"
                + (" — a weekend" if date and date.weekday() >= 5 else ""))
    rows.append(f"SKY   {w['sky']}, {w['low']} to {w['high']} C" + (f" (yesterday: {w['yesterday']})" if w["yesterday"] != w["sky"] else " (same as yesterday)"))
    where = place or B.scene_state(game).get("where") or ""
    key = find_place(data, where) if where else None
    if key:
        p = data["places"][key]
        rows.append(f"PLACE {key}: {p['desc']}")
        for d in p["details"][-4:]:
            rows.append(f"      established here: {d}")
        for r in p["regulars"][-4:]:
            rows.append(f"      regular: {r}")
        for c in p["changes"][-2:]:
            rows.append(f"      changed since: {c}")
        if not p["details"]:
            rows.append("      no established details yet: invent two this scene and record them with `lore add`")
    elif where:
        rows.append(f"PLACE {where}: not in the lore yet. Record it: `lore add \"{where}\" kind=place text=\"...\" --write`")
    pdata = PE.load(game)
    near = [k for k, x in pdata["people"].items() if where and x.get("where") and (x["where"].lower() in where.lower() or where.lower() in x["where"].lower())
            and x.get("status") == "alive"]
    if near:
        rows.append("NEAR  " + ", ".join(near) + " (recorded as being here)")
    for e, n, last in callbacks(game, data):
        rows.append(f"BRING BACK  [{e['kind']}] {e['term']}: {e['text'][:110]}" + (f" (last in scene {last})" if last else " (not seen since it was recorded)"))
    un = unseen(game)
    street = ("korea", "places", "crack", "powers that be", "bestiary", "cup", "people", "elsewhere", "awakening", "contracts", "treasures")
    rank = lambda sec: next((i for i, k in enumerate(street) if k in sec.lower()), 99)     # everyday lore before cosmology
    order = sorted(un.items(), key=lambda kv: (rank(kv[0]), -len(kv[1])))
    pick = [order[(L["day"] + i) % max(1, min(len(order), 6))] for i in range(min(2, len(order)))]
    for section, items in pick:
        t = items[(L["day"] * 7 + len(items)) % len(items)]
        rows.append(f"UNSEEN LORE  ({section}) {t['term']}: {t['line'][:150]}")
    wd = W.load(game)
    fresh = [t for t in wd.get("traces", []) if not t.get("surfaced")]
    if fresh:
        rows.append(f"WORLD {len(fresh)} off-screen event(s) have left a trace Mori has not met" + ("" if gm else " (`world status --gm`)"))
        if gm:
            rows += [f"      {t['faction']}: {t['trace']}" for t in fresh[:3]]
    return rows
