"""Prose checks that need no judgment: format, banned elements, repetition."""
import re
from collections import Counter

STOP = set("""the a an and or but of to in on at for with from by as is was were be been it its he she they
them his her their i you we my your our that this these those not no so then than had has have do did does
into out up down over under again just very there here what when where who how if while will would could
should one all some any more most other like about after before through off back still only even also
him me us are am said says say""".split())


def lint(text, rules):
    out = []
    add = lambda sev, code, msg: out.append((sev, code, msg))
    lines = text.splitlines()
    words = re.findall(r"[A-Za-z']+", text)
    lo, hi = rules.get("min_words", 0), rules.get("max_words", 10 ** 9)
    if not lo <= len(words) <= hi:
        add("warn", "length", f"Scene is {len(words)} words; the target is {lo} to {hi}.")

    for term in rules.get("banned_terms", []):
        for i, line in enumerate(lines, 1):
            if re.search(r"\b" + re.escape(term) + r"\b", line, re.I):
                add("error", "banned", f"Line {i}: '{term}' is on the banned list.")

    sys_re = re.compile(rules.get("system_pattern", r"^\s*(system|notice|quest|level up)\b\s*[:!-]"), re.I)
    for i, line in enumerate(lines, 1):
        if sys_re.search(line) and not line.strip().startswith("["):
            add("warn", "system-format", f"Line {i}: System messages go in [brackets].")
        if line.count("[") != line.count("]"):
            add("warn", "bracket", f"Line {i}: unbalanced bracket.")

    opt = rules.get("options")
    if opt:
        tail = [l.strip() for l in lines if l.strip()][-(opt["max"] + 3):]
        numbered = [l for l in tail if re.match(r"^\d+[.)]\s+\S", l)]
        if not opt["min"] <= len(numbered) <= opt["max"]:
            add("error", "options", f"Scene must end with {opt['min']}-{opt['max']} numbered options; found {len(numbered)}.")
        if opt.get("free_choice") and not any(re.search(opt["free_choice"], l, re.I) for l in tail):
            add("warn", "free-choice", "The closing options do not offer a free-form choice.")

    counts = Counter(w.lower() for w in words if len(w) > 3 and w.lower() not in STOP)
    limit = max(rules.get("repeat_floor", 6), len(words) * rules.get("repeat_ratio", 0.012))
    proper = {w for w in words if w[0].isupper()}
    for w, n in counts.most_common(8):
        if n > limit and w.capitalize() not in proper:
            add("note", "repetition", f"'{w}' appears {n} times.")

    for phrase in rules.get("weak_phrases", []):
        n = len(re.findall(re.escape(phrase), text, re.I))
        if n >= rules.get("weak_limit", 2):
            add("note", "weak-phrase", f"'{phrase}' appears {n} times.")

    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    long = rules.get("max_paragraph_words", 0)
    for i, p in enumerate(paras, 1):
        if long and len(p.split()) > long:
            add("note", "long-paragraph", f"Paragraph {i} runs {len(p.split())} words.")
    return out
