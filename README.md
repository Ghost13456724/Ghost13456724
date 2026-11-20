# novelbot

A helper bot for novel-style text RPGs that run on a `gm.py` game folder (built for **Equal to Heaven**). It does three jobs the dice engine leaves to the GM's memory:

1. **Power scaling.** Forecasts whole fights, audits foe cards and designs new foes to a target difficulty.
2. **State audit.** Checks that the ledger, `STATE_NOW.md`, the log and the event clock agree.
3. **Scene checks.** Compares a written scene with the ledger and log: status numbers, dice lines, techniques, names, format.

Every combat number comes from the game folder's own `gm.py`, so the bot cannot disagree with the engine the game is played with. It only reads the game folder; it never changes a file in it.

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
| `all` | `sync` + `foes` + `scene` |

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

## The two bots

`bots/SCENE_CHECKER.md` and `bots/POWERSCALER.md` are briefs for helper agents, in the same style as the game's other bot briefs. Spawn one with: "Read `novelbot/bots/SCENE_CHECKER.md` and do exactly that. Game folder: `/home/claude/rpg/eth`."

The scene checker runs the tool, then reads the scene against the bible, the secrets file, the ledger and the fight rules, and reports only continuity errors, secret leaks, broken rules, power-scale problems, fight-style violations and plot holes. It does not rewrite prose. The powerscaler designs foes, forecasts fights and audits the roster.

Suggested lines for `WORKFLOW.md`:

```
- New enemy: `python3 novelbot/bot.py -g eth design <role> --level N` -> foe card. Never a guessed card.
- Before any real fight: `python3 novelbot/bot.py -g eth fight <foe>`.
- Every scene sent to the checker, and at every arc boundary: `python3 novelbot/bot.py -g eth all`.
```

## Tests

```
python3 -m unittest discover -s tests
```

`tests/game/` is a small made-up game folder using a copy of the real `gm.py`.
