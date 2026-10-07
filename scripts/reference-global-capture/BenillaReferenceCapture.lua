-- Developer instrument for reference/3.3.5a-globals.tsv. This is our code, not shipped UI.
-- Run `/brcapture`, then log out or `/reload`; WoW serialises the result to SavedVariables.

-- Build 12340 keeps these in the locale MPQs. GetNumAddOns() does not enumerate them on every
-- installation, but FrameScript's LoadAddOn resolves their registered names directly.
local SHIPPED_ADDONS = {
    "Blizzard_AchievementUI",
    "Blizzard_ArenaUI",
    "Blizzard_AuctionUI",
    "Blizzard_BarbershopUI",
    "Blizzard_BattlefieldMinimap",
    "Blizzard_BindingUI",
    "Blizzard_Calendar",
    "Blizzard_CombatLog",
    "Blizzard_CombatText",
    "Blizzard_DebugTools",
    "Blizzard_GlyphUI",
    "Blizzard_GMChatUI",
    "Blizzard_GMSurveyUI",
    "Blizzard_GuildBankUI",
    "Blizzard_InspectUI",
    "Blizzard_ItemSocketingUI",
    "Blizzard_MacroUI",
    "Blizzard_RaidUI",
    "Blizzard_TalentUI",
    "Blizzard_TimeManager",
    "Blizzard_TokenUI",
    "Blizzard_TradeSkillUI",
    "Blizzard_TrainerUI",
}

local function LoadShippedAddOns()
    local rows = {}
    local loadedCount = 0
    for _, name in ipairs(SHIPPED_ADDONS) do
        local loaded = not not IsAddOnLoaded(name)
        local reason
        if not loaded then
            local result
            result, reason = LoadAddOn(name)
            loaded = not not result or not not IsAddOnLoaded(name)
        end
        if loaded then
            loadedCount = loadedCount + 1
        end
        table.insert(rows, {
            name = name,
            loaded = loaded,
            reason = reason,
        })
    end
    return rows, loadedCount, #SHIPPED_ADDONS
end

local function CaptureGlobals(loadShipped)
    local addons = {}
    local loadedAddOns = 0
    local shippedAddOns = 0
    if loadShipped then
        addons, loadedAddOns, shippedAddOns = LoadShippedAddOns()
    end

    local keys = {}
    for name, value in pairs(_G) do
        if type(name) == "string" then
            table.insert(keys, { t = type(value), name = name })
        end
    end
    table.sort(keys, function(a, b) return a.name < b.name end)
    keys.count = #keys

    local version, build, date, toc = GetBuildInfo()
    BenillaReferenceCapture = {
        globals = keys,
        shipped_addons = addons,
        shipped_addon_count = shippedAddOns,
        shipped_addon_loaded = loadedAddOns,
        shipped_addons_complete = loadShipped and loadedAddOns == shippedAddOns,
        client = {
            version = version,
            build = build,
            date = date,
            toc = toc,
        },
    }
    local status = ""
    if loadShipped then
        status = string.format("; shipped addons %d/%d loaded", loadedAddOns, shippedAddOns)
    end
    DEFAULT_CHAT_FRAME:AddMessage(string.format(
        "Benilla reference capture: %d globals recorded%s; log out or /reload to save.",
        #keys,
        status
    ))
    for _, addon in ipairs(addons) do
        if not addon.loaded then
            DEFAULT_CHAT_FRAME:AddMessage(string.format(
                "Benilla reference capture: failed to load %s (%s)",
                addon.name,
                tostring(addon.reason)
            ))
        end
    end
end

SLASH_BENILLAREFERENCECAPTURE1 = "/brcapture"
SlashCmdList.BENILLAREFERENCECAPTURE = function() CaptureGlobals(true) end
