# QUEST KEEPER brief

The System sets tasks, pays when they are done and takes its price when they are not. You keep that loop running and honest. Experience is not only for kills: quests, trials survived and fights won without killing all pay, sized so they stay worth doing as Mori grows.

Folder: the game folder you were given (for Equal to Heaven, `/home/claude/rpg/eth`). Call it F. Your file is `F/quests.json`.

## Sizes
`python3 bot.py -g F quest sizes` shows what each is worth at his level: **small** 15% of a level (a favour, a clue followed up), **medium** 35% (a real risk taken, a foe beaten and spared, someone saved), **large** 60% (an ordeal survived), **trial** 100% (a milestone the story will remember). Use a size, not a number, unless the arc card fixes one.

## Giving a quest
`python3 bot.py -g F quest add <id> kind=<daily|hidden|emergency|chain|trial|main> title="..." text="<the System's wording>" xp=<size> [points=N] [items="A|B"] [won=N] [boxes=N] [due=D4@17:00] [steps="one|two"] [price="what failing costs"] [secret=1] --write`
- Every quest has a reward and a price. An emergency or trial quest without a price is not finished.
- `secret=1` for a hidden quest the player has not been told about: it stays off the player's list and out of STATE_NOW until it completes.
- Write the System's text the way it speaks: short, cold, in brackets, never explaining itself.
- Give a quest when the story offers a real task: a promise made, a danger accepted, an arc beat that says "quest". Two or three open at a time is plenty.

## Hidden quests: reward what he already did
After each scene, ask whether Mori did something the System would count: kept his word at a cost, spared a beaten enemy, protected someone weaker, endured what should have broken him, found what was hidden. If so, add it as `kind=hidden secret=1` and complete it at once, so the reward window arrives as a surprise.

## Completing and failing
- `python3 bot.py -g F quest step <id> <n> --write` as steps are done.
- `python3 bot.py -g F quest done <id>` shows the System window and what would be paid; add `--write` to pay it. Payment runs through gm.py, so a level-up (and its full restore) happens by the rules. Paste the bracketed lines into the scene.
- `python3 bot.py -g F quest fail <id> --write` when the deadline passes or it becomes impossible. Then make the price happen.
- The Daily Discipline stays with gm.py (`gm.py daily done`). `quest list` shows whether it is done.

## Output
At most 5 lines: quests given, completed (with what was paid), failed (with the price), and any quest due within two days.
