# novelbot

A set of helper bots for novel-style text RPGs that run on a `gm.py` game folder (built for **Equal to Heaven**). They do the jobs the dice engine leaves to the GM's memory:

1. **Power scaling.** Forecasts whole fights, audits foe cards and designs new foes to a target difficulty.
2. **State audit.** Checks that the ledger, `STATE_NOW.md`, the log and the event clock agree.
3. **Scene checks.** Compares a written scene with the ledger and log: status numbers, dice lines, techniques, names, format.
4. **Bookkeeper.** Writes what a scene changed into every file at once and rebuilds `STATE_NOW.md`.
5. **World clock.** Runs each faction's off-screen agenda on a schedule, with dice.
6. **People tracker.** Where everyone is, how they feel about Mori, who knows what and who was told what.
7. **Clue ladder keeper.** Clues before truths, one rung at a time.

Every combat number comes from the game folder's own `gm.py`, so the bots cannot disagree with the engine the game is played with.

**Nothing is written without `--write`.** Every writing command first prints its plan as a dry run. With `--write`, the previous version of each changed file is kept in `.novelbot_bak/` inside the game folder. The checking commands never write.

**Secrets stay hidden.** The clue and faction files are GM-side. Their text is printed only with `--gm`, so the commands are safe to run in front of the player.

## Setup

Unzip this folder next to the game (for example `/home/claude/rpg/novelbot/`). Python 3 only, no installs.

```
cd /home/claude/rpg/novelbot
python3 bot.py -g ../eth all          # state audit + foe audit + check of LAST_SCENES.md
```

`-g` is the game folder: the one holding `ledger.json`, `foes.json`, `events.json`, `LOG.md`, `STATE_NOW.md` and `gm.py`.

## Commands

| Command | What it does |
| --- | --- |
| `fight <foe> [--level N]` | Odds for each action, what a clean kick does, what the foe's hit costs, then the whole fight replayed 600 times: win rate rested and as Mori is right now |
| `foes` | Audits every foe card and lists them from easiest to deadliest |
| `design <role> [--level N] [--name] [--type] [--rank]` | Builds a foe card for the fight you want and prints the `gm.py foe add` line |
| `rank` | Where Mori and each foe sit on the rank ladder |
| `sync` | Ledger against STATE_NOW, the log, the calendar and the event clock |
| `scene [file] [--turn]` | Mechanical check of a scene (default `LAST_SCENES.md`) |
| `all` | `sync` + `foes` + `scene`, plus the people, clue and world warnings |
| `book apply <delta.json>` | Apply one scene's changes to ledger, events, people, clues, log and STATE_NOW together |
| `book fix` | Repair drift that has one right answer (date, deadline flags, HP/MP maximum) |
| `book template` | Print a delta with every field |
| `book save <name>` / `book load <name>` | `gm.py save/load`, plus the files gm.py does not know about |
| `people init / show [name] / scan / set <name> k=v` | Seed the cast from the bible, show it, count trust changes from the log, edit one person |
| `clues init / status / next / place <id> / reveal <rung>` | The reveal ladder (add `--gm` to see the text) |
| `world init / status / tick / seen <trace id>` | Faction agendas (add `--gm` to see the text) |

### Power scaling

`fight` plays the fight forward round by round (one strike, one defence), with HP loss, fatigue and gm.py's penalties building up, so a long fight is as hard as it really is. Verdicts: fodder, favoured, even fight, dangerous, do not fight.

`design` roles are defined by the fight they give a rested Mori alone:

| Role | Target win rate |
| --- | --- |
| `grunt` | about 95% |
| `even` | about 50% |
| `elite` | about 25% |
| `boss` | under 10%: needs allies, a trick or a rule to break |

It grows a card step by step and replays the fight at each step, then returns the closest card. `--level 12` builds it for a level 12 Mori (+1 to every stat per level; spent points and new skills are not projected). `--rank C-rank` scales the card into a rank band instead and shows what that rank means for Mori.

`foes` flags cards with missing numbers, a weak point tougher than the body, a difficulty label the fight forecast contradicts, a foe Mori cannot wound whose card does not say what beats it, and families out of order (a leader weaker than its grunts).

The rank bands live in `novelbot/ranks.json`. **They are a proposed ruling, not canon**: each rank is about 1.8 times the one below, anchored on a level 1 E-rank and the Union Thug card. Edit the file and every command follows.

### State audit

`sync` checks, among other things: HP and MP maximums against Vitality and Intelligence, unclaimed level-ups, stats below the level's floor, technique bonus against mastery, STATE_NOW's day and HP against the ledger, injuries described in the notes but missing from the ledger (so no roll is penalised for them), `flags.date` against the calendar, deadlines in `flags` against `events.json`, and past events never marked done.

### Scene checks

`scene` flags: HP, MP, level or stat numbers that differ from the ledger; dice lines with no matching roll in `LOG.md` or a result that does not follow from the numbers; techniques above Mori's mastery; a name Mori has lost; banned elements; a blade in Mori's hands; System text outside `[brackets]`; a missing or wrong options block; a scene dated ahead of the ledger.

Two optional GM-side files in the game folder extend it:
- `secrets_watch.json`: `[{"pattern": "<regex>", "rung": 4}]`. A match above the story's current reveal rung is reported as a leak. The scene checker bot builds this from the reveal ladder.
- `review_rules.json`: extra `banned` patterns, or a different `options` rule.

### Bookkeeper

A scene's changes are written as a small JSON delta (`book template` shows every field): time, place, who is present, HP or money changes that no roll applied, items, injuries with their roll penalty, events, people updates, facts, clues placed, and a log line. `book apply` validates it (an item that is not there, time running backwards, money going negative, an unknown fact) and refuses to write anything if one check fails. Dice, level-ups and new days stay with `gm.py`, because those carry rules.

Once a delta has been applied, `STATE_NOW.md` is rebuilt from the files on every apply: date, place, company, HP, injuries, memories lost, inventory, the pending choice, open threads, what is due this week, what each person present believes, and the reveal rung.

### World clock

`factions.json` holds each faction's goal and steps. A step has a day, what the faction does off-screen, the **trace** it leaves in the world, an optional **chance** of working, what Mori would have to do to **stop** it, and follow-up steps. `world tick` runs everything that has come due: it rolls the chance, logs what happened as a `[W]` line, schedules the follow-ups, and files the trace for Mori to run into. Steps Mori could have stopped are held until the GM rules on them. `world status` warns about factions with nothing planned and about a week with nothing scheduled.

### People tracker

`people.json` holds, for each person: role, where they are, status, trust, what they truly **know**, what they were **told** instead, what they want, debts, and dated notes. Facts are registered once with a pattern of the words that would give them away. The scene check then reports when a fact surfaces in a scene in front of someone who is not in the know, and names anyone holding a cover story.

### Clue ladder keeper

`clues.json` holds each rung's truth, its clues, and watch patterns. A rung can be revealed only in order and only after two of its clues have been placed in play; `--force` overrides that and says so in the log. The scene check reads the watch patterns directly and reports any match above the current rung as a leak.

## The bots

`bots/` holds five briefs for helper agents, in the same style as the game's other bot briefs: `SCENE_CHECKER`, `POWERSCALER`, `BOOKKEEPER`, `WORLD_CLOCK`, `CLUE_KEEPER`. (The people tracker has no brief of its own: the bookkeeper writes it and the scene checker reads it.) Spawn one with: "Read `novelbot/bots/BOOKKEEPER.md` and do exactly that. Game folder: `/home/claude/rpg/eth`."

First-time setup in the game chat:

```
python3 novelbot/bot.py -g eth book fix --write       # date and deadline flags
python3 novelbot/bot.py -g eth people init --write    # cast from the bible
python3 novelbot/bot.py -g eth people scan --write    # trust changes already in the log
python3 novelbot/bot.py -g eth clues init --write     # ladder and clue lists from the GM files
python3 novelbot/bot.py -g eth world init --write     # public factions from the bible
```

Then run the CLUE_KEEPER and WORLD_CLOCK briefs once each to fill in clues, watch patterns and agendas, and the BOOKKEEPER brief on the current scene so the injuries reach the ledger.

Suggested lines for `WORKFLOW.md`:

```
- After EVERY scene: BOOKKEEPER (delta -> `bot.py -g eth book apply <delta> --write`), then `bot.py -g eth sync` must be CLEAN.
- When the day changes or time is skipped: WORLD_CLOCK (`world tick`), then surface one trace.
- Before a scene: CLUE_KEEPER `clues next --gm`; after a reveal: `clues reveal <rung> --write`.
- New enemy: `bot.py -g eth design <role> --level N` -> foe card. Never a guessed card.
- Before any real fight: `bot.py -g eth fight <foe>`.
- Big scenes and every ~4 scenes: SCENE_CHECKER (`bot.py -g eth all`).
- Saves: `bot.py -g eth book save <name>` / `book load <name>`, not bare gm.py save.
```

## Tests

```
python3 -m unittest discover -s tests
```

`tests/game/` is a small made-up game folder using a copy of the real `gm.py`.
