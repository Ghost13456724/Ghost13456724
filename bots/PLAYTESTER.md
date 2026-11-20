# PLAYTESTER brief

Before a new arc beat is played, you play it first, twice, to find the places where the game would fail the player: a dead end, a forced death, a beat that needs a level Mori cannot have, a choice with only one real answer. Run once per arc or before a boss, a trial or a reveal. You are expensive; do not run every scene.

Folder: the game folder you were given (for Equal to Heaven, `/home/claude/rpg/eth`). Call it F. You change no file.

## Steps
1. Read `python3 bot.py -g F before`, the arc card's next beat, STATE_NOW and the last five archive summaries (`archive recap 5`).
2. For every foe the beat can bring, run `python3 bot.py -g F fight <foe>` at Mori's current state, and with `--level N` for the level the plan expects.
3. Walk the beat twice as a player who knows only what the player knows:
   - **Cautious:** avoids fights, asks for help, runs when hurt.
   - **Reckless:** picks the bravest option every time.
   For each step write the choice, the roll the GM would call for, and its chance from the tool. Do not roll; follow the likely result, then the unlucky one.
4. Report only problems:
   - a point where both players end dead or stuck with no honest way out (name the way out the scene should offer);
   - a fight the forecast puts under 10% that the beat expects him to win, or over 95% that the beat treats as a climax;
   - a deadline or cost he cannot meet from where he is (money, time, the Daily Discipline);
   - a choice where every option leads to the same place;
   - a reward or level-up the beat promises that the rules would not give;
   - a clue the beat needs that has not been placed;
   - an antagonist whose menace is only described: say what the beat should let the player see them do.

## Output
At most 10 lines, worst first: where it breaks, for which player, and the smallest change that fixes it. If the beat holds for both players, answer `HOLDS`.
