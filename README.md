# novelbot

A canon keeper for novel-style text games. It scales power from recorded feats, reviews scenes against canon before they count, and keeps the world state honest between sessions.

It has two halves:

- **An engine** (`bot.py`, Python standard library only) that does the arithmetic and bookkeeping: power ratings, matchups, dice, continuity checks, prose format checks, and writing reviewed scenes into canon.
- **Three agent prompts** (`.claude/agents/`) that do the reading: `scene-reviewer` turns a scene's prose into a list of claims and judges it, `powerscaler` answers strength questions from the evidence, and `canon-importer` turns prose notes into structured canon.

The reader makes the judgment calls; the engine cannot forget an injury or misremember a stat.

## Quick start

```
python3 bot.py status                              # clock, locations, injuries
python3 bot.py ladder                              # tiers and current ranking
python3 bot.py show Seorin                         # sheet plus the feats behind each stat
python3 bot.py compare Seorin Ogre --a-form "Second Breath"
python3 bot.py roll Dojin Seorin                   # matchup plus a d20 (prints its seed)
python3 bot.py audit                               # inflated stats, outliers, contradictory results
python3 bot.py check examples/claims.json          # a scene that breaks canon (rejected)
python3 bot.py check examples/claims_fixed.json    # the same scene, earned
python3 bot.py lint examples/scene.md              # format and prose checks
python3 bot.py commit examples/claims_fixed.json   # write a reviewed scene into canon
python3 -m unittest discover -s tests
```

`data/` ships with a small sample world so every command works out of the box.

## Campaigns

Each game gets a folder under `campaigns/` with its own ladder, canon and rules. Pick one with `-c`:

```
python3 bot.py -c equal-to-heaven status
python3 bot.py -c equal-to-heaven rules            # house rules the reviewer checks by reading
python3 bot.py -c equal-to-heaven new "Jin Mori" "E-rank" --edge 2
python3 bot.py -c equal-to-heaven compare "Jin Mori" "<foe>"
```

`campaigns/equal-to-heaven/` holds the Equal to Heaven game: the ladder from E-rank to past universal scale, the dice bands, and the house rules from its GM guide. Its canon starts empty; run the `canon-importer` agent over the game's files and log to fill it.

To start another campaign, copy that folder, edit the tiers in `scale.json`, empty `canon.json`, and run the importer over that game's notes.

A ladder can also be made of realms with stages: give a tier `abbr` and `stages`, then write ratings as `"IG 5"` and convert with `bot.py rate IG 5`. On a realm ladder a character's `realm` is the baseline. A stat above it needs a feat, or `audit` reports it as `above-realm`.

## How power scaling works

Every stat is a rating on one logarithmic ladder: **10 points is one tier (about ten times the output), 3 points is about double.** The ladder in `data/scale.json` runs from E-rank to past universal, each tier with a physical benchmark.

| Stat | Meaning |
| --- | --- |
| `ap` | attack potency |
| `dur` | durability |
| `spd` | combat speed and reactions |
| `sta` | stamina and reserves |
| `tec` | technique; it modifies the dice roll, not the raw gap |

A matchup produces a **gap** from attack against durability in both directions, speed and stamina. A character who is ten points up in everything has a gap of +10. The gap picks a difficulty band, and the fight is rolled as `d20 + technique modifier` against that band's DC:

| Gap | Band | DC |
| --- | --- | --- |
| +15 or more | auto | no roll |
| +8 | trivial | 3 |
| +3 | easy | 7 |
| -3 to +3 | even | 11 |
| down to -8 | hard | 14 |
| down to -15 | desperate | 17 |
| down to -25 | beyond | 20 |
| lower | impossible | no roll |

Three rules stop the numbers from being gamed:

- **Durability gate.** If attack is 10 or more below the target's durability, the attacker cannot hurt them. The band drops to at least *beyond* and technique stops helping, so the win needs a weakness, help or a new power shown on the page.
- **Speed blitz.** A speed lead of 10 or more shifts the band one step.
- **Abilities that bypass durability** count as a win condition only if their potency beats the target's resistance, and their cost is always reported.

Stats have to be backed by **feats**. Shown feats outrank statements (a statement adds at most 3 points), a lone feat more than 8 points above the rest is an outlier and is not counted, and `audit` flags any stat more than 3 points away from its evidence. It also flags fair wins that the numbers say should not have happened.

All thresholds live in `data/scale.json`.

## How scene review works

1. The reviewer reads the scene and writes its claims as JSON (`examples/claims.json`): who is present, and an event for each fight, feat, power gain, item or ability used, injury, death, journey and use of knowledge.
2. `bot.py check` compares the claims with canon.
3. `bot.py lint` checks the prose file against `data/rules.json`.
4. The GM fixes the scene, then runs `bot.py commit`, which refuses scenes with errors unless `--force` is given.

| Check | What it catches |
| --- | --- |
| `impossible-win`, `unexplained-upset`, `free-upset` | wins the numbers do not allow, or allow only with conditions and a cost |
| `false-tension`, `jobbing` | a far stronger character written as struggling |
| `feat-above-stats` | a feat beyond the character's current rating |
| `unearned-power`, `free-power`, `big-jump` | power gains with no cause, no cost, or more than a tier at once |
| `knowledge-leak` | a character acting on a fact they never learned |
| `early-reveal` | a secret revealed more than one rung ahead of the clue ladder |
| `dead-character`, `teleport`, `time-reversal` | continuity breaks |
| `missing-item`, `unknown-ability` | using what the character does not have |
| `no-roll` | a contested fight decided without dice |
| `active-condition` | a reminder of injuries the prose should show |

Lint covers word count, banned terms, System messages outside `[brackets]`, the required ending (a block of numbered options, or a closing line such as "What do you do?"), repeated words and weak phrases. Rules that need reading, such as content limits, go in `house_rules` and are checked by the reviewer agent.

Event types: `fight`, `feat`, `power_up`, `uses_item`, `uses_ability`, `knows`, `learns`, `reveal`, `injury`, `recovers`, `death`, `travel`, `gains_item`, `loses_item`, `learns_ability`.

## Using the agents

In Claude Code, from this repository:

- "Use the scene-reviewer agent on `drafts/s09.md`" returns PASS, REVISE or REJECT with the smallest fix for each finding. It never commits and never edits canon.
- "Ask the powerscaler: can Seorin beat the Ogre in Second Breath?" or "Give me stats for a rival who should be a hard fight for Seorin."

- "Use the canon-importer agent on these notes for the equal-to-heaven campaign" turns prose notes into sheets, feats, facts and results, and lists every gap it had to leave.

## Files

```
bot.py                  entry point
novelbot/scale.py       tiers, evidence, matchups, audit
novelbot/review.py      claim checks and commit
novelbot/lint.py        prose and format checks
data/scale.json         ladder, bands, thresholds
data/canon.json         characters, feats, facts, results, clock (the bot writes this)
data/rules.json         style rules for lint
campaigns/<name>/       one folder per game, same three files as data/
examples/               a failing scene, the fixed version, and a prose sample
```
