# Catch-up for Equal to Heaven (Day 2, 04:05)

The story is ahead of the files. The ledger that was uploaded still has Mori at HP 1 with no blessing;
in the story he woke at 04:00, verified the hidden quest "The Courage to Stay", and was fully healed.
Run these in the game chat, from `/home/claude/rpg`, after the first-time setup in the README.
Check each dry run before adding `--write`.

## 1. What only gm.py may do
```
cd eth
python3 gm.py hp full
python3 gm.py set fatigue=0 time=04:05
python3 gm.py skill "The Pilgrim's Blessing" "Rebirth of the Body (used); Longevity: immune to ordinary disease and poison, sleep greatly increases regeneration"
python3 gm.py item + "Seohae Union envelope: hazard pay from Gangu (unopened)"
python3 gm.py item + "KAB card: Inspector Ha Sion, Surveillance Division"
cd ..
```

## 2. Rulings the story made
```
B="python3 novelbot/bot.py -g eth"
$B rules add longevity kind=rule text="Pilgrim's Blessing, Longevity: immune to ordinary disease and poison; sleeping greatly increases regeneration (replaces 'sleep = normal healing only')" --write
$B rules add death_save kind=rule text="At 0 HP with nobody to stabilise him: one death save, d20 vs DC 11, with a bonus only for something already established in the scene. Decide whether this stands beside the written 0 HP rule" --write
$B rules add system_rewards kind=lesson text="The System rewards what Mori does without being asked. After every scene, check for a hidden quest he has already fulfilled and pay it then. (The 'Courage to Stay' reward only happened because the player pointed out it was missing.)" --write
$B rules add growth_unasked kind=lesson text="Skill gains are announced by the GM when they are earned. Run the growth check after every scene. (Mastery 4, Erase the Rhythm and Endurance were only given because the player asked.)" --write
$B rules add respect_line_lifted kind=rule text="PLAYER RULING 2026-11-20: the 'respect line' is lifted. The player does not mind evil being shown: figures of real religions and mythologies (Buddhas, bodhisattvas, arhats, gods of any pantheon, the Abrahamic God and its relics) may be depicted, may be antagonists and may do evil when the story is better for it. This overrides the respect line at the top of GM_SECRETS, the Christian-relic line in its rulings section, and the same rule in the GM skill. Nothing already established has to be rewritten because of it." --write
$B rules add xp_sources kind=rule text="XP comes from kills, quests, trials survived and fights won without killing" --write
```

Then make the same change where the old rule is written, so no bot reads it as still binding:
- In `eth/GM_SECRETS.md`, replace the line that starts `Respect line:` with: `Respect line: LIFTED by the player on 2026-11-20. Any figure of any religion or mythology may be depicted, may be an antagonist and may do evil when the story is better for it. Existing plot stays as written unless the GM chooses to change it.`
- In the same file's rulings section, delete the bullet that says an Aegis fragment and a white feather "replace any Christian relic".
- The GM skill ("Standing rules from the user") still says to respect real religions and never depict the Abrahamic God. The player edits or removes that line in the skill; until then, this ruling wins.

## 3. The quest already completed in the story, and the ones owed
The hidden quest "The Courage to Stay" paid a blessing and no XP. Record it, then pay what the new XP rule owes.
```
$B quest add courage kind=hidden title="The Courage to Stay" text="Stay so the others can leave." --write
$B quest done courage --write
$B quest add wager kind=hidden title="A Wager Honoured" text="Win the dokkaebi's bet and spare it." xp=35 --write
$B quest add jung kind=hidden title="Not Them" text="Put yourself between the club and the boy." xp=35 --write
$B quest add temple kind=trial title="The Temple of Five Hundred" text="Walk." xp=100 --write
$B quest add furnace kind=hidden title="Four Hours" text="Survive the Flaming Mountains." xp=60 --write
$B quest done wager --write ; $B quest done jung --write ; $B quest done temple --write ; $B quest done furnace --write
```
These are fixed numbers, sized for the level he was when he earned them (level 1): 35 + 35 + 100 + 60 = 230 XP on top of his 60, which makes him level 2 with 190/200. New quests should use sizes (`xp=medium`) so they scale with his level. Whether to pay all of it, and how the System words it, is the GM's and the player's call.

## 4. One bookkeeping pass (`delta.json`)
```json
{"where": "St. Mary's 2F ward, his bed", "with": [],
 "now": "04:05, fully healed by the Pilgrim's Blessing; arm still in a sling, pins still in a bone that no longer needs them",
 "pending": "what to do with the 19 hours 54 minutes left on the Daily Discipline",
 "items_remove": ["Fishcake skewers"], "events_done": ["muster"],
 "threads_add": ["Pyo checked himself out with three broken ribs and has disappeared; he wanted the horn-ring",
                 "Inspector Ha Sion closed his file, but saw the meter read 0.0 and knows the dojang",
                 "His sister noticed something wrong when he could not say her name",
                 "The doctors will find a healed collarbone with pins in it",
                 "Gangu's hazard-pay envelope is unopened"],
 "facts": {"temple": {"text": "what really happened inside the gold Gate", "pattern": "arhat|precept|golden monkey|the lamp"},
           "system": {"text": "Mori sees a System", "pattern": "status window|Daily Discipline|the System"},
           "lost_name": {"text": "Mori has lost his sister's name", "pattern": "can't say her name|lost her name"}},
 "people": {"Hana": {"told": {"temple": "a hidden room collapsed and a statue fell on him"}, "where": "home", "note": "noticed something off when he did not say her name"},
            "Daeil": {"learn": ["temple"], "note": "was inside; saw Mori stay; went along with 'statue'"},
            "Seorin": {"learn": ["temple"], "note": "counted forty seconds; 'don't ever do that again'"},
            "Gangu": {"learn": ["temple"], "where": "Union office", "note": "left hazard pay; sat an hour without speaking"},
            "Pyo": {"learn": ["temple"], "where": "unknown", "status": "missing", "note": "checked out against advice; three broken ribs"},
            "Bang": {"learn": ["temple"], "where": "St. Mary's", "note": "right leg crushed; knee saved; a year in a brace"},
            "Ha Sion": {"told": {"temple": "sub-dungeon collapse, every account matches"}, "note": "meter flickered 0.0; looked at the ring; knows the dojang"}},
 "log": "Catch-up: hidden quest 'The Courage to Stay' verified, Pilgrim's Blessing applied, fully healed at 04:05."}
```
```
$B book apply delta.json --write
$B sync
$B ahead
```

## 5. Leak patterns (GM-side)
```
cp novelbot/examples/eth_secrets_watch.json eth/secrets_watch.json
```
The scene check then reports any of those names or phrases appearing in a scene before its rung of the reveal ladder. It leaves out every term that is already in the player's bible. The CLUE_KEEPER can add more.

Hidden powers and their first moves, taken from GM_SECRETS and the arc card (edit freely; the WORLD_CLOCK keeper carries on from here):
```
$B world import novelbot/examples/eth_factions_seed.json --write
$B rules add jeju_flicker kind=rule text="Whenever Mori fights all-out, the news later reports that the Jeju Wall flickered at that minute. A clue, never explained." --write
$B rules add the_staff_is_the_ruyi kind=rule text="Mori's 'staff' means the Ruyi and nothing else. He does not fight with staff forms: he commands it (Expand, Shrink, Sink, Come to me), uses its size and weight, plants it as a wall, pillar or vault, and drives Renewal's spin through it. Until it returns he fights bare-handed, and the System offers him no divine weapon. The Ruyi technique cards unlock when a skill named Ruyi is on his sheet." --write
$B rules add nobody_knows_yet kind=rule text="Until the Ruyi crosses Korea on camera, no Dominion knows the Monkey lives. The ring hides its wearer from divine sight: Muninn's crow, Wujing and any god's Vessel see only an odd E-rank. The Ferry knows only that something broke a Lure Temple in Incheon. Ha Sion has a meter reading he cannot explain, not an answer. Odin, Mara, Gwon and the rest learn at the Act III showdown, all at once." --write
$B rules add longevity_is_not_immortality kind=rule text="The blessing's 'Longevity' is regeneration and immunity to ordinary illness. He is still mortal; the immortalities are gone and can only be re-earned at a price." --write
```
In the Murim the tide is about 30 to 1 in 2047: set it with `"tide"` when he Descends.

Two notes for the GM from a read of GM_SECRETS against what has been played:
- The retroactive quest for the temple (section 3) must not be worded as a Tribulation. The Tribulation count is announced later, as the arc card has it.
- The Daily Discipline's first task is given two ways: the bible and every scene played say 1,000 Hoechook; the rulings section of GM_SECRETS says 1,000 staff spins. Keep what was played, and correct the note or record why it will change.

## 6. The book
Save the full "story so far" text as `eth/story.md`, then:
```
$B archive import story.md --write
$B archive book --write          # add --raw to keep the dice lines
```
