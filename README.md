# novelbot

A set of helper bots for novel-style text RPGs that run on a `gm.py` game folder (built for **Equal to Heaven**). They do the jobs the dice engine leaves to the GM's memory:

1. **Power scaling.** Forecasts whole fights, audits foe cards and designs new foes to a target difficulty.
2. **State audit.** Checks that the ledger, `STATE_NOW.md`, the log and the event clock agree.
3. **Scene checks.** Compares a written scene with the ledger and log: status numbers, dice lines, techniques, names, format.
4. **Bookkeeper.** Writes what a scene changed into every file at once and rebuilds `STATE_NOW.md`.
5. **World clock.** Runs each faction's off-screen agenda on a schedule, with dice.
6. **People tracker.** Where everyone is, how they feel about Mori, who knows what and who was told what.
7. **Clue ladder keeper.** Clues before truths, one rung at a time.
8. **Rulings and lessons keeper.** Mid-play rulings and the player's corrections, turned into counters and checks.
9. **Archivist.** Every scene saved in full, and the story exported as a book.
10. **Arsenal and fight referee.** The player chooses the intent; Mori picks the best move he owns.
11. **Quest log.** Tasks, rewards and prices; experience for more than kills.
12. **Beat tracker.** Which planned story beats were delivered, changed or skipped.
13. **Lookahead.** What is coming that he cannot survive or afford, and the honest ways back.

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
| `fight <foe> [--level N] [--defences N]` | Odds for each action, what a clean kick does, what the foe's hit costs, then the whole fight replayed 600 times: win rate rested and as Mori is right now |
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
| `rules scan / list / import <file> / add / set / rm` | Harvest rulings and corrections from the log; review and edit them |
| `rules mods <foe>` / `bump <id> <foe>` / `reset <id> <foe>` / `use <id>` | The modifier to pass to the next roll; grow or clear a bonus; spend a once-a-day item |
| `rules dice` / `rules audit` | Luck and difficulty report; skills with no number, rolls not applied, unreviewed rulings |
| `tech init / list / install` | Technique cards; `install` makes them callable in gm.py |
| `move start <foe>` / `attack` / `defend` / `read` / `result ...` / `end` | Fight referee: the move Mori uses and the exact gm.py line |
| `quest list / add / step / done / fail / sizes` | Quest log (`--gm` shows secret quests) |
| `beats init / status / mark <id> <state> [note]` | Planned story beats (`--gm` shows the text) |
| `ahead [days]` | Lookahead |
| `archive add <file> [--choice --title --chapter]` | Save a scene in full |
| `archive book [--raw]` / `list` / `recap [n]` | Build `BOOK.md` and `BOOK.html`; list scenes; "previously on" |

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

### Rulings and lessons keeper

`rulings.json` holds four kinds of entry. A **bonus** grows per foe up to a cap (adaptation: +1 per lost exchange, max +3) and `rules mods <foe>` prints the `mod=` to pass to `gm.py roll`. A **limited** item can be used N times a day and is refused after that. A **lesson** is a correction; give it a `pattern` and the scene check enforces it. A **rule** is a mechanics ruling kept where it can be found. `rules scan` harvests all of these from log lines such as "Rules added", "Correction (user)" and "Retcon", and from once-per-day items in the ledger.

`rules audit` also reports skills and techniques that are on the sheet but change no number, rolls that were not run with `--apply` (so fatigue and mastery never move), and how the fights were actually structured. `rules dice` reports luck and how hard the offered rolls were. If the log shows more than one defensive roll per attack, `fight <foe> --defences 2` forecasts the fight the way it is really being played.

### Archivist

`archive add` stores a scene exactly as the player read it under `archive/scenes/`, with its day, date, chapter, the choice that followed and a one-line summary. `archive book` builds `archive/BOOK.md` and a phone-friendly `archive/BOOK.html`: dice lines and option menus are removed, System messages are kept, and each choice appears as one line (`--raw` keeps everything). Only text the player has seen goes in. Loading an older save sets later scenes aside without deleting them.

### Arsenal and fight referee

The player never picks the flavour of kick. `techniques.json` holds a card for each technique: what it does in gm.py terms, what it needs on the sheet, what it costs, and when it applies (only the first time a foe sees it, only after Mori has read the foe, only on an opening). `move attack` tries every technique he owns against gm.py's numbers for this foe at this moment and prints the one he uses, the reason, and the exact `gm.py roll ... use=<technique> --apply` line. `move result` records how it went, which is what makes a foe wise to a trick, opens counters after a successful read, puts a foe off balance, and grows adaptation after a lost exchange. One exchange is one roll for his action and one for his defence. The fight forecast uses the arsenal too.

`tech init` writes five **proposed** cards for the techniques now on the sheet (Three-Stage Hoechook, Lowest Hoechook, Counter Hoechook, X Guard, Erase the Rhythm). Their numbers are a starting proposal, not canon: edit `techniques.json`. The scene check warns when an option asks the player to choose a technique.

### Quest log

`quests.json` holds each quest's kind, System text, steps, deadline, reward and price. A reward's XP is a size (small 15%, medium 35%, large 60%, trial 100% of the current level), so quests, trials and fights won without killing all pay and stay worth doing as he levels. `quest done` prints the System window and pays through gm.py, so level-ups and full restores follow the engine's rules. Secret quests stay off the player's list until they complete.

### Beat tracker

`beats init` reads every beat and bullet from the arc cards with its day window and the level the plan expects. Each item is pending, delivered, changed or skipped; changed and skipped need a reason. `beats status` warns about items past their window and still pending.

### Lookahead

`ahead` reads the next few days: Mori's condition, which foes he can beat right now compared with rested, the Daily Discipline and what the Penalty Zone would do to him as he is, deadlines against his money, quests due, faction steps coming, and the XP the arc plan needs per day. It ends with the honest ways back (the daily, the XP to a level-up, people who can treat him, items, open quests). It changes nothing.

## The bots

`bots/` holds nine briefs for helper agents, in the same style as the game's other bot briefs: `SCENE_CHECKER`, `POWERSCALER`, `BOOKKEEPER`, `WORLD_CLOCK` (which also keeps the beats), `CLUE_KEEPER`, `RULINGS_KEEPER`, `ARCHIVIST`, `FIGHT_REFEREE`, `QUEST_KEEPER`. (The people tracker has no brief of its own: the bookkeeper writes it and the scene checker reads it.) Spawn one with: "Read `novelbot/bots/BOOKKEEPER.md` and do exactly that. Game folder: `/home/claude/rpg/eth`."

First-time setup in the game chat:

```
python3 novelbot/bot.py -g eth book fix --write       # date and deadline flags
python3 novelbot/bot.py -g eth people init --write    # cast from the bible
python3 novelbot/bot.py -g eth people scan --write    # trust changes already in the log
python3 novelbot/bot.py -g eth clues init --write     # ladder and clue lists from the GM files
python3 novelbot/bot.py -g eth world init --write     # public factions from the bible
python3 novelbot/bot.py -g eth rules scan --write     # rulings and corrections already in the log
python3 novelbot/bot.py -g eth rules add xp_sources kind=rule text="XP comes from kills, quests, trials survived and fights won without killing (bible X; replaces the D2 kills-only ruling)" --write
python3 novelbot/bot.py -g eth tech init --write      # proposed technique cards
python3 novelbot/bot.py -g eth tech install --write   # make them callable in gm.py
python3 novelbot/bot.py -g eth beats init --write     # planned beats from the arc cards
python3 novelbot/bot.py -g eth ahead                  # what is coming
```

Then run the CLUE_KEEPER, WORLD_CLOCK and RULINGS_KEEPER briefs once each to fill in clues, watch patterns, agendas and rulings, the ARCHIVIST's backfill to save the scenes already played, and the BOOKKEEPER brief on the current scene so the injuries reach the ledger.

Suggested lines for `WORKFLOW.md`:

```
- OPTIONS offer intentions, never techniques. In a fight: FIGHT_REFEREE. `bot.py -g eth move start <foe>`, then per exchange ONE `move attack|read` and ONE `move defend`; run the gm.py line it prints (always `--apply`), then `move result`.
- XP: kills, quests, trials survived and fights won without killing. QUEST_KEEPER after each scene (`quest add/done`).
- After each scene: `bot.py -g eth ahead`; a FAIL means the next scene must offer a real way out. Mark beats (`beats mark`).
- After EVERY scene: ARCHIVIST (`archive add <scene> --choice "..." --write`), then BOOKKEEPER (delta -> `bot.py -g eth book apply <delta> --write`), then `bot.py -g eth sync` must be CLEAN.
- When the day changes or time is skipped: WORLD_CLOCK (`world tick`), then surface one trace.
- Before a scene: CLUE_KEEPER `clues next --gm`; after a reveal: `clues reveal <rung> --write`.
- New enemy: `bot.py -g eth design <role> --level N` -> foe card. Never a guessed card.
- Before any real fight: `bot.py -g eth fight <foe>`.
- Big scenes and every ~4 scenes: SCENE_CHECKER (`bot.py -g eth all`).
- A correction or a new ruling: log it, then RULINGS_KEEPER (`rules scan --write`).
- Session start or after a context reset: `bot.py -g eth archive recap 5`, then STATE_NOW.
- Saves: `bot.py -g eth book save <name>` / `book load <name>`, not bare gm.py save.
```

## Tests

```
python3 -m unittest discover -s tests
```

`tests/game/` is a small made-up game folder using a copy of the real `gm.py`.
