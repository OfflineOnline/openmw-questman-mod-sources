-- questman mod sources: splits the "Other" add-on (quests questMetadata's id rules don't recognise) by MOD.
--
-- OpenMW cannot say which plugin a journal record came from (DialogueRecord has only id / name / questName /
-- infos), so there are two layers, best first:
--   1. EXACT   questSourcesData.lua -- generated OFFLINE by tools/build_quest_sources.py, which reads your
--              plugins and records, per journal id, the plugin / MO2 mod that first defined it.
--   2. PREFIX  fallback when an id is not in the data: group by the id's prefix ("CS_Crab01" -> "CS_"), but only
--              when at least MIN_PREFIX unclaimed ids share it (else it would shatter "Other" into one-quest shards).
-- Anything still unplaced stays in "Other".
--
-- Slugs: src_<mod> (exact) and pfx_<prefix> (fallback). They are the persisted add-on filter key, so they are
-- derived from the mod / prefix name and stay stable across regenerations.

local core = require('openmw.core')

local M = {}

-- A mod quest the id rules left without a category counts as a Miscellaneous quest (otherwise the whole
-- mod pile also sits in the "Unknown" category). Set to false to leave the category as Unknown.
local SET_CATEGORY = true
local MIN_PREFIX = 3   -- fallback: smallest group of unclaimed ids that gets its own add-on

local byId, titles, catById = {}, {}, {}
do
    local ok, data = pcall(require, 'scripts.questman.questSourcesData')
    if ok and type(data) == 'table' then
        for _, src in ipairs(data.sources or {}) do
            if src.title and src.title ~= '' then titles[src.key] = src.title end
            for id in (src.ids or ''):gmatch('[^\r\n]+') do byId[id] = src.key end
        end
        -- "id <TAB> f|c <TAB> value": the tool's guess for a quest's faction (f) or category (c)
        for line in (data.categories or ''):gmatch('[^\r\n]+') do
            local id, kind, value = line:match('^(.-)\t(%a)\t(.+)$')
            if id then catById[id] = { kind = kind, value = value } end
        end
    end
end

local ruled            -- questMetadata.ruled (injected: this module must not require questMetadata back)
local prefixCount      -- prefix -> number of unclaimed journal ids, built once on first use

-- "cs_crab01" -> "cs". Ids without a letter-led "<prefix>_" yield nil.
local function prefixOf(id)
    return id:match('^([a-z][a-z0-9]*)_')
end

local function prime()
    if prefixCount then return end
    prefixCount = {}
    pcall(function()
        for _, rec in pairs(core.dialogue.journal.records) do
            local id = rec.id and rec.id:lower()
            if id and not byId[id] and not (ruled and ruled(id)) then
                local p = prefixOf(id)
                if p then prefixCount[p] = (prefixCount[p] or 0) + 1 end
            end
        end
    end)
end

function M.init(ruledFn) ruled = ruledFn end

--- Classification for a lowercase journal id the rules could not place, or nil.
function M.classify(id)
    local key = byId[id]
    if not key then
        local p = prefixOf(id)
        if p then
            prime()
            if (prefixCount[p] or 0) >= MIN_PREFIX then key = 'pfx_' .. p end
        end
    end
    if not key then return nil end
    local res = { addon = key }
    local c = catById[id]
    if c and c.kind == 'f' then
        res.faction = c.value          -- questMetadata derives the category (guild / great house) from it
    elseif c then
        res.category = c.value
    elseif SET_CATEGORY then
        res.category = 'Miscellaneous Quests'
    end
    return res
end

--- Display title for a mod add-on slug (nil for anything that is not one of ours).
function M.title(key)
    if type(key) ~= 'string' then return nil end
    if titles[key] then return titles[key] end
    local p = key:match('^pfx_(.+)$')
    if p then return p:upper() .. '_* (unknown mod)' end
    return nil
end

return M
