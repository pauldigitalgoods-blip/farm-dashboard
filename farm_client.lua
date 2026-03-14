-- =============================================================================
-- ADOPT ME FARM CLIENT
-- Connects to dashboard server, syncs inventory, polls for config
-- Paste SERVER_URL after you deploy to Railway
-- =============================================================================

local SERVER_URL = "https://YOUR-APP.railway.app"  -- paste your Railway URL here

-- =============================================================================
-- SERVICES
-- =============================================================================
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local player = Players.LocalPlayer

local cd = require(ReplicatedStorage.ClientModules.Core.ClientData)
local inventorydb = require(ReplicatedStorage.ClientDB.Inventory.InventoryDB)
local Fsys = require(ReplicatedStorage:WaitForChild("Fsys"))

-- =============================================================================
-- CONFIG (gets overwritten by server every 30s)
-- =============================================================================
getgenv().farmConfig = getgenv().farmConfig or {
    trade_target = "23nuns",
    trade_legendaries = true,
    trade_mega_neons = true,
    trade_neons = false,
    trade_full_growns = true,
    trade_newborns = false,
    trade_gifts = true,
    trade_food = false,
    trade_pet_wear = false,
    trade_cocoadiles = true,
    auto_buy = {},
    scan_interval = 5,
    join_wait = 30,
    force_trade = false,
}

-- =============================================================================
-- HTTP HELPERS
-- =============================================================================
local function post(endpoint, data)
    local req = http_request or request or (syn and syn.request) or (fluxus and fluxus.request)
    if not req then return nil end
    local ok, result = pcall(function()
        return req({
            Url = SERVER_URL .. endpoint,
            Method = "POST",
            Headers = {["Content-Type"] = "application/json"},
            Body = HttpService:JSONEncode(data)
        })
    end)
    if ok and result and result.Body then
        local ok2, parsed = pcall(HttpService.JSONDecode, HttpService, result.Body)
        if ok2 then return parsed end
    end
    return nil
end

local function get(endpoint)
    local req = http_request or request or (syn and syn.request) or (fluxus and fluxus.request)
    if not req then return nil end
    local ok, result = pcall(function()
        return req({ Url = SERVER_URL .. endpoint, Method = "GET" })
    end)
    if ok and result and result.Body then
        local ok2, parsed = pcall(HttpService.JSONDecode, HttpService, result.Body)
        if ok2 then return parsed end
    end
    return nil
end

-- =============================================================================
-- LOG TO SERVER
-- =============================================================================
local function logAction(message)
    print("[LOG] " .. message)
    task.spawn(post, "/log", {
        username = player.Name,
        message = message
    })
end

-- =============================================================================
-- BUILD INVENTORY SNAPSHOT
-- =============================================================================
local function buildInventory()
    local ok, inv = pcall(cd.get, "inventory")
    if not ok or not inv then return {} end

    local snapshot = {}

    -- Pets with rarity info
    snapshot.pets = {}
    for uid, d in pairs(inv.pets or {}) do
        if type(d) == "table" then
            local id = tostring(d.id or d.kind or "")
            local kind = tostring(d.kind or d.id or "")
            local props = type(d.properties) == "table" and d.properties or {}
            local petInfo = inventorydb.pets and inventorydb.pets[id]
            local rarity = petInfo and petInfo.rarity or "common"

            snapshot.pets[uid] = {
                id = id,
                kind = kind,
                rarity = rarity:lower(),
                age = tonumber(props.age) or 0,
                is_neon = props.is_neon == true or props.neon == true,
                is_mega = props.is_mega == true or props.mega == true,
                hatched = (props.hatched or d.hatched or 0) > 0,
            }
        end
    end

    -- Food
    snapshot.food = {}
    for uid, d in pairs(inv.food or {}) do
        if type(d) == "table" then
            snapshot.food[uid] = { id = tostring(d.id or d.kind or ""), kind = tostring(d.kind or d.id or "") }
        end
    end

    -- Gifts
    snapshot.gifts = {}
    for uid, d in pairs(inv.gifts or {}) do
        if type(d) == "table" then
            snapshot.gifts[uid] = { id = tostring(d.id or d.kind or "") }
        end
    end

    -- Pet accessories / pet wear
    snapshot.pet_accessories = {}
    for uid, d in pairs(inv.pet_accessories or {}) do
        if type(d) == "table" then
            snapshot.pet_accessories[uid] = { id = tostring(d.id or d.kind or "") }
        end
    end

    return snapshot
end

-- =============================================================================
-- GET CURRENCY
-- =============================================================================
local function getCurrency()
    local key = getgenv().farmConfig.currency_key or "eggs.2026"
    local ok, data = pcall(cd.get_data)
    if ok and data then
        local pd = data[player.Name] or {}
        -- Direct key
        local val = tonumber(pd[key])
        if val then return val end
        -- Scan for any egg-related key with big value
        for k, v in pairs(pd) do
            if tostring(k):lower():find("egg") and type(v) == "number" and v > 100 then
                return v
            end
        end
    end
    return 0
end

-- =============================================================================
-- PING SERVER — sends full inventory + currency
-- =============================================================================
local function pingServer()
    local inv = buildInventory()
    local currency = getCurrency()

    local result = post("/ping", {
        username = player.Name,
        display_name = player.Name,
        inventory = inv,
        currency = currency,
        currency_key = getgenv().farmConfig.currency_key or "eggs.2026",
        last_action = ""
    })

    -- Server returns latest config on every ping
    if result and result.config then
        getgenv().farmConfig = result.config
        print("[CONFIG] Updated from server")
    end
end

-- =============================================================================
-- POLL CONFIG — checks every 30s for changes
-- =============================================================================
local function pollConfig()
    local cfg = get("/config/" .. player.Name)
    if cfg then
        getgenv().farmConfig = cfg

        -- Handle force_trade command
        if cfg.force_trade then
            print("[CONFIG] Force trade command received")
            logAction("Force trade command received from dashboard")
            -- Signal to trader script
            getgenv().forceTrade = true
            -- Clear the flag on server
            cfg.force_trade = false
            post("/dashboard/config/" .. player.Name, cfg)
        end
    end
end

-- =============================================================================
-- AUTO BUY — checks items in config and buys them
-- =============================================================================
local function doAutoBuy()
    local autoBuy = getgenv().farmConfig.auto_buy or {}
    if #autoBuy == 0 then return end

    -- Restore remotes first
    pcall(function()
        local RC = require(ReplicatedStorage.ClientModules.Core.RouterClient.RouterClient)
        local upv = debug.getupvalue(RC.init, 7)
        if type(upv) == "table" then
            for realName, remote in pairs(upv) do
                if typeof(remote) == "Instance" then remote.Name = realName end
            end
        end
    end)

    local API = ReplicatedStorage:FindFirstChild("API")
    if not API then return end

    for _, item in ipairs(autoBuy) do
        if not item.enabled then continue end

        -- Get currency and check if we can afford
        local currency = getCurrency()
        local cost = tonumber(item.cost) or 0
        if cost > 0 and currency < cost then
            print("[BUY] Not enough currency for " .. item.name .. " (" .. currency .. " / " .. cost .. ")")
            continue
        end

        local canBuy = cost > 0 and math.min(math.floor(currency / cost), item.max_count or 5) or 1
        if canBuy <= 0 then continue end

        local remote = API:FindFirstChild(item.remote)
        if not remote then
            warn("[BUY] Remote not found: " .. tostring(item.remote))
            continue
        end

        local ok = pcall(function()
            remote:InvokeServer(item.category, item.item_id, { buy_count = canBuy })
        end)

        if ok then
            local msg = "Bought " .. canBuy .. "x " .. item.name
            print("[BUY] " .. msg)
            logAction(msg)
        else
            warn("[BUY] Failed: " .. item.name)
        end

        task.wait(1)
    end
end

-- =============================================================================
-- MAIN LOOPS
-- =============================================================================

-- Initial ping on startup
task.wait(2)
print("[FARM CLIENT] Connecting to dashboard...")
pingServer()
logAction("Script started")
print("[FARM CLIENT] Connected as " .. player.Name)

-- Ping loop — every 2 minutes
task.spawn(function()
    while true do
        task.wait(120)
        pcall(pingServer)
    end
end)

-- Config poll loop — every 30s
task.spawn(function()
    while true do
        task.wait(30)
        pcall(pollConfig)
    end
end)

-- Auto buy loop — every 30s
task.spawn(function()
    while true do
        task.wait(30)
        pcall(doAutoBuy)
    end
end)

print("[FARM CLIENT] All loops running")
print("[FARM CLIENT] Dashboard: " .. SERVER_URL)
