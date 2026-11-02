Questman Mod Sources -- splits Questman's "Other" add-on into one add-on per mod
===============================================================================
Built for Questman 1.6 (Nexus 59493), OpenMW 0.50+.  Works together with "Questman Notes" (different files).

WHAT IT DOES
  Quests Questman's id rules don't recognise (everything that isn't vanilla / Tamriel Rebuilt / Project Cyrodiil /
  Skyrim) used to pile up in the add-on "Other" and the category "Unknown". With this mod each mod gets its own
  add-on: its own row in the Progress tab (done / total), its own entry in the filter dropdown, and its name next
  to the category in the quest detail pane, e.g. "Miscellaneous Quests (Casimir's Legacy)".
  Categories: the tool also tries to place each mod quest into Questman's own categories (guild / house
  questline with its faction, Daedric, Vampire, Bounty, Main Quest). Everything without clear evidence counts as
  "Miscellaneous Quests" instead of "Unknown" (switch off: SET_CATEGORY = false in questSources.lua).

WHY A GENERATOR TOOL
  OpenMW cannot tell a Lua script which plugin a quest came from. So the information is collected once, offline:
  tools/build_quest_sources.py reads your plugins, finds every journal (quest) id and records which plugin / MO2 mod
  defined it first. Questman then only has to look the id up.

INSTALL (MO2)
  1. Install this zip as a NEW mod, BELOW Questman (and below Questman Notes, if you use it).
     It replaces questMetadata.lua and questProvider.lua of Questman and adds questSources.lua + questSourcesData.lua.
  2. Install Python 3 (python.org, tick "Add to PATH") if you don't have it.
  3. Open tools\run_generator.bat in a text editor and set the three paths at the top:
        MO2_MODS   = your MO2 "mods" folder
        MODLIST    = the profile's modlist.txt  (MO2: profiles\<profile>\modlist.txt)
        GAME_DATA  = Morrowind's "Data Files" folder (so vanilla quests are known and not blamed on patch mods)
     Run it. The tool sits inside this mod, so it writes Scripts\Questman\questSourcesData.lua right here.
     (From the MO2 mod list: right-click the mod -> "Open in Explorer" to find tools\.)
  4. Read tools\..\Scripts\Questman\questSourcesData_report.txt: every mod/plugin found, quest count, example ids.
     Don't like a name? Put "plugin or folder name = Nicer Name" into tools\renames.txt and run again.
  5. Start OpenMW, open Questman -> Progress tab.
  Re-run the generator whenever you add or remove quest mods.

HOW CATEGORIES ARE GUESSED (offline, from the plugin; UESP's quest categories are the same taxonomy, but only
cover the vanilla game, so they can't be looked up for mods)
  A quest is classified only when the evidence is clear (score >= 4 and no tie):
    name starts with a faction ("Mages Guild: ...", "House Telvanni: ...")                        +6
    a dialogue line that advances the quest needs the player in a faction                          +3
    a script on such a line joins / promotes the player in a faction                               +4
    the speaker of such a line belongs to a faction (weak, never enough alone)                     +1
    name mentions a Daedric Prince or shrine / vampires / "Bounty:" / "Main Quest"                 +4..6
  tools\..\Scripts\Questman\questSourcesData_categories.txt lists every guess WITH its reason. A wrong guess,
  or a mod you want fixed, goes into tools\categories.txt, e.g.
      rr_mq_* = House Telvanni          (id or id pattern)
      src:Some Quest Mod = misc         (all quests of one mod)
  then run the generator again.

HOW MODS ARE NAMED
  - MO2 mod folder with up to 4 plugins   -> the MO2 mod name ("Casimir's Legacy")
  - a bigger collection folder (like "NEMAS Plugins") -> one add-on per plugin file name
  - a quest is blamed on the FIRST plugin that defined it; patches that only add to it don't take it over
  - Tamriel_Data / TR_Mainland / Cyrodiil_Main / Sky_Main quests stay in their built-in add-ons
  - the Nexus mod id (from MO2's meta.ini) is stored in the data file and shown in the report

WITHOUT THE DATA FILE (or for ids it doesn't know)
  A fallback groups unplaced quests by the prefix of their id ("CS_Crab01" -> "CS_* (unknown mod)"), when at least
  3 unplaced quests share the prefix. Everything else stays in "Other".

IF QUESTMAN UPDATES
  It overwrites the two patched files; docs\*.patch hold the small changes (about 25 lines in total).
