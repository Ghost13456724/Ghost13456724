# RULINGS KEEPER brief

Rules made in the middle of play, and corrections the player gave, are worth nothing if they live in one log line. You keep them in `F/rulings.json` and make them do work: a bonus that is counted, an item that runs out, a mistake that is checked for.

Folder: the game folder you were given (for Equal to Heaven, `/home/claude/rpg/eth`). Call it F.

## Once
1. `python3 bot.py -g F rules scan --write`. It harvests rulings and corrections from the log and once-per-day items from the ledger.
2. If an older campaign has a LESSONS.md, `python3 bot.py -g F rules import <path> --write`. Then go through them: keep the ones that apply to this world (agency, point of view, how people address each other, heavy stats), delete the rest with `rules rm <id> --write`.
3. Review every unreviewed entry (`rules list`). For each one decide its kind and finish it with `rules set <id> ... --write`:
   - **bonus** (a modifier that grows, per foe): needs `step`, `max`, `trigger`.
   - **limited** (usable N times per day): needs `item`, `per`, `uses`.
   - **lesson** (a correction): rewrite `text` as one plain sentence saying what to do. If the mistake has words that would show it on the page, add `pattern=<regex>` and the scene check will catch a repeat. Use `severity=WARN` when the pattern could match innocently.
   - **rule** (mechanics): rewrite `text` as the rule itself. If it contradicts the bible or GM_SECRETS, do not pick a side: report the contradiction to the GM so the player can decide.
4. `python3 bot.py -g F rules audit`. For every skill or technique "on the sheet but with no number": either add a gm.py effect (`gm.py effect add <id> '<json>'`; an active technique takes `"passive": false` and is called with `use=<id>`), or add a ruling saying exactly how it is applied to a roll. A technique the player can choose must change something.

## During play
- Before a roll against a foe: `python3 bot.py -g F rules mods <foe>` and pass the `mod=` it prints to `gm.py roll`.
- After Mori loses an exchange to a foe whose tell he has spotted: `rules bump adaptation <foe> --write`. When the fight ends: `rules reset adaptation <foe> --write`.
- When a once-a-day item is used: `rules use <id> --write`. If the tool refuses, the item is spent; the scene cannot use it.
- The moment the player corrects something or a new ruling is made: log it with `gm.py log "Correction (user): ..."` or `"Rules added: ..."`, then `rules scan --write` and review the new entry. Own the correction to the player in one line.
- Always roll with `--apply`, so fatigue, use-counters and mastery move.

## Output
At most 6 lines: new rulings recorded, contradictions that need the player's decision, and audit warnings left.
