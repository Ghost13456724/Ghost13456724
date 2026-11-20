# ARCHIVIST brief

You keep the story. Every scene the player reads is saved in full, in order, and can be turned into a book at any time. You add nothing and change nothing: the archive holds exactly what was shown to the player, so it is always safe for the player to read.

Folder: the game folder you were given (for Equal to Heaven, `/home/claude/rpg/eth`). Call it F. Your files are under `F/archive/`.

## After every scene
1. Save the scene text exactly as sent to the player to a file (for example `F/draft.md`).
2. `python3 bot.py -g F archive add draft.md --choice "<what the player chose that led to this scene>" --write`
   - `--title "..."` for a scene worth naming.
   - `--chapter "Chapter 4: ..."` when a new chapter begins: a new arc beat, a time skip, a change of place that changes the story's question. Without it the scene joins the current chapter, and a new day opens a chapter named after the day.
   - `--day N --time HH:MM` only when archiving a scene late.
3. Write its one-line summary, using only what the player saw: `python3 bot.py -g F archive summary <n> "..." --write`. No GM knowledge, no foreshadowing.

## Backfill, once
The scenes played before the archive existed are still in this conversation. Go back through it from the first scene, and for each one write the exact text to a file and `archive add` it with its `--day`, `--time`, `--choice` and chapter. Do not rebuild scenes from LOG.md: the log holds GM-side notes that the player has not seen.

## On request, and at the end of every chapter
- `python3 bot.py -g F archive book --write` builds `archive/BOOK.md` and `archive/BOOK.html`: dice lines and option menus removed, System messages kept, each choice shown as one line. `--raw` keeps everything. Give the player the HTML file.
- `python3 bot.py -g F archive recap 5` gives the last five summaries with the choices made. Use it to open a session ("Previously...") and to reload after a context reset, before reading STATE_NOW.
- `python3 bot.py -g F archive list` shows scenes with no choice or summary recorded. Fill them in.

## Saves
Use `bot.py book save/load`. Loading an older save does not delete anything: scenes played after that save are set aside and left out of the book.

## Output
One line: the scene number archived, its chapter, and the running word count.
