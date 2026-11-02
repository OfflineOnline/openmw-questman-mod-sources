#!/usr/bin/env python3
"""
build_quest_sources.py -- tells Questman which MOD every journal quest comes from.

OpenMW cannot tell a Lua script which plugin a quest belongs to, so this tool reads your plugins
(.esp / .esm / .omwaddon / .omwgame) offline, finds every JOURNAL record (the quest ids) and notes which
plugin / mod defined it first. It writes Scripts/Questman/questSourcesData.lua, which the Questman add-on
reads in game to split the "Other" add-on into one add-on per mod.

Works with   * Mod Organizer 2   (--mo2-mods + --modlist)
             * a plain openmw.cfg (--openmw-cfg)
             * plain folders      (--data DIR, repeatable)
Needs only Python 3.8+ (no extra packages).

Examples
  python build_quest_sources.py ^
      --mo2-mods  "D:\\Modding\\MO2\\mods" ^
      --modlist   "D:\\Modding\\MO2\\profiles\\NEMAS\\modlist.txt" ^
      --out       "D:\\Modding\\MO2\\mods\\Questman Mod Sources\\Scripts\\Questman\\questSourcesData.lua"

  python build_quest_sources.py --openmw-cfg "%USERPROFILE%\\Documents\\My Games\\OpenMW\\openmw.cfg" --out questSourcesData.lua
"""
import argparse
import fnmatch
import configparser
import os
import re
import struct
import sys
import time

PLUGIN_EXT = ('.esp', '.esm', '.omwaddon', '.omwgame')
VANILLA = {'morrowind.esm', 'tribunal.esm', 'bloodmoon.esm'}   # ids from these are handled by Questman's own rules
# Plugins whose quests already have a built-in Questman add-on: ids Questman's rules miss land in that add-on.
BUILTIN = {
    'tr_mainland.esm': 'tamriel_rebuilt', 'tr_preview.esm': 'tamriel_rebuilt', 'tamriel_data.esm': 'tamriel_rebuilt',
    'cyrodiil_main.esm': 'project_cyrodiil', 'sky_main.esm': 'province_skyrim',
}


def ascii_lower(s):
    """Lowercase ASCII only -- exactly what Lua's string.lower does to the id in game."""
    return ''.join(chr(ord(c) + 32) if 'A' <= c <= 'Z' else c for c in s)


# ---------------------------------------------------------------------------------------------- plugin reading
JOURNAL_CMD = re.compile(r'journal\s*,?\s*"?([^\s",]+)"?\s*,?\s*(\d+)', re.I)


def cstr(data):
    return data.split(b'\0')[0].decode('cp1252', 'replace')


def parse_subrecords(body):
    sp = 0
    while sp + 8 <= len(body):
        name = body[sp:sp + 4]
        ssz = struct.unpack_from('<I', body, sp + 4)[0]
        yield name, body[sp + 8:sp + 8 + ssz]
        sp += 8 + ssz


def read_plugin(path):
    """Streams one TES3-format plugin (TR_Mainland is huge). Returns a dict:
         masters : [names]
         ids     : [journal ids defined here]
         names   : {lower id: quest name}          (journal INFO flagged "quest name")
         texts   : {lower id: [journal entry texts]}
         setters : {lower id: [(player_faction, actor_faction, script)]}   dialogue lines that advance the quest
    """
    out = {'masters': [], 'ids': [], 'names': {}, 'texts': {}, 'setters': {}}
    with open(path, 'rb') as f:
        head = f.read(16)
        if len(head) < 16 or head[:4] != b'TES3':
            raise ValueError('not a TES3 plugin')
        size = struct.unpack_from('<I', head, 4)[0]
        for name, data in parse_subrecords(f.read(size)):
            if name == b'MAST':
                out['masters'].append(cstr(data))
        cur_id, cur_type = None, None
        while True:
            head = f.read(16)
            if len(head) < 16:
                break
            name = head[:4]
            size = struct.unpack_from('<I', head, 4)[0]
            if name not in (b'DIAL', b'INFO'):
                f.seek(size, os.SEEK_CUR)
                continue
            body = f.read(size)
            if name == b'DIAL':
                did, dtype = None, None
                for sn, data in parse_subrecords(body):
                    if sn == b'NAME':
                        did = cstr(data)
                    elif sn == b'DATA' and data:
                        dtype = data[0]
                    elif sn == b'DELE':
                        dtype = -1
                cur_id, cur_type = did, dtype
                if did and dtype == 4:
                    out['ids'].append(did)
                continue
            # INFO
            if cur_id is None or cur_type in (None, -1):
                continue
            text, script, dnam, fnam, qname = '', '', '', '', False
            for sn, data in parse_subrecords(body):
                if sn == b'NAME':
                    text = cstr(data) if len(data) < 65536 else cstr(data[:65536])
                elif sn == b'BNAM':
                    script = cstr(data)
                elif sn == b'DNAM':
                    dnam = cstr(data)
                elif sn == b'FNAM':
                    fnam = cstr(data)
                elif sn == b'QSTN':
                    qname = True
            if cur_type == 4:
                lid = ascii_lower(cur_id)
                if qname and text:
                    out['names'][lid] = text
                elif text:
                    out['texts'].setdefault(lid, []).append(text)
            elif script and 'journal' in script.lower():
                for m in JOURNAL_CMD.finditer(script):
                    out['setters'].setdefault(ascii_lower(m.group(1)), []).append((dnam, fnam, script))
    return out


# ---------------------------------------------------------------------------------------------- discovery
class Plugin:
    def __init__(self, path, folder, modid=None):
        self.path = path
        self.name = os.path.basename(path)
        self.lname = self.name.lower()
        self.folder = folder        # MO2 mod folder / data folder name this plugin lives in
        self.modid = modid          # Nexus mod id from MO2's meta.ini, when known
        self.group_size = 1         # how many plugins share the folder (set later)
        self.order = 0              # position in load order (lower = earlier)


def find_plugins(folder, depth=1):
    out = []
    try:
        entries = sorted(os.listdir(folder), key=str.lower)
    except OSError:
        return out
    for e in entries:
        p = os.path.join(folder, e)
        if os.path.isfile(p) and e.lower().endswith(PLUGIN_EXT):
            out.append(p)
        elif depth > 0 and os.path.isdir(p):
            out.extend(find_plugins(p, depth - 1))
    return out


def read_modid(mod_dir):
    ini = os.path.join(mod_dir, 'meta.ini')
    if not os.path.isfile(ini):
        return None
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    try:
        cp.read(ini, encoding='utf-8')
        v = cp.get('General', 'modid', fallback='0').strip()
        return int(v) if v.isdigit() and int(v) > 0 else None
    except Exception:
        return None


def discover_mo2(mods_dir, modlist):
    """Enabled mods of an MO2 profile. modlist.txt lists the HIGHEST priority first, so reverse it: the mod
    loaded first (lowest priority) comes first."""
    names = []
    with open(modlist, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\r\n')
            if line.startswith('+') and not line.endswith('_separator'):
                names.append(line[1:])
    plugins = []
    for name in reversed(names):
        d = os.path.join(mods_dir, name)
        if not os.path.isdir(d):
            continue
        modid = read_modid(d)
        for p in find_plugins(d):
            plugins.append(Plugin(p, name, modid))
    return plugins


def parse_cfg(cfg):
    data, content = [], []
    with open(cfg, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('data='):
                v = line[5:].strip()
                if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
                    v = v[1:-1].replace('&&', '&')
                data.append(v)
            elif line.startswith('content='):
                content.append(line[8:].strip())
    return data, content


def discover_cfg(cfg):
    data, content = parse_cfg(cfg)
    base = os.path.dirname(os.path.abspath(cfg))
    dirs = [d if os.path.isabs(d) else os.path.join(base, d) for d in data if not d.startswith('?')]
    plugins = []
    for c in content:
        for d in reversed(dirs):   # a later data= folder overrides an earlier one
            p = os.path.join(d, c)
            if os.path.isfile(p):
                plugins.append(Plugin(p, os.path.basename(os.path.normpath(d))))
                break
    return plugins


def discover_dirs(dirs):
    plugins = []
    for d in dirs:
        for p in find_plugins(d):
            plugins.append(Plugin(p, os.path.basename(os.path.normpath(d))))
    return plugins


# ---------------------------------------------------------------------------------------------- naming
def slugify(text):
    s = re.sub(r'[^a-z0-9]+', '_', ascii_lower(text)).strip('_')
    return s or 'mod'


def load_renames(path):
    ren = {}
    if path and os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    ren[ascii_lower(k.strip())] = v.strip()
    return ren


def choose_title(pl, threshold, renames):
    """A mod folder with few plugins is named after the mod; a collection folder (like 'NEMAS Plugins') is
    split by plugin file name instead."""
    stem = os.path.splitext(pl.name)[0]
    title = pl.folder if pl.group_size <= threshold else stem
    for k in (pl.lname, ascii_lower(stem), ascii_lower(title)):
        if k in renames:
            return renames[k]
    return title


# ---------------------------------------------------------------------------------------------- categories
# Questman's own taxonomy (the same one UESP's Morrowind quest categories use for the vanilla game): Main Quest,
# guild / faction questlines, Great House questlines, Daedric, Vampire, Bounty, Miscellaneous. Modded quests carry no
# such label, so it is INFERRED from what the plugin says about the quest, and only when the evidence is clear:
#   * the quest NAME starts with a faction ("Mages Guild: Azura's Star", "House Telvanni: ...")        +6
#   * a dialogue line that advances the quest requires the PLAYER to be in a faction (or is spoken by
#     a member of one, or its script joins / promotes the player in one)                                +3 / +1 / +4
#   * the name mentions a Daedric Prince / vampires / bounties                                          +4
# A quest is classified when the best candidate scores >= 4 and is not tied; everything else stays "Miscellaneous".
FACTION_IDS = [   # (normalised substring of a faction id, Questman faction name) -- first match wins
    ('fightersguild', 'Fighters Guild'), ('magesguild', 'Mages Guild'), ('thievesguild', 'Thieves Guild'),
    ('moragtong', 'Morag Tong'), ('imperiallegion', 'Imperial Legion'), ('imperialcult', 'Imperial Cult'),
    ('eastempire', 'East Empire Company'), ('hlaalu', 'House Hlaalu'), ('redoran', 'House Redoran'),
    ('telvanni', 'House Telvanni'), ('houseindoril', 'House Indoril'), ('janatta', 'Ja-Natta Syndicate'),
    ('ordinators', 'Ordinators'), ('kingdomanvil', 'Kingdom of Anvil'), ('itinerantpriests', 'Itinerant Priests'),
    ('temple', 'Tribunal Temple'),
]
NAME_PREFIXES = {   # faction -> words a quest name may start with, followed by ':' or '-'
    'Fighters Guild': ['fighters guild', "fighter's guild", 'fg'], 'Mages Guild': ['mages guild', "mage's guild", 'mg'],
    'Thieves Guild': ['thieves guild', 'thief guild', 'tg'], 'Morag Tong': ['morag tong', 'mt'],
    'Imperial Legion': ['imperial legion', 'legion', 'il'], 'Imperial Cult': ['imperial cult', 'cult', 'ic'],
    'East Empire Company': ['east empire company', 'eec'], 'House Hlaalu': ['house hlaalu', 'hlaalu'],
    'House Redoran': ['house redoran', 'redoran'], 'House Telvanni': ['house telvanni', 'telvanni'],
    'House Indoril': ['house indoril', 'indoril'], 'Ja-Natta Syndicate': ['ja-natta syndicate', 'ja-natta'],
    'Ordinators': ['ordinators', 'ordinator'], 'Kingdom of Anvil': ['kingdom of anvil', 'anvil'],
    'Itinerant Priests': ['itinerant priests'], 'Tribunal Temple': ['tribunal temple', 'temple'],
}
HOUSES = {'House Hlaalu', 'House Redoran', 'House Telvanni', 'House Indoril'}
DAEDRA = re.compile(r'\b(azura|boethiah|mehrunes dagon|malacath|mephala|molag bal|sheogorath|hircine|namira|nocturnal|'
                    r'meridia|clavicus vile|peryite|vaermina|hermaeus mora|jyggalag|sanguine|daedric prince|daedric shrine)\b', re.I)
FACTION_CMD = re.compile(r'(?:pcjoinfaction|pcraiserank|pclowerrank|modfactionreputation|modpcfacrep|setpcfacrep)'
                         r'\s*,?\s*(?:"([^"]+)"|([A-Za-z_][\w ]*?)\s*(?:,|$|\r|\n))', re.I)
FACTION_CMD_BARE = re.compile(r'\b(pcjoinfaction|pcraiserank)\b\s*($|\r|\n|;)', re.I)
CAT_MAIN, CAT_DAEDRIC, CAT_VAMPIRE, CAT_BOUNTY, CAT_MISC = ('Main Quest', 'Daedric Quests', 'Vampire Quests', 'Bounty',
                                                           'Miscellaneous Quests')
CAT_SHORT = {'main': CAT_MAIN, 'daedric': CAT_DAEDRIC, 'vampire': CAT_VAMPIRE, 'bounty': CAT_BOUNTY, 'misc': CAT_MISC}


def faction_of(fid):
    n = re.sub(r'[^a-z0-9]', '', ascii_lower(fid or ''))
    for sub, fac in FACTION_IDS:
        if n and sub in n:
            return fac
    return None


def classify_quest(name, texts, setters):
    """-> (kind, value, score, evidence) with kind 'f' (faction) / 'c' (category), or None when unclear."""
    score, why = {}, {}

    def add(key, pts, note):
        score[key] = score.get(key, 0) + pts
        why.setdefault(key, []).append(note)

    lname = ascii_lower(name or '')
    for fac, words in NAME_PREFIXES.items():
        for w in words:
            if re.match(r'^(?:the )?' + re.escape(w) + r'\s*[:\-–—]', lname):
                add(('f', fac), 6, 'name starts with "%s"' % w)
                break
    if lname.startswith('main quest') or lname.startswith('the main quest'):
        add(('c', CAT_MAIN), 6, 'name says "main quest"')
    if DAEDRA.search(name or ''):
        add(('c', CAT_DAEDRIC), 4, 'name mentions a Daedric Prince / shrine')
    elif len(DAEDRA.findall(' '.join(texts))) >= 4:
        add(('c', CAT_DAEDRIC), 4, 'journal text names a Daedric Prince 4+ times')
    if 'vampir' in lname:
        add(('c', CAT_VAMPIRE), 4, 'name mentions vampires')
    if re.match(r'^\s*(bounty|wanted)\b', lname):
        add(('c', CAT_BOUNTY), 4, 'name starts with "bounty"/"wanted"')

    dn = fn = sc = 0
    for dnam, fnam, script in setters:
        f = faction_of(dnam)
        if f and dn < 6:
            dn += 3; add(('f', f), 3, 'a line needs the player in "%s"' % dnam)
        f = faction_of(fnam)
        if f and fn < 3:
            fn += 1; add(('f', f), 1, 'a line is spoken by a "%s" member' % fnam)
        if sc < 4:
            for m in FACTION_CMD.finditer(script):
                f = faction_of(m.group(1) or m.group(2))
                if f:
                    sc += 4; add(('f', f), 4, 'script: %s' % m.group(0).strip()[:40]); break
            else:
                if FACTION_CMD_BARE.search(script) and faction_of(fnam):
                    sc += 4; add(('f', faction_of(fnam)), 4, 'script joins / promotes in the speaker\'s faction')
    ranked = sorted(score.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] < 4:
        return None
    if len(ranked) > 1 and ranked[1][1] == ranked[0][1]:
        return None
    (kind, value), pts = ranked[0]
    return kind, value, pts, '; '.join(why[(kind, value)])


def load_category_overrides(path):
    """lines:  <id, id glob or src:Mod title> = <faction name | main | daedric | vampire | bounty | misc>"""
    out = []
    if path and os.path.isfile(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = [x.strip() for x in line.split('=', 1)]
                lv = ascii_lower(v)
                if lv in CAT_SHORT:
                    out.append((ascii_lower(k), 'c', CAT_SHORT[lv]))
                elif faction_of(v):
                    out.append((ascii_lower(k), 'f', faction_of(v)))
                else:
                    print('  categories file: unknown value "%s"' % v)
    return out


# ---------------------------------------------------------------------------------------------- main logic
def main():
    ap = argparse.ArgumentParser(description='Map Morrowind/OpenMW journal quest ids to the mod that defines them.')
    ap.add_argument('--mo2-mods', help='MO2 "mods" folder')
    ap.add_argument('--modlist', help='MO2 profile modlist.txt (only enabled mods are read)')
    ap.add_argument('--openmw-cfg', help='openmw.cfg (data= and content= lines)')
    ap.add_argument('--game-data', help='the Morrowind "Data Files" folder (Morrowind.esm / Tribunal.esm / Bloodmoon.esm). '
                    'Recommended with MO2: without it a mod that merely ADDS entries to a vanilla quest could be blamed for it')
    ap.add_argument('--data', action='append', default=[], help='plain folder containing plugins (repeatable)')
    ap.add_argument('--out', default='questSourcesData.lua', help='output file (default: ./questSourcesData.lua)')
    ap.add_argument('--report', help='also write a readable report (default: next to --out)')
    ap.add_argument('--renames', help='text file with "plugin or mod name = Nicer Title" lines')
    ap.add_argument('--categories', help='text file forcing categories: "id / id glob / src:Mod title = Mages Guild | daedric | vampire | bounty | main | misc"')
    ap.add_argument('--no-categories', action='store_true', help='do not guess guild / faction / Daedric ... categories')
    ap.add_argument('--collection-threshold', type=int, default=4,
                    help='a mod folder with MORE plugins than this is split by plugin name (default 4)')
    args = ap.parse_args()

    if args.mo2_mods and args.modlist:
        plugins = discover_mo2(args.mo2_mods, args.modlist)
    elif args.openmw_cfg:
        plugins = discover_cfg(args.openmw_cfg)
    elif args.data:
        plugins = discover_dirs(args.data)
    else:
        ap.error('give --mo2-mods and --modlist, or --openmw-cfg, or --data')
    if args.game_data:
        plugins = discover_dirs([args.game_data]) + plugins
    if not plugins:
        sys.exit('No plugins found -- check the paths.')
    if not any(p.lname in VANILLA for p in plugins):
        print('WARNING: Morrowind.esm / Tribunal.esm / Bloodmoon.esm were not scanned (give --game-data). Mods that only\n'
              '         extend a vanilla quest may be listed as its source; harmless for most quests, since Questman\n'
              '         only uses this data for quests its own rules cannot place.')

    for i, pl in enumerate(plugins):
        pl.order = i
    per_folder = {}
    for pl in plugins:
        per_folder[pl.folder] = per_folder.get(pl.folder, 0) + 1
    for pl in plugins:
        pl.group_size = per_folder[pl.folder]
    renames = load_renames(args.renames)

    # read every plugin
    info = {}   # lname -> read_plugin() dict
    t0 = time.time()
    for n, pl in enumerate(plugins, 1):
        try:
            info[pl.lname] = read_plugin(pl.path)
        except Exception as e:
            print(f'  skipped {pl.name}: {e}')
            continue
        if n % 50 == 0:
            print(f'  ... {n}/{len(plugins)} plugins')
    by_lname = {pl.lname: pl for pl in plugins if pl.lname in info}

    # transitive masters, so a plugin that EXTENDS another's quest never claims it
    def all_masters(lname, seen=None):
        seen = seen if seen is not None else set()
        for m in info.get(lname, {'masters': []})['masters']:
            lm = m.lower()
            if lm not in seen:
                seen.add(lm)
                all_masters(lm, seen)
        return seen
    master_cache = {ln: all_masters(ln) for ln in info}

    definers = {}   # lowercase id -> [plugin lnames], in load order
    display = {}    # lowercase id -> id as written in the plugin
    for pl in plugins:
        if pl.lname not in info:
            continue
        for jid in set(info[pl.lname]['ids']):
            lid = ascii_lower(jid)
            definers.setdefault(lid, []).append(pl.lname)
            display.setdefault(lid, jid)

    owner = {}      # lowercase id -> Plugin that first defined it
    for lid, cands in definers.items():
        if any(c in VANILLA for c in cands):
            continue    # a vanilla quest (maybe extended by a mod): Questman's own rules classify it
        roots = [c for c in cands if not any(o in master_cache[c] for o in cands if o != c)]
        owner[lid] = by_lname[(roots or cands)[0]]

    # group ids by source (mod)
    sources = {}    # key -> dict(title, plugins:set, folder, modid, ids:list)
    used_titles = {}
    for lid, pl in sorted(owner.items()):
        builtin = BUILTIN.get(pl.lname)
        if builtin:
            key, title = builtin, None
        else:
            title = choose_title(pl, args.collection_threshold, renames)
            key = 'src_' + slugify(title)
            # two different titles slugifying alike must not merge
            if used_titles.setdefault(key, title) != title:
                key = key + '_' + slugify(os.path.splitext(pl.name)[0])
                used_titles.setdefault(key, title)
        s = sources.setdefault(key, {'title': title, 'plugins': set(), 'folder': pl.folder,
                                     'modid': pl.modid, 'ids': []})
        s['plugins'].add(pl.name)
        s['ids'].append(lid)

    # ---- guess categories / factions
    quest_names, quest_texts, quest_setters = {}, {}, {}
    for pl in plugins:
        d = info.get(pl.lname)
        if not d:
            continue
        for k, v in d['names'].items():
            quest_names.setdefault(k, v)
        for k, v in d['texts'].items():
            quest_texts.setdefault(k, []).extend(v)
        for k, v in d['setters'].items():
            quest_setters.setdefault(k, []).extend(v)
    overrides = load_category_overrides(args.categories)
    cats = {}       # lowercase id -> (kind, value, note)
    key_title = {k: (v['title'] or k) for k, v in sources.items()}
    id_source = {i: k for k, v in sources.items() for i in v['ids']}
    for lid in owner:
        forced = None
        for pat, kind, value in overrides:
            if pat.startswith('src:'):
                hit = ascii_lower(key_title[id_source[lid]]) == pat[4:].strip()
            else:
                hit = fnmatch.fnmatchcase(lid, pat)
            if hit:
                forced = (kind, value, 'forced by categories file')
        if forced:
            cats[lid] = forced
        elif not args.no_categories:
            r = classify_quest(quest_names.get(lid, ''), quest_texts.get(lid, []), quest_setters.get(lid, []))
            if r:
                cats[lid] = (r[0], r[1], r[3])

    # ---- write Lua data
    def lua_str(v):
        return '"' + v.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'

    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    total = 0
    with open(args.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('-- GENERATED by tools/build_quest_sources.py on %s -- do not edit; re-run the tool instead.\n'
                % time.strftime('%Y-%m-%d %H:%M'))
        f.write('-- %d journal ids from %d mods / plugins.\nreturn {\n  sources = {\n' % (len(owner), len(sources)))
        for key in sorted(sources, key=lambda k: (sources[k]['title'] or k).lower()):
            s = sources[key]
            total += len(s['ids'])
            f.write('    { key = %s,' % lua_str(key))
            if s['title']:
                f.write(' title = %s,' % lua_str(s['title']))
            f.write(' plugin = %s,' % lua_str(', '.join(sorted(s['plugins']))))
            if s['modid']:
                f.write(' modid = %d,' % s['modid'])
            f.write('\n      ids = [==[\n')
            f.write('\n'.join(s['ids']))
            f.write('\n]==] },\n')
        f.write('  },\n')
        if cats:
            f.write('  -- id <TAB> f|c <TAB> value   (f = faction name, c = category), only for quests with clear evidence\n')
            f.write('  categories = [==[\n')
            for lid in sorted(cats):
                f.write('%s\t%s\t%s\n' % (lid, cats[lid][0], cats[lid][1]))
            f.write(']==],\n')
        f.write('}\n')

    # ---- readable report
    report = args.report or os.path.splitext(args.out)[0] + '_report.txt'
    with open(report, 'w', encoding='utf-8') as f:
        f.write('Quest sources found (%d journal ids, %d sources). Rename any of them with --renames.\n\n' % (total, len(sources)))
        for key in sorted(sources, key=lambda k: -len(sources[k]['ids'])):
            s = sources[key]
            nm = s['title'] or '(built-in add-on: %s)' % key
            f.write('%5d  %-45s plugin: %s%s\n' % (len(s['ids']), nm, ', '.join(sorted(s['plugins'])),
                                                    '   [nexus mod id %d]' % s['modid'] if s['modid'] else ''))
            f.write('        e.g. %s\n' % ', '.join(display[i] for i in s['ids'][:4]))
    cat_report = os.path.splitext(args.out)[0] + '_categories.txt'
    with open(cat_report, 'w', encoding='utf-8') as f:
        f.write('%d of %d mod quests got a category / faction; the rest stay Miscellaneous.\n' % (len(cats), len(owner)))
        f.write('Wrong guess? Add "<quest id> = misc" (or a faction name) to a categories file and pass --categories.\n\n')
        for lid in sorted(cats, key=lambda i: (cats[i][1], i)):
            kind, value, note = cats[lid]
            f.write('%-40s -> %-22s %s | "%s"\n' % (display.get(lid, lid), value, note, quest_names.get(lid, '')))
    print('Categories guessed for %d of %d quests (see %s)' % (len(cats), len(owner), cat_report))
    print('Done in %.1fs: %d journal ids, %d mods.' % (time.time() - t0, total, len(sources)))
    print('Wrote', args.out)
    print('Report:', report)


if __name__ == '__main__':
    main()
