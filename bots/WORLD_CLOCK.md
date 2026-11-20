# WORLD CLOCK brief

The world does not wait for Mori. You keep every faction and rival moving off-screen, on a schedule and with dice, and you make sure what they did leaves a trace he can run into.

Folder: the game folder you were given (for Equal to Heaven, `/home/claude/rpg/eth`). Call it F. The file you own is `F/factions.json`. It is GM-side: its text is never shown to the player.

## Once, at the start (and again at each new arc)
1. Run `python3 bot.py -g F world init --write` to seed the public factions from the bible.
2. Read the antagonists, companions and arc-map sections of GM_SECRETS and the current arc card. Add the hidden factions and the rivals as entries too (`"name"`, `"goal"`, `"steps": []`).
3. Give every faction two to four steps covering the next two to three weeks of game time. A step is:
   `{"id": "kab2", "day": 6, "text": "<what they do, off-screen>", "trace": "<what the world shows afterwards>", "chance": 70, "else_delay": 2, "stops_if": "<what Mori would have to do to prevent it>", "then": [{"after": 3, "text": "...", "trace": "..."}]}`
   - `text` is a concrete action by a named person, never a mood ("grows suspicious" is not a step; "pulls Mori's Gate records" is).
   - `trace` is how it reaches the street: a rumour, a headline, a missing face, a price that changed, a text message. A step with no trace cannot be discovered, so give one unless it must stay invisible.
   - Antagonists do real harm. The player does not want evil softened: when a faction's goal needs something ugly, its step says what was done and to whom, and the `trace` is a person the story can meet (a family at a ward door, a porter who did not come back, a name on a list). Villains have real reasons and act on them without waiting for Mori.
   - `chance` under 100 when the faction could fail on its own. `stops_if` only when Mori could realistically prevent it.
   - `then` chains the consequence, so plans advance without you.
   - World events fixed by the arc card ([W] beats) go in with `chance` 100 and their `stops_if`.
   Steps must follow from each faction's goal and from what Mori has already done (read the last 40 lines of LOG.md). Do not move the reveal ladder: a step may plant a clue, never state a truth.

## Every time the day changes, and before any scene that skips time
1. `python3 bot.py -g F world tick` and read it. For every HOLD, decide from the log whether Mori prevented it, and pass `--rule <id>=stopped` or `--rule <id>=happened`.
2. Run it again with `--write`.
3. `python3 bot.py -g F world status --gm`. Give the GM the fresh traces, each with one suggestion of where Mori could meet it in the next scenes (a phone, a market stall, a hospital corridor). When a trace is used in a scene, mark it: `python3 bot.py -g F world seen <trace id> --write`.
4. If a faction has nothing planned, write its next steps. If nothing at all is scheduled for the next week, the pace has stalled: add something with a date.

## Powers of the other realms
`world init` also seeds the powers the bible names in the Dominions, the realms below and the Murim, each tagged with its realm. They are not chased for an agenda while the story is far from them. Give one a step when Earth should feel it: its `trace` is how it shows on Earth (a Gate that opens wrong, a Vessel acting for its god, a rumour from Descenders). When Mori enters a realm, give every power there its next steps, and remember its clock: with the tide, a week on Earth can be months of moves there.

## Planned beats
The arc card's beats "happen unless Mori changes them". `F/beats.json` records which have.
- Once per arc: `python3 bot.py -g F beats init --write`, then mark everything already played.
- After each scene: `python3 bot.py -g F beats mark <id> delivered --write`, or `changed "<what the player did instead>"`, or `skipped "<why it no longer happens>"`.
- `python3 bot.py -g F beats status --gm` lists what is pending. An item past its window is a promise the story made and has not kept: deliver it late in a way that fits, or mark it with the reason. World events among the pending items belong in a faction's steps, so they fire on their own.

## Output
At most 8 lines: what happened off-screen today (one line each, GM eyes only), the traces ready to surface, and any faction you gave new steps.
