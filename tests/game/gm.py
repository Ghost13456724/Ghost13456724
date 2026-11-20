#!/usr/bin/env python3
"""gm.py v3 - Solo Leveling campaign toolkit. Deterministic replacement for the per-fight scaling agent.
Math = SCALING.md v3 (+ §1A stat model, §1B weapons). Everything that changes Mori's power is DATA in ledger.json:
stats, weapons, and "effects" (titles, skills, training, gear, buffs). Add or upgrade an effect and every later roll scales.
Run `python3 gm.py help`. Files (same folder): ledger.json, foes.json, events.json, LOG.md; saves in ../saves/sl_<name>/
v3 (db/SYSTEMS.md): class field + canon class milestones, System deletion flag, Shop buy/sell/use (db/shop.json), effect keys
pdr_add / mp_add / hp_add / hp_lost_scale / kp_add_stat, when.weapon_key and when.weapon_type "affinity" (= ledger weapon_affinity).
Shadow army: shadows.py (same ledger, key "shadows").
"""
import json, sys, os, math, random, shutil, time

D = os.path.dirname(os.path.abspath(__file__))
P = lambda n: os.path.join(D, n)
STATS = ["Str", "Con", "Agi", "Int", "Sense"]
# canon (Con -> max HP) and (Int -> max MP) pairs from the status windows (POWER_DB §1); linear interpolation
HP_T = [(10,100),(11,205),(16,766),(27,2220),(30,2600),(43,5114),(59,7229),(87,10270),(91,11035),(101,13001),(145,24406),(281,65230),(307,78230),(320,93300)]
MP_T = [(10,10),(11,22),(16,81),(27,350),(30,391),(39,548),(51,683),(66,850),(70,1022),(99,1677),(189,5019)]
DC = {"trivial":3, "easy":7, "even":11, "hard":14, "desperate":17, "beyond":20}
STRIKE = {"punch":1.0, "elbow":1.0, "knee":1.0, "kick":1.0, "stomp":1.1, "axe":1.1, "throw":1.25, "weapon":1.0, "grapple":1.0, "staff":1.0}  # base; training effects raise these
SET_ACTIONS = {"dodge","hit","chase","throw"}                      # Str+Agi "set" (SCALING §1A)
GOV = {"read":"Agi", "grapple":"Str", "sense":"Sense", "endure":"Con"}
BOX = ["Bandages","Towel","Water bottle","Gloves","Umbrella","Pen","Rope","Thermos","Socks","Lighter","Flashlight","Cup","Raincoat","Notebook","Matches"]
FIST = {"unarmed", "gauntlet", "greaves", "fist"}                    # fist/leg gear keeps unarmed technique effects on
COUNT_OF = {"kick":"kicks","punch":"strikes","elbow":"strikes","knee":"strikes","stomp":"kicks","axe":"kicks","throw":"throws"}

def load(n, default=None):
    try:
        with open(P(n)) as f: return json.load(f)
    except FileNotFoundError:
        return default
def save(n, o):
    tmp = P(n) + ".tmp"
    with open(tmp, "w") as f: json.dump(o, f, indent=1, ensure_ascii=False)
    os.replace(tmp, P(n))
def interp(tab, x):
    if x <= tab[0][0]: return round(tab[0][1] * x / tab[0][0])
    for (x0,y0),(x1,y1) in zip(tab, tab[1:]):
        if x <= x1: return round(y0 + (y1-y0)*(x-x0)/(x1-x0))
    (x0,y0),(x1,y1) = tab[-2], tab[-1]
    return round(y1 + (y1-y0)/(x1-x0)*(x-x1))
def log(L, text):
    with open(P("LOG.md"), "a") as f: f.write(f"- D{L['day']} {L.get('time','')}: {text}\n")

# ---------- effects engine: titles, skills, training, gear and buffs are data ----------
# effect = {"id","src","on":bool,"when":{foe_type:[..],actions:[..],unarmed:bool,weapon_type:str,hp_below:frac},
#           "stat_mult":{Str:1.4,..},"stat_add":{Agi:20,..},"tech":2,"strike_mult":{"kick":1.2},"kp_mult":1.33,
#           "taken_mult":0.5,"foe_mult":0.5,"dc_shift":-3,"note":"cite"}
def active(L, ctx):
    out = []
    for e in L.get("effects", []):
        if e["id"] in ctx.get("use", ()): pass                      # an active skill named with use=<id> on this roll
        elif not e.get("on", True) or e.get("passive", True) is False: continue
        w = e.get("when", {})
        if "foe_type" in w and ctx.get("foe_type") not in w["foe_type"]: continue
        if "actions" in w and ctx.get("action") not in w["actions"]: continue
        wt = (ctx.get("weapon") or {}).get("type") if ctx.get("weapon") else "unarmed"
        if "unarmed" in w and bool(w["unarmed"]) != (wt in FIST): continue        # gauntlets/greaves still count as unarmed
        if "weapon_type" in w:
            want = L.get("weapon_affinity") if w["weapon_type"] == "affinity" else w["weapon_type"]   # affinity: per-Player, unset = off
            want = want if isinstance(want, list) else str(want).split(",") if want else []   # "staff,unarmed" or a list
            if not (wt in want or ("unarmed" in want and wt in FIST)): continue
        if "weapon_key" in w and ctx.get("weapon_key") != w["weapon_key"]: continue
        if "hp_below" in w and not (L["hp"]/max(1, L["hp_max"]) < w["hp_below"]): continue
        out.append(e)
    return out
def eff_stat(L, stat, ctx):
    for e in active(L, ctx):                                         # generic: the action runs on another stat (stat_as {"Str":"Int"})
        if stat in e.get("stat_as", {}):
            v, used = eff_stat(L, e["stat_as"][stat], ctx); m = e.get("stat_as_mult", 1)
            return v * m, used + [e["id"]]
    v = L["stats"][stat]; used = []
    for e in active(L, ctx):
        if stat in e.get("stat_add", {}): v += e["stat_add"][stat]; used.append(e["id"])
    for e in active(L, ctx):
        if stat in e.get("stat_mult", {}): v *= e["stat_mult"][stat]; used.append(e["id"])
    for e in active(L, ctx):                                         # Conqueror of Adversity: +1% all stats per 1% HP lost
        if "hp_lost_scale" in e: v *= 1 + e["hp_lost_scale"] * (1 - L["hp"]/max(1, L["hp_max"])); used.append(e["id"])
    return v, used
def recalc(L, restore=False):
    con, _ = eff_stat(L, "Con", {}); it, _ = eff_stat(L, "Int", {})          # only unconditional effects (gear) count
    con = L["stats"]["Con"] + sum(e.get("stat_add", {}).get("Con",0) for e in L.get("effects", []) if e.get("on",True) and not e.get("when"))
    it = L["stats"]["Int"] + sum(e.get("stat_add", {}).get("Int",0) for e in L.get("effects", []) if e.get("on",True) and not e.get("when"))
    flat = [e for e in L.get("effects", []) if e.get("on",True) and not e.get("when")]
    L["hp_max"] = interp(HP_T, con) + sum(e.get("hp_add",0) for e in flat)
    L["mp_max"] = interp(MP_T, it) + sum(e.get("mp_add",0) for e in flat)      # e.g. Black Heart +100,000 MP (L58505)
    if restore: L["hp"], L["mp"], L["fatigue"] = L["hp_max"], L["mp_max"], 0
    L["hp"] = min(L["hp"], L["hp_max"]); L["mp"] = min(L["mp"], L["mp_max"])

# ---------- math ----------
def edge(r):
    if r >= 3.0: return "auto"
    if r <= 0.33: return "autofail"
    return max(-12, min(12, round(10*math.log2(r))))
def enum(e): return 14 if e == "auto" else -14 if e == "autofail" else e
def fmt_e(e): return e if isinstance(e,str) else format(e, "+")
def mods(L, multi=0, reach=False, edge_val=0, extra=0):
    out = []; f = L.get("fatigue",0); hp = L["hp"]/max(1,L["hp_max"])
    if f >= 90: out.append(("fatigue 90+", -6))
    elif f >= 70: out.append(("fatigue 70+", -3))
    elif f >= 50: out.append(("fatigue 50+", -1))
    if hp < 0.10: out.append(("HP<10%", -4))
    elif hp < 0.30: out.append(("HP<30%", -2))
    elif hp < 0.50: out.append(("HP<50%", -1))
    for inj in L.get("injuries", []): out.append((inj["name"], inj["mod"]))
    if multi:
        per = -1 if (isinstance(edge_val,int) and edge_val >= 8) else -2
        out.append((f"{multi} extra attacker(s)" + (" (reach)" if reach else ""), min(0, per*multi + (1 if reach else 0))))
    if extra: out.append(("situation", extra))
    return out
def tier(d, total, dc):
    if d == 20: return "STRONG"
    if d == 1: return "FAIL+"
    m = total - dc
    return "STRONG" if m >= 5 else "CLEAN" if m >= 0 else "PARTIAL" if m >= -4 else "FAIL"
def kill_text(r):
    if r >= 2.0: return {"STRONG":"overkill","CLEAN":"kill/disable","PARTIAL":"cripple"}
    if r >= 1.5: return {"STRONG":"kill anywhere","CLEAN":"kill on a vital, cripple on body","PARTIAL":"heavy wound"}
    if r >= 1.0: return {"STRONG":"kill on a vital","CLEAN":"heavy wound (30-50% of its HP)","PARTIAL":"light wound"}
    if r >= 0.67: return {"STRONG":"wound","CLEAN":"light wound (10-20%)","PARTIAL":"no effect"}
    if r >= 0.5: return {"STRONG":"light wound","CLEAN":"armour holds (weak points only)","PARTIAL":"no effect"}
    return {"STRONG":"no effect","CLEAN":"NO EFFECT; lower-grade weapon BREAKS","PARTIAL":"no effect"}
def tr_band(tr):
    for lim, b in [(0.5,(0,2)),(0.8,(3,8)),(1.2,(8,15)),(1.6,(15,25)),(2.2,(25,40)),(3.0,(40,60))]:
        if tr < lim: return b
    return (60,100)

def compute(L, F, action, foe_id=None, band=None, strike=None, weapon=None, weak=False, tech=None,
            multi=0, shift=0, extra=0, bench=None, hold=False, use=()):
    """Path 1 = canon benchmark on the foe card (or bench=): Mori effective stat / Jinwoo's effective stat at that canon moment.
       Path 2 = Mori effective stat / foe OES. DC = canon depiction of that action at equal footing (foe card 'dc'), else Even."""
    foe = F.get(foe_id) if foe_id else None
    W = L.get("weapons", {}).get(weapon) if weapon else None
    st = strike or ("throw" if action == "throw" else "grapple" if action == "grapple" else "weapon" if W else "kick")
    ctx = {"action":action, "foe_type":(foe or {}).get("type"), "weapon":W, "weapon_key":weapon, "strike":st, "use":tuple(use)}
    missing = [u for u in use if u not in [e["id"] for e in L.get("effects", [])]]
    if missing: sys.exit(f"unknown skill/effect id(s) {missing}: add with `effect add`")
    acts = active(L, ctx); lines = []; used = set()
    def my(stat):
        v, u = eff_stat(L, stat, ctx); used.update(u); return v
    foe_mult = 1.0
    for e in acts:
        if "foe_mult" in e: foe_mult *= e["foe_mult"]; used.add(e["id"])
    b = bench or (foe or {}).get("bench")
    if tech is None:
        tech = sum(e.get("tech",0) for e in acts if "tech" in e); used.update(e["id"] for e in acts if e.get("tech"))
    def path(refS, refA, label):
        if action in SET_ACTIONS:
            eS, eA = edge(my("Str")/refS), edge(my("Agi")/refA)
            a_half = enum(eA) if L["stats"]["Agi"] >= 20 else enum(eA)/2
            e = math.floor((enum(eS)+a_half)/2 + 0.5); e = "auto" if e >= 13 else "autofail" if e <= -13 else e
            return e, f"{label}Str {my('Str'):.0f}/{refS:.0f} {fmt_e(eS)}, Agi {my('Agi'):.0f}/{refA:.0f} {fmt_e(eA)} -> set {fmt_e(e)}"
        g = GOV[action]; e = edge(my(g)/refS)
        return e, f"{label}{g} {my(g):.0f}/{refS:.0f} -> {fmt_e(e)}"
    e1 = e2 = None
    if b:
        bm = (1.4 if b.get("title") else 1.0) * b.get("mult", {}).get(action, 1.0) * foe_mult   # Jinwoo's own title/skills at that moment
        if action in SET_ACTIONS: e1, t1 = path(b["Str"]*bm, b["Agi"]*bm, "P1 bench ")
        else: e1, t1 = path(b[GOV[action]]*bm, None, "P1 bench ")
        lines.append(t1 + (f"  [{b.get('row','')}]" if b.get("row") else ""))
    if foe:
        ref = {"read":"SPD","grapple":"ATK","sense":"STEALTH","endure":"ATK"}.get(action, "SPD")
        if foe.get(ref):
            e2, t2 = path(foe[ref]*foe_mult, foe[ref]*foe_mult, f"P2 foe {ref} "); lines.append(t2)
    e = e1 if e1 is not None else e2
    if e is None: sys.exit("need a foe with stats or bench=Str:50,Agi:35")
    if e1 is not None and e2 is not None and abs(enum(e1)-enum(e2)) > 3: lines.append(f"!! P1 and P2 differ by {abs(enum(e1)-enum(e2))}: re-check the foe card (bench or OES)")
    cardd = (foe or {}).get("dc", {}) if e1 is not None else {}
    bname = band or cardd.get(action + ("_weak" if weak else "")) or (("hard" if weak else None) if not cardd.get(action) else cardd.get(action)) or "even"
    if weak and not band and not cardd.get(action + "_weak"): bname = "hard"       # small moving target
    dc = (DC[bname] if bname in DC else int(bname)) + shift + sum(e_.get("dc_shift",0) for e_ in acts)
    M = mods(L, multi, bool(W and W.get("reach")), e if isinstance(e,int) else 12, extra); msum = sum(v for _, v in M)
    ev = 12 if e == "auto" else -12 if e == "autofail" else e
    need = dc - (ev + tech + msum); p = 100 if e == "auto" else 0 if e == "autofail" else max(5, min(95, (21-need)*5))
    out = {"edge":e, "ev":ev, "tech":tech, "msum":msum, "mods":M, "dc":dc, "band":bname, "need":need, "p":p, "lines":lines, "foe":foe, "W":W, "strike":st}
    if action in ("hit","throw","grapple") and foe:                 # damage dealt
        sm = STRIKE[st]
        for e_ in acts:
            if st in e_.get("strike_mult", {}): sm = max(sm, e_["strike_mult"][st]); used.add(e_["id"])
        kp = my("Str")*sm + (W["atk"] if W else 0)
        for e_ in acts:
            if "kp_add" in e_: kp += e_["kp_add"]; used.add(e_["id"])
            for s_, f_ in e_.get("kp_add_stat", {}).items(): kp += my(s_)*f_; used.add(e_["id"])   # e.g. Two Becomes One (+Str)
        for e_ in acts:
            if "kp_mult" in e_: kp *= e_["kp_mult"]; used.add(e_["id"])
        T = foe.get("T_hold") if hold and foe.get("T_hold") else foe.get("T_weak") if weak else foe.get("T")
        if T: out.update(kp=kp, T=T, kr=kp/T, kill=kill_text(kp/T), sm=sm)
    if foe and foe.get("ATK"):                                      # damage taken if the foe connects
        tk = 1 - min(90, L.get("pdr",0) + sum(e_.get("pdr_add",0) for e_ in acts))/100
        for e_ in active(L, dict(ctx, action="endure")):
            if "taken_mult" in e_: tk *= e_["taken_mult"]; used.add(e_["id"])
        con, _ = eff_stat(L, "Con", dict(ctx, action="endure"))
        tr = foe["ATK"]*foe_mult/con; lo, hi = tr_band(tr)
        out.update(tr=tr, dmg=(round(L["hp_max"]*lo/100*tk), round(L["hp_max"]*hi/100*tk)))
    out["used"] = sorted(used | set(use))
    out["mp"] = sum(e_.get("mp",0) for e_ in L.get("effects", []) if e_["id"] in use)
    return out

def show(L, R, action, d=None, apply=False, label=None):
    nm = label or action.capitalize()
    for l in R["lines"]: print("  " + l)
    ms = "".join(f" {v:+} ({k})" for k, v in R["mods"])
    print(f"  DC {R['dc']} ({R['band']}) | edge {fmt_e(R['edge'])} tech {R['tech']:+}{ms} | need {max(R['need'],2) if R['p'] not in (0,100) else '-'} on d20 = {R['p']}%" + (f" | effects: {', '.join(R['used'])}" if R["used"] else ""))
    if "kr" in R: print(f"  dmg: {R['strike']} x{R['sm']} KP {R['kp']:.0f} vs T {R['T']} = {R['kr']:.2f} -> CLEAN: {R['kill']['CLEAN']} | STRONG: {R['kill']['STRONG']} | PARTIAL: {R['kill']['PARTIAL']}")
    if R.get("mp"): print(f"  MP cost {R['mp']} (have {L.get('mp',0)})" + ("  !! NOT ENOUGH MP" if R['mp'] > L.get('mp',0) else ""))
    if "tr" in R: print(f"  if it lands on Mori: TR {R['tr']:.2f} -> FAIL {R['dmg'][0]}-{R['dmg'][1]} HP, PARTIAL half, nat 1 x1.5 + complication")
    if d is None: return
    if R["edge"] == "auto": t = "CLEAN" if d != 1 else "PARTIAL"; print(f"  PLAYER LINE: 🎲 **{nm}:** no roll needed, your lead is 3x or more → **Success**")
    elif R["edge"] == "autofail": t = "FAIL"; print(f"  PLAYER LINE: 🎲 **{nm}:** out of reach, the gap is 3x or more → **Fail**")
    else:
        total = d + R["ev"] + R["tech"] + R["msum"]; t = tier(d, total, R["dc"])
        parts = f"d20 **{d}** {fmt_e(R['ev'])} (edge)" + (f" +{R['tech']} (technique)" if R["tech"] else "") + "".join(f" {v:+} ({k})" for k, v in R["mods"])
        print(f"  PLAYER LINE: 🎲 **{nm}:** {parts} = **{total}** vs DC {R['dc']} → **{t.replace('FAIL+','Natural 1')}**")
    res = ""; hurt = 0
    if "kr" in R and t in ("STRONG","CLEAN","PARTIAL"): res += f" | foe: {R['kill'][t]}"
    if "dmg" in R and t in ("PARTIAL","FAIL","FAIL+") and action in ("dodge","endure","grapple","read","chase"):
        lo, hi = R["dmg"]; hurt = random.randint(lo, hi) if hi > lo else lo
        hurt = round(hurt * (0.5 if t == "PARTIAL" else 1.5 if t == "FAIL+" else 1))
        res += f" | Mori takes {hurt} HP" + (" + COMPLICATION (latched/pinned/weapon lost)" if t == "FAIL+" else "")
    print(f"  RESULT: {t}{res}")
    if apply:
        L["hp"] = max(0, L["hp"] - hurt); L["mp"] = max(0, L.get("mp",0) - R.get("mp",0))
        L["fatigue"] = min(100, L.get("fatigue",0) + {"trivial":1,"easy":1,"even":2,"hard":5,"desperate":5,"beyond":6}.get(R["band"],2))
        c = L.setdefault("counters", {})
        key = "dodges" if action == "dodge" else ("weapon_" + (R["W"].get("type") or "hits") if R["W"] and action in ("hit","throw") else COUNT_OF.get(R["strike"]) if action in ("hit","throw") else None)
        if key and t in ("STRONG","CLEAN"): c[key] = c.get(key,0) + 1
        save("ledger.json", L); print(f"  applied: HP {L['hp']}/{L['hp_max']} fatigue {L['fatigue']}")
        if L["fatigue"] >= 70 and not sysdel(L): print("  !! SYSTEM: \"Your fatigue is over 70. Your movements will be restricted.\" (L15820)")
        milestones(L)

# ---------- class, System deletion, Shop ----------
def sysdel(L): return bool(L.get("flags", {}).get("system_deleted"))
SYSDEL_MSG = "System deleted (L79728-79760): no Daily Quests, Shop, level-ups, Random Boxes or System messages (L81435-81439, L84096); combat math unchanged"
CLASS_SKILLS = {"Shadow Extraction":"1", "Shadow Storage":"1"}
CLASSES = {   # canon bonuses; a Player's class is decided from his own past actions (L16685-16733), so other names are allowed
    "Necromancer": {"cite":"L16733-16876", "skills":CLASS_SKILLS, "points":0, "title":None,
        "note":"Hidden Class offered at the Lv40 class quest (L13700-13716); 'army of the dead' (L16733). RULING (shadows.py): no Shadow Strengthening, extraction odds x0.85, grades above Knight cannot be promoted to"},
    "Monarch of Shadows": {"cite":"L16968-16986", "skills":CLASS_SKILLS, "points":10, "title":"Conqueror of Adversity", "upgrade_of":"Necromancer",
        "note":"'You have advanced from Necromancer to Monarch of Shadows. You have learned class-specific skills. You have obtained 10 stat points. You have obtained the title Conqueror of Adversity' (L16968-16974); granted because the advancement points passed the required amount (L16918-16950)",
        "milestones":{70:({"Domain of the Monarch":"1"}, "new class skill at Lv70 (L30605)"),
                      101:({"Shadow Extraction":"2","Shadow Storage":"2","Domain of the Monarch":"2","Shadow Exchange":"2"}, "all class skills +1 at Lv101 (L52489-52495; only skills already owned rise; Shadow Exchange comes from a Runestone, L34054)")}},
}
def set_class(L, name):
    old = L.get("class") or "None"; C = CLASSES.get(name, {}); L["class"] = name
    E = L.setdefault("effects", []); E[:] = [e for e in E if e.get("src") != "class"]
    E.append({"id":"class", "src":"class", "name":name, "on":True, "note":C.get("note","custom class (GM)")})
    sk = L.setdefault("skills", {})
    for k, v in C.get("skills", {}).items(): sk.setdefault(k, v)
    out = [f"[You have advanced from {old} to {name}.]" if C.get("upgrade_of") == old else f"[Your class is the {name}.]"]
    if C.get("skills"): out.append("[You have learned class-specific skills.] " + ", ".join(C["skills"]))
    if C.get("points") and not L.get("flags", {}).get("class_points_" + name):
        L["points"] = L.get("points",0) + C["points"]; L.setdefault("flags", {})["class_points_" + name] = True; out.append(f"[You have obtained {C['points']} stat points.]")
    if C.get("title") and C["title"] not in L.setdefault("titles", []):
        L["titles"].append(C["title"]); out.append(f"[You have obtained the title {C['title']}.]")
        lib = load("effects_lib.json", {}); tid = "conqueror_of_adversity"
        if tid in lib and not any(e["id"] == tid for e in E): E.append(dict(lib[tid], id=tid, on=False))
        out.append("  (title effect added OFF: one title active at a time; `effect on conqueror_of_adversity` + `set title_active=...` to equip)")
    for lv, (skills, why) in sorted(C.get("milestones", {}).items()):
        if L["level"] >= lv: class_milestone(L, lv, skills, why)
    return out
def class_milestone(L, lv, skills, why):
    sk = L.setdefault("skills", {}); done = L.setdefault("flags", {}).setdefault("class_milestones", [])
    if lv in done: return
    for k, v in skills.items():
        if lv == 70 or k in sk: sk[k] = v                             # Lv101 raises only skills already owned
    done.append(lv); print(f"  !! CLASS MILESTONE Lv{lv}: {why} -> skills {sk} (canon default; the GM may change it for Mori)")
def potion(L, it):
    r = it.get("restores") or {}; out = []
    if (r.get("hp_pct") or r.get("hp")) and L["hp"] < 0.10*L["hp_max"] and "Status Recovery" not in it["name"]:
        out.append("[Your health is below 10%. You cannot recover your health with a potion.] (L16016)")
    else:
        L["hp"] = min(L["hp_max"], L["hp"] + round(L["hp_max"]*r.get("hp_pct",0)/100) + r.get("hp",0))
    L["mp"] = min(L["mp_max"], L.get("mp",0) + round(L["mp_max"]*r.get("mp_pct",0)/100) + r.get("mp",0))
    if "fatigue_to" in r: L["fatigue"] = r["fatigue_to"]
    if "fatigue_minus" in r: L["fatigue"] = max(0, L.get("fatigue",0) - r["fatigue_minus"])
    if r.get("clear_injuries"): L["injuries"] = []
    return out

def milestones(L):
    c = L.get("counters", {})
    for m in L.get("milestones", []):
        if not m.get("done") and c.get(m["counter"],0) >= m["at"]: print(f"  !! MILESTONE {m['counter']} >= {m['at']}: {m['msg']}")

# ---------- commands ----------
def status(L, short=False):
    S = L["stats"]
    if sysdel(L) and not short: print("(" + SYSDEL_MSG + "; GM sheet, not a status window)")
    if not short:
        print(f"Name: Jin Mori | Level: {L['level']} | Class: {L.get('class','None')} | Title: {L.get('title_active','None')}")
        print(f"HP: {L['hp']}/{L['hp_max']} | MP: {L['mp']}/{L['mp_max']} | Fatigue: {L.get('fatigue',0)} | PDR {L.get('pdr',0)}%")
    print("Strength {Str} · Vitality {Con} · Agility {Agi} · Intelligence {Int} · Perception {Sense}".format(**S) + f" · unspent {L.get('points',0)}")
    if not short:
        for e in L.get("effects", []):
            w = e.get("when", {}); pay = {k: e[k] for k in ("stat_mult","stat_add","tech","strike_mult","kp_add","kp_add_stat","kp_mult","taken_mult","foe_mult","dc_shift","mp","pdr_add","mp_add","hp_add","hp_lost_scale") if k in e}
            print(f"  effect {'USE' if e.get('passive',True) is False else 'ON ' if e.get('on',True) else 'off'} {e['id']} [{e.get('src','')}] when {w or 'always'} -> {pay}")
        print("Skills: " + (", ".join(f"{k} {v}" for k, v in L.get("skills", {}).items()) or "-"))
        print("Weapons: " + ", ".join(f"{k}={w['name']} (Atk+{w['atk']})" for k, w in L.get("weapons", {}).items()))
        print("Items: " + ", ".join(L.get("items", [])))
        print(f"Gold {L.get('gold',0)} | Won {L.get('won',0):,} | Day {L['day']} {L.get('time','')} | Boxes {L.get('boxes',0)} | Counters {L.get('counters',{})}")
    flags(L)
def flags(L):
    out = []; dq = L.get("daily", {})
    if not sysdel(L):
        if L.get("flags",{}).get("system") and not dq.get("done_today"): out.append("DAILY QUEST NOT DONE (deadline 00:00 -> Penalty Zone)")
        if L.get("points",0): out.append(f"{L['points']} unspent stat points")
        if L.get("boxes",0): out.append(f"{L['boxes']} unopened Random Box")
        if L["level"] >= 10 and not L.get("flags", {}).get("shop_buy"): out.append("SHOP unlock message due (Lv10)")
    for e in due(L, 0, 3): out.append(f"EVENT D{e['day']} {e.get('time','')}: {e['text']}")
    for k, v in L.get("reminders", {}).items(): out.append(f"REMINDER {k}: {v}")
    if out: print("FLAGS:\n  - " + "\n  - ".join(out))
    milestones(L)
def due(L, a, b):
    return [e for e in load("events.json", []) if isinstance(e.get("day"), (int, float)) and L["day"]+a <= e["day"] <= L["day"]+b and not e.get("done")]
def levelup(L, n=1):
    if sysdel(L): sys.exit("no level-ups: " + SYSDEL_MSG)
    C = CLASSES.get(L.get("class"), {})
    for _ in range(n):
        L["level"] += 1
        for k in STATS: L["stats"][k] = L["stats"].get(k,10) + 1
        if L["level"] in C.get("milestones", {}): class_milestone(L, L["level"], *C["milestones"][L["level"]])
    recalc(L, restore=True)
    print(f"[You've leveled up!] x{n} -> Lv {L['level']} (+{n} to every stat, FULL RESTORE hp/mp/fatigue)")
    if L["level"] >= 10 and not L.get("flags", {}).get("shop_buy"):
        L.setdefault("flags", {})["shop_buy"] = True
        print("[You've leveled up past level 20. The 'buy' function of the shop is now enabled.] (L6854)")
    log(L, f"LEVEL UP x{n} -> Lv{L['level']} " + "/".join(str(L['stats'][k]) for k in STATS) + f" HP{L['hp_max']} MP{L['mp_max']}")
def kv(args):
    o = {}
    for a in args:
        if "=" in a and not a.startswith("{"):
            k, v = a.split("=", 1); o[k] = v
    return o
def num(v):
    try: return json.loads(v)
    except Exception: return v

def main(a):
    L = load("ledger.json"); F = load("foes.json", {})
    c = a[0] if a else "help"; r = a[1:]; o = kv(r); flagset = {x for x in r if x.startswith("--")}
    if c == "status": status(L, "--short" in flagset)
    elif c == "flags": flags(L)
    elif c == "levelup": levelup(L, int(r[0]) if r else 1); save("ledger.json", L); status(L, True)
    elif c == "spend":            # spend Str=3 Agi=2
        for k, v in o.items():
            v = int(v); assert k in STATS and v <= L.get("points",0), "not enough points / bad stat"
            L["stats"][k] += v; L["points"] -= v
        recalc(L); save("ledger.json", L); log(L, "spent " + " ".join(f"{k}+{v}" for k, v in o.items())); status(L, True)
    elif c == "set":              # set hp=100 time=14:30 gold=+50 won=-500000 points=+3 fatigue=0 title_active=...
        for k, v in o.items():
            if k in STATS: L["stats"][k] = int(v) if v[0] not in "+-" else L["stats"][k]+int(v)
            elif v[:1] in "+-" and v[1:].isdigit(): L[k] = L.get(k,0) + int(v)
            elif v.lstrip("-").isdigit(): L[k] = int(v)
            else: L[k] = v
        recalc(L); save("ledger.json", L); print("ok:", {k: (L["stats"][k] if k in STATS else L[k]) for k in o})
    elif c == "hp":               # hp -350 | hp -25% | hp full
        v = r[0]
        if v == "full": L["hp"] = L["hp_max"]
        elif v.endswith("%"): L["hp"] = max(0, min(L["hp_max"], L["hp"] + round(L["hp_max"]*int(v[:-1])/100)))
        else: L["hp"] = max(0, min(L["hp_max"], L["hp"] + int(v)))
        save("ledger.json", L); print(f"HP {L['hp']}/{L['hp_max']} ({100*L['hp']//L['hp_max']}%)")
    elif c == "effect":           # effect list | add <id> '<json>' | on|off|rm <id> | set <id> tech=3 strike_mult.kick=1.3
        E = L.setdefault("effects", []); find = lambda i: next(e for e in E if e["id"] == i)
        if not r or r[0] == "list": pass
        elif r[0] == "add":
            e = json.loads(r[2]); e["id"] = r[1]; E[:] = [x for x in E if x["id"] != r[1]] + [e]; log(L, f"effect add {r[1]} {r[2]}")
        elif r[0] in ("on","off"): find(r[1])["on"] = (r[0] == "on")
        elif r[0] == "rm": E[:] = [x for x in E if x["id"] != r[1]]; log(L, f"effect rm {r[1]}")
        elif r[0] == "set":
            e = find(r[1])
            for k, v in kv(r[2:]).items():
                t = e; ks = k.split(".")
                for kk in ks[:-1]: t = t.setdefault(kk, {})
                t[ks[-1]] = num(v)
            log(L, f"effect set {r[1]} " + " ".join(r[2:]))
        recalc(L); save("ledger.json", L)
        for e in E: print(("ON  " if e.get("on",True) else "off ") + json.dumps(e, ensure_ascii=False))
    elif c == "injury":           # injury add "left arm bitten" -1 | injury clear
        if r[0] == "clear": L["injuries"] = []
        else: L.setdefault("injuries", []).append({"name":r[1], "mod":int(r[2])})
        save("ledger.json", L); print(L.get("injuries"))
    elif c == "count":            # count kicks +40   (montage kills that were not rolled one by one)
        cn = L.setdefault("counters", {}); cn[r[0]] = cn.get(r[0],0) + int(r[1]); save("ledger.json", L); print(cn); milestones(L)
    elif c == "item":             # item + "Name" | item - "Name"
        (L["items"].append if r[0] == "+" else L["items"].remove)(r[1]); save("ledger.json", L); print(L["items"])
    elif c == "weapon":           # weapon fang name="Casaka's Poisoned Fang" atk=25 type=dagger [reach=1] | weapon -fang
        if r[0].startswith("-"): L["weapons"].pop(r[0][1:], None)
        else: L.setdefault("weapons", {})[r[0]] = {"name":o.get("name",r[0]), "atk":int(o.get("atk",0)), "type":o.get("type",""), "reach":bool(int(o.get("reach",0))), "notes":o.get("notes","")}
        save("ledger.json", L); print(L["weapons"])
    elif c == "skill":            # skill "Sprint" 1 | skill -"Sprint"   (display list; the mechanical part is an effect)
        if r[0].startswith("-"): L["skills"].pop(r[0][1:], None)
        else: L.setdefault("skills", {})[r[0]] = r[1] if len(r) > 1 else "1"
        save("ledger.json", L); print(L["skills"])
    elif c == "kill":             # kill "Steel-teeth Lycan" 3
        L.setdefault("kills", {})[r[0]] = L["kills"].get(r[0],0) + int(r[1] if len(r) > 1 else 1); save("ledger.json", L); print(L["kills"])
    elif c == "xp":               # xp +60 "reason"  (needs 100*level to level up)
        L["xp"] = L.get("xp",0) + int(r[0]); gained = 0
        while L["xp"] >= 100*L["level"]:
            L["xp"] -= 100*L["level"]; gained += 1; L["level"] += 0; levelup(L,1)
        save("ledger.json", L); log(L, f"XP {r[0]} {r[1] if len(r)>1 else ''} -> {L['xp']}/{100*L['level']}"); print(f"XP {L['xp']}/{100*L['level']} (Lv {L['level']})")
    elif c == "daily":            # daily done
        if sysdel(L): sys.exit(SYSDEL_MSG)
        dq = L.setdefault("daily", {}); assert not dq.get("done_today"), "already done today"
        dq["done_today"] = True; dq["count"] = dq.get("count",0)+1; L["points"] = L.get("points",0)+3; L["boxes"] = L.get("boxes",0)+1
        L["hp"], L["mp"], L["fatigue"] = L["hp_max"], L["mp_max"], 0
        save("ledger.json", L); log(L, f"Daily Quest #{dq['count']} done (+3 pts, box, Status Recovery)")
        print("[You've completed the 'Daily Quest: Daily Discipline'.] Rewards: Status Recovery, +3 stat points, Random Box x1"); flags(L)
    elif c == "box":
        if sysdel(L): sys.exit(SYSDEL_MSG)
        assert L.get("boxes",0) > 0, "no boxes"; L["boxes"] -= 1
        it = "DUNGEON KEY (GM: pick rank/location from canon)" if random.randint(1,30) == 1 else random.choice(BOX)
        L["items"].append(it); save("ledger.json", L); log(L, f"Random Box -> {it}"); print("Random Box ->", it)
    elif c == "day":              # day +1 [time=06:00]
        n = int(r[0]) if r and r[0].lstrip("+").isdigit() else 1
        for _ in range(n):
            dq = L.setdefault("daily", {})
            if sysdel(L): L["day"] += 1; continue
            if L["level"] >= 1 and not dq.get("done_today"):
                dq["missed"] = dq.get("missed",0)+1
                print(f"!! D{L['day']} DAILY MISSED -> PENALTY QUEST at 00:00 (Penalty Zone 4h; +3 pts + box, no recovery; L2870-3026, L3593)")
            dq["done_today"] = False; L["day"] += 1
        L["time"] = o.get("time", "06:00"); save("ledger.json", L)
        print(f"Now D{L['day']} {L['time']}." + ("" if sysdel(L) else " [The Daily Quest has arrived.]")); flags(L)
    elif c == "events":           # events [N days ahead] | events done <id>
        if r and r[0] == "done":
            ev = load("events.json", [])
            for e in ev:
                if e["id"] == r[1]: e["done"] = True
            save("events.json", ev); print("done", r[1])
        else:
            for e in due(L, -1, int(r[0]) if r else 14): print(f"D{e['day']} {e.get('time','')} [{e.get('type','W')}] arc{e.get('arc','?')} {e['id']}: {e['text'][:160]} ({e.get('cite','')})")
    elif c in ("odds", "roll"):
        # roll <action> foe=<id> [band=easy|even|hard|N] [strike=kick] [weapon=fang] [d=14] [multi=1] [shift=-3] [mod=-1]
        #      [tech=0] [bench=Str:50,Agi:35,Con:27,Sense:29] [label="Eye kick"] [--weak] [--hold] [--apply]
        act = r[0]; b = None
        if "bench" in o: b = {k: float(v) for k, v in (x.split(":") for x in o["bench"].split(","))}
        R = compute(L, F, act, o.get("foe"), o.get("band"), o.get("strike"), o.get("weapon"), "--weak" in flagset,
                    int(o["tech"]) if "tech" in o else None, int(o.get("multi",0)), int(o.get("shift",0)), int(o.get("mod",0)), b, "--hold" in flagset,
                    tuple(x for x in o.get("use","").split(",") if x))
        d = None
        if c == "roll": d = int(o["d"]) if "d" in o else random.randint(1,20)
        print(f"{c.upper()} {act}" + (f" vs {R['foe']['name']}" if R["foe"] else ""))
        show(L, R, act, d, "--apply" in flagset, o.get("label"))
        if c == "roll": log(L, f"roll {act} {o.get('foe','')} d{d} need {R['need']} ({R['p']}%) dc{R['dc']}")
    elif c == "foe":              # foe list | foe show <id> | foe add <id> '<json>'
        if not r or r[0] == "list":
            for k, f in F.items(): print(f"{k}: {f['name']} [{f.get('type','?')}] SPD {f.get('SPD')} ATK {f.get('ATK')} T {f.get('T')}/{f.get('T_weak')} bench={'y' if f.get('bench') else 'n'}")
        elif r[0] == "show": print(json.dumps(F[r[1]], indent=1, ensure_ascii=False))
        elif r[0] == "add": F[r[1]] = json.loads(r[2]); save("foes.json", F); print("added", r[1])
    elif c == "log": log(L, " ".join(r)); print("logged")
    elif c == "class":            # class "Monarch of Shadows" | class list
        if not r or r[0] == "list":
            for k, v in CLASSES.items(): print(f"{k} [{v['cite']}]: {v['note']}")
        else:
            for line in set_class(L, " ".join(x for x in r if not x.startswith("--"))): print(line)
            recalc(L); save("ledger.json", L); log(L, f"class -> {L['class']}")
    elif c == "system":           # system status | system delete [--no-reborn] | system restore
        fl = L.setdefault("flags", {})
        if r and r[0] == "delete":
            fl["system_deleted"] = True; fl["system_deleted_day"] = L["day"]
            print("['Player' Nurturing System delete code has been entered.] [The System will now be deleted.]")
            print("[All limitations imposed on the power 'Player' possesses has been lifted.] (L79728-79760)")
            lib = load("effects_lib.json", {})
            if "--no-reborn" not in flagset and not any(e["id"] == "sovereign_reborn" for e in L.setdefault("effects", [])):
                L["effects"].append(dict(lib["sovereign_reborn"], id="sovereign_reborn", on=True)); print("  effect sovereign_reborn ON (RULING x2 all stats)")
            recalc(L); save("ledger.json", L); log(L, "SYSTEM DELETED")
        elif r and r[0] == "restore": fl.pop("system_deleted", None); save("ledger.json", L); print("System flag cleared (GM undo)")
        print("system_deleted:", sysdel(L), "|", SYSDEL_MSG if sysdel(L) else "System active")
    elif c in ("buy", "sell", "use"):   # buy mana_potion 3 | sell cerberus_molar 3 | use healing_potion [--free]
        SH = load("db/shop.json", {}); it = SH.get(r[0]); n = int(r[1]) if len(r) > 1 and r[1].isdigit() else 1
        if not it or r[0].startswith("_") or r[0] == "rules": sys.exit("unknown shop id; see db/shop.json")
        inv = L.setdefault("inventory", {})
        if c == "use":
            if not inv.get(r[0]) and "--free" not in flagset: sys.exit(f"no {r[0]} in the Inventory (buy it or pass --free)")
            if inv.get(r[0]): inv[r[0]] -= 1
            for m in potion(L, it): print(m)
            print(f"used {it['name']}: HP {L['hp']}/{L['hp_max']} MP {L['mp']}/{L['mp_max']} fatigue {L.get('fatigue',0)}")
        else:
            if sysdel(L): sys.exit("the Store is gone: " + SYSDEL_MSG)
            if c == "buy" and L["level"] <= 20: sys.exit("[The 'buy' function opens past level 20] (L6854)")
            if it.get("price_gold") is None: sys.exit(f"no price: {it.get('note','')}")
            cost = it["price_gold"] * n * (1 if c == "sell" else -1)
            if L.get("gold",0) + cost < 0: sys.exit(f"not enough gold ({L.get('gold',0)} < {-cost})")
            L["gold"] = L.get("gold",0) + cost
            if c == "buy": inv[r[0]] = inv.get(r[0],0) + n
            print(f"{c} {n} x {it['name']} at {it['price_gold']} ({it['price_status']}) -> Gold {L['gold']}")
        save("ledger.json", L); log(L, f"{c} {r[0]} x{n}")
    elif c in ("save", "load", "saves"):
        root = os.path.join(D, "..", "saves"); os.makedirs(root, exist_ok=True)
        keep = ["ledger.json","foes.json","events.json","STATE_NOW.md","LOG.md","LESSONS.md","DIVERGENCE.md","CHARACTER.md","bots.json","arcs"]
        def copy(src, dst):
            os.makedirs(dst, exist_ok=True)
            for k in keep:
                s, t = os.path.join(src, k), os.path.join(dst, k)
                if os.path.isdir(s): shutil.rmtree(t, ignore_errors=True); shutil.copytree(s, t)
                elif os.path.exists(s): shutil.copy2(s, t)
        if c == "saves": print("\n".join(sorted(x for x in os.listdir(root) if x.startswith("sl_"))) or "(none)")
        elif c == "save":
            dst = os.path.join(root, "sl_" + r[0]); copy(D, dst)
            with open(os.path.join(dst, "SAVE_INFO.txt"), "w") as f: f.write(f"{r[0]} | D{L['day']} {L.get('time','')} | Lv{L['level']} | saved {time.strftime('%Y-%m-%d %H:%M')}\n" + " ".join(r[1:]) + "\n")
            print("saved ->", dst)
        else:
            copy(D, os.path.join(root, "sl__autosave_before_load")); copy(os.path.join(root, "sl_" + r[0]), D); print("loaded", r[0], "(previous state kept as sl__autosave_before_load)")
    else:
        print(__doc__); print("commands: status [--short] | flags | levelup [n] | spend Str=3 | set k=v | hp -25%|-300|full | effect list|add|on|off|rm|set | injury | count | item | weapon | skill | kill | daily done | box | day +1 | events [N] | odds/roll <dodge|hit|read|grapple|sense|endure|throw|chase> foe=<id> ... | foe list/show/add | log text | save/load/saves | class <name>|list | system status|delete|restore | buy/sell <shop id> [n] | use <shop id> [--free]")

if __name__ == "__main__":
    main(sys.argv[1:])
