"""Bookkeeper: write what a scene changed into the game's files, in one step.

The GM (or the bookkeeper bot) describes the scene's changes as a small JSON
"delta". `book apply` validates it, shows the plan, and with --write updates
ledger.json, events.json, people.json, clues.json, LOG.md and STATE_NOW.md together,
so they can no longer drift apart.

It does not replace gm.py: dice, level-ups and new days still go through gm.py,
because those carry rules (daily quest, penalties, full restores).
"""
import os
import re
import shutil
import subprocess
import sys

from . import clues as CL
from . import people as PE
from .game import Plan

EXTRA_SAVE = ["people.json", "clues.json", "factions.json", "scene_state.json", "secrets_watch.json",
              "review_rules.json", "LAST_SCENES.md", "SKILL_TREES.md"]
KEYS = {"day", "time", "where", "with", "now", "pending", "threads_add", "threads_done", "hp", "fatigue", "won", "gold",
        "items_add", "items_remove", "injuries_add", "injuries_heal", "memories_lost", "events_add", "events_done",
        "people", "facts", "clues_placed", "log"}


def _num(old, val, lo=None, hi=None):
    s = str(val)
    new = int(s[1:]) if s.startswith("=") else old + int(s) if s[:1] in "+-" else int(s)
    if lo is not None:
        new = max(lo, new)
    if hi is not None:
        new = min(hi, new)
    return new


def scene_state(game):
    return game.json("scene_state.json", None) or {"where": "", "with": [], "now": "", "pending": "", "threads": []}


def render_state(game, L, S, people, clue_data, events):
    """STATE_NOW.md, rebuilt from the files so it cannot disagree with them."""
    date = game.date_of(L["day"])
    when = f"D{L['day']}" + (f" {date.strftime('%a %d %b %Y')}" if date else "") + f" {L.get('time', '')}"
    hp = f"HP {L['hp']}/{L['hp_max']}" + (" (DOWN, dying)" if L["hp"] <= 0 else "")
    out = [f"# STATE NOW — {L.get('flags', {}).get('world', 'game')}  (written by `bot.py book`; numbers live in ledger.json)",
           f"{when.strip()} | {S.get('where') or '?'} | with: {', '.join(S.get('with') or ['alone'])}",
           f"Mori: Lv {L['level']}, {hp}, MP {L['mp']}/{L['mp_max']}, fatigue {L.get('fatigue', 0)} | "
           f"XP {L.get('xp', 0)}/{100 * L['level']} | won {L.get('won', 0):,} | unspent points {L.get('points', 0)}"]
    inj = L.get("injuries", [])
    out.append("Injuries: " + ("; ".join(f"{i['name']} ({i['mod']:+d})" for i in inj) if inj else "none"))
    lost = L.get("flags", {}).get("memories_lost", [])
    if lost:
        out.append("Memories lost: " + "; ".join(lost))
    out.append("Carrying: " + ("; ".join(L.get("items", [])) or "nothing"))
    if S.get("now"):
        out.append("NOW: " + S["now"])
    if S.get("pending"):
        out.append("PENDING PLAYER CHOICE: " + S["pending"])
    for t in S.get("threads", []):
        out.append("OPEN THREAD: " + t)
    for e in sorted((e for e in events if isinstance(e.get("day"), (int, float)) and not e.get("done") and e["day"] <= L["day"] + 7),
                    key=lambda e: e["day"]):
        out.append(f"DUE D{e['day']} {e.get('time', '')}: {e['text']}")
    here = [PE.find(people, n) for n in S.get("with") or []]
    for key in [k for k in here if k]:
        p = people["people"][key]
        bits = [f"trust {p.get('trust', 0):+d}"] + [f"told ({f}): {v}" for f, v in p["told"].items()]
        if p["knows"]:
            bits.append("knows: " + ", ".join(p["knows"]))
        out.append(f"HERE {key}: " + "; ".join(bits))
    if clue_data.get("ladder"):
        out.append(f"REVEAL LADDER: rung {clue_data['rung']} (details: `bot.py clues status --gm`)")
    return "\n".join(out[:40]) + "\n"


def apply(game, delta, write=False):
    plan = Plan(game)
    L, S = game.sheet(), scene_state(game)
    events = [dict(e) for e in game.events]
    people, clue_data = PE.load(game), CL.load(game)
    had_people, had_clues = bool(game.text("people.json")), bool(game.text("clues.json"))
    for k in set(delta) - KEYS:
        plan.error(f"unknown key '{k}' in the delta")
    if "day" in delta and delta["day"] != L["day"]:
        plan.error(f"the scene is on D{delta['day']} but the ledger is on D{L['day']}. Advance days with `gm.py day +N` "
                   "(it runs the daily-quest rules), then apply again")
    if "time" in delta:
        if not re.fullmatch(r"\d{1,2}:\d{2}", str(delta["time"])):
            plan.error(f"time '{delta['time']}' is not HH:MM")
        elif delta.get("day", L["day"]) == L["day"] and str(delta["time"]).zfill(5) < str(L.get("time", "00:00")).zfill(5):
            plan.error(f"time goes backwards: {L.get('time')} -> {delta['time']} on the same day")
        else:
            L["time"] = delta["time"]
    game.ledger["time"] = L.get("time", "")           # stamps for this delta use the scene's own time
    stamp = game.stamp()
    for k in ("where", "with", "now", "pending"):
        if k in delta:
            S[k] = delta[k]
    S["threads"] = [t for t in S.get("threads", []) if not any(d.lower() in t.lower() for d in delta.get("threads_done", []))]
    S["threads"] += [t for t in delta.get("threads_add", []) if t not in S["threads"]]
    if "hp" in delta:
        old = L["hp"]
        L["hp"] = _num(old, delta["hp"], 0, L["hp_max"])
        plan.note(f"HP {old} -> {L['hp']}/{L['hp_max']}" + ("  !! DOWN: 0 HP rule applies" if L["hp"] == 0 and old > 0 else ""))
    if "fatigue" in delta:
        L["fatigue"] = _num(L.get("fatigue", 0), delta["fatigue"], 0, 100)
    for k in ("won", "gold"):
        if k in delta:
            old = L.get(k, 0)
            L[k] = _num(old, delta[k])
            plan.note(f"{k} {old:,} -> {L[k]:,}")
            if L[k] < 0:
                plan.error(f"{k} would go negative ({L[k]:,})")
    for it in delta.get("items_remove", []):
        match = [x for x in L["items"] if it.lower() in x.lower()]
        if len(match) != 1:
            plan.error(f"items_remove '{it}' matches {len(match)} items in the ledger")
        else:
            L["items"].remove(match[0])
            plan.note(f"item - {match[0]}")
    for it in delta.get("items_add", []):
        L["items"].append(it)
        plan.note(f"item + {it}")
    for inj in delta.get("injuries_add", []):
        if not isinstance(inj, dict) or "name" not in inj or not isinstance(inj.get("mod"), int) or inj["mod"] > 0:
            plan.error(f"injury {inj!r} needs a name and a roll penalty, e.g. {{\"name\": \"cracked ribs\", \"mod\": -1}} (0 = cosmetic)")
        else:
            L.setdefault("injuries", []).append({"name": inj["name"], "mod": inj["mod"]})
            plan.note(f"injury + {inj['name']} ({inj['mod']:+d} on rolls)")
    for name in delta.get("injuries_heal", []):
        match = [i for i in L.get("injuries", []) if name.lower() in i["name"].lower()]
        if not match:
            plan.error(f"injuries_heal '{name}' is not in the ledger")
        for i in match:
            L["injuries"].remove(i)
            plan.note(f"injury - {i['name']}")
    for mem in delta.get("memories_lost", []):
        L.setdefault("flags", {}).setdefault("memories_lost", []).append(mem)
        plan.note(f"memory lost: {mem}")
    for text in delta.get("events_done", []):
        match = [e for e in events if text.lower() in e.get("text", "").lower() and not e.get("done")]
        if len(match) != 1:
            plan.error(f"events_done '{text}' matches {len(match)} open events")
        else:
            match[0]["done"] = True
            plan.note(f"event done: {match[0]['text'][:60]}")
    for e in delta.get("events_add", []):
        if not isinstance(e.get("day"), int) or not e.get("text") or e["day"] < L["day"]:
            plan.error(f"events_add {e!r} needs a day (today or later) and text")
        else:
            events.append(e)
            plan.note(f"event + D{e['day']} {e.get('time', '')}: {e['text'][:60]}")
    for fid, fact in delta.get("facts", {}).items():
        people["facts"][fid] = fact
        plan.note(f"fact + {fid}")
    for name, upd in delta.get("people", {}).items():
        PE.apply_update(people, name, upd, stamp, plan)
    for cid in delta.get("clues_placed", []):
        CL.place(clue_data, cid, stamp, plan)
    date = game.date_of(L["day"])
    if date and L.get("flags", {}).get("date") not in (None, date.isoformat()):
        plan.note(f"flags.date {L['flags']['date']} -> {date.isoformat()}")
        L["flags"]["date"] = date.isoformat()
    game.gm.recalc(L)
    plan.put_json("ledger.json", L)
    if events != game.events:
        plan.put_json("events.json", sorted(events, key=lambda e: (e.get("day", 0) if isinstance(e.get("day"), (int, float)) else 9e9, str(e.get("time", "")))))
    if had_people or delta.get("people") or delta.get("facts"):
        plan.put_json("people.json", people)
    if had_clues or delta.get("clues_placed"):
        plan.put_json("clues.json", clue_data)
    plan.put_json("scene_state.json", S)
    if delta.get("log"):
        plan.log(delta["log"])
    plan.put_text("STATE_NOW.md", render_state(game, L, S, people, clue_data, events))
    return plan.finish(write)


def fix(game, write=False):
    """Repair the drift that has exactly one right answer; leave judgment calls to the GM."""
    plan, L = Plan(game), game.sheet()
    date = game.date_of(L["day"])
    flags = L.setdefault("flags", {})
    if date and flags.get("date") and flags["date"] != date.isoformat():
        plan.note(f"flags.date {flags['date']} -> {date.isoformat()}")
        flags["date"] = date.isoformat()
    for key, val in list(flags.items()):
        m = re.fullmatch(r"D(\d+)", str(val))
        if key.endswith("_due") and m:
            match = [e for e in game.events if key.split("_")[0].lower() in e.get("text", "").lower()]
            if len(match) == 1 and match[0].get("day") != int(m.group(1)):
                plan.note(f"flags.{key} {val} -> D{match[0]['day']} (the event clock is the authority)")
                flags[key] = f"D{match[0]['day']}"
    before = (L["hp_max"], L["mp_max"])
    game.gm.recalc(L)
    if before != (L["hp_max"], L["mp_max"]):
        plan.note(f"HP/MP maximum {before[0]}/{before[1]} -> {L['hp_max']}/{L['mp_max']}")
    plan.put_json("ledger.json", L)
    if game.text("scene_state.json"):
        plan.put_text("STATE_NOW.md", render_state(game, L, scene_state(game), PE.load(game), CL.load(game), game.events))
        plan.note("STATE_NOW.md rebuilt from the files")
    else:
        plan.note("STATE_NOW.md left alone: it is hand-written. The first `book apply` (with where, with, now) takes it over")
    return plan.finish(write)


def save_slot(game, verb, name):
    """gm.py save/load, plus the files gm.py does not know about."""
    r = subprocess.run([sys.executable, "-B", game.path("gm.py"), verb, name], cwd=game.dir, capture_output=True, text=True)
    print("  " + (r.stdout + r.stderr).strip().replace("\n", "\n  "))
    if r.returncode:
        return 1
    slot = os.path.join(game.dir, "..", "saves", "sl_" + name)
    src, dst = (game.dir, slot) if verb == "save" else (slot, game.dir)
    moved = []
    if verb == "load":                                 # gm.py autosaved its own files; keep ours beside them
        auto = os.path.join(game.dir, "..", "saves", "sl__autosave_before_load")
        for n in EXTRA_SAVE:
            if os.path.exists(os.path.join(game.dir, n)) and os.path.isdir(auto):
                shutil.copy2(os.path.join(game.dir, n), os.path.join(auto, n))
    for n in EXTRA_SAVE:
        if os.path.exists(os.path.join(src, n)):
            shutil.copy2(os.path.join(src, n), os.path.join(dst, n))
            moved.append(n)
        elif verb == "load" and os.path.exists(os.path.join(dst, n)) and n.endswith(".json") and n != "review_rules.json":
            os.remove(os.path.join(dst, n))        # the slot predates this file; a newer copy would be from another timeline
            moved.append(f"removed {n}")
    print(f"  also {'saved' if verb == 'save' else 'restored'}: {', '.join(moved) or 'nothing extra'}")
    return 0


TEMPLATE = {
    "time": "10:20", "where": "St. Mary's 2F ward", "with": ["Hana"],
    "now": "one line: what is happening this second", "pending": "the choice in front of the player",
    "hp": "-12", "fatigue": "+5", "won": "-10000",
    "items_add": ["KAB business card (Ha Sion)"], "items_remove": ["Fishcake skewers"],
    "injuries_add": [{"name": "broken left collarbone (pinned)", "mod": -2}], "injuries_heal": ["numb left shoulder"],
    "events_add": [{"day": 5, "time": "14:00", "text": "KAB re-measurement appointment"}], "events_done": ["muster"],
    "threads_add": ["Pyo wants the horn-ring"], "threads_done": ["fishcakes"],
    "facts": {"temple": {"text": "what really happened inside the temple", "pattern": "arhat|precept|lamp"}},
    "people": {"Ha Sion": {"trust": "+1", "where": "KAB Incheon office", "told": {"temple": "sub-dungeon collapse, a statue fell"},
                           "note": "closed his file; knew the dojang"}},
    "clues_placed": ["c3"],
    "log": "one-line summary of the scene for LOG.md"
}
