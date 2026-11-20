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
$B rules add xp_sources kind=rule text="XP comes from kills, quests, trials survived and fights won without killing" --write
```

## 3. The quest already completed in the story, and the ones owed
The hidden quest "The Courage to Stay" paid a blessing and no XP. Record it, then pay what the new XP rule owes.
```
$B quest add courage kind=hidden title="The Courage to Stay" text="Stay so the others can leave." --write
$B quest done courage --write
$B quest add wager kind=hidden title="A Wager Honoured" text="Win the dokkaebi's bet and spare it." xp=medium --write
$B quest add jung kind=hidden title="Not Them" text="Put yourself between the club and the boy." xp=medium --write
$B quest add temple kind=trial title="The Temple of Five Hundred" text="Walk." xp=trial --write
$B quest add furnace kind=hidden title="Four Hours" text="Survive the Flaming Mountains." xp=large --write
$B quest done wager --write ; $B quest done jung --write ; $B quest done temple --write ; $B quest done furnace --write
```
That is 35 + 35 + 100 + 60 XP on top of his 60. Whether to pay all of it, and how the System words it, is the GM's and the player's call.

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

## 5. The book
Save the full "story so far" text as `eth/story.md`, then:
```
$B archive import story.md --write
$B archive book --write          # add --raw to keep the dice lines
```
