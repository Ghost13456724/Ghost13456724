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


HOME = "Earth"
# bible section title -> the realm its contents belong to; sections marked True also list visitable places
REALM_SECTIONS = [("Places", HOME, True), ("Elsewhere", HOME, True), ("The Saha World", "Saha", False),
                  ("The Dominions", "The Dominions", False), ("Below", "Below", False), ("The Murim", "The Murim", False)]


def section(text, title):
    m = re.search(rf"^## (?:[IVXL]+\. )?{re.escape(title)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def lead_terms(body):
    """Lines that open with a bolded name: ('The Celestial Court', the whole line, is_bullet)."""
    for line in body.splitlines():
        m = re.match(r"(\s*-\s+)?(?:the |a |an )?\*\*([^*]+?)[.,:]?\*\*", line, re.I)
        if m:
            yield m.group(2).strip(), re.sub(r"\*\*|^\s*-\s*", "", line).strip(), bool(m.group(1)), len(line) - len(line.lstrip())


def init(game, data):
    """Seed every realm the player's bible describes: Earth's places, and the cards for Saha, the Dominions,
    the realms below and the Murim (what each is, its rules, its powers)."""
    text, added = bible(game), 0
    realms = data.setdefault("realms", {})
    for title, realm, has_places in REALM_SECTIONS:
        body = section(text, title)
        if not body:
            continue
        card = realms.setdefault(realm, {"desc": "", "entries": [], "clock": None})
        if not card["desc"] and not has_places:
            card["desc"] = next((re.sub(r"\*\*", "", l).strip() for l in body.splitlines() if l.strip() and not l.startswith(("-", "|", "**"))), "")
        have = {e["term"] for e in card["entries"]}
        for name, line, bullet, indent in lead_terms(body):
            if has_places:
                for nm in re.findall(r"\*\*([^*]+?)\.?\*\*", line if False else next(l for l in body.splitlines() if name in l)):
                    if nm not in data["places"]:
                        data["places"][nm] = {"realm": realm, "desc": line, "details": [], "regulars": [], "changes": []}
                        added += 1
            elif name not in have:
                card["entries"].append({"term": name, "text": line[:400], "kind": "named" if bullet else "how it works"})
                have.add(name)
                added += 1
    realms.setdefault(HOME, {"desc": "", "entries": [], "clock": None})
    for p in data["places"].values():
        p.setdefault("realm", HOME)
    return added


def realm_now(game):
    from . import book as B
    return B.scene_state(game).get("realm") or HOME


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
    realm = fields.get("realm") or realm_now(game)
    if fields.get("realm") and realm not in data.setdefault("realms", {}):
        data["realms"][realm] = {"desc": "", "entries": [], "clock": None}
        plan.note(f"realm + {realm}")
    if kind == "place" and term not in data["places"]:
        data["places"][term] = {"realm": realm, "desc": fields["text"], "details": [], "regulars": [], "changes": []}
        return plan.note(f"place + {term} ({realm})")
    if place:
        key = find_place(data, place)
        if not key:
            return plan.error(f"unknown place '{place}': add it first with kind=place")
        slot = "regulars" if kind == "person" else "changes" if fields.get("change") else "details"
        data["places"][key][slot].append(f"{term}: {fields['text']}" if kind == "person" else fields["text"])
        plan.note(f"{key}: {slot[:-1]} + {fields['text'][:70]}")
    data["entries"].append({"id": f"L{len(data['entries']) + 1}", "kind": kind, "term": term, "text": fields["text"],
                            "realm": realm, "place": place, "source": fields.get("source", game.stamp())})
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


def callbacks(game, data, limit=3, realm=None):
    """Recorded details the story has gone longest without touching (those of the realm he is in)."""
    sc = scenes(game)
    rows = []
    for e in data["entries"]:
        if realm and e.get("realm", HOME) != realm:
            continue
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
    state = B.scene_state(game)
    where = place or state.get("where") or ""
    key = find_place(data, where) if where else None
    realm = (data["places"][key].get("realm") if key and place else None) or state.get("realm") or HOME
    rows.append(f"WHEN  D{L['day']}" + (f" {date.strftime('%A %d %B %Y')}" if date else "") + f", {L.get('time', '')} ({daypart(L.get('time'))})"
                + (" — a weekend" if date and date.weekday() >= 5 else "") + (" on Earth" if realm != HOME else ""))
    if realm == HOME:
        rows.append(f"SKY   {w['sky']}, {w['low']} to {w['high']} C" + (f" (yesterday: {w['yesterday']})" if w["yesterday"] != w["sky"] else " (same as yesterday)"))
    else:
        card = data.get("realms", {}).get(realm, {"desc": "", "entries": [], "clock": None})
        rows.append(f"REALM {realm}: {card['desc'][:200]}")
        clock = state.get("realm_clock", {}).get(realm)
        rows.append(f"      its own clock: " + (f"day {clock['day']} there" + (f"; the tide: {clock['tide']}" if clock.get("tide") else "") if clock else
                    "not started. Earth's date and Incheon's weather do not apply here: set its day, season and sky once (`book apply` with realm_day, tide) and keep them"))
        for e in [e for e in card["entries"] if e["kind"] == "how it works"][:5]:
            rows.append(f"      rule of this realm: {e['text'][:170]}")
        powers = [e["term"] for e in card["entries"] if e["kind"] != "how it works"]
        if powers:
            rows.append("      named in the bible for this realm: " + ", ".join(powers[:16]))
        local = [k for k, p in data["places"].items() if p.get("realm") == realm]
        rows.append("      places established here: " + (", ".join(local) if local else "none yet; record each one the story visits (`lore add \"<name>\" kind=place realm=\"" + realm + "\" text=...`)"))
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
    for e, n, last in callbacks(game, data, realm=realm):
        rows.append(f"BRING BACK  [{e['kind']}] {e['term']}: {e['text'][:110]}" + (f" (last in scene {last})" if last else " (not seen since it was recorded)"))
    un = unseen(game)
    street = ("korea", "places", "crack", "powers that be", "bestiary", "cup", "people", "elsewhere", "awakening", "contracts", "treasures")
    if realm != HOME:
        street = (realm.lower().replace("the ", ""),) + street                               # where he is comes first
    rank = lambda sec: next((i for i, k in enumerate(street) if k in sec.lower()), 99)     # everyday lore before cosmology
    order = sorted(un.items(), key=lambda kv: (rank(kv[0]), -len(kv[1])))
    pick = [order[(L["day"] + i) % max(1, min(len(order), 6))] for i in range(min(2, len(order)))]
    if realm != HOME and order:
        pick = [order[0]] + [x for x in pick if x[0] != order[0][0]][:1]                    # this realm's own lore first
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
