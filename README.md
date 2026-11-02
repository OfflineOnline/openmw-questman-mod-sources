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
- **Compatibility:** Should work for any other modlist out there too, in the example I used NEMAS 

---
## Requirements & Python Note

The generator tool located in `tools/build_quest_sources.py` is currently **Python-dependent** (requires Python 3.8+ installed on your system).

> **Standalone Executable:**  
> If there is community interest or request, a standalone Windows executable (`.exe`) will be packaged so the generator can be run without an existing Python installation. Feel free to open an Issue in this repository if you need it.


## Installation with Mod Organizer 2 (Recommended)

> **Quick Note:** The generator script needs **Python 3.8+**. If you don't have Python installed, grab it once from [python.org](https://www.python.org/) (make sure to tick *"Add Python to PATH"* during setup).

1. **Install the Mod:**  
   Install the archive via Mod Organizer 2 like any standard mod. Place it **below Questman** in your left-pane priority list so its scripts load properly.
2. **Set Your Paths:**  
   Right-click the mod in MO2 &rarr; *Open in Explorer*, navigate into the `tools/` folder, and open `run_generator.bat` in a text editor. Check the top three variables:
   - `MO2_MODS`: Path to your MO2 `mods` directory.
   - `MODLIST`: Path to your active profile's `modlist.txt`.
   - `GAME_DATA`: Path to Morrowind's vanilla `Data Files` folder *(essential so vanilla quests aren't accidentally credited to random patch plugins)*.
     
   *(The file already contains working example paths to show you the exact format).*
3. **Run the Generator:**  
   Double-click `run_generator.bat`.  
   - It parses your plugins and writes `Scripts/Questman/questSourcesData.lua` straight into the mod folder.
   - It also drops a clean `questSourcesData_report.txt` next to it, showing every detected mod, quest count, and sample IDs.
4. **Tune Names & Categories (Optional):**  
   If a mod gets attributed with a weird internal filename, add a clean name as `plugin.esp = Nicer Name` into `tools/renames.txt` and re-run the `.bat`.  
   *(Pre-configured bonus: Categories and renames are already tuned and ready out of the box for the NEMAS modlist!)*


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
