"""Archivist: keep every scene in full and turn the playthrough into a readable book.

archive/scenes/NNNN_D<day>.md   one file per scene, exactly as the player read it
archive/index.json              order, chapters, dates, the choice made, a one-line summary
archive/BOOK.md, BOOK.html      the story so far, rebuilt on demand

Only text the player has already seen goes in, so the book is safe for the player to read.
"""
import hashlib
import html
import re

INDEX = "archive/index.json"


def load(game):
    return game.json(INDEX, None) or {"title": game.ledger.get("flags", {}).get("world", "The Story"), "scenes": []}


def live(data):
    return [s for s in data["scenes"] if not s.get("branch")]


def add(game, data, text, plan, title=None, chapter=None, choice=None, day=None, time=None):
    text = text.strip() + "\n"
    digest = hashlib.sha1(text.encode()).hexdigest()[:12]
    if any(s["sha"] == digest for s in data["scenes"]):
        return plan.note("this scene is already in the archive; nothing added")
    day = game.ledger["day"] if day is None else day
    prev = live(data)[-1] if live(data) else None
    if prev and day < prev["day"]:
        plan.note(f"note: this scene is dated D{day}, before the last archived scene (D{prev['day']}); kept in the order added")
    if not chapter:
        chapter = prev["chapter"] if prev and prev["day"] == day else None
    n = len(data["scenes"]) + 1
    name = f"archive/scenes/{n:04d}_D{day}.md"
    date = game.date_of(day)
    words = len(re.findall(r"\S+", text))
    data["scenes"].append({"n": n, "file": name, "sha": digest, "day": day, "time": time or game.ledger.get("time", ""),
                           "date": date.isoformat() if date else None, "chapter": chapter, "title": title,
                           "choice": None, "summary": None, "words": words})
    if choice and prev:                       # the choice that led here belongs to the scene before
        prev["choice"] = choice
        plan.note(f"scene {prev['n']}: choice recorded")
    plan.put_text(name, text)
    plan.note(f"scene {n} archived ({words} words, D{day}" + (f", chapter '{chapter}'" if chapter else ", no chapter yet") + ")")
    if prev and prev.get("choice") is None:
        plan.note(f"scene {prev['n']} has no recorded choice: add it with `archive choice {prev['n']} \"...\"`")


def chapters(data):
    out, cur = [], None
    for s in live(data):
        name = s.get("chapter") or f"Day {s['day']}"
        if cur is None or cur[0] != name:
            cur = (name, [])
            out.append(cur)
        cur[1].append(s)
    return out


def clean(text):
    """Novel mode: drop dice lines and the closing option menu; keep System messages."""
    lines = [l for l in text.splitlines() if "🎲" not in l and not re.search(r"d20 \*\*\d+\*\*", l)]
    while lines and (not lines[-1].strip() or re.match(r"\s*\**\d+[.)]\s", lines[-1])
                     or re.match(r"\s*(what do you do|your move|choose)\b", lines[-1], re.I)):
        lines.pop()
    return "\n".join(lines).strip() + "\n"


def build(game, data, novel=True):
    md = [f"# {data['title']}", ""]
    total = 0
    for name, scenes in chapters(data):
        md += [f"## {name}", ""]
        for s in scenes:
            body = game.text(s["file"])
            body = clean(body) if novel else body
            total += len(body.split())
            if s.get("title"):
                md += [f"### {s['title']}", ""]
            md += [body.strip(), ""]
            if s.get("choice"):
                md += [f"> **You chose:** {s['choice']}", ""]
            md += ["* * *", ""]
    return "\n".join(md), total


def to_html(title, md):
    out, para = [], []

    def flush():
        if para:
            text = html.escape(" ".join(para))
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
            text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", text)
            cls = ' class="sys"' if para[0].lstrip().startswith("[") else ' class="choice"' if para[0].startswith(">") else ""
            out.append(f"<p{cls}>{re.sub(r'^&gt; ?', '', text)}</p>")
            para.clear()
    for line in md.splitlines():
        if line.startswith("#"):
            flush()
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{html.escape(line.lstrip('# '))}</h{level}>")
        elif line.strip() == "* * *":
            flush()
            out.append("<hr>")
        elif not line.strip():
            flush()
        else:
            if para and (line.lstrip().startswith("[") or para[0].lstrip().startswith("[")):
                flush()
            para.append(line)
    flush()
    css = ("body{max-width:40em;margin:2em auto;padding:0 1em;font:1.1em/1.6 Georgia,serif;background:#fbf8f1;color:#222}"
           "h1,h2,h3{font-family:sans-serif}h2{margin-top:3em;border-bottom:1px solid #ccc}"
           ".sys{font-family:monospace;background:#eef;padding:.4em .6em;border-left:3px solid #88a}"
           ".choice{color:#555;font-style:italic}hr{border:0;text-align:center}hr:after{content:'* * *';color:#999}"
           "@media(prefers-color-scheme:dark){body{background:#181818;color:#ddd}.sys{background:#223}.choice{color:#aaa}}")
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{html.escape(title)}</title><style>{css}</style></head><body>\n" + "\n".join(out) + "\n</body></html>\n")


def listing(data):
    rows = []
    for name, scenes in chapters(data):
        rows.append(f"{name}  ({len(scenes)} scenes, {sum(s['words'] for s in scenes):,} words)")
        for s in scenes:
            rows.append(f"  {s['n']:>4} D{s['day']} {s.get('time') or '':<5} {s.get('title') or '':<28} "
                        f"{'choice: ' + s['choice'][:40] if s.get('choice') else 'NO CHOICE RECORDED'}"
                        + ("" if s.get("summary") else "  (no summary)"))
    cut = [s for s in data["scenes"] if s.get("branch")]
    if cut:
        rows.append(f"set aside by a loaded save: {len(cut)} scene(s) (files kept, left out of the book)")
    return rows


def recap(data, n=5):
    """The last scenes' summaries: the cheap way back into the story after a break or a context reset."""
    return [f"D{s['day']} {s.get('time') or ''} {s.get('title') or ''}: {s.get('summary') or '(no summary written)'}"
            + (f" -> chose: {s['choice']}" if s.get("choice") else "") for s in live(data)[-n:]]


def mark_branch(data, keep_shas, stamp):
    """After loading an older save: scenes the save never saw belong to another timeline."""
    n = 0
    for s in data["scenes"]:
        if s["sha"] not in keep_shas and not s.get("branch"):
            s["branch"] = stamp
            n += 1
    return n
