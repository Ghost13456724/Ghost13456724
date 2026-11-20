# Start here

This kit adds helper bots to a text RPG that runs on a `gm.py` game folder. It was built for **Equal to Heaven**.

## 1. Put it in the game

In the chat where you play, upload `novelbot.zip` and send this message:

> Unzip novelbot.zip into /home/claude/rpg/ so the tool is at /home/claude/rpg/novelbot/bot.py. Read novelbot/START_HERE.md and novelbot/README.md, then do sections 2 to 4 of START_HERE.md exactly, showing me the output of each command. From now on follow the routine in section 5 on every turn, and add it to WORKFLOW.md.

## 2. One-time setup (the GM runs this)

```
cd /home/claude/rpg
python3 novelbot/bot.py -g eth setup            # dry run: read it
python3 novelbot/bot.py -g eth setup --write
```

That builds every tracker from the game's own files: date fixes, the cast, the clue ladder, the factions, rulings and lessons from the log, technique cards (installed into gm.py), the planned beats, and the places.

## 3. Bring the files level with the story

The ledger is behind the story (it still has Mori at HP 1; in the story he is healed and blessed). Do everything in `novelbot/examples/eth_catchup.md`, sections 1 to 4. The retroactive XP in its section 3 is the player's decision: ask before paying it.

## 4. Fill in what only the GM can write

Run each of these briefs once ("Read novelbot/bots/<NAME>.md and do exactly that. Game folder: /home/claude/rpg/eth"):

1. `CLUE_KEEPER`: assign clues to rungs, mark the ones already shown, write the watch patterns.
2. `WORLD_CLOCK`: give every faction its next steps; mark the beats already played.
3. `RULINGS_KEEPER`: review the harvested rulings; give every skill a number.
4. `WORLD_DRESSER`: record what the story has already established (the market, Nam's stall, the cart lady, the Gate tag, prices, the ward) with `lore add`.
5. `ARCHIVIST`: backfill. If the player has a "story so far" file, `python3 novelbot/bot.py -g eth archive import <file> --write` does it in one step.

Then `python3 novelbot/bot.py -g eth after` should show nothing left under TODO except what the next scene will settle.

## 5. The routine, every turn

**Before writing a scene**
```
python3 novelbot/bot.py -g eth before            # add --foe <id> if a fight is coming
```
It gives the recap, injuries to show, open quests, clues ready, what the world did, beats in their window, any danger ahead, and the scene's dressing: weekday, weather, the place and its regulars, a detail to bring back and a piece of lore the story has not shown yet. Every scene should carry one person with their own errand, one callback and one piece of lore shown through a thing or a habit, never explained.

**Writing it**
- Options offer what Mori could try, never which technique. He picks the move.
- A fight goes through the FIGHT REFEREE: `move start <foe>`, then per exchange one `move attack` or `move read` and one `move defend`; run the `gm.py roll ... --apply` line it prints; then `move result ...`.
- A new enemy comes from `design <role> --level N`, never from a guess.
- System messages in [brackets]. Dice only from gm.py.

**After the player has read it**
```
python3 novelbot/bot.py -g eth archive add <scene file> --choice "<what the player chose>" --write
python3 novelbot/bot.py -g eth book apply <delta.json> --write
python3 novelbot/bot.py -g eth after
```
Record what the scene established about the world (`lore add`). Do every TODO it lists. Growth and hidden-quest rewards are announced in the next scene without the player asking.

**Now and then**
- Big scenes and every fourth scene: SCENE_CHECKER (`bot.py -g eth all`).
- When the day changes: WORLD_CLOCK (`world tick`).
- Before a new beat, boss or trial: PLAYTESTER.
- A correction from the player: log it, then `rules scan --write`.
- Saves: `bot.py -g eth book save <name>` and `book load <name>`.
- The book: `bot.py -g eth archive book --write`, then give the player `eth/archive/BOOK.html`.

## The bots

| Bot | What it does | Brief |
| --- | --- | --- |
| Powerscaler | Fight forecasts, foe-card audit, foe designer, rank ladder | `POWERSCALER` |
| Scene checker | Status numbers, dice, leaks, techniques, names, options, voices | `SCENE_CHECKER` |
| Bookkeeper | One validated update of every file after a scene; state audit; saves | `BOOKKEEPER` |
| World clock | Faction agendas with dice, traces, and the planned beats | `WORLD_CLOCK` |
| People tracker | Trust, whereabouts, who knows what, who was told what | (bookkeeper writes it) |
| Clue keeper | Clues before truths, one rung at a time | `CLUE_KEEPER` |
| Rulings keeper | Mid-play rulings, counted bonuses, once-a-day items, lessons | `RULINGS_KEEPER` |
| Archivist | Every scene in full; the story as a book; recaps | `ARCHIVIST` |
| Fight referee | Mori picks his own best move; techniques grow with mastery and use | `FIGHT_REFEREE` |
| Quest keeper | Quests, rewards, prices, XP for more than kills; growth check | `QUEST_KEEPER` |
| World dresser | Places, regulars, weather, callbacks, lore not yet shown | `WORLD_DRESSER` |
| Lookahead | Dangers ahead and the honest ways back | (in `before` and `after`) |
| Playtester | Plays the next beat first to find dead ends | `PLAYTESTER` |

Nothing is written without `--write`, every write keeps a backup in `eth/.novelbot_bak/`, and secret text is printed only with `--gm`.

## Numbers that are proposals, not canon

Change them freely: the rank bands (`novelbot/ranks.json`), the technique cards and how they grow (`eth/techniques.json`), the growth thresholds (`eth/growth.json`, copy the defaults from `novelbot/growth.py`), the quest XP sizes (`novelbot/quests.py`), and the foe-designer win-rate targets (`novelbot/scale.py`).
