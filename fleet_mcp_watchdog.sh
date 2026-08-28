#!/bin/bash
# fleet-data MCP watchdog — auto-restart on crash + @reboot (local-data-mcp-server skill)
PORT=8004
PID_FILE="/srv/build/fleet-dashboard/fleet-mcp.pid"
LOG_FILE="/srv/build/fleet-dashboard/fleet-mcp.log"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        if curl -sf "http://localhost:$PORT/health" -o /dev/null --max-time 2; then
            exit 0
        fi
        kill "$OLD_PID" 2>/dev/null
        sleep 1
    fi
fi

cd /srv/build/fleet-dashboard
FLEET_MCP_TOKEN="fleet-mcp-brick-b94d2f18" nohup ./mcp-venv/bin/python fleet_data_mcp_server.py >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"
sleep 3
if kill -0 "$NEW_PID" 2>/dev/null; then
    echo "[$(date)] fleet-data MCP started (PID: $NEW_PID)" >> "$LOG_FILE"
else
    echo "[$(date)] FAILED to start" >> "$LOG_FILE"
fi
