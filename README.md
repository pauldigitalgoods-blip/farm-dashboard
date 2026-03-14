# Adopt Me Farm Dashboard

## Files
- `server.py` — Python Flask server (deploy to Railway)
- `dashboard.html` — Web dashboard (served by the server)
- `farm_client.lua` — Lua script (run on each farming account)
- `requirements.txt` — Python dependencies
- `Procfile` — Railway start command

## Deploy to Railway (instructions for deployment)

1. Go to https://railway.app and sign up with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
   - OR click "New Project" → "Empty Project" → add service → upload files
3. Upload all files from this folder
4. Railway will auto-detect Python and install requirements.txt
5. Click "Deploy"
6. Go to Settings → Networking → Generate Domain
7. Your URL will be something like: https://yourapp.railway.app

## Configure Lua script

In `farm_client.lua`, change line 7:
```lua
local SERVER_URL = "https://YOUR-APP.railway.app"
```
Replace with your actual Railway URL.

## How it works

1. Each farming account runs `farm_client.lua`
2. On startup it registers with the server and sends inventory
3. Every 2 minutes it pings the server with updated inventory + currency
4. Every 30 seconds it checks for config changes from the dashboard
5. Open your Railway URL in browser to see the dashboard
6. Edit configs per account or bulk-select multiple accounts

## Endpoints

POST /ping — script sends inventory data
POST /log — script sends activity logs  
GET  /config/{username} — script polls for config
GET  /dashboard/accounts — dashboard reads all accounts
GET  /dashboard/logs/{username} — dashboard reads logs
POST /dashboard/config/{username} — dashboard saves config
POST /dashboard/config/bulk — dashboard saves config for multiple accounts
POST /dashboard/force_trade/{username} — dashboard queues force trade
GET  / — serves dashboard.html

## Notes

- Accounts appear automatically when they run the script
- "Online" = pinged within last 3 minutes
- Database is SQLite, stored as farm.db on the server
- All config changes take effect within 30 seconds (next poll)
- Force trade command is picked up on next config poll
