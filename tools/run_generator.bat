@echo off
rem ---- 1. Edit these three paths once, 2. double-click this file (re-run after you change your mod list) ----
set "MO2_MODS=Z:\root\Wabbajack\Morrowind - Nerevar-Moon-and-Star\mods"
set "MODLIST=Z:\root\Wabbajack\Morrowind - Nerevar-Moon-and-Star\profiles\NEMAS\modlist.txt"
set "GAME_DATA=Z:\Program Files (x86)\Steam\steamapps\common\Morrowind\Data Files"
rem ---------------------------------------------------------------------------------------------------------
set "OUT=%~dp0..\Scripts\Questman\questSourcesData.lua"
where python >nul 2>nul && (set "PY=python") || (set "PY=py -3")
%PY% "%~dp0build_quest_sources.py" --mo2-mods "%MO2_MODS%" --modlist "%MODLIST%" --game-data "%GAME_DATA%" --out "%OUT%" --renames "%~dp0renames.txt" --categories "%~dp0categories.txt"
echo.
echo Open the *_report.txt and *_categories.txt next to questSourcesData.lua to see what was found.
pause
