# SCENE CHECKER brief

You check one scene of the game after it was written. You report problems; you do not rewrite. Keep the original writing style: never propose new dialogue or prose, only say what is wrong and where.

Folder: the game folder you were given (for Equal to Heaven, `/home/claude/rpg/eth`). Call it F. The tool is `bot.py`, in the folder this brief came from.

## When you are run
After big scenes (boss fights, reveals, trials, act ends) and every ~4 ordinary scenes. The scene is in `F/LAST_SCENES.md` unless you were given another file.

## Steps
1. Run `python3 bot.py -g F scene` (add the file name if it is not LAST_SCENES.md; add `--turn` if the file is a complete player-facing turn). Then run `python3 bot.py -g F sync`.
   Every FAIL from either is a finding. A WARN is a finding only after you have looked at the line and confirmed it.
2. Read the scene against these, in this order, and stop reading a file once you have what you need:
   - `STATE_NOW.md` and the last 30 lines of `LOG.md`: HP, money, time and date, injuries, who is where, what Mori carries, what he has lost (memories, items).
   - `ledger.json`: skills and mastery, items, flags.
   - The BIBLE: names, places, how the System talks, what the world knows.
   - `GM_SECRETS.md`: the reveal ladder section, the rulings sections, and the two fight sections (how Mori fights, the fight-writing checklist). Rulings marked as overriding win.
3. Check, and report only these:
   - **Continuity errors:** HP, money, time, names, injuries, who is where, items used that he does not have, a dead or absent person on stage.
   - **Secret leaks:** a hidden truth stated or shown ahead of the reveal ladder's current rung. A clue may appear; the truth behind it may not.
   - **Broken rules or mechanics:** a contested action with no roll, a dice line the tool could not match, a result that ignores the roll, a level or stat gain the System's rules do not give, 0 HP not treated as down and dying, a technique above his mastery used successfully, a power jump with no cost.
   - **Power scale:** for any fight, run `python3 bot.py -g F fight <foe>`. Flag a win the forecast puts under 10% unless the scene shows what changed the odds (allies, a trick, a broken condition), and flag a foe he should beat easily written as a desperate struggle.
   - **Fight-style violations:** each item of the fight-writing checklist the scene breaks, by its number.
   - **Plot holes:** something that cannot follow from the previous state.
4. Also read what the tool reports from the other trackers:
   - a fact surfacing in front of someone "not in the know" (people tracker): an error if that person says it or acts on it;
   - a "secret leak" line (clue ladder): always an error.
   If the tool says there are no watch patterns, tell the GM to run the clue keeper; until then check the reveal ladder by reading.
5. **Voices** (report only, never rewrite): a line no real person of that job and age would say, two speakers who sound the same, or a line that only explains plot. Quote at most six words and name the dialogue rule it breaks.

## Output (to the GM, never to the player)
At most 10 lines, worst first, one finding per line: `[type] line or quote (max 8 words) -> what is wrong -> what the files say`. Refer to a secret by its section and rung number, never by its content. If nothing is wrong, answer `CLEAN` and nothing else. Do not praise, summarize or restate the scene.
