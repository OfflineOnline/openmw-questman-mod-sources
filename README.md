<img width="2048" height="1152" alt="image" src="https://github.com/user-attachments/assets/4b8cdf8c-1fc1-4aed-8a0b-25c6f159babf" />


# Questman Mod Sources

An add-on for **[Questman 1.6](https://www.nexusmods.com/morrowind/mods/59493)** on **OpenMW 0.50+**.
Tested on [NEMAS](https://github.com/Sting-DR/Nerevar-Moon-and-Star) modlist

Splits Questman's generic "Other" bucket into dedicated add-on entries per mod, providing individual progress tracking, filter dropdown entries, and category grouping for third-party quests.

---

## Features
- **Individual Mod Tracking:** Replaces the catch-all "Other" group with a dedicated row per mod in Questman's Progress tab.
- **Smart Categorization:** Automatically maps quests to Questman categories (Guild, Great House, Daedric, Vampire, Bounty, Main Quest) or falls back to "Miscellaneous Quests".
- **Safe Mid-Save Installation:** Fully safe to install, update, or remove mid-playthrough. It only alters UI grouping logic and reads journal IDs; it does not touch your savegame state or quest progress.
- **Generator Pipeline:** Includes Python tooling (`tools/build_quest_sources.py`) to regenerate quest source mappings and categories.
- **Compatibility:** Should work for any other modlist out there too, in the example I used NEMAS 

---
## Requirements & Python Note

The generator tool located in `tools/build_quest_sources.py` is currently **Python-dependent** (requires Python 3.8+ installed on your system).

> **Standalone Executable:**  
> If there is community interest or request, a standalone Windows executable (`.exe`) will be packaged so the generator can be run without an existing Python installation. Feel free to open an Issue in this repository if you need it.


## Installation with MO2 (Recommended)
- Install the zip as a new MO2 mod below Questman
- Install Python 3 if you don’t have it.
- Open tools\run_generator.bat in a text editor and set the three paths at the top: your MO2 mods folder, the profile’s modlist.txt, and Morrowind’s Data Files folder. (I let My own paths there as example for you)
The Morrowind folder keeps vanilla quests from being credited to patch mods.
Run it. 
It writes the data file into the mod and a readable questSourcesData_report.txt listing every mod found, its quest count and example ids. If a name looks wrong, put plugin = Nicer Name in tools\renames.txt and run it again.

(The Categories and Renames are already set for NEMAS)



---

## Repository Structure

- `Scripts/Questman/`: Lua scripts extending Questman's metadata and quest providers.
- `docs/`: Original patches (`.patch`) and reference documentation.
- `tools/`: Build scripts (`build_quest_sources.py`, `run_generator.bat`) and mapping definitions (`categories.txt`, `renames.txt`).

---

## AI Transparency Notice
> Used Claude, Tested for functionality by myself. a human ~

---

## Credits & License
- Built for **Questman** by its original author [fixerm](https://www.nexusmods.com/profile/fixerm)  
- Compatible with **OpenMW**.
- Released under the [MIT License](LICENSE).
